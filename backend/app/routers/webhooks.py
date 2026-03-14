"""
Webhook endpoints for Unipile notifications.
Receives real-time events for new connections and messages.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Lead
from ..models.lead import LeadStatus
from ..models.user import LinkedInAccount
from ..models.sequence import (
    Sequence, SequenceEnrollment, SequenceStep,
    SequenceStatus, EnrollmentStatus, SequenceMode, PipelinePhase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/unipile/connection")
async def handle_new_connection(request: Request):
    """
    Handle Unipile new_relation webhook.
    Fired when someone accepts a LinkedIn connection request.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"[Webhook] New connection event received: {payload}")

    provider_id = payload.get("user_provider_id", "").lower()
    public_identifier = payload.get("user_public_identifier", "").lower()
    full_name = payload.get("user_full_name", "")
    account_id = payload.get("account_id", "")

    if not provider_id and not public_identifier:
        logger.warning("[Webhook] No provider_id or public_identifier in payload")
        return {"status": "ignored", "reason": "no identifier"}

    db = SessionLocal()
    try:
        # Find the user who owns this Unipile account
        linkedin_account = db.query(LinkedInAccount).filter(
            LinkedInAccount.unipile_account_id == account_id
        ).first()

        if not linkedin_account:
            logger.warning(f"[Webhook] No LinkedIn account found for account_id: {account_id}")
            return {"status": "ignored", "reason": "unknown account"}

        user_id = linkedin_account.user_id

        # Find matching lead by LinkedIn URL containing the public_identifier
        lead = None
        if public_identifier:
            lead = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.status == LeadStatus.INVITATION_SENT.value,
                Lead.linkedin_url.ilike(f"%{public_identifier}%")
            ).first()

        if not lead and provider_id:
            # Try matching by provider_id in linkedin_url
            lead = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.status == LeadStatus.INVITATION_SENT.value,
                Lead.linkedin_url.ilike(f"%{provider_id}%")
            ).first()

        if not lead:
            logger.info(
                f"[Webhook] Connection accepted by {full_name} ({public_identifier}) "
                f"but no matching lead with invitation_sent status found"
            )
            return {"status": "ok", "reason": "no matching lead"}

        # Update lead status
        lead.status = LeadStatus.CONNECTED.value
        lead.connected_at = datetime.utcnow()

        logger.info(
            f"[Webhook] Lead {lead.display_name} connected! "
            f"(matched by {public_identifier or provider_id})"
        )

        # Check if lead is enrolled in a sequence waiting for connection
        enrollment = db.query(SequenceEnrollment).filter(
            SequenceEnrollment.lead_id == lead.id,
            SequenceEnrollment.status == EnrollmentStatus.ACTIVE.value,
        ).first()

        if enrollment:
            sequence = db.query(Sequence).filter(
                Sequence.id == enrollment.sequence_id
            ).first()

            if sequence and sequence.sequence_mode == SequenceMode.SMART_PIPELINE.value:
                # Smart pipeline: set to apertura phase
                enrollment.current_phase = PipelinePhase.APERTURA.value
                enrollment.phase_entered_at = datetime.utcnow()
                enrollment.messages_in_phase = 0
                logger.info(
                    f"[Webhook] Pipeline enrollment activated for {lead.display_name} -> APERTURA"
                )
            elif sequence:
                # Classic sequence: advance to next step
                enrollment.current_step_order += 1
                enrollment.last_step_completed_at = datetime.utcnow()

                next_step = db.query(SequenceStep).filter(
                    SequenceStep.sequence_id == enrollment.sequence_id,
                    SequenceStep.step_order == enrollment.current_step_order
                ).first()

                if next_step:
                    from datetime import timedelta
                    enrollment.next_step_due_at = datetime.utcnow() + timedelta(days=next_step.delay_days)
                    logger.info(
                        f"[Webhook] Sequence advanced for {lead.display_name}, "
                        f"next step in {next_step.delay_days} days"
                    )

        db.commit()
        return {"status": "ok", "lead_id": lead.id, "lead_name": lead.display_name}

    except Exception as e:
        logger.error(f"[Webhook] Error processing connection: {e}")
        db.rollback()
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()


@router.post("/unipile/message")
async def handle_new_message(request: Request):
    """
    Handle Unipile new_message webhook.
    Fired when a new LinkedIn message is received.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"[Webhook] New message event received")

    # For now, just log it. The detect_replies scheduler 
    # will pick up the actual message content on next cycle.
    # This webhook mainly serves as a trigger to reduce polling.

    return {"status": "ok"}
