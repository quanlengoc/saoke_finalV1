"""
Reconciliation Schemas - V2
Request/Response for reconciliation process
"""

from datetime import date, datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ReconciliationStatus(str, Enum):
    """Status of reconciliation batch"""
    UPLOADING = "UPLOADING"                 # Khởi tạo
    PROCESSING = "PROCESSING"               # Đang xử lý
    COMPLETED = "COMPLETED"                 # Hoàn tất thành công
    ERROR = "ERROR"                         # Hoàn tất thất bại
    CANCELLED = "CANCELLED"                 # Tạm dừng
    PENDING_APPROVAL = "PENDING_APPROVAL"   # Chờ phê duyệt
    APPROVED = "APPROVED"                   # Đã phê duyệt
    # Legacy statuses (backward compat for old DB data)
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class ReconciliationRequest(BaseModel):
    """Request to start reconciliation"""
    config_id: int = Field(..., description="Config ID to use")
    period_from: date
    period_to: date
    
    # Cycle params for database queries
    cycle_params: Optional[Dict[str, Any]] = None


class FileUploadInfo(BaseModel):
    """Info about uploaded file"""
    source_name: str  # B1, B2, B3
    file_name: str
    file_path: str
    row_count: Optional[int] = None


class StepResult(BaseModel):
    """Result of a workflow step"""
    step_order: int
    step_name: str
    left_source: str
    right_source: str
    output_name: str
    row_count: int
    matched_count: int
    not_found_count: int
    mismatch_count: int
    execution_time_seconds: float


class OutputResult(BaseModel):
    """Result for a final output"""
    output_name: str
    display_name: Optional[str]
    row_count: int
    file_path: Optional[str] = None
    status_counts: Dict[str, int] = {}


class DataPreview(BaseModel):
    """Preview of first N rows of a data source after parsing"""
    source_name: str
    display_name: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    total_rows: int


class StepLogEntry(BaseModel):
    """A single step log entry from workflow execution"""
    step: str
    time: str
    status: str  # start, ok, warning, error
    message: str
    data_preview: Optional[DataPreview] = None


class ReconciliationResponse(BaseModel):
    """Response after reconciliation"""
    batch_id: str
    config_id: int
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: ReconciliationStatus
    
    # Files uploaded
    files_uploaded: List[FileUploadInfo] = []
    
    # Step-by-step execution logs
    step_logs: List[StepLogEntry] = []
    
    # Step results
    step_results: List[StepResult] = []
    
    # Final outputs
    outputs: List[OutputResult] = []
    
    # Timing
    total_time_seconds: float = 0.0
    created_at: datetime
    
    # Error if failed
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class ReconciliationListItem(BaseModel):
    """Item in reconciliation list"""
    batch_id: str
    config_id: Optional[int] = None
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: ReconciliationStatus
    error_message: Optional[str] = None
    created_by_name: str
    created_at: datetime
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None


class ReconciliationList(BaseModel):
    """List of reconciliations with pagination"""
    items: List[ReconciliationListItem]
    total: int
    page: int
    page_size: int
