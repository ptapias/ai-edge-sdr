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
    SequenceStatus, StepType, EnrollmentStatus,
    SequenceMode, PipelinePhase,
)
from .unipile_service import (
    UnipileService,
    InvitationErrorCategory,
    PERMANENT_ERRORS,
    GLOBAL_PAUSE_ERRORS,
)
from .claude_service import ClaudeService
from .experiment_service import ExperimentService
from ..models.draft_message import DraftMessage, DraftStatus
from .scheduler_service import _handle_invitation_failure, _calculate_backoff_minutes, MAX_INVITATION_ATTEMPTS

logger = logging.getLogger(__name__)

# Max step retry attempts for sequence enrollments
MAX_STEP_ATTEMPTS = 2

# In-memory set of lead IDs that failed permanently — prevents retries even if DB commit fails
_permanently_failed_leads: set = set()


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
        _permanently_failed_leads.add(lead.id)

        # If already_invited, the invitation exists on LinkedIn — mark lead accordingly
        if error_category_str == "already_invited":
            lead.status = LeadStatus.INVITATION_SENT.value
            if not lead.connection_sent_at:
                lead.connection_sent_at = datetime.utcnow()

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

            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead:
                enrollment.status = EnrollmentStatus.FAILED.value
                enrollment.failed_reason = "Lead not found"
                db.commit()
                continue

            is_pipeline = sequence and (sequence.sequence_mode or "classic") == SequenceMode.SMART_PIPELINE.value

            if is_pipeline:
                # Smart Pipeline: generate draft for current phase
                await _execute_pipeline_follow_up(db, enrollment, lead, sequence, settings)
                continue

            # Classic: get the current step
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
                lead.active_sequence_id = None
                db.commit()
                logger.info(f"[Sequence] Enrollment {enrollment.id} completed (no more steps)")
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
    # Safety: skip leads that already failed permanently (even if DB rollback lost the status)
    if lead.id in _permanently_failed_leads:
        enrollment.status = EnrollmentStatus.FAILED.value
        enrollment.failed_reason = "Skipped: previously failed permanently"
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
        lead.active_sequence_id = None
        db.commit()
        return

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

    # AutoOutreach: get experiment prompt template if active
    exp_service = ExperimentService()
    experiment_prompt = None
    active_experiment_id = exp_service.get_active_experiment_id(db, enrollment.user_id)
    if active_experiment_id:
        active_exp = exp_service.get_active_experiment(db, enrollment.user_id)
        if active_exp:
            experiment_prompt = active_exp.prompt_template

    message = claude.generate_linkedin_message(lead_data, sender_context, sequence.message_strategy, experiment_prompt)

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
        lead_job_title=(lead.job_title or "")[:500],
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

        # AutoOutreach: register lead in active experiment
        if active_experiment_id:
            exp_service.register_lead_sent(db, active_experiment_id, lead.id, message)
    else:
        # CRITICAL: Handle failure with proper classification, backoff, and pause
        _handle_enrollment_failure(enrollment, lead, sequence, settings, result, db, "connection_request")
        db.commit()



