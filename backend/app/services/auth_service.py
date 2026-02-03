"""
Authentication service for JWT token management and password hashing.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.user import User

logger = logging.getLogger(__name__)

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication operations."""

    def __init__(self):
        """Initialize auth service with settings."""
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days

    # Password operations
    def hash_password(self, password: str) -> str:
        """Hash a plain password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    # Token operations
    def create_access_token(self, user_id: str, email: str) -> str:
        """Create a new access token."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str, email: str) -> str:
        """Create a new refresh token."""
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        to_encode = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_tokens(self, user_id: str, email: str) -> Tuple[str, str]:
        """Create both access and refresh tokens."""
        access_token = self.create_access_token(user_id, email)
        refresh_token = self.create_refresh_token(user_id, email)
        return access_token, refresh_token

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate a JWT token.

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"Token decode error: {e}")
            return None

    def verify_access_token(self, token: str) -> Optional[dict]:
        """Verify an access token and return payload if valid."""
        payload = self.decode_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None

    def verify_refresh_token(self, token: str) -> Optional[dict]:
        """Verify a refresh token and return payload if valid."""
        payload = self.decode_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None

    # User operations
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.

        Returns:
            User object if authentication successful, None otherwise
        """
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_user(self, db: Session, email: str, password: str, full_name: Optional[str] = None) -> User:
        """
        Create a new user.

        Args:
            db: Database session
            email: User's email
            password: Plain password (will be hashed)
            full_name: Optional full name

        Returns:
            Created User object
        """
        hashed_password = self.hash_password(password)
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get a user by email."""
        return db.query(User).filter(User.email == email).first()


# Singleton instance
_auth_service = None


def get_auth_service() -> AuthService:
    """Get the singleton auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
