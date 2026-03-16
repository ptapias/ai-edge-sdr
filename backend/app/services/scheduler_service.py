"""
Background scheduler for automatic LinkedIn invitation sending.

This service runs in the background and automatically sends invitations
based on the automation settings (working hours, delays, limits, etc.)

CRITICAL: Includes error classification, exponential backoff, and global
pause logic to prevent infinite retry loops that could ban the LinkedIn account.
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Lead, AutomationSettings, InvitationLog, Campaign
from ..models.lead import LeadStatus
from .unipile_service import (
    UnipileService,
    InvitationErrorCategory,
    classify_invitation_error,
    PERMANENT_ERRORS,
    GLOBAL_PAUSE_ERRORS,
)

logger = logging.getLogger(__name__)

# Global flag to control the scheduler
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None

# Maximum invitation attempts before marking lead as permanently failed
MAX_INVITATION_ATTEMPTS = 5


def _calculate_backoff_minutes(attempts: int) -> int:
    """
    Calculate exponential backoff duration in minutes.

    Attempt 1: 5 min
    Attempt 2: 15 min
    Attempt 3: 45 min
    Attempt 4: 135 min (~2h 15min)
    Attempt 5: 360 min (6h, capped)
    """
    return min(5 * (3 ** (attempts - 1)), 360)


def _handle_invitation_failure(
    lead: Lead,
    settings: AutomationSettings,
    error_msg: str,
    error_category: InvitationErrorCategory,
    db: Session,
    source: str = "Scheduler",
):
    """
    Handle a failed invitation attempt with proper error classification,
    backoff, and global pause logic.

    This is the core fix that prevents infinite retry loops.
    """
    # Update lead retry tracking
    lead.invitation_attempts = (lead.invitation_attempts or 0) + 1
    lead.invitation_last_error = (error_msg or "Unknown error")[:500]
    lead.invitation_error_category = error_category.value
    if not lead.invitation_first_failed_at:
        lead.invitation_first_failed_at = datetime.utcnow()

    # --- PERMANENT ERROR: Mark lead as failed, never retry ---
    if error_category in PERMANENT_ERRORS:
        lead.status = LeadStatus.INVITATION_FAILED.value
        lead.invitation_next_retry_at = None
        logger.warning(
            f"[{source}] PERMANENT failure for {lead.display_name}: "
            f"{error_category.value} - {error_msg[:100]}"
        )

    # --- GLOBAL RATE LIMIT: Pause the entire scheduler ---
    elif error_category in GLOBAL_PAUSE_ERRORS:
        now = datetime.utcnow()

        if error_category == InvitationErrorCategory.RATE_LIMIT_WEEKLY:
            # Pause until next Monday 9 AM (user's timezone not available here, use UTC)
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            pause_until = (now + timedelta(days=days_until_monday)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            settings.pause_until(pause_until, f"Weekly limit reached")

        elif error_category == InvitationErrorCategory.RATE_LIMIT_DAILY:
            # Pause until tomorrow 9 AM
            pause_until = (now + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            settings.pause_until(pause_until, f"Daily limit reached")

        elif error_category == InvitationErrorCategory.RATE_LIMIT_RESEND:
            # "Cannot resend yet / provider limit" - pause for 2 hours
            pause_until = now + timedelta(hours=2)
            settings.pause_until(pause_until, f"Provider limit reached - temporary cooldown")

        elif error_category == InvitationErrorCategory.ACCOUNT_RESTRICTED:
            # Pause for 24 hours - requires manual review
            pause_until = now + timedelta(hours=24)
            settings.pause_until(pause_until, f"Account restricted - manual review needed")

        else:
            pause_until = now + timedelta(hours=6)
            settings.pause_until(pause_until, f"Rate limit: {error_category.value}")

        # Also set backoff on this specific lead
        lead.invitation_next_retry_at = settings.scheduler_paused_until
        logger.error(
            f"[{source}] GLOBAL PAUSE triggered by {lead.display_name}: "
            f"{error_category.value} - paused until {settings.scheduler_paused_until}"
        )

    # --- TEMPORARY ERROR: Exponential backoff on this lead only ---
    else:
        attempts = lead.invitation_attempts or 1
        backoff_minutes = _calculate_backoff_minutes(attempts)
        lead.invitation_next_retry_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
        logger.warning(
            f"[{source}] Temporary failure for {lead.display_name}: "
            f"{error_category.value} - retry in {backoff_minutes}min (attempt {attempts}/{MAX_INVITATION_ATTEMPTS})"
        )

    # --- MAX RETRIES: Mark as permanently failed ---
    if (lead.invitation_attempts or 0) >= MAX_INVITATION_ATTEMPTS and lead.status != LeadStatus.INVITATION_FAILED.value:
        lead.status = LeadStatus.INVITATION_FAILED.value
        lead.invitation_next_retry_at = None
        logger.error(
            f"[{source}] MAX RETRIES ({MAX_INVITATION_ATTEMPTS}) reached for {lead.display_name} - "
            f"marking as invitation_failed"
        )


async def send_automatic_invitation(db: Session) -> dict:
    """
    Send the next automatic invitation if conditions are met.

    Returns:
        dict with result information
    """
    settings = db.query(AutomationSettings).first()
    if not settings:
        return {"sent": False, "reason": "No settings found"}

    # Reset daily counter if it's a new day (using configured timezone)
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(settings.timezone or "Europe/Madrid")
    today = datetime.now(tz).date()
    last_reset_local = settings.last_reset_date.astimezone(tz).date() if settings.last_reset_date and settings.last_reset_date.tzinfo else (settings.last_reset_date.date() if settings.last_reset_date else None)
    if last_reset_local is None or last_reset_local < today:
        settings.invitations_sent_today = 0
        settings.last_reset_date = datetime.utcnow()
        # Also auto-clear daily pause if it expired
        if settings.scheduler_paused_until and datetime.utcnow() >= settings.scheduler_paused_until:
            settings.clear_pause()
            logger.info("[Scheduler] Auto-cleared expired scheduler pause")
        db.commit()

    # Check global pause (rate limit protection)
    if settings.is_globally_paused():
        return {"sent": False, "reason": f"Scheduler paused: {settings.scheduler_pause_reason}"}

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

    # Find next lead to contact (with backoff and retry exclusions)
    now = datetime.utcnow()
    target_statuses = settings.target_statuses.split(",")
    query = db.query(Lead).filter(
        Lead.status.in_(target_statuses),
        Lead.linkedin_url.isnot(None),
        # Exclude leads currently in backoff cooldown
        or_(
            Lead.invitation_next_retry_at.is_(None),
            Lead.invitation_next_retry_at <= now,
        ),
        # Exclude leads that have exhausted retries
        or_(
            Lead.invitation_attempts.is_(None),
            Lead.invitation_attempts < MAX_INVITATION_ATTEMPTS,
        ),
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

    # Auto-generate message if missing
    if not lead.linkedin_message:
        try:
            from .claude_service import ClaudeService
            from ..models.business_profile import BusinessProfile
            from .experiment_service import ExperimentService

            profile = db.query(BusinessProfile).filter(
                BusinessProfile.user_id == settings.user_id,
                BusinessProfile.is_default == True
            ).first()
            if profile:
                claude = ClaudeService()
                sender_context = {
                    "sender_name": profile.sender_name,
                    "sender_role": profile.sender_role,
                    "sender_company": profile.sender_company,
                    "sender_context": profile.sender_context,
                }
                lead_data = {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "job_title": lead.job_title,
                    "headline": lead.headline,
                    "company_name": lead.company_name,
                    "company_industry": lead.company_industry,
                    "city": lead.city,
                    "country": lead.country,
                }
                # Check for active experiment prompt
                exp_service = ExperimentService()
                experiment_prompt = None
                active_exp = exp_service.get_active_experiment(db, settings.user_id)
                if active_exp:
                    experiment_prompt = active_exp.prompt_template

                lead.linkedin_message = claude.generate_linkedin_message(
                    lead_data, sender_context, "hybrid", experiment_prompt
                )
                db.commit()
                logger.info(f"[Scheduler] Auto-generated message for {lead.display_name}")
            else:
                return {"sent": False, "reason": "No business profile for message generation"}
        except Exception as e:
            logger.error(f"[Scheduler] Failed to auto-generate message for {lead.display_name}: {e}")
            return {"sent": False, "reason": f"Message generation failed: {e}"}

    # Send invitation via Unipile
    unipile = UnipileService()
    result = await unipile.send_invitation_by_url(lead.linkedin_url, lead.linkedin_message)

    # Get campaign name for the log
    if not campaign_name and lead.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        campaign_name = campaign.name if campaign else None

    # Classify the error (if any) for the log
    error_category_str = result.get("error_category") if not result.get("success") else None

    # Log the attempt
    error_msg = result.get("error") if not result.get("success") else None
    log = InvitationLog(
        user_id=lead.user_id,
        lead_id=lead.id,
        lead_name=f"{lead.first_name} {lead.last_name}"[:200],
        lead_company=(lead.company_name or "")[:200],
        lead_job_title=(lead.job_title or "")[:200],
        lead_linkedin_url=(lead.linkedin_url or "")[:500],
        message_preview=lead.linkedin_message[:300] if lead.linkedin_message else None,
        campaign_id=lead.campaign_id,
        campaign_name=(campaign_name or "")[:200],
        success=result.get("success", False),
        error_message=error_msg[:490] if error_msg else None,
        error_category=error_category_str,
        mode="automatic"
    )
    db.add(log)

    if result.get("success"):
        # Update lead status
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()
        # Reset retry tracking on success
        lead.invitation_attempts = 0
        lead.invitation_last_error = None
        lead.invitation_error_category = None
        lead.invitation_next_retry_at = None

        # Update automation stats
        settings.invitations_sent_today += 1
        settings.last_invitation_at = datetime.utcnow()

        logger.info(f"[Scheduler] Sent invitation to {lead.first_name} {lead.last_name}")
    else:
        # CRITICAL: Handle failure with proper classification, backoff, and pause
        error_msg = result.get("error", "Unknown error")
        error_category = InvitationErrorCategory(
            result.get("error_category", InvitationErrorCategory.UNKNOWN.value)
        )
        _handle_invitation_failure(lead, settings, error_msg, error_category, db, "Scheduler")

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

    Phase 1 (every tick / 30s): Send automatic invitations
    Phase 2 (every tick / 30s): Process due sequence actions
    Phase 3 (every ~60 ticks / ~30min): Detect connection acceptances
    Phase 4 (every ~60 ticks / ~30min, offset): Detect classic replies
    Phase 5 (every ~60 ticks / ~30min, offset): Detect Smart Pipeline replies
    Phase 6 (every ~60 ticks / ~30min, offset): Process pipeline time-based phases
    """
    global _scheduler_running
    from .sequence_scheduler import process_sequence_actions, detect_connection_changes, detect_replies
    from .pipeline_scheduler import detect_pipeline_replies, process_time_based_phases

    logger.info("[Scheduler] Starting combined scheduler (invitations + sequences)")

    tick_count = 0
    while _scheduler_running:
        db = None
        try:
            # Create a new database session for each iteration
            db = SessionLocal()

            # Phase 1: Process automatic invitations (existing behavior)
            try:
                result = await send_automatic_invitation(db)
                if result.get("sent"):
                    logger.info(f"[Scheduler] Successfully sent invitation: {result}")
                elif result.get("reason") not in [
                    "Automation disabled", "Outside working hours",
                    "No eligible leads", "No settings found"
                ]:
                    reason = result.get("reason", "")
                    if "Scheduler paused" in reason:
                        if tick_count % 60 == 0:
                            logger.info(f"[Scheduler] {reason}")
                    else:
                        logger.debug(f"[Scheduler] Not sending: {reason}")
            except Exception as e:
                logger.error(f"[Scheduler] Error in send_automatic_invitation: {e}", exc_info=True)

            # Phase 2: Process sequence actions (connection requests + follow-ups)
            try:
                await process_sequence_actions(db)
            except Exception as e:
                logger.error(f"[Scheduler] Error in sequence actions: {e}", exc_info=True)

            # Phase 3: Detect connection acceptances (every ~30 min)
            if tick_count % 60 == 0:
                try:
                    logger.info(f"[Scheduler] Tick {tick_count}: running connection detection")
                    await detect_connection_changes(db)
                except Exception as e:
                    logger.error(f"[Scheduler] Error detecting connections: {e}", exc_info=True)

            # Phase 4: Detect replies (every ~30 min, offset from Phase 3)
            if tick_count % 60 == 30:
                try:
                    logger.info(f"[Scheduler] Tick {tick_count}: running reply detection")
                    await detect_replies(db)
                except Exception as e:
                    logger.error(f"[Scheduler] Error detecting replies: {e}", exc_info=True)

            # Phase 5: Detect Smart Pipeline replies (every ~30 min, offset from Phase 4)
            if tick_count % 60 == 45:
                try:
                    logger.info(f"[Scheduler] Tick {tick_count}: running pipeline reply detection")
                    await detect_pipeline_replies(db)
                except Exception as e:
                    logger.error(f"[Scheduler] Error in pipeline reply detection: {e}", exc_info=True)

            # Phase 6: Process time-based pipeline phases (every ~30 min, offset)
            if tick_count % 60 == 15:
                try:
                    logger.info(f"[Scheduler] Tick {tick_count}: processing pipeline time-based phases")
                    await process_time_based_phases(db)
                except Exception as e:
                    logger.error(f"[Scheduler] Error in pipeline time phases: {e}", exc_info=True)

            # Log heartbeat every 20 ticks (~10 min)
            if tick_count % 20 == 0:
                logger.info(f"[Scheduler] Heartbeat: tick {tick_count}, scheduler alive")

            tick_count += 1

        except Exception as e:
            logger.error(f"[Scheduler] CRITICAL error in scheduler loop tick {tick_count}: {e}", exc_info=True)
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

        # Wait 30 seconds before next check
        # Jitter: 25-35s to avoid fixed-interval patterns (LinkedIn best practice)
        await asyncio.sleep(25 + random.random() * 10)

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
