"""
File utility functions
Naming conventions, path helpers, etc.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from app.core.config import get_storage_path


def generate_batch_id(partner_code: str, service_code: str) -> str:
    """
    Generate a unique batch ID
    
    Format: PARTNER_SERVICE_YYYYMMDD_HHMMSS
    
    Args:
        partner_code: Partner code
        service_code: Service code
    
    Returns:
        Unique batch ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{partner_code}_{service_code}_{timestamp}"


def get_period_folder(period_from, period_to) -> str:
    """
    Get folder name for a reconciliation period
    
    Args:
        period_from: Start date
        period_to: End date
    
    Returns:
        Folder name (YYYYMM format based on period_from)
    """
    if hasattr(period_from, 'strftime'):
        return period_from.strftime("%Y%m")
    return str(period_from)[:7].replace("-", "")


def get_upload_path_simple(batch_id: str) -> Path:
    """
    Get the upload path for a batch (simplified - just batch_id folder)
    
    Args:
        batch_id: Batch ID (already contains partner, service, date)
    
    Returns:
        Absolute Path object: storage/uploads/{batch_id}/
    """
    base = get_storage_path('uploads')
    path = base / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_export_path_simple(batch_id: str) -> Path:
    """
    Get the export path for a batch (simplified - just batch_id folder)
    
    Args:
        batch_id: Batch ID (already contains partner, service, date)
    
    Returns:
        Absolute Path object: storage/exports/{batch_id}/
    """
    base = get_storage_path('exports')
    path = base / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_batch_files(batch_id: str) -> dict:
    """
    Delete all files associated with a batch
    
    Args:
        batch_id: Batch ID
    
    Returns:
        Dict with cleanup results
    """
    result = {
        'uploads_deleted': False,
        'exports_deleted': False,
        'errors': []
    }
    
    # Delete uploads folder
    uploads_path = get_storage_path('uploads') / batch_id
    if uploads_path.exists():
        try:
            shutil.rmtree(uploads_path)
            result['uploads_deleted'] = True
        except Exception as e:
            result['errors'].append(f"Error deleting uploads: {str(e)}")
    
    # Delete exports folder
    exports_path = get_storage_path('exports') / batch_id
    if exports_path.exists():
        try:
            shutil.rmtree(exports_path)
            result['exports_deleted'] = True
        except Exception as e:
            result['errors'].append(f"Error deleting exports: {str(e)}")
    
    # Also check legacy paths (for backward compatibility)
    # Old structure: uploads/{partner}/{period}/{batch_id}/
    uploads_base = get_storage_path('uploads')
    for partner_dir in uploads_base.iterdir():
        if partner_dir.is_dir() and partner_dir.name != batch_id:
            for sub_dir in partner_dir.iterdir():
                if sub_dir.is_dir():
                    batch_path = sub_dir / batch_id
                    if batch_path.exists():
                        try:
                            shutil.rmtree(batch_path)
                            result['uploads_deleted'] = True
                        except Exception as e:
                            result['errors'].append(f"Error deleting legacy uploads: {str(e)}")
    
    return result


def list_orphan_folders(db_batch_ids: List[str]) -> dict:
    """
    Find folders that don't have corresponding batch in database
    
    Args:
        db_batch_ids: List of batch IDs that exist in database
    
    Returns:
        Dict with orphan folders info
    """
    orphans = {
        'uploads': [],
        'exports': [],
        'total_size_mb': 0
    }
    
    # Check uploads
    uploads_base = get_storage_path('uploads')
    if uploads_base.exists():
        for folder in uploads_base.iterdir():
            if folder.is_dir() and folder.name not in db_batch_ids:
                # Calculate size
                size = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
                orphans['uploads'].append({
                    'path': str(folder),
                    'name': folder.name,
                    'size_mb': round(size / 1024 / 1024, 2)
                })
                orphans['total_size_mb'] += size / 1024 / 1024
    
    # Check exports
    exports_base = get_storage_path('exports')
    if exports_base.exists():
        for folder in exports_base.iterdir():
            if folder.is_dir() and folder.name not in db_batch_ids:
                size = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
                orphans['exports'].append({
                    'path': str(folder),
                    'name': folder.name,
                    'size_mb': round(size / 1024 / 1024, 2)
                })
                orphans['total_size_mb'] += size / 1024 / 1024
    
    orphans['total_size_mb'] = round(orphans['total_size_mb'], 2)
    return orphans


def cleanup_orphan_folders(db_batch_ids: List[str]) -> dict:
    """
    Delete all orphan folders (folders without corresponding batch in DB)
    
    Args:
        db_batch_ids: List of batch IDs that exist in database
    
    Returns:
        Dict with cleanup results
    """
    orphans = list_orphan_folders(db_batch_ids)
    deleted = []
    errors = []
    
    for folder_info in orphans['uploads'] + orphans['exports']:
        try:
            shutil.rmtree(folder_info['path'])
            deleted.append(folder_info['name'])
        except Exception as e:
            errors.append(f"{folder_info['name']}: {str(e)}")
    
    return {
        'deleted': deleted,
        'deleted_count': len(deleted),
        'freed_mb': orphans['total_size_mb'],
        'errors': errors
    }


