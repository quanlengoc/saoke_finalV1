"""
Reconciliation Endpoints - V2
Run reconciliation using dynamic workflow
"""

import time
import uuid
import zipfile
import threading
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, joinedload
import os
import shutil
import logging

logger = logging.getLogger(__name__)

# Supported file extensions for upload
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.xlsb', '.csv', '.zip'}

from app.core.database import get_db
from app.core.config import get_settings
from app.api.deps import get_current_user
from app.models import (
    PartnerServiceConfig,
    DataSourceConfig,
    ReconciliationLog,
    BatchRunHistory,
    User,
    UserPermission,
)
from app.models.audit_log import AuditLog
from app.utils.step_log_file import (
    make_on_step_log_callback,
    write_step_logs,
    read_step_logs_from_path,
    get_log_file_path,
)
from app.schemas.v2.reconciliation import (
    ReconciliationRequest,
    ReconciliationResponse,
    ReconciliationStatus,
    FileUploadInfo,
    StepResult,
    OutputResult,
    ReconciliationList,
    ReconciliationListItem,
)
from app.services.workflow_executor import WorkflowExecutor
import pandas as pd
import json as json_lib

router = APIRouter()


def _generate_batch_id(partner_code: str, service_code: str) -> str:
    """Generate unique batch ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"{partner_code}_{service_code}_{timestamp}_{short_uuid}"


def _check_reconcile_permission(db: Session, user: User, partner_code: str, service_code: str):
    """Check if user has reconcile permission for the given partner/service.
    Admin bypasses all checks. Raises HTTPException if not permitted."""
    if user.is_admin:
        return
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.partner_code == partner_code,
        UserPermission.service_code == service_code,
        UserPermission.can_reconcile == True
    ).first()
    if not permission:
        raise HTTPException(
            status_code=403,
            detail=f"Bạn không có quyền đối soát cho {partner_code}/{service_code}"
        )


def _write_audit(db, user_id, user_email, action: str,
                 batch_id: str, old_status, new_status: str, summary: str):
    """Write an audit log entry for batch status transitions.
    Non-blocking: errors logged but don't fail the main action."""
    try:
        if not user_id:
            logger.warning(f"Skipping audit log: no user_id for batch {batch_id}")
            return
        log = AuditLog(
            user_id=user_id,
            user_email=user_email or "unknown",
            action=action,
            entity_type="BATCH",
            entity_id=batch_id,
            old_values={"status": old_status} if old_status else None,
            new_values={"status": new_status},
            summary=summary,
        )
        db.add(log)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def _export_outputs_and_build_stats(
    result, config, batch_id: str, executor
) -> dict:
    """
    Export output DataFrames to CSV files and build summary_stats.
    
    Returns dict with keys:
        - file_result_a1: path to A1 CSV (or None) [backward compat]
        - file_result_a2: path to A2 CSV (or None) [backward compat]
        - file_results: dict of {output_name: csv_path} for ALL outputs
        - summary_stats: dict with V1-compatible stats format
    """
    settings = get_settings()
    output_dir = os.path.join(settings.OUTPUT_PATH, config.partner_code, batch_id)
    os.makedirs(output_dir, exist_ok=True)
    
    file_result_a1 = None
    file_result_a2 = None
    file_results = {}  # All output file paths
    
    # Export each output DataFrame to CSV
    for output_name, df in result.outputs.items():
        if df.empty:
            continue
        
        csv_path = os.path.join(output_dir, f"{output_name}_{batch_id}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"Exported {output_name}: {len(df)} rows -> {csv_path}")
        
        # Store in dynamic dict
        file_results[output_name.upper()] = csv_path
        
        # Map common output names to legacy file_result fields
        # Use EXACT match only — "A1" not "A1_1"/"A1_2"
        upper_name = output_name.upper()
        if upper_name == "A1":
            file_result_a1 = csv_path
        elif upper_name == "A2":
            file_result_a2 = csv_path
    
    # Build summary_stats with V1-compatible format
    # NOTE: output_stats (filter_columns, by_ badges) are NOT stored in DB
    #       They are computed on-demand by the stats endpoint from CSV files
    #       This keeps summary_stats small and avoids bloating the DB column
    # Collect data source row counts from executor.datasets
    datasets = executor.datasets if executor else {}

    summary_stats = {}
    for ds in config.data_sources:
        key = f"total_{ds.source_name.lower()}"
        ds_df = datasets.get(ds.source_name.upper(), pd.DataFrame())
        # Handle None (skipped optional sources) and empty DataFrames
        summary_stats[key] = len(ds_df) if ds_df is not None else 0
    
    # Build matching_stats from workflow step results
    matching_stats = {}
    steps = sorted(config.workflow_steps, key=lambda s: s.step_order)
    for step in steps:
        left = step.left_source.lower()
        right = step.right_source.lower()
        step_key = f"{left}_{right}"
        
        # Get the result dataset for this step
        # After output config resolution, status column may be renamed
        step_df = datasets.get(step.output_name.upper(), pd.DataFrame())
        if not step_df.empty:
            # Find status column (may be 'status', 'match_status', etc.)
            status_col = None
            for col_name in ('status', 'match_status', 'Status'):
                if col_name in step_df.columns:
                    status_col = col_name
                    break
            
            if status_col:
                status_counts = step_df[status_col].value_counts().to_dict()
            else:
                status_counts = {}
            
            matching_stats[step_key] = {
                "total": len(step_df),
                "matched": status_counts.get("MATCHED", 0),
                "not_found": status_counts.get("NOT_FOUND", 0),
                "mismatch": status_counts.get("AMOUNT_MISMATCH", 0) + status_counts.get("MISMATCH", 0),
            }
    
    summary_stats["matching_stats"] = matching_stats
    
    # Also include V2-style output_details for ALL step outputs (including intermediate)
    # This avoids needing to save intermediate CSVs just for row counts
    summary_stats["output_details"] = {}
    for step in steps:
        step_df = datasets.get(step.output_name.upper(), pd.DataFrame())
        if not step_df.empty:
            status_counts = {}
            for col_name in ('status', 'match_status', 'Status'):
                if col_name in step_df.columns:
                    status_counts = step_df[col_name].value_counts().to_dict()
                    break
            summary_stats["output_details"][step.output_name] = {
                "row_count": len(step_df),
                "status_counts": {str(k): int(v) for k, v in status_counts.items()}
            }
    
    return {
        "file_result_a1": file_result_a1,
        "file_result_a2": file_result_a2,
        "file_results": file_results,
        "summary_stats": summary_stats,
    }


def _validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _get_file_type_label(filename: str) -> str:
    """Get human-readable file type label"""
    ext = os.path.splitext(filename)[1].lower()
    labels = {
        '.xlsx': 'Excel', '.xls': 'Excel', '.xlsb': 'Excel Binary',
        '.csv': 'CSV', '.zip': 'ZIP Archive'
    }
    return labels.get(ext, 'Unknown')


@router.post("/upload-files/{config_id}")
async def upload_files(
    config_id: int,
    files: List[UploadFile] = File(...),
    source_names: str = Form(...),  # Comma-separated: "B1,B4,B1,B3" (can repeat for multiple files per source)
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload files for reconciliation
    
    Supports:
    - Multiple files per source (same source_name can appear multiple times)
    - ZIP files (will be extracted automatically during processing)
    - Excel (.xlsx, .xls, .xlsb) and CSV files
    - Files will be merged per source before matching
    """
    # Verify config
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == config_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # Check reconcile permission
    _check_reconcile_permission(db, current_user, config.partner_code, config.service_code)

    source_name_list = [s.strip().upper() for s in source_names.split(",")]
    
    if len(files) != len(source_name_list):
        raise HTTPException(
            status_code=400,
            detail=f"Số lượng files ({len(files)}) phải bằng số lượng source names ({len(source_name_list)})"
        )
    
    # Validate file extensions
    invalid_files = []
    for file in files:
        if not _validate_file_extension(file.filename):
            invalid_files.append(file.filename)
    
    if invalid_files:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"File không hỗ trợ: {', '.join(invalid_files)}. Chỉ chấp nhận: {allowed}"
        )
    
    # Create upload directory
    settings = get_settings()
    batch_folder = f"{config.partner_code}_{config.service_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    upload_dir = os.path.join(settings.UPLOAD_PATH, config.partner_code, batch_folder)
    os.makedirs(upload_dir, exist_ok=True)
    
    uploaded_files = []
    source_file_counts = {}  # Track file count per source for unique naming
    
    # Validate all sources first
    validated_sources = {}
    for source_name in set(source_name_list):
        source_config = db.query(DataSourceConfig).filter(
            DataSourceConfig.config_id == config_id,
            DataSourceConfig.source_name == source_name
        ).first()
        
        if not source_config:
            raise HTTPException(
                status_code=400,
                detail=f"Nguồn dữ liệu '{source_name}' không tồn tại trong cấu hình"
            )
        
        if source_config.source_type != "FILE_UPLOAD":
            raise HTTPException(
                status_code=400,
                detail=f"Nguồn dữ liệu '{source_name}' không phải loại FILE_UPLOAD"
            )
        
        validated_sources[source_name] = source_config
    
    # Save files - create subfolder per source for multiple files
    for file, source_name in zip(files, source_name_list):
        # Create source-specific subfolder
        source_folder = os.path.join(upload_dir, source_name.lower())
        os.makedirs(source_folder, exist_ok=True)
        
        # Track file index for unique naming
        if source_name not in source_file_counts:
            source_file_counts[source_name] = 0
        file_index = source_file_counts[source_name]
        source_file_counts[source_name] += 1
        
        # Save file with index prefix for uniqueness
        file_path = os.path.join(source_folder, f"{file_index:03d}_{file.filename}")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        file_size = os.path.getsize(file_path)
        file_type = _get_file_type_label(file.filename)
        
        uploaded_files.append(FileUploadInfo(
            source_name=source_name,
            file_name=file.filename,
            file_path=file_path
        ))
        
        logger.info(f"Saved {source_name}/{file.filename} ({file_type}, {file_size} bytes)")
    
    # Summary by source
    files_by_source = {}
    for f in uploaded_files:
        if f.source_name not in files_by_source:
            files_by_source[f.source_name] = []
        files_by_source[f.source_name].append(f.file_name)
    
    logger.info(f"Upload complete: {len(uploaded_files)} files for {len(files_by_source)} sources")
    
    return {
        "message": "Upload thành công! Dữ liệu sẽ được ghép tự động khi chạy đối soát.",
        "batch_folder": batch_folder,
        "files": uploaded_files,
        "summary": {
            source: {
                "count": len(fnames), 
                "files": fnames,
                "will_merge": len(fnames) > 1 or any(fn.lower().endswith('.zip') for fn in fnames)
            }
            for source, fnames in files_by_source.items()
        }
    }


@router.post("/check-duplicate")
async def check_duplicate_batch(
    request: ReconciliationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if a duplicate batch exists for the same partner+service and overlapping period.
    Returns:
      - has_duplicate: bool
      - approved_conflict: bool (if duplicate is APPROVED, creation is blocked)
      - duplicates: list of conflicting batches
    """
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == request.config_id
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Find batches with same partner+service and overlapping period
    overlapping = db.query(ReconciliationLog).filter(
        ReconciliationLog.partner_code == config.partner_code,
        ReconciliationLog.service_code == config.service_code,
        ReconciliationLog.period_from <= request.period_to,
        ReconciliationLog.period_to >= request.period_from,
    ).all()
    
    if not overlapping:
        return {"has_duplicate": False, "approved_conflict": False, "duplicates": []}
    
    duplicates = []
    approved_conflict = False
    for b in overlapping:
        is_approved = b.status == "APPROVED"
        if is_approved:
            approved_conflict = True
        duplicates.append({
            "batch_id": b.batch_id,
            "status": b.status,
            "period_from": str(b.period_from),
            "period_to": str(b.period_to),
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    
    return {
        "has_duplicate": True,
        "approved_conflict": approved_conflict,
        "duplicates": duplicates,
    }


def _delete_batch_data(batch: ReconciliationLog, db: Session):
    """
    Delete a batch and all its associated files on disk.
    (uploaded files, exported results)
    """
    settings = get_settings()
    
    # Delete exported result files
    for file_path in [batch.file_result_a1, batch.file_result_a2, batch.file_report]:
        if file_path:
            try:
                full_path = os.path.join(settings.OUTPUT_PATH, file_path) if not os.path.isabs(file_path) else file_path
                if os.path.exists(full_path):
                    os.remove(full_path)
                    logger.info(f"Deleted export file: {full_path}")
            except Exception as e:
                logger.warning(f"Failed to delete export file {file_path}: {e}")
    
    # Delete uploaded files folder
    # files_uploaded JSON has {source_name: [file_paths]}
    if batch.files_uploaded:
        try:
            files_info = json_lib.loads(batch.files_uploaded)
            # Find the common parent folder (batch folder)
            all_paths = []
            for source_files in files_info.values():
                if isinstance(source_files, list):
                    all_paths.extend(source_files)
            
            if all_paths:
                # Walk up to find the batch upload folder
                first_file = all_paths[0]
                # Structure: .../uploads/PARTNER/batch_folder/source_name/file
                source_dir = os.path.dirname(first_file)
                batch_dir = os.path.dirname(source_dir)
                if os.path.isdir(batch_dir):
                    shutil.rmtree(batch_dir, ignore_errors=True)
                    logger.info(f"Deleted upload folder: {batch_dir}")
        except Exception as e:
            logger.warning(f"Failed to delete upload files for {batch.batch_id}: {e}")
    
    # Delete the DB record
    db.delete(batch)
    db.flush()
    logger.info(f"Deleted batch record: {batch.batch_id}")


@router.delete("/batches/{batch_id}")
async def delete_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a batch and all its associated data (files, exports, DB record)"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Check reconcile permission
    _check_reconcile_permission(db, current_user, batch.partner_code, batch.service_code)

    if batch.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Không thể xóa batch đã được phê duyệt")

    _delete_batch_data(batch, db)
    db.commit()
    
    return {"message": f"Đã xóa batch {batch_id} và toàn bộ dữ liệu liên quan"}


@router.post("/{batch_id}/stop")
async def stop_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stop a running batch (PROCESSING status)"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Check reconcile permission
    _check_reconcile_permission(db, current_user, batch.partner_code, batch.service_code)

    if batch.status != "PROCESSING":
        raise HTTPException(status_code=400,
                          detail=f"Chỉ có thể dừng batch ở trạng thái PROCESSING, batch hiện tại: {batch.status}")

    # Mark batch for cancellation in WorkflowExecutor
    WorkflowExecutor.cancel_batch(batch_id)
    
    # Update batch status to CANCELLED
    batch.status = "CANCELLED"
    batch.error_message = "Batch was cancelled by user"
    batch.updated_at = datetime.utcnow()

    # Audit log: user stopped batch
    _write_audit(db, current_user.id, current_user.email, "STOP",
                 batch_id, "PROCESSING", "CANCELLED",
                 f"Dừng đối soát batch {batch_id}")

    db.commit()

    return {
        "message": f"Batch {batch_id} đã được dừng",
        "status": "CANCELLED"
    }


def _run_workflow_in_background(batch_id: str, config_id: int, file_paths: dict,
                                files_uploaded_info: dict, period_from, period_to,
                                cycle_params: dict = None, run_number: int = 1,
                                triggered_by: str = 'initial'):
    """
    Execute workflow in a background thread.
    
    Step logs are written to FILE (not DB) via make_on_step_log_callback.
    A BatchRunHistory row tracks this execution attempt.
    Only the final status update touches the DB (once, at the end).
    """
    from app.core.database import DatabaseManager
    from app.models import PartnerServiceConfig, ReconciliationLog, BatchRunHistory, User

    SessionLocal = DatabaseManager.get_session_factory('app')
    bg_db = SessionLocal()

    # Get batch creator info for audit logs
    batch_record = bg_db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    creator = bg_db.query(User).filter(User.id == batch_record.created_by).first() if batch_record else None
    audit_user_id = creator.id if creator else None
    audit_user_email = creator.email if creator else "system"
    
    log_file_rel = get_log_file_path(batch_id, run_number)
    
    try:
        config = bg_db.query(PartnerServiceConfig).filter(
            PartnerServiceConfig.id == config_id
        ).first()
        
        if not config:
            logger.error(f"[workflow_bg] config not found: config_id={config_id}")
            return
        
        start_time = time.time()
        
        # on_step_log callback writes to FILE, not DB
        on_step_log = make_on_step_log_callback(batch_id, run_number)
        
        # Build cycle_params with date_from/date_to from period
        effective_cycle_params = dict(cycle_params or {})
        if 'date_from' not in effective_cycle_params:
            effective_cycle_params['date_from'] = str(period_from) if period_from else ''
        if 'date_to' not in effective_cycle_params:
            effective_cycle_params['date_to'] = str(period_to) if period_to else ''

        # Create workflow executor
        executor = WorkflowExecutor(
            config=config,
            batch_id=batch_id,
            file_paths=file_paths,
            cycle_params=effective_cycle_params,
            on_step_log=on_step_log,
        )
        
        # Execute workflow
        result = executor.execute()
        
        total_time = time.time() - start_time
        
        # Write final logs to file (includes all steps)
        write_step_logs(batch_id, run_number, result.step_logs)
        
        # Use a fresh session for final DB updates (single write)
        final_db = SessionLocal()
        try:
            if not result.success:
                # Update batch status
                final_db.query(ReconciliationLog).filter(
                    ReconciliationLog.batch_id == batch_id
                ).update({
                    ReconciliationLog.status: "ERROR",
                    ReconciliationLog.error_message: result.error_message or "Workflow execution failed",
                    ReconciliationLog.step_logs: log_file_rel,
                })
                # Update run history
                final_db.query(BatchRunHistory).filter(
                    BatchRunHistory.batch_id == batch_id,
                    BatchRunHistory.run_number == run_number,
                ).update({
                    BatchRunHistory.status: "ERROR",
                    BatchRunHistory.completed_at: datetime.utcnow(),
                    BatchRunHistory.duration_seconds: total_time,
                    BatchRunHistory.error_message: result.error_message,
                    BatchRunHistory.log_file_path: log_file_rel,
                })
                # Audit log: workflow failed
                _write_audit(final_db, audit_user_id, audit_user_email, "STATUS_CHANGE",
                             batch_id, "PROCESSING", "ERROR",
                             f"Lỗi đối soát: {result.error_message or 'Unknown error'}")
                final_db.commit()
                logger.error(f"[workflow_bg] Workflow failed: {result.error_message}")
                return
            
            # Export outputs and build stats
            export_info = _export_outputs_and_build_stats(result, config, batch_id, executor)
            summary_json = json_lib.dumps(export_info["summary_stats"], ensure_ascii=False)
            file_results_json = json_lib.dumps(export_info["file_results"])
            
            # Update batch record (single DB write)
            final_db.query(ReconciliationLog).filter(
                ReconciliationLog.batch_id == batch_id
            ).update({
                ReconciliationLog.status: "COMPLETED",
                ReconciliationLog.error_message: None,
                ReconciliationLog.step_logs: log_file_rel,
                ReconciliationLog.summary_stats: summary_json,
                ReconciliationLog.file_result_a1: export_info["file_result_a1"],
                ReconciliationLog.file_result_a2: export_info["file_result_a2"],
                ReconciliationLog.file_results: file_results_json,
            })
            # Update run history
            final_db.query(BatchRunHistory).filter(
                BatchRunHistory.batch_id == batch_id,
                BatchRunHistory.run_number == run_number,
            ).update({
                BatchRunHistory.status: "COMPLETED",
                BatchRunHistory.completed_at: datetime.utcnow(),
                BatchRunHistory.duration_seconds: total_time,
                BatchRunHistory.log_file_path: log_file_rel,
                BatchRunHistory.summary_stats: summary_json,
                BatchRunHistory.file_results: file_results_json,
            })
            # Audit log: workflow completed
            _write_audit(final_db, audit_user_id, audit_user_email, "STATUS_CHANGE",
                         batch_id, "PROCESSING", "COMPLETED",
                         f"Hoàn tất đối soát ({total_time:.1f}s)")
            final_db.commit()

            logger.info(f"[workflow_bg] Workflow completed in {total_time:.2f}s for {batch_id}")
        finally:
            final_db.close()
        
    except Exception as e:
        logger.exception(f"[workflow_bg] Unexpected error for {batch_id}: {e}")
        err_db = None
        try:
            err_db = SessionLocal()
            
            # Check if this was a user cancellation
            is_cancelled = "cancelled" in str(e).lower()
            status = "CANCELLED" if is_cancelled else "ERROR"
            
            err_db.query(ReconciliationLog).filter(
                ReconciliationLog.batch_id == batch_id
            ).update({
                ReconciliationLog.status: status,
                ReconciliationLog.error_message: str(e),
                ReconciliationLog.step_logs: log_file_rel,
            })
            err_db.query(BatchRunHistory).filter(
                BatchRunHistory.batch_id == batch_id,
                BatchRunHistory.run_number == run_number,
            ).update({
                BatchRunHistory.status: status,
                BatchRunHistory.completed_at: datetime.utcnow(),
                BatchRunHistory.error_message: str(e),
                BatchRunHistory.log_file_path: log_file_rel,
            })
            # Audit log: error/cancellation
            summary = "Tạm dừng đối soát" if is_cancelled else f"Lỗi đối soát: {str(e)[:200]}"
            _write_audit(err_db, audit_user_id, audit_user_email, "STATUS_CHANGE",
                         batch_id, "PROCESSING", status, summary)
            err_db.commit()
            
            # Reset cancellation flag after handling
            if is_cancelled:
                WorkflowExecutor.reset_cancellation(batch_id)
        except:
            if err_db:
                try:
                    err_db.rollback()
                except:
                    pass
        finally:
            if err_db:
                try:
                    err_db.close()
                except:
                    pass
    finally:
        bg_db.close()


@router.post("/run")
async def run_reconciliation(
    request: ReconciliationRequest,
    batch_folder: str = Query(..., description="Folder from upload-files"),
    force_replace: bool = Query(False, description="Force replace duplicate unapproved batches"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run reconciliation process.
    Creates a batch record with PROCESSING status and launches workflow in background.
    Frontend should redirect to batch detail page to see live progress.
    """
    # Get config
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == request.config_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # Check reconcile permission
    _check_reconcile_permission(db, current_user, config.partner_code, config.service_code)

    # Check for duplicate batches (same partner+service + overlapping period)
    overlapping = db.query(ReconciliationLog).filter(
        ReconciliationLog.partner_code == config.partner_code,
        ReconciliationLog.service_code == config.service_code,
        ReconciliationLog.period_from <= request.period_to,
        ReconciliationLog.period_to >= request.period_from,
    ).all()
    
    if overlapping:
        # Check if any are APPROVED → block
        approved = [b for b in overlapping if b.status == "APPROVED"]
        if approved:
            raise HTTPException(
                status_code=409,
                detail=f"Đã tồn tại batch được phê duyệt cho khoảng thời gian trùng lặp: "
                       f"{approved[0].batch_id}. Không thể tạo batch mới."
            )
        
        # Unapproved duplicates exist
        if not force_replace:
            raise HTTPException(
                status_code=409,
                detail={
                    "type": "duplicate_warning",
                    "message": f"Đã tồn tại {len(overlapping)} batch chưa duyệt cho khoảng thời gian trùng lặp.",
                    "duplicates": [
                        {"batch_id": b.batch_id, "status": b.status,
                         "period_from": str(b.period_from), "period_to": str(b.period_to)}
                        for b in overlapping
                    ]
                }
            )
        
        # force_replace=True → delete old unapproved batches
        # Use retry logic to handle SQLite lock contention from background threads
        max_retries = 3
        for attempt in range(max_retries):
            try:
                for old_batch in overlapping:
                    logger.info(f"Force replacing batch {old_batch.batch_id} (status={old_batch.status})")
                    _delete_batch_data(old_batch, db)
                db.commit()
                logger.info(f"Deleted {len(overlapping)} duplicate batches")
                break
            except Exception as e:
                db.rollback()
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt+1}/{max_retries} for force_replace due to: {e}")
                    import asyncio
                    await asyncio.sleep(1.0 * (attempt + 1))
                    # Re-query overlapping batches since we rolled back
                    overlapping = db.query(ReconciliationLog).filter(
                        ReconciliationLog.partner_code == config.partner_code,
                        ReconciliationLog.service_code == config.service_code,
                        ReconciliationLog.period_from <= request.period_to,
                        ReconciliationLog.period_to >= request.period_from,
                        ReconciliationLog.status != "APPROVED",
                    ).all()
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Không thể xóa batch cũ do database đang bận. Vui lòng thử lại sau. ({e})"
                    )
    
    batch_id = _generate_batch_id(config.partner_code, config.service_code)
    
    # Build file paths mapping for FILE_UPLOAD sources
    settings = get_settings()
    upload_dir = os.path.join(settings.UPLOAD_PATH, config.partner_code, batch_folder)
    
    file_paths = {}
    # Build compact upload_info: {batch_folder, sources: {name: {folder, file_count}}}
    upload_sources = {}
    for source in config.data_sources:
        if source.source_type == "FILE_UPLOAD":
            source_folder = os.path.join(upload_dir, source.source_name.lower())
            if os.path.isdir(source_folder):
                file_paths[source.source_name] = source_folder
                file_count = len([f for f in os.listdir(source_folder) if os.path.isfile(os.path.join(source_folder, f))])
                upload_sources[source.source_name] = {
                    "folder": source.source_name.lower(),
                    "file_count": file_count
                }
            else:
                for filename in os.listdir(upload_dir):
                    if filename.startswith(source.source_name + "_"):
                        fpath = os.path.join(upload_dir, filename)
                        file_paths[source.source_name] = fpath
                        upload_sources[source.source_name] = {
                            "folder": "",
                            "file_count": 1
                        }
                        break
    
    upload_info = {
        "batch_folder": batch_folder,
        "sources": upload_sources
    }
    
    # Create batch record immediately with PROCESSING status
    batch = ReconciliationLog(
        batch_id=batch_id,
        config_id=config.id,
        partner_code=config.partner_code,
        service_code=config.service_code,
        period_from=request.period_from,
        period_to=request.period_to,
        status="PROCESSING",
        created_by=current_user.id,
        files_uploaded=json_lib.dumps(upload_info, ensure_ascii=False),
        step_logs="",  # Will be set to file path by background thread
    )
    
    # Create first run history record
    run_history = BatchRunHistory(
        batch_id=batch_id,
        run_number=1,
        triggered_by="initial",
        status="PROCESSING",
        started_at=datetime.utcnow(),
        log_file_path=get_log_file_path(batch_id, 1),
    )
    
    db.add(batch)
    db.add(run_history)

    # Audit log: batch created
    _write_audit(db, current_user.id, current_user.email, "CREATE",
                 batch_id, None, "PROCESSING",
                 f"Tạo batch đối soát {config.partner_code}/{config.service_code}")

    # Retry commit in case of SQLite lock contention
    for attempt in range(3):
        try:
            db.commit()
            break
        except Exception as e:
            db.rollback()
            if attempt < 2:
                logger.warning(f"Retry {attempt+1}/3 creating batch due to: {e}")
                import asyncio
                await asyncio.sleep(1.0 * (attempt + 1))
                # Re-add since rollback may have removed it
                db.add(batch)
                db.add(run_history)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Không thể tạo batch do database đang bận. Vui lòng thử lại sau."
                )
    
    # Launch workflow in background thread
    thread = threading.Thread(
        target=_run_workflow_in_background,
        args=(batch_id, config.id, file_paths, upload_info,
              request.period_from, request.period_to, request.cycle_params,
              1, 'initial'),
        daemon=True,
        name=f"run-{batch_id}"
    )
    thread.start()
    
    return {
        "batch_id": batch_id,
        "config_id": config.id,
        "partner_code": config.partner_code,
        "service_code": config.service_code,
        "status": "PROCESSING",
        "message": "Đang thực hiện đối soát...",
    }


@router.get("/batches", response_model=ReconciliationList)
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    partner_code: Optional[str] = None,
    service_code: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List reconciliation batches with filtering.
    - Admin: sees all batches
    - User with approve permission: sees own batches + batches for permitted partner/service
    - Regular user: sees only batches they created
    """
    logger.info(f"[list_batches] user={current_user.email} id={current_user.id} is_admin={current_user.is_admin}")

    query = db.query(ReconciliationLog).options(
        joinedload(ReconciliationLog.creator),
        joinedload(ReconciliationLog.approver),
    )

    if not current_user.is_admin:
        # Check if user has any approve permissions
        approve_permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_approve == True
        ).all()

        if approve_permissions:
            # Approver: sees own batches + batches they can approve
            from sqlalchemy import or_, and_
            approved_pairs = [
                and_(
                    ReconciliationLog.partner_code == p.partner_code,
                    ReconciliationLog.service_code == p.service_code
                )
                for p in approve_permissions
            ]
            query = query.filter(
                or_(
                    ReconciliationLog.created_by == current_user.id,
                    *approved_pairs
                )
            )
        else:
            # Regular user: only own batches
            query = query.filter(ReconciliationLog.created_by == current_user.id)

    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)
    if status:
        query = query.filter(ReconciliationLog.status == status)
    
    total = query.count()
    batches = query.order_by(ReconciliationLog.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    items = []
    for b in batches:
        try:
            batch_status = ReconciliationStatus(b.status)
        except ValueError:
            batch_status = b.status  # fallback raw string for unknown statuses
        items.append(
            ReconciliationListItem(
                batch_id=b.batch_id,
                config_id=b.config_id,
                partner_code=b.partner_code,
                service_code=b.service_code,
                period_from=b.period_from,
                period_to=b.period_to,
                status=batch_status,
                error_message=b.error_message,
                created_by_name=b.creator.full_name if b.creator else "Unknown",
                created_at=b.created_at,
                approved_by_name=b.approver.full_name if b.approver else None,
                approved_at=b.approved_at
            )
        )
    
    return ReconciliationList(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/batches/{batch_id}")
async def get_batch_detail(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get batch detail with results, including config data sources info"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Parse JSON fields
    files_uploaded = {}
    if batch.files_uploaded:
        try:
            files_uploaded = json_lib.loads(batch.files_uploaded) if isinstance(batch.files_uploaded, str) else batch.files_uploaded
        except:
            files_uploaded = {}
    
    # Read step_logs from FILE (not DB JSON)
    # step_logs column now stores a file path like "logs/batches/.../run_1.json"
    # For backward compat, also handles legacy JSON array strings
    log_source = batch.step_logs or ""

    # During PROCESSING, batch.step_logs may be empty but log file is being written
    # Look up the log file path from the latest BatchRunHistory
    if not log_source.strip() and batch.status == "PROCESSING":
        latest_run = db.query(BatchRunHistory).filter(
            BatchRunHistory.batch_id == batch_id
        ).order_by(BatchRunHistory.run_number.desc()).first()
        if latest_run and latest_run.log_file_path:
            log_source = latest_run.log_file_path
        else:
            # Fallback: try to read from default run_1 path
            from app.utils.step_log_file import get_log_file_path as _get_log_path
            log_source = _get_log_path(batch_id, 1)

    step_logs = read_step_logs_from_path(log_source)
    
    summary_stats = {}
    if batch.summary_stats:
        try:
            summary_stats = json_lib.loads(batch.summary_stats) if isinstance(batch.summary_stats, str) else batch.summary_stats
        except:
            summary_stats = {}
    
    # Get data sources from config for dynamic display
    data_sources_info = []
    if batch.config_id:
        config = db.query(PartnerServiceConfig).filter(
            PartnerServiceConfig.id == batch.config_id
        ).first()
        if config:
            for ds in sorted(config.data_sources, key=lambda x: x.display_order or 0):
                # Support both old format (list of file paths) and new format (compact)
                if "sources" in files_uploaded:
                    # New compact format
                    src_info = files_uploaded.get("sources", {}).get(ds.source_name, {})
                    file_count = src_info.get("file_count", 0)
                    file_names = [f"{file_count} file(s)"] if file_count > 0 else []
                else:
                    # Legacy format: {source_name: [file_paths]}
                    ds_files = files_uploaded.get(ds.source_name, [])
                    file_names = []
                    for f in ds_files:
                        if isinstance(f, str):
                            file_names.append(os.path.basename(f))
                        else:
                            file_names.append(str(f))
                
                data_sources_info.append({
                    "source_name": ds.source_name,
                    "display_name": ds.display_name,
                    "source_type": ds.source_type,
                    "is_required": ds.is_required,
                    "files": file_names,
                })
    
    # Build run history
    run_history_list = []
    runs = db.query(BatchRunHistory).filter(
        BatchRunHistory.batch_id == batch_id
    ).order_by(BatchRunHistory.run_number.desc()).all()
    for run in runs:
        run_history_list.append({
            "run_number": run.run_number,
            "triggered_by": run.triggered_by,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "error_message": run.error_message,
            "log_file_path": run.log_file_path,
        })
    
    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "config_id": batch.config_id,
        "partner_code": batch.partner_code,
        "service_code": batch.service_code,
        "period_from": batch.period_from.isoformat() if batch.period_from else None,
        "period_to": batch.period_to.isoformat() if batch.period_to else None,
        "status": batch.status,
        "error_message": batch.error_message,
        "files_uploaded": files_uploaded,
        "data_sources": data_sources_info,
        "step_logs": step_logs,
        "summary_stats": summary_stats,
        "run_history": run_history_list,
        "file_result_a1": batch.file_result_a1,
        "file_result_a2": batch.file_result_a2,
        "file_report": batch.file_report,
        "created_by": batch.created_by,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "approved_by": batch.approved_by,
        "approved_at": batch.approved_at.isoformat() if batch.approved_at else None,
        "is_locked": batch.is_locked,
    }


@router.get("/batches/{batch_id}/runs/{run_number}/logs")
async def get_run_logs(
    batch_id: str,
    run_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get step logs for a specific run of a batch."""
    run = db.query(BatchRunHistory).filter(
        BatchRunHistory.batch_id == batch_id,
        BatchRunHistory.run_number == run_number,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    logs = read_step_logs_from_path(run.log_file_path) if run.log_file_path else []
    return {
        "run_number": run.run_number,
        "triggered_by": run.triggered_by,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds,
        "error_message": run.error_message,
        "step_logs": logs,
    }


# _run_rerun_in_background removed — unified into _run_workflow_in_background above


@router.post("/batches/{batch_id}/rerun")
async def rerun_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run reconciliation for a failed/errored batch using existing uploaded files.
    Uses the V2 WorkflowExecutor for dynamic workflow execution.
    Returns immediately with PROCESSING status; frontend polls for progress.
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Check reconcile permission
    _check_reconcile_permission(db, current_user, batch.partner_code, batch.service_code)

    # Only allow rerun from: COMPLETED, ERROR, CANCELLED
    allowed = ['COMPLETED', 'ERROR', 'CANCELLED', 'UPLOADING']
    if batch.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể chạy lại batch ở trạng thái {batch.status}"
        )
    
    # Get config
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == batch.config_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu hình đối soát")
    
    # Rebuild file_paths from files_uploaded (supports both old & new format)
    files_uploaded_raw = batch.files_uploaded or '{}'
    try:
        files_uploaded = json_lib.loads(files_uploaded_raw) if isinstance(files_uploaded_raw, str) else (files_uploaded_raw or {})
    except:
        files_uploaded = {}
    
    if not files_uploaded:
        raise HTTPException(
            status_code=400, 
            detail="Không tìm thấy thông tin file đã upload. Vui lòng tạo batch mới."
        )
    
    # Build file_paths mapping: source_name -> folder or file path
    settings = get_settings()
    file_paths = {}
    
    if "batch_folder" in files_uploaded:
        # NEW compact format: {batch_folder, sources: {name: {folder, file_count}}}
        batch_folder = files_uploaded["batch_folder"]
        upload_dir = os.path.join(settings.UPLOAD_PATH, batch.partner_code, batch_folder)
        sources = files_uploaded.get("sources", {})
        for source in config.data_sources:
            if source.source_type == "FILE_UPLOAD":
                src_info = sources.get(source.source_name, {})
                folder_name = src_info.get("folder", source.source_name.lower())
                source_folder = os.path.join(upload_dir, folder_name)
                if os.path.isdir(source_folder):
                    file_paths[source.source_name] = source_folder
    else:
        # LEGACY format: {source_name: [file_paths]}
        for source in config.data_sources:
            if source.source_type == "FILE_UPLOAD":
                source_files = files_uploaded.get(source.source_name, [])
                if source_files and len(source_files) > 0:
                    first_file = source_files[0]
                    folder = os.path.dirname(first_file)
                    if os.path.isdir(folder):
                        file_paths[source.source_name] = folder
                    elif os.path.isfile(first_file):
                        file_paths[source.source_name] = first_file
    
    # Determine next run number
    max_run = db.query(BatchRunHistory).filter(
        BatchRunHistory.batch_id == batch_id
    ).count()
    next_run = max_run + 1
    
    # Create run history record
    run_history = BatchRunHistory(
        batch_id=batch_id,
        run_number=next_run,
        triggered_by="rerun",
        status="PROCESSING",
        started_at=datetime.utcnow(),
        log_file_path=get_log_file_path(batch_id, next_run),
    )
    
    # Update status to PROCESSING immediately
    old_status = batch.status
    batch.status = "PROCESSING"
    batch.error_message = None
    batch.step_logs = ""  # Will be set to file path by background thread
    db.add(run_history)

    # Audit log: user rerun batch
    _write_audit(db, current_user.id, current_user.email, "RERUN",
                 batch_id, old_status, "PROCESSING",
                 f"Chạy lại đối soát batch {batch_id} (lần {next_run})")

    db.commit()
    
    # Launch workflow execution in a background thread
    thread = threading.Thread(
        target=_run_workflow_in_background,
        args=(batch.batch_id, batch.config_id, file_paths, {},
              batch.period_from, batch.period_to, None,
              next_run, 'rerun'),
        daemon=True,
        name=f"rerun-{batch.batch_id}"
    )
    thread.start()
    
    return {
        "batch_id": batch.batch_id,
        "status": "PROCESSING",
        "run_number": next_run,
        "message": f"Đang chạy lại đối soát (lần {next_run})...",
    }
