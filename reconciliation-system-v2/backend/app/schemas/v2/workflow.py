"""
Workflow Step Schemas - V2
Dynamic workflow step configurations
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal, Union
from pydantic import BaseModel, Field, field_validator


JoinType = Literal["left", "inner", "right", "outer"]


class MatchingRule(BaseModel):
    """Individual matching rule"""
    type: Literal["key_match", "amount_match", "custom"]
    left_expr: Optional[str] = None  # For key_match
    right_expr: Optional[str] = None  # For key_match
    left_col: Optional[str] = None   # For amount_match
    right_col: Optional[str] = None  # For amount_match
    tolerance: Optional[float] = 0   # For amount_match


class MatchingRulesConfig(BaseModel):
    """Complete matching rules configuration"""
    match_type: Literal["expression", "custom_module"] = "expression"
    rules: List[MatchingRule] = []
    status_logic: Dict[str, str] = {}
    custom_module: Optional[str] = None  # For custom_module mode


class StatusCombineRule(BaseModel):
    """Rule for combining statuses from multiple steps"""
    conditions: Dict[str, str]  # e.g., {"b1b4": "MATCHED", "b1b2": "NO_REFUND"}
    final: str  # e.g., "OK"


class StatusCombineConfig(BaseModel):
    """Configuration for combining statuses"""
    rules: List[StatusCombineRule] = []
    default: str = "UNKNOWN"


class WorkflowStepBase(BaseModel):
    """Base schema for workflow step"""
    step_order: int = Field(..., ge=1)
    step_name: str = Field(..., max_length=100)
    left_source: str = Field(..., max_length=50, description="B1, A1, etc.")
    right_source: str = Field(..., max_length=50, description="B4, B2, etc.")
    join_type: JoinType = "left"
    matching_rules: Dict[str, Any]  # Flexible structure - can be MatchingRulesConfig or key_match/amount_match format
    output_name: str = Field(..., max_length=50)
    output_type: Optional[str] = "intermediate"  # intermediate, report
    output_columns: Optional[List[Dict[str, Any]]] = None  # Output columns config
    is_final_output: bool = False
    status_combine_rules: Optional[Dict[str, Any]] = None  # Flexible structure


class WorkflowStepCreate(WorkflowStepBase):
    """Schema for creating a new workflow step"""
    config_id: int = Field(..., description="Parent config ID")


class WorkflowStepUpdate(BaseModel):
    """Schema for updating workflow step - all fields optional"""
    step_order: Optional[int] = None
    step_name: Optional[str] = None
    left_source: Optional[str] = None
    right_source: Optional[str] = None
    join_type: Optional[JoinType] = None
    matching_rules: Optional[Dict[str, Any]] = None  # Flexible structure
    output_name: Optional[str] = None
    output_type: Optional[str] = None  # intermediate, report
    output_columns: Optional[List[Dict[str, Any]]] = None  # Output columns config
    is_final_output: Optional[bool] = None
    status_combine_rules: Optional[Dict[str, Any]] = None  # Flexible structure


class WorkflowStepResponse(BaseModel):
    """Response schema with all fields"""
    id: int
    config_id: int
    step_order: int
    step_name: str
    left_source: str
    right_source: str
    join_type: str
    matching_rules: Dict[str, Any]  # Return as dict for flexibility
    output_name: str
    output_type: Optional[str] = "intermediate"
    output_columns: Optional[List[Dict[str, Any]]] = None
    is_final_output: bool
    status_combine_rules: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('matching_rules', 'status_combine_rules', 'output_columns', mode='before')
    @classmethod
    def parse_json_config(cls, v):
        """Parse JSON string to dict/list if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {} if '{' in v else []
        return v
    
    class Config:
        from_attributes = True
