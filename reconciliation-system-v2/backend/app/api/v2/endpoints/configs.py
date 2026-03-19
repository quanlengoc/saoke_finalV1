"""
Partner Service Config Endpoints - V2
CRUD operations for configs with related data
"""

import json
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin
from app.models import PartnerServiceConfig, DataSourceConfig, WorkflowStep, OutputConfig, User
from app.schemas.v2.config import (
    PartnerServiceConfigCreate,
    PartnerServiceConfigUpdate,
    PartnerServiceConfigResponse,
    PartnerServiceConfigList,
    DataSourceSummary,
    WorkflowStepSummary,
    OutputConfigSummary,
)

router = APIRouter()


def _build_config_response(config: PartnerServiceConfig) -> PartnerServiceConfigResponse:
    """Build response with related data summaries"""
    data_sources = [
        DataSourceSummary(
            source_name=ds.source_name,
            source_type=ds.source_type,
            display_name=ds.display_name,
            is_required=ds.is_required
        )
        for ds in sorted(config.data_sources, key=lambda x: x.display_order)
    ]
    
    workflow_steps = [
        WorkflowStepSummary(
            step_order=ws.step_order,
            step_name=ws.step_name,
            left_source=ws.left_source,
            right_source=ws.right_source,
            output_name=ws.output_name,
            is_final_output=ws.is_final_output
        )
        for ws in sorted(config.workflow_steps, key=lambda x: x.step_order)
    ]
    
    output_configs = [
        OutputConfigSummary(
            output_name=oc.output_name,
            display_name=oc.display_name,
            use_for_report=oc.use_for_report
        )
        for oc in sorted(config.output_configs, key=lambda x: x.display_order)
    ]
    
    return PartnerServiceConfigResponse(
        id=config.id,
        partner_code=config.partner_code,
        partner_name=config.partner_name,
        service_code=config.service_code,
        service_name=config.service_name,
        is_active=config.is_active,
        valid_from=config.valid_from,
        valid_to=config.valid_to,
        report_template_path=config.report_template_path,
        report_cell_mapping=config.report_cell_mapping,
        created_at=config.created_at,
        updated_at=config.updated_at,
        data_sources=data_sources,
        workflow_steps=workflow_steps,
        output_configs=output_configs
    )


