"""
Report endpoints (V2)
Preview results, download files, generate reports
"""

import os
import json
import logging
import tempfile
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd

from app.api.deps import get_db, get_current_user
from app.models import User, ReconciliationLog, PartnerServiceConfig, UserPermission
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Filter helpers
# =============================================================================

def _detect_column_type(series: pd.Series) -> str:
    """Auto-detect data type from pandas Series."""
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    # Try date parsing
    try:
        sample = series.dropna().head(100)
        if len(sample) > 0:
            parsed = pd.to_datetime(sample, errors='coerce')
            if parsed.notna().sum() > len(parsed) * 0.5:
                return "date"
    except Exception:
        pass
    # Check boolean-like (only 2 unique values like true/false, 0/1, yes/no)
    unique = series.dropna().unique()
    if len(unique) <= 2:
        lower_vals = {str(v).lower() for v in unique}
        if lower_vals <= {'true', 'false', '0', '1', 'yes', 'no', 't', 'f'}:
            return "boolean"
    return "string"


def parse_filters(filters_param: str = None, status_filter: str = None) -> list:
    """Parse filter params → list of filter dicts.

    New format: filters_param = JSON array of {col, op, value, min, max}
    Legacy format: status_filter = "col_name=value"
    """
    if filters_param:
        try:
            return json.loads(filters_param)
        except (json.JSONDecodeError, TypeError):
            return []
    if status_filter and '=' in status_filter:
        col, val = status_filter.split('=', 1)
        return [{"col": col.strip(), "op": "eq", "value": val.strip()}]
    return []


def apply_filters(chunk: pd.DataFrame, filters: list) -> pd.DataFrame:
    """Apply all filters to a DataFrame chunk. Returns filtered chunk."""
    if not filters:
        return chunk
    mask = pd.Series(True, index=chunk.index)
    for f in filters:
        col = f.get("col", "")
        op = f.get("op", "eq")
        # Case-insensitive column lookup
        col_map = {c.lower(): c for c in chunk.columns}
        actual_col = col_map.get(col.lower())
        if not actual_col:
            continue
        if op == "eq":
            mask &= chunk[actual_col].astype(str).str.upper() == str(f.get("value", "")).upper()
        elif op == "like":
            mask &= chunk[actual_col].astype(str).str.upper().str.contains(
                str(f.get("value", "")).upper(), na=False
            )
        elif op == "range":
            # Try numeric range first
            series = pd.to_numeric(chunk[actual_col], errors='coerce')
            if series.isna().all():
                # Try date range
                series = pd.to_datetime(chunk[actual_col], errors='coerce')
            if f.get("min") is not None and str(f["min"]) != "":
                try:
                    min_val = pd.to_datetime(f["min"]) if hasattr(series.dtype, 'tz') or str(series.dtype).startswith('datetime') else float(f["min"])
                    mask &= series >= min_val
                except (ValueError, TypeError):
                    pass
            if f.get("max") is not None and str(f["max"]) != "":
                try:
                    max_val = pd.to_datetime(f["max"]) if hasattr(series.dtype, 'tz') or str(series.dtype).startswith('datetime') else float(f["max"])
                    mask &= series <= max_val
                except (ValueError, TypeError):
                    pass
    return chunk[mask]


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


def _get_csv_line_count(file_path: str) -> int:
    """Count lines in CSV file without loading into memory. O(1) memory."""
    count = -1  # exclude header
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for _ in f:
            count += 1
    return max(count, 0)


