"""
Reconciliation endpoints
Upload files, run reconciliation, get status and results
"""

import os
import shutil
import traceback
import logging
from typing import Any, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.core.exceptions import ReconciliationException, MatchingError
from app.models import User, PartnerServiceConfig, ReconciliationLog, UserPermission
from app.schemas.reconciliation import (
    ReconciliationRequest, ReconciliationResponse, ReconciliationStatus,
    BatchListResponse, BatchDetailResponse
)
from app.services.file_processor import FileProcessor
from app.services.data_loader import DataLoader
from app.services.reconciliation_engine import ReconciliationEngine
from app.services.workflow_service import WorkflowService
from app.utils.file_utils import get_batch_folder, get_output_folder, cleanup_batch_files, list_orphan_folders, cleanup_orphan_folders

logger = logging.getLogger(__name__)

router = APIRouter()


def check_user_permission(
    user: User,
    partner_code: str,
    service_code: str,
    action: str,
    db: Session
) -> bool:
    """Check if user has permission for partner/service"""
    if user.is_admin:
        return True
    
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.partner_code == partner_code,
        UserPermission.service_code == service_code
    ).first()
    
    if not permission:
        return False
    
    if action == "reconcile":
        return permission.can_reconcile
    elif action == "approve":
        return permission.can_approve
    
    return False


def _build_matching_config(config: PartnerServiceConfig) -> dict:
    """Build matching_config dict from database config"""
    import json
    
    def parse_json(value):
        if value is None:
            return {}
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return value if isinstance(value, dict) else {}
    
    return {
        "b1_b4": parse_json(config.matching_rules_b1b4),
        "b1_b2": parse_json(config.matching_rules_b1b2),
        "a1_b3": parse_json(config.matching_rules_b3a1),
        "status_combine": parse_json(config.status_combine_rules),
        "output_columns": parse_json(config.output_a1_config),
        "a2_output": parse_json(config.output_a2_config),
    }


