"""
Campaign model - represents a lead generation campaign.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..database import Base


class Campaign(Base):
    """Modelo de Campaña - agrupa leads de una búsqueda."""

    __tablename__ = "campaigns"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Campaign info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Search configuration
    search_query = Column(Text, nullable=True)  # Natural language query
    search_filters = Column(Text, nullable=True)  # JSON of Apify filters used

    # Stats
    total_leads = Column(Integer, default=0)
    verified_leads = Column(Integer, default=0)
    contacted_leads = Column(Integer, default=0)

    # Business profile relationship
    business_id = Column(String(36), ForeignKey("business_profiles.id"), nullable=True)
    business_profile = relationship("BusinessProfile", back_populates="campaigns")

    # Leads relationship
    leads = relationship("Lead", back_populates="campaign", lazy="dynamic")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Campaign {self.name}>"
