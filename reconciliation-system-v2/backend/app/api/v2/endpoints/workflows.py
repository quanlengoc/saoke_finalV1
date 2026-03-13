"""
Workflow Step Endpoints - V2
CRUD operations for workflow steps
"""

import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin
from app.models import WorkflowStep, PartnerServiceConfig, User
from app.schemas.v2.workflow import (
    WorkflowStepCreate,
    WorkflowStepUpdate,
    WorkflowStepResponse,
)

router = APIRouter()


@router.get("/by-config/{config_id}", response_model=List[WorkflowStepResponse])
async def list_workflow_steps(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all workflow steps for a config in order"""
    steps = db.query(WorkflowStep).filter(
        WorkflowStep.config_id == config_id
    ).order_by(WorkflowStep.step_order).all()
    
    return steps


@router.get("/{step_id}", response_model=WorkflowStepResponse)
async def get_workflow_step(
    step_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get workflow step by ID"""
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    
    return step


@router.post("/", response_model=WorkflowStepResponse)
async def create_workflow_step(
    data: WorkflowStepCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Create a new workflow step"""
    # Verify config exists
    config = db.query(PartnerServiceConfig).filter(
        PartnerServiceConfig.id == data.config_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Check for duplicate step order - SKIP này để cho phép frontend quản lý order
    # Thay vào đó, cập nhật step_order của các step khác nếu cần
    existing = db.query(WorkflowStep).filter(
        WorkflowStep.config_id == data.config_id,
        WorkflowStep.step_order == data.step_order
    ).first()
    
    if existing:
        # Shift step_order của các step có order >= data.step_order lên 1
        db.query(WorkflowStep).filter(
            WorkflowStep.config_id == data.config_id,
            WorkflowStep.step_order >= data.step_order
        ).update({WorkflowStep.step_order: WorkflowStep.step_order + 100})  # Shift lớn để tránh conflict
        db.commit()
    
    # Serialize dict fields to JSON string for Text columns
    matching_rules = data.matching_rules
    if hasattr(matching_rules, 'model_dump'):
        matching_rules = matching_rules.model_dump()
    matching_rules_json = json.dumps(matching_rules, ensure_ascii=False) if isinstance(matching_rules, dict) else matching_rules
    
    status_combine_rules_json = None
    if data.status_combine_rules:
        scr = data.status_combine_rules
        if hasattr(scr, 'model_dump'):
            scr = scr.model_dump()
        status_combine_rules_json = json.dumps(scr, ensure_ascii=False) if isinstance(scr, dict) else scr
    
    output_columns_json = None
    if data.output_columns:
        output_columns_json = json.dumps(data.output_columns, ensure_ascii=False) if isinstance(data.output_columns, list) else data.output_columns
    
    step = WorkflowStep(
        config_id=data.config_id,
        step_order=data.step_order,
        step_name=data.step_name,
        left_source=data.left_source,
        right_source=data.right_source,
        join_type=data.join_type,
        matching_rules=matching_rules_json,
        output_name=data.output_name,
        output_type=data.output_type or 'intermediate',
        output_columns=output_columns_json,
        is_final_output=data.is_final_output,
        status_combine_rules=status_combine_rules_json
    )
    
    db.add(step)
    db.commit()
    db.refresh(step)
    
    db.add(step)
    db.commit()
    db.refresh(step)
    
    return step


@router.patch("/{step_id}", response_model=WorkflowStepResponse)
async def update_workflow_step(
    step_id: int,
    data: WorkflowStepUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Update workflow step by ID"""
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Convert nested models to dicts and serialize to JSON
    json_fields = ["matching_rules", "status_combine_rules", "output_columns"]
    for field in json_fields:
        if field in update_data and update_data[field] is not None:
            val = update_data[field]
            if hasattr(val, "model_dump"):
                val = val.model_dump()
            if isinstance(val, (dict, list)):
                update_data[field] = json.dumps(val, ensure_ascii=False)
    
    for field, value in update_data.items():
        setattr(step, field, value)
    
    db.commit()
    db.refresh(step)
    
    return step


@router.delete("/{step_id}")
async def delete_workflow_step(
    step_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Delete workflow step by ID"""
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
    
    if not step:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    
    db.delete(step)
    db.commit()
    
    return {"message": "Workflow step deleted successfully"}


@router.post("/reorder/{config_id}")
async def reorder_steps(
    config_id: int,
    step_orders: List[dict],  # [{"step_id": 1, "step_order": 1}, ...]
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Reorder workflow steps for a config"""
    for item in step_orders:
        step = db.query(WorkflowStep).filter(
            WorkflowStep.id == item["step_id"],
            WorkflowStep.config_id == config_id
        ).first()
        
        if step:
            step.step_order = item["step_order"]
    
    db.commit()
    
    return {"message": "Steps reordered successfully"}
