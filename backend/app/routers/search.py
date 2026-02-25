"""
Search router for natural language lead search.
"""
import json
import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas.search import SearchRequest, SearchResponse, NLToFiltersResponse
from ..models import Lead, Campaign, User
from ..services.apify_service import ApifyService
from ..services.claude_service import ClaudeService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
def search_leads(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for leads using natural language query (assigned to current user).

    1. Converts NL query to Apify filters using Claude
    2. Executes Apify actor to fetch leads
    3. Stores leads in database with campaign
    """
    try:
        claude_service = ClaudeService()
        apify_service = ApifyService()

        # Step 1: Convert natural language to filters
        logger.info(f"Processing search query: {request.query}")
        nl_result = claude_service.natural_language_to_filters(request.query)

        # Update fetch count from request
        nl_result.filters.fetch_count = request.max_results

        logger.info(f"Interpreted as: {nl_result.interpretation}")
        logger.info(f"Filters: {nl_result.filters.model_dump()}")

        # Step 2: Create campaign (assigned to current user)
        campaign = Campaign(
            name=request.campaign_name or f"Search: {request.query[:50]}",
            search_query=request.query,
            search_filters=json.dumps(nl_result.filters.model_dump()),
            business_id=request.business_id,
            user_id=current_user.id
        )
        db.add(campaign)
        try:
            db.flush()  # Get campaign ID
        except Exception as flush_err:
            logger.error(f"DB flush failed: {flush_err}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create campaign: {str(flush_err)}"
            )

        # Step 3: Fetch leads from Apify
        try:
            raw_leads = apify_service.search_leads(nl_result.filters)
        except Exception as e:
            logger.error(f"Apify search failed: {e}")
            # Still commit the campaign even if Apify fails
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Lead search failed: {str(e)}"
            )

        # Step 4: Transform and store leads (assigned to current user)
        lead_count = 0
        errors = 0
        for raw_lead in raw_leads:
            try:
                lead_data = apify_service.transform_lead(raw_lead)
                lead = Lead(
                    **lead_data,
                    campaign_id=campaign.id,
                    user_id=current_user.id
                )
                db.add(lead)
                lead_count += 1
            except Exception as lead_err:
                logger.error(f"Error transforming lead: {lead_err}")
                errors += 1

        # Update campaign stats
        campaign.total_leads = lead_count

        try:
            db.commit()
        except Exception as commit_err:
            logger.error(f"DB commit failed: {commit_err}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save leads: {str(commit_err)}"
            )

        logger.info(f"Search complete. Campaign {campaign.id}: {lead_count} leads, {errors} errors")

        return SearchResponse(
            campaign_id=campaign.id,
            total_leads=lead_count,
            filters_used=nl_result.filters,
            message=f"Found {lead_count} leads. {nl_result.interpretation}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in search: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Search error: {str(e)}"
        )


@router.post("/preview", response_model=NLToFiltersResponse)
def preview_search(
    request: SearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Preview how a natural language query will be interpreted.
    Does not execute the actual search.
    """
    claude_service = ClaudeService()
    result = claude_service.natural_language_to_filters(request.query)
    result.filters.fetch_count = request.max_results
    return result
