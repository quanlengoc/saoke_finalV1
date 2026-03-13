# Reconciliation System V2 - Development Plan

> **Ngày tạo:** 2026-02-11  
> **Mục tiêu:** Xây dựng hệ thống đối soát linh hoạt với workflow động, hỗ trợ số lượng cặp matching và nguồn dữ liệu không giới hạn.

---

## 1. Tổng quan yêu cầu

### 1.1. Vấn đề với V1

| Vấn đề | Mô tả |
|--------|-------|
| **Hardcoded workflow** | Cố định 4 bước: B1↔B4, B1↔B2, combine, B3↔A1 |
| **Fixed data sources** | Chỉ hỗ trợ B1, B2, B3, B4 |
| **Fixed outputs** | Chỉ có A1, A2 |
| **Code duplication** | Mỗi cặp matching có hàm riêng |
| **Khó mở rộng** | Thêm cặp mới = sửa code + DB schema + UI |

### 1.2. Mục tiêu V2

- ✅ **Dynamic workflow**: Cấu hình số lượng bước matching không giới hạn
- ✅ **Dynamic data sources**: Thêm/bớt nguồn dữ liệu (B1, B2, ..., Bn)
- ✅ **Dynamic outputs**: Cấu hình output nào dùng cho report
- ✅ **Single matching engine**: 1 hàm generic cho tất cả cặp matching
- ✅ **Extensible data loaders**: FILE_UPLOAD, DATABASE, mở rộng SFTP/API sau
- ✅ **Production-ready logging**: Log chi tiết cho vận hành

---

## 2. Yêu cầu tính năng chi tiết

### 2.1. Cấu hình cho Đối tác + Dịch vụ + Thời gian áp dụng

#### A. Data Sources (Nguồn dữ liệu)

| Field | Mô tả | Ví dụ |
|-------|-------|-------|
| `source_name` | Tên nguồn (unique) | B1, B2, B4, B5 |
| `source_type` | Loại nguồn | FILE_UPLOAD, DATABASE, SFTP, API |
| `display_name` | Tên hiển thị | "Sao kê ngân hàng" |
| `is_required` | Bắt buộc? | true/false |
| `file_config` | Cấu hình file | header_row, columns |
| `db_config` | Cấu hình DB | connection, sql_file |
| `sftp_config` | Cấu hình sFTP | path pattern: `yyyymmdd/SACOMBANK_*.xlsx` |

#### B. Workflow Steps (Các bước matching)

| Field | Mô tả |
|-------|-------|
| `step_order` | Thứ tự (auto) |
| `left_source` | Nguồn trái (driver) |
| `right_source` | Nguồn phải (lookup) |
| `join_type` | LEFT, INNER, RIGHT, OUTER |
| `matching_rules` | key_match, amount_match |
| `output_name` | Tên kết quả |
| `is_final_output` | Dùng cho report? |

#### C. Output Configs

| Field | Mô tả |
|-------|-------|
| `output_name` | Tên output |
| `columns` | Columns và nguồn |
| `use_for_report` | Dùng trong report SQL? |
| `filter_status` | Lọc status (optional) |

#### D. Validation
- Thời gian áp dụng không overlap (cùng partner + service)
- Validate khi save

---

### 2.2. Tạo Batch đối soát

- Chọn đối tác → Chọn dịch vụ → Chu kỳ
- Chu kỳ phải nằm trong thời gian áp dụng config
- Upload files: Dynamic dropzones từ data sources (FILE_UPLOAD)
- Mỗi batch gắn với `config_id`

### 2.3. Hiển thị kết quả

- Hiển thị theo outputs được cấu hình (`is_final_output=true`)
- Không fix cứng A1, A2
- Stats theo từng output

---

## 3. DB Schema mới

```sql
-- Bảng chính (đơn giản hóa)
CREATE TABLE partner_service_config (
    id INTEGER PRIMARY KEY,
    partner_code VARCHAR(50) NOT NULL,
    partner_name VARCHAR(255) NOT NULL,
    service_code VARCHAR(50) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    valid_from DATE NOT NULL,
    valid_to DATE,
    report_template_path VARCHAR(500),
    report_cell_mapping TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(partner_code, service_code, valid_from)
);

-- Nguồn dữ liệu động
CREATE TABLE data_source_config (
    id INTEGER PRIMARY KEY,
    config_id INTEGER REFERENCES partner_service_config(id),
    source_name VARCHAR(20) NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    display_name VARCHAR(100),
    is_required BOOLEAN DEFAULT FALSE,
    display_order INTEGER DEFAULT 0,
    file_config TEXT,
    db_config TEXT,
    sftp_config TEXT,
    api_config TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(config_id, source_name)
);

-- Workflow steps
CREATE TABLE workflow_step (
    id INTEGER PRIMARY KEY,
    config_id INTEGER REFERENCES partner_service_config(id),
    step_order INTEGER NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    left_source VARCHAR(50) NOT NULL,
    right_source VARCHAR(50) NOT NULL,
    join_type VARCHAR(10) DEFAULT 'left',
    matching_rules TEXT NOT NULL,
    output_name VARCHAR(50) NOT NULL,
    is_final_output BOOLEAN DEFAULT FALSE,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(config_id, step_order),
    UNIQUE(config_id, output_name)
);

-- Output config
CREATE TABLE output_config (
    id INTEGER PRIMARY KEY,
    config_id INTEGER REFERENCES partner_service_config(id),
    output_name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100),
    columns_config TEXT NOT NULL,
    filter_status TEXT,
    use_for_report BOOLEAN DEFAULT TRUE,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(config_id, output_name)
);

backend/app/
├── models/
│   ├── [config.py](http://_vscodecontentref_/1)           # PartnerServiceConfig (simplified)
│   ├── data_source.py      # DataSourceConfig (NEW)
│   ├── workflow.py         # WorkflowStep (NEW)
│   └── output.py           # OutputConfig (NEW)
│
├── services/
│   ├── generic_matching_engine.py  # Core matching
│   ├── workflow_executor.py        # Execute from DB (NEW)
│   └── data_loaders/               # Loaders by type (NEW)
│       ├── base_loader.py
│       ├── file_loader.py
│       └── database_loader.py
│
└── api/v1/endpoints/
    ├── configs.py          # Updated CRUD
    ├── data_sources.py     # NEW
    └── workflow_steps.py   # NEW

# Log files
logs/
├── app.log              # General
├── reconciliation.log   # Matching engine
├── api.log              # API requests
├── data_loader.log      # Data loading (NEW)
└── workflow.log         # Workflow execution (NEW)

# Format với correlation_id (batch_id)
{timestamp} | {level} | {logger} | {file}:{line} | {batch_id} | {message}