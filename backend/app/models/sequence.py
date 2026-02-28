"""
Sequence models for automated LinkedIn outreach workflows.
"""
import uuid
import json
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base


class SequenceStatus(str, Enum):
    """Status of a sequence workflow."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class SequenceMode(str, Enum):
    """Whether a sequence uses classic timer-based steps or smart pipeline."""
    CLASSIC = "classic"
    SMART_PIPELINE = "smart_pipeline"


class StepType(str, Enum):
    """Type of sequence step."""
    CONNECTION_REQUEST = "connection_request"
    FOLLOW_UP_MESSAGE = "follow_up_message"


class PipelinePhase(str, Enum):
    """5-phase smart outreach pipeline phases."""
    APERTURA = "apertura"              # Phase 1: Opening question, no pitch
    CALIFICACION = "calificacion"      # Phase 2: Qualification questions
    VALOR = "valor"                    # Phase 3: Value proposition / fit check
    NURTURE = "nurture"                # Phase 4: Long-term light touch
    REACTIVACION = "reactivacion"      # Phase 5: Reactivation after silence


class EnrollmentStatus(str, Enum):
    """Status of a lead's enrollment in a sequence."""
    ACTIVE = "active"
    COMPLETED = "completed"
    REPLIED = "replied"
    PAUSED = "paused"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"
    PARKED = "parked"  # Lead parked after exhausting nurture/reactivation


class Sequence(Base):
    """Sequence workflow template for automated outreach."""

    __tablename__ = "sequences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default=SequenceStatus.DRAFT.value)

    # Business profile for AI message generation context
    business_id = Column(String(36), ForeignKey("business_profiles.id"), nullable=True)
    business_profile = relationship("BusinessProfile")

    # Strategy for message generation
    message_strategy = Column(String(20), default="hybrid")  # hybrid/direct/gradual

    # Pipeline mode: "classic" = timer-based steps, "smart_pipeline" = response-based 5-phase
    sequence_mode = Column(String(20), default=SequenceMode.CLASSIC.value)

    # Stats (denormalized for performance)
    total_enrolled = Column(Integer, default=0)
    active_enrolled = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    replied_count = Column(Integer, default=0)

    # Multi-tenancy
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", back_populates="sequences")

    # Relationships
    steps = relationship(
        "SequenceStep",
        back_populates="sequence",
        order_by="SequenceStep.step_order",
        cascade="all, delete-orphan"
    )
    enrollments = relationship("SequenceEnrollment", back_populates="sequence")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Sequence {self.name} ({self.status})>"


class SequenceStep(Base):
    """Individual step within a sequence."""

    __tablename__ = "sequence_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Parent sequence
    sequence_id = Column(String(36), ForeignKey("sequences.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = relationship("Sequence", back_populates="steps")

    # Step config
    step_order = Column(Integer, nullable=False)  # 1, 2, 3...
    step_type = Column(String(30), nullable=False)  # connection_request or follow_up_message

    # Timing: delay in days before this step executes
    # Step 1 (connection_request): delay_days = 0 (send immediately)
    # Step 2+: delay_days = N (wait N days after previous step or connection acceptance)
    delay_days = Column(Integer, default=0)

    # AI prompt context: optional user guidance for message generation
    prompt_context = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SequenceStep {self.step_order}: {self.step_type}>"


class SequenceEnrollment(Base):
    """Tracks a lead's progress through a sequence."""

    __tablename__ = "sequence_enrollments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # References
    sequence_id = Column(String(36), ForeignKey("sequences.id"), nullable=False, index=True)
    sequence = relationship("Sequence", back_populates="enrollments")

    lead_id = Column(String(36), ForeignKey("leads.id"), nullable=False, index=True)
    lead = relationship("Lead", back_populates="sequence_enrollments")

    # Progress tracking
    status = Column(String(20), default=EnrollmentStatus.ACTIVE.value, index=True)
    current_step_order = Column(Integer, default=1)

    # Step execution tracking
    last_step_completed_at = Column(DateTime, nullable=True)
    next_step_due_at = Column(DateTime, nullable=True)

    # Message tracking per step (JSON: {"1": "message text", "2": "message text"})
    messages_sent = Column(Text, nullable=True)

    # Outcome tracking
    replied_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_reason = Column(Text, nullable=True)

    # Smart Pipeline phase tracking (nullable for backward compat with classic mode)
    current_phase = Column(String(20), nullable=True)       # PipelinePhase value
    phase_entered_at = Column(DateTime, nullable=True)       # When current phase started
    last_response_at = Column(DateTime, nullable=True)       # When lead last responded
    last_response_text = Column(Text, nullable=True)         # Last inbound message text
    phase_analysis = Column(Text, nullable=True)             # JSON: Claude's analysis result
    messages_in_phase = Column(Integer, default=0)           # Messages sent in current phase
    nurture_count = Column(Integer, default=0)               # Total nurture messages sent
    reactivation_count = Column(Integer, default=0)          # Times reactivated
    total_messages_sent = Column(Integer, default=0)         # Total outbound messages

    # Multi-tenancy
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Timestamps
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # A lead can only be enrolled once per sequence
    __table_args__ = (
        UniqueConstraint('lead_id', 'sequence_id', name='uq_enrollment_lead_sequence'),
    )

    def get_messages(self) -> dict:
        """Get messages dict from JSON."""
        if self.messages_sent:
            try:
                return json.loads(self.messages_sent)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def store_message(self, step_order: int, message: str):
        """Store a sent message for a step."""
        messages = self.get_messages()
        messages[str(step_order)] = message
        self.messages_sent = json.dumps(messages)

    def get_phase_analysis(self) -> dict:
        """Get phase analysis dict from JSON."""
        if self.phase_analysis:
            try:
                return json.loads(self.phase_analysis)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def store_phase_analysis(self, analysis: dict):
        """Store Claude's phase analysis as JSON."""
        self.phase_analysis = json.dumps(analysis)

    def __repr__(self):
        if self.current_phase:
            return f"<SequenceEnrollment lead={self.lead_id} phase={self.current_phase} ({self.status})>"
        return f"<SequenceEnrollment lead={self.lead_id} step={self.current_step_order} ({self.status})>"
