"""
Cache service for rate-limiting API calls and storing data.

CRITICAL: This is essential for LinkedIn safety - too many API calls = ban risk.
"""
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached item with expiration."""
    data: Any
    expires_at: datetime
    last_message_hash: Optional[str] = None  # To detect new messages


class UnipileCache:
    """
    In-memory cache for Unipile API responses.

    IMPORTANT: Implements rate limiting with random jitter to simulate human behavior.
    - Chats are cached for 30-60 minutes (random)
    - User profiles are cached for 24 hours (they rarely change)
    - Messages are cached for 5-10 minutes (random)
    """

    # Cache TTL settings (in minutes)
    CHATS_TTL_MIN = 30
    CHATS_TTL_MAX = 60
    PROFILES_TTL_MIN = 1440  # 24 hours
    PROFILES_TTL_MAX = 1800  # 30 hours
    MESSAGES_TTL_MIN = 5
    MESSAGES_TTL_MAX = 10

    def __init__(self):
        self._chats_cache: Optional[CacheEntry] = None
        self._profiles_cache: Dict[str, CacheEntry] = {}
        self._messages_cache: Dict[str, CacheEntry] = {}
        self._last_api_call: Optional[datetime] = None

    def _get_random_ttl(self, min_minutes: int, max_minutes: int) -> timedelta:
        """Get a random TTL to simulate human behavior."""
        minutes = random.randint(min_minutes, max_minutes)
        # Add random seconds for extra jitter
        seconds = random.randint(0, 59)
        return timedelta(minutes=minutes, seconds=seconds)

    def _is_expired(self, entry: Optional[CacheEntry]) -> bool:
        """Check if a cache entry is expired."""
        if entry is None:
            return True
        return datetime.utcnow() > entry.expires_at

    def _hash_messages(self, messages: list) -> str:
        """Create a simple hash of messages to detect changes."""
        if not messages:
            return ""
        # Use last message ID and timestamp as hash
        last_msg = messages[0] if messages else {}
        return f"{last_msg.get('id', '')}-{last_msg.get('timestamp', '')}"

    # ===== CHATS CACHE =====

    def get_chats(self) -> Tuple[Optional[Any], bool]:
        """
        Get cached chats.

        Returns:
            Tuple of (cached_data, is_fresh)
            - cached_data: The cached chats or None if not cached
            - is_fresh: True if cache is still valid, False if expired
        """
        if self._chats_cache is None:
            return None, False

        is_fresh = not self._is_expired(self._chats_cache)
        return self._chats_cache.data, is_fresh

    def set_chats(self, data: Any) -> None:
        """Cache chats with random TTL (30-60 minutes)."""
        ttl = self._get_random_ttl(self.CHATS_TTL_MIN, self.CHATS_TTL_MAX)
        self._chats_cache = CacheEntry(
            data=data,
            expires_at=datetime.utcnow() + ttl
        )
        self._last_api_call = datetime.utcnow()
        logger.info(f"Chats cached for {ttl.total_seconds() / 60:.1f} minutes")

    def get_chats_cache_info(self) -> Dict[str, Any]:
        """Get info about the chats cache state."""
        if self._chats_cache is None:
            return {
                "cached": False,
                "expires_in_seconds": 0,
                "last_api_call": None
            }

        now = datetime.utcnow()
        expires_in = (self._chats_cache.expires_at - now).total_seconds()

        return {
            "cached": True,
            "is_fresh": expires_in > 0,
            "expires_in_seconds": max(0, int(expires_in)),
            "last_api_call": self._last_api_call.isoformat() if self._last_api_call else None
        }

    def invalidate_chats(self) -> None:
        """Force invalidate chats cache (use sparingly)."""
        self._chats_cache = None
        logger.info("Chats cache invalidated")

    # ===== PROFILES CACHE =====

    def get_profile(self, provider_id: str) -> Tuple[Optional[Any], bool]:
        """Get cached user profile."""
        entry = self._profiles_cache.get(provider_id)
        if entry is None:
            return None, False

        is_fresh = not self._is_expired(entry)
        return entry.data, is_fresh

    def set_profile(self, provider_id: str, data: Any) -> None:
        """Cache user profile with random TTL (24-30 hours)."""
        ttl = self._get_random_ttl(self.PROFILES_TTL_MIN, self.PROFILES_TTL_MAX)
        self._profiles_cache[provider_id] = CacheEntry(
            data=data,
            expires_at=datetime.utcnow() + ttl
        )

    # ===== MESSAGES CACHE =====

    def get_messages(self, chat_id: str) -> Tuple[Optional[Any], bool, bool]:
        """
        Get cached messages for a chat.

        Returns:
            Tuple of (cached_data, is_fresh, has_new_messages)
        """
        entry = self._messages_cache.get(chat_id)
        if entry is None:
            return None, False, False

        is_fresh = not self._is_expired(entry)
        return entry.data, is_fresh, False  # has_new_messages determined after fetch

    def set_messages(self, chat_id: str, data: Any, messages_list: list) -> bool:
        """
        Cache messages for a chat.

        Returns:
            True if there are new messages since last cache
        """
        new_hash = self._hash_messages(messages_list)
        old_entry = self._messages_cache.get(chat_id)

        has_new_messages = False
        if old_entry and old_entry.last_message_hash:
            has_new_messages = old_entry.last_message_hash != new_hash

        ttl = self._get_random_ttl(self.MESSAGES_TTL_MIN, self.MESSAGES_TTL_MAX)
        self._messages_cache[chat_id] = CacheEntry(
            data=data,
            expires_at=datetime.utcnow() + ttl,
            last_message_hash=new_hash
        )

        if has_new_messages:
            logger.info(f"New messages detected in chat {chat_id}")

        return has_new_messages

    # ===== RATE LIMITING =====

    def can_make_api_call(self, min_interval_seconds: int = 60) -> bool:
        """
        Check if enough time has passed since last API call.

        Args:
            min_interval_seconds: Minimum seconds between API calls

        Returns:
            True if it's safe to make an API call
        """
        if self._last_api_call is None:
            return True

        elapsed = (datetime.utcnow() - self._last_api_call).total_seconds()
        return elapsed >= min_interval_seconds

    def record_api_call(self) -> None:
        """Record that an API call was made."""
        self._last_api_call = datetime.utcnow()


# Singleton instance
_cache_instance: Optional[UnipileCache] = None


def get_unipile_cache() -> UnipileCache:
    """Get the singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = UnipileCache()
    return _cache_instance
