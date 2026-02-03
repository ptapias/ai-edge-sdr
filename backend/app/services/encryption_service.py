"""
Encryption service for securing sensitive data like API keys.
Uses Fernet symmetric encryption (AES-128-CBC).
"""
import logging
from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize encryption service with key from settings."""
        encryption_key = settings.encryption_key
        if not encryption_key:
            logger.warning("ENCRYPTION_KEY not set - using a generated key (NOT SECURE FOR PRODUCTION)")
            # Generate a key for development (NOT for production)
            encryption_key = Fernet.generate_key().decode()

        # Ensure the key is bytes
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()

        try:
            self.fernet = Fernet(encryption_key)
        except Exception as e:
            logger.error(f"Invalid encryption key: {e}")
            # Generate a fallback key for development
            self.fernet = Fernet(Fernet.generate_key())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""

        encrypted = self.fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data)
        """
        if not ciphertext:
            return ""

        try:
            decrypted = self.fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise


# Singleton instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get the singleton encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
