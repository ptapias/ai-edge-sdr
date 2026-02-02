"""
LinkedIn router for Unipile API operations.
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import Lead
from ..models.lead import LeadStatus
from ..services.unipile_service import UnipileService
from ..services.claude_service import ClaudeService
from ..models import BusinessProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])


class InvitationRequest(BaseModel):
    """Request to send invitation to a lead."""
    lead_id: str
    message: Optional[str] = None  # If not provided, use lead.linkedin_message


class BulkInvitationRequest(BaseModel):
    """Request to send invitations to multiple leads."""
    lead_ids: List[str]


@router.get("/status")
async def check_linkedin_connection():
    """
    Check Unipile connection status.

    Returns:
        Connection status and account info
    """
    unipile = UnipileService()
    result = await unipile.check_connection_status()
    return result


@router.post("/send-invitation")
async def send_single_invitation(
    request: InvitationRequest,
    db: Session = Depends(get_db)
):
    """
    Send LinkedIn invitation to a single lead.

    Args:
        request: Invitation request with lead_id and optional message

    Returns:
        Result of the invitation attempt
    """
    lead = db.query(Lead).filter(Lead.id == request.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.linkedin_url:
        raise HTTPException(status_code=400, detail="Lead has no LinkedIn URL")

    message = request.message or lead.linkedin_message
    if not message:
        raise HTTPException(
            status_code=400,
            detail="No message provided and lead has no generated message"
        )

    unipile = UnipileService()
    result = await unipile.send_invitation_by_url(lead.linkedin_url, message)

    if result["success"]:
        lead.status = LeadStatus.INVITATION_SENT.value
        lead.connection_sent_at = datetime.utcnow()
        lead.linkedin_message = message  # Store the message used
        db.commit()

    return {
        "lead_id": lead.id,
        "lead_name": f"{lead.first_name} {lead.last_name}",
        **result
    }


@router.post("/send-invitations/bulk")
async def send_bulk_invitations(
    request: BulkInvitationRequest,
    db: Session = Depends(get_db)
):
    """
    Send LinkedIn invitations to multiple leads.

    Note: This sends invitations sequentially to avoid rate limiting.
    For production use with many leads, use the automatic mode instead.

    Args:
        request: Bulk invitation request with list of lead_ids

    Returns:
        Results for each lead
    """
    results = []
    unipile = UnipileService()

    for lead_id in request.lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            results.append({
                "lead_id": lead_id,
                "success": False,
                "error": "Lead not found"
            })
            continue

        if not lead.linkedin_url:
            results.append({
                "lead_id": lead_id,
                "success": False,
                "error": "No LinkedIn URL"
            })
            continue

        if not lead.linkedin_message:
            results.append({
                "lead_id": lead_id,
                "success": False,
                "error": "No message generated"
            })
            continue

        # Check if already sent
        if lead.status == LeadStatus.INVITATION_SENT.value:
            results.append({
                "lead_id": lead_id,
                "success": False,
                "error": "Invitation already sent"
            })
            continue

        result = await unipile.send_invitation_by_url(
            lead.linkedin_url,
            lead.linkedin_message
        )

        if result["success"]:
            lead.status = LeadStatus.INVITATION_SENT.value
            lead.connection_sent_at = datetime.utcnow()

        results.append({
            "lead_id": lead_id,
            "lead_name": f"{lead.first_name} {lead.last_name}",
            **result
        })

    db.commit()

    successful = sum(1 for r in results if r.get("success"))
    return {
        "total": len(request.lead_ids),
        "successful": successful,
        "failed": len(request.lead_ids) - successful,
        "results": results
    }


@router.get("/chats")
async def get_linkedin_chats(
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get LinkedIn chats from Unipile.

    Args:
        limit: Maximum number of chats to return

    Returns:
        List of chats
    """
    unipile = UnipileService()
    result = await unipile.get_chats(limit=limit)
    return result


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get messages from a specific LinkedIn chat.

    Args:
        chat_id: Unipile chat ID
        limit: Maximum number of messages to return

    Returns:
        List of messages
    """
    unipile = UnipileService()
    result = await unipile.get_chat_messages(chat_id, limit=limit)
    return result


@router.post("/chats/{chat_id}/send")
async def send_chat_message(
    chat_id: str,
    text: str,
    db: Session = Depends(get_db)
):
    """
    Send a message in a LinkedIn chat.

    Args:
        chat_id: Unipile chat ID
        text: Message text to send

    Returns:
        Result of send operation
    """
    unipile = UnipileService()
    result = await unipile.send_message(chat_id, text)

    # Update last_message_at for any lead associated with this chat
    if result["success"]:
        lead = db.query(Lead).filter(Lead.linkedin_chat_id == chat_id).first()
        if lead:
            lead.last_message_at = datetime.utcnow()
            if lead.status == LeadStatus.CONNECTED.value:
                lead.status = LeadStatus.IN_CONVERSATION.value
            db.commit()

    return result


@router.get("/user/{provider_id}")
async def get_linkedin_user(provider_id: str):
    """
    Get LinkedIn user information.

    Args:
        provider_id: LinkedIn username/provider ID

    Returns:
        User information from Unipile
    """
    unipile = UnipileService()
    result = await unipile.get_user_info(provider_id)
    return result


class GenerateReplyRequest(BaseModel):
    """Request to generate a contextual reply."""
    conversation_history: str  # Formatted conversation history
    contact_name: str
    contact_job_title: Optional[str] = None
    contact_company: Optional[str] = None


@router.post("/generate-reply")
def generate_conversation_reply(
    request: GenerateReplyRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a contextual AI reply for an ongoing conversation.

    Args:
        request: Conversation context and contact info

    Returns:
        Generated reply message
    """
    # Get default business profile for sender context
    profile = db.query(BusinessProfile).filter(BusinessProfile.is_default == True).first()

    sender_context = None
    if profile:
        sender_context = {
            "sender_name": profile.sender_name,
            "sender_role": profile.sender_role,
            "sender_company": profile.sender_company,
            "sender_context": profile.sender_context,
        }

    contact_info = {
        "name": request.contact_name,
        "job_title": request.contact_job_title or "Unknown",
        "company": request.contact_company or "Unknown"
    }

    claude = ClaudeService()
    reply = claude.generate_conversation_reply(
        conversation_history=request.conversation_history,
        contact_info=contact_info,
        sender_context=sender_context
    )

    return {
        "reply": reply,
        "length": len(reply)
    }
