"""
CSV Import schemas for API validation.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class CSVColumnMapping(BaseModel):
    """Mapping of CSV columns to lead fields."""
    csv_column: str
    lead_field: str


class CSVPreviewRow(BaseModel):
    """A preview row from the CSV."""
    data: Dict[str, Any]


class CSVPreviewResponse(BaseModel):
    """Response for CSV preview endpoint."""
    total_rows: int
    duplicate_count: int
    new_count: int
    preview_rows: List[Dict[str, Any]]
    detected_columns: List[str]
    column_mapping: Dict[str, str]
    status_breakdown: Dict[str, int]


class CSVImportRequest(BaseModel):
    """Request to execute CSV import."""
    campaign_name: str
    campaign_description: Optional[str] = None
    rows: List[Dict[str, Any]]
    column_mapping: Dict[str, str]


class CSVImportResponse(BaseModel):
    """Response for CSV import execution."""
    campaign_id: str
    campaign_name: str
    total_processed: int
    imported: int
    duplicates_skipped: int
    errors: int
    status_breakdown: Dict[str, int]
