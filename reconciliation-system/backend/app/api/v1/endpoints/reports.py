"""
Report endpoints
Preview results, download files, generate reports
"""

import os
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd

from app.api.deps import get_db, get_current_user
from app.models import User, ReconciliationLog, PartnerServiceConfig, UserPermission
from app.services.report_generator import ReportGenerator


router = APIRouter()


def check_user_permission(
    user: User,
    partner_code: str,
    service_code: str,
    db: Session
) -> bool:
    """Check if user has any permission for partner/service"""
    if user.is_admin:
        return True
    
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.partner_code == partner_code,
        UserPermission.service_code == service_code
    ).first()
    
    return permission is not None


@router.get("/preview/{batch_id}/{file_type}")
async def preview_results(
    batch_id: str,
    file_type: str,
    skip: int = 0,
    limit: int = 100,
    status_b1b4: str = Query(default=None, description="Filter by B1B4 status"),
    status_b1b2: str = Query(default=None, description="Filter by B1B2 status"),
    status_b3a1: str = Query(default=None, description="Filter by B3A1 status (for A2)"),
    final_status: str = Query(default=None, description="Filter by Final Status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Preview reconciliation results (A1 or A2)
    
    file_type: "a1" or "a2"
    Returns paginated JSON data
    """
    if file_type not in ["a1", "a2"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'a1' or 'a2'"
        )
    
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )
    
    # Get file path based on file_type
    if file_type == "a1":
        file_path = batch.file_result_a1
    elif file_type == "a2":
        file_path = batch.file_result_a2
    else:
        file_path = None
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{file_type.upper()} file not found"
        )
    
    # Read CSV
    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")
        
        # Apply filters (case-insensitive column matching)
        df_columns_lower = {c.lower(): c for c in df.columns}
        
        if status_b1b4 and 'status_b1b4' in df_columns_lower:
            actual_col = df_columns_lower['status_b1b4']
            df = df[df[actual_col].astype(str).str.upper() == status_b1b4.upper()]
        
        if status_b1b2 and 'status_b1b2' in df_columns_lower:
            actual_col = df_columns_lower['status_b1b2']
            df = df[df[actual_col].astype(str).str.upper() == status_b1b2.upper()]
        
        # Filter B3A1 for A2 results
        if status_b3a1 and 'status_b3a1' in df_columns_lower:
            actual_col = df_columns_lower['status_b3a1']
            df = df[df[actual_col].astype(str).str.upper() == status_b3a1.upper()]
        
        # Filter by Final Status
        if final_status and 'final_status' in df_columns_lower:
            actual_col = df_columns_lower['final_status']
            df = df[df[actual_col].astype(str).str.upper() == final_status.upper()]
        
        total = len(df)
        
        # Paginate
        df_page = df.iloc[skip:skip + limit]
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "columns": list(df_page.columns),
            "data": df_page.fillna("").to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file: {str(e)}"
        )


@router.get("/download/{batch_id}/{file_type}")
async def download_file(
    batch_id: str,
    file_type: str,
    format: str = Query(default="csv"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download reconciliation result file
    
    file_type: "a1", "a2", or "report"
    format: "csv" or "xlsx"
    """
    if file_type not in ["a1", "a2", "report"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_type must be 'a1', 'a2', or 'report'"
        )
    
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )
    
    # Get file path based on file_type
    if file_type == "a1":
        file_path = batch.file_result_a1
    elif file_type == "a2":
        file_path = batch.file_result_a2
    elif file_type == "report":
        file_path = batch.file_report
    else:
        file_path = None
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{file_type.upper()} file not found"
        )
    
    # Convert format if needed
    if format == "xlsx" and file_path.endswith(".csv"):
        # Convert CSV to Excel
        xlsx_path = file_path.replace(".csv", ".xlsx")
        
        if not os.path.exists(xlsx_path):
            df = pd.read_csv(file_path, encoding="utf-8-sig")
            df.to_excel(xlsx_path, index=False)
        
        file_path = xlsx_path
    
    filename = os.path.basename(file_path)
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.post("/generate/{batch_id}")
async def generate_report(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Generate report from template for a batch
    
    Uses A1 data and report template from config
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
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )
    
    if batch.status not in ["COMPLETED", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch must be completed before generating report"
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
    
    if not config.report_template_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No report template configured"
        )
    
    try:
        # Get A1 data
        a1_path = batch.file_result_a1
        
        if not a1_path or not os.path.exists(a1_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A1 file not found"
            )
        
        df_a1 = pd.read_csv(a1_path, encoding="utf-8-sig")
        
        # Parse cell mapping from config
        cell_mapping = None
        if config.report_cell_mapping:
            try:
                import json
                cell_mapping = json.loads(config.report_cell_mapping) if isinstance(config.report_cell_mapping, str) else config.report_cell_mapping
            except:
                pass
        
        # Generate report
        # Create period string from period_from (YYYYMMDD format)
        period = batch.period_from.strftime('%Y%m%d') if batch.period_from else 'unknown'
        
        generator = ReportGenerator(
            partner_code=batch.partner_code,
            service_code=batch.service_code,
            period=period,
            batch_id=batch.batch_id,
            period_from=batch.period_from,
            period_to=batch.period_to,
            created_by=current_user.email or current_user.username
        )
        report_path = generator.generate_report(
            a1_df=df_a1,
            template_path=config.report_template_path,
            cell_mapping=cell_mapping
        )
        
        # Get execution logs
        execution_logs = generator.get_logs()
        
        # Update batch step_logs with report generation logs
        import json
        existing_logs = []
        if batch.step_logs:
            try:
                existing_logs = json.loads(batch.step_logs) if isinstance(batch.step_logs, str) else batch.step_logs
            except:
                existing_logs = []
        
        # Add report generation logs
        existing_logs.append({
            "step": "report_generation",
            "time": pd.Timestamp.now().isoformat(),
            "status": "ok" if report_path else "error",
            "message": f"Report generated: {report_path}" if report_path else "Report generation failed",
            "details": execution_logs
        })
        batch.step_logs = json.dumps(existing_logs, ensure_ascii=False)
        
        if not report_path:
            db.commit()
            return {
                "message": "Report generation failed - check logs for details",
                "success": False,
                "logs": execution_logs
            }
        
        # Update batch with report path
        batch.file_report = report_path
        db.commit()
        
        return {
            "message": "Report generated successfully",
            "success": True,
            "download_url": f"/api/v1/reports/download/{batch_id}/report",
            "logs": execution_logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )


