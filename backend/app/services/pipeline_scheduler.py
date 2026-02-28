"""
Smart Pipeline Scheduler - 5-phase response-driven outreach pipeline.

Handles:
1. Detecting replies from pipeline-enrolled leads
2. Analyzing responses with Claude to decide phase transitions
3. Generating and sending phase-appropriate messages
4. Time-based triggers (nurture cadence, reactivation timeout)

Separated from sequence_scheduler.py to avoid regression risk.
"""
import logging
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Lead, AutomationSettings
from ..models.lead import LeadStatus
from ..models.user import LinkedInAccount
from ..models.sequence import (
    Sequence, SequenceEnrollment,
    SequenceStatus, EnrollmentStatus,
    SequenceMode, PipelinePhase,
)
from .unipile_service import UnipileService
from .claude_service import ClaudeService
from .encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────
MAX_MESSAGES_PER_PHASE = 2
MAX_NURTURE_TOUCHES = 4
MAX_REACTIVATION_ATTEMPTS = 1
NURTURE_MIN_DAYS = 42   # ~6 weeks
NURTURE_MAX_DAYS = 56   # ~8 weeks
REACTIVATION_SILENCE_DAYS = 30


# ── Helpers (shared with sequence_scheduler.py) ────────────────

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


def _get_business_context(db: Session, business_id) -> dict:
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
        sender = "You" if msg.get("is_sender") else "Contact"
        text = msg.get("text", msg.get("body", ""))
        if text:
            lines.append(f"{sender}: {text}")

    return "\n".join(lines[-15:])  # Last 15 messages for pipeline (more context)


# ── Core Pipeline Functions ──────────────────────────────────

async def detect_pipeline_replies(db: Session):
    """
    Detect inbound messages for smart-pipeline enrollments
    and trigger phase analysis + transitions.

    Called every ~5 minutes from the main scheduler loop.
    """
    # Find active smart_pipeline enrollments that have a LinkedIn chat
    active = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value,
        Lead.linkedin_chat_id.isnot(None),
        SequenceEnrollment.current_phase.isnot(None),
    ).all()

    if not active:
        return

    logger.info(f"[Pipeline] Checking replies for {len(active)} pipeline enrollments")

    for enrollment in active:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if not lead or not lead.linkedin_chat_id:
                continue

            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            if not sequence or sequence.status != SequenceStatus.ACTIVE.value:
                continue

            # Get Unipile service for this user
            unipile = _get_user_unipile_service(db, enrollment.user_id)

            # Fetch latest messages
            msg_result = await unipile.get_chat_messages(
                lead.linkedin_chat_id, limit=20, force_refresh=True
            )
            if not msg_result.get("success"):
                continue

            messages = msg_result.get("data", {})
            if isinstance(messages, dict):
                messages = messages.get("items", [])

            # Find the latest inbound message
            latest_inbound = None
            latest_inbound_time = None

            for msg in messages:
                if msg.get("is_sender"):
                    continue  # Skip our own messages

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

                # Check if this message is newer than our last tracked response
                reference_time = enrollment.last_response_at or enrollment.phase_entered_at or enrollment.enrolled_at
                if msg_dt > reference_time:
                    if latest_inbound_time is None or msg_dt > latest_inbound_time:
                        latest_inbound = msg
                        latest_inbound_time = msg_dt

            if not latest_inbound:
                continue  # No new reply

            # ── New reply detected! ──
            inbound_text = latest_inbound.get("text", latest_inbound.get("body", ""))
            logger.info(
                f"[Pipeline] Reply detected from {lead.display_name} "
                f"(phase={enrollment.current_phase}): {inbound_text[:80]}..."
            )

            # Store response info
            enrollment.last_response_at = latest_inbound_time
            enrollment.last_response_text = inbound_text

            # Format full conversation for Claude
            conversation_history = _format_conversation(msg_result.get("data", {}))

            # Get context
            sender_context = _get_business_context(db, sequence.business_id)
            lead_data = _get_lead_data(lead)

            # Analyze the response with Claude
            claude = ClaudeService()
            analysis = claude.analyze_phase_response(
                conversation_history=conversation_history,
                current_phase=enrollment.current_phase,
                lead_data=lead_data,
                sender_context=sender_context,
                messages_in_phase=enrollment.messages_in_phase or 0,
            )

            # Store analysis
            enrollment.store_phase_analysis(analysis)

            # Update lead intelligence fields
            if analysis.get("sentiment"):
                lead.sentiment_level = analysis["sentiment"]
            if analysis.get("buying_signals"):
                import json
                lead.buying_signals = json.dumps(analysis["buying_signals"])
            if analysis.get("signal_strength"):
                lead.signal_strength = analysis["signal_strength"]

            # Execute phase transition
            await _handle_phase_transition(
                db, enrollment, lead, sequence, analysis,
                sender_context, lead_data, conversation_history, unipile
            )

            db.commit()

        except Exception as e:
            logger.error(f"[Pipeline] Error processing enrollment {enrollment.id}: {e}")
            continue


