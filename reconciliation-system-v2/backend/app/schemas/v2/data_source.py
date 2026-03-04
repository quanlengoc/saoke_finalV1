"""
Data Source Config Schemas - V2
Dynamic data source configurations
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator


SourceType = Literal["FILE_UPLOAD", "DATABASE", "SFTP", "API"]


class DataSourceConfigBase(BaseModel):
    """Base schema for data source config"""
    source_name: str = Field(..., max_length=20, description="B1, B2, B3, B4, etc.")
    source_type: SourceType = Field(..., description="FILE_UPLOAD, DATABASE, SFTP, API")
    display_name: Optional[str] = Field(None, max_length=100)
    is_required: bool = False
    display_order: int = 0
    
    # Type-specific configs
    file_config: Optional[Dict[str, Any]] = None
    db_config: Optional[Dict[str, Any]] = None
    sftp_config: Optional[Dict[str, Any]] = None
    api_config: Optional[Dict[str, Any]] = None
    
    @field_validator('source_name')
    @classmethod
    def uppercase_source_name(cls, v: str) -> str:
        return v.upper()


class DataSourceConfigCreate(DataSourceConfigBase):
    """Schema for creating a new data source"""
    config_id: int = Field(..., description="Parent config ID")


class DataSourceConfigUpdate(BaseModel):
    """Schema for updating data source - all fields optional"""
    display_name: Optional[str] = None
    is_required: Optional[bool] = None
    display_order: Optional[int] = None
    file_config: Optional[Dict[str, Any]] = None
    db_config: Optional[Dict[str, Any]] = None
    sftp_config: Optional[Dict[str, Any]] = None
    api_config: Optional[Dict[str, Any]] = None


class DataSourceConfigResponse(BaseModel):
    """Response schema with all fields"""
    id: int
    config_id: int
    source_name: str
    source_type: str
    display_name: Optional[str] = None
    is_required: bool = False
    display_order: int = 0
    file_config: Optional[Dict[str, Any]] = None
    db_config: Optional[Dict[str, Any]] = None
    sftp_config: Optional[Dict[str, Any]] = None
    api_config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('file_config', 'db_config', 'sftp_config', 'api_config', mode='before')
    @classmethod
    def parse_json_config(cls, v):
        """Parse JSON string to dict if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v
    
    class Config:
        from_attributes = True


# Example file_config structure
FILE_CONFIG_EXAMPLE = {
    "header_row": 1,
    "data_start_row": 2,
    "sheet_name": "Sheet1",
    "columns": {
        "txn_id": "A",
        "amount": "C",
        "date": "B"
    },
    "transforms": {
        "txn_id": ".str.strip().str.upper()",
        "amount": ".str.replace(',', '').astype(float)"
    }
}

# Example db_config structure
DB_CONFIG_EXAMPLE = {
    "db_connection": "vnptmoney_main",
    "sql_file": "shared/query.sql",
    "sql_params": {},
    "mock_file": "mock_data.csv"
}
