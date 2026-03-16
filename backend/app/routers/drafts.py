"""
Drafts router for Smart Pipeline draft/approval system.
Allows users to review, approve, edit, and reject AI-generated messages
before they are sent to LinkedIn contacts.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Lead
from ..models.user import User
from ..models.draft_message import DraftMessage, DraftStatus
from ..models.sequence import (
    Sequence, SequenceStep, SequenceEnrollment,
    EnrollmentStatus, SequenceMode,
)
from ..services.unipile_service import UnipileService
from ..routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


class ApproveBody(BaseModel):
    message: Optional[str] = None  # Edited message, if user changed it


class RejectBody(BaseModel):
    reason: Optional[str] = None


class DraftResponse(BaseModel):
    id: str
    enrollment_id: str
    lead_id: str
    sequence_id: str
    pipeline_phase: Optional[str] = None
    step_order: Optional[int] = None
    generated_message: str
    final_message: Optional[str] = None
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    sent_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    # Joined fields
    lead_name: str
    lead_company: Optional[str] = None
    lead_job_title: Optional[str] = None
    sequence_name: str


def _draft_to_response(draft: DraftMessage, lead: Lead, sequence: Sequence) -> dict:
    return {
        "id": draft.id,
        "enrollment_id": draft.enrollment_id,
        "lead_id": draft.lead_id,
        "sequence_id": draft.sequence_id,
        "pipeline_phase": draft.pipeline_phase,
        "step_order": draft.step_order,
        "generated_message": draft.generated_message,
        "final_message": draft.final_message,
        "status": draft.status,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "reviewed_at": draft.reviewed_at.isoformat() if draft.reviewed_at else None,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
        "rejection_reason": draft.rejection_reason,
        "lead_name": lead.display_name if lead else "Unknown",
        "lead_company": lead.company_name if lead else None,
        "lead_job_title": lead.job_title if lead else None,
        "sequence_name": sequence.name if sequence else "Unknown",
    }


@router.get("/count")
def get_draft_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of pending drafts (for nav badge)."""
    count = db.query(DraftMessage).filter(
        DraftMessage.user_id == current_user.id,
        DraftMessage.status == DraftStatus.PENDING.value
    ).count()
    return {"count": count}