async def _handle_phase_transition(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    sequence: Sequence,
    analysis: dict,
    sender_context: dict,
    lead_data: dict,
    conversation_history: str,
    unipile: UnipileService,
):
    """
    Execute the phase transition based on Claude's analysis.

    Outcomes:
    - advance: Move to next phase, generate + send message
    - stay: Stay in current phase, generate + send another message
    - nurture: Move to NURTURE phase, schedule delayed message
    - meeting: Mark as MEETING_SCHEDULED, human takes over
    - park: Mark enrollment as PARKED
    - exit: Mark enrollment as COMPLETED (explicit rejection)
    """
    outcome = analysis.get("outcome", "stay")
    next_phase = analysis.get("next_phase")
    now = datetime.utcnow()

    logger.info(
        f"[Pipeline] Transition for {lead.display_name}: "
        f"{enrollment.current_phase} → outcome={outcome}, next_phase={next_phase}"
    )

    if outcome == "advance":
        if not next_phase:
            # Fallback: infer next phase
            phase_order = ["apertura", "calificacion", "valor"]
            current_idx = phase_order.index(enrollment.current_phase) if enrollment.current_phase in phase_order else -1
            next_phase = phase_order[current_idx + 1] if current_idx < len(phase_order) - 1 else "valor"

        enrollment.current_phase = next_phase
        enrollment.phase_entered_at = now
        enrollment.messages_in_phase = 0

        # Generate and send next phase message
        await _generate_and_send(
            db, enrollment, lead, sequence,
            next_phase, sender_context, lead_data,
            conversation_history, analysis, unipile
        )

    elif outcome == "stay":
        if (enrollment.messages_in_phase or 0) < MAX_MESSAGES_PER_PHASE:
            # Send another message in the same phase
            await _generate_and_send(
                db, enrollment, lead, sequence,
                enrollment.current_phase, sender_context, lead_data,
                conversation_history, analysis, unipile
            )
        else:
            # Max messages reached, force to nurture
            logger.info(f"[Pipeline] Max messages in phase, moving {lead.display_name} to NURTURE")
            _move_to_nurture(enrollment, now)

    elif outcome == "nurture":
        _move_to_nurture(enrollment, now)

    elif outcome == "meeting":
        enrollment.status = EnrollmentStatus.COMPLETED.value
        enrollment.completed_at = now
        enrollment.next_step_due_at = None

        lead.status = LeadStatus.MEETING_SCHEDULED.value
        lead.active_sequence_id = None

        sequence.completed_count = (sequence.completed_count or 0) + 1
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)
        sequence.replied_count = (sequence.replied_count or 0) + 1

        logger.info(f"[Pipeline] 🎯 MEETING for {lead.display_name}! Human takes over.")

    elif outcome == "park":
        enrollment.status = EnrollmentStatus.PARKED.value
        enrollment.completed_at = now
        enrollment.next_step_due_at = None

        lead.active_sequence_id = None
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)

        logger.info(f"[Pipeline] Parked {lead.display_name} (no fit or declined)")

    elif outcome == "exit":
        enrollment.status = EnrollmentStatus.COMPLETED.value
        enrollment.completed_at = now
        enrollment.next_step_due_at = None

        lead.status = LeadStatus.DISQUALIFIED.value
        lead.active_sequence_id = None

        sequence.completed_count = (sequence.completed_count or 0) + 1
        sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)

        logger.info(f"[Pipeline] Exited {lead.display_name} (explicit rejection)")


