"""
N8N service for triggering automation workflows.
"""
import logging
from typing import Dict, Any, Optional
import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class N8NService:
    """Service for triggering N8N webhooks."""

    def __init__(self):
        self.base_url = settings.n8n_base_url
        self.linkedin_webhook = settings.n8n_webhook_linkedin

    async def trigger_linkedin_connection(
        self,
        lead_data: Dict[str, Any],
        message: str,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger LinkedIn connection request via N8N.

        Args:
            lead_data: Lead information
            message: Connection message
            account_id: LinkedIn account ID (optional)

        Returns:
            Response from N8N webhook
        """
        webhook_url = f"{self.base_url}{self.linkedin_webhook}"

        payload = {
            "lead": {
                "id": lead_data.get("id"),
                "firstName": lead_data.get("first_name"),
                "lastName": lead_data.get("last_name"),
                "linkedinUrl": lead_data.get("linkedin_url"),
                "salesNavigatorId": lead_data.get("sales_navigator_id"),
                "job_title": lead_data.get("job_title"),
                "company_name": lead_data.get("company_name"),
            },
            "message": message,
            "account_id": account_id,
            "action": "send_connection"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code in (200, 201):
                    logger.info(f"N8N webhook triggered successfully for lead {lead_data.get('id')}")
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": response.json() if response.text else {}
                    }
                else:
                    logger.error(f"N8N webhook failed: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text
                    }

        except httpx.TimeoutException:
            logger.error("N8N webhook timeout")
            return {
                "success": False,
                "error": "Webhook timeout"
            }
        except Exception as e:
            logger.error(f"N8N webhook error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def trigger_email_send(
        self,
        lead_data: Dict[str, Any],
        subject: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Trigger email send via N8N (placeholder for future implementation).

        Args:
            lead_data: Lead information
            subject: Email subject
            body: Email body

        Returns:
            Response from N8N webhook
        """
        # Placeholder - implement when email workflow is ready
        logger.info(f"Email trigger not yet implemented for lead {lead_data.get('id')}")
        return {
            "success": False,
            "error": "Email workflow not yet configured"
        }
