"""
Sequences router - CRUD for automated outreach sequences.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Lead, User
from ..models.sequence import (
    Sequence, SequenceStep, SequenceEnrollment,
    SequenceStatus, StepType, EnrollmentStatus
)
from ..schemas.sequence import (
    SequenceCreate, SequenceUpdate, SequenceStatusUpdate,
    SequenceStepCreate, SequenceStepUpdate, StepReorderRequest,
    EnrollLeadsRequest, UnenrollLeadsRequest,
    SequenceResponse, SequenceListResponse, SequenceStepResponse,
    EnrollmentResponse, SequenceStatsResponse, SequenceDashboardResponse,
)

router = APIRouter(prefix="/api/sequences", tags=["sequences"])


# ─── Sequence CRUD ───────────────────────────────────────────────────────────

@router.get("/", response_model=list[SequenceListResponse])
async def list_sequences(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sequences for the current user."""
    query = db.query(Sequence).filter(Sequence.user_id == current_user.id)
    if status:
        query = query.filter(Sequence.status == status)
    sequences = query.order_by(Sequence.updated_at.desc()).all()

    result = []
    for seq in sequences:
        steps_count = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).count()
        item = SequenceListResponse(
            id=seq.id,
            name=seq.name,
            description=seq.description,
            status=seq.status,
            message_strategy=seq.message_strategy,
            total_enrolled=seq.total_enrolled or 0,
            active_enrolled=seq.active_enrolled or 0,
            completed_count=seq.completed_count or 0,
            replied_count=seq.replied_count or 0,
            steps_count=steps_count,
            created_at=seq.created_at,
            updated_at=seq.updated_at,
        )
        result.append(item)
    return result


@router.get("/dashboard", response_model=SequenceDashboardResponse)
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary stats across all sequences."""
    sequences = db.query(Sequence).filter(Sequence.user_id == current_user.id).all()

    total_enrolled = sum(s.total_enrolled or 0 for s in sequences)
    total_active = sum(s.active_enrolled or 0 for s in sequences)
    total_replied = sum(s.replied_count or 0 for s in sequences)
    total_completed = sum(s.completed_count or 0 for s in sequences)
    active_sequences = sum(1 for s in sequences if s.status == SequenceStatus.ACTIVE.value)

    overall_reply_rate = (total_replied / total_enrolled * 100) if total_enrolled > 0 else 0

    seq_list = []
    for seq in sequences:
        steps_count = db.query(SequenceStep).filter(SequenceStep.sequence_id == seq.id).count()
        seq_list.append(SequenceListResponse(
            id=seq.id,
            name=seq.name,
            description=seq.description,
            status=seq.status,
            message_strategy=seq.message_strategy,
            total_enrolled=seq.total_enrolled or 0,
            active_enrolled=seq.active_enrolled or 0,
            completed_count=seq.completed_count or 0,
            replied_count=seq.replied_count or 0,
            steps_count=steps_count,
            created_at=seq.created_at,
            updated_at=seq.updated_at,
        ))

    return SequenceDashboardResponse(
        total_sequences=len(sequences),
        active_sequences=active_sequences,
        total_enrolled=total_enrolled,
        total_active=total_active,
        total_replied=total_replied,
        total_completed=total_completed,
        overall_reply_rate=round(overall_reply_rate, 1),
        sequences=seq_list,
    )


@router.post("/", response_model=SequenceResponse)
async def create_sequence(
    data: SequenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new sequence with optional steps."""
    sequence = Sequence(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        status=SequenceStatus.DRAFT.value,
        business_id=data.business_id,
        message_strategy=data.message_strategy,
        user_id=current_user.id,
    )
    db.add(sequence)

    # Create steps if provided
    for i, step_data in enumerate(data.steps, start=1):
        step = SequenceStep(
            id=str(uuid.uuid4()),
            sequence_id=sequence.id,
            step_order=i,
            step_type=step_data.step_type,
            delay_days=step_data.delay_days,
            prompt_context=step_data.prompt_context,
        )
        db.add(step)

    db.commit()
    db.refresh(sequence)
    return sequence


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a sequence with its steps and stats."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return sequence


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: str,
    data: SequenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a sequence's basic info."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sequence, field, value)

    sequence.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sequence)
    return sequence


@router.delete("/{sequence_id}")
async def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sequence. Fails if there are active enrollments."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    active = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.sequence_id == sequence_id,
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value
    ).count()
    if active > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {active} leads are actively enrolled. Pause or archive instead."
        )

    # Clear active_sequence_id from any leads
    db.query(Lead).filter(Lead.active_sequence_id == sequence_id).update(
        {"active_sequence_id": None}, synchronize_session=False
    )

    db.delete(sequence)
    db.commit()
    return {"message": "Sequence deleted"}


