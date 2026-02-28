"""
Pydantic schemas for sequence endpoints.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# --- Step schemas ---

class SequenceStepCreate(BaseModel):
    step_type: str = Field(..., pattern="^(connection_request|follow_up_message)$")
    delay_days: int = Field(0, ge=0, le=90)
    prompt_context: Optional[str] = None


class SequenceStepUpdate(BaseModel):
    step_type: Optional[str] = Field(None, pattern="^(connection_request|follow_up_message)$")
    delay_days: Optional[int] = Field(None, ge=0, le=90)
    prompt_context: Optional[str] = None


class SequenceStepResponse(BaseModel):
    id: str
    step_order: int
    step_type: str
    delay_days: int
    prompt_context: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StepReorderRequest(BaseModel):
    step_ids: List[str]  # Ordered list of step IDs


# --- Sequence schemas ---

class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    business_id: Optional[str] = None
    message_strategy: str = Field("hybrid", pattern="^(hybrid|direct|gradual)$")
    sequence_mode: str = Field("classic", pattern="^(classic|smart_pipeline)$")
    steps: List[SequenceStepCreate] = []


class SequenceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    business_id: Optional[str] = None
    message_strategy: Optional[str] = Field(None, pattern="^(hybrid|direct|gradual)$")


class SequenceStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|paused|archived)$")


class SequenceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    business_id: Optional[str] = None
    message_strategy: str
    sequence_mode: str = "classic"
    total_enrolled: int
    active_enrolled: int
    completed_count: int
    replied_count: int
    steps: List[SequenceStepResponse] = []
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SequenceListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    message_strategy: str
    sequence_mode: str = "classic"
    total_enrolled: int
    active_enrolled: int
    completed_count: int
    replied_count: int
    steps_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Enrollment schemas ---

class EnrollLeadsRequest(BaseModel):
    lead_ids: List[str] = Field(..., min_length=1)


class UnenrollLeadsRequest(BaseModel):
    lead_ids: List[str] = Field(..., min_length=1)


class EnrollmentResponse(BaseModel):
    id: str
    sequence_id: str
    lead_id: str
    status: str
    current_step_order: int
    next_step_due_at: Optional[datetime] = None
    last_step_completed_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_reason: Optional[str] = None
    enrolled_at: datetime
    updated_at: datetime
    # Denormalized lead info
    lead_name: Optional[str] = None
    lead_company: Optional[str] = None
    lead_job_title: Optional[str] = None
    lead_status: Optional[str] = None
    lead_score_label: Optional[str] = None
    # Smart Pipeline fields
    current_phase: Optional[str] = None
    phase_entered_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    messages_in_phase: int = 0
    nurture_count: int = 0
    reactivation_count: int = 0
    total_messages_sent: int = 0

    class Config:
        from_attributes = True


# --- Stats schemas ---

class SequenceStatsResponse(BaseModel):
    sequence_id: str
    sequence_name: str
    sequence_mode: str = "classic"
    total_enrolled: int
    active: int
    completed: int
    replied: int
    failed: int
    paused: int
    withdrawn: int
    parked: int = 0
    reply_rate: float  # percentage
    completion_rate: float  # percentage
    steps_breakdown: List[dict]  # [{step_order, step_type, reached, completed}]
    phase_breakdown: Optional[dict] = None  # Smart pipeline: {phase: count}


class SequenceDashboardResponse(BaseModel):
    total_sequences: int
    active_sequences: int
    total_enrolled: int
    total_active: int
    total_replied: int
    total_completed: int
    overall_reply_rate: float
    sequences: List[SequenceListResponse]
