"""
Campaign schemas for API validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CampaignBase(BaseModel):
    """Base schema for Campaign."""
    name: str
    description: Optional[str] = None
    search_query: Optional[str] = None


class CampaignCreate(CampaignBase):
    """Schema for creating a new Campaign."""
    business_id: Optional[str] = None


class CampaignUpdate(BaseModel):
    """Schema for updating a Campaign."""
    name: Optional[str] = None
    description: Optional[str] = None


class CampaignResponse(CampaignBase):
    """Schema for Campaign API response."""
    id: str
    search_filters: Optional[str] = None
    total_leads: int = 0
    verified_leads: int = 0
    contacted_leads: int = 0
    business_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
