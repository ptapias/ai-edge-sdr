"""
Automation settings model for automatic LinkedIn outreach.
"""
import uuid
from datetime import datetime, time
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Time

from ..database import Base


class AutomationSettings(Base):
    """Settings for automatic LinkedIn invitation sending."""

    __tablename__ = "automation_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Toggle
    enabled = Column(Boolean, default=False)

    # Working hours (24h format)
    work_start_hour = Column(Integer, default=9)  # 9 AM
    work_start_minute = Column(Integer, default=0)
    work_end_hour = Column(Integer, default=18)  # 6 PM
    work_end_minute = Column(Integer, default=0)

    # Working days (bitmask: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)
    # Default: Monday-Friday = 1+2+4+8+16 = 31
    working_days = Column(Integer, default=31)

    # Invitation settings
    daily_limit = Column(Integer, default=40)  # Max 40 per day
    min_delay_seconds = Column(Integer, default=60)  # Min delay between invitations (1 min)
    max_delay_seconds = Column(Integer, default=300)  # Max delay between invitations (5 min)

    # Score filter - only send to leads with this minimum score
    min_lead_score = Column(Integer, default=0)  # 0 = no filter

    # Status filter - only send to leads with these statuses
    # Default: send to new and pending
    target_statuses = Column(String(200), default="new,pending")

    # Tracking
    invitations_sent_today = Column(Integer, default=0)
    last_invitation_at = Column(DateTime, nullable=True)
    last_reset_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AutomationSettings enabled={self.enabled} limit={self.daily_limit}>"

    def is_working_hour(self, current_time: datetime = None) -> bool:
        """Check if current time is within working hours."""
        if current_time is None:
            current_time = datetime.utcnow()

        # Check day of week (0=Monday, 6=Sunday)
        day_bit = 1 << current_time.weekday()
        if not (self.working_days & day_bit):
            return False

        # Check time
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = self.work_start_hour * 60 + self.work_start_minute
        end_minutes = self.work_end_hour * 60 + self.work_end_minute

        return start_minutes <= current_minutes <= end_minutes

    def can_send_invitation(self) -> bool:
        """Check if we can send another invitation today."""
        # Check daily limit
        if self.invitations_sent_today >= self.daily_limit:
            return False

        # Check if enabled
        if not self.enabled:
            return False

        # Check working hours
        if not self.is_working_hour():
            return False

        return True

    def reset_daily_counter(self):
        """Reset the daily invitation counter."""
        self.invitations_sent_today = 0
        self.last_reset_date = datetime.utcnow()


class InvitationLog(Base):
    """Log of sent invitations for tracking and analytics."""

    __tablename__ = "invitation_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), nullable=False)
    lead_name = Column(String(200), nullable=True)
    lead_company = Column(String(200), nullable=True)

    # Result
    success = Column(Boolean, default=False)
    error_message = Column(String(500), nullable=True)

    # Metadata
    sent_at = Column(DateTime, default=datetime.utcnow)
    mode = Column(String(20), default="manual")  # manual or automatic
