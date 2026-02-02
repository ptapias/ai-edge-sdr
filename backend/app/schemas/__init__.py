"""
Pydantic schemas for request/response validation.
"""
from .lead import LeadBase, LeadCreate, LeadResponse, LeadUpdate, LeadScoring
from .campaign import CampaignBase, CampaignCreate, CampaignResponse
from .business_profile import BusinessProfileBase, BusinessProfileCreate, BusinessProfileResponse
from .search import SearchRequest, SearchResponse, ApifyFilters

__all__ = [
    "LeadBase", "LeadCreate", "LeadResponse", "LeadUpdate", "LeadScoring",
    "CampaignBase", "CampaignCreate", "CampaignResponse",
    "BusinessProfileBase", "BusinessProfileCreate", "BusinessProfileResponse",
    "SearchRequest", "SearchResponse", "ApifyFilters",
]
