"""
Lead schemas for API validation.
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, EmailStr, Field


class LeadStatusEnum(str, Enum):
    """CRM status for leads."""
    NEW = "new"
    PENDING = "pending"
    INVITATION_SENT = "invitation_sent"
    CONNECTED = "connected"
    IN_CONVERSATION = "in_conversation"
    MEETING_SCHEDULED = "meeting_scheduled"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class LeadBase(BaseModel):
    """Base schema for Lead."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_number: Optional[str] = None
    job_title: Optional[str] = None
    headline: Optional[str] = None
    seniority_level: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    company_website: Optional[str] = None
    company_size: Optional[int] = None
    company_industry: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    sales_navigator_id: Optional[str] = None


class LeadCreate(LeadBase):
    """Schema for creating a new Lead."""
    campaign_id: Optional[str] = None


class LeadUpdate(BaseModel):
    """Schema for updating a Lead."""
    status: Optional[str] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    score_label: Optional[str] = None
    score_reason: Optional[str] = None
    linkedin_message: Optional[str] = None
    email_message: Optional[str] = None
    email_verified: Optional[bool] = None
    email_status: Optional[str] = None
    notes: Optional[str] = None


class LeadStatusUpdate(BaseModel):
    """Schema for updating lead status."""
    status: LeadStatusEnum
    notes: Optional[str] = None


class LeadStatusInfo(BaseModel):
    """Schema for status information."""
    value: str
    label: str
    color: str
    order: int


class LeadBulkStatusUpdate(BaseModel):
    """Schema for bulk status update."""
    lead_ids: List[str]
    status: LeadStatusEnum


class LeadScoring(BaseModel):
    """Schema for lead scoring result."""
    score: int = Field(..., ge=0, le=100)
    label: str = Field(..., description="hot/warm/cold")
    reason: str = Field(..., description="AI explanation for the score")


class LeadResponse(LeadBase):
    """Schema for Lead API response."""
    id: str
    email_verified: bool = False
    email_status: Optional[str] = None
    score: Optional[int] = None
    score_label: Optional[str] = None
    score_reason: Optional[str] = None
    status: str = "new"
    linkedin_message: Optional[str] = None
    email_message: Optional[str] = None
    notes: Optional[str] = None
    campaign_id: Optional[str] = None
    linkedin_provider_id: Optional[str] = None
    linkedin_chat_id: Optional[str] = None
    connection_sent_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Schema for paginated lead list response."""
    total: int
    page: int
    page_size: int
    leads: list[LeadResponse]
