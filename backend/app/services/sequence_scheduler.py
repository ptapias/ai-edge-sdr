"""
Sequence scheduler - processes automated sequence steps.

Handles:
1. Executing due sequence actions (connection requests + follow-ups)
2. Detecting connection acceptances via Unipile chat polling
3. Detecting replies and auto-exiting leads from sequences
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Lead, AutomationSettings, InvitationLog, Campaign
from ..models.lead import LeadStatus
from ..models.user import LinkedInAccount
from ..models.sequence import (
    Sequence, SequenceStep, SequenceEnrollment,
    SequenceStatus, StepType, EnrollmentStatus,
    SequenceMode, PipelinePhase
)
from .unipile_service import UnipileService
from .claude_service import ClaudeService
from .encryption_service import get_encryption_service

logger = logging.getLogger(__name__)


def _get_user_unipile_service(db: Session, user_id: str) -> UnipileService:
    """Get UnipileService with user's credentials if available, else default."""
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == user_id,
        LinkedInAccount.is_connected == True
    ).first()

    if linkedin_account and linkedin_account.unipile_api_key_encrypted:
        encryption_service = get_encryption_service()
        api_key = encryption_service.decrypt(linkedin_account.unipile_api_key_encrypted)
        account_id = linkedin_account.unipile_account_id
        return UnipileService(api_key=api_key, account_id=account_id)
    else:
        return UnipileService()


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


async def process_sequence_actions(db: Session):
    """
    Process all due sequence actions across all users.
    Called every 30 seconds from the main scheduler loop.
    """
    now = datetime.utcnow()

    # Find enrollments where next_step_due_at <= now AND status = active
    # Note: smart_pipeline enrollments ARE included here for step 1 (connection request).
    # After the connection request is sent, next_step_due_at=None prevents re-processing.
    # Post-connection phases are handled by pipeline_scheduler.py.
    due_enrollments = db.query(SequenceEnrollment).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        SequenceEnrollment.next_step_due_at.isnot(None),
        SequenceEnrollment.next_step_due_at <= now,
    ).limit(5).all()  # Process max 5 per tick to avoid overload

    if due_enrollments:
        logger.info(f"[Sequence] Found {len(due_enrollments)} due enrollments to process")

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

    # Send via Unipile (use per-user credentials)
    unipile = _get_user_unipile_service(db, enrollment.user_id)
    result = await unipile.send_invitation_by_url(lead.linkedin_url, message)

    # Log the invitation attempt
    campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first() if lead.campaign_id else None
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
        mode="automatic"
    )
    db.add(log)

    if result.get("success"):
        # Update lead
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()
        lead.linkedin_message = message

        # Update enrollment - now waiting for connection acceptance
        enrollment.last_step_completed_at = datetime.utcnow()
        enrollment.next_step_due_at = None  # Will be set when connection detected
        enrollment.store_message(step.step_order, message)

        # Update automation settings counter
        if settings:
            settings.invitations_sent_today = (settings.invitations_sent_today or 0) + 1
            settings.last_invitation_at = datetime.utcnow()

        db.commit()
        logger.info(f"[Sequence] Connection request sent to {lead.display_name} (sequence: {sequence.name})")
    else:
        logger.warning(f"[Sequence] Connection request failed for {lead.display_name}: {result.get('error')}")
        db.commit()  # Still commit the log


async def _execute_follow_up(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    step: SequenceStep,
    sequence: Sequence,
    settings: Optional[AutomationSettings]
):
    """Send a follow-up message (post-connection)."""
    # Respect working hours for follow-up messages
    if settings and not settings.is_working_hour():
        return  # Will retry next tick

    if not lead.linkedin_chat_id:
        # Can't send without chat ID; skip for now, connection detection will handle this
        return

    # Get conversation history for context (use per-user credentials)
    unipile = _get_user_unipile_service(db, enrollment.user_id)
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
        logger.warning(f"[Sequence] Follow-up failed for {lead.display_name}: {result.get('error')}")


