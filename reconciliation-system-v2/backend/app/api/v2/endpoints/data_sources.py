"""
Data Source Config Endpoints - V2
CRUD operations for data sources
"""

import json
import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_config_reader, get_storage_path
from app.api.deps import get_current_user, get_current_admin
from app.models import DataSourceConfig, PartnerServiceConfig, User
from app.schemas.v2.data_source import (
    DataSourceConfigCreate,
    DataSourceConfigUpdate,
    DataSourceConfigResponse,
)

router = APIRouter()


@router.get("/db-connections")
async def list_db_connections(_: User = Depends(get_current_admin)):
    """List available database connections from config.ini (excluding app DB)"""
    reader = get_config_reader()
    connections = [c for c in reader.list_database_connections() if c != 'app']
    return {"connections": connections}


@router.get("/sql-templates")
async def list_sql_templates(_: User = Depends(get_current_admin)):
    """List available SQL template files in storage/sql_templates/"""
    sql_dir = get_storage_path('sql_templates')
    files = []
    for root, _, filenames in os.walk(sql_dir):
        for f in filenames:
            if f.endswith('.sql'):
                rel_path = os.path.relpath(os.path.join(root, f), sql_dir).replace('\\', '/')
                files.append(rel_path)
    files.sort()
    return {"files": files}


@router.post("/sql-templates/upload")
async def upload_sql_template(
    file: UploadFile = File(...),
    _: User = Depends(get_current_admin),
):
    """Upload a new SQL template file to storage/sql_templates/shared/"""
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file .sql")

    # Sanitize filename
    safe_name = file.filename.replace('..', '').replace('/', '').replace('\\', '')
    sql_dir = get_storage_path('sql_templates') / 'shared'
    sql_dir.mkdir(parents=True, exist_ok=True)
    dest = sql_dir / safe_name

    content = await file.read()
    # Validate: only allow SELECT/WITH statements
    from app.core.sql_security import SqlGuard, SqlSecurityError
    try:
        text = content.decode('utf-8-sig').strip()
        # Template may have {params}, validate structure (not the params themselves)
        # Just check it starts with SELECT/WITH
        import re
        if not re.match(r'^\s*(--|/\*|SELECT|WITH)\b', text, re.IGNORECASE | re.MULTILINE):
            raise SqlSecurityError("File SQL phải bắt đầu bằng SELECT hoặc WITH", violation_type="blocked_statement")
    except SqlSecurityError as e:
        raise HTTPException(status_code=400, detail=f"File SQL không hợp lệ: {e}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File không phải text UTF-8")

    with open(dest, 'wb') as f:
        f.write(content)

    return {"file": f"shared/{safe_name}", "message": "Upload thành công"}


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
