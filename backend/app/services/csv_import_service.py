"""
CSV/Excel Import service for parsing and importing leads from various file formats.
Supports multiple column naming conventions (prospecting tools, sponsors lists, etc.)
"""
import uuid
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy.orm import Session

from ..models.lead import Lead, LeadStatus
from ..models.campaign import Campaign

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flexible column mapping
# Each lead field has a list of possible CSV column names (matched case-insensitively).
# This supports the original prospecting-tool format AND the AI Edge sponsors format,
# plus common variations.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: Dict[str, List[str]] = {
    # ── Personal info ──
    "first_name": [
        "firstname", "first_name", "first name", "fname", "given name",
    ],
    "last_name": [
        "lastname", "last_name", "last name", "lname", "surname", "family name",
    ],

    # ── Contact info ──
    "email": [
        "email", "linkedinemail", "work email", "work_email",
        "email address", "e-mail", "workemail",
    ],
    "personal_email": [
        "personalemail", "personal_email", "personal email", "proemail",
    ],
    "mobile_number": [
        "phonenumbers", "phone", "phone number", "mobile",
        "mobile_number", "telephone", "tel",
    ],

    # ── Professional info ──
    "job_title": [
        "job_title", "jobtitle", "job title", "title", "position", "role",
    ],
    "headline": [
        "headline", "occupation", "bio", "tagline",
    ],
    "seniority_level": [
        "seniority", "seniority_level", "seniority level",
    ],

    # ── Company info ──
    "company_name": [
        "company_name", "companyname", "company", "company name",
        "organization", "org", "employer",
    ],
    "company_website": [
        "company_website", "companywebsite", "company website", "website",
    ],
    "company_industry": [
        "industry", "industries", "company_industry", "company industry", "sector",
    ],
    "company_annual_revenue": [
        "annual revenue", "annual_revenue", "annualrevenue", "revenue",
    ],

    # ── Location ──
    "country": ["country", "nation"],
    "city": ["city", "company city", "companycity"],
    "state": ["company state", "companystate", "region", "province"],

    # ── LinkedIn ──
    "linkedin_url": [
        "linkedinurl", "linkedin_url", "linkedin url", "linkedin",
        "linkedin profile", "profile url", "profileurl",
    ],
    "sales_navigator_id": [
        "salesnavigatorid", "sales_navigator_id", "sales navigator id",
    ],

    # ── Internal fields (used for processing, not stored directly) ──
    "_location": ["location"],
    "_csv_state": ["state"],          # Prospecting tool "state" field (often garbage)
    "_profile_status": ["profilestatus", "profile_status", "profile status"],
    "_message_sent": ["messagesent", "message_sent", "message sent"],
    "_message_replied": ["messagereplied", "message_replied", "message replied"],
    "_connection_request_date": [
        "connectionrequestdate", "connection_request_date",
    ],
    "_connected_at": ["connectedat", "connected_at", "connected at"],
    "_tags": ["tags"],
    "_profile_picture_url": [
        "profilepictureurl", "profile_picture_url", "profile picture url",
    ],
    "_departments": ["departments", "department"],
    "_employees_raw": [
        "# employees", "employees", "number of employees",
        "headcount", "company size", "num employees",
    ],
}


def _build_alias_lookup() -> Dict[str, str]:
    """Build a reverse lookup: normalized alias -> lead_field."""
    lookup: Dict[str, str] = {}
    for lead_field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[alias.lower().strip()] = lead_field
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def detect_column_mapping(columns: List[str]) -> Dict[str, str]:
    """
    Auto-detect column mapping based on CSV/Excel headers.
    Uses case-insensitive matching against known aliases.
    Returns {csv_column_name: lead_field_name}.
    """
    mapping: Dict[str, str] = {}
    used_fields: set = set()

    for csv_col in columns:
        normalized = csv_col.lower().strip()
        if normalized in _ALIAS_LOOKUP:
            lead_field = _ALIAS_LOOKUP[normalized]
            if lead_field not in used_fields:
                mapping[csv_col] = lead_field
                used_fields.add(lead_field)

    return mapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def parse_employee_count(raw: str) -> Optional[int]:
    """
    Parse employee count strings like '5001-10,000 employees' or '501-1000'.
    Returns the upper bound of the range as an integer, or None if unparseable.
    """
    if not raw:
        return None
    cleaned = raw.lower().replace(",", "").replace("employees", "").strip()
    numbers = re.findall(r"\d+", cleaned)
    if numbers:
        return max(int(n) for n in numbers)
    return None


