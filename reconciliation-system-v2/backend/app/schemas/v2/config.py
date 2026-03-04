"""
Partner Service Config Schemas - V2
Simplified config with relationships to dynamic tables
"""

import json
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class PartnerServiceConfigBase(BaseModel):
    """Base schema for partner service config"""
    partner_code: str = Field(..., max_length=50)
    partner_name: str = Field(..., max_length=255)
    service_code: str = Field(..., max_length=50)
    service_name: str = Field(..., max_length=255)
    is_active: bool = True
    valid_from: date
    valid_to: Optional[date] = None
    report_template_path: Optional[str] = None
    report_cell_mapping: Optional[Dict[str, Any]] = None


class PartnerServiceConfigCreate(PartnerServiceConfigBase):
    """Schema for creating a new config"""
    pass


class PartnerServiceConfigUpdate(BaseModel):
    """Schema for updating config - all fields optional"""
    partner_name: Optional[str] = None
    service_name: Optional[str] = None
    is_active: Optional[bool] = None
    valid_to: Optional[date] = None
    report_template_path: Optional[str] = None
    report_cell_mapping: Optional[Dict[str, Any]] = None


class DataSourceSummary(BaseModel):
    """Summary of data source for listing"""
    source_name: str
    source_type: str
    display_name: Optional[str]
    is_required: bool


class WorkflowStepSummary(BaseModel):
    """Summary of workflow step for listing"""
    step_order: int
    step_name: str
    left_source: str
    right_source: str
    output_name: str
    is_final_output: bool


class OutputConfigSummary(BaseModel):
    """Summary of output config for listing"""
    output_name: str
    display_name: Optional[str]
    use_for_report: bool


class PartnerServiceConfigResponse(PartnerServiceConfigBase):
    """Response schema with all relationships"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    # Related data summaries
    data_sources: List[DataSourceSummary] = []
    workflow_steps: List[WorkflowStepSummary] = []
    output_configs: List[OutputConfigSummary] = []
    
    @field_validator('report_cell_mapping', mode='before')
    @classmethod
    def parse_json_config(cls, v):
        """Parse JSON string to dict if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v
    
    class Config:
        from_attributes = True


class PartnerServiceConfigList(BaseModel):
    """List response with pagination"""
    items: List[PartnerServiceConfigResponse]
    total: int
    page: int
    page_size: int
