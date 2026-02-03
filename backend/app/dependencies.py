"""
FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .services.auth_service import get_auth_service
from .models.user import User

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for JWT tokens
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.

    Extracts JWT token from Authorization header, validates it,
    and returns the corresponding user.

    Raises:
        HTTPException 401: If token is missing, invalid, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    auth_service = get_auth_service()

    # Verify the access token
    payload = auth_service.verify_access_token(token)
    if payload is None:
        raise credentials_exception

    # Get user from database
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional dependency to get the current user if authenticated.

    Returns None if no valid authentication is provided,
    instead of raising an exception.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    auth_service = get_auth_service()

    # Verify the access token
    payload = auth_service.verify_access_token(token)
    if payload is None:
        return None

    # Get user from database
    user_id = payload.get("sub")
    if user_id is None:
        return None

    user = auth_service.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        return None

    return user


def require_verified_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the user to be verified.

    Can be used for endpoints that need email verification.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    return current_user