def _move_to_nurture(enrollment: SequenceEnrollment, now: datetime):
    """Move enrollment to NURTURE phase with delayed scheduling."""
    enrollment.current_phase = PipelinePhase.NURTURE.value
    enrollment.phase_entered_at = now
    enrollment.messages_in_phase = 0

    # Schedule nurture message 6-8 weeks out
    delay_days = random.randint(NURTURE_MIN_DAYS, NURTURE_MAX_DAYS)
    enrollment.next_step_due_at = now + timedelta(days=delay_days)

    logger.info(
        f"[Pipeline] Moving to NURTURE, next touch in {delay_days} days "
        f"(scheduled for {enrollment.next_step_due_at.strftime('%Y-%m-%d')})"
    )


async def _generate_and_send(
    db: Session,
    enrollment: SequenceEnrollment,
    lead: Lead,
    sequence: Sequence,
    phase: str,
    sender_context: dict,
    lead_data: dict,
    conversation_history: str,
    phase_analysis: dict,
    unipile: UnipileService,
):
    """Generate a phase-appropriate message and send it via Unipile."""
    if not lead.linkedin_chat_id:
        logger.warning(f"[Pipeline] Cannot send message to {lead.display_name}: no chat_id")
        return

    # Check working hours
    settings = db.query(AutomationSettings).filter(
        AutomationSettings.user_id == enrollment.user_id
    ).first()
    if settings and not settings.is_working_hour():
        # Don't send outside working hours — schedule for next tick
        logger.info(f"[Pipeline] Outside working hours, deferring message for {lead.display_name}")
        enrollment.next_step_due_at = datetime.utcnow() + timedelta(minutes=30)
        return

    claude = ClaudeService()
    message = claude.generate_phase_message(
        phase=phase,
        lead_data=lead_data,
        sender_context=sender_context,
        conversation_history=conversation_history,
        phase_analysis=phase_analysis,
        messages_in_phase=enrollment.messages_in_phase or 0,
    )

    # Send via Unipile
    result = await unipile.send_message(lead.linkedin_chat_id, message)

    if result.get("success"):
        enrollment.messages_in_phase = (enrollment.messages_in_phase or 0) + 1
        enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
        enrollment.last_step_completed_at = datetime.utcnow()

        # Store message in enrollment history
        msg_key = f"pipeline_{phase}_{enrollment.messages_in_phase}"
        enrollment.store_message(msg_key, message)

        lead.last_message_at = datetime.utcnow()
        if lead.status == LeadStatus.CONNECTED.value:
            lead.status = LeadStatus.IN_CONVERSATION.value

        logger.info(
            f"[Pipeline] Sent {phase} message to {lead.display_name} "
            f"(msg #{enrollment.messages_in_phase} in phase, total #{enrollment.total_messages_sent})"
        )
    else:
        logger.error(
            f"[Pipeline] Failed to send {phase} message to {lead.display_name}: "
            f"{result.get('error')}"
        )


# ── Time-Based Phase Processing ──────────────────────────────

