# CLAUDE.md - Hướng dẫn cho AI Assistant

> File này được Claude Code đọc tự động mỗi phiên. Mọi quy tắc ở đây sẽ được tuân thủ xuyên suốt.

## Dự án: Reconciliation System V2

Hệ thống đối soát giao dịch tự động giữa sao kê ngân hàng và dữ liệu VNPT Money.

## Phiên bản đang sử dụng: V2

- **LUÔN sử dụng API V2** (`/api/v2/`), KHÔNG dùng V1 trừ khi được yêu cầu rõ ràng
- V2 = dynamic workflow (cấu hình từ DB), V1 = hardcode workflow (legacy)

## Kiến trúc tổng quan

```
reconciliation-system-v2/
├── backend/                 # FastAPI (Python 3.x)
│   ├── app/
│   │   ├── api/v2/          # ← API endpoints chính (V2)
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── services/        # Business logic
│   │   │   ├── generic_matching_engine.py  # Core matching (V2)
│   │   │   ├── workflow_executor.py        # Chạy dynamic workflow
│   │   │   ├── data_loader.py              # Load data
│   │   │   └── file_processor.py           # Xử lý file upload
│   │   ├── schemas/         # Pydantic validation
│   │   ├── core/            # Config, DB, Security
│   │   └── utils/           # Utilities
│   ├── config.ini           # Cấu hình chính (DB, storage, mock)
│   └── requirements.txt
├── frontend/                # React 18 + Vite
│   └── src/
│       ├── pages/           # Dùng ReconciliationV2Page (không phải V1)
│       ├── components/      # RuleBuilder, etc.
│       ├── services/api.js  # Axios client
│       └── stores/          # Zustand state
├── storage/                 # uploads, exports, templates, mock_data
└── docker-compose.yml       # Docker orchestration
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0, Pandas, Pydantic 2.x |
| Frontend | React 18, Vite, Zustand, Tailwind CSS, React Query |
| Database | SQLite (dev) / Oracle (production) |
| Auth | JWT (python-jose), bcrypt |
| Infra | Docker Compose, Redis, Nginx |

## Database Models chính (V2)

- `PartnerServiceConfig` - Cấu hình chính (partner_code + service_code + validity_period)
- `DataSourceConfig` - Nguồn dữ liệu động (FILE_UPLOAD, DATABASE, SFTP, API). Tên source tùy ý, không fix cứng
- `WorkflowStep` - Bước đối soát động, mỗi step gồm 3 phần: nguồn dữ liệu, quy tắc so khớp, output (trung gian hoặc chi tiết)
- `OutputConfig` - Cấu hình tạo Report: upload file mẫu Excel + SQL fill dữ liệu vào cell/dòng
- `ReconciliationLog` - Theo dõi batch đối soát
- `BatchRunHistory` - Lịch sử mỗi lần chạy
- `User` / `UserPermission` - Auth & phân quyền

## Phân quyền người dùng

### Nhóm người dùng

| Nhóm | Xác định bởi | Mô tả |
|------|--------------|-------|
| **Admin** | `User.is_admin = True` | Toàn quyền hệ thống |
| **Approver** | `UserPermission.can_approve = True` | Được phê duyệt batch cho partner/service cụ thể |
| **Reconciler** | `UserPermission.can_reconcile = True` | Được chạy đối soát cho partner/service cụ thể |
| **User thường** | Không có permission nào | Chỉ xem batch mình tạo |

### Phạm vi quyền theo chức năng

| Chức năng | Admin | Approver | Reconciler | User thường |
|-----------|-------|----------|------------|-------------|
| Quản lý users, configs | Full CRUD | - | - | - |
| Xem danh sách batch | Tất cả | Batch mình tạo + batch thuộc partner/service được approve | Batch mình tạo | Batch mình tạo |
| Upload file & chạy đối soát | Tất cả | - | Partner/service được cấp quyền | - |
| Gửi phê duyệt (submit) | Tất cả | - | Batch mình tạo | Batch mình tạo |
| Phê duyệt / Từ chối batch | Tất cả | Partner/service được cấp quyền (không duyệt batch mình tạo) | - | - |
| Unlock batch | Tất cả | Partner/service được cấp quyền | - | - |
| Download kết quả / Report | Tất cả | Batch thuộc phạm vi quyền | Batch mình tạo | Batch mình tạo |

### Cơ chế phân quyền

- Quyền gán theo cặp **partner_code + service_code** (bảng `user_permissions`)
- Mỗi user có thể có nhiều permission cho nhiều cặp partner/service khác nhau
- `can_reconcile` và `can_approve` là 2 flag độc lập — 1 user có thể có cả 2
- Admin bypass tất cả kiểm tra quyền (`User.is_admin = True`)
- Constraint: User không được approve batch do chính mình tạo (trừ admin)

### Trạng thái batch (Status Flow)

| Status | Tên hiển thị | Mô tả |
|--------|-------------|-------|
| `UPLOADING` | Khởi tạo | Batch mới tạo, đang upload file |
| `PROCESSING` | Đang xử lý | Workflow đang chạy |
| `COMPLETED` | Hoàn tất | Đối soát xong, có thể chạy lại hoặc gửi phê duyệt |
| `ERROR` | Lỗi | Đối soát thất bại, có thể chạy lại |
| `CANCELLED` | Tạm dừng | User dừng giữa chừng, có thể chạy lại |
| `PENDING_APPROVAL` | Chờ phê duyệt | Đã gửi, chờ approver duyệt |
| `APPROVED` | Đã phê duyệt | Trạng thái cuối cùng (final) |

```
UPLOADING → PROCESSING → COMPLETED → PENDING_APPROVAL → APPROVED (final)
                ↓              ↑  ↑           ↓
              ERROR     (rerun)|  |     COMPLETED (reject → về Hoàn tất)
                ↓              |  |
            PROCESSING --------+  |
                                  |
            CANCELLED → PROCESSING
