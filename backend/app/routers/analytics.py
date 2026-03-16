"""
Analytics router for dashboard data and reporting.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Date

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Lead, Campaign, User
from ..models.lead import LeadStatus
from ..models.automation import InvitationLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/pipeline")
def get_pipeline_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Count leads per CRM status."""
    results = (
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id)
        .group_by(Lead.status)
        .all()
    )

    pipeline = {status.value: 0 for status in LeadStatus}
    for status, count in results:
        pipeline[status] = count

    return {"pipeline": pipeline, "total": sum(pipeline.values())}


@router.get("/conversion")
def get_conversion_funnel(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Funnel metrics with conversion rates between stages."""
    total = db.query(Lead).filter(Lead.user_id == current_user.id).count()

    stages = [
        ("new", LeadStatus.NEW.value),
        ("invitation_sent", LeadStatus.INVITATION_SENT.value),
        ("connected", LeadStatus.CONNECTED.value),
        ("in_conversation", LeadStatus.IN_CONVERSATION.value),
        ("meeting_scheduled", LeadStatus.MEETING_SCHEDULED.value),
        ("qualified", LeadStatus.QUALIFIED.value),
        ("closed_won", LeadStatus.CLOSED_WON.value),
    ]

    # Count leads that are AT or PAST each stage
    stage_order = {s[1]: i for i, s in enumerate(stages)}
    counts = (
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id)
        .group_by(Lead.status)
        .all()
    )

    status_counts = {s: 0 for _, s in stages}
    for status, count in counts:
        if status in status_counts:
            status_counts[status] = count

    # Build cumulative funnel (at or past each stage)
    funnel = []
    cumulative = total
    for label, status_val in stages:
        at_stage = status_counts.get(status_val, 0)
        funnel.append({
            "stage": label,
            "count": at_stage,
            "cumulative": cumulative,
            "rate": round((cumulative / total * 100) if total > 0 else 0, 1),
        })
        cumulative -= at_stage

    # Conversion rates between adjacent stages
    for i in range(1, len(funnel)):
        prev_cum = funnel[i - 1]["cumulative"]
        curr_cum = funnel[i]["cumulative"]
        funnel[i]["conversion_from_previous"] = (
            round((curr_cum / prev_cum * 100) if prev_cum > 0 else 0, 1)
        )

    return {"total": total, "funnel": funnel}


@router.get("/temperature")
def get_temperature_distribution(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Score label distribution: hot/warm/cold/unscored."""
    results = (
        db.query(Lead.score_label, func.count(Lead.id))
        .filter(Lead.user_id == current_user.id)
        .group_by(Lead.score_label)
        .all()
    )

    distribution = {"hot": 0, "warm": 0, "cold": 0, "unscored": 0}
    for label, count in results:
        if label in ("hot", "warm", "cold"):
            distribution[label] = count
        else:
            distribution["unscored"] += count

    return {"distribution": distribution, "total": sum(distribution.values())}


@router.get("/response-tracking")
def get_response_tracking(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Acceptance rate, active conversations, and tracking metrics."""
    contacted = db.query(Lead).filter(
        Lead.user_id == current_user.id,
        Lead.connection_sent_at.isnot(None)
    ).count()

    connected = db.query(Lead).filter(
        Lead.user_id == current_user.id,
        Lead.connected_at.isnot(None)
    ).count()

    # Active conversations = leads that have a linkedin_chat_id (actual message exchange)
    active_conversations = db.query(Lead).filter(
        Lead.user_id == current_user.id,
        Lead.linkedin_chat_id.isnot(None)
    ).count()

    # Average time to connect (for leads that have both dates)
    avg_time_query = (
        db.query(
            func.avg(
                func.extract("epoch", Lead.connected_at - Lead.connection_sent_at) / 86400
            )
        )
        .filter(
            Lead.user_id == current_user.id,
            Lead.connected_at.isnot(None),
            Lead.connection_sent_at.isnot(None),
        )
        .scalar()
    )

    avg_days = None
    if avg_time_query is not None:
        try:
            avg_days = round(float(avg_time_query), 1)
        except (ValueError, TypeError):
            avg_days = None

    return {
        "contacted": contacted,
        "connected": connected,
        "active_conversations": active_conversations,
        "acceptance_rate": round((connected / contacted * 100) if contacted > 0 else 0, 1),
        "conversation_rate": round((active_conversations / connected * 100) if connected > 0 else 0, 1),
        "avg_days_to_connect": avg_days,
    }


@router.get("/activity")
def get_activity_timeline(
    period: str = Query("30d", description="Period: 7d, 14d, 30d, 90d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Daily activity over the specified period. Only counts successful invitations."""
    days_map = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
    days = days_map.get(period, 30)
    start_date = datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None) - timedelta(days=days)

    # Only count successful invitation logs
    invitation_data = (
        db.query(
            cast(InvitationLog.sent_at, Date).label("date"),
            func.count(InvitationLog.id).label("invitations"),
        )
        .filter(
            InvitationLog.user_id == current_user.id,
            InvitationLog.sent_at >= start_date,
            InvitationLog.success == True,
        )
        .group_by(cast(InvitationLog.sent_at, Date))
        .all()
    )

    inv_by_date = {}
    for row in invitation_data:
        inv_by_date[str(row.date)] = row.invitations

    # Connections by day
    connection_data = (
        db.query(
            cast(Lead.connected_at, Date).label("date"),
            func.count(Lead.id).label("connections"),
        )
        .filter(
            Lead.user_id == current_user.id,
            Lead.connected_at.isnot(None),
            Lead.connected_at >= start_date,
        )
        .group_by(cast(Lead.connected_at, Date))
        .all()
    )

    conn_by_date = {}
    for row in connection_data:
        conn_by_date[str(row.date)] = row.connections

    # Build daily timeline (using Spanish timezone for correct day boundaries)
    from zoneinfo import ZoneInfo
    now_local = datetime.now(ZoneInfo("Europe/Madrid"))
    timeline = []
    for i in range(days):
        date = (now_local - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        timeline.append({
            "date": date,
            "invitations": inv_by_date.get(date, 0),
            "connections": conn_by_date.get(date, 0),
        })

    return {"period": period, "timeline": timeline}


@router.get("/campaigns")
def get_campaign_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Per-campaign breakdown with stats."""
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.user_id == current_user.id)
        .all()
    )

    result = []
    for campaign in campaigns:
        leads = (
            db.query(Lead)
            .filter(Lead.campaign_id == campaign.id, Lead.user_id == current_user.id)
            .all()
        )

        status_counts = {}
        score_counts = {"hot": 0, "warm": 0, "cold": 0, "unscored": 0}
        contacted = 0
        accepted = 0

        for lead in leads:
            status_counts[lead.status] = status_counts.get(lead.status, 0) + 1
            if lead.score_label in ("hot", "warm", "cold"):
                score_counts[lead.score_label] += 1
            else:
                score_counts["unscored"] += 1
            if lead.connection_sent_at:
                contacted += 1
            if lead.connected_at:
                accepted += 1

        result.append({
            "id": campaign.id,
            "name": campaign.name,
            "total_leads": len(leads),
            "status_breakdown": status_counts,
            "score_breakdown": score_counts,
            "contacted": contacted,
            "accepted": accepted,
            "acceptance_rate": round((accepted / contacted * 100) if contacted > 0 else 0, 1),
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        })

    return {"campaigns": result}
