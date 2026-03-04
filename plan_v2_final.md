# Plan V2 Final — Hệ thống Đối soát Giao dịch (Reconciliation System V2)

> **Tài liệu được tạo từ code thực tế** (không dựa trên file plan cũ).  
> Cập nhật lần cuối: 2026-02-26

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc kỹ thuật](#2-kiến-trúc-kỹ-thuật)
3. [Quy tắc phát triển (Coding Conventions)](#3-quy-tắc-phát-triển-coding-conventions)
4. [Database Schema](#4-database-schema)
5. [Backend — Models](#5-backend--models)
6. [Backend — Services](#6-backend--services)
7. [Backend — API Endpoints](#7-backend--api-endpoints)
8. [Frontend](#8-frontend)
9. [Luồng xử lý chính (Workflow)](#9-luồng-xử-lý-chính-workflow)
10. [Cấu hình đối soát (Configuration)](#10-cấu-hình-đối-soát-configuration)
11. [Storage & File Structure](#11-storage--file-structure)
12. [Authentication & Authorization](#12-authentication--authorization)
13. [Logging](#13-logging)

---

## 1. Tổng quan hệ thống

Hệ thống đối soát giao dịch **hoàn toàn động (fully dynamic)**. Hỗ trợ:

- **Số nguồn dữ liệu không giới hạn** — mỗi config tự định nghĩa bao nhiêu data source tùy ý, tên tùy ý (không bắt buộc là B1/B2/B3/B4), mỗi source có thể là FILE_UPLOAD, DATABASE, SFTP, API
- **Số bước so khớp không giới hạn** — workflow gồm N bước matching, mỗi bước chọn 2 nguồn bất kỳ (kể cả output của bước trước) để so khớp, luật matching cấu hình riêng
- **Số output không giới hạn** — mỗi bước tạo 1 output với cấu hình columns riêng, output có thể là intermediate (dùng cho bước sau) hoặc final (xuất file)
- Đối soát tự động với luật cấu hình hoàn toàn từ database (config-driven), không hardcode logic
- Xuất kết quả ra CSV/Excel, fill vào template Excel báo cáo
- Quy trình phê duyệt (approval workflow)
- Quản lý user + phân quyền theo partner/service

> **Lưu ý:** Các tên B1, B2, B3, B4, A1, A1_1, A1_2, A4 trong tài liệu này chỉ là **ví dụ** từ config SACOMBANK/TOPUP. Thực tế tên data source, workflow step, output có thể là bất kỳ tên nào do admin cấu hình.

Hệ thống triển khai 2 phiên bản API song song:
- **V1** (`/api/v1/`): API gốc (upload + reconcile cùng endpoint, config cứng)
- **V2** (`/api/v2/`): API mới (dynamic config: data source, workflow step, output config lưu ở DB, tách upload/run riêng)

Cả V1 và V2 **chia sẻ chung** bảng `reconciliation_logs` để quản lý batch.

---

## 2. Kiến trúc kỹ thuật

### Technology Stack

| Layer     | Technology                                           |
|-----------|------------------------------------------------------|
| Backend   | **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.x**, **Pydantic V2** |
| Database  | **SQLite** (dev), **Oracle** (prod) — chuyển đổi qua `config.ini` |
| Frontend  | **React 18** (JSX), **Vite**, **Tailwind CSS**, **TanStack React Query** |
| Auth      | **JWT** (Bearer token), `bcrypt` password hashing    |
| Data Proc | **pandas**, **numpy**, **openpyxl**                  |

### Server Ports

| Service   | Port  | Note                        |
|-----------|-------|-----------------------------|
| Backend   | 8001  | Cấu hình trong `config.ini` [server].port |
| Frontend  | 3001  | Vite dev server, proxy → 8001 |

### Cấu trúc thư mục

```
reconciliation-system-v2/
├── backend/
│   ├── config.ini                     # Cấu hình server, DB, storage, mock
│   ├── requirements.txt
│   ├── tests/                         # File test, debug (KHÔNG để ở root)
│   ├── scripts/                       # Scripts migration, tiện ích
│   ├── tools/                         # Công cụ hỗ trợ
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── init_db.py                 # Khởi tạo data mặc định
│   │   ├── core/
│   │   │   ├── config.py              # Settings (Pydantic), ConfigIniReader
│   │   │   ├── database.py            # DatabaseManager (SQLite/Oracle)
│   │   │   ├── security.py            # JWT, password hashing
│   │   │   ├── logging_config.py      # Logging setup
│   │   │   └── exceptions.py          # Custom exceptions
│   │   ├── models/                    # SQLAlchemy models
│   │   ├── schemas/                   # Pydantic schemas (request/response)
│   │   ├── services/                  # Business logic
│   │   ├── api/
│   │   │   ├── deps.py                # Shared dependencies
│   │   │   ├── v1/                    # API V1 endpoints
│   │   │   └── v2/                    # API V2 endpoints
│   │   └── utils/                     # Utility functions
│   └── data/
│       └── app.db                     # SQLite database file
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx                    # Routes + Protected routes
│   │   ├── services/api.js            # Axios API clients (V1 + V2)
│   │   ├── stores/authStore.js        # Zustand auth state
│   │   ├── pages/                     # Page components
│   │   ├── components/                # Shared components
│   │   └── layouts/                   # Layout components
│
└── storage/
    ├── uploads/                       # File uploads
    ├── exports/                       # Output CSV/Excel
    ├── processed/                     # Processed data
    ├── templates/                     # Report templates (.xlsx)
    ├── sql_templates/                 # SQL query files
    ├── mock_data/                     # Mock CSV files
    └── custom_matching/               # Custom matching modules (.py)
```

---

## 3. Quy tắc phát triển (Coding Conventions)

> **QUAN TRỌNG:** Mọi thay đổi code đều phải tuân thủ các quy tắc sau. AI assistant và developer đều phải đọc và tuân theo section này trước khi code.

### 3.1 Tổ chức file — Đặt đúng thư mục

Thư mục `backend/` root **CHỈ** chứa:
- `config.ini`, `requirements.txt` — file cấu hình
- `app/` — source code chính
- `data/` — database files
- `logs/` — log files
- `tests/` — file test, debug
- `scripts/` — file migration, script tiện ích
- `tools/` — công cụ hỗ trợ
- `storage/` — uploads, exports, templates

**KHÔNG được** tạo file `.py` trực tiếp ở `backend/` root. Cụ thể:

| Loại file | Thư mục đúng | Ví dụ |
|-----------|-------------|-------|
| File test, unit test | `backend/tests/` | `test_api_v2.py`, `test_matching.py` |
| File debug, kiểm tra | `backend/tests/` | `_debug_config.py`, `_check.py` |
| Script migration DB | `backend/scripts/` | `migrate_workflow_columns.py` |
| Script tiện ích chạy 1 lần | `backend/scripts/` | `fix_db.py`, `seed_data.py` |
| Công cụ hỗ trợ | `backend/tools/` | `db_inspector.py` |
| Business logic | `backend/app/services/` | `matching_engine.py` |
| API endpoint | `backend/app/api/` | `reconciliation.py` |
| Model | `backend/app/models/` | `reconciliation.py` |
| Utility | `backend/app/utils/` | `transform_utils.py` |

### 3.2 Đặt tên file

- File test/debug prefix với `test_` hoặc `_` (underscore): `test_xlsb.py`, `_debug_config.py`
- File migration prefix với `migrate_`: `migrate_add_column.py`
- Không tạo file tạm/rác trong source tree — nếu cần thì dùng thư mục `tests/` hoặc xóa sau khi dùng

### 3.3 Code style

- **Logging**: Dùng `logging.getLogger('tên_module')` — KHÔNG dùng `print()` trong code production
- **Error handling**: Luôn log traceback khi `except`, không nuốt lỗi im lặng
- **Import**: Tránh import trong thân hàm (trừ circular import). Import ở đầu file
- **Type hints**: Khuyến khích dùng type hints cho function signatures
- **Docstring**: Mọi class và public function phải có docstring

### 3.4 Quy trình thay đổi code

1. **Đọc context** trước khi sửa — hiểu file đang làm gì, ai gọi nó
2. **Không tạo file thừa** — chỉ tạo file khi thực sự cần thiết
3. **Dọn dẹp** — file test/debug tạm phải nằm đúng thư mục hoặc xóa sau khi dùng
4. **Verify** — sau khi sửa phải kiểm tra import, syntax error
5. **Không hardcode** — config lấy từ DB hoặc `config.ini`, không hardcode path/value

---

## 4. Database Schema

### 3.1 Bảng `partner_service_config`

Cấu hình chính — 1 row = 1 partner + 1 service + 1 validity period.

| Column               | Type         | Note                                          |
|----------------------|--------------|-----------------------------------------------|
| id                   | INTEGER PK   | Auto-increment                                |
| partner_code         | VARCHAR(50)  | Mã đối tác (SACOMBANK, VCB, ...)              |
| partner_name         | VARCHAR(255) | Tên đối tác                                   |
| service_code         | VARCHAR(50)  | Mã dịch vụ (TOPUP, CASHIN, ...)               |
| service_name         | VARCHAR(255) | Tên dịch vụ                                   |
| is_active            | BOOLEAN      | Trạng thái hoạt động                          |
| valid_from           | DATE         | Ngày bắt đầu hiệu lực                        |
| valid_to             | DATE NULL    | Ngày kết thúc (NULL = vô thời hạn)            |
| report_template_path | VARCHAR(500) | Đường dẫn template báo cáo                    |
| report_cell_mapping  | TEXT (JSON)  | Mapping cell Excel cho báo cáo                |
| created_at           | DATETIME     |                                               |
| updated_at           | DATETIME     |                                               |

**Unique constraint**: `(partner_code, service_code, valid_from)`

**Relationships** (có cascade delete):
- `data_sources` → `DataSourceConfig`
- `workflow_steps` → `WorkflowStep`
- `output_configs` → `OutputConfig`

### 3.2 Bảng `data_source_config`

Cấu hình nguồn dữ liệu động — mỗi row = 1 data source.

| Column        | Type          | Note                                            |
|---------------|---------------|------------------------------------------------|
| id            | INTEGER PK    |                                                |
| config_id     | INTEGER FK    | → partner_service_config.id (CASCADE)          |
| source_name   | VARCHAR(20)   | Tên tùy ý do admin đặt (ví dụ: B1, B2, BANK_STMT, TXN_DATA, ...) |
| source_type   | VARCHAR(20)   | FILE_UPLOAD, DATABASE, SFTP (future), API (future) |
| display_name  | VARCHAR(100)  | Hiển thị trên UI                               |
| is_required   | BOOLEAN       | Bắt buộc phải có dữ liệu?                     |
| display_order | INTEGER       | Thứ tự hiển thị                                |
| file_config   | TEXT (JSON)   | Config cho FILE_UPLOAD (header_row, data_start_row, columns, transforms) |
| db_config     | TEXT (JSON)   | Config cho DATABASE (db_connection, sql_file, mock_file, columns) |
| sftp_config   | TEXT (JSON)   | Config cho SFTP (future)                       |
| api_config    | TEXT (JSON)   | Config cho API (future)                        |

**Unique constraint**: `(config_id, source_name)`

**file_config JSON example:**
```json
{
  "header_row": 1,
  "data_start_row": 2,
  "sheet_name": "Sheet1",
  "columns": {
    "txn_id": "A",
    "amount": "C",
    "date": "B"
  },
  "transforms": {
    "txn_id": ".str.strip().str.upper()"
  }
}
```

**db_config JSON example:**
```json
{
  "db_connection": "vnptmoney_main",
  "sql_file": "shared/query_topup.sql",
  "sql_params": {},
  "mock_file": "SACOMBANK_TOPUP_b4_mock.csv",
  "columns": {
    "txn_id": "TRANSACTION_ID",
    "amount": "TOTAL_AMOUNT"
  }
}
```

### 3.3 Bảng `workflow_step`

Cấu hình các bước matching — mỗi row = 1 step trong quy trình đối soát.

| Column              | Type          | Note                                           |
|---------------------|---------------|------------------------------------------------|
| id                  | INTEGER PK    |                                                |
| config_id           | INTEGER FK    | → partner_service_config.id                    |
| step_order          | INTEGER       | Thứ tự thực hiện (1, 2, 3, ...)               |
| step_name           | VARCHAR(100)  | Tên hiển thị                                   |
| left_source         | VARCHAR(50)   | Nguồn bên trái — bất kỳ data source hoặc output của step trước ||
| right_source        | VARCHAR(50)   | Nguồn bên phải — bất kỳ data source hoặc output của step trước |
| join_type           | VARCHAR(10)   | left, inner, right, outer                      |
| matching_rules      | TEXT (JSON)   | Luật matching (key_match, amount_match, ...)   |
| output_name         | VARCHAR(50)   | Tên output tùy ý (ví dụ: A1_1, RESULT_FINAL, ...) |
| output_type         | VARCHAR(20)   | intermediate / report                          |
| output_columns      | TEXT (JSON)   | (Legacy — giờ dùng OutputConfig)               |
| is_final_output     | BOOLEAN       | Có phải output cuối không?                     |
| status_combine_rules| TEXT (JSON)   | Luật tổng hợp trạng thái                      |

**Unique constraints**: `(config_id, step_order)`, `(config_id, output_name)`

**matching_rules JSON example:**
```json
{
  "match_type": "expression", /*có 2 trạng thái là expression hoặc advance*/
  "rules": [
    {
      "rule_name": "key_match",
      "expression": "LEFT['txn_id'] == RIGHT['ref_id']"
    },
    {
      "rule_name": "amount_match",
      "expression": "abs(LEFT['amount'] - RIGHT['total_amount']) <= 0.01",
      "left_number_transform": {
        "enabled": true,
        "thousandSeparator": ",",
        "decimalSeparator": "."
      }
    }
  ],
  "status_logic": {
    "all_match": "MATCHED",
    "no_key_match": "NOT_FOUND",
    "amount_mismatch": "MISMATCH"
  }
}
```

**status_combine_rules JSON example:**
```json
{
  "rules": [
    {"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"},
    {"b1b4": "NOT_FOUND", "b1b2": "MATCHED", "final": "REFUNDED"}
  ],
  "default": "UNKNOWN"
}
```

### 3.4 Bảng `output_config`

Cấu hình output columns — mỗi row = 1 output (A1, A4, ...).

| Column         | Type          | Note                                          |
|----------------|---------------|-----------------------------------------------|
| id             | INTEGER PK    |                                               |
| config_id      | INTEGER FK    | → partner_service_config.id                   |
| output_name    | VARCHAR(50)   | Tên output tùy ý, phải match với WorkflowStep.output_name |
| display_name   | VARCHAR(100)  | Tên hiển thị                                  |
| columns_config | TEXT (JSON)   | Cấu hình columns đầu ra                       |
| filter_status  | TEXT (JSON)   | Lọc theo trạng thái                           |
| use_for_report | BOOLEAN       | Dùng cho báo cáo?                             |
| display_order  | INTEGER       | Thứ tự hiển thị                               |

**Unique constraint**: `(config_id, output_name)`

**columns_config JSON example:**
```json
{
  "columns": [
    {"name": "stt", "source": "auto", "type": "row_number"},
    {"name": "txn_id", "source": "B1", "column": "txn_id", "display_name": "Mã giao dịch"},
    {"name": "amount", "source": "B4", "column": "total_amount", "display_name": "Số tiền"},
    {"name": "ref_no", "source": "A1_1", "column": "ref_no", "display_name": "Mã tham chiếu"},
    {"name": "status", "source": "MATCH_STATUS", "column": "match_status", "display_name": "Trạng thái"},
    {"name": "note", "source": "computed", "column": "match_detail", "display_name": "Ghi chú"}
  ]
}
```

**Các loại source trong columns_config:**

| Source type         | Mô tả                                                                 |
|---------------------|------------------------------------------------------------------------|
| `auto`              | Tự sinh (row_number, ...)                                             |
| `MATCH_STATUS` / `computed` | Lấy từ kết quả matching: `status`, `note`, `amount_diff`. Hỗ trợ alias: `match_status`→`status`, `match_detail`→`note` |
| Tên dataset bất kỳ (ví dụ: `B1`, `B4`, `A1_1`, ...) | Lookup giá trị từ dataset gốc qua `{source}_index` → tra bảng source |

### 3.5 Bảng `reconciliation_logs`

Log batch đối soát — 1 row = 1 lần chạy đối soát.

| Column          | Type          | Note                                          |
|-----------------|---------------|-----------------------------------------------|
| id              | INTEGER PK    |                                               |
| batch_id        | VARCHAR(100)  | Unique, format: `PARTNER_SERVICE_YYYYMMDD_HHMMSS_uuid8` |
| partner_code    | VARCHAR(50)   |                                               |
| service_code    | VARCHAR(50)   |                                               |
| config_id       | INTEGER       | Config ID đã dùng (no FK constraint)          |
| period_from     | DATE          | Kỳ đối soát từ                                |
| period_to       | DATE          | Kỳ đối soát đến                               |
| status          | VARCHAR(20)   | UPLOADING, PROCESSING, COMPLETED, APPROVED, FAILED, ERROR |
| created_by      | INTEGER FK    | → users.id                                    |
| approved_by     | INTEGER FK    | → users.id (NULL nếu chưa duyệt)             |
| approved_at     | DATETIME      |                                               |
| step_logs       | TEXT (JSON)   | Array step logs: `[{step, time, status, message, data_preview}]` |
| files_uploaded  | TEXT (JSON)   | `{source_name: [file_paths]}` — file đã upload |
| file_result_a1  | VARCHAR(500)  | Path file A1 (legacy)                         |
| file_result_a2  | VARCHAR(500)  | Path file A2 (legacy)                         |
| file_report     | VARCHAR(500)  | Path file report                              |
| file_results    | TEXT (JSON)   | Dict `{OUTPUT_NAME: csv_path}` cho TẤT CẢ outputs |
| summary_stats   | TEXT (JSON)   | Thống kê tổng hợp                             |
| error_message   | TEXT          | Thông báo lỗi                                 |

**Indexes**: `(partner_code, service_code)`, `(period_from, period_to)`, `(status)`

### 3.6 Bảng `users` & `user_permissions`

| Bảng              | Mô tả                                                        |
|-------------------|---------------------------------------------------------------|
| `users`           | email, password_hash, full_name, is_admin, is_active          |
| `user_permissions`| user_id, partner_code, service_code, can_reconcile, can_approve |

---

## 5. Backend — Models

Tất cả models nằm trong `backend/app/models/`:

| File                | Class                | Mô tả                                       |
|---------------------|----------------------|----------------------------------------------|
| `config.py`         | `PartnerServiceConfig` | Config chính với relationships đến child tables |
| `data_source.py`    | `DataSourceConfig`   | Nguồn dữ liệu, có `*_config_dict` properties  |
| `workflow.py`       | `WorkflowStep`       | Bước matching, có `matching_rules_dict`, `status_combine_rules_dict` |
| `output.py`         | `OutputConfig`       | Cấu hình output columns, có `get_columns_list()` |
| `reconciliation.py` | `ReconciliationLog`  | Batch log, có `file_results_dict`, `get_file_path(output_name)` |
| `user.py`           | `User`, `UserPermission` | User + phân quyền                        |

**Key properties trên ReconciliationLog:**
- `file_results_dict` → parse JSON `file_results` thành dict
- `get_file_path(output_name)` → tìm path output: check `file_results` trước, fallback sang `file_result_a1/a2`
- `is_locked` → True nếu status = APPROVED hoặc PENDING_APPROVAL

---

## 6. Backend — Services

### 5.1 GenericMatchingEngine (`services/generic_matching_engine.py`)

**Nguyên tắc thiết kế: MỘT hàm matching duy nhất cho TẤT CẢ cặp dataset.**

```
match_datasets(left_df, right_df, left_name, right_name, rules_config, join_type)
```

**Input:** 2 DataFrame + luật matching (JSON config)

**Output:** DataFrame với các cột:
- `{left_name}_index` — Index từ left DataFrame
- `{right_name}_index` — Index từ right DataFrame (NaN nếu không khớp)
- `status` — MATCHED, NOT_FOUND, MISMATCH
- `note` — Mô tả
- `amount_diff` — Chênh lệch số tiền

**Các mode matching:**
1. **Expression mode** (`match_type: "expression"`)
   - Parse expression `LEFT['col'] == RIGHT['col']` thành key columns
   - Hỗ trợ transforms: `.str.strip()`, `.str.upper()`, `.str.replace()`, `.str[start:end]`
   - Pandas merge (left/inner/right/outer join)
   - Deduplicate right side trước merge
   - Amount check riêng (tolerance, number transforms)

2. **Custom module mode** (`match_type: "custom_module"`)
   - Load Python module từ `storage/custom_matching/{module_name}.py`
   - Gọi function `match(left_df, right_df, rules_config, left_name, right_name)`

### 5.2 WorkflowExecutor (`services/workflow_executor.py`)

**Orchestrator chính cho quy trình đối soát V2.**

#### Flow:

```
execute()
  ├─ 1. _load_all_data_sources()     → Load B1, B2, B3, B4, ... vào self.datasets
  ├─ 2. _execute_workflow_steps()     → Chạy matching theo thứ tự step_order
  │     └─ _execute_single_step(step)
  │          ├─ matching_engine.match_datasets(left, right, ...)
  │          ├─ _apply_output_columns(raw_result, columns_config)   ← QUAN TRỌNG
  │          ├─ _apply_filter(resolved_df, filter_config)
  │          └─ Store resolved result vào self.datasets[output_name]
  ├─ 3. _build_outputs()             → Build remaining outputs chưa xử lý
  └─ 4. _calculate_stats()           → Tính thống kê
```

#### Điểm quan trọng: OutputConfig được áp dụng NGAY SAU matching

Khi step 1 (B1↔B4→A1_1) hoàn thành:
1. Raw result có `b1_index`, `b4_index`, `status`, `note`, `amount_diff`
2. OutputConfig cho A1_1 được áp dụng ngay → resolved DataFrame có `txn_id`, `amount`, `status`, ...
3. Resolved A1_1 được lưu vào `self.datasets["A1_1"]`
4. Step 3 (A1_1↔A1_2→A1) dùng resolved A1_1 (đã có column names thân thiện)

**Nếu không áp dụng ngay**, step 3 sẽ không tìm thấy `txn_id` trong A1_1 vì raw result chỉ có `b1_index`.

#### `_apply_output_columns(df, columns_config)`

Map từ raw matching result → output columns theo config:

| Source loại | Cách xử lý |
|-------------|-------------|
| `auto` (row_number) | Sinh `range(1, len+1)` |
| `computed` / `MATCH_STATUS` | Lấy từ `df['status']`, `df['note']`, `df['amount_diff']`. Alias: `match_status`→`status`, `match_detail`→`note` |
| Dataset name (B1, B4, A1_1, ...) | Tìm `{source}_index` trong df, lookup giá trị từ `self.datasets[SOURCE]` |

#### `MATCH_STATUS_COLUMN_MAP`
```python
{
    'match_status': 'status',
    'match_detail': 'note', 
    'amount_difference': 'amount_diff',
}
```

### 5.3 DataLoaderFactory + Data Loaders (`services/data_loaders/`)

**Factory pattern** — tạo loader phù hợp dựa trên `source_type`:

| Source Type   | Loader Class        | Mô tả                                          |
|---------------|--------------------|-------------------------------------------------|
| `FILE_UPLOAD` | `FileDataLoader`   | Load Excel (.xlsx/.xls/.xlsb), CSV, ZIP         |
| `DATABASE`    | `DatabaseDataLoader`| Query Oracle/SQLite hoặc load mock CSV           |

#### FileDataLoader

- Hỗ trợ **single file** hoặc **folder chứa nhiều files**
- Tự động extract ZIP files
- Merge multiple files thành 1 DataFrame
- Áp dụng `header_row`, `data_start_row`, column mapping, transforms
- Hỗ trợ: `.xlsx`, `.xls`, `.xlsb`, `.csv`, `.zip`

#### DatabaseDataLoader

- Đọc SQL template từ `storage/sql_templates/`
- Thay params (`date_from`, `date_to`, ...)
- Connect qua `config.ini` [database.{connection_name}]
- **Mock mode**: đọc CSV từ `storage/mock_data/` thay vì query DB thực

### 5.4 ReportGenerator (`services/report_generator.py`)

- Tạo temp table từ A1 data
- Execute SQL queries trên temp table
- Fill kết quả vào template Excel (openpyxl)
- Cell mapping cấu hình trong `PartnerServiceConfig.report_cell_mapping`

### 5.5 WorkflowService (`services/workflow_service.py`)

CRUD operations cho batch records — `create_batch()`, update status, etc.

> **Ghi nhớ kiến trúc:** Toàn bộ engine (GenericMatchingEngine, WorkflowExecutor, DataLoaders) làm việc hoàn toàn dựa trên config từ DB. Không có logic nào hardcode tên data source (B1/B2/B3/B4) hay tên output (A1/A2). Mọi tên gọi đều do admin cấu hình.

---

## 7. Backend — API Endpoints

### 6.1 API V1 (`/api/v1/`)

| Prefix          | Module                  | Mô tả                          |
|-----------------|------------------------|---------------------------------|
| `/auth`         | `auth.py`              | Login, get me, change password  |
| `/users`        | `users.py`             | CRUD users + permissions (Admin)|
| `/partners`     | `partners.py`          | List partners, services, config |
| `/configs`      | `configs.py`           | CRUD configs (Admin)            |
| `/mock-data`    | `mock_data.py`         | Upload/preview mock data (Admin)|
| `/reconciliation`| `reconciliation.py`   | Upload + run, list/get batches  |
| `/reports`      | `reports.py`           | Preview, download, generate report, stats |
| `/approvals`    | `approvals.py`         | Submit, approve, reject, unlock |

#### Key V1 Endpoints:

| Method | Path                          | Mô tả                                  |
|--------|-------------------------------|-----------------------------------------|
| POST   | `/reconciliation/upload`      | Upload files + chạy đối soát (1 bước)  |
| GET    | `/reconciliation/batches`     | Danh sách batch                         |
| GET    | `/reconciliation/batches/{id}`| Chi tiết batch                          |
| POST   | `/reconciliation/batches/{id}/rerun` | Chạy lại batch                   |
| DELETE | `/reconciliation/batches/{id}`| Xóa batch                               |
| GET    | `/reports/preview/{batch_id}/{file_type}` | Preview output (bất kỳ output name) |
| GET    | `/reports/download/{batch_id}/{file_type}` | Download CSV/Excel |
| POST   | `/reports/generate/{batch_id}` | Generate report từ template           |
| GET    | `/reports/stats/{batch_id}`   | Thống kê chi tiết + `output_stats` + `file_results` |

**`/reports/preview/{batch_id}/{file_type}`:**
- `file_type` chấp nhận bất kỳ output name (a1, a4, ...) — không chỉ a1/a2
- Dùng `batch.get_file_path(file_type)` để tìm file path
- Pagination: `skip` + `limit`
- Filter: `status_b1b4`, `status_b1b2`, `status_b3a1`, `final_status`

**`/reports/stats/{batch_id}`:**
- Trả về `output_stats` (dynamic, từ `file_results` dict) + `a1_stats` + `a2_stats` (legacy)
- Trả về `file_results` dict: `{OUTPUT_NAME: file_path}`
- Trả về `final_status_options` (parse từ workflow step's `status_combine_rules`)

### 6.2 API V2 (`/api/v2/`)

| Prefix           | Module              | Mô tả                              |
|------------------|---------------------|-------------------------------------|
| `/configs`       | `configs.py`        | CRUD partner_service_config         |
| `/data-sources`  | `data_sources.py`   | CRUD data_source_config             |
| `/workflows`     | `workflows.py`      | CRUD workflow_step                  |
| `/outputs`       | `outputs.py`        | CRUD output_config                  |
| `/reconciliation`| `reconciliation.py` | Upload files, run, list, rerun      |

#### Key V2 Endpoints:

| Method | Path                                  | Mô tả                            |
|--------|---------------------------------------|-----------------------------------|
| POST   | `/reconciliation/upload-files/{config_id}` | Upload files (tách riêng) |
| POST   | `/reconciliation/run`                 | Chạy đối soát (WorkflowExecutor)  |
| POST   | `/reconciliation/check-duplicate`     | Kiểm tra batch trùng             |
| DELETE | `/reconciliation/batches/{batch_id}`  | Xóa batch + files                |
| GET    | `/reconciliation/batches`             | Danh sách batch (paginated)       |
| GET    | `/reconciliation/batches/{batch_id}`  | Chi tiết batch + data_sources info|
| POST   | `/reconciliation/batches/{batch_id}/rerun` | Chạy lại batch (WorkflowExecutor) |

#### Upload flow (V2):

1. **Upload files**: `POST /upload-files/{config_id}`
   - Gửi kèm `source_names` (comma-separated): `"B1,B4,B1,B3"` (có thể lặp cho multi-file)
   - Files lưu vào `uploads/{partner_code}/{batch_folder}/{source_name}/`
   - Hỗ trợ: `.xlsx`, `.xls`, `.xlsb`, `.csv`, `.zip`
   - Trả về `batch_folder` để dùng cho bước run

2. **Check duplicate**: `POST /check-duplicate`
   - Tìm batch trùng partner+service+period
   - Trả về `has_duplicate`, `approved_conflict`, `duplicates[]`
   - Nếu `approved_conflict=true` → không cho tạo batch mới

3. **Run**: `POST /run?batch_folder=xxx&force_replace=false`
   - Nếu có duplicate chưa duyệt + `force_replace=true` → xóa batch cũ
   - Tạo `WorkflowExecutor` → `execute()` → export outputs → save batch record
   - Lưu `file_results` JSON với tất cả output paths
   - Trả về `ReconciliationResponse` (batch_id, outputs, step_logs, ...)

4. **Rerun**: `POST /batches/{batch_id}/rerun`
   - Rebuild `file_paths` từ `files_uploaded` JSON
   - Chạy lại `WorkflowExecutor` → update batch record

#### Export & Stats Logic (`_export_outputs_and_build_stats`):

- Export mỗi output DataFrame → CSV file
- Build `file_results` dict: `{OUTPUT_NAME: csv_path}`
- Build `summary_stats` (V1-compatible): `total_b1`, `total_b4`, `matching_stats.{step_key}`
- Cũng build `output_details` (V2-style): `{output_name: {row_count, status_counts}}`
- Save `file_results` JSON vào DB column

---

## 8. Frontend

### 7.1 Routes

| Path                            | Page Component          | Mô tả                    |
|---------------------------------|------------------------|---------------------------|
| `/`                             | `DashboardPage`        | Dashboard                 |
| `/login`                        | `LoginPage`            | Đăng nhập                 |
| `/reconciliation`               | `ReconciliationPage`   | Đối soát V1               |
| `/reconciliation-v2`            | `ReconciliationV2Page` | Đối soát V2 (3-step wizard)|
| `/batches`                      | `BatchListPage`        | Danh sách batch            |
| `/batches/:batchId`             | `BatchDetailPage`      | Chi tiết batch             |
| `/approvals`                    | `ApprovalsPage`        | Phê duyệt                 |
| `/admin/users`                  | `UsersPage`            | Quản lý users (Admin)     |
| `/admin/configs`                | `ConfigsPage`          | Config V1 (Admin)          |
| `/admin/configs-v2`             | `ConfigsV2Page`        | Config V2 list (Admin)     |
| `/admin/configs-v2/new`         | `ConfigEditV2Page`     | Tạo config V2 (Admin)     |
| `/admin/configs-v2/:id`         | `ConfigDetailV2Page`   | Chi tiết config V2 (Admin) |
| `/admin/configs-v2/:id/edit`    | `ConfigEditV2Page`     | Sửa config V2 (Admin)     |
| `/admin/mock-data`              | `MockDataPage`         | Quản lý mock data (Admin)  |

### 7.2 ReconciliationV2Page — 3-Step Wizard

**Step 1: Select Config**
- Load danh sách configs từ `configsApiV2.list()`
- Chọn cấu hình → load data sources từ `dataSourcesApiV2.getByConfig(configId)`
- Nhập period_from/period_to

**Step 2: Upload Files**
- Hiển thị dropzones cho mỗi FILE_UPLOAD data source
- Hỗ trợ drag & drop, multi-file per source
- File types: Excel (.xlsx, .xls, .xlsb), CSV, ZIP
- Upload gọi `reconciliationApiV2.uploadFiles(configId, files, sourceNames)`

**Step 3: Run & Review**
- Check duplicate trước khi chạy: `reconciliationApiV2.checkDuplicate()`
- Nếu trùng:
  - Approved → block (không cho tạo mới)
  - Unapproved → hiện warning, cho phép force replace
- Chạy: `reconciliationApiV2.run(requestData, batchFolder, forceReplace)`
- Hiển thị kết quả: step_logs, output counts, download links
- Error → hiển thị step_logs từ `detail.step_logs`

### 7.3 BatchDetailPage — Dynamic Output Sections

**Key component: `OutputDetailSection`**

```jsx
function OutputDetailSection({ outputName, batchId, outputStats }) {
  // Tự quản lý state + query riêng cho pagination
  // Gọi reportsApi.preview(batchId, outputName.toLowerCase(), {skip, limit})
  // Hiển thị:
  //   - Header: "Chi tiết {outputName} ({total} bản ghi)"
  //   - Download buttons: CSV + Excel
  //   - Status breakdown badges
  //   - Data table với pagination
}
```

**Dynamic output rendering:**
- Fetch `stats` từ `reportsApi.getStats(batchId)`
- Loop `stats.file_results` → render `OutputDetailSection` cho mỗi output
- `stats.output_stats[outputName]` → truyền vào `outputStats` prop
- Download buttons tự generate cho mỗi output

### 7.4 API Services (`services/api.js`)

2 axios instances:
| Instance | baseURL    | Mô tả |
|----------|-----------|--------|
| `api`    | `/api/v1` | V1 API |
| `apiV2`  | `/api/v2` | V2 API |

Cả 2 dùng chung interceptor cho JWT auth (Bearer token).

**Exported API objects:**
- `authApi` — login, getMe, changePassword
- `partnersApi` — list partners, services
- `reconciliationApi` — V1 reconciliation ops
- `reconciliationApiV2` — V2 upload, run, check-duplicate, list, rerun
- `reportsApi` — preview, download (blob), generateReport, getStats
- `approvalsApi` — submit, approve, reject, unlock
- `configsApi` — V1 config CRUD
- `configsApiV2` — V2 config CRUD
- `dataSourcesApiV2` — data source CRUD
- `workflowsApiV2` — workflow step CRUD
- `outputsApiV2` — output config CRUD
- `usersApi` — user CRUD + permissions
- `mockDataApi` — mock data management

---

## 9. Luồng xử lý chính (Workflow)

### Ví dụ: SACOMBANK / TOPUP

```
Data Sources:
  B1 = Sao kê ngân hàng (FILE_UPLOAD, required)
  B2 = Dữ liệu hoàn tiền (FILE_UPLOAD, optional)
  B3 = Chi tiết đối tác (FILE_UPLOAD, optional)
  B4 = Dữ liệu giao dịch VNPT Money (DATABASE, required)

Workflow Steps:
  Step 1: B1 ↔ B4 → A1_1  (intermediate)
  Step 2: B1 ↔ B2 → A1_2  (intermediate)
  Step 3: A1_1 ↔ A1_2 → A1 (final output — kết quả đối soát chi tiết)
  Step 4: A1_1 ↔ A1_2 → A4 (final output — ví dụ: báo cáo sai lệch)
```

### Chi tiết từng bước:

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: B1 ↔ B4 → A1_1                                    │
│  Input:  B1 DataFrame, B4 DataFrame                         │
│  Engine: GenericMatchingEngine.match_datasets()              │
│  Output raw: b1_index, b4_index, status, note, amount_diff  │
│  Apply OutputConfig A1_1 → resolved columns (txn_id, ...)   │
│  Store: self.datasets["A1_1"] = resolved DataFrame          │
└─────────────────────────────────────────────────────────────┘
       ↓ A1_1 resolved (có column names thân thiện)
┌─────────────────────────────────────────────────────────────┐
│  Step 2: B1 ↔ B2 → A1_2                                    │
│  Input:  B1 DataFrame, B2 DataFrame                         │
│  Output raw: b1_index, b2_index, status, note, amount_diff  │
│  Apply OutputConfig A1_2 → resolved columns                 │
│  Store: self.datasets["A1_2"] = resolved DataFrame          │
└─────────────────────────────────────────────────────────────┘
       ↓ A1_2 resolved
┌─────────────────────────────────────────────────────────────┐
│  Step 3: A1_1 ↔ A1_2 → A1 (FINAL)                          │
│  Input:  A1_1 resolved, A1_2 resolved                       │
│  Output raw: a1_1_index, a1_2_index, status, note           │
│  Apply OutputConfig A1 → resolved columns                   │
│    - Source "A1_1" → lookup từ self.datasets["A1_1"]        │
│    - Source "A1_2" → lookup từ self.datasets["A1_2"]        │
│    - Source "MATCH_STATUS" → lấy status/note từ raw result  │
│  Store: self.outputs["A1"] = final DataFrame                │
└─────────────────────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: A1_1 ↔ A1_2 → A4 (FINAL)                          │
│  (Tương tự Step 3 nhưng columns/filter khác)                │
└─────────────────────────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────────────────────────┐
│  Export: mỗi output → CSV file                              │
│  file_results = {"A1": "path/A1.csv", "A4": "path/A4.csv"} │
│  Save batch record → reconciliation_logs                    │
└─────────────────────────────────────────────────────────────┘
```

### Key insight: Chaining

Output columns được apply **NGAY SAU matching** (trong `_execute_single_step`), và kết quả resolved được dùng làm **input cho step tiếp theo**. Điều này cho phép:

- Step 3 (A1_1↔A1_2→A1) reference columns từ A1_1/A1_2 bằng **tên column thân thiện** (e.g., `txn_id`, `amount`), thay vì raw index columns (`b1_index`, `b4_index`)
- OutputConfig cho A1 có thể reference `{"source": "A1_1", "column": "txn_id"}` — lookup trực tiếp từ resolved A1_1

---

## 10. Cấu hình đối soát (Configuration)

### Config INI (`backend/config.ini`)

```ini
[server]
host = 127.0.0.1
port = 8001

[database.app]
type = sqlite
path = ./data/app.db

[database.vnptmoney_main]
type = oracle
dsn = 10.0.0.1:1521/vnptmoney
user = readonly_user
password = secret_password_1

[mock]
enabled = true          # true = dùng mock CSV thay vì query Oracle

[storage]
base_path = ./storage
uploads = ./storage/uploads
exports = ./storage/exports
templates = ./storage/templates
sql_templates = ./storage/sql_templates
mock_data = ./storage/mock_data
custom_matching = ./storage/custom_matching
```

### Config từ Database (V2)

Mọi cấu hình đối soát được lưu trong DB:

1. **PartnerServiceConfig** — master record
2. **DataSourceConfig** — danh sách data sources (tên tùy ý, không giới hạn số lượng)
3. **WorkflowStep** — danh sách steps matching theo thứ tự
4. **OutputConfig** — cấu hình columns cho mỗi output

Admin quản lý qua:
- Frontend: `/admin/configs-v2`
- API: `GET/POST/PATCH/DELETE /api/v2/configs/`, `data-sources/`, `workflows/`, `outputs/`

---

## 11. Storage & File Structure

### Upload Structure

```
storage/uploads/
└── {partner_code}/
    └── {batch_folder}/                 # e.g., SACOMBANK_TOPUP_20260211_093045
        ├── b1/
        │   ├── 000_FILE_1_01-05.01.2026.xlsb
        │   ├── 001_FILE_2_06-10.01.2026.xlsb
        │   └── 002_FILE_3_11-15.01.2026.xlsb
        └── b4/
            └── 000_Findata_mock.csv
```

### Export Structure

```
storage/exports/
└── {partner_code}/
    └── {batch_id}/
        ├── A1_{batch_id}.csv
        ├── A4_{batch_id}.csv
        └── (report.xlsx nếu có template)
```

### Template Structure

```
storage/templates/
└── shared/
    └── report_template.xlsx
```

### SQL Templates

```
storage/sql_templates/
└── shared/
    └── query_topup.sql
```

### Custom Matching Modules

```
storage/custom_matching/
└── sacombank_topup.py      # Custom matching function
```

---

## 12. Authentication & Authorization

### JWT Authentication

- Login → `POST /api/v1/auth/login` → { access_token, token_type }
- Token hết hạn: `ACCESS_TOKEN_EXPIRE_MINUTES = 480` (8 giờ)
- Frontend lưu token trong `localStorage` (zustand persist)
- Mỗi request gửi `Authorization: Bearer {token}`

### Authorization

- `User.is_admin` → quyền admin (quản lý config, users, mock data)
- `UserPermission` → phân quyền theo `partner_code` + `service_code`:
  - `can_reconcile` — có quyền chạy đối soát
  - `can_approve` — có quyền phê duyệt
- V2 API hiện **chưa enforce auth** đầy đủ (TODO)

### Approval Workflow

1. Batch COMPLETED → user submit for approval
2. Approver → approve hoặc reject (với notes)
3. APPROVED batch → locked, không thể rerun/delete
4. Có thể unlock (admin)

---

## 13. Logging

### Log Files (`backend/logs/`)

| Logger              | File                     | Mô tả                            |
|---------------------|--------------------------|-----------------------------------|
| `api`               | `api.log.{date}`         | HTTP request/response logs         |
| `app`               | `app.log.{date}`         | Application logs                   |
| `reconciliation`    | `reconciliation.log.{date}` | Matching engine logs           |
| `report`            | `report.log.{date}`      | Report generation logs             |

### Step Logs

Mỗi batch có `step_logs` JSON array, ghi lại từng bước:

```json
[
  {"step": "init", "time": "2026-02-11T09:30:45", "status": "start", "message": "Starting workflow..."},
  {"step": "load_B1", "time": "...", "status": "ok", "message": "Loaded B1: 5000 rows in 0.5s", "data_preview": {...}},
  {"step": "load_B4", "time": "...", "status": "ok", "message": "Loaded B4: 4800 rows in 1.2s", "data_preview": {...}},
  {"step": "step_1_B1_B4", "time": "...", "status": "ok", "message": "Completed: 5000 rows, MATCHED=4500, NOT_FOUND=500"},
  {"step": "step_2_B1_B2", "time": "...", "status": "ok", "message": "..."},
  {"step": "complete", "time": "...", "status": "ok", "message": "Workflow completed in 3.5s"}
]
```

`data_preview` chứa:
- `source_name`, `display_name`
- `columns`, `rows` (first 10 rows)
- `total_rows`

---

## Phụ lục: Sơ đồ tổng quan

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Frontend    │────▶│  FastAPI Backend  │────▶│  SQLite DB  │
│  React+Vite  │     │  Port 8001       │     │  app.db     │
│  Port 3001   │     │                  │     └─────────────┘
└─────────────┘     │  /api/v1/ (legacy)│
                     │  /api/v2/ (dynamic)│    ┌─────────────┐
                     │                  │────▶│  Oracle DB  │
                     │  Services:       │     │  (production)│
                     │  - WorkflowExec. │     └─────────────┘
                     │  - MatchingEngine│
                     │  - DataLoaders   │     ┌─────────────┐
                     │  - ReportGen.    │────▶│  Storage    │
                     └──────────────────┘     │  uploads/   │
                                              │  exports/   │
                                              │  templates/ │
                                              │  mock_data/ │
                                              └─────────────┘
```
