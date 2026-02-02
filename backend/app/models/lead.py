"""
Lead model - represents a potential contact/lead.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Lead(Base):
    """Modelo de Lead - contacto potencial."""

    __tablename__ = "leads"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Personal info
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)

    # Contact info
    email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False)
    email_status = Column(String(20), nullable=True)  # valid/invalid/risky
    personal_email = Column(String(255), nullable=True)
    mobile_number = Column(String(50), nullable=True)

    # Professional info
    job_title = Column(String(255), nullable=True)
    headline = Column(Text, nullable=True)
    seniority_level = Column(String(50), nullable=True)
    functional_level = Column(String(50), nullable=True)

    # Company info
    company_name = Column(String(255), nullable=True)
    company_domain = Column(String(255), nullable=True)
    company_website = Column(String(500), nullable=True)
    company_size = Column(Integer, nullable=True)
    company_industry = Column(String(100), nullable=True)
    company_description = Column(Text, nullable=True)
    company_annual_revenue = Column(String(100), nullable=True)
    company_total_funding = Column(String(100), nullable=True)
    company_phone = Column(String(50), nullable=True)
    company_full_address = Column(Text, nullable=True)

    # Location
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    # LinkedIn
    linkedin_url = Column(String(500), nullable=True)
    sales_navigator_id = Column(String(100), nullable=True)

    # Lead scoring (AI)
    score = Column(Integer, nullable=True)  # 1-100
    score_label = Column(String(20), nullable=True)  # hot/warm/cold
    score_reason = Column(Text, nullable=True)  # AI explanation

    # Outreach status
    status = Column(String(50), default="new")  # new/contacted/connected/replied
    linkedin_message = Column(Text, nullable=True)
    email_message = Column(Text, nullable=True)

    # Tracking
    connection_sent_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)

    # Campaign relationship
    campaign_id = Column(String(36), ForeignKey("campaigns.id"), nullable=True)
    campaign = relationship("Campaign", back_populates="leads")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Lead {self.first_name} {self.last_name} - {self.company_name}>"

    @property
    def display_name(self) -> str:
        """Nombre para mostrar."""
        if self.full_name:
            return self.full_name
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"
