"""
Mock data management endpoints (V2)
Upload and manage mock CSV files for testing
"""

import os
import shutil
from typing import Any, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.core.config import get_storage_path
from app.models import User


router = APIRouter()


class MockFileInfo(BaseModel):
    """Mock file info response"""
    filename: str
    size: int
    partner_code: str
    service_code: str


class MockFileListResponse(BaseModel):
    """List of mock files"""
    files: List[MockFileInfo]


def parse_mock_filename(filename: str) -> tuple:
    """Parse mock filename to extract partner_code and service_code"""
    if not filename.endswith('_b4_mock.csv'):
        return None, None

    parts = filename.replace('_b4_mock.csv', '').split('_')
    if len(parts) >= 2:
        partner_code = parts[0]
        service_code = '_'.join(parts[1:])
        return partner_code, service_code
    return None, None


@router.get("/", response_model=MockFileListResponse)
async def list_mock_files(
    _: User = Depends(get_current_admin)
) -> Any:
    """List all mock CSV files (Admin only)"""
    mock_path = get_storage_path('mock_data')
    files = []

    for f in mock_path.glob('*.csv'):
        partner_code, service_code = parse_mock_filename(f.name)
        files.append(MockFileInfo(
            filename=f.name,
            size=f.stat().st_size,
            partner_code=partner_code or 'Unknown',
            service_code=service_code or 'Unknown'
        ))

    return MockFileListResponse(files=files)


@router.post("/upload")
async def upload_mock_file(
    partner_code: str = Query(..., description="Partner code (e.g., SACOMBANK)"),
    service_code: str = Query(..., description="Service code (e.g., TOPUP)"),
    file: UploadFile = File(...),
    _: User = Depends(get_current_admin)
) -> Any:
    """Upload a mock CSV file for testing (Admin only)"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )

    filename = f"{partner_code.upper()}_{service_code.upper()}_b4_mock.csv"
    mock_path = get_storage_path('mock_data') / filename

    try:
        with open(mock_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    file_size = mock_path.stat().st_size

    import pandas as pd
    try:
        df = pd.read_csv(mock_path, nrows=5)
        columns = list(df.columns)
        row_count = len(pd.read_csv(mock_path))
    except Exception:
        columns = []
        row_count = 0

    return {
        "message": "Mock file uploaded successfully",
        "filename": filename,
        "size": file_size,
        "columns": columns,
        "row_count": row_count,
        "partner_code": partner_code.upper(),
        "service_code": service_code.upper()
    }


@router.get("/download/{filename}")
async def download_mock_file(
    filename: str,
    _: User = Depends(get_current_admin)
) -> Any:
    """Download a mock CSV file (Admin only)"""
    mock_path = get_storage_path('mock_data') / filename

    if not mock_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock file not found"
        )

    return FileResponse(
        path=mock_path,
        filename=filename,
        media_type='text/csv'
    )


@router.get("/preview/{filename}")
async def preview_mock_file(
    filename: str,
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(get_current_admin)
) -> Any:
    """Preview contents of a mock CSV file (Admin only)"""
    mock_path = get_storage_path('mock_data') / filename

    if not mock_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock file not found"
        )

    import pandas as pd
    try:
        df = pd.read_csv(mock_path)
        total_rows = len(df)
        df_preview = df.head(limit)

        return {
            "filename": filename,
            "columns": list(df.columns),
            "total_rows": total_rows,
            "preview_rows": limit,
            "data": df_preview.to_dict(orient='records')
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )


@router.delete("/{filename}")
async def delete_mock_file(
    filename: str,
    _: User = Depends(get_current_admin)
) -> Any:
    """Delete a mock CSV file (Admin only)"""
    mock_path = get_storage_path('mock_data') / filename

    if not mock_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock file not found"
        )

    try:
        mock_path.unlink()
        return {"message": f"Mock file '{filename}' deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/columns/{partner_code}/{service_code}")
async def get_b4_columns(
    partner_code: str,
    service_code: str,
    _: User = Depends(get_current_admin)
) -> Any:
    """Get column names from mock B4 file for a partner/service (Admin only)"""
    filename = f"{partner_code.upper()}_{service_code.upper()}_b4_mock.csv"
    mock_path = get_storage_path('mock_data') / filename

    if not mock_path.exists():
        return {
            "exists": False,
            "filename": filename,
            "columns": []
        }

    import pandas as pd
    try:
        df = pd.read_csv(mock_path, nrows=1)
        return {
            "exists": True,
            "filename": filename,
            "columns": list(df.columns)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )
