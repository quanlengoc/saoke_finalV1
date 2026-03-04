"""
Configuration management endpoints (Admin only)
CRUD for partner/service configurations
"""

import json
from typing import Any, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_admin
from app.models import User, PartnerServiceConfig
from app.schemas.config import (
    PartnerServiceConfigCreate as ConfigCreate, 
    PartnerServiceConfigUpdate as ConfigUpdate, 
    PartnerServiceConfigResponse as ConfigResponse, 
    PartnerServiceConfigResponse as ConfigListResponse
)


router = APIRouter()


@router.get("/", response_model=List[ConfigListResponse])
async def list_configs(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    include_inactive: bool = Query(default=False),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    List all configurations (Admin only)
    
    Can filter by partner_code and/or service_code
    """
    query = db.query(PartnerServiceConfig)
    
    if partner_code:
        query = query.filter(PartnerServiceConfig.partner_code == partner_code)
    
    if service_code:
        query = query.filter(PartnerServiceConfig.service_code == service_code)
    
    if not include_inactive:
        query = query.filter(PartnerServiceConfig.is_active == True)
    
    configs = query.order_by(
        PartnerServiceConfig.partner_code,
        PartnerServiceConfig.service_code,
        PartnerServiceConfig.valid_from.desc()
    ).offset(skip).limit(limit).all()
    
    return configs


@router.post("/", response_model=ConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    request: ConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Create a new configuration (Admin only)
    
    Note: Configs have valid_from/valid_to for versioning.
    Multiple configs can exist for same partner/service with different date ranges.
    """
    # Check for overlapping configs
    overlap_query = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.partner_code == request.partner_code,
        PartnerServiceConfig.service_code == request.service_code,
        PartnerServiceConfig.is_active == True
    )
    
    existing_configs = overlap_query.all()
    
    for existing in existing_configs:
        # Check date overlap
        existing_end = existing.valid_to or date(9999, 12, 31)
        new_end = request.valid_to or date(9999, 12, 31)
        
        if not (request.valid_from > existing_end or new_end < existing.valid_from):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date range overlaps with existing config ID {existing.id} "
                       f"({existing.valid_from} to {existing.valid_to})"
            )
    
    config = PartnerServiceConfig(
        partner_code=request.partner_code,
        partner_name=request.partner_name,
        service_code=request.service_code,
        service_name=request.service_name,
        valid_from=request.valid_from,
        valid_to=request.valid_to,
        file_b1_config=request.file_b1_config if isinstance(request.file_b1_config, str) else json.dumps(request.file_b1_config),
        file_b2_config=request.file_b2_config if isinstance(request.file_b2_config, str) else json.dumps(request.file_b2_config) if request.file_b2_config else None,
        file_b3_config=request.file_b3_config if isinstance(request.file_b3_config, str) else json.dumps(request.file_b3_config) if request.file_b3_config else None,
        data_b4_config=request.data_b4_config if isinstance(request.data_b4_config, str) else json.dumps(request.data_b4_config),
        matching_rules_b1b4=request.matching_rules_b1b4 if isinstance(request.matching_rules_b1b4, str) else json.dumps(request.matching_rules_b1b4),
        matching_rules_b1b2=request.matching_rules_b1b2 if isinstance(request.matching_rules_b1b2, str) else json.dumps(request.matching_rules_b1b2) if request.matching_rules_b1b2 else None,
        matching_rules_b3a1=request.matching_rules_b3a1 if isinstance(request.matching_rules_b3a1, str) else json.dumps(request.matching_rules_b3a1) if request.matching_rules_b3a1 else None,
        status_combine_rules=request.status_combine_rules if isinstance(request.status_combine_rules, str) else json.dumps(request.status_combine_rules),
        output_a1_config=request.output_a1_config if isinstance(request.output_a1_config, str) else json.dumps(request.output_a1_config),
        output_a2_config=request.output_a2_config if isinstance(request.output_a2_config, str) else json.dumps(request.output_a2_config) if request.output_a2_config else None,
        report_template_path=request.report_template_path,
        report_cell_mapping=request.report_cell_mapping if isinstance(request.report_cell_mapping, str) else json.dumps(request.report_cell_mapping) if request.report_cell_mapping else None,
        is_active=True
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return config


@router.get("/{config_id}", response_model=ConfigResponse)
async def get_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Get a specific configuration by ID (Admin only)
    """
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    return config


@router.put("/{config_id}", response_model=ConfigResponse)
async def update_config(
    config_id: int,
    request: ConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Update a configuration (Admin only)
    """
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    
    print(f"[CONFIG UPDATE] ID={config_id}, Fields to update: {list(update_data.keys())}")
    
    # Fields that need JSON serialization
    json_fields = [
        'file_b1_config', 'file_b2_config', 'file_b3_config',
        'data_b4_config', 'matching_rules_b1b4', 'matching_rules_b1b2',
        'matching_rules_b3a1', 'status_combine_rules', 'output_a1_config',
        'output_a2_config', 'report_cell_mapping'
    ]
    
    for field, value in update_data.items():
        if hasattr(config, field):
            if field in json_fields and value is not None:
                # Serialize dict to JSON string
                if isinstance(value, dict):
                    print(f"[CONFIG UPDATE] Setting {field} (dict -> JSON)")
                    setattr(config, field, json.dumps(value))
                else:
                    print(f"[CONFIG UPDATE] Setting {field} (as-is)")
                    setattr(config, field, value)
            else:
                setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    print(f"[CONFIG UPDATE] Saved successfully. matching_rules_b1b4 first 200 chars: {str(config.matching_rules_b1b4)[:200]}")
    
    return config


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    hard_delete: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Delete a configuration (Admin only)
    
    By default, soft delete (set is_active=False).
    Use hard_delete=True to permanently remove.
    """
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    if hard_delete:
        db.delete(config)
    else:
        config.is_active = False
    
    db.commit()
    
    return {"message": "Configuration deleted successfully"}


@router.post("/{config_id}/duplicate", response_model=ConfigResponse)
async def duplicate_config(
    config_id: int,
    new_valid_from: date = Query(...),
    new_valid_to: date = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin)
) -> Any:
    """
    Duplicate a configuration with new date range (Admin only)
    
    Useful for creating new version when partner file format changes.
    """
    original = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == config_id
    ).first()
    
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # Create copy
    new_config = PartnerServiceConfig(
        partner_code=original.partner_code,
        partner_name=original.partner_name,
        service_code=original.service_code,
        service_name=original.service_name,
        valid_from=new_valid_from,
        valid_to=new_valid_to,
        file_b1_config=original.file_b1_config,
        file_b2_config=original.file_b2_config,
        file_b3_config=original.file_b3_config,
        data_b4_config=original.data_b4_config,
        matching_rules_b1b4=original.matching_rules_b1b4,
        matching_rules_b1b2=original.matching_rules_b1b2,
        matching_rules_b3a1=original.matching_rules_b3a1,
        status_combine_rules=original.status_combine_rules,
        output_a1_config=original.output_a1_config,
        output_a2_config=original.output_a2_config,
        report_template_path=original.report_template_path,
        report_cell_mapping=original.report_cell_mapping,
        is_active=True
    )
    
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return new_config
