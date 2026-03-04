"""
Output Config Endpoints - V2
CRUD operations for output configurations
"""

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import OutputConfig, PartnerServiceConfig
from app.schemas.v2.output import (
    OutputConfigCreate,
    OutputConfigUpdate,
    OutputConfigResponse,
)

router = APIRouter()


@router.get("/by-config/{config_id}", response_model=List[OutputConfigResponse])
async def list_output_configs(
    config_id: int,
    db: Session = Depends(get_db)
):
    """List all output configs for a config"""
    outputs = db.query(OutputConfig).filter(
        OutputConfig.config_id == config_id
    ).order_by(OutputConfig.display_order).all()
    
    return outputs


@router.get("/{output_id}", response_model=OutputConfigResponse)
async def get_output_config(
    output_id: int,
    db: Session = Depends(get_db)
):
    """Get output config by ID"""
    output = db.query(OutputConfig).filter(OutputConfig.id == output_id).first()
    
    if not output:
        raise HTTPException(status_code=404, detail="Output config not found")
    
    return output


@router.post("/", response_model=OutputConfigResponse)
async def create_output_config(
    data: OutputConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new output config"""
    # Verify config exists
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == data.config_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Check for duplicate output name
    existing = db.query(OutputConfig).filter(
        OutputConfig.config_id == data.config_id,
        OutputConfig.output_name == data.output_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Output config {data.output_name} already exists for this config"
        )
    
    # Serialize dict fields to JSON string for Text columns
    columns_config_json = json.dumps(data.columns_config.model_dump(), ensure_ascii=False)
    filter_status_json = None
    if data.filter_status:
        filter_status_json = json.dumps(data.filter_status.model_dump(), ensure_ascii=False)
    
    output = OutputConfig(
        config_id=data.config_id,
        output_name=data.output_name,
        display_name=data.display_name,
        columns_config=columns_config_json,
        filter_status=filter_status_json,
        use_for_report=data.use_for_report,
        display_order=data.display_order
    )
    
    db.add(output)
    db.commit()
    db.refresh(output)
    
    return output


@router.patch("/{output_id}", response_model=OutputConfigResponse)
async def update_output_config(
    output_id: int,
    data: OutputConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update output config by ID"""
    output = db.query(OutputConfig).filter(OutputConfig.id == output_id).first()
    
    if not output:
        raise HTTPException(status_code=404, detail="Output config not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Convert nested models to dicts and serialize to JSON
    if "columns_config" in update_data and update_data["columns_config"]:
        config = update_data["columns_config"]
        if hasattr(config, "model_dump"):
            config = config.model_dump()
        update_data["columns_config"] = json.dumps(config, ensure_ascii=False) if isinstance(config, dict) else config
    if "filter_status" in update_data and update_data["filter_status"]:
        status = update_data["filter_status"]
        if hasattr(status, "model_dump"):
            status = status.model_dump()
        update_data["filter_status"] = json.dumps(status, ensure_ascii=False) if isinstance(status, dict) else status
    
    for field, value in update_data.items():
        setattr(output, field, value)
    
    db.commit()
    db.refresh(output)
    
    return output


@router.delete("/{output_id}")
async def delete_output_config(
    output_id: int,
    db: Session = Depends(get_db)
):
    """Delete output config by ID"""
    output = db.query(OutputConfig).filter(OutputConfig.id == output_id).first()
    
    if not output:
        raise HTTPException(status_code=404, detail="Output config not found")
    
    db.delete(output)
    db.commit()
    
    return {"message": "Output config deleted successfully"}
