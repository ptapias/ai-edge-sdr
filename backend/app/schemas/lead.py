"""
Lead schemas for API validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


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
    campaign_id: Optional[str] = None
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
