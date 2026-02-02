"""
LinkedIn router for Unipile API operations.

CRITICAL: Uses caching to prevent LinkedIn bans from excessive API calls.
- Chat list: 30-60 min cache
- Profiles: 24-30 hour cache
- Messages: 5-10 min cache
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
from ..services.cache_service import get_unipile_cache
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


@router.get("/cache-status")
async def get_cache_status():
    """
    Get cache status for all Unipile data.

    Returns info about when data will refresh to help understand API call frequency.
    IMPORTANT: This helps monitor that we're not making too many LinkedIn API calls.
    """
    cache = get_unipile_cache()
    chats_info = cache.get_chats_cache_info()

    return {
        "chats": chats_info,
        "message": "Cache helps prevent LinkedIn bans by limiting API calls",
        "refresh_intervals": {
            "chats": "30-60 minutes (random)",
            "profiles": "24-30 hours (random)",
            "messages": "5-10 minutes (random)"
        }
    }


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
    limit: int = Query(50, ge=1, le=100),
    enrich: bool = Query(True, description="Enrich chats with attendee profile info"),
    force_refresh: bool = Query(False, description="Force refresh from LinkedIn API (use sparingly!)")
):
    """
    Get LinkedIn chats from Unipile, optionally enriched with attendee profile info.

    IMPORTANT: Results are cached 30-60 min to prevent LinkedIn bans.
    Only use force_refresh when absolutely necessary.

    Args:
        limit: Maximum number of chats to return
        enrich: Whether to fetch attendee profile details (name, job title)
        force_refresh: Bypass cache (use sparingly to avoid LinkedIn ban!)

    Returns:
        List of chats with enriched attendee information and cache info
    """
    unipile = UnipileService()
    result = await unipile.get_chats(limit=limit, force_refresh=force_refresh)

    if not result.get("success") or not enrich:
        return result

    # Enrich chats with attendee profile information
    chats = result.get("data", {})
    items = chats.get("items", []) if isinstance(chats, dict) else chats

    enriched_items = []
    for chat in items:
        enriched_chat = dict(chat)

        # Try to get attendee provider_id from various possible locations
        attendee_provider_id = None

        # Check attendees array
        attendees = chat.get("attendees", [])
        if attendees and len(attendees) > 0:
            attendee = attendees[0]
            attendee_provider_id = attendee.get("provider_id") or attendee.get("identifier")

        # If no attendees, try other fields
        if not attendee_provider_id:
            attendee_provider_id = chat.get("attendee_provider_id") or chat.get("provider_id")

        # Fetch profile info if we have a provider_id
        if attendee_provider_id:
            try:
                profile_result = await unipile.get_user_info(attendee_provider_id)
                if profile_result.get("success"):
                    profile_data = profile_result.get("data", {})
                    # Add enriched info to chat
                    enriched_chat["attendee_name"] = (
                        profile_data.get("full_name") or
                        f"{profile_data.get('first_name', '')} {profile_data.get('last_name', '')}".strip() or
                        profile_data.get("name")
                    )
                    enriched_chat["attendee_job_title"] = (
                        profile_data.get("headline") or
                        profile_data.get("occupation") or
                        profile_data.get("job_title")
                    )
                    enriched_chat["attendee_profile_url"] = profile_data.get("profile_url") or profile_data.get("linkedin_url")
                    enriched_chat["attendee_profile_picture"] = profile_data.get("profile_picture") or profile_data.get("picture_url")
            except Exception as e:
                logger.warning(f"Failed to enrich chat with profile info: {e}")

        enriched_items.append(enriched_chat)

    # Return enriched result
    if isinstance(chats, dict):
        result["data"]["items"] = enriched_items
    else:
        result["data"] = enriched_items

    return result


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    limit: int = Query(50, ge=1, le=100),
    force_refresh: bool = Query(False, description="Force refresh from LinkedIn API"),
    analyze: bool = Query(False, description="Analyze conversation sentiment (only on new messages)")
):
    """
    Get messages from a specific LinkedIn chat.

    IMPORTANT: Results are cached 5-10 min to prevent LinkedIn bans.
    Conversation analysis only runs when there are new messages.

    Args:
        chat_id: Unipile chat ID
        limit: Maximum number of messages to return
        force_refresh: Bypass cache (use sparingly!)
        analyze: Run sentiment analysis if there are new messages

    Returns:
        List of messages with cache info and optional analysis
    """
    unipile = UnipileService()
    result = await unipile.get_chat_messages(chat_id, limit=limit, force_refresh=force_refresh)

    # Only analyze if requested AND there are new messages (to save API calls)
    if analyze and result.get("success") and result.get("has_new_messages"):
        try:
            # Get messages for analysis
            messages_data = result.get("data", {})
            messages_list = messages_data.get("items", []) if isinstance(messages_data, dict) else messages_data

            if messages_list:
                # Format conversation for analysis
                conversation_text = []
                for msg in reversed(messages_list[-10:]):  # Last 10 messages
                    sender = "You" if msg.get("is_sender") == 1 else "Contact"
                    text = msg.get("text", msg.get("body", ""))
                    conversation_text.append(f"{sender}: {text}")

                # Analyze with Claude
                claude = ClaudeService()
                analysis = claude.analyze_conversation_sentiment("\n".join(conversation_text))
                result["analysis"] = analysis
        except Exception as e:
            logger.warning(f"Failed to analyze conversation: {e}")

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


class AnalyzeConversationRequest(BaseModel):
    """Request to analyze conversation sentiment."""
    conversation_history: str  # Formatted conversation history


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


@router.post("/analyze-conversation")
def analyze_conversation(request: AnalyzeConversationRequest):
    """
    Analyze a conversation to determine engagement level (hot/warm/cold).

    IMPORTANT: Only call this when there are new messages to save API costs.

    Args:
        request: Conversation history text

    Returns:
        Analysis with level, reason, and next_action
    """
    claude = ClaudeService()
    analysis = claude.analyze_conversation_sentiment(request.conversation_history)

    return {
        "success": True,
        **analysis
    }
