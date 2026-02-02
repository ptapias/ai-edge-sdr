"""
Unipile service for LinkedIn automation via Unipile API.

CRITICAL: Uses caching to prevent excessive API calls and LinkedIn bans.
- Chats: cached 30-60 min (random)
- Profiles: cached 24-30 hours (random)
- Messages: cached 5-10 min (random)
"""
import logging
import re
from typing import Dict, Any, Optional, List
import httpx

from ..config import get_settings
from .cache_service import get_unipile_cache

logger = logging.getLogger(__name__)
settings = get_settings()


class UnipileService:
    """Service for Unipile API interactions (LinkedIn automation)."""

    def __init__(self):
        self.base_url = settings.unipile_api_url
        self.api_key = settings.unipile_api_key
        self.account_id = settings.unipile_account_id
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _extract_provider_id(self, linkedin_url: str) -> Optional[str]:
        """
        Extract LinkedIn provider ID (username/handle) from LinkedIn URL.

        Args:
            linkedin_url: LinkedIn profile URL

        Returns:
            Provider ID (username) or None
        """
        if not linkedin_url:
            return None

        # Pattern to match LinkedIn profile URLs
        patterns = [
            r'linkedin\.com/in/([^/?]+)',
            r'linkedin\.com/sales/people/([^/?]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, linkedin_url)
            if match:
                return match.group(1)

        return None

    async def get_user_info(self, provider_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get LinkedIn user information (cached 24-30 hours).

        Args:
            provider_id: LinkedIn username/provider ID
            force_refresh: If True, bypass cache

        Returns:
            User information from Unipile
        """
        cache = get_unipile_cache()

        # Check cache first (profiles are stable, cache 24+ hours)
        if not force_refresh:
            cached_data, is_fresh = cache.get_profile(provider_id)
            if cached_data is not None and is_fresh:
                logger.debug(f"Profile cache HIT for {provider_id}")
                return {
                    "success": True,
                    "data": cached_data,
                    "from_cache": True
                }

        # Cache miss or expired - make API call
        logger.info(f"Profile cache MISS for {provider_id} - fetching from API")
        url = f"{self.base_url}/users/{provider_id}"
        params = {"account_id": self.account_id}

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    # Store in cache
                    cache.set_profile(provider_id, data)
                    return {
                        "success": True,
                        "data": data,
                        "from_cache": False
                    }
                else:
                    logger.error(f"Failed to get user info: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_invitation(
        self,
        provider_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send LinkedIn connection invitation.

        Args:
            provider_id: LinkedIn username/provider ID
            message: Connection message (max 300 chars)

        Returns:
            Response from Unipile API
        """
        url = f"{self.base_url}/users/invite"

        payload = {
            "provider_id": provider_id,
            "account_id": self.account_id,
            "message": message[:300]  # Ensure max 300 chars
        }

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code in (200, 201):
                    logger.info(f"Invitation sent successfully to {provider_id}")
                    return {
                        "success": True,
                        "data": response.json() if response.text else {},
                        "status_code": response.status_code
                    }
                else:
                    logger.error(f"Failed to send invitation: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error sending invitation: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_invitation_by_url(
        self,
        linkedin_url: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send LinkedIn connection invitation using profile URL.

        Args:
            linkedin_url: LinkedIn profile URL
            message: Connection message (max 300 chars)

        Returns:
            Response from Unipile API
        """
        provider_id = self._extract_provider_id(linkedin_url)

        if not provider_id:
            return {
                "success": False,
                "error": f"Could not extract provider ID from URL: {linkedin_url}"
            }

        return await self.send_invitation(provider_id, message)

    async def get_chats(self, limit: int = 50, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get LinkedIn chat list (cached 30-60 min with random jitter).

        IMPORTANT: This cache prevents excessive API calls to LinkedIn.
        The random TTL simulates human behavior.

        Args:
            limit: Maximum number of chats to return
            force_refresh: If True, bypass cache

        Returns:
            List of chats with cache metadata
        """
        cache = get_unipile_cache()

        # Check cache first
        if not force_refresh:
            cached_data, is_fresh = cache.get_chats()
            if cached_data is not None and is_fresh:
                cache_info = cache.get_chats_cache_info()
                logger.debug(f"Chats cache HIT - expires in {cache_info['expires_in_seconds']}s")
                return {
                    "success": True,
                    "data": cached_data,
                    "from_cache": True,
                    "cache_info": cache_info
                }

        # Cache miss or expired - make API call
        logger.info("Chats cache MISS - fetching from LinkedIn API")
        url = f"{self.base_url}/chats"
        params = {
            "account_id": self.account_id,
            "limit": limit
        }

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    # Store in cache with random TTL (30-60 min)
                    cache.set_chats(data)
                    cache_info = cache.get_chats_cache_info()
                    return {
                        "success": True,
                        "data": data,
                        "from_cache": False,
                        "cache_info": cache_info
                    }
                else:
                    logger.error(f"Failed to get chats: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error getting chats: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_chat_messages(
        self,
        chat_id: str,
        limit: int = 50,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get messages from a specific chat (cached 5-10 min with random jitter).

        Args:
            chat_id: Chat ID from Unipile
            limit: Maximum number of messages to return
            force_refresh: If True, bypass cache

        Returns:
            List of messages with has_new_messages flag
        """
        cache = get_unipile_cache()

        # Check cache first
        if not force_refresh:
            cached_data, is_fresh, _ = cache.get_messages(chat_id)
            if cached_data is not None and is_fresh:
                logger.debug(f"Messages cache HIT for chat {chat_id}")
                return {
                    "success": True,
                    "data": cached_data,
                    "from_cache": True,
                    "has_new_messages": False
                }

        # Cache miss or expired - make API call
        logger.info(f"Messages cache MISS for chat {chat_id} - fetching from API")
        url = f"{self.base_url}/chats/{chat_id}/messages"
        params = {
            "account_id": self.account_id,
            "limit": limit
        }

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    # Extract messages list for hash comparison
                    messages_list = data.get("items", []) if isinstance(data, dict) else data
                    # Store in cache and check for new messages
                    has_new_messages = cache.set_messages(chat_id, data, messages_list)
                    return {
                        "success": True,
                        "data": data,
                        "from_cache": False,
                        "has_new_messages": has_new_messages
                    }
                else:
                    logger.error(f"Failed to get messages: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_message(
        self,
        chat_id: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Send a message to a chat.

        Args:
            chat_id: Chat ID from Unipile
            text: Message text

        Returns:
            Response from Unipile API
        """
        url = f"{self.base_url}/chats/{chat_id}/messages"

        payload = {
            "account_id": self.account_id,
            "text": text
        }

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code in (200, 201):
                    logger.info(f"Message sent successfully to chat {chat_id}")
                    return {
                        "success": True,
                        "data": response.json() if response.text else {},
                        "status_code": response.status_code
                    }
                else:
                    logger.error(f"Failed to send message: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def check_connection_status(self) -> Dict[str, Any]:
        """
        Check if the Unipile account is connected and healthy.

        Returns:
            Connection status
        """
        url = f"{self.base_url}/accounts/{self.account_id}"

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "connected": True,
                        "data": response.json()
                    }
                else:
                    return {
                        "success": False,
                        "connected": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Error checking connection: {e}")
            return {
                "success": False,
                "connected": False,
                "error": str(e)
            }