@router.get("/", response_model=PartnerServiceConfigList)
async def list_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    partner_code: Optional[str] = None,
    service_code: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all configs with pagination and filtering"""
    query = db.query(PartnerServiceConfig).options(
        joinedload(PartnerServiceConfig.data_sources),
        joinedload(PartnerServiceConfig.workflow_steps),
        joinedload(PartnerServiceConfig.output_configs)
    )
    
    if partner_code:
        query = query.filter(PartnerServiceConfig.partner_code == partner_code)
    if service_code:
        query = query.filter(PartnerServiceConfig.service_code == service_code)
    if is_active is not None:
        query = query.filter(PartnerServiceConfig.is_active == is_active)
    
    # Get total count before pagination (need separate query without joinedload for count)
    count_query = db.query(PartnerServiceConfig)
    if partner_code:
        count_query = count_query.filter(PartnerServiceConfig.partner_code == partner_code)
    if service_code:
        count_query = count_query.filter(PartnerServiceConfig.service_code == service_code)
    if is_active is not None:
        count_query = count_query.filter(PartnerServiceConfig.is_active == is_active)
    total = count_query.count()
    
    configs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    items = [_build_config_response(c) for c in configs]
    
    return PartnerServiceConfigList(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{config_id}", response_model=PartnerServiceConfigResponse)
async def get_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get config by ID with all related data"""
    config = db.query(PartnerServiceConfig).options(
        joinedload(PartnerServiceConfig.data_sources),
        joinedload(PartnerServiceConfig.workflow_steps),
        joinedload(PartnerServiceConfig.output_configs)
    ).filter(PartnerServiceConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    return _build_config_response(config)


@router.get("/by-code/{partner_code}/{service_code}", response_model=PartnerServiceConfigResponse)
async def get_config_by_code(
    partner_code: str,
    service_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get active config by partner and service code"""
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.partner_code == partner_code.upper(),
        PartnerServiceConfig.service_code == service_code.upper(),
        PartnerServiceConfig.is_active == True
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    return _build_config_response(config)


@router.post("/", response_model=PartnerServiceConfigResponse)
async def create_config(
    data: PartnerServiceConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Create a new config
    
    Validates that date ranges don't overlap with existing configs 
    for the same partner_code + service_code
    """
    # Check for overlapping date ranges with same partner+service
    existing_configs = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.partner_code == data.partner_code.upper(),
        PartnerServiceConfig.service_code == data.service_code.upper(),
        PartnerServiceConfig.is_active == True
    ).all()
    
    new_start = data.valid_from
    new_end = data.valid_to or date(9999, 12, 31)  # Treat None as "forever"
    
    for existing in existing_configs:
        existing_start = existing.valid_from
        existing_end = existing.valid_to or date(9999, 12, 31)
        
        # Check if date ranges overlap
        # Two ranges [A, B] and [C, D] overlap if: A <= D and C <= B
        if new_start <= existing_end and existing_start <= new_end:
            raise HTTPException(
                status_code=400, 
                detail=f"Khoảng thời gian áp dụng ({data.valid_from} - {data.valid_to or 'vô hạn'}) "
                       f"giao nhau với cấu hình ID {existing.id} "
                       f"({existing.valid_from} - {existing.valid_to or 'vô hạn'}). "
                       f"Vui lòng chọn khoảng thời gian khác."
            )
    
    # Serialize report_cell_mapping to JSON if it's a dict
    report_cell_mapping_str = None
    if data.report_cell_mapping:
        report_cell_mapping_str = json.dumps(data.report_cell_mapping) if isinstance(data.report_cell_mapping, dict) else data.report_cell_mapping
    
    config = PartnerServiceConfig(
        partner_code=data.partner_code.upper(),
        partner_name=data.partner_name,
        service_code=data.service_code.upper(),
        service_name=data.service_name,
        is_active=data.is_active,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        report_template_path=data.report_template_path,
        report_cell_mapping=report_cell_mapping_str
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return _build_config_response(config)


@router.patch("/{config_id}", response_model=PartnerServiceConfigResponse)
async def update_config(
    config_id: int,
    data: PartnerServiceConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Update config by ID"""
    config = db.query(PartnerServiceConfig).filter(PartnerServiceConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Serialize dict/list fields to JSON string for SQLite
        if field == 'report_cell_mapping' and value is not None and isinstance(value, dict):
            value = json.dumps(value)
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    return _build_config_response(config)


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Delete config and all related data (cascade)"""
    config = db.query(PartnerServiceConfig).filter(PartnerServiceConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    db.delete(config)
    db.commit()
    
    return {"message": "Config deleted successfully"}


@router.post("/{config_id}/clone", response_model=PartnerServiceConfigResponse)
async def clone_config(
    config_id: int,
    data: PartnerServiceConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Clone a config with all related data (data sources, workflow steps, output configs).

    The new config uses the provided basic info (partner_code, service_code, etc.)
    but copies all data_sources, workflow_steps, and output_configs from the source.
    """
    # Load source config with all relationships
    source = db.query(PartnerServiceConfig).options(
        joinedload(PartnerServiceConfig.data_sources),
        joinedload(PartnerServiceConfig.workflow_steps),
        joinedload(PartnerServiceConfig.output_configs),
    ).filter(PartnerServiceConfig.id == config_id).first()

    if not source:
        raise HTTPException(status_code=404, detail="Source config not found")

    # Validate date overlap (same logic as create)
    existing_configs = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.partner_code == data.partner_code.upper(),
        PartnerServiceConfig.service_code == data.service_code.upper(),
        PartnerServiceConfig.is_active == True,
    ).all()

    new_start = data.valid_from
    new_end = data.valid_to or date(9999, 12, 31)
    for existing in existing_configs:
        existing_start = existing.valid_from
        existing_end = existing.valid_to or date(9999, 12, 31)
        if new_start <= existing_end and existing_start <= new_end:
            raise HTTPException(
                status_code=400,
                detail=f"Khoảng thời gian áp dụng ({data.valid_from} - {data.valid_to or 'vô hạn'}) "
                       f"giao nhau với cấu hình ID {existing.id} "
                       f"({existing.valid_from} - {existing.valid_to or 'vô hạn'})."
            )

    # Create new config with provided basic info
    report_cell_mapping_str = None
    if data.report_cell_mapping:
        report_cell_mapping_str = json.dumps(data.report_cell_mapping) if isinstance(data.report_cell_mapping, dict) else data.report_cell_mapping

    new_config = PartnerServiceConfig(
        partner_code=data.partner_code.upper(),
        partner_name=data.partner_name,
        service_code=data.service_code.upper(),
        service_name=data.service_name,
        is_active=data.is_active,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        report_template_path=source.report_template_path,
        report_cell_mapping=source.report_cell_mapping,
    )
    db.add(new_config)
    db.flush()  # get new_config.id

    # Clone data sources
    for ds in source.data_sources:
        new_ds = DataSourceConfig(
            config_id=new_config.id,
            source_name=ds.source_name,
            source_type=ds.source_type,
            display_name=ds.display_name,
            is_required=ds.is_required,
            display_order=ds.display_order,
            file_config=ds.file_config,
            db_config=ds.db_config,
            sftp_config=ds.sftp_config,
            api_config=ds.api_config,
        )
        db.add(new_ds)

    # Clone workflow steps
    for ws in source.workflow_steps:
        new_ws = WorkflowStep(
            config_id=new_config.id,
            step_order=ws.step_order,
            step_name=ws.step_name,
            left_source=ws.left_source,
            right_source=ws.right_source,
            join_type=ws.join_type,
            matching_rules=ws.matching_rules,
            output_name=ws.output_name,
            output_type=ws.output_type,
            output_columns=ws.output_columns,
            is_final_output=ws.is_final_output,
            status_combine_rules=ws.status_combine_rules,
        )
        db.add(new_ws)

    # Clone output configs
    for oc in source.output_configs:
        new_oc = OutputConfig(
            config_id=new_config.id,
            output_name=oc.output_name,
            display_name=oc.display_name,
            columns_config=oc.columns_config,
            filter_status=oc.filter_status,
            use_for_report=oc.use_for_report,
            display_order=oc.display_order,
        )
        db.add(new_oc)

    db.commit()
    db.refresh(new_config)

    return _build_config_response(new_config)
