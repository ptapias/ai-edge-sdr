"""
Authentication router for user registration, login, and token management.
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..services.auth_service import get_auth_service
from ..services.unipile_service import UnipileService
from ..models.user import User, LinkedInAccount
from ..schemas.auth import (
    UserRegister,
    UserLogin,
    TokenRefresh,
    Token,
    UserResponse,
    UserUpdate,
    LinkedInAccountResponse,
    LinkedInConnectRequest,
    LinkedInCheckpointRequest,
    LinkedInConnectResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    Returns access and refresh tokens upon successful registration.
    """
    auth_service = get_auth_service()

    # Check if email already exists
    existing_user = auth_service.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = auth_service.create_user(
        db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
    )

    # Generate tokens
    access_token, refresh_token = auth_service.create_tokens(user.id, user.email)

    logger.info(f"New user registered: {user.email}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/login", response_model=Token)
def login(
    user_data: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.

    Returns access and refresh tokens. Refresh token is also set as HTTP-only cookie.
    """
    auth_service = get_auth_service()

    # Authenticate user
    user = auth_service.authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Generate tokens
    access_token, refresh_token = auth_service.create_tokens(user.id, user.email)

    # Set refresh token as HTTP-only cookie for additional security
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )

    logger.info(f"User logged in: {user.email}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=Token)
def refresh_token(
    token_data: Optional[TokenRefresh] = None,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Accepts refresh token from request body or HTTP-only cookie.
    """
    auth_service = get_auth_service()

    # Get refresh token from body or cookie
    token = token_data.refresh_token if token_data else refresh_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    # Verify refresh token
    payload = auth_service.verify_refresh_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user
    user_id = payload.get("sub")
    user = auth_service.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Generate new tokens
    new_access_token, new_refresh_token = auth_service.create_tokens(user.id, user.email)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )


@router.post("/logout")
def logout(response: Response):
    """
    Logout user by clearing refresh token cookie.

    Note: This only clears the cookie. The access token remains valid
    until it expires. For immediate invalidation, implement token blacklisting.
    """
    response.delete_cookie(key="refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current authenticated user's information."""
    # Check if user has LinkedIn connected
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        has_linkedin_connected=linkedin_account.is_connected if linkedin_account else False
    )


@router.patch("/me", response_model=UserResponse)
def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name

    db.commit()
    db.refresh(current_user)

    # Check LinkedIn status
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        has_linkedin_connected=linkedin_account.is_connected if linkedin_account else False
    )


# LinkedIn Account endpoints
@router.get("/linkedin", response_model=Optional[LinkedInAccountResponse])
def get_linkedin_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's LinkedIn account connection status."""
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    if not linkedin_account:
        return None

    return LinkedInAccountResponse(
        id=linkedin_account.id,
        account_name=linkedin_account.account_name,
        linkedin_profile_url=linkedin_account.linkedin_profile_url,
        linkedin_email=linkedin_account.linkedin_email,
        is_connected=linkedin_account.is_connected,
        connection_status=linkedin_account.connection_status,
        connected_at=linkedin_account.connected_at,
        last_sync_at=linkedin_account.last_sync_at
    )