# Keep old functions for backward compatibility
def get_upload_path(partner_code: str, period: str, batch_id: str) -> Path:
    """
    Get the upload path for a batch
    
    Args:
        partner_code: Partner code
        period: Period folder (YYYYMM)
        batch_id: Batch ID
    
    Returns:
        Absolute Path object
    """
    base = get_storage_path('uploads')
    path = base / partner_code / period / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_processed_path(partner_code: str, period: str, batch_id: str) -> Path:
    """
    Get the processed files path for a batch
    
    Args:
        partner_code: Partner code
        period: Period folder (YYYYMM)
        batch_id: Batch ID
    
    Returns:
        Absolute Path object
    """
    base = get_storage_path('processed')
    path = base / partner_code / period / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_export_path(partner_code: str, period: str, batch_id: str) -> Path:
    """
    Get the export path for a batch
    
    Args:
        partner_code: Partner code
        period: Period folder (YYYYMM)
        batch_id: Batch ID
    
    Returns:
        Absolute Path object
    """
    base = get_storage_path('exports')
    path = base / partner_code / period / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing/replacing invalid characters
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = os.path.basename(filename)
    
    # Replace invalid characters with underscore
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200-len(ext)] + ext
    
    return filename


def generate_stored_filename(
    file_type: str,
    partner_code: str,
    service_code: str,
    period: str,
    batch_id: str,
    original_name: str,
    index: int = 0
) -> str:
    """
    Generate standardized filename for storage
    
    Format: {partner}_{service}_{file_type}_{period}_{batch}_{index}_{timestamp}.{ext}
    
    Args:
        file_type: Type of file (B1, B2, B3)
        partner_code: Partner code
        service_code: Service code
        period: Period (YYYYMM)
        batch_id: Batch ID
        original_name: Original filename
        index: File index (for multiple files)
    
    Returns:
        Standardized filename
    """
    # Get extension from original name
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    
    # Generate filename
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{partner_code}_{service_code}_{file_type}_{period}_{index:02d}_{timestamp}{ext}"
    
    return sanitize_filename(filename)


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension without dot"""
    _, ext = os.path.splitext(filename)
    return ext.lower().lstrip('.')


def is_excel_file(filename: str) -> bool:
    """Check if file is an Excel file"""
    ext = get_file_extension(filename)
    return ext in ('xlsx', 'xls', 'xlsm', 'xlsb')


def is_csv_file(filename: str) -> bool:
    """Check if file is a CSV file"""
    ext = get_file_extension(filename)
    return ext == 'csv'


def is_zip_file(filename: str) -> bool:
    """Check if file is a ZIP archive"""
    ext = get_file_extension(filename)
    return ext in ('zip', 'rar', '7z')


def is_supported_file(filename: str) -> bool:
    """Check if file type is supported"""
    return is_excel_file(filename) or is_csv_file(filename) or is_zip_file(filename)


def get_relative_path(absolute_path: Path, base_name: str = 'storage') -> str:
    """
    Convert absolute path to relative path from storage root
    
    Args:
        absolute_path: Absolute path
        base_name: Base folder name to start relative path from
    
    Returns:
        Relative path string
    """
    parts = absolute_path.parts
    try:
        idx = parts.index(base_name)
        return str(Path(*parts[idx:]))
    except ValueError:
        return str(absolute_path)


def get_batch_folder(partner_code: str, service_code: str, batch_id: str, period_from=None) -> Path:
    """
    Get the folder path for a specific batch
    
    SIMPLIFIED: Only uses batch_id as folder name since batch_id already contains
    partner_code, service_code, and date information.
    
    Structure: storage/uploads/{batch_id}/
    
    Args:
        partner_code: Partner code (kept for backward compatibility, not used)
        service_code: Service code (kept for backward compatibility, not used)
        batch_id: Batch ID (contains partner_service_date_time)
        period_from: Optional (kept for backward compatibility, not used)
    
    Returns:
        Absolute Path object to batch folder
    """
    base = get_storage_path('uploads')
    path = base / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_output_folder(partner_code: str, service_code: str, batch_id: str, period_from=None) -> Path:
    """
    Get the output folder path for a specific batch's results
    
    SIMPLIFIED: Only uses batch_id as folder name since batch_id already contains
    partner_code, service_code, and date information.
    
    Structure: storage/exports/{batch_id}/
    
    Args:
        partner_code: Partner code (kept for backward compatibility, not used)
        service_code: Service code (kept for backward compatibility, not used)
        batch_id: Batch ID (contains partner_service_date_time)
        period_from: Optional (kept for backward compatibility, not used)
    
    Returns:
        Absolute Path object to output folder
    """
    base = get_storage_path('exports')
    path = base / batch_id
    path.mkdir(parents=True, exist_ok=True)
    return path
