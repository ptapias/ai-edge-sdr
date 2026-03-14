"""
Sequence scheduler - processes automated sequence steps.

Handles:
1. Executing due sequence actions (connection requests + follow-ups)
2. Detecting connection acceptances via Unipile chat polling
3. Detecting replies and auto-exiting leads from sequences

CRITICAL: Includes error classification and exponential backoff to prevent
infinite retry loops that could ban the LinkedIn account.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Lead, AutomationSettings, InvitationLog, Campaign
from ..models.lead import LeadStatus
from ..models.sequence import (
    Sequence, SequenceStep, SequenceEnrollment,
    SequenceStatus, StepType, EnrollmentStatus
)
from .unipile_service import (
    UnipileService,
    InvitationErrorCategory,
    PERMANENT_ERRORS,
    GLOBAL_PAUSE_ERRORS,
)
from .claude_service import ClaudeService
from .scheduler_service import _handle_invitation_failure, _calculate_backoff_minutes, MAX_INVITATION_ATTEMPTS

logger = logging.getLogger(__name__)

# Max step retry attempts for sequence enrollments
MAX_STEP_ATTEMPTS = 5


def _get_business_context(db: Session, business_id: Optional[str]) -> dict:
    """Get business profile context for AI message generation."""
    if not business_id:
        return {}
    from ..models import BusinessProfile
    bp = db.query(BusinessProfile).filter(BusinessProfile.id == business_id).first()
    if not bp:
        return {}
    return {
        "sender_name": bp.sender_name,
        "sender_role": bp.sender_role,
        "sender_company": bp.sender_company,
        "sender_context": bp.sender_context,
    }


def _get_lead_data(lead: Lead) -> dict:
    """Extract lead data for AI message generation."""
    return {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.display_name,
        "job_title": lead.job_title,
        "headline": lead.headline,
        "company_name": lead.company_name,
        "company_website": lead.company_website,
        "company_industry": lead.company_industry,
        "company_size": lead.company_size,
        "seniority_level": lead.seniority_level,
        "city": lead.city,
        "country": lead.country,
    }


def _format_conversation(messages_data: dict) -> str:
    """Format Unipile messages into conversation text for Claude."""
    items = messages_data.get("items", [])
    if not items:
        return ""

    lines = []
    for msg in sorted(items, key=lambda m: m.get("timestamp", m.get("sent_at", ""))):
        sender = "You" if msg.get("is_sender") else "Them"
        text = msg.get("text", msg.get("body", ""))
        if text:
            lines.append(f"{sender}: {text}")

    return "\n".join(lines[-10:])  # Last 10 messages


def _handle_enrollment_failure(
    enrollment: SequenceEnrollment,
    lead: Lead,
    sequence: Sequence,
    settings: Optional[AutomationSettings],
    result: dict,
    db: Session,
    step_type: str = "connection_request",
):
    """
    Handle a failed sequence step with proper error classification and backoff.
    Prevents infinite retry loops for sequence actions.
    """
    error_msg = result.get("error", "Unknown error")
    error_category_str = result.get("error_category", InvitationErrorCategory.UNKNOWN.value)
    error_category = InvitationErrorCategory(error_category_str)

    # Update enrollment retry tracking
    enrollment.step_attempts = (enrollment.step_attempts or 0) + 1
    enrollment.step_last_error = (error_msg or "Unknown error")[:500]
    enrollment.step_error_category = error_category_str

    if error_category in PERMANENT_ERRORS:
        # Permanent failure - fail the enrollment
        enrollment.status = EnrollmentStatus.FAILED.value
        enrollment.failed_reason = f"Permanent error: {error_category_str} - {error_msg[:200]}"
        enrollment.next_step_due_at = None
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
        lead.active_sequence_id = None
        logger.warning(
            f"[Sequence] PERMANENT failure for {lead.display_name} in '{sequence.name}': "
            f"{error_category_str} - {error_msg[:100]}"
        )

    elif error_category in GLOBAL_PAUSE_ERRORS:
        # Global rate limit - pause the enrollment and trigger global pause
        pause_hours = 24
        enrollment.next_step_due_at = datetime.utcnow() + timedelta(hours=pause_hours)
        enrollment.step_next_retry_at = enrollment.next_step_due_at

        # Also trigger global pause via the settings if available
        if settings:
            _handle_invitation_failure(lead, settings, error_msg, error_category, db, "Sequence")
        logger.error(
            f"[Sequence] GLOBAL PAUSE triggered by {lead.display_name} in '{sequence.name}': "
            f"{error_category_str}"
        )

    else:
        # Temporary failure - exponential backoff
        attempts = enrollment.step_attempts or 1
        backoff_minutes = _calculate_backoff_minutes(attempts)
        enrollment.next_step_due_at = datetime.utcnow() + timedelta(minutes=backoff_minutes)
        enrollment.step_next_retry_at = enrollment.next_step_due_at
        logger.warning(
            f"[Sequence] Temporary failure for {lead.display_name} in '{sequence.name}': "
            f"{error_category_str} - retry in {backoff_minutes}min (attempt {attempts}/{MAX_STEP_ATTEMPTS})"
        )

    # Max retries exhausted
    if (enrollment.step_attempts or 0) >= MAX_STEP_ATTEMPTS and enrollment.status != EnrollmentStatus.FAILED.value:
        enrollment.status = EnrollmentStatus.FAILED.value
        enrollment.failed_reason = f"Max retries ({MAX_STEP_ATTEMPTS}) reached for {step_type}: {error_msg[:200]}"
        enrollment.next_step_due_at = None
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
        lead.active_sequence_id = None
        logger.error(
            f"[Sequence] MAX RETRIES ({MAX_STEP_ATTEMPTS}) reached for {lead.display_name} "
            f"in '{sequence.name}' - failing enrollment"
        )


async def process_sequence_actions(db: Session):
    """
    Process all due sequence actions across all users.
    Called every 30 seconds from the main scheduler loop.
    """
    now = datetime.utcnow()

    # Find enrollments where next_step_due_at <= now AND status = active
    # Also exclude enrollments in step retry backoff
    due_enrollments = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        SequenceEnrollment.next_step_due_at.isnot(None),
        SequenceEnrollment.next_step_due_at <= now,
        # Exclude enrollments in retry backoff
        or_(
            SequenceEnrollment.step_next_retry_at.is_(None),
            SequenceEnrollment.step_next_retry_at <= now,
        ),
    ).limit(5).all()  # Process max 5 per tick to avoid overload

    for enrollment in due_enrollments:
        try:
            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            if not sequence or sequence.status != SequenceStatus.ACTIVE.value:
                continue

            # Get user's automation settings for working hours check
            settings = db.query(AutomationSettings).filter(
                AutomationSettings.user_id == enrollment.user_id
            ).first()

            if settings and not settings.is_working_hour():
                continue  # Respect working hours

            # Check global pause
            if settings and settings.is_globally_paused():
                continue

            # Get the current step
            current_step = db.query(SequenceStep).filter(
                SequenceStep.sequence_id == enrollment.sequence_id,
                SequenceStep.step_order == enrollment.current_step_order
            ).first()

            if not current_step:
                # No more steps, mark completed
                enrollment.status = EnrollmentStatus.COMPLETED.value
                enrollment.completed_at = now
                sequence.completed_count = (sequence.completed_count or 0) + 1
                sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
                lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
                if lead:
                    lead.active_sequence_id = None
                db.commit()
                logger.info(f"[Sequence] Enrollment {enrollment.id} completed (no more steps)")
                continue

            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead:
                enrollment.status = EnrollmentStatus.FAILED.value
                enrollment.failed_reason = "Lead not found"
                db.commit()
                continue

            if current_step.step_type == StepType.CONNECTION_REQUEST.value:
                await _execute_connection_request(db, enrollment, lead, current_step, sequence, settings)
            elif current_step.step_type == StepType.FOLLOW_UP_MESSAGE.value:
                await _execute_follow_up(db, enrollment, lead, current_step, sequence, settings)

        except Exception as e:
            logger.error(f"[Sequence] Error processing enrollment {enrollment.id}: {e}")
            continue


async def _execute_connection_request(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    step: SequenceStep,
    sequence: Sequence,
    settings: Optional[AutomationSettings]
):
    """Send a personalized connection request for step 1."""
    # Check daily invitation limit
    if settings and settings.invitations_sent_today >= settings.daily_limit:
        return  # Will retry next tick

    if not lead.linkedin_url:
        enrollment.status = EnrollmentStatus.FAILED.value
        enrollment.failed_reason = "No LinkedIn URL"
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
        lead.active_sequence_id = None
        db.commit()
        return

    # Generate personalized message via Claude
    claude = ClaudeService()
    sender_context = _get_business_context(db, sequence.business_id)
    lead_data = _get_lead_data(lead)

    message = claude.generate_linkedin_message(lead_data, sender_context, sequence.message_strategy)

    # Send via Unipile
    unipile = UnipileService()
    result = await unipile.send_invitation_by_url(lead.linkedin_url, message)

    # Log the invitation attempt
    campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first() if lead.campaign_id else None
    error_category_str = result.get("error_category") if not result.get("success") else None
    log = InvitationLog(
        user_id=enrollment.user_id,
        lead_id=lead.id,
        lead_name=lead.display_name,
        lead_company=lead.company_name,
        lead_job_title=lead.job_title,
        lead_linkedin_url=lead.linkedin_url,
        message_preview=message[:300] if message else None,
        campaign_id=lead.campaign_id,
        campaign_name=campaign.name if campaign else None,
        success=result.get("success", False),
        error_message=result.get("error") if not result.get("success") else None,
        error_category=error_category_str,
        mode="automatic"
    )
    db.add(log)

    if result.get("success"):
        # Update lead
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()
        lead.linkedin_message = message
        # Reset invitation retry tracking
        lead.invitation_attempts = 0
        lead.invitation_last_error = None
        lead.invitation_error_category = None
        lead.invitation_next_retry_at = None

        # Update enrollment - now waiting for connection acceptance
        enrollment.last_step_completed_at = datetime.utcnow()
        enrollment.next_step_due_at = None  # Will be set when connection detected
        enrollment.store_message(step.step_order, message)
        # Reset step retry tracking
        enrollment.step_attempts = 0
        enrollment.step_last_error = None
        enrollment.step_error_category = None
        enrollment.step_next_retry_at = None

        # Update automation settings counter
        if settings:
            settings.invitations_sent_today = (settings.invitations_sent_today or 0) + 1
            settings.last_invitation_at = datetime.utcnow()

        db.commit()
        logger.info(f"[Sequence] Connection request sent to {lead.display_name} (sequence: {sequence.name})")
    else:
        # CRITICAL: Handle failure with proper classification, backoff, and pause
        _handle_enrollment_failure(enrollment, lead, sequence, settings, result, db, "connection_request")
        db.commit()


async def _execute_follow_up(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    step: SequenceStep,
    sequence: Sequence,
    settings: Optional[AutomationSettings]
):
    """Send a follow-up message (post-connection)."""
    if not lead.linkedin_chat_id:
        # Can't send without chat ID; skip for now, connection detection will handle this
        return

    # Get conversation history for context
    unipile = UnipileService()
    try:
        chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=20)
        conversation_history = _format_conversation(chat_result.get("data", {})) if chat_result.get("success") else ""
    except Exception:
        conversation_history = ""

    # Generate contextual follow-up message
    claude = ClaudeService()
    sender_context = _get_business_context(db, sequence.business_id)
    lead_data = _get_lead_data(lead)

    # Count total steps in sequence
    total_steps = db.query(SequenceStep).filter(
        SequenceStep.sequence_id == sequence.id
    ).count()

    message = claude.generate_sequence_follow_up(
        lead_data=lead_data,
        sender_context=sender_context,
        step_context=step.prompt_context,
        conversation_history=conversation_history,
        step_number=step.step_order,
        total_steps=total_steps,
    )

    # Send message via Unipile
    result = await unipile.send_message(lead.linkedin_chat_id, message)

    if result.get("success"):
        # Store message and advance
        enrollment.store_message(step.step_order, message)
        enrollment.last_step_completed_at = datetime.utcnow()
        enrollment.current_step_order += 1
        # Reset step retry tracking for the next step
        enrollment.step_attempts = 0
        enrollment.step_last_error = None
        enrollment.step_error_category = None
        enrollment.step_next_retry_at = None

        # Check if there's a next step
        next_step = db.query(SequenceStep).filter(
            SequenceStep.sequence_id == enrollment.sequence_id,
            SequenceStep.step_order == enrollment.current_step_order
        ).first()

        if next_step:
            enrollment.next_step_due_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
        else:
            # Sequence completed
            enrollment.status = EnrollmentStatus.COMPLETED.value
            enrollment.completed_at = datetime.utcnow()
            enrollment.next_step_due_at = None
            sequence.completed_count = (sequence.completed_count or 0) + 1
            sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
            lead.active_sequence_id = None

        lead.last_message_at = datetime.utcnow()
        db.commit()
        logger.info(f"[Sequence] Follow-up step {step.step_order} sent to {lead.display_name} (sequence: {sequence.name})")
    else:
        # CRITICAL: Handle failure with proper classification and backoff
        _handle_enrollment_failure(enrollment, lead, sequence, settings, result, db, "follow_up")
        db.commit()


async def detect_connection_changes(db: Session):
    """
    Poll Unipile chats to detect accepted connections.
    Called every 5 minutes from the main scheduler loop.

    Checks BOTH:
    1. Sequence-enrolled leads waiting for connection acceptance
    2. Non-sequence leads with status invitation_sent (manual/auto invitations)
    """
    # Find sequence enrollments waiting for connection acceptance
    waiting_enrollments = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Lead.status == LeadStatus.INVITATION_SENT.value,
        SequenceEnrollment.next_step_due_at.is_(None)  # Waiting for connection
    ).all()

    # Find non-sequence leads with invitation_sent status
    enrolled_lead_ids = [e.lead_id for e in waiting_enrollments]
    standalone_query = db.query(Lead).filter(
        Lead.status == LeadStatus.INVITATION_SENT.value,
        Lead.linkedin_url.isnot(None),
    )
    if enrolled_lead_ids:
        standalone_query = standalone_query.filter(~Lead.id.in_(enrolled_lead_ids))
    standalone_leads = standalone_query.all()

    total_to_check = len(waiting_enrollments) + len(standalone_leads)
    if total_to_check == 0:
        return

    logger.info(
        f"[ConnectionDetect] Checking connection status for "
        f"{len(waiting_enrollments)} enrolled + {len(standalone_leads)} standalone leads"
    )

    # Make one Unipile API call to get chats
    unipile = UnipileService()
    try:
        chats_result = await unipile.get_chats(limit=100, force_refresh=True)
    except Exception as e:
        logger.error(f"[ConnectionDetect] Failed to fetch chats: {e}")
        return

    if not chats_result.get("success"):
        return

    chats = chats_result.get("data", {})
    if isinstance(chats, dict):
        chats = chats.get("items", [])

    # Build lookup: provider_id -> chat_id
    chat_lookup = {}
    for chat in chats:
        attendees = chat.get("attendees", [])
        for att in attendees:
            pid = att.get("provider_id") or att.get("identifier")
            if pid:
                chat_lookup[pid.lower()] = chat.get("id")

    connected_count = 0

    # --- Phase A: Check sequence-enrolled leads ---
    for enrollment in waiting_enrollments:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead or not lead.linkedin_url:
                continue

            provider_id = unipile._extract_provider_id(lead.linkedin_url)
            if not provider_id:
                continue

            chat_id = chat_lookup.get(provider_id.lower())
            if chat_id:
                # Connection accepted!
                lead.status = LeadStatus.CONNECTED.value
                lead.connected_at = datetime.utcnow()
                lead.linkedin_chat_id = chat_id

                # Advance enrollment to next step
                enrollment.current_step_order += 1
                enrollment.last_step_completed_at = datetime.utcnow()
                enrollment.step_attempts = 0
                enrollment.step_last_error = None
                enrollment.step_error_category = None
                enrollment.step_next_retry_at = None

                next_step = db.query(SequenceStep).filter(
                    SequenceStep.sequence_id == enrollment.sequence_id,
                    SequenceStep.step_order == enrollment.current_step_order
                ).first()

                if next_step:
                    enrollment.next_step_due_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
                    logger.info(
                        f"[ConnectionDetect] Enrolled lead {lead.display_name} connected, "
                        f"next step in {next_step.delay_days} days"
                    )
                else:
                    enrollment.status = EnrollmentStatus.COMPLETED.value
                    enrollment.completed_at = datetime.utcnow()
                    sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
                    if sequence:
                        sequence.completed_count = (sequence.completed_count or 0) + 1
                        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
                    lead.active_sequence_id = None

                connected_count += 1
                db.commit()

        except Exception as e:
            logger.error(f"[ConnectionDetect] Error checking enrollment {enrollment.id}: {e}")
            continue

    # --- Phase B: Check standalone (non-sequence) leads ---
    for lead in standalone_leads:
        try:
            if not lead.linkedin_url:
                continue

            provider_id = unipile._extract_provider_id(lead.linkedin_url)
            if not provider_id:
                continue

            chat_id = chat_lookup.get(provider_id.lower())
            if chat_id:
                lead.status = LeadStatus.CONNECTED.value
                lead.connected_at = datetime.utcnow()
                lead.linkedin_chat_id = chat_id
                connected_count += 1
                db.commit()
                logger.info(f"[ConnectionDetect] Standalone lead {lead.display_name} connected")

        except Exception as e:
            logger.error(f"[ConnectionDetect] Error checking standalone lead {lead.id}: {e}")
            continue

    if connected_count > 0:
        logger.info(f"[ConnectionDetect] Detected {connected_count} new connections total")


async def detect_replies(db: Session):
    """
    Check for inbound messages from enrolled leads and auto-exit from sequence.
    Called every 5 minutes (offset from connection detection).
    """
    # Find active enrollments where lead has a chat_id
    active = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Lead.linkedin_chat_id.isnot(None)
    ).all()

    if not active:
        return

    logger.info(f"[Sequence] Checking replies for {len(active)} active enrollments")

    unipile = UnipileService()
    replied_count = 0

    for enrollment in active:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead or not lead.linkedin_chat_id:
                continue

            # Check latest messages
            msg_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=5, force_refresh=True)
            if not msg_result.get("success"):
                continue

            messages = msg_result.get("data", {})
            if isinstance(messages, dict):
                messages = messages.get("items", [])

            # Check if there's a recent inbound message
            for msg in messages:
                is_sender = msg.get("is_sender", True)
                if is_sender:
                    continue  # Skip our own messages

                # Got an inbound message - check if it's after enrollment
                msg_time = msg.get("timestamp") or msg.get("sent_at") or msg.get("created_at")
                if not msg_time:
                    continue

                try:
                    if isinstance(msg_time, str):
                        msg_dt = datetime.fromisoformat(msg_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    else:
                        msg_dt = msg_time
                except (ValueError, TypeError):
                    continue

                if msg_dt > enrollment.enrolled_at:
                    # Lead replied! Auto-exit sequence
                    enrollment.status = EnrollmentStatus.REPLIED.value
                    enrollment.replied_at = datetime.utcnow()
                    enrollment.next_step_due_at = None

                    lead.status = LeadStatus.IN_CONVERSATION.value
                    lead.last_message_at = datetime.utcnow()
                    lead.active_sequence_id = None

                    # Update sequence stats
                    sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
                    if sequence:
                        sequence.replied_count = (sequence.replied_count or 0) + 1
                        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)

                    db.commit()
                    replied_count += 1
                    logger.info(f"[Sequence] Reply detected for {lead.display_name}, exiting sequence")
                    break  # Move to next enrollment

        except Exception as e:
            logger.error(f"[Sequence] Error checking replies for enrollment {enrollment.id}: {e}")
            continue

    if replied_count > 0:
        logger.info(f"[Sequence] Detected {replied_count} replies")
