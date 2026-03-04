"""
Approval workflow endpoints
Submit, approve, reject batches
"""

from typing import Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User, ReconciliationLog, UserPermission
from app.services.workflow_service import WorkflowService
from app.schemas.approval import (
    ApprovalRequest, ApprovalResponse, ApprovalHistoryResponse
)


router = APIRouter()


def check_approve_permission(
    user: User,
    partner_code: str,
    service_code: str,
    db: Session
) -> bool:
    """Check if user has approval permission for partner/service"""
    if user.is_admin:
        return True
    
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user.id,
        UserPermission.partner_code == partner_code,
        UserPermission.service_code == service_code,
        UserPermission.can_approve == True
    ).first()
    
    return permission is not None


@router.get("/pending", response_model=List[ApprovalResponse])
async def list_pending_approvals(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    List batches pending approval
    
    Only shows batches user has approval permission for
    """
    query = db.query(ReconciliationLog).filter(
        ReconciliationLog.status == "COMPLETED",
        ReconciliationLog.is_locked == False
    )
    
    if not current_user.is_admin:
        # Get user's approval permissions
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_approve == True
        ).all()
        
        if not permissions:
            return []
        
        allowed_pairs = [(p.partner_code, p.service_code) for p in permissions]
        
        from sqlalchemy import or_, and_
        conditions = [
            and_(
                ReconciliationLog.partner_code == pc,
                ReconciliationLog.service_code == sc
            )
            for pc, sc in allowed_pairs
        ]
        query = query.filter(or_(*conditions))
    
    # Apply filters
    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)
    
    batches = query.order_by(
        ReconciliationLog.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return batches


@router.post("/submit/{batch_id}")
async def submit_for_approval(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Submit a batch for approval (lock it)
    
    After submission, the batch cannot be rerun until unlocked
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    if batch.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed batches can be submitted for approval"
        )
    
    if batch.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch is already locked/submitted"
        )
    
    # Lock the batch
    workflow = WorkflowService(db)
    workflow.lock_batch(batch.id, current_user.id)
    workflow.add_step_log(batch.id, "SUBMIT", f"Submitted for approval by {current_user.email}")
    
    db.commit()
    
    return {
        "message": "Batch submitted for approval",
        "batch_id": batch_id,
        "status": "PENDING_APPROVAL"
    }


@router.post("/approve/{batch_id}")
async def approve_batch(
    batch_id: str,
    request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Approve a batch
    
    Requires approval permission for the partner/service
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_approve_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No approval permission for this partner/service"
        )
    
    if batch.status not in ["COMPLETED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed batches can be approved"
        )
    
    # Cannot approve own batch (optional rule)
    if batch.created_by == current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve your own batch"
        )
    
    workflow = WorkflowService(db)
    workflow.approve_batch(
        batch_id=batch.id,
        user_id=current_user.id,
        notes=request.notes
    )
    
    db.commit()
    
    return {
        "message": "Batch approved successfully",
        "batch_id": batch_id,
        "status": "APPROVED",
        "approved_by": current_user.email,
        "approved_at": datetime.now().isoformat()
    }


@router.post("/reject/{batch_id}")
async def reject_batch(
    batch_id: str,
    request: ApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Reject a batch
    
    Batch will be unlocked and can be rerun
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_approve_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No approval permission"
        )
    
    if batch.status not in ["COMPLETED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed batches can be rejected"
        )
    
    if not request.notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required"
        )
    
    workflow = WorkflowService(db)
    workflow.reject_batch(
        batch_id=batch.id,
        user_id=current_user.id,
        reason=request.notes
    )
    
    db.commit()
    
    return {
        "message": "Batch rejected",
        "batch_id": batch_id,
        "status": "REJECTED",
        "rejected_by": current_user.email,
        "reason": request.notes
    }


@router.post("/unlock/{batch_id}")
async def unlock_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Unlock a batch (admin only or approver)
    
    Allows the batch to be rerun
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check permission
    if not check_approve_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permission to unlock"
        )
    
    if batch.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlock approved batch"
        )
    
    workflow = WorkflowService(db)
    workflow.unlock_batch(batch.id, current_user.id)
    
    db.commit()
    
    return {
        "message": "Batch unlocked",
        "batch_id": batch_id
    }


@router.get("/history/{batch_id}", response_model=List[ApprovalHistoryResponse])
async def get_approval_history(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get approval history for a batch
    """
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    workflow = WorkflowService(db)
    history = workflow.get_batch_history(batch.id)
    
    # Parse step_logs for approval-related entries
    step_logs = batch.step_logs or []
    
    approval_history = []
    for log in step_logs:
        step_type = log.get("step", "")
        if step_type in ["SUBMIT", "APPROVE", "REJECT", "UNLOCK", "RESET"]:
            approval_history.append({
                "action": step_type,
                "message": log.get("message", ""),
                "timestamp": log.get("timestamp", ""),
                "user_id": log.get("user_id")
            })
    
    return approval_history


@router.get("/stats")
async def get_approval_stats(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get approval statistics
    """
    query = db.query(ReconciliationLog)
    
    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)
    
    total = query.count()
    pending = query.filter(ReconciliationLog.status == "COMPLETED", ReconciliationLog.is_locked == True).count()
    approved = query.filter(ReconciliationLog.status == "APPROVED").count()
    rejected = query.filter(ReconciliationLog.status == "REJECTED").count()
    
    return {
        "total": total,
        "pending_approval": pending,
        "approved": approved,
        "rejected": rejected
    }
