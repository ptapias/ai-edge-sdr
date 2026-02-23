"""
CSV Import router for uploading and importing leads from CSV files.
"""
import csv
import io
import logging
from typing import List, Dict, Any

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


@router.post("/preview", response_model=CSVPreviewResponse)
async def preview_csv_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file and preview the import.
    Returns detected column mapping, duplicate count, and sample rows.
    """
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        content = await file.read()
        text = content.decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))

        columns = reader.fieldnames or []
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        result = preview_import(db, rows, columns, current_user.id)
        return CSVPreviewResponse(**result)

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding not supported. Please use UTF-8.")
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")


@router.post("/execute", response_model=CSVImportResponse)
async def execute_csv_import(
    request: CSVImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute the CSV import: create campaign and lead records.
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
        logger.error(f"CSV import execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
