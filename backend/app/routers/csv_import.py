"""
CSV/Excel Import router for uploading and importing leads from files.
Supports CSV (.csv) and Excel (.xlsx, .xls) formats.
"""
import csv
import io
import logging
from typing import List, Dict, Any, Tuple

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..schemas.csv_import import CSVPreviewResponse, CSVImportRequest, CSVImportResponse
from ..services.csv_import_service import (
    preview_import,
    execute_import,
    detect_column_mapping,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/import", tags=["csv-import"])

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")


def parse_file_to_rows(filename: str, content: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse CSV or Excel file content into (columns, rows)."""
    lower = filename.lower()

    if lower.endswith(".csv"):
        text = content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))
        columns = reader.fieldnames or []
        rows = list(reader)
        return columns, rows

    elif lower.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="Excel support requires openpyxl. Please upload a CSV file instead.",
            )

        try:
            wb = openpyxl.load_workbook(
                io.BytesIO(content), read_only=True, data_only=True
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not open Excel file: {str(e)}",
            )

        ws = wb.active
        if not ws:
            wb.close()
            raise HTTPException(
                status_code=400, detail="Excel file has no active worksheet"
            )

        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not all_rows:
            raise HTTPException(status_code=400, detail="Excel file is empty")

        # First row = headers
        columns = [
            str(c).strip() if c is not None else f"Column_{i}"
            for i, c in enumerate(all_rows[0])
        ]

        # Remaining rows = data
        rows: List[Dict[str, Any]] = []
        for data_row in all_rows[1:]:
            row_dict: Dict[str, Any] = {}
            for i, col_name in enumerate(columns):
                val = data_row[i] if i < len(data_row) else None
                row_dict[col_name] = str(val).strip() if val is not None else ""
            # Skip completely empty rows
            if any(v for v in row_dict.values()):
                rows.append(row_dict)

        return columns, rows

    else:
        raise HTTPException(status_code=400, detail="Unsupported file format")


@router.post("/preview", response_model=CSVPreviewResponse)
async def preview_csv_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV or Excel file and preview the import.
    Returns detected column mapping, duplicate count, and sample rows.
    """
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV or Excel file (.csv, .xlsx, .xls)",
        )

    try:
        content = await file.read()
        columns, rows = parse_file_to_rows(file.filename, content)

        if not rows:
            raise HTTPException(
                status_code=400, detail="File is empty or contains no data rows"
            )

        result = preview_import(db, rows, columns, current_user.id)
        return CSVPreviewResponse(**result)

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding not supported. Please use UTF-8.",
        )
    except csv.Error as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid CSV format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error previewing file: {e}")
        raise HTTPException(
            status_code=400, detail=f"Could not parse file: {str(e)}"
        )


@router.post("/execute", response_model=CSVImportResponse)
async def execute_csv_import(
    request: CSVImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute the import: create campaign and lead records.
    Expects the parsed rows and column mapping from the preview step.
    """
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows to import")

    if not request.campaign_name:
        raise HTTPException(status_code=400, detail="Campaign name is required")

    try:
        result = execute_import(
            db=db,
            rows=request.rows,
            column_mapping=request.column_mapping,
            campaign_name=request.campaign_name,
            campaign_description=request.campaign_description,
            user_id=current_user.id,
        )
        return CSVImportResponse(**result)

    except Exception as e:
        logger.error(f"Import execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