async def _execute_pipeline_follow_up(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    sequence: Sequence,
    settings: Optional[AutomationSettings]
):
    """
    Smart Pipeline follow-up logic.
    
    Checks who sent the last message and generates a draft:
    - After connection accepted (no reply): wait 24h, then draft first message
    - We sent last, no reply: wait 48h, then draft follow-up
    - After 2nd follow-up with no reply: wait 48h, then final follow-up
    - They replied: analyze and draft response (handled by detect_replies)
    """
    if not lead.linkedin_chat_id:
        logger.debug(f"[SmartPipeline] {lead.display_name}: no chat_id, skipping")
        return

    # Check conversation to determine who sent last message
    unipile = UnipileService()
    try:
        chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=20)
        conversation_history = ""
        last_message_is_ours = False
        our_message_count = 0

        if chat_result.get("success"):
            messages_data = chat_result.get("data", {})
            items = messages_data.get("items", []) if isinstance(messages_data, dict) else messages_data
            if isinstance(items, list) and len(items) > 0:
                conversation_history = _format_conversation(messages_data)
                
                # Check last message sender
                last_msg = items[0]  # Most recent first
                is_sender = last_msg.get("is_sender")
                if isinstance(is_sender, (int, float)):
                    last_message_is_ours = is_sender == 1
                elif isinstance(is_sender, bool):
                    last_message_is_ours = is_sender
                
                # Count our messages (for follow-up limiting)
                our_message_count = sum(
                    1 for m in items 
                    if (isinstance(m.get("is_sender"), (int, float)) and m.get("is_sender") == 1)
                    or (isinstance(m.get("is_sender"), bool) and m.get("is_sender"))
                )
    except Exception as e:
        logger.error(f"[SmartPipeline] Error fetching messages for {lead.display_name}: {e}")
        return

    # If they sent the last message, this should be handled by detect_replies
    # (which sets last_response_at and triggers phase analysis)
    # Here we only handle follow-ups when WE sent the last message
    
    if not last_message_is_ours and not conversation_history:
        # No messages at all — this is the first message after connection
        pass  # Generate first message draft
    elif not last_message_is_ours:
        # They sent last — detect_replies should handle this
        # But if we're here, it means the timer expired and they already replied
        # but detect_replies hasn't processed it. Skip and let detect_replies handle it.
        logger.debug(f"[SmartPipeline] {lead.display_name}: they sent last, deferring to detect_replies")
        enrollment.next_step_due_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        return

    # Limit follow-ups: max 3 messages from us without a reply = stop
    # (connection request + 2 follow-ups)
    if our_message_count >= 3:
        enrollment.status = EnrollmentStatus.PARKED.value
        enrollment.next_step_due_at = None
        db.commit()
        logger.info(
            f"[SmartPipeline] {lead.display_name}: parked after {our_message_count} "
            f"messages without reply"
        )
        return

    # Generate the draft
    current_phase = enrollment.current_phase or PipelinePhase.APERTURA.value
    claude = ClaudeService()
    sender_context = _get_business_context(db, sequence.business_id)
    lead_data = _get_lead_data(lead)

    message = claude.generate_smart_pipeline_message(
        lead_data=lead_data,
        sender_context=sender_context,
        conversation_history=conversation_history,
        current_phase=current_phase,
    )

    # Check for existing pending draft (avoid duplicates)
    existing_draft = db.query(DraftMessage).filter(
        DraftMessage.enrollment_id == enrollment.id,
        DraftMessage.status == DraftStatus.PENDING.value,
    ).first()
    if existing_draft:
        return

    # Save as draft
    import uuid
    draft = DraftMessage(
        id=str(uuid.uuid4()),
        enrollment_id=enrollment.id,
        lead_id=lead.id,
        sequence_id=sequence.id,
        user_id=enrollment.user_id,
        pipeline_phase=current_phase,
        step_order=enrollment.current_step_order,
        generated_message=message,
        status=DraftStatus.PENDING.value,
    )
    db.add(draft)

    # Pause enrollment until user approves
    enrollment.status = EnrollmentStatus.PAUSED.value
    enrollment.next_step_due_at = None
    db.commit()

    logger.info(
        f"[SmartPipeline] Draft created for {lead.display_name} "
        f"phase={current_phase}, our_msgs={our_message_count} "
        f"(sequence: {sequence.name})"
    )