@router.post("/upload", response_model=ReconciliationResponse)
async def upload_and_reconcile(
    partner_code: str = Form(...),
    service_code: str = Form(...),
    date_from: date = Form(...),
    date_to: date = Form(...),
    files_b1: List[UploadFile] = File(...),
    files_b2: List[UploadFile] = File(default=[]),
    files_b3: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload files and run reconciliation
    
    - date_from, date_to: Reconciliation period
    - files_b1: Bank statement(s) (required, multiple allowed)
    - files_b2: Refund data (optional, multiple allowed)
    - files_b3: Partner details (optional, multiple allowed)
    
    Returns batch info and reconciliation results
    """
    # Check permission
    if not check_user_permission(current_user, partner_code, service_code, "reconcile", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission for this partner/service"
        )
    
    # Get configuration (use date_from for config lookup)
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.partner_code == partner_code,
        PartnerServiceConfig.service_code == service_code,
        PartnerServiceConfig.is_active == True,
        PartnerServiceConfig.valid_from <= date_from,
        (PartnerServiceConfig.valid_to >= date_from) | (PartnerServiceConfig.valid_to == None)
    ).order_by(PartnerServiceConfig.valid_from.desc()).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active configuration found for {partner_code}/{service_code} on {date_from}"
        )
    
    settings = get_settings()
    workflow = WorkflowService(db)
    
    try:
        # Generate batch_id
        from datetime import datetime
        batch_id = f"{partner_code}_{service_code}_{date_from.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
        
        # Create batch with config_id
        batch = workflow.create_batch(
            batch_id=batch_id,
            partner_code=partner_code,
            service_code=service_code,
            period_from=date_from,
            period_to=date_to,
            created_by=current_user.id,
            config_id=config.id  # Store reference to applied config
        )
        
        batch_folder = get_batch_folder(partner_code, service_code, batch.batch_id)
        os.makedirs(batch_folder, exist_ok=True)
        
        # Save uploaded files (support multiple files per type)
        file_paths = {"b1": [], "b2": [], "b3": []}
        
        # Save B1 files
        for idx, file_b1 in enumerate(files_b1):
            b1_path = os.path.join(batch_folder, f"B1_{idx+1}_{file_b1.filename}")
            with open(b1_path, "wb") as f:
                shutil.copyfileobj(file_b1.file, f)
            file_paths["b1"].append(b1_path)
        
        # Save B2 files if provided
        for idx, file_b2 in enumerate(files_b2):
            if file_b2.filename:  # Skip empty uploads
                b2_path = os.path.join(batch_folder, f"B2_{idx+1}_{file_b2.filename}")
                with open(b2_path, "wb") as f:
                    shutil.copyfileobj(file_b2.file, f)
                file_paths["b2"].append(b2_path)
        
        # Save B3 files if provided
        for idx, file_b3 in enumerate(files_b3):
            if file_b3.filename:  # Skip empty uploads
                b3_path = os.path.join(batch_folder, f"B3_{idx+1}_{file_b3.filename}")
                with open(b3_path, "wb") as f:
                    shutil.copyfileobj(file_b3.file, f)
                file_paths["b3"].append(b3_path)
        
        # Update batch with file paths - lưu vào files_uploaded dạng JSON string
        import json
        batch.files_uploaded = json.dumps(file_paths)
        db.commit()  # Commit ngay sau khi lưu file để đảm bảo batch được lưu
        db.refresh(batch)
        
        # Update status to processing
        workflow.update_status(batch.batch_id, "PROCESSING", "Bắt đầu xử lý đối soát")
        
        # Step 1: Process files (support multiple files per type)
        workflow.add_step_log(batch.batch_id, "FILE_PROCESS", "PROCESSING", "Đang xử lý file upload...")
        
        file_processor = FileProcessor(
            partner_code=partner_code,
            service_code=service_code,
            period_from=date_from,
            period_to=date_to,
            batch_id=batch.batch_id
        )
        
        # Parse file configs from database config
        import json
        def parse_file_config(config_str):
            if not config_str:
                return {"header_row": 1, "data_start_row": 2}
            try:
                return json.loads(config_str) if isinstance(config_str, str) else config_str
            except json.JSONDecodeError:
                return {"header_row": 1, "data_start_row": 2}
        
        b1_file_config = parse_file_config(config.file_b1_config)
        b2_file_config = parse_file_config(config.file_b2_config)
        b3_file_config = parse_file_config(config.file_b3_config)
        
        # Process and merge B1 files
        import pandas as pd
        df_b1_list = []
        for b1_path in file_paths["b1"]:
            df = file_processor.process_file(b1_path, "b1", b1_file_config)
            df_b1_list.append(df)
        df_b1 = pd.concat(df_b1_list, ignore_index=True) if df_b1_list else pd.DataFrame()
        
        # Process and merge B2 files
        df_b2 = None
        if file_paths["b2"]:
            df_b2_list = []
            for b2_path in file_paths["b2"]:
                df = file_processor.process_file(b2_path, "b2", b2_file_config)
                df_b2_list.append(df)
            df_b2 = pd.concat(df_b2_list, ignore_index=True) if df_b2_list else None
        
        # Process and merge B3 files
        df_b3 = None
        if file_paths["b3"]:
            df_b3_list = []
            for b3_path in file_paths["b3"]:
                df = file_processor.process_file(b3_path, "b3", b3_file_config)
                df_b3_list.append(df)
            df_b3 = pd.concat(df_b3_list, ignore_index=True) if df_b3_list else None
        
        workflow.add_step_log(
            batch.batch_id, "FILE_PROCESS", "OK",
            f"Đã xử lý: B1={len(df_b1)} dòng ({len(file_paths['b1'])} file)" +
            (f", B2={len(df_b2)} dòng ({len(file_paths['b2'])} file)" if df_b2 is not None else "") +
            (f", B3={len(df_b3)} dòng ({len(file_paths['b3'])} file)" if df_b3 is not None else "")
        )
        
        # Step 2: Load B4 data
        workflow.add_step_log(batch.batch_id, "LOAD_B4", "PROCESSING", "Đang tải dữ liệu B4...")
        
        from app.utils.file_utils import get_period_folder
        import json
        period = get_period_folder(date_from, date_to)
        data_loader = DataLoader(
            partner_code=partner_code,
            service_code=service_code,
            batch_id=batch.batch_id,
            period=period
        )
        # Parse b4_config from JSON string if needed
        b4_config_raw = config.data_b4_config if hasattr(config, 'data_b4_config') else '{}'
        b4_config = json.loads(b4_config_raw) if isinstance(b4_config_raw, str) else (b4_config_raw or {})
        df_b4 = data_loader.load_b4_data(b4_config, date_from, date_to)
        
        workflow.add_step_log(batch.batch_id, "LOAD_B4", "OK", f"Đã tải B4: {len(df_b4)} dòng (kỳ {date_from} - {date_to})")
        
        # Step 3: Run reconciliation
        workflow.add_step_log(batch.batch_id, "RECONCILE", "PROCESSING", "Đang chạy đối soát...")
        
        # Build matching_config from database config
        matching_config = _build_matching_config(config)
        
        engine = ReconciliationEngine()
        result = engine.run_full_reconciliation(df_b1, df_b4, df_b2, df_b3, matching_config)
        
        # Step 4: Save outputs
        workflow.add_step_log(batch.batch_id, "SAVE_OUTPUT", "PROCESSING", "Đang lưu kết quả...")
        
        output_folder = get_output_folder(partner_code, service_code, batch.batch_id)
        os.makedirs(output_folder, exist_ok=True)
        
        output_files = {}
        
        # Save A1
        a1_path = os.path.join(output_folder, f"A1_{batch.batch_id}.csv")
        result["a1_df"].to_csv(a1_path, index=False, encoding="utf-8-sig")
        output_files["a1"] = a1_path
        
        # Save A2
        a2_path = os.path.join(output_folder, f"A2_{batch.batch_id}.csv")
        result["a2_df"].to_csv(a2_path, index=False, encoding="utf-8-sig")
        output_files["a2"] = a2_path
        
        # Update batch with correct column names
        batch.file_result_a1 = a1_path
        batch.file_result_a2 = a2_path
        
        stats = {
            "total_b1": len(df_b1),
            "total_b4": len(df_b4),
            "total_b2": len(df_b2) if df_b2 is not None else 0,
            "total_b3": len(df_b3) if df_b3 is not None else 0,
            "total_a1": len(result["a1_df"]),
            "total_a2": len(result["a2_df"]),
            "matched": result["summary_stats"].get("matched", 0),
            "not_found": result["summary_stats"].get("not_found", 0),
            "mismatch": result["summary_stats"].get("mismatch", 0),
            "matching_stats": result["summary_stats"].get("matching_stats", {})
        }
        batch.summary_stats = json.dumps(stats)
        
        workflow.update_status(batch.batch_id, "COMPLETED", "Đối soát hoàn tất")
        workflow.add_step_log(batch.batch_id, "COMPLETE", "OK", f"Hoàn tất: A1={len(result['a1_df'])} dòng, A2={len(result['a2_df'])} dòng")
        
        db.commit()
        
        return {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "message": "Đối soát thành công",
            "stats": stats,
            "output_files": {
                "a1": f"/api/v1/reports/download/{batch.batch_id}/a1",
                "a2": f"/api/v1/reports/download/{batch.batch_id}/a2"
            }
        }
        
    except ReconciliationException as e:
        workflow.update_status(batch.batch_id, "ERROR", str(e))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Upload reconciliation error: {str(e)}")
        logger.error(traceback.format_exc())
        if batch:
            workflow.update_status(batch.batch_id, "ERROR", f"Lỗi hệ thống: {str(e)}")
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi xử lý: {str(e)}"
        )


@router.get("/check-duplicate")
async def check_duplicate_batch(
    partner_code: str = Query(...),
    service_code: str = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Check if a batch with the same partner/service/period exists
    """
    existing_batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.partner_code == partner_code,
        ReconciliationLog.service_code == service_code,
        ReconciliationLog.period_from == date_from,
        ReconciliationLog.period_to == date_to
    ).first()
    
    if existing_batch:
        return {
            "exists": True,
            "batch": {
                "batch_id": existing_batch.batch_id,
                "status": existing_batch.status,
                "period_from": existing_batch.period_from.isoformat() if existing_batch.period_from else None,
                "period_to": existing_batch.period_to.isoformat() if existing_batch.period_to else None,
                "created_at": existing_batch.created_at.isoformat() if existing_batch.created_at else None,
            }
        }
    
    return {"exists": False, "batch": None}


