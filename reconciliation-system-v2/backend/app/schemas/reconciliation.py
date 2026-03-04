"""
Reconciliation schemas
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ============================================================================
# Reconciliation Request Schemas
# ============================================================================

class ReconciliationStartRequest(BaseModel):
    """Schema for starting a new reconciliation"""
    partner_code: str = Field(..., min_length=1, max_length=50)
    service_code: str = Field(..., min_length=1, max_length=50)
    period_from: date
    period_to: date


class ReconciliationRunRequest(BaseModel):
    """Schema for running reconciliation on an existing batch"""
    batch_id: str


# ============================================================================
# Step Log Schema
# ============================================================================

class StepLog(BaseModel):
    """Single step log entry"""
    step: str
    time: str
    status: str  # ok, error, warning
    message: str


# ============================================================================
# Summary Statistics Schema
# ============================================================================

class SummaryStats(BaseModel):
    """Reconciliation summary statistics"""
    total_b1: int = 0
    total_b4: int = 0
    total_b2: int = 0
    total_b3: int = 0
    matched: int = 0
    not_found: int = 0
    mismatch: int = 0
    refunded: int = 0
    other: int = 0


# ============================================================================
# Files Info Schema
# ============================================================================

class FilesUploaded(BaseModel):
    """Information about uploaded files"""
    b1: List[str] = Field(default_factory=list)
    b2: List[str] = Field(default_factory=list)
    b3: List[str] = Field(default_factory=list)


# ============================================================================
# Reconciliation Response Schemas
# ============================================================================

class ReconciliationLogBase(BaseModel):
    """Base reconciliation log schema"""
    batch_id: str
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: str


class ReconciliationLogResponse(ReconciliationLogBase):
    """Full reconciliation log response"""
    id: int
    created_by: int
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    step_logs: Optional[List[StepLog]]
    files_uploaded: Optional[FilesUploaded]
    file_result_a1: Optional[str]
    file_result_a2: Optional[str]
    file_report: Optional[str]
    summary_stats: Optional[SummaryStats]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ReconciliationLogSimple(ReconciliationLogBase):
    """Simple reconciliation log for list views"""
    id: int
    created_at: datetime
    summary_stats: Optional[SummaryStats]
    
    class Config:
        from_attributes = True


# ============================================================================
# Approval Schemas
# ============================================================================

class ApprovalRequest(BaseModel):
    """Schema for approval request"""
    batch_id: str
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Schema for approval response"""
    batch_id: str
    status: str
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    message: str


# ============================================================================
# File Upload Response
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response after file upload"""
    batch_id: str
    file_type: str  # b1, b2, b3
    files_count: int
    files: List[str]
    message: str


# ============================================================================
# Reconciliation Result Preview
# ============================================================================

class ReconciliationResultRow(BaseModel):
    """Single row in reconciliation result"""
    row_number: int
    data: Dict[str, Any]
    status_b1b4: Optional[str]
    status_b1b2: Optional[str]
    final_status: str


class ReconciliationResultPreview(BaseModel):
    """Preview of reconciliation results"""
    batch_id: str
    file_type: str  # a1, a2
    total_rows: int
    preview_rows: List[Dict[str, Any]]
    columns: List[str]


# ============================================================================
# History Query
# ============================================================================

class ReconciliationHistoryQuery(BaseModel):
    """Query parameters for reconciliation history"""
    partner_code: Optional[str] = None
    service_code: Optional[str] = None
    status: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class ReconciliationHistoryResponse(BaseModel):
    """Paginated reconciliation history response"""
    items: List[ReconciliationLogSimple]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Aliases for backward compatibility with endpoints
# ============================================================================

# Request schema alias
ReconciliationRequest = ReconciliationStartRequest

# Status enum values
class ReconciliationStatus:
    """Reconciliation status constants"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


# Response schemas for endpoints
class ReconciliationResponse(BaseModel):
    """Response schema for reconciliation operations"""
    batch_id: str
    status: str
    message: str
    partner_code: Optional[str] = None
    service_code: Optional[str] = None
    summary_stats: Optional[SummaryStats] = None
    step_logs: Optional[List[StepLog]] = None
    files: Optional[Dict[str, Any]] = None


class BatchListItem(BaseModel):
    """Single batch item in list"""
    id: int
    batch_id: str
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: str
    created_at: datetime
    created_by_name: Optional[str] = None
    summary_stats: Optional[SummaryStats] = None
    
    class Config:
        from_attributes = True


class BatchListResponse(BaseModel):
    """Response for batch list"""
    items: List[BatchListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class BatchDetailResponse(BaseModel):
    """Detailed batch information"""
    id: int
    batch_id: str
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: str
    created_by: int
    created_by_name: Optional[str] = None
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    step_logs: Optional[List[StepLog]] = None
    files_uploaded: Optional[FilesUploaded] = None
    file_result_a1: Optional[str] = None
    file_result_a2: Optional[str] = None
    file_report: Optional[str] = None
    summary_stats: Optional[SummaryStats] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