@router.get("/stats/{batch_id}")
async def get_batch_stats(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed statistics for a batch
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
    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )
    
    # Parse summary_stats from JSON
    import json
    stats = {}
    if batch.summary_stats:
        try:
            stats = json.loads(batch.summary_stats) if isinstance(batch.summary_stats, str) else batch.summary_stats
        except:
            pass
    
    a1_stats = {}
    a2_stats = {}
    
    # A1 breakdown by status
    if batch.file_result_a1 and os.path.exists(batch.file_result_a1):
        try:
            df_a1 = pd.read_csv(batch.file_result_a1, encoding="utf-8-sig")
            if "final_status" in df_a1.columns:
                a1_stats["by_final_status"] = df_a1["final_status"].value_counts().to_dict()
            if "status_b1b4" in df_a1.columns:
                a1_stats["by_status_b1b4"] = df_a1["status_b1b4"].value_counts().to_dict()
            if "status_b1b2" in df_a1.columns:
                a1_stats["by_status_b1b2"] = df_a1["status_b1b2"].value_counts().to_dict()
            a1_stats["total"] = len(df_a1)
        except:
            pass
    
    # A2 breakdown
    if batch.file_result_a2 and os.path.exists(batch.file_result_a2):
        try:
            df_a2 = pd.read_csv(batch.file_result_a2, encoding="utf-8-sig")
            if "source" in df_a2.columns:
                a2_stats["by_source"] = df_a2["source"].value_counts().to_dict()
            a2_stats["total"] = len(df_a2)
        except:
            pass
    
    # Get final status options from config
    final_status_options = []
    if batch.config_id:
        config = db.query(PartnerServiceConfig).filter(
            PartnerServiceConfig.id == batch.config_id
        ).first()
        if config and config.status_combine_rules:
            try:
                combine_rules = json.loads(config.status_combine_rules) if isinstance(config.status_combine_rules, str) else config.status_combine_rules
                # Extract unique final values
                if isinstance(combine_rules, dict) and 'rules' in combine_rules:
                    for rule in combine_rules['rules']:
                        if 'final' in rule and rule['final'] not in final_status_options:
                            final_status_options.append(rule['final'])
                    if 'default' in combine_rules and combine_rules['default'] not in final_status_options:
                        final_status_options.append(combine_rules['default'])
            except:
                pass
    
    return {
        "batch_id": batch_id,
        "status": batch.status,
        "reconcile_date": str(batch.period_from),
        "basic_stats": stats,
        "a1_stats": a1_stats,
        "a2_stats": a2_stats,
        "final_status_options": final_status_options
    }