async def _execute_follow_up(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    step: SequenceStep,
    sequence: Sequence,
    settings: Optional[AutomationSettings]
):
    """Send a follow-up message (post-connection) or create a draft for smart_pipeline."""
    if not lead.linkedin_chat_id:
        return

    # Get conversation history for context
    unipile = UnipileService()
    try:
        chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=20)
        conversation_history = _format_conversation(chat_result.get("data", {})) if chat_result.get("success") else ""
    except Exception:
        conversation_history = ""

    claude = ClaudeService()
    sender_context = _get_business_context(db, sequence.business_id)
    lead_data = _get_lead_data(lead)

    # Smart Pipeline: generate phase-aware message and save as draft
    if sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value:
        current_phase = enrollment.current_phase or PipelinePhase.APERTURA.value
        message = claude.generate_smart_pipeline_message(
            lead_data=lead_data,
            sender_context=sender_context,
            conversation_history=conversation_history,
            current_phase=current_phase,
        )

        # Check for existing pending draft (avoid duplicates)
        existing_draft = db.query(DraftMessage).filter(
            DraftMessage.enrollment_id == enrollment.id,
            DraftMessage.status == DraftStatus.PENDING.value,
        ).first()
        if existing_draft:
            return  # Already has a pending draft

        # Save as draft instead of sending
        import uuid
        draft = DraftMessage(
            id=str(uuid.uuid4()),
            enrollment_id=enrollment.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            user_id=enrollment.user_id,
            pipeline_phase=current_phase,
            step_order=enrollment.current_step_order,
            generated_message=message,
            status=DraftStatus.PENDING.value,
        )
        db.add(draft)

        # Pause enrollment until user approves
        enrollment.status = EnrollmentStatus.PAUSED.value
        enrollment.next_step_due_at = None
        db.commit()

        logger.info(
            f"[SmartPipeline] Draft created for {lead.display_name} "
            f"phase={current_phase} (sequence: {sequence.name})"
        )
        return

    # Classic sequence: generate and send immediately
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
        lead.awaiting_reply = True
        db.commit()
        logger.info(f"[Sequence] Follow-up step {step.step_order} sent to {lead.display_name} (sequence: {sequence.name})")
    else:
        # CRITICAL: Handle failure with proper classification and backoff
        _handle_enrollment_failure(enrollment, lead, sequence, settings, result, db, "follow_up")
        db.commit()