```

**Chuyển trạng thái cho phép:**
- UPLOADING → PROCESSING (chạy)
- PROCESSING → COMPLETED / ERROR / CANCELLED
- COMPLETED → PROCESSING (chạy lại) / PENDING_APPROVAL (gửi phê duyệt)
- ERROR → PROCESSING (chạy lại)
- CANCELLED → PROCESSING (chạy lại)
- PENDING_APPROVAL → APPROVED (phê duyệt) / COMPLETED (từ chối → về Hoàn tất)
- APPROVED → (final, không chuyển tiếp)

**Lưu ý:**
- KHÔNG có trạng thái REJECTED — khi từ chối, batch trở về COMPLETED
- `is_locked` là computed property: `True` khi status ∈ {APPROVED, PENDING_APPROVAL}
- KHÔNG phải DB column — không dùng trong SQLAlchemy query filter
- Mọi thao tác user (submit/approve/reject) được ghi vào bảng `audit_logs`

## Luồng đối soát (Business Flow) - Hoàn toàn Dynamic

Toàn bộ luồng được **cấu hình động từ database**, không hardcode:

### Bước 1: Cấu hình (Admin)

**a) Data Sources** (`DataSourceConfig`):
- Định nghĩa N nguồn dữ liệu, tên tùy ý (VD: B1, B4... chỉ là convention)
- Mỗi source chọn loại: FILE_UPLOAD, DATABASE, SFTP, API
- Cấu hình cách đọc (format file, query DB, endpoint API...)

**b) Workflow Steps** (`WorkflowStep`):
- Định nghĩa N bước đối soát, chạy tuần tự theo step_order
- Mỗi step gồm 3 phần:
  1. **Chọn nguồn**: left_source + right_source (có thể là data gốc hoặc output trung gian của step trước)
  2. **Quy tắc so khớp**: key_match (expression/custom module) + amount_match (tolerance) + join_type
  3. **Output**: đặt tên output_name + chọn columns + đánh dấu là **trung gian** (dùng cho step sau) hay **chi tiết cuối** (xuất ra cho user)

**c) Report Config** (`OutputConfig`):
- Upload file mẫu Excel (template)
- Cấu hình SQL queries để lấy dữ liệu từ kết quả chi tiết
- Map dữ liệu SQL vào sheet/cell/dòng cụ thể trong template
- Dữ liệu đầu vào cho report = các output chi tiết (final) từ workflow steps

### Bước 2: Chạy đối soát (User)
- Chọn partner + service + kỳ đối soát
- Upload các file theo DataSourceConfig yêu cầu (type=FILE_UPLOAD)
- System tự load các source khác (DATABASE, SFTP, API)
- `WorkflowExecutor` chạy tuần tự từng step → `GenericMatchingEngine` matching → tạo output
- Output trung gian chaining vào step tiếp theo, output chi tiết xuất file

### Bước 3: Duyệt (Approver)
- Review kết quả chi tiết → Approve/Reject

### Bước 4: Báo cáo
- Download các output chi tiết (CSV)
- Tạo Report Excel từ template + SQL fill dữ liệu

## Matching Engine (GenericMatchingEngine)

- **Key Match**: Ghép giao dịch bằng expression (concat columns) hoặc custom Python module
- **Amount Match**: So khớp số tiền với tolerance (configurable)
- **Join types**: LEFT, INNER, RIGHT, OUTER - tùy cấu hình mỗi step
- **Trạng thái kết quả**: MATCHED, NOT_FOUND, AMOUNT_MISMATCH
- Output mỗi step có thể dùng làm input cho step tiếp theo (chaining)

## API V2 - Đầy đủ tất cả endpoints

Frontend chỉ dùng 1 axios instance duy nhất: `baseURL: '/api/v2'`

| Module | Prefix | Endpoints |
|--------|--------|-----------|
| Auth | `/auth` | login, me, change-password |
| Users | `/users` | CRUD + permissions (admin) |
| Partners | `/partners` | list, services, config by date |
| Configs | `/configs` | CRUD dynamic configs |
| Data Sources | `/data-sources` | CRUD per config |
| Workflows | `/workflows` | CRUD steps per config |
| Outputs | `/outputs` | CRUD output configs |
| Reconciliation | `/reconciliation` | upload, run, batches, rerun, stop |
| Reports | `/reports` | preview, download, generate, stats |
| Approvals | `/approvals` | pending, submit, approve, reject, unlock, history, stats |
| Mock Data | `/mock-data` | CRUD mock files (admin) |

## Quy tắc code

### Backend (Python)
- Async/await cho API endpoints
- SQLAlchemy 2.0 declarative style
- Pydantic v2 cho schemas
- Config đọc từ `config.ini` (ConfigParser + Pydantic Settings)
- Tất cả endpoints nằm trong `app/api/v2/endpoints/` — KHÔNG thêm endpoint mới vào `app/api/v1/`
- Khi sửa matching logic → sửa `generic_matching_engine.py` (V2), KHÔNG sửa `reconciliation_engine.py` (V1)

### Frontend (React)
- Functional components + hooks
- State: Zustand | HTTP: Axios (auto JWT) | Style: Tailwind CSS | Route: React Router v6
- `api.js` dùng DUY NHẤT `/api/v2` — KHÔNG tạo thêm axios instance V1
- Backward compat aliases: `configsApiV2 = configsApi`, `reconciliationApiV2 = reconciliationApi`, etc.
- V2 pages: `ReconciliationV2Page`, `ConfigsV2Page`, `ConfigDetailV2Page`, `ConfigEditV2Page`

### Docker
- Backend: 8001, Frontend: 3000, Redis: 6379
- Mock mode: `config.ini` → `[mock] enabled = true` (dev không cần Oracle)

## File Storage

```
storage/
├── uploads/{partner_code}/{batch_id}/{source_name}/
├── processed/{partner_code}/{period}/{batch_id}/{source_name}.csv
├── exports/{partner_code}/{batch_id}/
├── templates/shared/*.xlsx
├── mock_data/
├── sql_templates/shared/*.sql
└── custom_matching/{partner_code}/{service_code}.py
```

## Hướng dẫn đọc tài liệu chi tiết (QUAN TRỌNG)

**TRƯỚC KHI sửa code**, đọc file docs tương ứng để hiểu đủ ngữ cảnh (pages, components, API, backend files liên quan):

| Khi được yêu cầu về... | Đọc file | Ghi chú |
|---|---|---|
| Upload file, chạy đối soát, xem kết quả batch, download CSV/Excel, tạo report | `docs/features/RECONCILIATION.md` | Gồm 3 pages: ReconciliationV2Page (wizard 3 bước), BatchListPage, BatchDetailPage |
| Tạo/sửa cấu hình, thêm data source, thêm workflow step, cấu hình output/report | `docs/features/CONFIG.md` | Gồm 3 pages nhưng ConfigEditV2Page là chính (4 tabs: basic, sources, workflow, outputs) |
| Phê duyệt, từ chối, gửi duyệt, unlock batch | `docs/features/APPROVALS.md` | 1 page ApprovalsPage + phần actions trong BatchDetailPage |
| Quản lý user, phân quyền, mock data | `docs/features/ADMIN.md` | 2 pages: UsersPage (CRUD + permissions), MockDataPage (upload CSV mock) |
| Deploy server, sub-path, Nginx, Oracle, Docker production | `docs/DEPLOY.md` | Ví dụ cụ thể cho ptdata.vnptmone.vh/Sokhop |
| Chạy Docker dev, lệnh Docker, volumes | `docs/DOCKER.md` | Quick start + troubleshooting |

Mỗi file feature ghi rõ: routes, luồng API calls, danh sách frontend files, danh sách backend files, và lưu ý khi nâng cấp.

## Nguyên tắc thiết kế DB & Logging

### 1. Thiết kế DB
- **KHÔNG lưu quá nhiều dữ liệu vào 1 cột** (ví dụ: không nhồi JSON lớn vào 1 column text)
- Khi cần lưu lịch sử, tạo bảng riêng với các cột rõ nghĩa

### 2. Ba tầng logging

| Tầng | Nơi lưu | Mục đích | Ví dụ |
|------|---------|----------|-------|
| **AuditLog** | DB (bảng `audit_logs`) | Lịch sử thao tác user | Approve/reject batch, CRUD user, đổi quyền |
| **BatchRunHistory** | DB (bảng `batch_run_history`) | Lịch sử chạy batch hệ thống | Số lần chạy, duration, trạng thái, link file log |
| **Log files** | Filesystem | Debug kỹ thuật, ELK | app.log, error.log, step log files |

### 3. AuditLog (bảng chung cho mọi thao tác user)

Thiết kế theo chuẩn **Audit Trail** — bảng append-only, không update/delete:

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `id` | Integer PK | Auto increment |
| `timestamp` | DateTime | Thời điểm thao tác |
| `user_id` | Integer FK | Ai thao tác |
| `user_email` | String | Email (denormalized để query nhanh) |
| `action` | String | Hành động: APPROVE, REJECT, SUBMIT, CREATE, UPDATE, DELETE, LOGIN, LOGOUT |
| `entity_type` | String | Đối tượng: BATCH, USER, CONFIG, PERMISSION |
| `entity_id` | String | ID đối tượng bị tác động |
| `old_values` | JSON | Giá trị trước (nullable) |
| `new_values` | JSON | Giá trị sau (nullable) |
| `summary` | String | Mô tả ngắn gọn |
| `ip_address` | String | IP client (nullable) |

Các feature ghi AuditLog: approve/reject/submit batch, lock/unlock, CRUD user, đổi quyền, thay đổi config, login/logout.

### 4. BatchRunHistory (riêng cho lịch sử chạy batch)

Tách riêng vì đặc thù khác: theo dõi hệ thống chạy, có domain-specific fields (run_number, duration, log_file_path, summary_stats). KHÔNG gộp vào AuditLog.

### 5. Step log files (log quá trình chạy từng step)

- Lưu ra file JSON: `logs/batches/{batch_id}/run_{N}.json`
- Background thread callback ghi realtime, KHÔNG ghi vào DB
- Cần **cron job dọn dẹp**: xóa file > 6 tháng hoặc gzip file > 1 tháng

### 6. System logs (log kỹ thuật)

- Format chuẩn cho ELK: `%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s`
- Rotation: app.log (30 ngày), error.log (90 ngày), api.log (7 ngày)
- Error log ghi traceback đầy đủ với file:line để debug

## Lưu ý quan trọng

- Tên data source và output chỉ là convention, KHÔNG phải constant. Hệ thống hoạt động với bất kỳ tên nào
- Số lượng data sources, workflow steps, outputs là ĐỘNG - không giới hạn
- Mỗi WorkflowStep output có thể là trung gian (input cho step sau) hoặc chi tiết cuối (xuất ra + dùng cho report)
- OutputConfig là bước tạo Report từ template Excel + SQL, KHÔNG phải output của matching
- V1 API vẫn tồn tại (legacy) nhưng KHÔNG dùng — tất cả đã migrate sang V2
- Frontend `api.js` và `authStore.js` đều dùng `/api/v2` duy nhất
- Khi deploy lên server với sub-path (VD: `/Sokhop`), cần cấu hình: VITE base path, React Router basename, Nginx location, CORS origins