@router.post("/linkedin/connect", response_model=LinkedInConnectResponse)
async def connect_linkedin(
    connect_data: LinkedInConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Connect LinkedIn account using email and password.

    Uses Unipile API to authenticate. May require 2FA/OTP verification.
    """
    # Initialize Unipile service (uses shared API key from environment)
    unipile = UnipileService()

    # Attempt to connect LinkedIn via Unipile
    result = await unipile.connect_linkedin_account(
        username=connect_data.username,
        password=connect_data.password
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to connect LinkedIn account")
        )

    # Get or create LinkedIn account record
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    if not linkedin_account:
        linkedin_account = LinkedInAccount(user_id=current_user.id)
        db.add(linkedin_account)

    # Update with connection info
    linkedin_account.linkedin_email = connect_data.username
    linkedin_account.unipile_account_id = result.get("account_id")

    if result.get("requires_checkpoint"):
        # Checkpoint required (2FA/OTP)
        linkedin_account.is_connected = False
        linkedin_account.connection_status = "CHECKPOINT"
        linkedin_account.pending_checkpoint_type = result.get("checkpoint_type")
        db.commit()
        db.refresh(linkedin_account)

        logger.info(f"LinkedIn connection requires checkpoint for user: {current_user.email}")

        return LinkedInConnectResponse(
            success=True,
            connected=False,
            requires_checkpoint=True,
            checkpoint_type=result.get("checkpoint_type"),
            message=f"Verification required. Please enter the code sent to your {result.get('checkpoint_type', 'device')}.",
            account=LinkedInAccountResponse(
                id=linkedin_account.id,
                linkedin_email=linkedin_account.linkedin_email,
                is_connected=False,
                connection_status="CHECKPOINT",
                connected_at=None,
                last_sync_at=None
            )
        )
    else:
        # Successfully connected
        linkedin_account.is_connected = True
        linkedin_account.connection_status = "OK"
        linkedin_account.pending_checkpoint_type = None
        linkedin_account.connected_at = datetime.utcnow()

        # Try to get account info for display name
        account_info = await unipile.get_account_info(linkedin_account.unipile_account_id)
        if account_info.get("success"):
            linkedin_account.account_name = account_info.get("name")

        db.commit()
        db.refresh(linkedin_account)

        logger.info(f"LinkedIn connected successfully for user: {current_user.email}")

        return LinkedInConnectResponse(
            success=True,
            connected=True,
            requires_checkpoint=False,
            message="LinkedIn account connected successfully!",
            account=LinkedInAccountResponse(
                id=linkedin_account.id,
                account_name=linkedin_account.account_name,
                linkedin_email=linkedin_account.linkedin_email,
                is_connected=True,
                connection_status="OK",
                connected_at=linkedin_account.connected_at,
                last_sync_at=None
            )
        )


@router.post("/linkedin/checkpoint", response_model=LinkedInConnectResponse)
async def solve_linkedin_checkpoint(
    checkpoint_data: LinkedInCheckpointRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Solve LinkedIn 2FA/OTP checkpoint.

    Must be called within 5 minutes of the initial connection attempt.
    """
    # Get LinkedIn account
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    if not linkedin_account or not linkedin_account.unipile_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending LinkedIn connection found"
        )

    if linkedin_account.connection_status != "CHECKPOINT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No checkpoint pending for this account"
        )

    # Solve checkpoint via Unipile
    unipile = UnipileService()
    result = await unipile.solve_checkpoint(
        account_id=linkedin_account.unipile_account_id,
        code=checkpoint_data.code
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to verify code")
        )

    if result.get("requires_checkpoint"):
        # Another checkpoint required
        linkedin_account.pending_checkpoint_type = result.get("checkpoint_type")
        db.commit()

        return LinkedInConnectResponse(
            success=True,
            connected=False,
            requires_checkpoint=True,
            checkpoint_type=result.get("checkpoint_type"),
            message=f"Additional verification required: {result.get('checkpoint_type')}"
        )
    else:
        # Successfully connected
        linkedin_account.is_connected = True
        linkedin_account.connection_status = "OK"
        linkedin_account.pending_checkpoint_type = None
        linkedin_account.connected_at = datetime.utcnow()

        # Try to get account info for display name
        account_info = await unipile.get_account_info(linkedin_account.unipile_account_id)
        if account_info.get("success"):
            linkedin_account.account_name = account_info.get("name")

        db.commit()
        db.refresh(linkedin_account)

        logger.info(f"LinkedIn checkpoint solved, connected for user: {current_user.email}")

        return LinkedInConnectResponse(
            success=True,
            connected=True,
            requires_checkpoint=False,
            message="LinkedIn account connected successfully!",
            account=LinkedInAccountResponse(
                id=linkedin_account.id,
                account_name=linkedin_account.account_name,
                linkedin_email=linkedin_account.linkedin_email,
                is_connected=True,
                connection_status="OK",
                connected_at=linkedin_account.connected_at,
                last_sync_at=None
            )
        )


@router.delete("/linkedin/disconnect")
async def disconnect_linkedin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect LinkedIn account."""
    linkedin_account = db.query(LinkedInAccount).filter(
        LinkedInAccount.user_id == current_user.id
    ).first()

    if not linkedin_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LinkedIn account connected"
        )

    # Delete account from Unipile if it exists
    if linkedin_account.unipile_account_id:
        unipile = UnipileService()
        await unipile.delete_account(linkedin_account.unipile_account_id)

    # Clear the record
    linkedin_account.unipile_account_id = None
    linkedin_account.linkedin_email = None
    linkedin_account.account_name = None
    linkedin_account.linkedin_profile_url = None
    linkedin_account.is_connected = False
    linkedin_account.connection_status = None
    linkedin_account.pending_checkpoint_type = None
    linkedin_account.connected_at = None

    db.commit()

    logger.info(f"LinkedIn disconnected for user: {current_user.email}")

    return {"message": "LinkedIn account disconnected"}