async def detect_connection_changes(db: Session):
    """
    Poll Unipile user profiles to detect accepted connections.
    Called every ~30 min from the main scheduler loop.

    Uses get_user_info() per lead to check invitation status,
    since chat attendee_provider_id uses internal LinkedIn IDs
    that don't match the URL slugs stored in our leads.
    """
    # Find sequence enrollments waiting for connection acceptance
    waiting_enrollments = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Lead.status == LeadStatus.INVITATION_SENT.value,
        SequenceEnrollment.next_step_due_at.is_(None)
    ).all()

    # Also check failed enrollments (already_invited)
    failed_already_invited = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.FAILED.value,
        SequenceEnrollment.step_error_category == "already_invited",
        Lead.status == LeadStatus.INVITATION_SENT.value,
    ).all()
    waiting_enrollments = list(waiting_enrollments) + list(failed_already_invited)

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

    unipile = UnipileService()

    # Pre-fetch chats for chat_id lookup (needed to set linkedin_chat_id)
    chat_pid_lookup = {}
    try:
        chats_result = await unipile.get_chats(limit=100, force_refresh=True)
        if chats_result.get("success"):
            chats_data = chats_result.get("data", {})
            chat_items = chats_data.get("items", []) if isinstance(chats_data, dict) else chats_data
            for chat in chat_items:
                att_pid = chat.get("attendee_provider_id")
                if att_pid:
                    chat_pid_lookup[att_pid.lower()] = chat.get("id")
    except Exception as e:
        logger.error(f"[ConnectionDetect] Failed to fetch chats: {e}")

    connected_count = 0

    async def _check_lead_connected(lead):
        """Check if lead accepted connection. Returns chat_id or None."""
        if not lead.linkedin_url:
            return None

        slug = unipile._extract_provider_id(lead.linkedin_url)
        if not slug:
            return None

        try:
            user_info = await unipile.get_user_info(slug, force_refresh=True)
            if not user_info.get("success"):
                return None

            data = user_info.get("data", {})
            internal_pid = data.get("provider_id")

            # Save the internal provider_id for future lookups
            if internal_pid and not lead.linkedin_provider_id:
                lead.linkedin_provider_id = internal_pid

            # Check if connected
            network_distance = data.get("network_distance", "")
            invitation = data.get("invitation") or {}
            inv_status = invitation.get("status", "")

            is_connected = (
                network_distance == "FIRST_DEGREE"
                or inv_status == "ACCEPTED"
            )

            if is_connected:
                chat_id = None
                if internal_pid:
                    chat_id = chat_pid_lookup.get(internal_pid.lower())
                return chat_id or "CONNECTED_NO_CHAT"

            return None

        except Exception as e:
            logger.debug(f"[ConnectionDetect] Error checking {lead.display_name}: {e}")
            return None

    # --- Phase A: Check sequence-enrolled leads ---
    for enrollment in waiting_enrollments:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead:
                continue

            chat_id = await _check_lead_connected(lead)
            if not chat_id:
                continue

            # Connection accepted!
            lead.status = LeadStatus.CONNECTED.value
            lead.connected_at = datetime.utcnow()
            if chat_id != "CONNECTED_NO_CHAT":
                lead.linkedin_chat_id = chat_id

            # AutoOutreach: record acceptance in experiment
            exp_service = ExperimentService()
            exp_service.record_acceptance(db, lead.id)

            # Reactivate failed enrollments
            if enrollment.status == EnrollmentStatus.FAILED.value:
                enrollment.status = EnrollmentStatus.ACTIVE.value
                enrollment.step_attempts = 0
                enrollment.step_last_error = None
                enrollment.step_error_category = None
                enrollment.step_next_retry_at = None
                sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
                if sequence:
                    sequence.active_enrolled = (sequence.active_enrolled or 0) + 1

            # Check if this is a Smart Pipeline sequence
            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            is_pipeline = sequence and (sequence.sequence_mode or "classic") == SequenceMode.SMART_PIPELINE.value

            if is_pipeline:
                # Smart Pipeline: enter apertura phase, wait 24h for them to respond
                enrollment.current_phase = PipelinePhase.APERTURA.value
                enrollment.phase_entered_at = datetime.utcnow()
                enrollment.last_step_completed_at = datetime.utcnow()
                enrollment.next_step_due_at = datetime.utcnow() + timedelta(hours=24)
                enrollment.step_attempts = 0
                enrollment.step_last_error = None
                enrollment.step_error_category = None
                enrollment.step_next_retry_at = None
                logger.info(
                    f"[ConnectionDetect] Smart Pipeline: {lead.display_name} connected, "
                    f"entering apertura phase (draft in 24h if no reply)"
                )
            else:
                # Classic sequence: advance to next step
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
                    if sequence:
                        sequence.completed_count = (sequence.completed_count or 0) + 1
                        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
                    lead.active_sequence_id = None

            connected_count += 1
            db.commit()
            logger.info(f"[ConnectionDetect] {lead.display_name} accepted connection!")

        except Exception as e:
            logger.error(f"[ConnectionDetect] Error checking enrollment {enrollment.id}: {e}")
            db.rollback()
            continue

    # --- Phase B: Check standalone (non-sequence) leads ---
    for lead in standalone_leads:
        try:
            chat_id = await _check_lead_connected(lead)
            if not chat_id:
                continue

            lead.status = LeadStatus.CONNECTED.value
            lead.connected_at = datetime.utcnow()
            if chat_id != "CONNECTED_NO_CHAT":
                lead.linkedin_chat_id = chat_id

            # AutoOutreach: record acceptance in experiment
            exp_service = ExperimentService()
            exp_service.record_acceptance(db, lead.id)

            connected_count += 1
            db.commit()
            logger.info(f"[ConnectionDetect] Standalone lead {lead.display_name} connected")

        except Exception as e:
            logger.error(f"[ConnectionDetect] Error checking standalone lead {lead.id}: {e}")
            db.rollback()
            continue

    if connected_count > 0:
        logger.info(f"[ConnectionDetect] Detected {connected_count} new connections total")
    else:
        logger.info(f"[ConnectionDetect] No new connections detected (checked {total_to_check} leads)")


async def detect_replies(db: Session):
    """
    Check for inbound messages from enrolled leads and auto-exit from sequence.
    Called every 5 minutes (offset from connection detection).
    """
    # Find active enrollments where lead has a chat_id
    # Only check classic sequences - smart_pipeline enrollments are handled by detect_pipeline_replies
    active = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Lead.linkedin_chat_id.isnot(None),
        Sequence.sequence_mode != SequenceMode.SMART_PIPELINE.value,
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
                    lead.awaiting_reply = False

                    # AutoOutreach: record response in experiment
                    exp_service = ExperimentService()
                    exp_service.record_response(db, lead.id)
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
