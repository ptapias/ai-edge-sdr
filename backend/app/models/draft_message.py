"""
DraftMessage model for Smart Pipeline draft/approval system.
When a Smart Pipeline sequence generates a follow-up message,
it saves it as a draft pending user approval before sending.
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..database import Base


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class DraftMessage(Base):
    __tablename__ = "draft_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enrollment_id = Column(String(36), ForeignKey("sequence_enrollments.id"), index=True)
    lead_id = Column(String(36), ForeignKey("leads.id"), index=True)
    sequence_id = Column(String(36), ForeignKey("sequences.id"), index=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)

    # Phase context
    pipeline_phase = Column(String(20), nullable=True)
    step_order = Column(Integer, nullable=True)

    # Message content
    generated_message = Column(Text, nullable=False)
    final_message = Column(Text, nullable=True)  # User-edited version

    # Lead reply context
    lead_reply_text = Column(Text, nullable=True)

    # AI analysis
    analysis_sentiment = Column(String(20), nullable=True)
    analysis_signal_strength = Column(String(20), nullable=True)
    analysis_buying_signals = Column(Text, nullable=True)  # JSON list
    analysis_reasoning = Column(Text, nullable=True)
    analysis_outcome = Column(String(20), nullable=True)

    # Status
    status = Column(String(20), default=DraftStatus.PENDING.value, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    lead = relationship("Lead")
    sequence = relationship("Sequence")

    __table_args__ = (
        Index("ix_draft_user_status", "user_id", "status"),
    )
