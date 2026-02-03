"""
Automation router for managing automatic LinkedIn outreach.
"""
import logging
import random
from typing import Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import Lead, AutomationSettings, InvitationLog, BusinessProfile, Campaign
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
from ..services.scheduler_service import is_scheduler_running

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

    # Get current time in configured timezone
    try:
        tz = ZoneInfo(settings.timezone or "Europe/Madrid")
        current_time = datetime.now(tz).strftime("%H:%M")
    except Exception:
        current_time = None

    return AutomationStatusResponse(
        enabled=settings.enabled,
        is_working_hour=settings.is_working_hour(),
        can_send=settings.can_send_invitation(),
        invitations_sent_today=settings.invitations_sent_today,
        daily_limit=settings.daily_limit,
        remaining_today=max(0, settings.daily_limit - settings.invitations_sent_today),
        next_invitation_in_seconds=next_in_seconds,
        current_time=current_time,
        timezone=settings.timezone,
        scheduler_running=is_scheduler_running()
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

    # Apply campaign filter if set
    campaign_name = None
    if settings.target_campaign_id:
        query = query.filter(Lead.campaign_id == settings.target_campaign_id)
        campaign = db.query(Campaign).filter(Campaign.id == settings.target_campaign_id).first()
        campaign_name = campaign.name if campaign else None

    # Apply score filter
    if settings.min_lead_score > 0:
        query = query.filter(Lead.score >= settings.min_lead_score)

    # Get oldest lead first (FIFO)
    lead = query.order_by(Lead.created_at).first()

    if not lead:
        campaign_hint = f" in campaign '{campaign_name}'" if campaign_name else ""
        return {
            "sent": False,
            "reason": f"No eligible leads found{campaign_hint}. Make sure leads have LinkedIn URL and generated message.",
            "invitations_today": settings.invitations_sent_today
        }

    # Send invitation via Unipile
    unipile = UnipileService()
    result = await unipile.send_invitation_by_url(lead.linkedin_url, lead.linkedin_message)

    # Get campaign name for the log
    if not campaign_name and lead.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        campaign_name = campaign.name if campaign else None

    # Log the attempt with full details
    log = InvitationLog(
        lead_id=lead.id,
        lead_name=f"{lead.first_name} {lead.last_name}",
        lead_company=lead.company_name,
        lead_job_title=lead.job_title,
        lead_linkedin_url=lead.linkedin_url,
        message_preview=lead.linkedin_message[:300] if lead.linkedin_message else None,
        campaign_id=lead.campaign_id,
        campaign_name=campaign_name,
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

    # Count queries - ONLY count successful invitations
    today_count = db.query(InvitationLog).filter(
        InvitationLog.sent_at >= today_start,
        InvitationLog.success == True
    ).count()
    week_count = db.query(InvitationLog).filter(
        InvitationLog.sent_at >= week_start,
        InvitationLog.success == True
    ).count()
    month_count = db.query(InvitationLog).filter(
        InvitationLog.sent_at >= month_start,
        InvitationLog.success == True
    ).count()
    total_count = db.query(InvitationLog).filter(InvitationLog.success == True).count()

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


@router.get("/queue")
def get_invitation_queue(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get the next leads in the invitation queue.
    Shows what will be sent next based on current settings.
    """
    settings = get_or_create_settings(db)
    target_statuses = settings.target_statuses.split(",")

    query = db.query(Lead).filter(
        Lead.status.in_(target_statuses),
        Lead.linkedin_url.isnot(None),
        Lead.linkedin_message.isnot(None)
    )

    # Apply campaign filter if set
    if settings.target_campaign_id:
        query = query.filter(Lead.campaign_id == settings.target_campaign_id)

    # Apply score filter
    if settings.min_lead_score > 0:
        query = query.filter(Lead.score >= settings.min_lead_score)

    # Get total count
    total_eligible = query.count()

    # Get next leads in queue
    leads = query.order_by(Lead.created_at).limit(limit).all()

    queue = []
    for lead in leads:
        # Get campaign name
        campaign_name = None
        if lead.campaign_id:
            campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
            campaign_name = campaign.name if campaign else None

        queue.append({
            "lead_id": lead.id,
            "lead_name": f"{lead.first_name} {lead.last_name}",
            "job_title": lead.job_title,
            "company": lead.company_name,
            "linkedin_url": lead.linkedin_url,
            "message_preview": lead.linkedin_message[:100] + "..." if lead.linkedin_message and len(lead.linkedin_message) > 100 else lead.linkedin_message,
            "score": lead.score,
            "score_label": lead.score_label,
            "campaign_id": lead.campaign_id,
            "campaign_name": campaign_name,
        })

    return {
        "total_eligible": total_eligible,
        "queue": queue,
        "settings": {
            "target_campaign_id": settings.target_campaign_id,
            "min_lead_score": settings.min_lead_score,
            "target_statuses": target_statuses
        }
    }


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
