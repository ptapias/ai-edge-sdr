"""
Intelligence router for AI-powered lead analysis and prioritization.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Lead, User, BusinessProfile
from ..models.lead import LeadStatus
from ..services.claude_service import ClaudeService
from ..services.unipile_service import UnipileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


def compute_priority_score(lead: Lead) -> int:
    """
    Compute priority score (0-100) based on:
    - AI score (30%)
    - Recency of activity (30%)
    - Pipeline stage weight (20%)
    - Has conversation (20%)
    """
    score_component = 0
    if lead.score is not None:
        score_component = lead.score * 0.3

    # Recency: more recent = higher score
    recency_component = 0
    last_activity = lead.last_message_at or lead.connected_at or lead.connection_sent_at or lead.updated_at
    if last_activity:
        days_since = (datetime.utcnow() - last_activity).days
        if days_since <= 1:
            recency_component = 30
        elif days_since <= 3:
            recency_component = 25
        elif days_since <= 7:
            recency_component = 20
        elif days_since <= 14:
            recency_component = 15
        elif days_since <= 30:
            recency_component = 10
        else:
            recency_component = 5

    # Stage weight: later stages = higher priority
    stage_weights = {
        LeadStatus.IN_CONVERSATION.value: 20,
        LeadStatus.MEETING_SCHEDULED.value: 18,
        LeadStatus.CONNECTED.value: 15,
        LeadStatus.QUALIFIED.value: 12,
        LeadStatus.INVITATION_SENT.value: 10,
        LeadStatus.NEW.value: 5,
    }
    stage_component = stage_weights.get(lead.status, 5)

    # Has conversation
    conversation_component = 20 if lead.linkedin_chat_id else 0

    total = int(score_component + recency_component + stage_component + conversation_component)
    return min(100, max(0, total))


@router.get("/focus-leads")
def get_focus_leads(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top priority leads to focus on.
    Ranks leads by computed priority score considering:
    - AI score, recency, pipeline stage, conversation status.
    """
    # Get leads that are actionable (not closed/disqualified)
    actionable_statuses = [
        LeadStatus.CONNECTED.value,
        LeadStatus.IN_CONVERSATION.value,
        LeadStatus.MEETING_SCHEDULED.value,
        LeadStatus.INVITATION_SENT.value,
        LeadStatus.QUALIFIED.value,
        LeadStatus.NEW.value,
        LeadStatus.PENDING.value,
    ]

    leads = (
        db.query(Lead)
        .filter(
            Lead.user_id == current_user.id,
            Lead.status.in_(actionable_statuses)
        )
        .all()
    )

    # Compute priority and sort
    scored_leads = []
    for lead in leads:
        priority = compute_priority_score(lead)
        scored_leads.append({
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
            "job_title": lead.job_title,
            "company_name": lead.company_name,
            "status": lead.status,
            "score": lead.score,
            "score_label": lead.score_label,
            "priority_score": priority,
            "has_conversation": lead.linkedin_chat_id is not None,
            "linkedin_chat_id": lead.linkedin_chat_id,
            "sentiment_level": lead.sentiment_level if hasattr(lead, 'sentiment_level') else None,
            "last_activity": (
                lead.last_message_at or lead.connected_at or lead.connection_sent_at or lead.updated_at
            ).isoformat() if (lead.last_message_at or lead.connected_at or lead.connection_sent_at or lead.updated_at) else None,
            "recommended_action": _get_recommended_action(lead),
        })

    scored_leads.sort(key=lambda x: x["priority_score"], reverse=True)

    return {"focus_leads": scored_leads[:limit]}


def _get_recommended_action(lead: Lead) -> str:
    """Suggest next action based on lead status and data."""
    if lead.status == LeadStatus.IN_CONVERSATION.value:
        return "Follow up on conversation"
    if lead.status == LeadStatus.CONNECTED.value:
        if lead.linkedin_message:
            return "Start conversation"
        return "Generate first message"
    if lead.status == LeadStatus.MEETING_SCHEDULED.value:
        return "Prepare for meeting"
    if lead.status == LeadStatus.INVITATION_SENT.value:
        return "Waiting for acceptance"
    if lead.status == LeadStatus.QUALIFIED.value:
        return "Schedule meeting"
    if lead.status in (LeadStatus.NEW.value, LeadStatus.PENDING.value):
        if lead.linkedin_message:
            return "Send connection request"
        return "Generate message & send"
    return "Review lead"


@router.post("/analyze-signals/{lead_id}")
async def analyze_buying_signals(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze conversation for buying signals."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.user_id == current_user.id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.linkedin_chat_id:
        return {
            "lead_id": lead_id,
            "signals": [],
            "signal_strength": "none",
            "summary": "No conversation found for this lead."
        }

    # Get conversation from Unipile
    try:
        from ..models.user import LinkedInAccount
        from ..services.encryption_service import get_encryption_service

        linkedin_account = db.query(LinkedInAccount).filter(
            LinkedInAccount.user_id == current_user.id,
            LinkedInAccount.is_connected == True
        ).first()

        if linkedin_account and linkedin_account.unipile_api_key_encrypted:
            encryption_service = get_encryption_service()
            api_key = encryption_service.decrypt(linkedin_account.unipile_api_key_encrypted)
            account_id = linkedin_account.unipile_account_id
            unipile_service = UnipileService(api_key=api_key, account_id=account_id)
        else:
            unipile_service = UnipileService()

        messages_response = await unipile_service.get_chat_messages(lead.linkedin_chat_id)
        messages = messages_response.get("data", {}).get("items", [])

        if not messages:
            return {
                "lead_id": lead_id,
                "signals": [],
                "signal_strength": "none",
                "summary": "No messages found in conversation."
            }

        # Format conversation
        conversation_text = ""
        for msg in messages:
            sender = "You" if msg.get("is_sender", 0) == 1 else "Contact"
            text = msg.get("text", msg.get("body", ""))
            conversation_text += f"{sender}: {text}\n"

        # Analyze with Claude
        claude_service = ClaudeService()
        analysis = claude_service.detect_buying_signals(conversation_text)

        # Update lead with analysis
        if hasattr(lead, 'buying_signals'):
            import json
            lead.buying_signals = json.dumps(analysis.get("signals", []))
            lead.signal_strength = analysis.get("signal_strength", "none")
            lead.sentiment_level = analysis.get("sentiment", "warm")
            lead.sentiment_reason = analysis.get("summary", "")
            lead.sentiment_analyzed_at = datetime.utcnow()
            db.commit()

        return {
            "lead_id": lead_id,
            **analysis
        }

    except Exception as e:
        logger.error(f"Failed to analyze signals for lead {lead_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/stage-recommendation/{lead_id}")
def get_stage_recommendation(
    lead_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI recommendation for lead stage transition."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.user_id == current_user.id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    claude_service = ClaudeService()

    lead_data = {
        "name": f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
        "job_title": lead.job_title,
        "company": lead.company_name,
        "current_stage": lead.status,
        "score": lead.score,
        "score_label": lead.score_label,
        "has_conversation": lead.linkedin_chat_id is not None,
        "connected": lead.connected_at is not None,
        "invitation_sent": lead.connection_sent_at is not None,
    }

    recommendation = claude_service.recommend_stage_transition(lead_data)

    # Update lead with recommendation
    if hasattr(lead, 'ai_recommended_stage'):
        lead.ai_recommended_stage = recommendation.get("recommended_stage")
        lead.ai_recommendation_reason = recommendation.get("reason")
        lead.priority_score = compute_priority_score(lead)
        db.commit()

    return {
        "lead_id": lead_id,
        **recommendation
    }
