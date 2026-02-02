"""
Leads router for CRUD operations and AI actions.
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from ..database import get_db
from ..schemas.lead import (
    LeadResponse, LeadUpdate, LeadScoring, LeadListResponse,
    LeadStatusUpdate, LeadStatusInfo, LeadBulkStatusUpdate, LeadStatusEnum
)
from ..models import Lead, BusinessProfile
from ..models.lead import LeadStatus, LEAD_STATUS_CONFIG
from ..services.claude_service import ClaudeService
from ..services.verifier_service import VerifierService
from ..services.n8n_service import N8NService
from ..services.unipile_service import UnipileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("/", response_model=LeadListResponse)
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    score_label: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List leads with pagination and filters."""
    query = db.query(Lead)

    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if status:
        query = query.filter(Lead.status == status)
    if score_label:
        query = query.filter(Lead.score_label == score_label)

    total = query.count()

    leads = (
        query
        .order_by(desc(Lead.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return LeadListResponse(
        total=total,
        page=page,
        page_size=page_size,
        leads=[LeadResponse.model_validate(lead) for lead in leads]
    )


# NOTE: This route MUST come BEFORE /{lead_id} to avoid "statuses" being interpreted as a lead_id
@router.get("/statuses", response_model=List[LeadStatusInfo])
def get_available_statuses():
    """Get all available CRM statuses with their configuration."""
    statuses = []
    for status, config in LEAD_STATUS_CONFIG.items():
        statuses.append(LeadStatusInfo(
            value=status.value,
            label=config["label"],
            color=config["color"],
            order=config["order"]
        ))
    return sorted(statuses, key=lambda x: x.order)


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    """Get a single lead by ID."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: str, update: LeadUpdate, db: Session = Depends(get_db)):
    """Update a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)

    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    """Delete a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    db.delete(lead)
    db.commit()
    return {"message": "Lead deleted"}


@router.patch("/{lead_id}/status", response_model=LeadResponse)
def update_lead_status(
    lead_id: str,
    status_update: LeadStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update a lead's CRM status."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = status_update.status.value
    if status_update.notes:
        # Append to existing notes with timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_note = f"[{timestamp}] Status changed to {status_update.status.value}: {status_update.notes}"
        if lead.notes:
            lead.notes = f"{lead.notes}\n{new_note}"
        else:
            lead.notes = new_note

    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/status/bulk")
def bulk_update_status(
    bulk_update: LeadBulkStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update status for multiple leads at once."""
    updated = 0
    for lead_id in bulk_update.lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = bulk_update.status.value
            lead.updated_at = datetime.utcnow()
            updated += 1

    db.commit()
    return {"updated": updated, "status": bulk_update.status.value}


class NotesUpdate(BaseModel):
    """Request body for updating lead notes."""
    notes: str


@router.patch("/{lead_id}/notes", response_model=LeadResponse)
def update_lead_notes(
    lead_id: str,
    notes_update: NotesUpdate,
    db: Session = Depends(get_db)
):
    """Update a lead's notes."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.notes = notes_update.notes
    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/verify")
async def verify_emails(
    lead_ids: List[str],
    db: Session = Depends(get_db)
):
    """Verify emails for specified leads."""
    verifier = VerifierService()
    results = []

    for lead_id in lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead or not lead.email:
            continue

        result = await verifier.verify_email(lead.email)

        lead.email_verified = result["verified"]
        lead.email_status = result["status"]

        results.append({
            "lead_id": lead_id,
            "email": lead.email,
            **result
        })

    db.commit()

    return {"verified": len(results), "results": results}


@router.post("/qualify")
def qualify_leads(
    lead_ids: List[str],
    business_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Qualify/score leads using AI."""
    claude_service = ClaudeService()
    results = []

    # Get business context if provided
    business_context = None
    if business_id:
        profile = db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
        if profile:
            business_context = {
                "ideal_customer": profile.ideal_customer,
                "target_industries": profile.target_industries,
                "target_company_sizes": profile.target_company_sizes,
                "target_job_titles": profile.target_job_titles,
            }

    for lead_id in lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            continue

        lead_data = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "job_title": lead.job_title,
            "seniority_level": lead.seniority_level,
            "company_name": lead.company_name,
            "company_industry": lead.company_industry,
            "company_size": lead.company_size,
            "country": lead.country,
        }

        scoring = claude_service.score_lead(lead_data, business_context)

        lead.score = scoring.score
        lead.score_label = scoring.label
        lead.score_reason = scoring.reason

        results.append({
            "lead_id": lead_id,
            "score": scoring.score,
            "label": scoring.label,
            "reason": scoring.reason
        })

    db.commit()

    return {"qualified": len(results), "results": results}


@router.post("/{lead_id}/message/linkedin")
def generate_linkedin_message(
    lead_id: str,
    business_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate LinkedIn connection message for a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    claude_service = ClaudeService()

    # Get sender context if provided
    sender_context = None
    if business_id:
        profile = db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
        if profile:
            sender_context = {
                "sender_name": profile.sender_name,
                "sender_role": profile.sender_role,
                "sender_company": profile.sender_company,
                "sender_context": profile.sender_context,
            }

    lead_data = {
        "first_name": lead.first_name,
        "job_title": lead.job_title,
        "company_name": lead.company_name,
        "company_industry": lead.company_industry,
    }

    message = claude_service.generate_linkedin_message(lead_data, sender_context)

    lead.linkedin_message = message
    db.commit()

    return {
        "lead_id": lead_id,
        "message": message,
        "length": len(message)
    }


@router.post("/{lead_id}/message/email")
def generate_email_message(
    lead_id: str,
    business_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate cold email for a lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    claude_service = ClaudeService()

    # Get sender context if provided
    sender_context = None
    if business_id:
        profile = db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
        if profile:
            sender_context = {
                "sender_name": profile.sender_name,
                "sender_role": profile.sender_role,
                "sender_company": profile.sender_company,
                "value_proposition": profile.value_proposition,
            }

    lead_data = {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "job_title": lead.job_title,
        "company_name": lead.company_name,
        "company_industry": lead.company_industry,
    }

    email = claude_service.generate_email_message(lead_data, sender_context)

    lead.email_message = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
    db.commit()

    return {
        "lead_id": lead_id,
        "subject": email.get("subject"),
        "body": email.get("body")
    }


@router.post("/{lead_id}/action/linkedin")
async def send_linkedin_connection(
    lead_id: str,
    db: Session = Depends(get_db)
):
    """Send LinkedIn connection request via Unipile API."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.linkedin_message:
        raise HTTPException(
            status_code=400,
            detail="Generate LinkedIn message first"
        )

    if not lead.linkedin_url:
        raise HTTPException(
            status_code=400,
            detail="Lead has no LinkedIn URL"
        )

    unipile_service = UnipileService()

    # Send invitation via Unipile
    result = await unipile_service.send_invitation_by_url(
        lead.linkedin_url,
        lead.linkedin_message
    )

    if result["success"]:
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()
        # Store provider_id if available
        if "data" in result and "provider_id" in result.get("data", {}):
            lead.linkedin_provider_id = result["data"]["provider_id"]
        db.commit()

    return result
