"""
Router for AutoOutreach experiments — self-improving connection messages.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..models.experiment import OutreachExperiment, OutreachExperimentLead
from ..models.lead import Lead
from ..schemas.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentDetailResponse,
    ExperimentLeadResponse,
    ExperimentEvaluateResponse,
    ExperimentProposeResponse,
    ExperimentDashboardResponse,
)
from ..services.experiment_service import ExperimentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("/dashboard", response_model=ExperimentDashboardResponse)
def get_experiment_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get experiment dashboard with all stats and history."""
    service = ExperimentService()
    stats = service.get_dashboard_stats(db, current_user.id)

    # Convert experiment objects to response models
    experiment_responses = []
    for exp in stats["experiments"]:
        experiment_responses.append(ExperimentResponse.model_validate(exp))

    return ExperimentDashboardResponse(
        total_experiments=stats["total_experiments"],
        kept_count=stats["kept_count"],
        discarded_count=stats["discarded_count"],
        running_count=stats["running_count"],
        current_baseline_rate=stats["current_baseline_rate"],
        best_ever_rate=stats["best_ever_rate"],
        total_improvement=stats["total_improvement"],
        experiments=experiment_responses,
    )


@router.get("/", response_model=List[ExperimentResponse])
def list_experiments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all experiments for the current user."""
    experiments = (
        db.query(OutreachExperiment)
        .filter(OutreachExperiment.user_id == current_user.id)
        .order_by(desc(OutreachExperiment.experiment_number))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return experiments


@router.get("/active", response_model=ExperimentResponse)
def get_active_experiment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the currently running experiment."""
    service = ExperimentService()
    active = service.get_active_experiment(db, current_user.id)
    if not active:
        raise HTTPException(status_code=404, detail="No active experiment")
    return active


@router.get("/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment_detail(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed experiment with all lead outcomes."""
    exp = db.query(OutreachExperiment).filter(
        OutreachExperiment.id == experiment_id,
        OutreachExperiment.user_id == current_user.id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get leads with denormalized info
    exp_leads = db.query(OutreachExperimentLead).filter(
        OutreachExperimentLead.experiment_id == experiment_id
    ).all()

    leads_data = []
    for el in exp_leads:
        lead = db.query(Lead).filter(Lead.id == el.lead_id).first()
        leads_data.append(ExperimentLeadResponse(
            id=el.id,
            lead_id=el.lead_id,
            message_sent=el.message_sent,
            sent_at=el.sent_at,
            accepted=el.accepted,
            accepted_at=el.accepted_at,
            responded=el.responded,
            responded_at=el.responded_at,
            lead_name=lead.display_name if lead else None,
            lead_company=lead.company_name if lead else None,
            lead_job_title=lead.job_title if lead else None,
        ))

    return ExperimentDetailResponse(
        **{k: v for k, v in ExperimentResponse.model_validate(exp).model_dump().items()},
        leads=leads_data,
    )


@router.post("/baseline", response_model=ExperimentResponse)
def create_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create the initial baseline experiment."""
    service = ExperimentService()

    # Check if baseline already exists
    existing = service.get_current_baseline(db, current_user.id)
    if existing and existing.decision == "baseline":
        raise HTTPException(status_code=400, detail="Baseline already exists. Use propose to create new experiments.")

    experiment = service.create_baseline(db, current_user.id)
    return experiment


@router.post("/", response_model=ExperimentResponse)
def create_experiment(
    data: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new experiment manually."""
    service = ExperimentService()

    if data.is_baseline:
        return service.create_baseline(db, current_user.id, data.prompt_template)

    prompt = data.prompt_template or service.get_active_prompt_template(db, current_user.id)

    try:
        experiment = service.create_experiment(
            db=db,
            user_id=current_user.id,
            name=data.experiment_name,
            hypothesis=data.hypothesis or "",
            prompt_template=prompt,
            change_description="Manual experiment",
            batch_size=data.batch_size,
        )
        return experiment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/start", response_model=ExperimentResponse)
def start_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a pending experiment (begin sending connections with its prompt)."""
    service = ExperimentService()
    try:
        return service.start_experiment(db, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{experiment_id}/evaluate", response_model=ExperimentEvaluateResponse)
def evaluate_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Evaluate an experiment and make KEEP/DISCARD decision."""
    exp = db.query(OutreachExperiment).filter(
        OutreachExperiment.id == experiment_id,
        OutreachExperiment.user_id == current_user.id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    service = ExperimentService()
    try:
        result = service.evaluate_experiment(db, experiment_id)
        return ExperimentEvaluateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/propose", response_model=ExperimentProposeResponse)
def propose_next_experiment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ask Claude to analyze past experiments and propose the next prompt variation."""
    service = ExperimentService()
    proposal = service.propose_next_experiment(db, current_user.id)
    return ExperimentProposeResponse(**proposal)


@router.post("/propose-and-create", response_model=ExperimentResponse)
def propose_and_create_experiment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """One-click: Claude proposes next experiment AND creates it ready to run."""
    service = ExperimentService()

    # Check no active experiment
    active = service.get_active_experiment(db, current_user.id)
    if active:
        raise HTTPException(
            status_code=400,
            detail=f"Experiment #{active.experiment_number} is still running. Evaluate it first."
        )

    # Get proposal
    proposal = service.propose_next_experiment(db, current_user.id)

    # Create experiment from proposal
    try:
        experiment = service.create_experiment(
            db=db,
            user_id=current_user.id,
            name=proposal["proposed_name"],
            hypothesis=proposal["hypothesis"],
            prompt_template=proposal["prompt_template"],
            change_description=proposal["change_description"],
        )
        return experiment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{experiment_id}")
def delete_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an experiment (only if pending or discarded)."""
    exp = db.query(OutreachExperiment).filter(
        OutreachExperiment.id == experiment_id,
        OutreachExperiment.user_id == current_user.id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status in ("running", "kept", "baseline"):
        raise HTTPException(status_code=400, detail=f"Cannot delete experiment in '{exp.status}' status")

    db.delete(exp)
    db.commit()
    return {"message": "Experiment deleted"}
