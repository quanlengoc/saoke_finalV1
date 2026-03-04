"""
Approval workflow schemas
"""

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    """Schema for approval request"""
    batch_id: str
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Schema for approval response"""
    id: int
    batch_id: str
    partner_code: str
    service_code: str
    period_from: date
    period_to: date
    status: str
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    message: Optional[str] = None
    summary_matched: Optional[int] = None
    summary_not_found: Optional[int] = None
    summary_mismatch: Optional[int] = None
    
    class Config:
        from_attributes = True


class ApprovalHistoryItem(BaseModel):
    """Single approval history item"""
    batch_id: str
    partner_code: str
    service_code: str
    action: str  # approve, reject, submit
    performed_by: int
    performed_by_name: Optional[str] = None
    performed_at: datetime
    comment: Optional[str] = None


class ApprovalHistoryResponse(BaseModel):
    """Response for approval history"""
    items: List[ApprovalHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class SubmitForApprovalRequest(BaseModel):
    """Request to submit batch for approval"""
    batch_id: str
    comment: Optional[str] = None


class SubmitForApprovalResponse(BaseModel):
    """Response after submitting for approval"""
    batch_id: str
    status: str
    message: str
    submitted_at: datetime