@router.get("/")
def list_drafts(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all drafts for the current user, optionally filtered by status."""
    query = db.query(DraftMessage).filter(
        DraftMessage.user_id == current_user.id
    )
    if status:
        query = query.filter(DraftMessage.status == status).order_by(DraftMessage.created_at.desc())
    else:
        # Default: show pending first
        query = query.order_by(
            DraftMessage.status != DraftStatus.PENDING.value,
            DraftMessage.created_at.desc()
        )

    drafts = query.limit(100).all()

    results = []
    for draft in drafts:
        lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
        sequence = db.query(Sequence).filter(Sequence.id == draft.sequence_id).first()
        results.append(_draft_to_response(draft, lead, sequence))

    return results




@router.get('/pending-for-chat')
def get_pending_draft_for_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending draft for a lead by their LinkedIn chat ID.
    Used by Inbox to pre-fill reply with pipeline draft."""
    lead = db.query(Lead).filter(
        Lead.user_id == current_user.id,
        Lead.linkedin_chat_id == chat_id
    ).first()
    if not lead:
        return None

    draft = db.query(DraftMessage).filter(
        DraftMessage.lead_id == lead.id,
        DraftMessage.user_id == current_user.id,
        DraftMessage.status == DraftStatus.PENDING.value
    ).order_by(DraftMessage.created_at.desc()).first()
    if not draft:
        return None

    sequence = db.query(Sequence).filter(Sequence.id == draft.sequence_id).first()
    return _draft_to_response(draft, lead, sequence)


@router.get("/{draft_id}")
def get_draft(
    draft_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full draft details."""
    draft = db.query(DraftMessage).filter(
        DraftMessage.id == draft_id,
        DraftMessage.user_id == current_user.id
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
    sequence = db.query(Sequence).filter(Sequence.id == draft.sequence_id).first()
    return _draft_to_response(draft, lead, sequence)


@router.post("/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    body: Optional[ApproveBody] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve a draft and send it via LinkedIn."""
    draft = db.query(DraftMessage).filter(
        DraftMessage.id == draft_id,
        DraftMessage.user_id == current_user.id,
        DraftMessage.status == DraftStatus.PENDING.value
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Pending draft not found")

    # Use edited message if provided
    final_message = body.message if body and body.message else draft.generated_message
    draft.final_message = final_message
    draft.status = DraftStatus.APPROVED.value
    draft.reviewed_at = datetime.utcnow()

    # Send via Unipile
    lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
    if not lead or not lead.linkedin_chat_id:
        raise HTTPException(status_code=400, detail="Lead has no LinkedIn chat")

    unipile = UnipileService()
    result = await unipile.send_message(lead.linkedin_chat_id, final_message)

    if result.get("success"):
        draft.status = DraftStatus.SENT.value
        draft.sent_at = datetime.utcnow()

        # Resume enrollment
        enrollment = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.id == draft.enrollment_id
        ).first()
        if enrollment:
            enrollment.status = EnrollmentStatus.ACTIVE.value
            enrollment.store_message(draft.step_order or enrollment.current_step_order, final_message)
            enrollment.last_step_completed_at = datetime.utcnow()
            enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
            enrollment.messages_in_phase = (enrollment.messages_in_phase or 0) + 1

            # Set next step due: 48h to check if they reply
            # If no reply in 48h, system will generate another follow-up draft
            enrollment.next_step_due_at = datetime.utcnow() + timedelta(hours=48)

        lead.last_message_at = datetime.utcnow()
        lead.awaiting_reply = True
        db.commit()

        logger.info(f"[Drafts] Approved and sent draft for {lead.display_name} (phase: {draft.pipeline_phase})")
        return {"status": "sent", "draft_id": draft.id}
    else:
        draft.status = DraftStatus.PENDING.value  # Revert to pending
        draft.reviewed_at = None
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to send: {result.get('error', 'Unknown')}")


@router.post("/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    body: Optional[RejectBody] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a draft. Enrollment stays paused until user decides."""
    draft = db.query(DraftMessage).filter(
        DraftMessage.id == draft_id,
        DraftMessage.user_id == current_user.id,
        DraftMessage.status == DraftStatus.PENDING.value
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Pending draft not found")

    draft.status = DraftStatus.REJECTED.value
    draft.reviewed_at = datetime.utcnow()
    draft.rejection_reason = body.reason if body else None
    db.commit()

    logger.info(f"[Drafts] Draft rejected for lead {draft.lead_id}")
    return {"status": "rejected", "draft_id": draft.id}


@router.post("/{draft_id}/regenerate")
def regenerate_draft(
    draft_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate a rejected draft with a new AI message."""
    draft = db.query(DraftMessage).filter(
        DraftMessage.id == draft_id,
        DraftMessage.user_id == current_user.id,
        DraftMessage.status == DraftStatus.REJECTED.value
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Rejected draft not found")

    lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
    sequence = db.query(Sequence).filter(Sequence.id == draft.sequence_id).first()
    enrollment = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.id == draft.enrollment_id
    ).first()

    if not lead or not sequence or not enrollment:
        raise HTTPException(status_code=404, detail="Related data not found")

    # Get conversation history
    import asyncio
    from ..services.unipile_service import UnipileService
    from ..services.claude_service import ClaudeService
    from ..services.sequence_scheduler import _get_business_context, _get_lead_data, _format_conversation

    unipile = UnipileService()
    conversation_history = ""
    if lead.linkedin_chat_id:
        try:
            loop = asyncio.get_event_loop()
            chat_result = loop.run_until_complete(unipile.get_chat_messages(lead.linkedin_chat_id, limit=20))
            conversation_history = _format_conversation(chat_result.get("data", {})) if chat_result.get("success") else ""
        except Exception:
            pass

    claude = ClaudeService()
    sender_context = _get_business_context(db, sequence.business_id)
    lead_data = _get_lead_data(lead)

    new_message = claude.generate_smart_pipeline_message(
        lead_data=lead_data,
        sender_context=sender_context,
        conversation_history=conversation_history,
        current_phase=draft.pipeline_phase or "apertura",
        rejection_context=f"Previous message was rejected: {draft.rejection_reason or 'no reason given'}"
    )

    # Create new draft
    import uuid
    new_draft = DraftMessage(
        id=str(uuid.uuid4()),
        enrollment_id=draft.enrollment_id,
        lead_id=draft.lead_id,
        sequence_id=draft.sequence_id,
        user_id=current_user.id,
        pipeline_phase=draft.pipeline_phase,
        step_order=draft.step_order,
        generated_message=new_message,
        status=DraftStatus.PENDING.value,
    )
    db.add(new_draft)
    db.commit()

    lead_obj = db.query(Lead).filter(Lead.id == new_draft.lead_id).first()
    seq_obj = db.query(Sequence).filter(Sequence.id == new_draft.sequence_id).first()
    return _draft_to_response(new_draft, lead_obj, seq_obj)
