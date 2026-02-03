"""
BusinessProfile model - represents the user's business context for AI scoring.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class BusinessProfile(Base):
    """Perfil de negocio para contextualizar la calificación de leads."""

    __tablename__ = "business_profiles"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Business info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)  # What the business does

    # Target customer profile
    ideal_customer = Column(Text, nullable=True)  # ICP description
    target_industries = Column(Text, nullable=True)  # Comma-separated
    target_company_sizes = Column(String(100), nullable=True)  # e.g., "50-500"
    target_job_titles = Column(Text, nullable=True)  # Comma-separated
    target_locations = Column(Text, nullable=True)  # Comma-separated

    # Value proposition
    value_proposition = Column(Text, nullable=True)
    key_benefits = Column(Text, nullable=True)  # Comma-separated

    # Personalization context for AI messages
    sender_name = Column(String(100), nullable=True)
    sender_role = Column(String(255), nullable=True)
    sender_company = Column(String(255), nullable=True)
    sender_context = Column(Text, nullable=True)  # Additional context for AI

    # Defaults
    is_default = Column(Boolean, default=False)

    # Campaigns relationship
    campaigns = relationship("Campaign", back_populates="business_profile")

    # User relationship (multi-tenancy)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="business_profiles")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BusinessProfile {self.name}>"