async def process_time_based_phases(db: Session):
    """
    Handle time-based triggers for the smart pipeline:
    1. Nurture messages that are due
    2. Reactivation for leads silent 30+ days

    Called every ~5 minutes from the main scheduler loop.
    """
    now = datetime.utcnow()

    # ── 1. Process due nurture messages ──
    nurture_due = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value,
        SequenceEnrollment.current_phase == PipelinePhase.NURTURE.value,
        SequenceEnrollment.next_step_due_at.isnot(None),
        SequenceEnrollment.next_step_due_at <= now,
        Lead.linkedin_chat_id.isnot(None),
    ).limit(3).all()

    for enrollment in nurture_due:
        try:
            # Check nurture limit
            if (enrollment.nurture_count or 0) >= MAX_NURTURE_TOUCHES:
                # Max nurtures reached → park
                enrollment.status = EnrollmentStatus.PARKED.value
                enrollment.completed_at = now
                enrollment.next_step_due_at = None

                lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
                if lead:
                    lead.active_sequence_id = None

                sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
                if sequence:
                    sequence.active_enrolled = max(0, (sequence.active_enrolled or 0) - 1)

                db.commit()
                logger.info(
                    f"[Pipeline] Parking enrollment {enrollment.id} — "
                    f"max nurture touches ({MAX_NURTURE_TOUCHES}) reached"
                )
                continue

            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            if not lead or not sequence:
                continue

            # Check working hours
            settings = db.query(AutomationSettings).filter(
                AutomationSettings.user_id == enrollment.user_id
            ).first()
            if settings and not settings.is_working_hour():
                continue  # Will retry next tick

            unipile = _get_user_unipile_service(db, enrollment.user_id)
            sender_context = _get_business_context(db, sequence.business_id)
            lead_data = _get_lead_data(lead)

            # Get conversation history
            try:
                chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=20)
                conversation_history = _format_conversation(
                    chat_result.get("data", {})
                ) if chat_result.get("success") else ""
            except Exception:
                conversation_history = ""

            # Generate and send nurture message
            claude = ClaudeService()
            message = claude.generate_phase_message(
                phase=PipelinePhase.NURTURE.value,
                lead_data=lead_data,
                sender_context=sender_context,
                conversation_history=conversation_history,
                phase_analysis=enrollment.get_phase_analysis(),
                messages_in_phase=enrollment.messages_in_phase or 0,
            )

            result = await unipile.send_message(lead.linkedin_chat_id, message)

            if result.get("success"):
                enrollment.nurture_count = (enrollment.nurture_count or 0) + 1
                enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
                enrollment.messages_in_phase = (enrollment.messages_in_phase or 0) + 1
                enrollment.last_step_completed_at = now

                # Store message
                msg_key = f"nurture_{enrollment.nurture_count}"
                enrollment.store_message(msg_key, message)

                lead.last_message_at = now

                # Schedule next nurture touch
                delay_days = random.randint(NURTURE_MIN_DAYS, NURTURE_MAX_DAYS)
                enrollment.next_step_due_at = now + timedelta(days=delay_days)

                db.commit()
                logger.info(
                    f"[Pipeline] Sent nurture #{enrollment.nurture_count} to {lead.display_name}, "
                    f"next in {delay_days} days"
                )
            else:
                logger.error(
                    f"[Pipeline] Failed nurture message for {lead.display_name}: "
                    f"{result.get('error')}"
                )

        except Exception as e:
            logger.error(f"[Pipeline] Error processing nurture for enrollment {enrollment.id}: {e}")
            continue

    # ── 2. Process reactivation triggers ──
    # Find pipeline enrollments in apertura/calificacion/valor
    # where phase_entered_at is 30+ days ago and no response received
    reactivation_cutoff = now - timedelta(days=REACTIVATION_SILENCE_DAYS)

    silent_enrollments = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value,
        SequenceEnrollment.current_phase.in_([
            PipelinePhase.APERTURA.value,
            PipelinePhase.CALIFICACION.value,
            PipelinePhase.VALOR.value,
        ]),
        SequenceEnrollment.phase_entered_at.isnot(None),
        SequenceEnrollment.phase_entered_at <= reactivation_cutoff,
        Lead.linkedin_chat_id.isnot(None),
        # Only trigger if no response was received in this phase
        # (last_response_at is either None or before phase_entered_at)
    ).limit(3).all()

    for enrollment in silent_enrollments:
        try:
            # Skip if they actually responded (check last_response_at vs phase_entered_at)
            if enrollment.last_response_at and enrollment.phase_entered_at:
                if enrollment.last_response_at >= enrollment.phase_entered_at:
                    continue  # They responded in this phase, not silent

            # Check reactivation limit
            if (enrollment.reactivation_count or 0) >= MAX_REACTIVATION_ATTEMPTS:
                # Already tried reactivation, move to nurture
                _move_to_nurture(enrollment, now)
                db.commit()
                logger.info(
                    f"[Pipeline] Moving enrollment {enrollment.id} to NURTURE "
                    f"(max reactivations reached)"
                )
                continue

            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            if not lead or not sequence:
                continue

            # Check working hours
            settings = db.query(AutomationSettings).filter(
                AutomationSettings.user_id == enrollment.user_id
            ).first()
            if settings and not settings.is_working_hour():
                continue

            unipile = _get_user_unipile_service(db, enrollment.user_id)
            sender_context = _get_business_context(db, sequence.business_id)
            lead_data = _get_lead_data(lead)

            # Get conversation history
            try:
                chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=20)
                conversation_history = _format_conversation(
                    chat_result.get("data", {})
                ) if chat_result.get("success") else ""
            except Exception:
                conversation_history = ""

            # Move to reactivation phase
            old_phase = enrollment.current_phase
            enrollment.current_phase = PipelinePhase.REACTIVACION.value
            enrollment.phase_entered_at = now
            enrollment.messages_in_phase = 0
            enrollment.reactivation_count = (enrollment.reactivation_count or 0) + 1

            # Generate and send reactivation message
            claude = ClaudeService()
            message = claude.generate_phase_message(
                phase=PipelinePhase.REACTIVACION.value,
                lead_data=lead_data,
                sender_context=sender_context,
                conversation_history=conversation_history,
                phase_analysis=enrollment.get_phase_analysis(),
                messages_in_phase=0,
            )

            result = await unipile.send_message(lead.linkedin_chat_id, message)

            if result.get("success"):
                enrollment.messages_in_phase = 1
                enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
                enrollment.last_step_completed_at = now

                msg_key = f"reactivacion_{enrollment.reactivation_count}"
                enrollment.store_message(msg_key, message)

                lead.last_message_at = now

                db.commit()
                logger.info(
                    f"[Pipeline] Sent reactivation to {lead.display_name} "
                    f"(was in {old_phase} for 30+ days, attempt #{enrollment.reactivation_count})"
                )
            else:
                # Revert phase change on failure
                enrollment.current_phase = old_phase
                enrollment.reactivation_count = (enrollment.reactivation_count or 0) - 1
                logger.error(
                    f"[Pipeline] Failed reactivation for {lead.display_name}: "
                    f"{result.get('error')}"
                )

        except Exception as e:
            logger.error(f"[Pipeline] Error processing reactivation for enrollment {enrollment.id}: {e}")
            continue

    # ── 3. Process deferred apertura messages ──
    # When a connection is detected outside working hours, the apertura message
    # is deferred: messages_in_phase=0, next_step_due_at is set, phase=APERTURA.
    # Pick these up and send the apertura now (if within working hours).
    deferred_apertura = db.query(SequenceEnrollment).join(
        Lead, SequenceEnrollment.lead_id == Lead.id
    ).join(
        Sequence, SequenceEnrollment.sequence_id == Sequence.id
    ).filter(
        SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        Sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value,
        SequenceEnrollment.current_phase == PipelinePhase.APERTURA.value,
        SequenceEnrollment.messages_in_phase == 0,
        SequenceEnrollment.next_step_due_at.isnot(None),
        SequenceEnrollment.next_step_due_at <= now,
        Lead.linkedin_chat_id.isnot(None),
    ).limit(3).all()

    for enrollment in deferred_apertura:
        try:
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            sequence = db.query(Sequence).filter(Sequence.id == enrollment.sequence_id).first()
            if not lead or not sequence:
                continue

            # Check working hours
            settings = db.query(AutomationSettings).filter(
                AutomationSettings.user_id == enrollment.user_id
            ).first()
            if settings and not settings.is_working_hour():
                continue  # Will retry next tick

            unipile = _get_user_unipile_service(db, enrollment.user_id)
            sender_context = _get_business_context(db, sequence.business_id)
            lead_data = _get_lead_data(lead)

            # Get conversation history
            try:
                chat_result = await unipile.get_chat_messages(lead.linkedin_chat_id, limit=10)
                conversation_history = _format_conversation(
                    chat_result.get("data", {})
                ) if chat_result.get("success") else ""
            except Exception:
                conversation_history = ""

            claude = ClaudeService()
            apertura_msg = claude.generate_phase_message(
                phase=PipelinePhase.APERTURA.value,
                lead_data=lead_data,
                sender_context=sender_context,
                conversation_history=conversation_history,
                messages_in_phase=0,
            )

            result = await unipile.send_message(lead.linkedin_chat_id, apertura_msg)

            if result.get("success"):
                enrollment.messages_in_phase = 1
                enrollment.total_messages_sent = (enrollment.total_messages_sent or 0) + 1
                enrollment.last_step_completed_at = now
                enrollment.next_step_due_at = None  # Pipeline uses reply-based from here
                enrollment.store_message("pipeline_apertura_1", apertura_msg)

                lead.last_message_at = now
                if lead.status == LeadStatus.CONNECTED.value:
                    lead.status = LeadStatus.IN_CONVERSATION.value

                db.commit()
                logger.info(
                    f"[Pipeline] Deferred APERTURA message sent to {lead.display_name} "
                    f"(connection detected outside working hours)"
                )
            else:
                logger.error(
                    f"[Pipeline] Failed deferred apertura for {lead.display_name}: "
                    f"{result.get('error')}"
                )

        except Exception as e:
            logger.error(f"[Pipeline] Error processing deferred apertura for enrollment {enrollment.id}: {e}")
            continue
