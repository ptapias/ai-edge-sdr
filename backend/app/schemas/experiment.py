"""
Pydantic schemas for outreach experiments (AutoOutreach).
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    experiment_name: str = Field(..., min_length=1, max_length=255)
    hypothesis: Optional[str] = None
    prompt_template: Optional[str] = None  # If None, uses current default
    batch_size: int = Field(25, ge=10, le=50)
    is_baseline: bool = False


class ExperimentUpdate(BaseModel):
    experiment_name: Optional[str] = Field(None, min_length=1, max_length=255)
    hypothesis: Optional[str] = None
    batch_size: Optional[int] = Field(None, ge=10, le=50)


class ExperimentLeadResponse(BaseModel):
    id: str
    lead_id: str
    message_sent: Optional[str] = None
    sent_at: Optional[datetime] = None
    accepted: Optional[bool] = None
    accepted_at: Optional[datetime] = None
    responded: Optional[bool] = None
    responded_at: Optional[datetime] = None
    # Denormalized lead info
    lead_name: Optional[str] = None
    lead_company: Optional[str] = None
    lead_job_title: Optional[str] = None

    class Config:
        from_attributes = True


class ExperimentResponse(BaseModel):
    id: str
    experiment_number: int
    experiment_name: str
    hypothesis: Optional[str] = None
    change_description: Optional[str] = None
    prompt_template: str
    status: str
    batch_size: int
    connections_sent: int
    connections_accepted: int
    responses_received: int
    acceptance_rate: Optional[float] = None
    response_rate: Optional[float] = None
    baseline_acceptance_rate: Optional[float] = None
    baseline_response_rate: Optional[float] = None
    improvement_acceptance: Optional[float] = None
    improvement_response: Optional[float] = None
    decision: str
    started_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperimentDetailResponse(ExperimentResponse):
    leads: List[ExperimentLeadResponse] = []


class ExperimentEvaluateResponse(BaseModel):
    experiment_id: str
    connections_sent: int
    connections_accepted: int
    responses_received: int
    acceptance_rate: float
    response_rate: float
    baseline_acceptance_rate: Optional[float] = None
    decision: str
    improvement_acceptance: Optional[float] = None
    improvement_response: Optional[float] = None


class ExperimentProposeResponse(BaseModel):
    proposed_name: str
    hypothesis: str
    change_description: str
    prompt_template: str
    analysis: str  # Claude's analysis of what to change and why


class ExperimentDashboardResponse(BaseModel):
    total_experiments: int
    kept_count: int
    discarded_count: int
    running_count: int
    current_baseline_rate: Optional[float] = None
    best_ever_rate: Optional[float] = None
    total_improvement: Optional[float] = None  # pp from first baseline
    experiments: List[ExperimentResponse] = []