@router.get("/preview/{batch_id}/{file_type}")
async def preview_results(
    batch_id: str,
    file_type: str,
    skip: int = 0,
    limit: int = 100,
    status_filter: str = Query(default=None, description="Legacy filter: col_name=value"),
    filters: str = Query(default=None, description="JSON array of filter objects: [{col, op, value, min, max}]"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Preview reconciliation results for any output type.

    file_type: output name (e.g., any configured output name)
    filters: JSON array [{col, op, value, min, max}] — supports eq, like, range
    status_filter: legacy filter "col_name=value" (backward compat)
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
        # Parse filters (new JSON format or legacy status_filter)
        active_filters = parse_filters(filters, status_filter)
        has_filter = len(active_filters) > 0

        if not has_filter:
            # === CASE 1: No filter — efficient seek-based pagination ===
            header = pd.read_csv(file_path, nrows=0, encoding="utf-8-sig")
            columns = list(header.columns)

            if skip > 0:
                df_page = pd.read_csv(
                    file_path, skiprows=range(1, skip + 1),
                    nrows=limit, encoding="utf-8-sig"
                )
            else:
                df_page = pd.read_csv(
                    file_path, nrows=limit, encoding="utf-8-sig"
                )

            total = _get_csv_line_count(file_path)

            return {
                "total": total,
                "skip": skip,
                "limit": limit,
                "columns": columns,
                "data": df_page.fillna("").to_dict(orient="records")
            }
        else:
            # === CASE 2: With filter — chunked reading ===
            collected_rows = []
            total_matched = 0
            skipped = 0
            columns = None

            for chunk in pd.read_csv(file_path, chunksize=50000, encoding="utf-8-sig"):
                if columns is None:
                    columns = list(chunk.columns)

                filtered = apply_filters(chunk, active_filters)
                total_matched += len(filtered)

                # Collect rows for the requested page
                if len(collected_rows) < limit:
                    for _, row in filtered.iterrows():
                        if skipped < skip:
                            skipped += 1
                            continue
                        if len(collected_rows) < limit:
                            collected_rows.append(row)

            df_page = pd.DataFrame(collected_rows, columns=columns) if collected_rows else pd.DataFrame(columns=columns or [])

            return {
                "total": total_matched,
                "skip": skip,
                "limit": limit,
                "columns": columns or [],
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
    status_filter: Optional[str] = Query(default=None),
    filters: Optional[str] = Query(default=None, description="JSON array of filter objects"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download reconciliation result file.
    file_type: any output name or "report"
    format: "csv" or "xlsx"
    filters: JSON array [{col, op, value, min, max}] — new multi-filter format
    status_filter: legacy filter "column_name=value" (backward compat)
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

    # Parse filters (new JSON format or legacy status_filter)
    active_filters = parse_filters(filters, status_filter)

    # If filters are active, use chunked reading to filter without loading all into RAM
    if active_filters and file_path.endswith(".csv"):
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            suffix = "_filtered"

            # Chunked filter + write to temp CSV
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".csv",
                dir=os.path.dirname(file_path)
            )
            tmp_path = tmp.name
            tmp.close()

            first_chunk = True
            has_data = False
            for chunk in pd.read_csv(file_path, chunksize=50000, encoding="utf-8-sig"):
                filtered = apply_filters(chunk, active_filters)
                if not filtered.empty:
                    filtered.to_csv(
                        tmp_path, mode='a', header=first_chunk,
                        index=False, encoding="utf-8-sig"
                    )
                    first_chunk = False
                    has_data = True

            if has_data:
                if format == "xlsx":
                    xlsx_tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".xlsx",
                        dir=os.path.dirname(file_path)
                    )
                    xlsx_tmp_path = xlsx_tmp.name
                    xlsx_tmp.close()
                    df_filtered = pd.read_csv(tmp_path, encoding="utf-8-sig")
                    df_filtered.to_excel(xlsx_tmp_path, index=False)
                    os.unlink(tmp_path)
                    return FileResponse(
                        path=xlsx_tmp_path,
                        filename=f"{base_name}{suffix}.xlsx",
                        media_type="application/octet-stream",
                        background=None
                    )
                else:
                    return FileResponse(
                        path=tmp_path,
                        filename=f"{base_name}{suffix}.csv",
                        media_type="application/octet-stream",
                        background=None
                    )
            else:
                os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to apply filters: {e}")
            # Fall through to download full file

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

    # Use pre-computed output_stats from summary_stats (computed during workflow execution)
    output_stats = stats.get("output_stats", {})

    # Fallback: read CSV for old batches that don't have pre-computed output_stats
    if not output_stats:
        # Try to get config for filterable column lookup
        fallback_config = None
        if batch.config_id:
            fallback_config = db.query(PartnerServiceConfig).filter(
                PartnerServiceConfig.id == batch.config_id
            ).first()

        for output_name, output_path in batch.file_results_dict.items():
            if output_path and os.path.exists(output_path):
                try:
                    df_out = pd.read_csv(output_path, encoding="utf-8-sig")
                    out_stat = {"total": len(df_out), "filter_columns": {}}

                    # Try config-driven filterable columns
                    filterable_cols = []
                    if fallback_config:
                        step_map = {s.output_name.upper(): s for s in (fallback_config.workflow_steps or [])}
                        step = step_map.get(output_name.upper())
                        if step:
                            cols_list = step.output_columns_list if hasattr(step, 'output_columns_list') else []
                            filterable_cols = [c for c in cols_list if c.get("filterable")]

                    # ALWAYS include match_status and other status columns (default badges + filter)
                    for col in df_out.columns:
                        col_lower = col.lower()
                        if ('status' in col_lower) and ('detail' not in col_lower) and ('note' not in col_lower):
                            value_counts = df_out[col].value_counts().to_dict()
                            out_stat[f"by_{col}"] = {str(k): int(v) for k, v in value_counts.items()}
                            out_stat["filter_columns"][col] = [str(k) for k in value_counts.keys()]

                    # Additional filterable columns from config
                    if filterable_cols:
                        for col_cfg in filterable_cols:
                            col_name = col_cfg.get("display_name") or col_cfg.get("column_name")
                            if not col_name or col_name not in df_out.columns:
                                continue
                            if col_name in out_stat["filter_columns"]:
                                continue
                            data_type = _detect_column_type(df_out[col_name])
                            if data_type == "string":
                                vc = df_out[col_name].value_counts().to_dict()
                                values_list = [str(k) for k in vc.keys()]
                                out_stat["filter_columns"][col_name] = {
                                    "type": "string",
                                    "values": values_list
                                }
                                if len(values_list) <= 20:
                                    out_stat[f"by_{col_name}"] = {str(k): int(v) for k, v in vc.items()}
                            elif data_type == "number":
                                s = pd.to_numeric(df_out[col_name], errors='coerce')
                                out_stat["filter_columns"][col_name] = {
                                    "type": "number",
                                    "min": float(s.min()) if not s.isna().all() else None,
                                    "max": float(s.max()) if not s.isna().all() else None,
                                }
                            elif data_type == "date":
                                s = pd.to_datetime(df_out[col_name], errors='coerce')
                                out_stat["filter_columns"][col_name] = {
                                    "type": "date",
                                    "min": str(s.min().date()) if not s.isna().all() else None,
                                    "max": str(s.max().date()) if not s.isna().all() else None,
                                }
                            elif data_type == "boolean":
                                vc = df_out[col_name].astype(str).value_counts().to_dict()
                                out_stat["filter_columns"][col_name] = {
                                    "type": "boolean",
                                    "values": [str(k) for k in vc.keys()]
                                }

                    if 'source' in df_out.columns:
                        out_stat["by_source"] = {str(k): int(v) for k, v in df_out["source"].value_counts().to_dict().items()}
                    output_stats[output_name] = out_stat
                except Exception:
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