@router.patch("/{sequence_id}/status", response_model=SequenceResponse)
async def update_sequence_status(
    sequence_id: str,
    data: SequenceStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate, pause, or archive a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Validate: must have at least one step to activate
    if data.status == SequenceStatus.ACTIVE.value:
        steps = db.query(SequenceStep).filter(SequenceStep.sequence_id == sequence_id).count()
        if steps == 0:
            raise HTTPException(status_code=400, detail="Add at least one step before activating")

    # If pausing, pause all active enrollments
    if data.status == SequenceStatus.PAUSED.value:
        db.query(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value
        ).update({"status": EnrollmentStatus.PAUSED.value}, synchronize_session=False)

    # If reactivating from paused, reactivate paused enrollments
    if data.status == SequenceStatus.ACTIVE.value and sequence.status == SequenceStatus.PAUSED.value:
        db.query(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.status == EnrollmentStatus.PAUSED.value
        ).update({"status": EnrollmentStatus.ACTIVE.value}, synchronize_session=False)

    sequence.status = data.status
    sequence.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sequence)
    return sequence


# ─── Step Management ─────────────────────────────────────────────────────────

@router.post("/{sequence_id}/steps", response_model=SequenceStepResponse)
async def add_step(
    sequence_id: str,
    data: SequenceStepCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a step to a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Get next step order
    max_order = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id
    ).count()

    step = SequenceStep(
        id=str(uuid.uuid4()),
        sequence_id=sequence_id,
        step_order=max_order + 1,
        step_type=data.step_type,
        delay_days=data.delay_days,
        prompt_context=data.prompt_context,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.put("/{sequence_id}/steps/{step_id}", response_model=SequenceStepResponse)
async def update_step(
    sequence_id: str,
    step_id: str,
    data: SequenceStepUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a step's configuration."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    step = db.query(SequenceStep).filter(
        SequenceStep.id == step_id,
        SequenceStep.sequence_id == sequence_id
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(step, field, value)

    step.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(step)
    return step


@router.delete("/{sequence_id}/steps/{step_id}")
async def delete_step(
    sequence_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a step from a sequence and reorder remaining steps."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    step = db.query(SequenceStep).filter(
        SequenceStep.id == step_id,
        SequenceStep.sequence_id == sequence_id
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    deleted_order = step.step_order
    db.delete(step)

    # Reorder remaining steps
    remaining = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id,
        SequenceStep.step_order > deleted_order
    ).order_by(SequenceStep.step_order).all()

    for s in remaining:
        s.step_order -= 1

    db.commit()
    return {"message": "Step deleted"}


@router.put("/{sequence_id}/steps/reorder")
async def reorder_steps(
    sequence_id: str,
    data: StepReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder steps in a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    for order, step_id in enumerate(data.step_ids, start=1):
        step = db.query(SequenceStep).filter(
            SequenceStep.id == step_id,
            SequenceStep.sequence_id == sequence_id
        ).first()
        if step:
            step.step_order = order

    db.commit()
    return {"message": "Steps reordered"}


# ─── Enrollment ──────────────────────────────────────────────────────────────

@router.post("/{sequence_id}/enroll")
async def enroll_leads(
    sequence_id: str,
    data: EnrollLeadsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll leads into a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    if sequence.status not in [SequenceStatus.ACTIVE.value, SequenceStatus.DRAFT.value]:
        raise HTTPException(status_code=400, detail="Sequence must be active or draft to enroll leads")

    # Get the first step to set initial due time
    first_step = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id,
        SequenceStep.step_order == 1
    ).first()
    if not first_step:
        raise HTTPException(status_code=400, detail="Sequence has no steps")

    enrolled = 0
    skipped = 0
    errors = []

    for lead_id in data.lead_ids:
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.user_id == current_user.id
        ).first()

        if not lead:
            errors.append(f"Lead {lead_id} not found")
            continue

        # Check if already enrolled in any active sequence
        if lead.active_sequence_id:
            skipped += 1
            errors.append(f"{lead.display_name} already in a sequence")
            continue

        # Check if already enrolled in this specific sequence
        existing = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.lead_id == lead_id,
            SequenceEnrollment.sequence_id == sequence_id
        ).first()
        if existing:
            skipped += 1
            errors.append(f"{lead.display_name} already enrolled in this sequence")
            continue

        # Create enrollment
        enrollment = SequenceEnrollment(
            id=str(uuid.uuid4()),
            sequence_id=sequence_id,
            lead_id=lead_id,
            status=EnrollmentStatus.ACTIVE.value,
            current_step_order=1,
            next_step_due_at=datetime.utcnow(),  # Execute first step immediately
            user_id=current_user.id,
        )
        db.add(enrollment)

        # Mark lead as in sequence
        lead.active_sequence_id = sequence_id
        enrolled += 1

    # Update sequence stats
    sequence.total_enrolled = (sequence.total_enrolled or 0) + enrolled
    sequence.active_enrolled = (sequence.active_enrolled or 0) + enrolled

    db.commit()

    return {
        "enrolled": enrolled,
        "skipped": skipped,
        "errors": errors[:10],  # Limit error messages
        "total_in_sequence": sequence.total_enrolled,
    }


@router.post("/{sequence_id}/unenroll")
async def unenroll_leads(
    sequence_id: str,
    data: UnenrollLeadsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove leads from a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    unenrolled = 0
    for lead_id in data.lead_ids:
        enrollment = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.lead_id == lead_id,
            SequenceEnrollment.status.in_([EnrollmentStatus.ACTIVE.value, EnrollmentStatus.PAUSED.value])
        ).first()

        if enrollment:
            enrollment.status = EnrollmentStatus.WITHDRAWN.value
            enrollment.next_step_due_at = None
            sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)

            # Clear lead's active sequence
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                lead.active_sequence_id = None
            unenrolled += 1

    db.commit()
    return {"unenrolled": unenrolled}