async def detect_connection_changes(db: Session):
    """
    Poll Unipile chats to detect accepted connections for enrolled leads.
    Called every 5 minutes from the main scheduler loop.
    """
    # Find enrollments waiting for connection acceptance
    waiting = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Lead.status == LeadStatus.INVITATION_SENT.value,
        SequenceEnrollment.next_step_due_at.is_(None)  # Waiting for connection
    ).all()

    if not waiting:
        return

    logger.info(f"[Sequence] Checking connection status for {len(waiting)} enrolled leads")

    # Group enrollments by user_id to use per-user credentials
    user_ids = set(e.user_id for e in waiting if e.user_id)
    if not user_ids:
        return

    # Use first user's credentials (typically single-user system)
    user_id = next(iter(user_ids))
    unipile = _get_user_unipile_service(db, user_id)
    try:
        chats_result = await unipile.get_chats(limit=100)
    except Exception as e:
        logger.error(f"[Sequence] Failed to fetch chats for connection detection: {e}")
        return

    logger.info(f"[Sequence] Connection check - from_cache: {chats_result.get('from_cache', False)}")
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

    # Check each waiting enrollment
    connected_count = 0
    for enrollment in waiting:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead or not lead.linkedin_url:
                continue

            # Extract provider_id from lead's LinkedIn URL
            provider_id = unipile._extract_provider_id(lead.linkedin_url)
            if not provider_id:
                continue

            # Check if this lead appears in chats (= connected)
            chat_id = chat_lookup.get(provider_id.lower())
            if chat_id:
                # Connection accepted!
                lead.status = LeadStatus.CONNECTED.value
                lead.connected_at = datetime.utcnow()
                lead.linkedin_chat_id = chat_id

                # Check if this is a smart_pipeline sequence
                sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
                is_pipeline = sequence and sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value

                if is_pipeline:
                    # Smart Pipeline: initialize APERTURA phase
                    enrollment.current_phase = PipelinePhase.APERTURA.value
                    enrollment.phase_entered_at = datetime.utcnow()
                    enrollment.messages_in_phase = 0
                    enrollment.last_step_completed_at = datetime.utcnow()
                    enrollment.next_step_due_at = None  # Pipeline uses reply-based, not timer

                    # Respect working hours - defer apertura message if outside hours
                    user_settings = db.query(AutomationSettings).filter(
                        AutomationSettings.user_id == enrollment.user_id
                    ).first()
                    if user_settings and not user_settings.is_working_hour():
                        # Connection is recorded, but apertura msg will be sent
                        # by pipeline_scheduler on next tick inside working hours
                        enrollment.next_step_due_at = datetime.utcnow()  # Signal to pipeline scheduler
                        logger.info(
                            f"[Sequence] Connection detected for {lead.display_name} (pipeline), "
                            f"apertura deferred - outside working hours"
                        )
                    else:
                        # Generate and send the first apertura message immediately
                        try:
                            from .pipeline_scheduler import (
                                _get_business_context as _pb_ctx,
                                _get_lead_data as _pl_data,
                                _format_conversation,
                            )
                            sender_ctx = _pb_ctx(db, sequence.business_id)
                            lead_d = _pl_data(lead)

                            # Get conversation history (the connection request message)
                            try:
                                chat_result = await unipile.get_chat_messages(chat_id, limit=10)
                                conv_history = _format_conversation(
                                    chat_result.get("data", {})
                                ) if chat_result.get("success") else ""
                            except Exception:
                                conv_history = ""

                            claude = ClaudeService()
                            apertura_msg = claude.generate_phase_message(
                                phase=PipelinePhase.APERTURA.value,
                                lead_data=lead_d,
                                sender_context=sender_ctx,
                                conversation_history=conv_history,
                                messages_in_phase=0,
                            )

                            send_result = await unipile.send_message(chat_id, apertura_msg)
                            if send_result.get("success"):
                                enrollment.messages_in_phase = 1
                                enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
                                enrollment.store_message("pipeline_apertura_1", apertura_msg)
                                lead.last_message_at = datetime.utcnow()
                                lead.status = LeadStatus.IN_CONVERSATION.value
                                logger.info(
                                    f"[Sequence] Pipeline APERTURA message sent to {lead.display_name} "
                                    f"on connection acceptance"
                                )
                            else:
                                logger.warning(
                                    f"[Sequence] Failed to send apertura message to {lead.display_name}: "
                                    f"{send_result.get('error')}"
                                )
                        except Exception as e:
                            logger.error(f"[Sequence] Error sending apertura on connection: {e}")

                else:
                    # Classic mode: advance enrollment to next step
                    enrollment.current_step_order += 1
                    enrollment.last_step_completed_at = datetime.utcnow()

                    next_step = db.query(SequenceStep).filter(
                        SequenceStep.sequence_id == enrollment.sequence_id,
                        SequenceStep.step_order == enrollment.current_step_order
                    ).first()

                    if next_step:
                        enrollment.next_step_due_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
                        logger.info(
                            f"[Sequence] Connection detected for {lead.display_name}, "
                            f"next step in {next_step.delay_days} days"
                        )
                    else:
                        # No more steps after connection
                        enrollment.status = EnrollmentStatus.COMPLETED.value
                        enrollment.completed_at = datetime.utcnow()
                        if sequence:
                            sequence.completed_count = (sequence.completed_count or 0) + 1
                            sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
                        lead.active_sequence_id = None

                connected_count += 1
                db.commit()

        except Exception as e:
            logger.error(f"[Sequence] Error checking connection for enrollment {enrollment.id}: {e}")
            continue

    if connected_count > 0:
        logger.info(f"[Sequence] Detected {connected_count} new connections")


async def detect_replies(db: Session):
    """
    Check for inbound messages from enrolled leads and auto-exit from sequence.
    Called every 5 minutes (offset from connection detection).
    """
    # Find active CLASSIC enrollments where lead has a chat_id
    # Exclude smart_pipeline enrollments (handled by pipeline_scheduler.py)
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

    # Use per-user credentials
    user_ids = set(e.user_id for e in active if e.user_id)
    user_id = next(iter(user_ids)) if user_ids else None
    unipile = _get_user_unipile_service(db, user_id) if user_id else UnipileService()
    replied_count = 0

    for enrollment in active:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead or not lead.linkedin_chat_id:
                continue

            # Check latest messages
            msg_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=5)
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
