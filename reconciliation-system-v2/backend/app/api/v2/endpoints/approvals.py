"""
Approval workflow endpoints (V2)
Submit, approve, reject batches
All actions are logged to audit_logs table.
"""

from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_user
from app.models import User, ReconciliationLog, UserPermission
from app.models.audit_log import AuditLog
from sqlalchemy.orm import joinedload


router = APIRouter()


class ApprovalActionRequest(BaseModel):
    """Request body for approve/reject actions"""
    notes: Optional[str] = None


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


def _write_audit(db: Session, user: User, action: str, batch: ReconciliationLog,
                 old_status: str, new_status: str, summary: str, request: Request = None):
    """Write an audit log entry. Non-blocking: errors logged but don't fail the main action."""
    try:
        log = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=action,
            entity_type="BATCH",
            entity_id=batch.batch_id,
            old_values={"status": old_status},
            new_values={"status": new_status},
            summary=summary,
            ip_address=request.client.host if request else None,
        )
        db.add(log)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to write audit log: {e}")


@router.get("/pending")
async def list_pending_approvals(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """List batches pending approval. Only shows batches user has approval permission for."""
    query = db.query(ReconciliationLog).options(
        joinedload(ReconciliationLog.creator)
    ).filter(
        ReconciliationLog.status == "PENDING_APPROVAL"
    )

    if not current_user.is_admin:
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

    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)

    batches = query.order_by(
        ReconciliationLog.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for b in batches:
        result.append({
            "id": b.id,
            "batch_id": b.batch_id,
            "partner_code": b.partner_code,
            "service_code": b.service_code,
            "period_from": str(b.period_from) if b.period_from else None,
            "period_to": str(b.period_to) if b.period_to else None,
            "status": b.status,
            "created_by": b.created_by,
            "created_by_name": b.creator.full_name if b.creator else "Unknown",
            "created_at": b.created_at,
        })

    return result


@router.post("/submit/{batch_id}")
async def submit_for_approval(
    batch_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Submit a batch for approval (COMPLETED → PENDING_APPROVAL)"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch không tồn tại"
        )

    if batch.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ batch Hoàn tất mới có thể gửi phê duyệt (hiện tại: {batch.status})"
        )

    old_status = batch.status
    batch.status = "PENDING_APPROVAL"
    batch.updated_at = datetime.utcnow()

    _write_audit(db, current_user, "SUBMIT", batch, old_status, "PENDING_APPROVAL",
                 f"{current_user.email} gửi phê duyệt batch {batch_id}", request)

    db.commit()

    return {
        "message": "Đã gửi phê duyệt",
        "batch_id": batch_id,
        "status": "PENDING_APPROVAL"
    }


@router.post("/approve/{batch_id}")
async def approve_batch(
    batch_id: str,
    body: ApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Approve a batch (PENDING_APPROVAL → APPROVED)"""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch không tồn tại"
        )

    if not check_approve_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền phê duyệt cho partner/service này"
        )

    if batch.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ batch Chờ phê duyệt mới có thể phê duyệt (hiện tại: {batch.status})"
        )

    if batch.created_by == current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể phê duyệt batch do chính mình tạo"
        )

    old_status = batch.status
    batch.status = "APPROVED"
    batch.approved_by = current_user.id
    batch.approved_at = datetime.utcnow()
    batch.updated_at = datetime.utcnow()

    _write_audit(db, current_user, "APPROVE", batch, old_status, "APPROVED",
                 f"{current_user.email} phê duyệt batch {batch_id}", request)

    db.commit()

    return {
        "message": "Đã phê duyệt",
        "batch_id": batch_id,
        "status": "APPROVED",
        "approved_by": current_user.email,
        "approved_at": batch.approved_at.isoformat()
    }


@router.post("/reject/{batch_id}")
async def reject_batch(
    batch_id: str,
    body: ApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Reject a batch (PENDING_APPROVAL → COMPLETED). User can rerun or resubmit."""
    batch = db.query(ReconciliationLog).filter(
        ReconciliationLog.batch_id == batch_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch không tồn tại"
        )

    if not check_approve_permission(current_user, batch.partner_code, batch.service_code, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền phê duyệt"
        )

    if batch.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ batch Chờ phê duyệt mới có thể từ chối (hiện tại: {batch.status})"
        )

    if not body.notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập lý do từ chối"
        )

    old_status = batch.status
    batch.status = "COMPLETED"
    batch.error_message = f"Từ chối: {body.notes}"
    batch.approved_by = None
    batch.approved_at = None
    batch.updated_at = datetime.utcnow()

    _write_audit(db, current_user, "REJECT", batch, old_status, "COMPLETED",
                 f"{current_user.email} từ chối batch {batch_id}: {body.notes}", request)

    db.commit()

    return {
        "message": "Đã từ chối — batch trở về trạng thái Hoàn tất",
        "batch_id": batch_id,
        "status": "COMPLETED",
        "rejected_by": current_user.email,
        "reason": body.notes
    }


@router.get("/history/{batch_id}")
async def get_approval_history(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Get audit history for a batch from audit_logs table"""
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "BATCH",
        AuditLog.entity_id == batch_id
    ).order_by(AuditLog.timestamp.desc()).all()

    return [
        {
            "action": log.action,
            "user_email": log.user_email,
            "summary": log.summary,
            "old_values": log.old_values_dict,
            "new_values": log.new_values_dict,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]


@router.get("/stats")
async def get_approval_stats(
    partner_code: str = Query(default=None),
    service_code: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Get approval statistics"""
    query = db.query(ReconciliationLog)

    if partner_code:
        query = query.filter(ReconciliationLog.partner_code == partner_code)
    if service_code:
        query = query.filter(ReconciliationLog.service_code == service_code)

    total = query.count()
    pending = query.filter(ReconciliationLog.status == "PENDING_APPROVAL").count()
    approved = query.filter(ReconciliationLog.status == "APPROVED").count()

    return {
        "total": total,
        "pending_approval": pending,
        "approved": approved,
    }
