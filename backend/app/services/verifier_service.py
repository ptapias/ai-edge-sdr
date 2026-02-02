"""
Million Verifier service for email verification.
"""
import logging
from typing import Dict, Any, List
import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VerifierService:
    """Service for email verification via Million Verifier API."""

    def __init__(self):
        self.api_key = settings.million_verifier_api_key
        self.base_url = "https://api.millionverifier.com/api/v3"

    async def verify_email(self, email: str) -> Dict[str, Any]:
        """
        Verify a single email address.

        Args:
            email: Email address to verify

        Returns:
            Dictionary with verification result:
            - status: 'valid', 'invalid', 'risky', 'unknown'
            - verified: boolean
            - details: additional info
        """
        if not self.api_key:
            logger.warning("Million Verifier API key not configured")
            return {
                "status": "unknown",
                "verified": False,
                "details": "API key not configured"
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/",
                    params={
                        "api": self.api_key,
                        "email": email
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"Million Verifier API error: {response.status_code}")
                    return {
                        "status": "unknown",
                        "verified": False,
                        "details": f"API error: {response.status_code}"
                    }

                data = response.json()

                # Map Million Verifier result to our format
                result_code = data.get("result", "unknown")

                status_map = {
                    "ok": "valid",
                    "catch_all": "risky",
                    "unknown": "unknown",
                    "invalid": "invalid",
                    "disposable": "invalid",
                }

                status = status_map.get(result_code, "unknown")

                return {
                    "status": status,
                    "verified": status == "valid",
                    "details": {
                        "result": result_code,
                        "quality": data.get("quality"),
                        "free": data.get("free"),
                        "role": data.get("role"),
                    }
                }

        except httpx.TimeoutException:
            logger.error(f"Timeout verifying email: {email}")
            return {
                "status": "unknown",
                "verified": False,
                "details": "Verification timeout"
            }
        except Exception as e:
            logger.error(f"Error verifying email {email}: {e}")
            return {
                "status": "unknown",
                "verified": False,
                "details": str(e)
            }

    async def verify_batch(self, emails: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Verify multiple email addresses.

        Args:
            emails: List of email addresses

        Returns:
            Dictionary mapping email to verification result
        """
        results = {}
        for email in emails:
            if email:
                results[email] = await self.verify_email(email)
        return results
