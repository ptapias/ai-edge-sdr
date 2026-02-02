"""
Campaigns router for CRUD operations.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..schemas.campaign import CampaignCreate, CampaignResponse, CampaignUpdate
from ..models import Campaign

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("/", response_model=List[CampaignResponse])
def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List all campaigns."""
    campaigns = (
        db.query(Campaign)
        .order_by(desc(Campaign.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return campaigns


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Get a single campaign by ID."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/", response_model=CampaignResponse)
def create_campaign(campaign: CampaignCreate, db: Session = Depends(get_db)):
    """Create a new campaign."""
    db_campaign = Campaign(**campaign.model_dump())
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    return db_campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    update: CampaignUpdate,
    db: Session = Depends(get_db)
):
    """Update a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Delete a campaign and all its leads."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    db.delete(campaign)
    db.commit()
    return {"message": "Campaign deleted"}


@router.get("/{campaign_id}/stats")
def get_campaign_stats(campaign_id: str, db: Session = Depends(get_db)):
    """Get statistics for a campaign."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    from ..models import Lead

    total = campaign.leads.count()
    verified = campaign.leads.filter(Lead.email_verified == True).count()
    hot = campaign.leads.filter(Lead.score_label == "hot").count()
    warm = campaign.leads.filter(Lead.score_label == "warm").count()
    cold = campaign.leads.filter(Lead.score_label == "cold").count()
    contacted = campaign.leads.filter(Lead.status == "contacted").count()
    connected = campaign.leads.filter(Lead.status == "connected").count()
    replied = campaign.leads.filter(Lead.status == "replied").count()

    return {
        "campaign_id": campaign_id,
        "total_leads": total,
        "verified_emails": verified,
        "scoring": {
            "hot": hot,
            "warm": warm,
            "cold": cold,
            "unscored": total - hot - warm - cold
        },
        "status": {
            "new": total - contacted - connected - replied,
            "contacted": contacted,
            "connected": connected,
            "replied": replied
        }
    }
