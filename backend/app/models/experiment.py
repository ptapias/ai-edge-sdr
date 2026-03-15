"""
OutreachExperiment models — AutoOutreach self-improving message system.
Inspired by Karpathy's autoresearch: measure, iterate, improve.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class OutreachExperiment(Base):
    """An A/B experiment on the connection message prompt template."""

    __tablename__ = "outreach_experiments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Experiment identity
    experiment_number = Column(Integer, nullable=False)  # Sequential: 1, 2, 3...
    experiment_name = Column(String(255), nullable=False)  # e.g. "exp-003-shorter-opener"
    hypothesis = Column(Text, nullable=True)  # What we're testing and why
    change_description = Column(Text, nullable=True)  # What changed vs previous

    # The prompt template (the "train.py" equivalent)
    prompt_template = Column(Text, nullable=False)  # Full system prompt used for message generation

    # Status tracking
    status = Column(String(20), nullable=False, default="pending")
    # Values: pending, baseline, running, evaluating, kept, discarded

    # Batch configuration
    batch_size = Column(Integer, default=25)  # Target batch size

    # Results (filled during evaluation)
    connections_sent = Column(Integer, default=0)
    connections_accepted = Column(Integer, default=0)
    responses_received = Column(Integer, default=0)
    acceptance_rate = Column(Float, nullable=True)  # 0-100
    response_rate = Column(Float, nullable=True)  # 0-100

    # Baseline comparison
    baseline_acceptance_rate = Column(Float, nullable=True)
    baseline_response_rate = Column(Float, nullable=True)
    improvement_acceptance = Column(Float, nullable=True)  # percentage points
    improvement_response = Column(Float, nullable=True)

    # Decision
    decision = Column(String(20), default="pending")  # pending, keep, discard

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    evaluated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    experiment_leads = relationship("OutreachExperimentLead", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OutreachExperiment #{self.experiment_number} {self.status}>"


class OutreachExperimentLead(Base):
    """Links a lead to an experiment, tracking its individual outcome."""

    __tablename__ = "outreach_experiment_leads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(36), ForeignKey("outreach_experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)

    # Message sent
    message_sent = Column(Text, nullable=True)

    # Outcome tracking
    sent_at = Column(DateTime, nullable=True)
    accepted = Column(Boolean, nullable=True)  # None = pending
    accepted_at = Column(DateTime, nullable=True)
    responded = Column(Boolean, nullable=True)
    responded_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    experiment = relationship("OutreachExperiment", back_populates="experiment_leads")
    lead = relationship("Lead")

    def __repr__(self):
        return f"<ExperimentLead exp={self.experiment_id[:8]} lead={self.lead_id[:8]}>"
