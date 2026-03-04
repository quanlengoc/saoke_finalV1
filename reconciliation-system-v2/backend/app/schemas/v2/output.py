"""
Output Config Schemas - V2
Dynamic output configurations for reports
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Literal, Union
from pydantic import BaseModel, Field, field_validator


class OutputColumn(BaseModel):
    """Single output column configuration"""
    name: str = Field(..., description="Column name in output")
    source: str = Field(..., description="B1, B4, computed, auto")
    column: Optional[str] = None  # Source column name
    display_name: Optional[str] = None
    type: Optional[Literal["row_number", "text", "number", "date"]] = None


class OutputColumnsConfig(BaseModel):
    """Configuration for output columns"""
    columns: List[OutputColumn] = []


class FilterStatusConfig(BaseModel):
    """Configuration for filtering by status"""
    match_status: List[str] = []  # e.g., ["NOT_MATCHED", "AMOUNT_MISMATCH"]


class OutputConfigBase(BaseModel):
    """Base schema for output config"""
    output_name: str = Field(..., max_length=50)
    display_name: Optional[str] = Field(None, max_length=100)
    columns_config: OutputColumnsConfig
    filter_status: Optional[FilterStatusConfig] = None
    use_for_report: bool = True
    display_order: int = 0


class OutputConfigCreate(OutputConfigBase):
    """Schema for creating a new output config"""
    config_id: int = Field(..., description="Parent config ID")


class OutputConfigUpdate(BaseModel):
    """Schema for updating output config - all fields optional"""
    display_name: Optional[str] = None
    columns_config: Optional[OutputColumnsConfig] = None
    filter_status: Optional[FilterStatusConfig] = None
    use_for_report: Optional[bool] = None
    display_order: Optional[int] = None


class OutputConfigResponse(BaseModel):
    """Response schema with all fields"""
    id: int
    config_id: int
    output_name: str
    display_name: Optional[str]
    columns_config: Dict[str, Any]  # Return as dict
    filter_status: Optional[Dict[str, Any]]
    use_for_report: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
    
    @field_validator('columns_config', 'filter_status', mode='before')
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
