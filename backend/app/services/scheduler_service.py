"""
Background scheduler for automatic LinkedIn invitation sending.

This service runs in the background and automatically sends invitations
based on the automation settings (working hours, delays, limits, etc.)
"""
import asyncio
import logging
import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Lead, AutomationSettings, InvitationLog, Campaign
from ..models.lead import LeadStatus
from ..models.user import LinkedInAccount
from .unipile_service import UnipileService
from .encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

# Global flag to control the scheduler
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None


async def send_automatic_invitation(db: Session) -> dict:
    """
    Send the next automatic invitation if conditions are met.

    Returns:
        dict with result information
    """
    settings = db.query(AutomationSettings).first()
    if not settings:
        return {"sent": False, "reason": "No settings found"}

    # Reset daily counter if it's a new day
    today = datetime.utcnow().date()
    if settings.last_reset_date is None or settings.last_reset_date.date() < today:
        settings.invitations_sent_today = 0
        settings.last_reset_date = datetime.utcnow()
        db.commit()

    # Check if we can send
    if not settings.enabled:
        return {"sent": False, "reason": "Automation disabled"}

    if not settings.is_working_hour():
        return {"sent": False, "reason": "Outside working hours"}

    if settings.invitations_sent_today >= settings.daily_limit:
        return {"sent": False, "reason": "Daily limit reached"}

    # Check minimum delay between invitations
    if settings.last_invitation_at:
        elapsed = (datetime.utcnow() - settings.last_invitation_at).total_seconds()
        # Use random delay between min and max
        required_delay = random.randint(settings.min_delay_seconds, settings.max_delay_seconds)
        if elapsed < required_delay:
            return {"sent": False, "reason": f"Waiting for delay ({int(required_delay - elapsed)}s remaining)"}

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
        return {"sent": False, "reason": "No eligible leads"}

    # Send invitation via Unipile (use per-user credentials if available)
    unipile = UnipileService()
    if lead.user_id:
        linkedin_account = db.query(LinkedInAccount).filter(
            LinkedInAccount.user_id == lead.user_id,
            LinkedInAccount.is_connected == True
        ).first()
        if linkedin_account and linkedin_account.unipile_api_key_encrypted:
            encryption_service = get_encryption_service()
            api_key = encryption_service.decrypt(linkedin_account.unipile_api_key_encrypted)
            account_id = linkedin_account.unipile_account_id
            unipile = UnipileService(api_key=api_key, account_id=account_id)
    result = await unipile.send_invitation_by_url(lead.linkedin_url, lead.linkedin_message)

    # Get campaign name for the log
    if not campaign_name and lead.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        campaign_name = campaign.name if campaign else None

    # Log the attempt
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

        logger.info(f"[Scheduler] Sent invitation to {lead.first_name} {lead.last_name}")
    else:
        logger.warning(f"[Scheduler] Failed to send to {lead.first_name} {lead.last_name}: {result.get('error')}")

    db.commit()

    return {
        "sent": result.get("success", False),
        "lead_name": f"{lead.first_name} {lead.last_name}",
        "error": result.get("error") if not result.get("success") else None
    }


async def scheduler_loop():
    """
    Main scheduler loop that runs in the background.
    Multi-phase loop processing invitations and sequence steps.

    Phase 1 (every tick / 30s): Send automatic invitations + process due sequence actions
    Phase 2 (~30 min + jitter): Detect connection acceptances via Unipile
    Phase 3 (~30 min + jitter, offset ~15 min from Phase 2): Detect replies (classic)
    Phase 4 (~30 min + jitter, offset ~20 min from Phase 2): Smart pipeline reply detection + time-based phases

    IMPORTANT: Phases 2-4 use randomized intervals (27-32 min) to simulate human behavior
    and avoid LinkedIn detection patterns. Each phase fires independently with its own jitter.
    """
    global _scheduler_running
    from .sequence_scheduler import process_sequence_actions, detect_connection_changes, detect_replies
    from .pipeline_scheduler import detect_pipeline_replies, process_time_based_phases

    logger.info("[Scheduler] Starting combined scheduler (invitations + sequences + pipeline)")
    logger.info("[Scheduler] LinkedIn safety: polling every ~30 min with random jitter")

    tick_count = 0

    # Dynamic tick targets with jitter for human-like behavior
    # Each phase fires independently at ~30 min intervals with ±2.5 min variation
    # Initial offsets stagger the phases to avoid burst API calls
    next_connection_tick = random.randint(55, 65)     # First check at ~27-32 min
    next_reply_tick = random.randint(25, 35)           # Offset ~15 min from connections
    next_pipeline_tick = random.randint(40, 50)        # Offset ~20 min from connections

    while _scheduler_running:
        try:
            # Create a new database session for each iteration
            db = SessionLocal()
            try:
                # Phase 1: Process automatic invitations (existing behavior)
                result = await send_automatic_invitation(db)
                if result.get("sent"):
                    logger.info(f"[Scheduler] Successfully sent invitation: {result}")
                elif result.get("reason") not in ["Automation disabled", "Outside working hours", "No eligible leads"]:
                    logger.debug(f"[Scheduler] Not sending: {result.get('reason')}")

                # Phase 1b: Process sequence actions (connection requests + follow-ups)
                try:
                    await process_sequence_actions(db)
                except Exception as e:
                    logger.error(f"[Scheduler] Error in sequence actions: {e}")

                # Phase 2: Detect connection acceptances (~30 min + jitter)
                if tick_count >= next_connection_tick:
                    try:
                        logger.info(f"[Scheduler] Running connection detection (tick {tick_count})")
                        await detect_connection_changes(db)
                    except Exception as e:
                        logger.error(f"[Scheduler] Error detecting connections: {e}")
                    next_connection_tick = tick_count + random.randint(55, 65)

                # Phase 3: Detect replies - classic sequences (~30 min + jitter)
                if tick_count >= next_reply_tick:
                    try:
                        logger.info(f"[Scheduler] Running reply detection (tick {tick_count})")
                        await detect_replies(db)
                    except Exception as e:
                        logger.error(f"[Scheduler] Error detecting replies: {e}")
                    next_reply_tick = tick_count + random.randint(55, 65)

                # Phase 4: Smart pipeline processing (~30 min + jitter)
                if tick_count >= next_pipeline_tick:
                    try:
                        logger.info(f"[Scheduler] Running pipeline detection (tick {tick_count})")
                        await detect_pipeline_replies(db)
                    except Exception as e:
                        logger.error(f"[Scheduler] Error in pipeline reply detection: {e}")
                    try:
                        await process_time_based_phases(db)
                    except Exception as e:
                        logger.error(f"[Scheduler] Error in pipeline time-based phases: {e}")
                    next_pipeline_tick = tick_count + random.randint(55, 65)

                tick_count += 1
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Scheduler] Error in scheduler loop: {e}")

        # Wait 30 seconds before next check
        await asyncio.sleep(30)

    logger.info("[Scheduler] Scheduler stopped")


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_running, _scheduler_task

    if _scheduler_running:
        logger.warning("[Scheduler] Scheduler already running")
        return

    _scheduler_running = True
    _scheduler_task = asyncio.create_task(scheduler_loop())
    logger.info("[Scheduler] Scheduler started")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running, _scheduler_task

    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
    logger.info("[Scheduler] Scheduler stop requested")


def is_scheduler_running() -> bool:
    """Check if the scheduler is running."""
    return _scheduler_running
