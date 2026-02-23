"""
CSV Import service for parsing and importing leads from CSV files.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy.orm import Session

from ..models.lead import Lead, LeadStatus
from ..models.campaign import Campaign

logger = logging.getLogger(__name__)

# Hardcoded column mapping from prospecting tool CSV format
DEFAULT_COLUMN_MAPPING = {
    "firstName": "first_name",
    "lastName": "last_name",
    "occupation": "headline",
    "job_title": "job_title",
    "linkedinUrl": "linkedin_url",
    "linkedinEmail": "email",
    "proEmail": "personal_email",
    "phoneNumbers": "mobile_number",
    "company_name": "company_name",
    "company_website": "company_website",
    "country": "country",
    "salesNavigatorId": "sales_navigator_id",
    "location": "_location",  # Special: parsed into city, state, country
    "state": "_csv_state",  # CSV state field (often "none")
    "profileStatus": "_profile_status",  # Used for status derivation
    "messageSent": "_message_sent",
    "messageReplied": "_message_replied",
    "connectionRequestDate": "_connection_request_date",
    "connectedAt": "_connected_at",
    "tags": "_tags",
    "profilePictureUrl": "_profile_picture_url",
}


def detect_column_mapping(columns: List[str]) -> Dict[str, str]:
    """Auto-detect column mapping based on CSV headers."""
    mapping = {}
    for csv_col in columns:
        if csv_col in DEFAULT_COLUMN_MAPPING:
            mapping[csv_col] = DEFAULT_COLUMN_MAPPING[csv_col]
    return mapping


def parse_location(location: str) -> Dict[str, Optional[str]]:
    """Parse location string like 'City, State, Country' into components."""
    if not location:
        return {"city": None, "state": None, "country": None}

    parts = [p.strip() for p in location.split(",")]

    if len(parts) >= 3:
        return {"city": parts[0], "state": parts[1], "country": parts[2]}
    elif len(parts) == 2:
        return {"city": parts[0], "state": None, "country": parts[1]}
    elif len(parts) == 1:
        return {"city": None, "state": None, "country": parts[0]}

    return {"city": None, "state": None, "country": None}


def derive_status(row: Dict[str, Any]) -> str:
    """Derive lead CRM status from CSV data."""
    message_replied = str(row.get("messageReplied", "")).strip().lower()
    profile_status = str(row.get("profileStatus", "")).strip().lower()
    connection_request_date = str(row.get("connectionRequestDate", "")).strip()
    connected_at = str(row.get("connectedAt", "")).strip()

    if message_replied == "yes":
        return LeadStatus.IN_CONVERSATION.value
    if connected_at and connected_at not in ("", "none", "null"):
        return LeadStatus.CONNECTED.value
    if profile_status == "connected":
        return LeadStatus.CONNECTED.value
    if connection_request_date and connection_request_date not in ("", "none", "null"):
        return LeadStatus.INVITATION_SENT.value

    return LeadStatus.NEW.value


def check_duplicates(
    db: Session,
    rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],
    user_id: str
) -> Tuple[int, List[Dict[str, Any]]]:
    """Check for duplicate leads and return count + non-duplicate rows."""
    duplicates = 0
    new_rows = []

    for row in rows:
        linkedin_url = row.get("linkedinUrl", "").strip()
        email = row.get("linkedinEmail", "").strip()

        is_duplicate = False

        if linkedin_url:
            existing = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.linkedin_url == linkedin_url
            ).first()
            if existing:
                is_duplicate = True

        if not is_duplicate and email:
            existing = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.email == email
            ).first()
            if existing:
                is_duplicate = True

        if is_duplicate:
            duplicates += 1
        else:
            new_rows.append(row)

    return duplicates, new_rows


def preview_import(
    db: Session,
    rows: List[Dict[str, Any]],
    columns: List[str],
    user_id: str
) -> Dict[str, Any]:
    """Preview CSV import: detect mapping, count duplicates, show sample rows."""
    column_mapping = detect_column_mapping(columns)
    duplicate_count, new_rows = check_duplicates(db, rows, column_mapping, user_id)

    # Status breakdown
    status_breakdown: Dict[str, int] = {}
    for row in new_rows:
        status = derive_status(row)
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

    # Preview first 5 mapped rows
    preview_rows = []
    for row in new_rows[:5]:
        mapped = map_row_to_lead_data(row, column_mapping)
        preview_rows.append(mapped)

    return {
        "total_rows": len(rows),
        "duplicate_count": duplicate_count,
        "new_count": len(new_rows),
        "preview_rows": preview_rows,
        "detected_columns": columns,
        "column_mapping": column_mapping,
        "status_breakdown": status_breakdown,
    }


def map_row_to_lead_data(row: Dict[str, Any], column_mapping: Dict[str, str]) -> Dict[str, Any]:
    """Map a CSV row to lead field data."""
    lead_data: Dict[str, Any] = {}

    for csv_col, lead_field in column_mapping.items():
        value = row.get(csv_col, "")
        if isinstance(value, str):
            value = value.strip()
        if value in ("", "none", "null", None):
            value = None

        if lead_field.startswith("_"):
            continue  # Skip internal fields

        lead_data[lead_field] = value

    # Parse location
    location = row.get("location", "")
    if location and str(location).strip() not in ("", "none", "null"):
        loc_parts = parse_location(str(location).strip())
        if not lead_data.get("city"):
            lead_data["city"] = loc_parts["city"]
        if not lead_data.get("state") or lead_data.get("state") == "none":
            lead_data["state"] = loc_parts["state"]
        if not lead_data.get("country"):
            lead_data["country"] = loc_parts["country"]

    # Build full_name
    first = lead_data.get("first_name", "") or ""
    last = lead_data.get("last_name", "") or ""
    if first or last:
        lead_data["full_name"] = f"{first} {last}".strip()

    # Derive status
    lead_data["status"] = derive_status(row)

    # Parse connection dates
    connected_at = row.get("connectedAt", "")
    if connected_at and str(connected_at).strip() not in ("", "none", "null"):
        try:
            lead_data["connected_at"] = datetime.fromisoformat(str(connected_at).strip())
        except (ValueError, TypeError):
            pass

    connection_request_date = row.get("connectionRequestDate", "")
    if connection_request_date and str(connection_request_date).strip() not in ("", "none", "null"):
        try:
            lead_data["connection_sent_at"] = datetime.fromisoformat(str(connection_request_date).strip())
        except (ValueError, TypeError):
            pass

    return lead_data


def execute_import(
    db: Session,
    rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],
    campaign_name: str,
    campaign_description: Optional[str],
    user_id: str
) -> Dict[str, Any]:
    """Execute the CSV import: create campaign and lead records."""
    # Filter duplicates first
    duplicate_count, new_rows = check_duplicates(db, rows, column_mapping, user_id)

    # Create campaign
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=campaign_name,
        description=campaign_description or f"CSV Import - {len(new_rows)} leads",
        search_query=f"CSV Import ({len(rows)} total, {len(new_rows)} new)",
        total_leads=len(new_rows),
        user_id=user_id,
    )
    db.add(campaign)

    # Import leads
    imported = 0
    errors = 0
    status_breakdown: Dict[str, int] = {}

    for row in new_rows:
        try:
            lead_data = map_row_to_lead_data(row, column_mapping)

            lead = Lead(
                id=str(uuid.uuid4()),
                campaign_id=campaign.id,
                user_id=user_id,
                **{k: v for k, v in lead_data.items() if v is not None}
            )
            db.add(lead)

            status = lead_data.get("status", "new")
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
            imported += 1

        except Exception as e:
            logger.error(f"Error importing row: {e}")
            errors += 1

    db.commit()

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_processed": len(rows),
        "imported": imported,
        "duplicates_skipped": duplicate_count,
        "errors": errors,
        "status_breakdown": status_breakdown,
    }
