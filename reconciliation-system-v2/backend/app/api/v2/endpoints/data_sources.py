"""
Data Source Config Endpoints - V2
CRUD operations for data sources
"""

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin
from app.models import DataSourceConfig, PartnerServiceConfig, User
from app.schemas.v2.data_source import (
    DataSourceConfigCreate,
    DataSourceConfigUpdate,
    DataSourceConfigResponse,
)

router = APIRouter()


@router.get("/by-config/{config_id}", response_model=List[DataSourceConfigResponse])
async def list_data_sources(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all data sources for a config"""
    data_sources = db.query(DataSourceConfig).filter(
        DataSourceConfig.config_id == config_id
    ).order_by(DataSourceConfig.display_order).all()
    
    return data_sources


@router.get("/{source_id}", response_model=DataSourceConfigResponse)
async def get_data_source(
    source_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get data source by ID"""
    source = db.query(DataSourceConfig).filter(DataSourceConfig.id == source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    return source


@router.post("/", response_model=DataSourceConfigResponse)
async def create_data_source(
    data: DataSourceConfigCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Create a new data source"""
    # Verify config exists
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == data.config_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Check for duplicate source name in same config
    existing = db.query(DataSourceConfig).filter(
        DataSourceConfig.config_id == data.config_id,
        DataSourceConfig.source_name == data.source_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Data source {data.source_name} already exists for this config"
        )
    
    # Serialize dict fields to JSON string for Text columns
    file_config = json.dumps(data.file_config, ensure_ascii=False) if isinstance(data.file_config, dict) else data.file_config
    db_config = json.dumps(data.db_config, ensure_ascii=False) if isinstance(data.db_config, dict) else data.db_config
    sftp_config = json.dumps(data.sftp_config, ensure_ascii=False) if isinstance(data.sftp_config, dict) else data.sftp_config
    api_config = json.dumps(data.api_config, ensure_ascii=False) if isinstance(data.api_config, dict) else data.api_config
    
    source = DataSourceConfig(
        config_id=data.config_id,
        source_name=data.source_name,
        source_type=data.source_type,
        display_name=data.display_name,
        is_required=data.is_required,
        display_order=data.display_order,
        file_config=file_config,
        db_config=db_config,
        sftp_config=sftp_config,
        api_config=api_config
    )
    
    db.add(source)
    db.commit()
    db.refresh(source)
    
    return source


@router.patch("/{source_id}", response_model=DataSourceConfigResponse)
async def update_data_source(
    source_id: int,
    data: DataSourceConfigUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Update data source by ID"""
    source = db.query(DataSourceConfig).filter(DataSourceConfig.id == source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Serialize dict fields to JSON string for Text columns
    json_fields = ['file_config', 'db_config', 'sftp_config', 'api_config']
    for field in json_fields:
        if field in update_data and update_data[field] is not None:
            if isinstance(update_data[field], dict):
                update_data[field] = json.dumps(update_data[field], ensure_ascii=False)
    
    for field, value in update_data.items():
        setattr(source, field, value)
    
    db.commit()
    db.refresh(source)
    
    return source


@router.delete("/{source_id}")
async def delete_data_source(
    source_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Delete data source by ID"""
    source = db.query(DataSourceConfig).filter(DataSourceConfig.id == source_id).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    
    db.delete(source)
    db.commit()
    
    return {"message": "Data source deleted successfully"}
