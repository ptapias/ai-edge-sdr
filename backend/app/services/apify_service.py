"""
Apify service for fetching leads from Leads Finder actor.
"""
import logging
from typing import List, Dict, Any, Optional

from apify_client import ApifyClient

from ..config import get_settings
from ..schemas.search import ApifyFilters

logger = logging.getLogger(__name__)
settings = get_settings()


class ApifyService:
    """Service for interacting with Apify Leads Finder."""

    def __init__(self):
        self.client = ApifyClient(settings.apify_api_token)
        self.actor_id = settings.apify_actor_id

    def search_leads(self, filters: ApifyFilters) -> List[Dict[str, Any]]:
        """
        Execute the Apify actor to search for leads.

        Args:
            filters: ApifyFilters with search parameters

        Returns:
            List of lead dictionaries from Apify
        """
        # Build actor input from filters
        actor_input = {
            "email_status": filters.email_status,
            "fetch_count": filters.fetch_count,
            "file_name": "LinkedIn Leads"
        }

        # Add optional filters if provided
        if filters.contact_job_title:
            actor_input["contact_job_title"] = filters.contact_job_title
        if filters.contact_seniority:
            actor_input["contact_seniority"] = filters.contact_seniority
        if filters.contact_location:
            actor_input["contact_location"] = filters.contact_location
        if filters.company_industry:
            actor_input["company_industry"] = filters.company_industry
        if filters.company_size:
            actor_input["company_size"] = filters.company_size
        if filters.company_location:
            actor_input["company_location"] = filters.company_location

        logger.info(f"Starting Apify actor: {self.actor_id}")
        logger.info(f"Actor input: {actor_input}")

        try:
            # Run the actor and wait for completion
            run = self.client.actor(self.actor_id).call(run_input=actor_input)

            logger.info(f"Actor finished. Status: {run.get('status')}")
            logger.info(f"Dataset ID: {run.get('defaultDatasetId')}")

            # Get results from the dataset
            dataset_id = run["defaultDatasetId"]
            items = list(self.client.dataset(dataset_id).iterate_items())

            logger.info(f"Retrieved {len(items)} leads from Apify")
            return items

        except Exception as e:
            logger.error(f"Error running Apify actor: {e}")
            raise

    def transform_lead(self, apify_lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Apify lead data to our Lead model format.

        Args:
            apify_lead: Raw lead data from Apify

        Returns:
            Transformed lead dictionary matching our schema
        """
        return {
            "first_name": apify_lead.get("first_name"),
            "last_name": apify_lead.get("last_name"),
            "full_name": apify_lead.get("full_name"),
            "email": apify_lead.get("email"),
            "personal_email": apify_lead.get("personal_email"),
            "mobile_number": apify_lead.get("mobile_number"),
            "job_title": apify_lead.get("job_title"),
            "headline": apify_lead.get("headline"),
            "seniority_level": apify_lead.get("seniority_level"),
            "functional_level": apify_lead.get("functional_level"),
            "company_name": apify_lead.get("company_name"),
            "company_domain": apify_lead.get("company_domain"),
            "company_website": apify_lead.get("company_website"),
            "company_size": self._parse_company_size(apify_lead.get("company_size")),
            "company_industry": apify_lead.get("industry"),
            "company_description": apify_lead.get("company_description"),
            "company_annual_revenue": apify_lead.get("company_annual_revenue"),
            "company_total_funding": apify_lead.get("company_total_funding"),
            "company_phone": apify_lead.get("company_phone"),
            "company_full_address": apify_lead.get("company_full_address"),
            "city": apify_lead.get("city"),
            "state": apify_lead.get("state"),
            "country": apify_lead.get("country"),
            "linkedin_url": apify_lead.get("linkedin"),
            "sales_navigator_id": self._extract_sales_nav_id(apify_lead.get("linkedin")),
        }

    def _parse_company_size(self, size: Any) -> Optional[int]:
        """Parse company size to integer."""
        if size is None:
            return None
        if isinstance(size, int):
            return size
        if isinstance(size, str):
            # Handle ranges like "50-200"
            try:
                if "-" in size:
                    parts = size.split("-")
                    return int(parts[0])
                return int(size.replace(",", ""))
            except ValueError:
                return None
        return None

    def _extract_sales_nav_id(self, linkedin_url: Optional[str]) -> Optional[str]:
        """Extract Sales Navigator ID from LinkedIn URL."""
        if not linkedin_url:
            return None

        # Look for ACw... pattern (Sales Navigator ID)
        if "ACw" in linkedin_url:
            import re
            match = re.search(r"ACw[A-Za-z0-9_-]+", linkedin_url)
            if match:
                return match.group(0)

        # Extract from /in/username format
        if "/in/" in linkedin_url:
            parts = linkedin_url.split("/in/")
            if len(parts) > 1:
                return parts[1].split("/")[0].split("?")[0]

        return None