@router.get("/{sequence_id}/enrollments", response_model=list[EnrollmentResponse])
async def list_enrollments(
    sequence_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List enrollments for a sequence with lead info."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    query = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.sequence_id == sequence_id
    )
    if status:
        query = query.filter(SequenceEnrollment.status == status)

    enrollments = query.order_by(SequenceEnrollment.enrolled_at.desc()).all()

    result = []
    for e in enrollments:
        lead = db.query(Lead).filter(Lead.id == e.lead_id).first()
        result.append(EnrollmentResponse(
            id=e.id,
            sequence_id=e.sequence_id,
            lead_id=e.lead_id,
            status=e.status,
            current_step_order=e.current_step_order,
            next_step_due_at=e.next_step_due_at,
            last_step_completed_at=e.last_step_completed_at,
            replied_at=e.replied_at,
            completed_at=e.completed_at,
            failed_reason=e.failed_reason,
            enrolled_at=e.enrolled_at,
            updated_at=e.updated_at,
            lead_name=lead.display_name if lead else None,
            lead_company=lead.company_name if lead else None,
            lead_job_title=lead.job_title if lead else None,
            lead_status=lead.status if lead else None,
            lead_score_label=lead.score_label if lead else None,
        ))

    return result


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.get("/{sequence_id}/stats", response_model=SequenceStatsResponse)
async def get_sequence_stats(
    sequence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed stats for a sequence."""
    sequence = db.query(Sequence).filter(
        Sequence.id == sequence_id,
        Sequence.user_id == current_user.id
    ).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    enrollments = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.sequence_id == sequence_id
    ).all()

    total = len(enrollments)
    active = sum(1 for e in enrollments if e.status == EnrollmentStatus.ACTIVE.value)
    completed = sum(1 for e in enrollments if e.status == EnrollmentStatus.COMPLETED.value)
    replied = sum(1 for e in enrollments if e.status == EnrollmentStatus.REPLIED.value)
    failed = sum(1 for e in enrollments if e.status == EnrollmentStatus.FAILED.value)
    paused = sum(1 for e in enrollments if e.status == EnrollmentStatus.PAUSED.value)
    withdrawn = sum(1 for e in enrollments if e.status == EnrollmentStatus.WITHDRAWN.value)

    reply_rate = (replied / total * 100) if total > 0 else 0
    completion_rate = (completed / total * 100) if total > 0 else 0

    # Steps breakdown
    steps = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence_id
    ).order_by(SequenceStep.step_order).all()

    steps_breakdown = []
    for step in steps:
        reached = sum(1 for e in enrollments if e.current_step_order >= step.step_order)
        step_completed = sum(1 for e in enrollments if e.current_step_order > step.step_order)
        steps_breakdown.append({
            "step_order": step.step_order,
            "step_type": step.step_type,
            "reached": reached,
            "completed": step_completed,
        })

    return SequenceStatsResponse(
        sequence_id=sequence.id,
        sequence_name=sequence.name,
        total_enrolled=total,
        active=active,
        completed=completed,
        replied=replied,
        failed=failed,
        paused=paused,
        withdrawn=withdrawn,
        reply_rate=round(reply_rate, 1),
        completion_rate=round(completion_rate, 1),
        steps_breakdown=steps_breakdown,
    )
