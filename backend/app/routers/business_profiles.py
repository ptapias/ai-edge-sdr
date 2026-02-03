"""
Business profiles router for CRUD operations.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.business_profile import (
    BusinessProfileCreate,
    BusinessProfileResponse,
    BusinessProfileUpdate
)
from ..models import BusinessProfile, User

router = APIRouter(prefix="/api/business-profiles", tags=["business-profiles"])


@router.get("/", response_model=List[BusinessProfileResponse])
def list_business_profiles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all business profiles (filtered by current user)."""
    profiles = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.user_id == current_user.id)
        .order_by(desc(BusinessProfile.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Auto-fix: if profiles exist but none is default, set the first one
    if profiles:
        has_default = any(p.is_default for p in profiles)
        if not has_default:
            profiles[0].is_default = True
            db.commit()
            db.refresh(profiles[0])

    return profiles


@router.get("/default", response_model=BusinessProfileResponse)
def get_default_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the default business profile (filtered by current user)."""
    profile = db.query(BusinessProfile).filter(
        BusinessProfile.is_default == True,
        BusinessProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No default profile set")
    return profile


@router.get("/{profile_id}", response_model=BusinessProfileResponse)
def get_business_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single business profile by ID (must belong to current user)."""
    profile = db.query(BusinessProfile).filter(
        BusinessProfile.id == profile_id,
        BusinessProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/", response_model=BusinessProfileResponse)
def create_business_profile(
    profile: BusinessProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new business profile (assigned to current user)."""
    # Check if any profiles exist for this user - if not, this will be default
    existing_count = db.query(BusinessProfile).filter(
        BusinessProfile.user_id == current_user.id
    ).count()
    should_be_default = profile.is_default or existing_count == 0

    # If this is set as default, unset other defaults for this user
    if should_be_default:
        db.query(BusinessProfile).filter(
            BusinessProfile.is_default == True,
            BusinessProfile.user_id == current_user.id
        ).update({"is_default": False})

    profile_data = profile.model_dump()
    profile_data["is_default"] = should_be_default
    profile_data["user_id"] = current_user.id

    db_profile = BusinessProfile(**profile_data)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.patch("/{profile_id}", response_model=BusinessProfileResponse)
def update_business_profile(
    profile_id: str,
    update: BusinessProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a business profile (must belong to current user)."""
    profile = db.query(BusinessProfile).filter(
        BusinessProfile.id == profile_id,
        BusinessProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = update.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults for this user
    if update_data.get("is_default"):
        db.query(BusinessProfile).filter(
            BusinessProfile.is_default == True,
            BusinessProfile.id != profile_id,
            BusinessProfile.user_id == current_user.id
        ).update({"is_default": False})

    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
def delete_business_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a business profile (must belong to current user)."""
    profile = db.query(BusinessProfile).filter(
        BusinessProfile.id == profile_id,
        BusinessProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return {"message": "Profile deleted"}
