"""
Pydantic schemas for authentication endpoints.
"""
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# Request schemas
class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class TokenRefresh(BaseModel):
    """Schema for token refresh."""
    refresh_token: str


class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8)


# Response schemas
class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded token data."""
    user_id: str
    email: str
    exp: datetime


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    has_linkedin_connected: bool = False

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None


# LinkedIn Account schemas
class LinkedInAccountResponse(BaseModel):
    """LinkedIn account response schema."""
    id: str
    account_name: Optional[str] = None
    linkedin_profile_url: Optional[str] = None
    linkedin_email: Optional[str] = None
    is_connected: bool
    connection_status: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LinkedInConnectRequest(BaseModel):
    """Request to connect LinkedIn with email/password."""
    username: EmailStr = Field(..., description="LinkedIn email address")
    password: str = Field(..., description="LinkedIn password")


class LinkedInCheckpointRequest(BaseModel):
    """Request to solve LinkedIn 2FA/OTP checkpoint."""
    code: str = Field(..., description="Verification code from 2FA/OTP")


class LinkedInConnectResponse(BaseModel):
    """Response from LinkedIn connection attempt."""
    success: bool
    connected: bool = False
    requires_checkpoint: bool = False
    checkpoint_type: Optional[str] = None
    message: Optional[str] = None
    account: Optional[LinkedInAccountResponse] = None
