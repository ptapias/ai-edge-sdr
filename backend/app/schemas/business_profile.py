"""
BusinessProfile schemas for API validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BusinessProfileBase(BaseModel):
    """Base schema for BusinessProfile."""
    name: str
    description: Optional[str] = None
    ideal_customer: Optional[str] = None
    target_industries: Optional[str] = None
    target_company_sizes: Optional[str] = None
    target_job_titles: Optional[str] = None
    target_locations: Optional[str] = None
    value_proposition: Optional[str] = None
    key_benefits: Optional[str] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    sender_company: Optional[str] = None
    sender_context: Optional[str] = None


class BusinessProfileCreate(BusinessProfileBase):
    """Schema for creating a new BusinessProfile."""
    is_default: bool = False


class BusinessProfileUpdate(BaseModel):
    """Schema for updating a BusinessProfile."""
    name: Optional[str] = None
    description: Optional[str] = None
    ideal_customer: Optional[str] = None
    target_industries: Optional[str] = None
    target_company_sizes: Optional[str] = None
    target_job_titles: Optional[str] = None
    target_locations: Optional[str] = None
    value_proposition: Optional[str] = None
    key_benefits: Optional[str] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    sender_company: Optional[str] = None
    sender_context: Optional[str] = None
    is_default: Optional[bool] = None


class BusinessProfileResponse(BusinessProfileBase):
    """Schema for BusinessProfile API response."""
    id: str
    is_default: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