@router.delete("/batches/{batch_id}")
async def delete_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete a batch (only if not approved/locked)
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, "delete", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to delete this batch"
        )
    
    # Cannot delete approved/locked batches
    if batch.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete approved batch"
        )
    
    if hasattr(batch, 'is_locked') and batch.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete locked batch"
        )
    
    # Delete associated files using cleanup function
    cleanup_result = cleanup_batch_files(batch_id)
    
    # Delete from database
    db.delete(batch)
    db.commit()
    
    return {
        "message": f"Batch {batch_id} deleted successfully",
        "files_cleanup": cleanup_result
    }


@router.get("/batches")
async def list_batches(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    status: str = Query(default=None),
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    List reconciliation batches
    
    Filtered by user's permissions (admin sees all)
    """
    query = db.query(ReconciliationLog)
    
    if not current_user.is_admin:
        # Get user's permitted partner/services
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id
        ).all()
        
        allowed_pairs = [(p.partner_code, p.service_code) for p in permissions]
        
        if not allowed_pairs:
            return []
        
        # Filter by permissions
        from sqlalchemy import or_, and_
        conditions = [
            and_(
                ReconciliationLog.partner_code == pc,
                ReconciliationLog.service_code == sc
            )
            for pc, sc in allowed_pairs
        ]
        query = query.filter(or_(*conditions))
    
    # Apply filters
    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)
    if status:
        query = query.filter(ReconciliationLog.status == status)
    if from_date:
        query = query.filter(ReconciliationLog.period_from >= from_date)
    if to_date:
        query = query.filter(ReconciliationLog.period_to <= to_date)
    
    # Get total count for pagination
    total = query.count()
    
    batches = query.order_by(
        ReconciliationLog.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # Convert to dict for response
    import json
    items = []
    for b in batches:
        items.append({
            "id": b.id,
            "batch_id": b.batch_id,
            "partner_code": b.partner_code,
            "service_code": b.service_code,
            "config_id": b.config_id,
            "period_from": b.period_from.isoformat() if b.period_from else None,
            "period_to": b.period_to.isoformat() if b.period_to else None,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "summary_stats": json.loads(b.summary_stats) if b.summary_stats else None,
            "error_message": b.error_message
        })
    
    return {
        "items": items,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/batches/{batch_id}")
async def get_batch_detail(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get batch details including stats and step logs
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, "reconcile", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to view this batch"
        )
    
    import json
    # Parse JSON fields
    step_logs = json.loads(batch.step_logs) if batch.step_logs else []
    files_uploaded = json.loads(batch.files_uploaded) if batch.files_uploaded else {}
    summary_stats = json.loads(batch.summary_stats) if batch.summary_stats else {}
    
    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "partner_code": batch.partner_code,
        "service_code": batch.service_code,
        "period_from": batch.period_from.isoformat() if batch.period_from else None,
        "period_to": batch.period_to.isoformat() if batch.period_to else None,
        "status": batch.status,
        "created_by": batch.created_by,
        "approved_by": batch.approved_by,
        "approved_at": batch.approved_at.isoformat() if batch.approved_at else None,
        "step_logs": step_logs,
        "files_uploaded": files_uploaded,
        "file_result_a1": batch.file_result_a1,
        "file_result_a2": batch.file_result_a2,
        "file_report": batch.file_report,
        "summary_stats": summary_stats,
        "error_message": batch.error_message,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
    }


@router.post("/batches/{batch_id}/rerun")
async def rerun_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Re-run reconciliation for a batch (use existing uploaded files)
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, "reconcile", db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )
    
    if batch.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch is locked, cannot rerun"
        )
    
    if batch.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rerun approved batch"
        )
    
    # Get config
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == batch.config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    workflow = WorkflowService(db)
    
    try:
        # Reset status
        workflow.reset_batch(batch.batch_id, current_user.id)
        workflow.update_status(batch.batch_id, "PROCESSING", "Đang chạy lại đối soát...")
        
        # Get input files from files_uploaded (JSON string)
        import json
        files_uploaded_raw = batch.files_uploaded or '{}'
        file_paths = json.loads(files_uploaded_raw) if isinstance(files_uploaded_raw, str) else (files_uploaded_raw or {})
        
        if not file_paths.get("b1"):
            raise ReconciliationException("Missing B1 file - Không tìm thấy file B1 đã upload")
        
        # Process files (support multiple files)
        file_processor = FileProcessor(
            partner_code=batch.partner_code,
            service_code=batch.service_code,
            period_from=batch.period_from,
            period_to=batch.period_to,
            batch_id=batch.batch_id
        )
        
        # Parse file configs from database config
        def parse_file_config_run(config_str):
            if not config_str:
                return {"header_row": 1, "data_start_row": 2}
            try:
                return json.loads(config_str) if isinstance(config_str, str) else config_str
            except json.JSONDecodeError:
                return {"header_row": 1, "data_start_row": 2}
        
        b1_file_config = parse_file_config_run(config.file_b1_config)
        b2_file_config = parse_file_config_run(config.file_b2_config)
        b3_file_config = parse_file_config_run(config.file_b3_config)
        
        import pandas as pd
        # Process B1 files (can be list or single path)
        b1_paths = file_paths["b1"] if isinstance(file_paths["b1"], list) else [file_paths["b1"]]
        df_b1_list = [file_processor.process_file(p, "b1", b1_file_config) for p in b1_paths]
        df_b1 = pd.concat(df_b1_list, ignore_index=True) if df_b1_list else pd.DataFrame()
        
        # Process B2 files
        df_b2 = None
        if file_paths.get("b2"):
            b2_paths = file_paths["b2"] if isinstance(file_paths["b2"], list) else [file_paths["b2"]]
            df_b2_list = [file_processor.process_file(p, "b2", b2_file_config) for p in b2_paths if p]
            df_b2 = pd.concat(df_b2_list, ignore_index=True) if df_b2_list else None
        
        # Process B3 files
        df_b3 = None
        if file_paths.get("b3"):
            b3_paths = file_paths["b3"] if isinstance(file_paths["b3"], list) else [file_paths["b3"]]
            df_b3_list = [file_processor.process_file(p, "b3", b3_file_config) for p in b3_paths if p]
            df_b3 = pd.concat(df_b3_list, ignore_index=True) if df_b3_list else None
        
        # Load B4
        from app.utils.file_utils import get_period_folder
        import json
        period = get_period_folder(batch.period_from, batch.period_to)
        data_loader = DataLoader(
            partner_code=batch.partner_code,
            service_code=batch.service_code,
            batch_id=batch.batch_id,
            period=period
        )
        # Parse b4_config from JSON string if needed
        b4_config_raw = config.data_b4_config if hasattr(config, 'data_b4_config') else '{}'
        b4_config = json.loads(b4_config_raw) if isinstance(b4_config_raw, str) else (b4_config_raw or {})
        df_b4 = data_loader.load_b4_data(b4_config, batch.period_from, batch.period_to)
        
        # Run reconciliation
        matching_config = _build_matching_config(config)
        engine = ReconciliationEngine()
        result = engine.run_full_reconciliation(df_b1, df_b4, df_b2, df_b3, matching_config)
        
        # Save outputs
        output_folder = get_output_folder(batch.partner_code, batch.service_code, batch.batch_id)
        os.makedirs(output_folder, exist_ok=True)
        
        output_files = {}
        
        a1_path = os.path.join(output_folder, f"A1_{batch.batch_id}.csv")
        result["a1_df"].to_csv(a1_path, index=False, encoding="utf-8-sig")
        output_files["a1"] = a1_path
        
        a2_path = os.path.join(output_folder, f"A2_{batch.batch_id}.csv")
        result["a2_df"].to_csv(a2_path, index=False, encoding="utf-8-sig")
        output_files["a2"] = a2_path
        
        # Update batch with correct column names
        batch.file_result_a1 = a1_path
        batch.file_result_a2 = a2_path
        
        stats = {
            "total_b1": len(df_b1),
            "total_b4": len(df_b4),
            "total_a1": len(result["a1_df"]),
            "total_a2": len(result["a2_df"]),
            "matched": result["summary_stats"].get("matched", 0),
            "not_found": result["summary_stats"].get("not_found", 0),
            "mismatch": result["summary_stats"].get("mismatch", 0),
            "matching_stats": result["summary_stats"].get("matching_stats", {})
        }
        batch.summary_stats = json.dumps(stats)
        
        workflow.update_status(batch.batch_id, "COMPLETED", "Chạy lại hoàn tất")
        db.commit()
        
        return {
            "batch_id": batch.batch_id,
            "status": "COMPLETED",
            "message": "Chạy lại đối soát thành công",
            "stats": stats
        }
        
    except Exception as e:
        workflow.update_status(batch.batch_id, "ERROR", f"Lỗi: {str(e)}")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/storage/orphans")
async def list_orphan_storage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    List orphan folders (folders without corresponding batch in database)
    
    This helps identify storage that can be cleaned up.
    Admin only.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )
    
    # Get all batch IDs from database
    db_batch_ids = [b.batch_id for b in db.query(ReconciliationLog.batch_id).all()]
    
    orphans = list_orphan_folders(db_batch_ids)
    
    return {
        "orphan_folders": orphans,
        "db_batch_count": len(db_batch_ids)
    }


@router.delete("/storage/cleanup-orphans")
async def cleanup_orphan_storage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete all orphan folders (folders without corresponding batch in database)
    
    Admin only. Use with caution!
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only"
        )
    
    # Get all batch IDs from database
    db_batch_ids = [b.batch_id for b in db.query(ReconciliationLog.batch_id).all()]
    
    result = cleanup_orphan_folders(db_batch_ids)
    
    return {
        "message": "Orphan cleanup completed",
        "result": result
    }
