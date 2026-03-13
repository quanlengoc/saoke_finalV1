# Tính năng: Đối soát & Kết quả

> Trang chạy đối soát, danh sách batch, chi tiết batch + download kết quả.

## Pages & Routes

| Route | Page | Mô tả |
|---|---|---|
| `/reconciliation-v2` | `ReconciliationV2Page` | Wizard 3 bước: chọn config → upload → chạy |
| `/batches` | `BatchListPage` | Danh sách tất cả batch, filter theo partner/status/ngày |
| `/batches/:batchId` | `BatchDetailPage` | Chi tiết batch: info, outputs, preview data, download, approval actions |

## Luồng người dùng

```
ReconciliationV2Page (3 steps)
│
├─ Step 1: Chọn cấu hình
│   └─ GET /configs/ → hiển thị cards (partner/service)
│
├─ Step 2: Upload files
│   ├─ GET /data-sources/by-config/{id} → render dropzones cho FILE_UPLOAD sources
│   ├─ Nhập kỳ đối soát (period_from, period_to)
│   ├─ POST /reconciliation/check-duplicate → kiểm tra batch trùng trước khi upload
│   └─ POST /reconciliation/upload-files/{configId} → upload files
│
└─ Step 3: Chạy đối soát
    ├─ POST /reconciliation/run → chạy workflow
    └─ Navigate → /batches/{batchId} (xem kết quả)

BatchListPage
├─ GET /reconciliation/batches → danh sách, filter, pagination
├─ POST /reconciliation/batches/{id}/rerun → chạy lại batch lỗi
└─ Link → /batches/{id} (chi tiết)

BatchDetailPage
├─ GET /reconciliation/batches/{id} → thông tin batch + step_logs
├─ GET /reports/preview/{batchId}/{outputName} → preview data bảng
├─ GET /reports/download/{batchId}/{outputName}?format=csv → download
├─ GET /reports/stats/{batchId} → thống kê theo output
├─ POST /reports/generate/{batchId} → tạo report Excel
├─ POST /approvals/submit/{batchId} → gửi phê duyệt
├─ POST /reconciliation/batches/{id}/rerun → chạy lại
└─ POST /reconciliation/batches/{id}/stop → dừng batch đang chạy
```

## Frontend files

| File | Vai trò |
|---|---|
| `src/pages/ReconciliationV2Page.jsx` | Wizard chạy đối soát (3 steps) |
| `src/pages/BatchListPage.jsx` | Danh sách batch + filter |
| `src/pages/BatchDetailPage.jsx` | Chi tiết batch + preview + download + approval actions |
| `src/services/api.js` → `reconciliationApi` | Upload, run, listBatches, rerun, stop, checkDuplicate, deleteBatch |
| `src/services/api.js` → `reportsApi` | Preview, download, generateReport, getStats |

## Backend files

| File | Vai trò |
|---|---|
| `app/api/v2/endpoints/reconciliation.py` | API upload, run, batches CRUD, rerun, stop |
| `app/api/v2/endpoints/reports.py` | API preview, download, generate report, stats |
| `app/services/workflow_executor.py` | Chạy dynamic workflow theo steps |
| `app/services/generic_matching_engine.py` | Core matching: key_match + amount_match |
| `app/services/data_loader.py` | Load data từ các source types |
| `app/services/file_processor.py` | Xử lý file upload (Excel, CSV, ZIP) |
| `app/models/reconciliation.py` | Model `ReconciliationLog`, `BatchRunHistory` |

## Trạng thái batch

```
UPLOADING → PROCESSING → COMPLETED → (submit) → APPROVED
                │                        └────→ REJECTED
                └──→ FAILED / ERROR → (rerun) → PROCESSING
```

## Lưu ý khi nâng cấp

- **Duplicate check**: Kiểm tra batch trùng kỳ + partner trước khi upload (bước 2), không phải khi run (bước 3)
- **Force replace**: Nếu có batch trùng chưa duyệt → user xác nhận xóa cũ, tạo mới
- **Batch đã APPROVED**: Không cho tạo batch mới trùng kỳ — phải unlock trước
- **Step logs**: Backend trả về `step_logs` (array of `{step, message, status, time}`) — hiển thị dạng terminal log
- **ZIP files**: Hỗ trợ upload ZIP, tự giải nén khi xử lý. Nhiều file cùng 1 source → ghép (concat) tự động
- **Report Excel**: Tạo từ template + SQL fill — endpoint POST `/reports/generate/{batchId}`
