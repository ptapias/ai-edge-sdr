"""
Automation router for managing automatic LinkedIn outreach.
"""
import logging
import random
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Lead, AutomationSettings, InvitationLog, BusinessProfile
from ..models.lead import LeadStatus
from ..schemas.automation import (
    AutomationSettingsResponse,
    AutomationSettingsUpdate,
    AutomationStatusResponse,
    InvitationLogResponse,
    InvitationStatsResponse
)
from ..services.unipile_service import UnipileService
from ..services.claude_service import ClaudeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/automation", tags=["automation"])


def get_or_create_settings(db: Session) -> AutomationSettings:
    """Get or create automation settings (singleton)."""
    settings = db.query(AutomationSettings).first()
    if not settings:
        settings = AutomationSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings", response_model=AutomationSettingsResponse)
def get_automation_settings(db: Session = Depends(get_db)):
    """Get current automation settings."""
    settings = get_or_create_settings(db)
    return settings


@router.patch("/settings", response_model=AutomationSettingsResponse)
def update_automation_settings(
    update: AutomationSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update automation settings."""
    settings = get_or_create_settings(db)

    update_data = update.model_dump(exclude_unset=True)

    # Enforce maximum daily limit of 40 connections (LinkedIn limit)
    if "daily_limit" in update_data:
        update_data["daily_limit"] = min(update_data["daily_limit"], 40)

    for key, value in update_data.items():
        setattr(settings, key, value)

    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


@router.post("/toggle", response_model=AutomationSettingsResponse)
def toggle_automation(
    enabled: bool,
    db: Session = Depends(get_db)
):
    """Enable or disable automation."""
    settings = get_or_create_settings(db)
    settings.enabled = enabled
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)

    logger.info(f"Automation {'enabled' if enabled else 'disabled'}")
    return settings


@router.get("/status", response_model=AutomationStatusResponse)
def get_automation_status(db: Session = Depends(get_db)):
    """Get current automation status."""
    settings = get_or_create_settings(db)

    # Reset daily counter if it's a new day
    today = datetime.utcnow().date()
    if settings.last_reset_date is None or settings.last_reset_date.date() < today:
        settings.reset_daily_counter()
        db.commit()

    # Calculate next invitation time
    next_in_seconds = None
    if settings.last_invitation_at:
        min_wait = settings.min_delay_seconds
        elapsed = (datetime.utcnow() - settings.last_invitation_at).total_seconds()
        if elapsed < min_wait:
            next_in_seconds = int(min_wait - elapsed)

    return AutomationStatusResponse(
        enabled=settings.enabled,
        is_working_hour=settings.is_working_hour(),
        can_send=settings.can_send_invitation(),
        invitations_sent_today=settings.invitations_sent_today,
        daily_limit=settings.daily_limit,
        remaining_today=max(0, settings.daily_limit - settings.invitations_sent_today),
        next_invitation_in_seconds=next_in_seconds
    )


@router.post("/send-next")
async def send_next_invitation(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send the next invitation (manual trigger for automatic mode).

    This endpoint can be called by a cron job or external scheduler.
    """
    settings = get_or_create_settings(db)

    # Reset daily counter if it's a new day
    today = datetime.utcnow().date()
    if settings.last_reset_date is None or settings.last_reset_date.date() < today:
        settings.reset_daily_counter()
        db.commit()

    # Check if we can send
    if not settings.can_send_invitation():
        return {
            "sent": False,
            "reason": "Cannot send: " + (
                "disabled" if not settings.enabled else
                "outside working hours" if not settings.is_working_hour() else
                "daily limit reached"
            ),
            "invitations_today": settings.invitations_sent_today,
            "daily_limit": settings.daily_limit
        }

    # Check minimum delay between invitations
    if settings.last_invitation_at:
        elapsed = (datetime.utcnow() - settings.last_invitation_at).total_seconds()
        if elapsed < settings.min_delay_seconds:
            return {
                "sent": False,
                "reason": f"Waiting for delay. Next in {int(settings.min_delay_seconds - elapsed)} seconds",
                "invitations_today": settings.invitations_sent_today
            }

    # Find next lead to contact
    target_statuses = settings.target_statuses.split(",")
    query = db.query(Lead).filter(
        Lead.status.in_(target_statuses),
        Lead.linkedin_url.isnot(None),
        Lead.linkedin_message.isnot(None)
    )

    # Apply score filter
    if settings.min_lead_score > 0:
        query = query.filter(Lead.score >= settings.min_lead_score)

    # Get oldest lead first (FIFO)
    lead = query.order_by(Lead.created_at).first()

    if not lead:
        return {
            "sent": False,
            "reason": "No eligible leads found. Make sure leads have LinkedIn URL and generated message.",
            "invitations_today": settings.invitations_sent_today
        }

    # Send invitation via Unipile
    unipile = UnipileService()
    result = await unipile.send_invitation_by_url(lead.linkedin_url, lead.linkedin_message)

    # Log the attempt
    log = InvitationLog(
        lead_id=lead.id,
        lead_name=f"{lead.first_name} {lead.last_name}",
        lead_company=lead.company_name,
        success=result.get("success", False),
        error_message=result.get("error") if not result.get("success") else None,
        mode="automatic"
    )
    db.add(log)

    if result.get("success"):
        # Update lead status
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()

        # Update automation stats
        settings.invitations_sent_today += 1
        settings.last_invitation_at = datetime.utcnow()

        logger.info(f"Auto-sent invitation to {lead.first_name} {lead.last_name}")

    db.commit()

    # Calculate random delay for next invitation
    next_delay = random.randint(settings.min_delay_seconds, settings.max_delay_seconds)

    return {
        "sent": result.get("success", False),
        "lead_id": lead.id,
        "lead_name": f"{lead.first_name} {lead.last_name}",
        "company": lead.company_name,
        "error": result.get("error") if not result.get("success") else None,
        "invitations_today": settings.invitations_sent_today,
        "daily_limit": settings.daily_limit,
        "next_delay_seconds": next_delay if result.get("success") else 60
    }


@router.get("/logs", response_model=List[InvitationLogResponse])
def get_invitation_logs(
    limit: int = 50,
    mode: Optional[str] = None,
    success: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get invitation logs."""
    query = db.query(InvitationLog)

    if mode:
        query = query.filter(InvitationLog.mode == mode)
    if success is not None:
        query = query.filter(InvitationLog.success == success)

    logs = query.order_by(desc(InvitationLog.sent_at)).limit(limit).all()
    return logs


@router.get("/stats", response_model=InvitationStatsResponse)
def get_invitation_stats(db: Session = Depends(get_db)):
    """Get invitation statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # Count queries
    today_count = db.query(InvitationLog).filter(InvitationLog.sent_at >= today_start).count()
    week_count = db.query(InvitationLog).filter(InvitationLog.sent_at >= week_start).count()
    month_count = db.query(InvitationLog).filter(InvitationLog.sent_at >= month_start).count()
    total_count = db.query(InvitationLog).count()

    # Success rate
    successful_count = db.query(InvitationLog).filter(InvitationLog.success == True).count()
    success_rate = (successful_count / total_count * 100) if total_count > 0 else 0

    # Last 7 days breakdown
    by_day = []
    for i in range(7):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_total = db.query(InvitationLog).filter(
            InvitationLog.sent_at >= day_start,
            InvitationLog.sent_at < day_end
        ).count()
        day_successful = db.query(InvitationLog).filter(
            InvitationLog.sent_at >= day_start,
            InvitationLog.sent_at < day_end,
            InvitationLog.success == True
        ).count()
        by_day.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": day_total,
            "successful": day_successful
        })

    return InvitationStatsResponse(
        today=today_count,
        this_week=week_count,
        this_month=month_count,
        total=total_count,
        success_rate=round(success_rate, 1),
        by_day=by_day
    )


