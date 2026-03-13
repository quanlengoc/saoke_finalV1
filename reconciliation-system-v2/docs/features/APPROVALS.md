# Tính năng: Phê duyệt

> Trang phê duyệt/từ chối batch đối soát đã hoàn thành.

## Pages & Routes

| Route | Page | Mô tả |
|---|---|---|
| `/approvals` | `ApprovalsPage` | Danh sách batch chờ duyệt + modal duyệt/từ chối |

## Luồng phê duyệt

```
Batch COMPLETED
  └─ User: POST /approvals/submit/{batchId}     → batch bị lock
       └─ Approver: xem danh sách pending
            ├─ POST /approvals/approve/{batchId} → APPROVED
            └─ POST /approvals/reject/{batchId}  → REJECTED (bắt buộc ghi chú)
                 └─ Admin: POST /approvals/unlock/{batchId} → mở lock để sửa/chạy lại
```

## API Endpoints

```
GET    /approvals/pending             → Danh sách batch chờ duyệt
POST   /approvals/submit/{batchId}    → Gửi batch đi duyệt (lock)
POST   /approvals/approve/{batchId}   → Phê duyệt (body: {notes})
POST   /approvals/reject/{batchId}    → Từ chối (body: {notes} - bắt buộc)
POST   /approvals/unlock/{batchId}    → Mở khóa batch bị reject/lock
GET    /approvals/history/{batchId}   → Lịch sử phê duyệt của batch
GET    /approvals/stats               → Thống kê phê duyệt
```

## Frontend files

| File | Vai trò |
|---|---|
| `src/pages/ApprovalsPage.jsx` | Danh sách pending + modal approve/reject |
| `src/pages/BatchDetailPage.jsx` | Cũng có nút Submit/Approve/Reject ở phần actions |
| `src/services/api.js` → `approvalsApi` | Tất cả endpoints phê duyệt |

## Backend files

| File | Vai trò |
|---|---|
| `app/api/v2/endpoints/approvals.py` | API phê duyệt, schema `ApprovalActionRequest` |
| `app/models/reconciliation.py` | Field `status`, `is_locked`, `approved_by`, `approved_at` trên `ReconciliationLog` |

## Lưu ý khi nâng cấp

- **Reject bắt buộc notes**: Frontend validate `notes.trim()` trước khi gọi API reject
- **Submit = lock batch**: Sau khi submit, batch không thể rerun/sửa cho đến khi unlock
- **Approve/Reject dùng chung schema**: `ApprovalActionRequest { notes: Optional[str] }` — không có field `action` hay `batch_id` trong body
- **Batch APPROVED → không cho tạo batch mới trùng kỳ**: Logic check trong endpoint `/reconciliation/check-duplicate`
- **step_logs parsing**: Backend parse `batch.step_logs` — có thể là string hoặc list, cần handle cả 2 trường hợp
- **ApprovalsPage chỉ hiển thị pending**: Dùng `approvalsApi.listPending({})` — không có filter phức tạp
