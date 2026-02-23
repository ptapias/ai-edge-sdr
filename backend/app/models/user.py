"""
User and LinkedInAccount models for multi-user authentication.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class User(Base):
    """User model for authentication and multi-tenancy."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Auth info
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Profile info
    full_name = Column(String(255), nullable=True)

    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    linkedin_account = relationship("LinkedInAccount", back_populates="user", uselist=False)
    leads = relationship("Lead", back_populates="user")
    campaigns = relationship("Campaign", back_populates="user")
    business_profiles = relationship("BusinessProfile", back_populates="user")
    automation_settings = relationship("AutomationSettings", back_populates="user", uselist=False)
    invitation_logs = relationship("InvitationLog", back_populates="user")
    sequences = relationship("Sequence", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"


class LinkedInAccount(Base):
    """LinkedIn account credentials linked to a user."""

    __tablename__ = "linkedin_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Owner
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    user = relationship("User", back_populates="linkedin_account")

    # Unipile credentials
    unipile_account_id = Column(String(255), nullable=True)  # Account ID from Unipile after connection
    unipile_api_key_encrypted = Column(Text, nullable=True)  # Not needed - using shared Unipile API key

    # LinkedIn info
    linkedin_email = Column(String(255), nullable=True)  # LinkedIn email used to connect
    account_name = Column(String(255), nullable=True)  # LinkedIn display name
    linkedin_profile_url = Column(String(500), nullable=True)

    # Connection status
    is_connected = Column(Boolean, default=False)
    connection_status = Column(String(50), nullable=True)  # OK, CREDENTIALS, CHECKPOINT, etc.
    pending_checkpoint_type = Column(String(50), nullable=True)  # 2FA, OTP, IN_APP_VALIDATION, etc.
    connected_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LinkedInAccount {self.account_name or self.id}>"
