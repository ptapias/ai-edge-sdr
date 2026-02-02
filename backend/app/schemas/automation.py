"""
Automation settings schemas for API validation.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AutomationSettingsBase(BaseModel):
    """Base schema for automation settings."""
    enabled: bool = False
    work_start_hour: int = Field(9, ge=0, le=23)
    work_start_minute: int = Field(0, ge=0, le=59)
    work_end_hour: int = Field(18, ge=0, le=23)
    work_end_minute: int = Field(0, ge=0, le=59)
    working_days: int = Field(31, ge=0, le=127)  # Bitmask for days
    daily_limit: int = Field(40, ge=1, le=100)
    min_delay_seconds: int = Field(60, ge=30, le=3600)
    max_delay_seconds: int = Field(300, ge=60, le=7200)
    min_lead_score: int = Field(0, ge=0, le=100)
    target_statuses: str = "new,pending"
    target_campaign_id: Optional[str] = None  # Filter by campaign


class AutomationSettingsUpdate(BaseModel):
    """Schema for updating automation settings."""
    enabled: Optional[bool] = None
    work_start_hour: Optional[int] = Field(None, ge=0, le=23)
    work_start_minute: Optional[int] = Field(None, ge=0, le=59)
    work_end_hour: Optional[int] = Field(None, ge=0, le=23)
    work_end_minute: Optional[int] = Field(None, ge=0, le=59)
    working_days: Optional[int] = Field(None, ge=0, le=127)
    daily_limit: Optional[int] = Field(None, ge=1, le=100)
    min_delay_seconds: Optional[int] = Field(None, ge=30, le=3600)
    max_delay_seconds: Optional[int] = Field(None, ge=60, le=7200)
    min_lead_score: Optional[int] = Field(None, ge=0, le=100)
    target_statuses: Optional[str] = None
    target_campaign_id: Optional[str] = None  # Filter by campaign (null = all campaigns)


class AutomationSettingsResponse(AutomationSettingsBase):
    """Schema for automation settings response."""
    id: str
    invitations_sent_today: int
    last_invitation_at: Optional[datetime]
    last_reset_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationStatusResponse(BaseModel):
    """Schema for automation status check."""
    enabled: bool
    is_working_hour: bool
    can_send: bool
    invitations_sent_today: int
    daily_limit: int
    remaining_today: int
    next_invitation_in_seconds: Optional[int]


class InvitationLogResponse(BaseModel):
    """Schema for invitation log entry."""
    id: str
    lead_id: str
    lead_name: Optional[str]
    lead_company: Optional[str]
    lead_job_title: Optional[str]
    lead_linkedin_url: Optional[str]
    message_preview: Optional[str]
    campaign_id: Optional[str]
    campaign_name: Optional[str]
    success: bool
    error_message: Optional[str]
    sent_at: datetime
    mode: str

    class Config:
        from_attributes = True


class InvitationStatsResponse(BaseModel):
    """Schema for invitation statistics."""
    today: int
    this_week: int
    this_month: int
    total: int
    success_rate: float
    by_day: List[dict]  # [{date: str, count: int, successful: int}]
