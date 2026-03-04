"""
Configuration schemas for partner/service config
"""

import json
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# File Config Schemas
# ============================================================================

class FileColumnMapping(BaseModel):
    """Column mapping for file reading"""
    # Key = internal column name, Value = Excel column (A, B, C...)
    columns: Dict[str, str] = Field(default_factory=dict)


class FileConfig(BaseModel):
    """Configuration for reading a file"""
    header_row: int = Field(1, ge=1, description="Row number containing headers (1-based)")
    data_start_row: int = Field(2, ge=1, description="Row number where data starts (1-based)")
    columns: Dict[str, str] = Field(..., description="Column mapping: internal_name -> Excel column")
    sheet_name: Optional[str] = Field(None, description="Sheet name (for Excel files)")


# ============================================================================
# B4 Data Config Schema
# ============================================================================

class DataB4Config(BaseModel):
    """Configuration for B4 data source"""
    db_connection: str = Field(..., description="Database connection name from config.ini")
    sql_file: str = Field(..., description="Path to SQL file (relative to sql_templates/)")
    sql_params: Dict[str, Any] = Field(default_factory=dict, description="SQL parameters")
    mock_file: Optional[str] = Field(None, description="Mock CSV file for testing")


# ============================================================================
# Matching Rules Schemas
# ============================================================================

class MatchingRule(BaseModel):
    """Single matching rule"""
    rule_name: str
    type: str = Field("expression", description="Rule type: expression")
    expression: str = Field(..., description="Pandas expression for matching")


class MatchingRulesConfig(BaseModel):
    """Matching rules configuration"""
    match_type: str = Field("expression", description="expression or custom_module")
    rules: List[MatchingRule] = Field(default_factory=list)
    # For custom_module type
    module_path: Optional[str] = None
    function_name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    # Status logic
    status_logic: Dict[str, str] = Field(
        default_factory=lambda: {
            "all_match": "MATCHED",
            "key_match_amount_mismatch": "MISMATCH",
            "no_key_match": "NOT_FOUND"
        }
    )


# ============================================================================
# Status Combine Rules Schema
# ============================================================================

class StatusCombineRule(BaseModel):
    """Single status combination rule"""
    b1b4: str
    b1b2: str
    final: str


class StatusCombineConfig(BaseModel):
    """Status combination configuration"""
    rules: List[StatusCombineRule] = Field(default_factory=list)
    default: str = "UNKNOWN"


# ============================================================================
# Output Column Config Schemas
# ============================================================================

class OutputColumn(BaseModel):
    """Single output column configuration"""
    name: str = Field(..., description="Output column name")
    source: str = Field(..., description="Source: B1, B2, B4, A1, B3, or _SYSTEM")
    column: str = Field(..., description="Source column name")
    default: Optional[Any] = Field(None, description="Default value if not found")


class OutputConfig(BaseModel):
    """Output columns configuration"""
    columns: List[OutputColumn] = Field(default_factory=list)


# ============================================================================
# Report Config Schemas
# ============================================================================

class SqlCell(BaseModel):
    """SQL query mapped to a cell"""
    cell: str = Field(..., description="Cell reference (e.g., C10)")
    sql: str = Field(..., description="SQL query to execute")


class ReportSheet(BaseModel):
    """Single sheet configuration in report"""
    sheet_name: str
    static_cells: Dict[str, str] = Field(default_factory=dict, description="Static values: cell -> value")
    sql_cells: List[SqlCell] = Field(default_factory=list, description="SQL-based values")
    data_start_cell: Optional[str] = Field(None, description="For data tables: starting cell")
    data_sql: Optional[str] = Field(None, description="SQL query for table data")
    columns: List[str] = Field(default_factory=list, description="Column letters for data table")


class ReportCellMapping(BaseModel):
    """Report cell mapping configuration"""
    sheets: List[ReportSheet] = Field(default_factory=list)


# ============================================================================
# Partner Service Config Schemas
# ============================================================================

class PartnerServiceConfigBase(BaseModel):
    """Base schema for partner service config"""
    partner_code: str = Field(..., min_length=1, max_length=50)
    partner_name: str = Field(..., min_length=1, max_length=255)
    service_code: str = Field(..., min_length=1, max_length=50)
    service_name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    valid_from: date
    valid_to: Optional[date] = None


class PartnerServiceConfigCreate(PartnerServiceConfigBase):
    """Schema for creating a config"""
    file_b1_config: Dict[str, Any]
    file_b2_config: Optional[Dict[str, Any]] = None
    file_b3_config: Optional[Dict[str, Any]] = None
    data_b4_config: Dict[str, Any]
    matching_rules_b1b4: Dict[str, Any]
    matching_rules_b1b2: Optional[Dict[str, Any]] = None
    matching_rules_b3a1: Optional[Dict[str, Any]] = None
    status_combine_rules: Dict[str, Any]
    output_a1_config: Dict[str, Any]
    output_a2_config: Optional[Dict[str, Any]] = None
    report_template_path: Optional[str] = None
    report_cell_mapping: Optional[Dict[str, Any]] = None


class PartnerServiceConfigUpdate(BaseModel):
    """Schema for updating a config"""
    partner_name: Optional[str] = None
    service_name: Optional[str] = None
    is_active: Optional[bool] = None
    valid_to: Optional[date] = None
    file_b1_config: Optional[Dict[str, Any]] = None
    file_b2_config: Optional[Dict[str, Any]] = None
    file_b3_config: Optional[Dict[str, Any]] = None
    data_b4_config: Optional[Dict[str, Any]] = None
    matching_rules_b1b4: Optional[Dict[str, Any]] = None
    matching_rules_b1b2: Optional[Dict[str, Any]] = None
    matching_rules_b3a1: Optional[Dict[str, Any]] = None
    status_combine_rules: Optional[Dict[str, Any]] = None
    output_a1_config: Optional[Dict[str, Any]] = None
    output_a2_config: Optional[Dict[str, Any]] = None
    report_template_path: Optional[str] = None
    report_cell_mapping: Optional[Dict[str, Any]] = None


class PartnerServiceConfigResponse(PartnerServiceConfigBase):
    """Schema for config response"""
    id: int
    file_b1_config: Dict[str, Any]
    file_b2_config: Optional[Dict[str, Any]]
    file_b3_config: Optional[Dict[str, Any]]
    data_b4_config: Dict[str, Any]
    matching_rules_b1b4: Dict[str, Any]
    matching_rules_b1b2: Optional[Dict[str, Any]]
    matching_rules_b3a1: Optional[Dict[str, Any]]
    status_combine_rules: Dict[str, Any]
    output_a1_config: Dict[str, Any]
    output_a2_config: Optional[Dict[str, Any]]
    report_template_path: Optional[str]
    report_cell_mapping: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    # Validators to parse JSON strings from database
    @field_validator('file_b1_config', 'data_b4_config', 'matching_rules_b1b4', 
                     'status_combine_rules', 'output_a1_config', mode='before')
    @classmethod
    def parse_json_required(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @field_validator('file_b2_config', 'file_b3_config', 'matching_rules_b1b2',
                     'matching_rules_b3a1', 'output_a2_config', 'report_cell_mapping', mode='before')
    @classmethod
    def parse_json_optional(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    class Config:
        from_attributes = True


# ============================================================================
# Simple Partner/Service List
# ============================================================================

class PartnerServiceSimple(BaseModel):
    """Simple partner/service info for dropdown lists"""
    partner_code: str
    partner_name: str
    service_code: str
    service_name: str
    
    class Config:
        from_attributes = True
