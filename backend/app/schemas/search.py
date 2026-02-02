"""
Search schemas for natural language lead search.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ApifyFilters(BaseModel):
    """Filters to send to Apify Leads Finder."""
    contact_job_title: Optional[List[str]] = Field(None, description="Job titles to search")
    contact_seniority: Optional[List[str]] = Field(None, description="Seniority levels")
    contact_location: Optional[List[str]] = Field(None, description="Contact locations")
    company_industry: Optional[List[str]] = Field(None, description="Industries")
    company_size: Optional[List[str]] = Field(None, description="Company size ranges")
    company_location: Optional[List[str]] = Field(None, description="Company locations")
    email_status: List[str] = Field(default=["validated"], description="Email validation status")
    fetch_count: int = Field(default=50, ge=1, le=1000, description="Number of leads to fetch")


class SearchRequest(BaseModel):
    """Request schema for natural language search."""
    query: str = Field(..., min_length=5, description="Natural language search query")
    campaign_name: Optional[str] = Field(None, description="Name for the campaign")
    business_id: Optional[str] = Field(None, description="Business profile ID for scoring")
    max_results: int = Field(default=50, ge=1, le=500, description="Maximum leads to fetch")


class SearchResponse(BaseModel):
    """Response schema for search operation."""
    campaign_id: str
    total_leads: int
    filters_used: ApifyFilters
    message: str


class NLToFiltersResponse(BaseModel):
    """Response from Claude NL-to-filters conversion."""
    filters: ApifyFilters
    interpretation: str = Field(..., description="How the AI interpreted the query")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the interpretation")