def _find_csv_col(column_mapping: Dict[str, str], lead_field: str) -> Optional[str]:
    """Find the CSV column name that maps to a given lead field."""
    for csv_col, field in column_mapping.items():
        if field == lead_field:
            return csv_col
    return None


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------

def derive_status(
    row: Dict[str, Any],
    column_mapping: Optional[Dict[str, str]] = None,
) -> str:
    """Derive lead CRM status from CSV data using the column mapping."""
    if column_mapping:
        reply_col = _find_csv_col(column_mapping, "_message_replied")
        status_col = _find_csv_col(column_mapping, "_profile_status")
        conn_req_col = _find_csv_col(column_mapping, "_connection_request_date")
        conn_at_col = _find_csv_col(column_mapping, "_connected_at")
    else:
        reply_col = "messageReplied"
        status_col = "profileStatus"
        conn_req_col = "connectionRequestDate"
        conn_at_col = "connectedAt"

    message_replied = str(row.get(reply_col, "") if reply_col else "").strip().lower()
    profile_status = str(row.get(status_col, "") if status_col else "").strip().lower()
    connection_request_date = str(row.get(conn_req_col, "") if conn_req_col else "").strip()
    connected_at = str(row.get(conn_at_col, "") if conn_at_col else "").strip()

    if message_replied == "yes":
        return LeadStatus.IN_CONVERSATION.value
    if connected_at and connected_at not in ("", "none", "null"):
        return LeadStatus.CONNECTED.value
    if profile_status == "connected":
        return LeadStatus.CONNECTED.value
    if connection_request_date and connection_request_date not in ("", "none", "null"):
        return LeadStatus.INVITATION_SENT.value

    return LeadStatus.NEW.value


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def check_duplicates(
    db: Session,
    rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],
    user_id: str,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Check for duplicate leads and return count + non-duplicate rows."""
    linkedin_url_col = _find_csv_col(column_mapping, "linkedin_url")
    email_col = _find_csv_col(column_mapping, "email")

    duplicates = 0
    new_rows = []

    for row in rows:
        linkedin_url = ""
        if linkedin_url_col:
            linkedin_url = str(row.get(linkedin_url_col, "") or "").strip()

        email = ""
        if email_col:
            email = str(row.get(email_col, "") or "").strip()

        is_duplicate = False

        if linkedin_url:
            existing = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.linkedin_url == linkedin_url,
            ).first()
            if existing:
                is_duplicate = True

        if not is_duplicate and email:
            existing = db.query(Lead).filter(
                Lead.user_id == user_id,
                Lead.email == email,
            ).first()
            if existing:
                is_duplicate = True

        if is_duplicate:
            duplicates += 1
        else:
            new_rows.append(row)

    return duplicates, new_rows


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def preview_import(
    db: Session,
    rows: List[Dict[str, Any]],
    columns: List[str],
    user_id: str,
) -> Dict[str, Any]:
    """Preview import: detect mapping, count duplicates, show sample rows."""
    column_mapping = detect_column_mapping(columns)
    duplicate_count, new_rows = check_duplicates(db, rows, column_mapping, user_id)

    # Status breakdown
    status_breakdown: Dict[str, int] = {}
    for row in new_rows:
        status = derive_status(row, column_mapping)
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


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------

def map_row_to_lead_data(
    row: Dict[str, Any],
    column_mapping: Dict[str, str],
) -> Dict[str, Any]:
    """Map a CSV/Excel row to lead field data using the column mapping."""
    lead_data: Dict[str, Any] = {}

    for csv_col, lead_field in column_mapping.items():
        value = row.get(csv_col, "")
        if isinstance(value, str):
            value = value.strip()
        if value in ("", "none", "null", None):
            value = None

        # Skip internal fields (those starting with _)
        if lead_field.startswith("_"):
            continue

        lead_data[lead_field] = value

    # ── Parse "# Employees" into company_size (integer) ──
    employees_col = _find_csv_col(column_mapping, "_employees_raw")
    if employees_col:
        raw_employees = str(row.get(employees_col, "") or "")
        parsed = parse_employee_count(raw_employees)
        if parsed is not None:
            lead_data["company_size"] = parsed

    # ── Parse location (from prospecting tools) ──
    location_col = _find_csv_col(column_mapping, "_location")
    if location_col:
        location = str(row.get(location_col, "") or "").strip()
        if location and location not in ("none", "null"):
            loc_parts = parse_location(location)
            if not lead_data.get("city"):
                lead_data["city"] = loc_parts["city"]
            if not lead_data.get("state") or lead_data.get("state") == "none":
                lead_data["state"] = loc_parts["state"]
            if not lead_data.get("country"):
                lead_data["country"] = loc_parts["country"]

    # ── Build full_name ──
    first = lead_data.get("first_name", "") or ""
    last = lead_data.get("last_name", "") or ""
    if first or last:
        lead_data["full_name"] = f"{first} {last}".strip()

    # ── Derive status ──
    lead_data["status"] = derive_status(row, column_mapping)

    # ── Parse connection dates (from prospecting tools) ──
    conn_at_col = _find_csv_col(column_mapping, "_connected_at")
    if conn_at_col:
        connected_at = str(row.get(conn_at_col, "") or "").strip()
        if connected_at and connected_at not in ("", "none", "null"):
            try:
                lead_data["connected_at"] = datetime.fromisoformat(connected_at)
            except (ValueError, TypeError):
                pass

    conn_req_col = _find_csv_col(column_mapping, "_connection_request_date")
    if conn_req_col:
        connection_request_date = str(row.get(conn_req_col, "") or "").strip()
        if connection_request_date and connection_request_date not in ("", "none", "null"):
            try:
                lead_data["connection_sent_at"] = datetime.fromisoformat(
                    connection_request_date
                )
            except (ValueError, TypeError):
                pass

    return lead_data


# ---------------------------------------------------------------------------
# Execute import
# ---------------------------------------------------------------------------

def execute_import(
    db: Session,
    rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],
    campaign_name: str,
    campaign_description: Optional[str],
    user_id: str,
) -> Dict[str, Any]:
    """Execute the import: create campaign and lead records."""
    # Filter duplicates first
    duplicate_count, new_rows = check_duplicates(db, rows, column_mapping, user_id)

    if not new_rows:
        return {
            "campaign_id": "",
            "campaign_name": campaign_name,
            "total_processed": len(rows),
            "imported": 0,
            "duplicates_skipped": duplicate_count,
            "errors": 0,
            "status_breakdown": {},
        }

    # Create campaign
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=campaign_name,
        description=campaign_description or f"Import - {len(new_rows)} leads",
        search_query=f"File Import ({len(rows)} total, {len(new_rows)} new)",
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

            # Filter out None values
            lead_fields = {k: v for k, v in lead_data.items() if v is not None}

            lead = Lead(
                id=str(uuid.uuid4()),
                campaign_id=campaign.id,
                user_id=user_id,
                **lead_fields,
            )
            db.add(lead)

            status = lead_data.get("status", "new")
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
            imported += 1

        except Exception as e:
            logger.error(f"Error importing row: {e}")
            errors += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error committing import: {e}")
        raise

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_processed": len(rows),
        "imported": imported,
        "duplicates_skipped": duplicate_count,
        "errors": errors,
        "status_breakdown": status_breakdown,
    }