@router.post("/generate-messages")
def generate_messages_for_pending(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Generate LinkedIn messages for leads that don't have one.
    This prepares leads for automatic sending.
    """
    # Get default business profile
    profile = db.query(BusinessProfile).filter(BusinessProfile.is_default == True).first()
    if not profile:
        raise HTTPException(status_code=400, detail="No default business profile found")

    # Find leads without messages
    leads = db.query(Lead).filter(
        Lead.linkedin_url.isnot(None),
        Lead.linkedin_message.is_(None),
        Lead.status.in_(["new", "pending"])
    ).limit(limit).all()

    if not leads:
        return {"generated": 0, "message": "No leads need message generation"}

    claude = ClaudeService()
    sender_context = {
        "sender_name": profile.sender_name,
        "sender_role": profile.sender_role,
        "sender_company": profile.sender_company,
        "sender_context": profile.sender_context,
    }

    results = []
    for lead in leads:
        lead_data = {
            "first_name": lead.first_name,
            "job_title": lead.job_title,
            "company_name": lead.company_name,
            "company_industry": lead.company_industry,
        }

        try:
            message = claude.generate_linkedin_message(lead_data, sender_context)
            lead.linkedin_message = message
            results.append({
                "lead_id": lead.id,
                "lead_name": f"{lead.first_name} {lead.last_name}",
                "success": True
            })
        except Exception as e:
            results.append({
                "lead_id": lead.id,
                "lead_name": f"{lead.first_name} {lead.last_name}",
                "success": False,
                "error": str(e)
            })

    db.commit()

    return {
        "generated": sum(1 for r in results if r.get("success")),
        "results": results
    }
