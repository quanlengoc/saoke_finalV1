"""
Report endpoints (V2)
Preview results, download files, generate reports
"""

import os
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd

from app.api.deps import get_db, get_current_user
from app.models import User, ReconciliationLog, PartnerServiceConfig, UserPermission
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

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
    status_filter: str = Query(default=None, description="Generic filter: col_name=value (e.g., match_status=MATCHED)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Preview reconciliation results for any output type.

    file_type: output name (e.g., any configured output name)
    status_filter: generic filter "col_name=value" for any status column
    Returns paginated JSON data
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )

    file_path = batch.get_file_path(file_type)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{file_type.upper()} file not found"
        )

    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")

        df_columns_lower = {c.lower(): c for c in df.columns}

        # Generic status filter: "col_name=value" for any status column
        if status_filter and '=' in status_filter:
            filter_col, filter_val = status_filter.split('=', 1)
            filter_col_lower = filter_col.strip().lower()
            if filter_col_lower in df_columns_lower:
                actual_col = df_columns_lower[filter_col_lower]
                df = df[df[actual_col].astype(str).str.upper() == filter_val.strip().upper()]

        total = len(df)
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
    Download reconciliation result file.
    file_type: any output name or "report"
    format: "csv" or "xlsx"
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )

    file_path = batch.get_file_path(file_type)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{file_type.upper()} file not found"
        )

    if format == "xlsx" and file_path.endswith(".csv"):
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
    """Generate report from template for a batch"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

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
        import json as json_mod
        file_results = {}
        if batch.file_results:
            try:
                file_results = json_mod.loads(batch.file_results) if isinstance(batch.file_results, str) else (batch.file_results or {})
            except Exception as e:
                logger.warning(f"Failed to parse file_results: {e}")

        # Get A1 data — prefer file_results["A1"], fallback to legacy file_result_a1
        a1_path = file_results.get("A1") or batch.file_result_a1

        if not a1_path or not os.path.exists(a1_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="A1 file not found"
            )

        df_a1 = pd.read_csv(a1_path, encoding="utf-8-sig")

        # Load ALL other output DataFrames from file_results
        additional_outputs = {}
        for output_name, csv_path in file_results.items():
            if output_name.upper() != "A1" and csv_path and os.path.exists(csv_path):
                try:
                    additional_outputs[output_name] = pd.read_csv(csv_path, encoding="utf-8-sig")
                    logger.info(f"Loaded additional output {output_name}: {len(additional_outputs[output_name])} rows")
                except Exception as e:
                    logger.warning(f"Failed to load output {output_name} from {csv_path}: {e}")

        # Parse cell mapping from config
        cell_mapping = None
        if config.report_cell_mapping:
            try:
                import json
                cell_mapping = json.loads(config.report_cell_mapping) if isinstance(config.report_cell_mapping, str) else config.report_cell_mapping
            except:
                pass

        # Generate report
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
            cell_mapping=cell_mapping,
            additional_outputs=additional_outputs
        )

        execution_logs = generator.get_logs()

        # Append report generation log to file-based step_logs
        from app.utils.step_log_file import append_step_log_to_batch
        report_log_entry = {
            "step": "report_generation",
            "time": pd.Timestamp.now().isoformat(),
            "status": "ok" if report_path else "error",
            "message": f"Report generated: {report_path}" if report_path else "Report generation failed",
            "details": execution_logs,
        }
        append_step_log_to_batch(batch, report_log_entry, db)

        if not report_path:
            db.commit()
            return {
                "message": "Report generation failed - check logs for details",
                "success": False,
                "logs": execution_logs
            }

        batch.file_report = report_path
        db.commit()

        return {
            "message": "Report generated successfully",
            "success": True,
            "download_url": f"/api/v2/reports/download/{batch_id}/report",
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
    """Get detailed statistics for a batch"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    if not check_user_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission"
        )

    import json
    stats = {}
    if batch.summary_stats:
        try:
            stats = json.loads(batch.summary_stats) if isinstance(batch.summary_stats, str) else batch.summary_stats
        except:
            pass

    # Dynamic output stats from file_results
    output_stats = {}
    for output_name, output_path in batch.file_results_dict.items():
        if output_path and os.path.exists(output_path):
            try:
                df_out = pd.read_csv(output_path, encoding="utf-8-sig")
                out_stat = {"total": len(df_out), "filter_columns": {}}
                for col in df_out.columns:
                    col_lower = col.lower()
                    if ('status' in col_lower) and ('detail' not in col_lower) and ('note' not in col_lower):
                        value_counts = df_out[col].value_counts().to_dict()
                        out_stat[f"by_{col}"] = value_counts
                        out_stat["filter_columns"][col] = list(value_counts.keys())
                if output_name.upper().startswith('A2') and 'source' in df_out.columns:
                    out_stat["by_source"] = df_out["source"].value_counts().to_dict()
                output_stats[output_name] = out_stat
            except:
                pass

    # Get final status options from config's workflow steps
    config = None
    final_status_options = []
    if batch.config_id:
        config = db.query(PartnerServiceConfig).filter(
            PartnerServiceConfig.id == batch.config_id
        ).first()
        if config:
            try:
                for ws in (config.workflow_steps or []):
                    scr = getattr(ws, 'status_combine_rules', None)
                    if scr:
                        combine_rules = json.loads(scr) if isinstance(scr, str) else scr
                        if isinstance(combine_rules, dict) and 'rules' in combine_rules:
                            for rule in combine_rules['rules']:
                                if 'final' in rule and rule['final'] not in final_status_options:
                                    final_status_options.append(rule['final'])
                            if 'default' in combine_rules and combine_rules['default'] not in final_status_options:
                                final_status_options.append(combine_rules['default'])
            except Exception:
                pass

    # Build output_order from workflow steps
    output_order = {}
    if batch.config_id:
        if not config:
            config = db.query(PartnerServiceConfig).filter(
                PartnerServiceConfig.id == batch.config_id
            ).first()
        if config:
            for ws in (config.workflow_steps or []):
                output_order[ws.output_name] = {
                    "step_order": ws.step_order,
                    "step_name": ws.step_name or f"Step {ws.step_order}",
                    "left_source": ws.left_source,
                    "right_source": ws.right_source,
                    "output_type": ws.output_type or "intermediate",
                    "is_final_output": ws.is_final_output or False,
                    "display_name": f"Step {ws.step_order}: {ws.left_source} ↔ {ws.right_source}",
                }

    return {
        "batch_id": batch_id,
        "status": batch.status,
        "reconcile_date": str(batch.period_from),
        "basic_stats": stats,
        "output_stats": output_stats,
        "file_results": batch.file_results_dict,
        "final_status_options": final_status_options,
        "output_order": output_order,
    }
