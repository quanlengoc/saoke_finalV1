# Kế hoạch Hệ thống Đối soát (Reconciliation System)

## 1. Tổng quan

Hệ thống đối soát tự động giữa các đối tác của VNPT Money với VNPT Money theo từng dịch vụ. Mỗi một cặp đối tác + dịch vụ sẽ có quy tắc đối soát và xuất ra báo cáo khác nhau. Có phân quyền chức năng 
---

## 2. Mô tả yêu cầu

### 2.1. Bài toán
#### Yêu cầu chung: 
- Cho phép cấu hình nguyên tắc so khớp và báo cáo kết quả đầu ra theo từng đối tác + dịch vụ, nguyên tắc số khớp gồm nhiều bước, kết quả bước trước có thể là đầu vào của bước sau 
- Cho phép chạy so khớp cho đối tác + dịch vụ theo từng khoảng thời gian và xuất ra báo cáo chi tiết, tổng hợp cuối cùng 
- Với mỗi lần chạy so khớp cần lưu lại lịch sử xử lý tửng bước 
- Có phân quyền người dùng cho các chứng năng 
#### Chi tiết thực hiện phần so khớp: 
- B1: Người dùng cấu hình nguyên tắc so khớp với từng đối tác + dịch vụ, nguyên tắc so khớp bao gồm các thông tin như sau:
- - Danh sách nguồn dữ liệu: mỗi nguồn dữ liệu sẽ mã + tên gọi, và nguồn dữ liệu đó được lấy từ nhiều hình thức như từ file các file Upload, từ SQL + kết nối CSDL, từ file sFTP có đường dẫn, ... các hình thức lấy dũ liệu có thể bổ sung dần về sau. Các cột dữ liệu từ File hoặc CSDL sẽ lấy ra và alias tương ứng là gì. Có nguồn là bắt buộc, nguồn không bắt buộc, nhưng phải có ít nhất 1 nguồn là bắt buộc 
- - Danh sách các bước so khớp: mỗi bước so khớp sẽ bao gồm 2 nguồn dữ liệu được chọn từ danh sách nguồn dữ liệu, loại so khớp là left, right,inner, full outer ... và cấu hình cách thức key so khớp, và amount so khớp. Key so khớp có thể combine nhiều cột ở mỗi nguồn và có một số hàm xử lý đơn giản. Amount so khớp thì chỉ chọn từ 1 cột ở mỗi nguồn và có bước xử lý chuỗi cũng như transform dấu ngăn nghìn và dấu ngăn thập phân. Kết quả so khớp sẽ được đánh dấu là kết quả để sử dụng trung gian để làm đầu vào cho bước sau hoặc là dùng để xuất báo. 
- - Xuất bao cáo: Chọn file template báo cáo (cho phép upload file template), cấu hình cho từng sheet, mỗi sheet có xuất dữ liệu cho các ô cụ thể, hoặc 1 bảng dữ liệu chi tiết bắt đầu từ 1 ô nào đó. 
- - Lưu ý: tại mỗi bước cấu hình phải cho save luôn vì việc cấu hình rất phức tạp 

- B2: Người dùng tạo batch so khớp: chọn đối tác + dịch vụ + khoảng so khớp (ngày bắt đầu + ngày kết thúc )
- - Mỗi batch có trạng thái đang chạy, đã duyệt
- - KHi tạo batch mới nếu bị trùng đối tác + dịch vụ + khoảng so khớp đã tồn tại thì batch đã tồn tại không phải trạng thái đã duyệt thì cảnh báo người dùng về việc nếu tiếp tục thì sẽ xoá batch cũ và thực hiện lại từ đầu. (batch cũ được xoá thì phải xoá cả liệu đã upload hay load về và output ra để tránh nặng hệ thống), nếu batch cũ đã duyệt thì ko được tạo batch mới có thông tin bị trùng 
- - Với mỗi nguồn dữ liệu mà có dạng file như file upload hay sFTP thì có cho chọn nhiều file bao gồm cả file zip/rar, hỗ trợ ít nhất các định dạng txt, xlsx, xls, xlsb, csv, sau đó có thể bổ sung thêm. Có ghi chú cho người dùng loại file support. 
- - Kết quả batch 
- - Lưu và hiển thị lịch sử từng bước xử lý để người dùng biết là hệ thống vẫn đang chạy 

#### Lưu ý: 
- Viết các hàm chung để có tái sử dụng và khi sửa thì chỉ sửa 1 nơi ví dụ hàm so khớp
- Viết component chung để có thể sử dụng và khi sửa thì chỉ sửa 1 nơi ví cụ component con nguồn dữ liệu, component con bươc so khớp, ... , component cha cấu hình cho 1 dịch vụ + Đối tác 


### 2.2. Yêu cầu chức năng

| STT | Chức năng | Mô tả |
|-----|-----------|-------|
| 1 | Import dữ liệu B4 | Lấy dữ liệu giao dịch từ database nội bộ |
| 2 | Import sao kê Partner | Đọc file Excel/CSV sao kê từ đối tác |
| 3 | Cấu hình Rule | Cho phép cấu hình các rule đối soát linh hoạt |
| 4 | Thực hiện đối soát | Chạy so khớp theo rule đã cấu hình |
| 5 | Xuất báo cáo | Xuất kết quả đối soát ra file Excel |
| 6 | Lưu lịch sử | Lưu kết quả đối soát vào database |

### 2.3. Yêu cầu phi chức năng

- Hỗ trợ đối soát **nhiều dịch vụ** (TOPUP, PINCODE, ...)
- Hỗ trợ đối soát **nhiều đối tác** (VIETTEL, MOBIFONE, ...)
- Cấu hình rule **linh hoạt** qua file YAML
- **Mở rộng** dễ dàng khi thêm dịch vụ/đối tác mới
- Xử lý được **dữ liệu lớn** (hàng triệu giao dịch)

---

## 3. Định hướng lập trình

### 3.1. Công nghệ sử dụng

| Thành phần | Công nghệ | Lý do |
|------------|-----------|-------|
| Backend | Python 3.10+ | Xử lý data tốt, thư viện phong phú |
| Database Dev | SQLite | Nhẹ, không cần cài đặt, dùng để test |
| Database Prod | Oracle | Database production thực tế |
| DB Driver | cx_Oracle / oracledb | Kết nối Oracle |
| Data Processing | Pandas | Xử lý DataFrame hiệu quả |
| Config | INI + YAML | INI cho DB, YAML cho rules |
| Report | openpyxl/xlsxwriter | Xuất Excel |

### 3.2. Kiến trúc hệ thống

```
reconciliation-system/
├── config/
│   ├── config.ini             # Cấu hình DB (SQLite/Oracle)
│   ├── config.ini.example     # File mẫu config
│   ├── services.yaml          # Danh sách dịch vụ
│   └── rules/
│       ├── topup_viettel.yaml
│       ├── topup_mobifone.yaml
│       ├── pincode_viettel.yaml
│       └── ...
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config_loader.py   # Load cấu hình INI + YAML
│   │   ├── database.py        # Database factory (SQLite/Oracle)
│   │   ├── rule_engine.py     # Engine xử lý rule
│   │   └── matcher.py         # Logic so khớp
│   ├── data/
│   │   ├── __init__.py
│   │   ├── b4_loader.py       # Load dữ liệu B4
│   │   ├── partner_loader.py  # Load sao kê Partner
│   │   └── transformers.py    # Chuẩn hóa dữ liệu
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── excel_report.py    # Xuất báo cáo Excel
│   │   └── summary.py         # Tạo báo cáo tổng hợp
│   └── main.py                # Entry point
├── storage/
│   ├── input/                 # File sao kê đầu vào
│   ├── output/                # File báo cáo đầu ra
│   ├── database/              # SQLite database files
│   │   └── test.db
│   └── sql_templates/         # SQL query templates
│       ├── sqlite/            # SQL cho SQLite
│       └── oracle/            # SQL cho Oracle
├── tests/
│   ├── test_matcher.py
│   ├── test_rule_engine.py
│   └── ...
├── requirements.txt
└── README.md
```

### 3.3. Cấu hình Database (config.ini)

```ini
# File: config/config.ini

[database]
# Chọn driver: sqlite hoặc oracle
driver = sqlite

[sqlite]
# Đường dẫn file SQLite (dùng cho dev/test)
database = storage/database/test.db

[oracle]
# Cấu hình Oracle (dùng cho production)
host = 10.0.0.1
port = 1521
service_name = ORCL
username = recon_user
password = ${ORACLE_PASSWORD}
# Hoặc dùng TNS
# tns_name = PROD_DB

[logging]
level = INFO
file = storage/logs/reconciliation.log
```

```ini
# File: config/config.ini.example (Không chứa thông tin nhạy cảm)

[database]
driver = sqlite

[sqlite]
database = storage/database/test.db

[oracle]
host = your_oracle_host
port = 1521
service_name = your_service_name
username = your_username
password = your_password

[logging]
level = INFO
file = storage/logs/reconciliation.log
```

### 3.4. Database Factory Pattern

```python
# File: src/core/database.py (Mô tả logic)

"""
Database Factory - Hỗ trợ chuyển đổi SQLite <-> Oracle qua config

Sử dụng:
    from src.core.database import get_connection
    
    conn = get_connection()  # Tự động đọc config.ini
    df = pd.read_sql(query, conn)
"""

# Đọc config.ini -> lấy driver
# Nếu driver = 'sqlite' -> dùng sqlite3
# Nếu driver = 'oracle' -> dùng cx_Oracle hoặc oracledb
```

### 3.5. SQL Templates theo Database

```
storage/sql_templates/
├── sqlite/
│   ├── query_b4_topup.sql      # Cú pháp SQLite
│   ├── query_b4_pincode.sql
│   └── ...
├── oracle/
│   ├── query_b4_topup.sql      # Cú pháp Oracle (TO_DATE, NVL, ...)
│   ├── query_b4_pincode.sql
│   └── ...
└── shared/
    └── ...                      # SQL chung nếu có
```

**Ví dụ khác biệt SQL:**

```sql
-- SQLite: storage/sql_templates/sqlite/query_b4_topup.sql
SELECT 
    transaction_ref,
    datetime(transaction_date) as transaction_date,
    COALESCE(partner_ref, '') as partner_ref,
    total_amount
FROM transactions
WHERE service_id = :service_id
  AND transaction_date BETWEEN :date_from AND :date_to

-- Oracle: storage/sql_templates/oracle/query_b4_topup.sql
SELECT 
    transaction_ref,
    TO_CHAR(transaction_date, 'YYYY-MM-DD HH24:MI:SS') as transaction_date,
    NVL(partner_ref, '') as partner_ref,
    total_amount
FROM transactions
WHERE service_id = :service_id
  AND transaction_date BETWEEN TO_DATE(:date_from, 'YYYY-MM-DD') 
                           AND TO_DATE(:date_to, 'YYYY-MM-DD')
```

### 3.6. Luồng xử lý chính

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT                                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ Database B4 │    │ File Excel  │    │ Config YAML │          │
│  │ (Nội bộ)    │    │ (Sao kê)    │    │ (Rules)     │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PROCESSING                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ B4 Loader   │    │ Partner     │    │ Config      │          │
│  │             │    │ Loader      │    │ Loader      │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              Transformer (Chuẩn hóa data)           │        │
│  └─────────────────────────┬───────────────────────────┘        │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              Rule Engine (Áp dụng rules)            │        │
│  └─────────────────────────┬───────────────────────────┘        │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              Matcher (So khớp giao dịch)            │        │
│  └─────────────────────────┬───────────────────────────┘        │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ Excel       │    │ Database    │    │ Summary     │          │
│  │ Report      │    │ Results     │    │ Report      │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.7. Nguyên tắc thiết kế

| Nguyên tắc | Mô tả |
|------------|-------|
| **Single Responsibility** | Mỗi module chỉ làm 1 việc |
| **Open/Closed** | Dễ mở rộng, không sửa code cũ |
| **Dependency Injection** | Inject config, không hardcode |
| **Configuration over Code** | Cấu hình qua YAML, không sửa code |
| **Testable** | Viết unit test cho từng module |

### 3.8. Mở rộng hệ thống

Khi thêm **dịch vụ mới** hoặc **đối tác mới**:

1. Tạo file config rule mới: `config/rules/{service}_{partner}.yaml`
2. Tạo SQL query mới: 
   - `storage/sql_templates/sqlite/{service}/` (cho test)
   - `storage/sql_templates/oracle/{service}/` (cho production)
3. Tạo transformer mới (nếu format sao kê khác): `src/data/transformers.py`
4. **Không cần sửa** code core (rule_engine, matcher, database)

### 3.9. Chuyển đổi môi trường Dev/Prod

| Môi trường | config.ini | Mục đích |
|------------|------------|----------|
| **Development** | `driver = sqlite` | Test local, không cần Oracle |
| **Testing** | `driver = sqlite` | Unit test, CI/CD |
| **Production** | `driver = oracle` | Chạy thực tế với DB Oracle |

```bash
# Chuyển sang SQLite (dev/test)
# Sửa config/config.ini: driver = sqlite

# Chuyển sang Oracle (production)  
# Sửa config/config.ini: driver = oracle
```

---

## 4. Database Schema (Web Application)

> **Lưu ý:** Đây là schema cho ứng dụng web quản lý đối soát. Dữ liệu B4 được query trực tiếp từ database Oracle/SQLite, dữ liệu Partner được đọc từ file Excel - không cần import vào database trung gian. Kết quả đối soát chi tiết được xuất ra file A1/A2.

### 4.1. Bảng users (Quản lý người dùng)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,             -- Email đăng nhập
    password_hash VARCHAR(255) NOT NULL,            -- Mật khẩu đã hash
    full_name VARCHAR(255) NOT NULL,                -- Họ tên
    is_admin BOOLEAN DEFAULT FALSE,                 -- Quyền admin
    is_active BOOLEAN DEFAULT TRUE,                 -- Trạng thái hoạt động
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

### 4.2. Bảng user_permissions (Phân quyền người dùng)

```sql
CREATE TABLE user_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                       -- FK -> users.id
    partner_code VARCHAR(50) NOT NULL,              -- Mã đối tác (SACOMBANK, VCB, ...)
    service_code VARCHAR(50) NOT NULL,              -- Mã dịch vụ (TOPUP, PINCODE, ...)
    can_reconcile BOOLEAN DEFAULT TRUE,             -- Quyền thực hiện đối soát
    can_approve BOOLEAN DEFAULT FALSE,              -- Quyền phê duyệt
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, partner_code, service_code)
);
```

### 4.3. Bảng partner_service_config (Cấu hình đối soát)

```sql
CREATE TABLE partner_service_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Thông tin Partner/Service
    partner_code VARCHAR(50) NOT NULL,              -- SACOMBANK, VCB, BIDV, ...
    partner_name VARCHAR(255) NOT NULL,             -- Tên đối tác
    service_code VARCHAR(50) NOT NULL,              -- TOPUP, PINCODE, PAYMENT, ...
    service_name VARCHAR(255) NOT NULL,             -- Tên dịch vụ
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Thời hạn hiệu lực
    valid_from DATE NOT NULL,                       -- Ngày bắt đầu
    valid_to DATE,                                  -- Ngày kết thúc (NULL = vô hạn)
    
    -- Cấu hình đọc file Excel (JSON)
    file_b1_config TEXT NOT NULL,                   -- Config file B1 (sao kê Partner)
    file_b2_config TEXT,                            -- Config file B2 (hoàn tiền, nếu có)
    file_b3_config TEXT,                            -- Config file B3 (dữ liệu bổ sung)
    
    -- Cấu hình lấy dữ liệu B4 (JSON)
    data_b4_config TEXT NOT NULL,                   -- {db_connection, sql_file, sql_params, mock_file}
    
    -- Quy tắc matching (JSON) - Hỗ trợ UI simple + expression nâng cao
    matching_rules_b1b4 TEXT NOT NULL,              -- Rule khớp B1 với B4
    matching_rules_b1b2 TEXT,                       -- Rule khớp B1 với B2
    matching_rules_a1b3 TEXT,                       -- Rule khớp A1 với B3
    
    -- Quy tắc tổng hợp status (JSON)
    status_combine_rules TEXT NOT NULL,             -- Logic kết hợp status cuối cùng
    
    -- Cấu hình output (JSON)
    output_a1_config TEXT NOT NULL,                 -- Columns cho file A1
    output_a2_config TEXT,                          -- Columns cho file A2
    
    -- Cấu hình báo cáo
    report_template_path VARCHAR(500),              -- Đường dẫn template Excel
    report_cell_mapping TEXT,                       -- Mapping dữ liệu vào cell (JSON)
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (partner_code, service_code, valid_from)
);

CREATE INDEX idx_config_partner ON partner_service_config(partner_code);
CREATE INDEX idx_config_service ON partner_service_config(service_code);
```

### 4.4. Bảng reconciliation_logs (Lịch sử đối soát)

```sql
CREATE TABLE reconciliation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Batch identification
    batch_id VARCHAR(100) UNIQUE NOT NULL,          -- Format: PARTNER_SERVICE_YYYYMMDD_HHMMSS
    
    -- Partner và Service
    partner_code VARCHAR(50) NOT NULL,
    service_code VARCHAR(50) NOT NULL,
    
    -- Kỳ đối soát
    period_from DATE NOT NULL,
    period_to DATE NOT NULL,
    
    -- Trạng thái: UPLOADING, PROCESSING, COMPLETED, APPROVED, ERROR
    status VARCHAR(20) DEFAULT 'UPLOADING' NOT NULL,
    
    -- Tracking user
    created_by INTEGER NOT NULL,                    -- FK -> users.id
    approved_by INTEGER,                            -- FK -> users.id
    approved_at DATETIME,
    
    -- Logs chi tiết (JSON array)
    step_logs TEXT,                                 -- [{"step":"upload_b1","time":"...","status":"ok"}]
    
    -- Files đã upload (JSON)
    files_uploaded TEXT,                            -- {"b1":["file1.xlsx"],"b2":[],"b3":[]}
    
    -- Files kết quả
    file_result_a1 VARCHAR(500),                    -- Đường dẫn file A1
    file_result_a2 VARCHAR(500),                    -- Đường dẫn file A2
    file_report VARCHAR(500),                       -- Đường dẫn file báo cáo
    
    -- Thống kê kết quả (JSON)
    summary_stats TEXT,                             -- {"total_b1":1000,"matched":950,"not_found":30,"mismatch":20}
    
    -- Lỗi (nếu có)
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (approved_by) REFERENCES users(id)
);

CREATE INDEX idx_recon_batch ON reconciliation_logs(batch_id);
CREATE INDEX idx_recon_partner_service ON reconciliation_logs(partner_code, service_code);
CREATE INDEX idx_recon_period ON reconciliation_logs(period_from, period_to);
CREATE INDEX idx_recon_status ON reconciliation_logs(status);
```

### 4.5. Mô tả cấu trúc JSON trong các cột config

#### file_b1_config / file_b2_config / file_b3_config
```json
{
    "header_row": 1,
    "data_start_row": 2,
    "columns": {
        "txn_id": "A",
        "txn_date": "B",
        "amount": "C",
        "description": "D",
        "status": "E"
    }
}
```

#### data_b4_config
```json
{
    "db_connection": "vnptmoney_main",
    "sql_file": "shared/query_b4_topup.sql",
    "sql_params": {
        "service_id": "TOPUP",
        "partner_id": "SACOMBANK"
    },
    "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
}
```

#### matching_rules_b1b4 (Cấu trúc chính - hỗ trợ UI Simple + Expression nâng cao)

```json
{
    "match_type": "expression",
    "rules": [
        {
            "rule_name": "key_match",
            "type": "expression",
            "expression": "b1[''txn_id''].str.strip().str.upper() == b4[''transaction_ref''].str.strip().str.upper()",
            "_ui_config": {
                "mode": "simple",
                "leftColumns": ["txn_id"],
                "rightColumns": ["transaction_ref"],
                "separator": "",
                "transforms": ["strip", "upper"],
                "matchMode": "exact",
                "fuzzyThreshold": 85
            }
        },
        {
            "rule_name": "amount_match",
            "type": "expression",
            "expression": "abs(b1[''amount''].astype(float) - b4[''total_amount''].astype(float)) <= 0.01",
            "_ui_config": {
                "mode": "simple",
                "leftColumns": ["amount"],
                "rightColumns": ["total_amount"],
                "tolerance": 0.01,
                "toleranceType": "absolute"
            }
        }
    ],
    "status_logic": {
        "all_match": "MATCHED",
        "key_match_amount_mismatch": "MISMATCH",
        "no_key_match": "NOT_FOUND"
    }
}
```

#### Mô tả các trường trong matching_rules

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| `match_type` | Loại matching | `"expression"` |
| `rules[].rule_name` | Tên rule | `"key_match"`, `"amount_match"` |
| `rules[].type` | Loại rule | `"expression"` |
| `rules[].expression` | Biểu thức Pandas | `"b1['txn_id'] == b4['ref']"` |
| `rules[]._ui_config` | Config cho UI (không dùng khi chạy) | Object |
| `_ui_config.mode` | Chế độ UI | `"simple"` hoặc `"advanced"` |
| `_ui_config.leftColumns` | Cột bên B1 | `["txn_id"]` hoặc `["col1", "col2"]` |
| `_ui_config.rightColumns` | Cột bên B4 | `["transaction_ref"]` |
| `_ui_config.separator` | Ký tự nối khi ghép nhiều cột | `"_"`, `""` |
| `_ui_config.transforms` | Các transform áp dụng | `["strip", "upper", "lower"]` |
| `_ui_config.matchMode` | Chế độ so khớp | `"exact"` hoặc `"fuzzy"` |
| `_ui_config.fuzzyThreshold` | Ngưỡng fuzzy (%) | `85` |
| `_ui_config.tolerance` | Độ lệch cho phép (số tiền) | `0.01` |
| `_ui_config.toleranceType` | Loại tolerance | `"absolute"` hoặc `"percent"` |
| `status_logic` | Logic xác định status | Object |

#### status_combine_rules
```json
{
    "rules": [
        {"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"},
        {"b1b4": "MATCHED", "b1b2": "MATCHED", "final": "REFUNDED"},
        {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_IN_SYSTEM"},
        {"b1b4": "MISMATCH", "b1b2": "*", "final": "AMOUNT_ERROR"}
    ],
    "default": "UNKNOWN"
}
```

#### output_a1_config
```json
{
    "columns": [
        {"name": "txn_id", "source": "B1", "column": "txn_id"},
        {"name": "txn_date", "source": "B1", "column": "txn_date"},
        {"name": "phone_number", "source": "B1", "column": "phone_number"},
        {"name": "amount_b1", "source": "B1", "column": "amount"},
        {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
        {"name": "diff_amount", "source": "_CALC", "formula": "amount_b1 - amount_b4"},
        {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
        {"name": "final_status", "source": "_SYSTEM", "column": "final_status"}
    ]
}
```

---

## 5. Dữ liệu mẫu

### 5.1. Users và Permissions

```sql
-- Users
INSERT INTO users (email, password_hash, full_name, is_admin, is_active) VALUES
('admin@vnpt.vn', '<hashed_password>', 'Admin System', TRUE, TRUE),
('user1@vnpt.vn', '<hashed_password>', 'Nguyễn Văn A', FALSE, TRUE),
('user2@vnpt.vn', '<hashed_password>', 'Trần Thị B', FALSE, TRUE);

-- Permissions
INSERT INTO user_permissions (user_id, partner_code, service_code, can_reconcile, can_approve) VALUES
(2, 'SACOMBANK', 'TOPUP', TRUE, FALSE),
(2, 'SACOMBANK', 'PAYMENT', TRUE, FALSE),
(2, 'VCB', 'TOPUP', TRUE, TRUE),
(3, 'BIDV', 'TOPUP', TRUE, TRUE),
(3, 'SACOMBANK', 'TOPUP', TRUE, TRUE);
```

### 5.2. Partner Service Config - SACOMBANK TOPUP

```sql
INSERT INTO partner_service_config (
    partner_code, partner_name, service_code, service_name,
    is_active, valid_from, valid_to,
    file_b1_config, 
    data_b4_config, 
    matching_rules_b1b4,
    status_combine_rules, 
    output_a1_config
) VALUES (
    'SACOMBANK', 
    'Ngân hàng Sacombank', 
    'TOPUP', 
    'Nạp tiền điện thoại',
    TRUE, 
    '2025-01-01', 
    NULL,
    
    -- file_b1_config
    '{
        "header_row": 1,
        "data_start_row": 2,
        "columns": {
            "txn_id": "A",
            "txn_date": "B",
            "amount": "C",
            "phone_number": "D",
            "status": "E"
        }
    }',
    
    -- data_b4_config
    '{
        "db_connection": "vnptmoney_main",
        "sql_file": "shared/query_b4_topup.sql",
        "sql_params": {
            "service_id": "TOPUP",
            "partner_id": "SACOMBANK"
        },
        "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
    }',
    
    -- matching_rules_b1b4
    '{
        "match_type": "expression",
        "rules": [
            {
                "rule_name": "key_match",
                "type": "expression",
                "expression": "b1[''txn_id''].str.strip().str.upper() == b4[''transaction_ref''].str.strip().str.upper()",
                "_ui_config": {
                    "mode": "simple",
                    "leftColumns": ["txn_id"],
                    "rightColumns": ["transaction_ref"],
                    "separator": "",
                    "transforms": ["strip", "upper"],
                    "matchMode": "exact"
                }
            },
            {
                "rule_name": "amount_match",
                "type": "expression",
                "expression": "abs(b1[''amount''].astype(float) - b4[''total_amount''].astype(float)) <= 0.01",
                "_ui_config": {
                    "mode": "simple",
                    "leftColumns": ["amount"],
                    "rightColumns": ["total_amount"],
                    "tolerance": 0.01,
                    "toleranceType": "absolute"
                }
            }
        ],
        "status_logic": {
            "all_match": "MATCHED",
            "key_match_amount_mismatch": "MISMATCH",
            "no_key_match": "NOT_FOUND"
        }
    }',
    
    -- status_combine_rules
    '{
        "rules": [
            {"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"},
            {"b1b4": "MATCHED", "b1b2": "MATCHED", "final": "REFUNDED"},
            {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_IN_SYSTEM"},
            {"b1b4": "MISMATCH", "b1b2": "*", "final": "AMOUNT_ERROR"}
        ],
        "default": "UNKNOWN"
    }',
    
    -- output_a1_config
    '{
        "columns": [
            {"name": "txn_id", "source": "B1", "column": "txn_id"},
            {"name": "txn_date", "source": "B1", "column": "txn_date"},
            {"name": "phone_number", "source": "B1", "column": "phone_number"},
            {"name": "amount_b1", "source": "B1", "column": "amount"},
            {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
            {"name": "diff_amount", "source": "_CALC", "formula": "amount_b1 - amount_b4"},
            {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
            {"name": "final_status", "source": "_SYSTEM", "column": "final_status"}
        ]
    }'
);
```

### 5.3. Partner Service Config - VIETTEL PINCODE (với ghép nhiều cột)

```sql
INSERT INTO partner_service_config (
    partner_code, partner_name, service_code, service_name,
    is_active, valid_from, valid_to,
    file_b1_config, 
    data_b4_config, 
    matching_rules_b1b4,
    status_combine_rules, 
    output_a1_config
) VALUES (
    'VIETTEL', 
    'Tập đoàn Viettel', 
    'PINCODE', 
    'Mã thẻ cào',
    TRUE, 
    '2025-01-01', 
    NULL,
    
    -- file_b1_config
    '{
        "header_row": 1,
        "data_start_row": 2,
        "columns": {
            "batch_id": "A",
            "serial_prefix": "B",
            "txn_date": "C",
            "amount": "D",
            "quantity": "E",
            "status": "F"
        }
    }',
    
    -- data_b4_config
    '{
        "db_connection": "vnptmoney_main",
        "sql_file": "shared/query_b4_pincode.sql",
        "sql_params": {
            "service_id": "PINCODE",
            "partner_id": "VIETTEL"
        },
        "mock_file": "VIETTEL_PINCODE_b4_mock.csv"
    }',
    
    -- matching_rules_b1b4 (ghép 2 cột làm key)
    '{
        "match_type": "expression",
        "rules": [
            {
                "rule_name": "key_match",
                "type": "expression",
                "expression": "(b1[''batch_id''].astype(str) + ''_'' + b1[''serial_prefix''].astype(str)).str.strip().str.upper() == b4[''transaction_ref''].str.strip().str.upper()",
                "_ui_config": {
                    "mode": "simple",
                    "leftColumns": ["batch_id", "serial_prefix"],
                    "rightColumns": ["transaction_ref"],
                    "separator": "_",
                    "transforms": ["strip", "upper"],
                    "matchMode": "exact"
                }
            },
            {
                "rule_name": "amount_match",
                "type": "expression",
                "expression": "abs(b1[''amount''].astype(float) - b4[''total_amount''].astype(float)) <= 0",
                "_ui_config": {
                    "mode": "simple",
                    "leftColumns": ["amount"],
                    "rightColumns": ["total_amount"],
                    "tolerance": 0,
                    "toleranceType": "absolute"
                }
            },
            {
                "rule_name": "quantity_match",
                "type": "expression",
                "expression": "b1[''quantity''].astype(int) == b4[''quantity''].astype(int)",
                "_ui_config": {
                    "mode": "simple",
                    "leftColumns": ["quantity"],
                    "rightColumns": ["quantity"],
                    "tolerance": 0,
                    "toleranceType": "absolute"
                }
            }
        ],
        "status_logic": {
            "all_match": "MATCHED",
            "key_match_amount_mismatch": "AMOUNT_MISMATCH",
            "key_match_qty_mismatch": "QTY_MISMATCH",
            "no_key_match": "NOT_FOUND"
        }
    }',
    
    -- status_combine_rules
    '{
        "rules": [
            {"b1b4": "MATCHED", "final": "OK"},
            {"b1b4": "AMOUNT_MISMATCH", "final": "AMOUNT_ERROR"},
            {"b1b4": "QTY_MISMATCH", "final": "QTY_ERROR"},
            {"b1b4": "NOT_FOUND", "final": "NOT_IN_SYSTEM"}
        ],
        "default": "UNKNOWN"
    }',
    
    -- output_a1_config
    '{
        "columns": [
            {"name": "batch_id", "source": "B1", "column": "batch_id"},
            {"name": "serial_prefix", "source": "B1", "column": "serial_prefix"},
            {"name": "txn_date", "source": "B1", "column": "txn_date"},
            {"name": "amount_b1", "source": "B1", "column": "amount"},
            {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
            {"name": "qty_b1", "source": "B1", "column": "quantity"},
            {"name": "qty_b4", "source": "B4", "column": "quantity", "default": 0},
            {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
            {"name": "final_status", "source": "_SYSTEM", "column": "final_status"}
        ]
    }'
);
```

### 5.4. UI Rule Config - Mô tả giao diện

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CẤU HÌNH RULE SO KHỚP B1 ↔ B4                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ▼ Rule 1: So khớp Key                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                     │ │
│  │  ┌─── BÊN TRÁI (B1) ───────────────────────────────────────────┐   │ │
│  │  │                                                              │   │ │
│  │  │  Công thức ghép:                                             │   │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐│   │ │
│  │  │  │ [Cột: txn_ref    ▼] [+ Thêm]                             ││   │ │
│  │  │  │ [Text: '-'        ] [+ Thêm]                             ││   │ │
│  │  │  │ [Cột: txn_date   ▼] [+ Thêm]                             ││   │ │
│  │  │  └──────────────────────────────────────────────────────────┘│   │ │
│  │  │  Preview: B1['txn_ref'] || '-' || B1['txn_date']             │   │ │
│  │  │                                                              │   │ │
│  │  │  Transforms:  [✓] Strip  [✓] Upper  [ ] Lower  [ ] Trim số 0 │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                     │ │
│  │  Kiểu so sánh:  (●) Bằng (=)  ( ) Chứa (LIKE)  ( ) Gần đúng        │ │
│  │                                                                     │ │
│  │  ┌─── BÊN PHẢI (B4) ───────────────────────────────────────────┐   │ │
│  │  │                                                              │   │ │
│  │  │  Công thức ghép:                                             │   │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐│   │ │
│  │  │  │ [Text: 'VNP'      ] [+ Thêm]                             ││   │ │
│  │  │  │ [Cột: partner_ref▼] [+ Thêm]                             ││   │ │
│  │  │  └──────────────────────────────────────────────────────────┘│   │ │
│  │  │  Preview: 'VNP' || B4['partner_ref']                         │   │ │
│  │  │                                                              │   │ │
│  │  │  Transforms:  [✓] Strip  [✓] Upper  [ ] Lower  [ ] Trim số 0 │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ▼ Rule 2: So khớp Số tiền                                               │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Cột B1: [amount     ▼]    Cột B4: [total_amount ▼]                │ │
│  │  Cho phép lệch: [100] VNĐ                                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [+ Thêm Rule]                                                           │
│                                                                          │
│  ──────────────────────────────────────────────────────────────────────  │
│  [ ] Chế độ nâng cao (xem/sửa Expression)                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.5. Cấu trúc JSON matching_rules (cập nhật theo UI mới)

```json
{
    "match_type": "expression",
    "rules": [
        {
            "rule_name": "key_match",
            "type": "expression",
            "expression": "(b1[''txn_ref''].astype(str) + ''-'' + b1[''txn_date''].astype(str)).str.strip().str.upper() == (''VNP'' + b4[''partner_ref''].astype(str)).str.strip().str.upper()",
            
            "_ui_config": {
                "mode": "simple",
                "left": {
                    "parts": [
                        {"type": "column", "value": "txn_ref"},
                        {"type": "text", "value": "-"},
                        {"type": "column", "value": "txn_date"}
                    ],
                    "transforms": ["strip", "upper"]
                },
                "compareType": "exact",
                "right": {
                    "parts": [
                        {"type": "text", "value": "VNP"},
                        {"type": "column", "value": "partner_ref"}
                    ],
                    "transforms": ["strip", "upper"]
                }
            }
        },
        {
            "rule_name": "amount_match",
            "type": "expression",
            "expression": "abs(b1[''amount''].astype(float) - b4[''total_amount''].astype(float)) <= 100",
            
            "_ui_config": {
                "mode": "simple",
                "left": {
                    "parts": [{"type": "column", "value": "amount"}],
                    "transforms": []
                },
                "compareType": "tolerance",
                "tolerance": 100,
                "toleranceType": "absolute",
                "right": {
                    "parts": [{"type": "column", "value": "total_amount"}],
                    "transforms": []
                }
            }
        }
    ],
    "status_logic": {
        "all_match": "MATCHED",
        "key_match_amount_mismatch": "MISMATCH",
        "no_key_match": "NOT_FOUND"
    }
}
```

### 5.6. Mô tả cấu trúc _ui_config mới

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| `mode` | Chế độ UI | `"simple"` hoặc `"advanced"` |
| `left` | Config bên trái (B1) | Object |
| `left.parts[]` | Danh sách các phần ghép | Array |
| `left.parts[].type` | Loại phần tử | `"column"` hoặc `"text"` |
| `left.parts[].value` | Giá trị (tên cột hoặc text) | `"txn_ref"`, `"-"` |
| `left.transforms` | Transform áp dụng cho B1 | `["strip", "upper"]` |
| `compareType` | Kiểu so sánh | `"exact"`, `"like"`, `"fuzzy"`, `"tolerance"` |
| `tolerance` | Độ lệch cho phép (nếu compareType=tolerance) | `100` |
| `toleranceType` | Loại tolerance | `"absolute"` hoặc `"percent"` |
| `right` | Config bên phải (B4) | Object (tương tự left) |
| `right.parts[]` | Danh sách các phần ghép | Array |
| `right.transforms` | Transform áp dụng cho B4 | `["strip", "upper"]` |

### 5.7. Frontend - Hàm generate Expression từ UI config (cập nhật)

```javascript
function generateExpression(ruleConfig) {
    const { left, right, compareType, tolerance, toleranceType } = ruleConfig._ui_config;
    
    // Build expression cho mỗi bên
    let leftExpr = buildSideExpr('b1', left);
    let rightExpr = buildSideExpr('b4', right);
    
    // Tạo expression theo compareType
    switch (compareType) {
        case 'exact':
            return `${leftExpr} == ${rightExpr}`;
        case 'like':
            return `${leftExpr}.str.contains(${rightExpr})`;
        case 'fuzzy':
            return `fuzzy_match(${leftExpr}, ${rightExpr}, threshold=0.85)`;
        case 'tolerance':
            if (toleranceType === 'percent') {
                return `abs(${leftExpr} - ${rightExpr}) / ${rightExpr} <= ${tolerance/100}`;
            }
            return `abs(${leftExpr} - ${rightExpr}) <= ${tolerance}`;
        default:
            return `${leftExpr} == ${rightExpr}`;
    }
}

function buildSideExpr(prefix, sideConfig) {
    const { parts, transforms } = sideConfig;
    
    // Build expression từ parts
    let expr;
    if (parts.length === 1 && parts[0].type === 'column') {
        expr = `${prefix}['${parts[0].value}']`;
    } else {
        // Ghép nhiều phần (column + text)
        const partExprs = parts.map(p => {
            if (p.type === 'column') {
                return `${prefix}['${p.value}'].astype(str)`;
            } else {
                return `'${p.value}'`;
            }
        });
        expr = `(${partExprs.join(' + ')})`;
    }
    
    // Apply transforms
    if (transforms.includes('strip')) expr += '.str.strip()';
    if (transforms.includes('upper')) expr += '.str.upper()';
    if (transforms.includes('lower')) expr += '.str.lower()';
    if (transforms.includes('trim_zero')) expr += '.str.lstrip("0")';
    
    return expr;
}
```

### 5.8. Ví dụ dữ liệu mẫu với cấu trúc mới

```sql
-- SACOMBANK TOPUP với key ghép phức tạp
INSERT INTO partner_service_config (
    partner_code, partner_name, service_code, service_name,
    is_active, valid_from, valid_to,
    file_b1_config, 
    data_b4_config, 
    matching_rules_b1b4,
    status_combine_rules, 
    output_a1_config
) VALUES (
    'SACOMBANK', 
    'Ngân hàng Sacombank', 
    'TOPUP', 
    'Nạp tiền điện thoại',
    TRUE, 
    '2025-01-01', 
    NULL,
    
    -- file_b1_config
    '{
        "header_row": 1,
        "data_start_row": 2,
        "columns": {
            "txn_ref": "A",
            "txn_date": "B",
            "amount": "C",
            "phone_number": "D",
            "status": "E"
        }
    }',
    
    -- data_b4_config
    '{
        "db_connection": "vnptmoney_main",
        "sql_file": "shared/query_b4_topup.sql",
        "sql_params": {
            "service_id": "TOPUP",
            "partner_id": "SACOMBANK"
        },
        "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
    }',
    
    -- matching_rules_b1b4 (cấu trúc mới với left/right riêng biệt)
    '{
        "match_type": "expression",
        "rules": [
            {
                "rule_name": "key_match",
                "type": "expression",
                "expression": "(b1[''txn_ref''].astype(str) + ''-'' + b1[''txn_date''].astype(str)).str.strip().str.upper() == (''VNP'' + b4[''partner_ref''].astype(str)).str.strip().str.upper()",
                "_ui_config": {
                    "mode": "simple",
                    "left": {
                        "parts": [
                            {"type": "column", "value": "txn_ref"},
                            {"type": "text", "value": "-"},
                            {"type": "column", "value": "txn_date"}
                        ],
                        "transforms": ["strip", "upper"]
                    },
                    "compareType": "exact",
                    "right": {
                        "parts": [
                            {"type": "text", "value": "VNP"},
                            {"type": "column", "value": "partner_ref"}
                        ],
                        "transforms": ["strip", "upper"]
                    }
                }
            },
            {
                "rule_name": "amount_match",
                "type": "expression",
                "expression": "abs(b1[''amount''].astype(float) - b4[''total_amount''].astype(float)) <= 100",
                "_ui_config": {
                    "mode": "simple",
                    "left": {
                        "parts": [{"type": "column", "value": "amount"}],
                        "transforms": []
                    },
                    "compareType": "tolerance",
                    "tolerance": 100,
                    "toleranceType": "absolute",
                    "right": {
                        "parts": [{"type": "column", "value": "total_amount"}],
                        "transforms": []
                    }
                }
            }
        ],
        "status_logic": {
            "all_match": "MATCHED",
            "key_match_amount_mismatch": "MISMATCH",
            "no_key_match": "NOT_FOUND"
        }
    }',
    
    -- status_combine_rules
    '{
        "rules": [
            {"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"},
            {"b1b4": "MATCHED", "b1b2": "MATCHED", "final": "REFUNDED"},
            {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_IN_SYSTEM"},
            {"b1b4": "MISMATCH", "b1b2": "*", "final": "AMOUNT_ERROR"}
        ],
        "default": "UNKNOWN"
    }',
    
    -- output_a1_config
    '{
        "columns": [
            {"name": "txn_ref", "source": "B1", "column": "txn_ref"},
            {"name": "txn_date", "source": "B1", "column": "txn_date"},
            {"name": "phone_number", "source": "B1", "column": "phone_number"},
            {"name": "amount_b1", "source": "B1", "column": "amount"},
            {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
            {"name": "diff_amount", "source": "_CALC", "formula": "amount_b1 - amount_b4"},
            {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
            {"name": "final_status", "source": "_SYSTEM", "column": "final_status"}
        ]
    }'
);
```

### 5.9. Test Cases

| Case | B1 Input | B4 Input | Kết quả |
|------|----------|----------|---------|
| Key ghép + text | txn_ref="ABC", txn_date="20250101" → "ABC-20250101" | partner_ref="ABC-20250101" → "VNPABC-20250101" | NOT_FOUND (khác prefix) |
| Key ghép match | txn_ref="VNP123", txn_date="" → "VNP123-" | partner_ref="123-" → "VNP123-" | MATCHED |
| Amount trong tolerance | amount=100000 | total_amount=100050 | MATCHED (lệch 50 <= 100) |
| Amount ngoài tolerance | amount=100000 | total_amount=100200 | MISMATCH (lệch 200 > 100) |
| Transform upper | txn_ref="abc123" (lower) | partner_ref="ABC123" (upper) | MATCHED (sau upper) |

---

## 6. Quy tắc đối soát (Reconciliation Rules)

### 6.1. UI Cấu hình Rule

Hệ thống cho phép cấu hình rule đối soát thông qua giao diện hoặc file YAML với các thành phần:

| Thành phần | Mô tả | Ví dụ |
|------------|-------|-------|
| `rule_id` | Mã định danh rule | `TOPUP_VIETTEL_01` |
| `service_id` | Loại dịch vụ | `TOPUP`, `PINCODE` |
| `partner_id` | Mã đối tác | `VIETTEL`, `MOBIFONE` |
| `match_keys` | Các trường dùng để khớp | `['partner_ref']`, `['b4_ref']` |
| `compare_fields` | Các trường so sánh giá trị | `['total_amount']`, `['quantity']` |
| `tolerance` | Độ chênh lệch cho phép | `0`, `0.01` (1%) |
| `priority` | Thứ tự ưu tiên áp dụng rule | `1`, `2`, `3` |
| `enabled` | Bật/tắt rule | `true`, `false` |

### 6.2. Ví dụ Config YAML

```yaml
# File: config/rules/topup_viettel.yaml
service_id: TOPUP
partner_id: VIETTEL

rules:
  - rule_id: TOPUP_VTT_01
    name: "Match theo Partner Ref"
    description: "Khớp giao dịch B4 và Partner theo mã partner_ref"
    priority: 1
    enabled: true
    match_keys:
      - b4_field: partner_ref
        partner_field: partner_ref
    compare_fields:
      - field: total_amount
        tolerance: 0
        
  - rule_id: TOPUP_VTT_02
    name: "Match theo B4 Ref"
    description: "Khớp giao dịch theo mã B4 khi partner có lưu b4_ref"
    priority: 2
    enabled: true
    match_keys:
      - b4_field: transaction_ref
        partner_field: b4_ref
    compare_fields:
      - field: total_amount
        tolerance: 0
```

```yaml
# File: config/rules/pincode_viettel.yaml
service_id: PINCODE
partner_id: VIETTEL

rules:
  - rule_id: PIN_VTT_01
    name: "Match theo Partner Ref"
    priority: 1
    enabled: true
    match_keys:
      - b4_field: partner_ref
        partner_field: partner_ref
    compare_fields:
      - field: total_amount
        tolerance: 0
      - field: quantity
        tolerance: 0
        
  - rule_id: PIN_VTT_02
    name: "Match theo B4 Ref"
    priority: 2
    enabled: true
    match_keys:
      - b4_field: transaction_ref
        partner_field: b4_ref
    compare_fields:
      - field: total_amount
        tolerance: 0
      - field: quantity
        tolerance: 0
```

### 6.3. Kết quả đối soát (Match Status)

| Status | Mô tả |
|--------|-------|
| `MATCHED` | Khớp hoàn toàn (ref + amount + quantity) |
| `AMOUNT_MISMATCH` | Khớp ref nhưng lệch số tiền |
| `QTY_MISMATCH` | Khớp ref nhưng lệch số lượng (PINCODE) |
| `B4_ONLY` | Chỉ có trong dữ liệu B4 |
| `PARTNER_ONLY` | Chỉ có trong dữ liệu Partner |

### 6.4. Luồng xử lý Rule

```
┌─────────────────────────────────────────────────────────────┐
│                    RULE ENGINE                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Load rules từ YAML (theo service_id + partner_id)       │
│                         │                                    │
│                         ▼                                    │
│  2. Sắp xếp rules theo priority (1 -> n)                    │
│                         │                                    │
│                         ▼                                    │
│  3. Với mỗi rule (enabled = true):                          │
│     ┌─────────────────────────────────────────────────┐     │
│     │ a. Lấy match_keys -> JOIN B4 với Partner        │     │
│     │ b. Với các record khớp key:                     │     │
│     │    - So sánh compare_fields                     │     │
│     │    - Nếu khớp -> MATCHED                        │     │
│     │    - Nếu lệch amount -> AMOUNT_MISMATCH         │     │
│     │    - Nếu lệch qty -> QTY_MISMATCH               │     │
│     │ c. Đánh dấu các record đã xử lý                 │     │
│     └─────────────────────────────────────────────────┘     │
│                         │                                    │
│                         ▼                                    │
│  4. Các record B4 chưa khớp -> B4_ONLY                      │
│                         │                                    │
│                         ▼                                    │
│  5. Các record Partner chưa khớp -> PARTNER_ONLY            │
│                         │                                    │
│                         ▼                                    │
│  6. Xuất kết quả -> reconciliation_results                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Kết quả mong đợi với dữ liệu mẫu

### 7.1. TOPUP (2024-01-15)

| B4 Ref | Partner Ref | B4 Amount | Partner Amount | Status |
|--------|-------------|-----------|----------------|--------|
| B4_TOP_001 | VTT_001 | 50,000 | 50,000 | MATCHED |
| B4_TOP_002 | VTT_002 | 100,000 | 100,000 | MATCHED |
| B4_TOP_003 | VTT_003 | 200,000 | 180,000 | AMOUNT_MISMATCH (-20,000) |
| B4_TOP_004 | - | 50,000 | - | B4_ONLY |
| - | VTT_006 | - | 150,000 | PARTNER_ONLY |

### 7.2. PINCODE (2024-01-15)

| B4 Ref | Partner Ref | B4 Qty | Partner Qty | Status |
|--------|-------------|--------|-------------|--------|
| B4_PIN_001 | VTT_P001 | 10 | 10 | MATCHED |
| B4_PIN_002 | VTT_P002 | 20 | 18 | QTY_MISMATCH (-2) |
| B4_PIN_003 | VTT_P003 | 5 | 5 | MATCHED |
| B4_PIN_004 | - | 2 | - | B4_ONLY |
| - | VTT_P005 | - | 4 | PARTNER_ONLY |

---

## 8. Tiến độ phát triển

### 8.1. Đã hoàn thành ✅

#### Backend (FastAPI + SQLAlchemy)
- [x] Khởi tạo project structure với FastAPI
- [x] Cấu hình database SQLite cho development
- [x] Tạo models: User, PartnerServiceConfig, ReconciliationLog
- [x] Tạo schemas cho tất cả các entities
- [x] Tạo endpoints CRUD cho configs, users, partners
- [x] Authentication với JWT tokens
- [x] Mock data endpoints để test

#### Frontend (React + Vite + TailwindCSS)
- [x] Khởi tạo project với Vite + React 18
- [x] Cấu hình TailwindCSS
- [x] Tạo layout: AuthLayout, MainLayout
- [x] Trang đăng nhập (LoginPage)
- [x] Trang Dashboard
- [x] Trang quản lý Configs (ConfigsPage)
- [x] Trang quản lý Users (UsersPage)
- [x] Trang Mock Data (MockDataPage)
- [x] Trang Reconciliation (ReconciliationPage)
- [x] Trang Approvals (ApprovalsPage)
- [x] Trang Batch List/Detail

#### Config Form Modal (ConfigFormModal.jsx) - Cấu hình đối soát
- [x] Tab 1: Thông tin cơ bản (Partner, Service, Valid dates)
- [x] Tab 2: Cấu hình File B1 (FileConfigEditor)
- [x] Tab 3: Cấu hình File B2 (FileConfigEditor)
- [x] Tab 4: Cấu hình File B3 (FileConfigEditor)
- [x] Tab 5: Cấu hình Data B4 (DataB4ConfigEditor)
- [x] Tab 6: Matching Rules (MatchingRulesEditor)
  - [x] Matching B1↔B4
  - [x] Matching B1↔B2
  - [x] Matching B3↔A1 (đổi từ A1↔B3)
- [x] Tab 7: Report Template (ReportTemplateEditor)
  - [x] Multi-sheet support (Tổng hợp, Chi tiết, ...)
  - [x] Cell mapping cho từng sheet
- [x] Tab 8: Output Config (OutputColumnsEditor)
  - [x] A1 config
  - [x] A2 config (cho phép chọn source từ A1)

#### UI/UX Improvements (Session 2025-02-05)
- [x] **Expression Preview**: Hiển thị expression đầy đủ bao gồm transforms và advanced config (substring, regex, replace)
- [x] **Amount tolerance=0**: Sử dụng `==` thay vì `<= 0` khi tolerance bằng 0
- [x] **Đổi hướng so khớp**: A1↔B3 → B3↔A1 (B3 là chuẩn)
- [x] **A2 Output Config**: Cho phép chọn A1 làm source
- [x] **Output Columns Editor UX**:
  - Thứ tự: Source → Column → Alias
  - Auto-fill alias khi chọn column
- [x] **Save & Continue button**: Thêm 2 nút "Lưu & Tiếp tục" và "Lưu & Đóng"
- [x] **Fix state sync**: Sửa lỗi JSON preview không đồng bộ với UI
  - FileConfigEditor: Bỏ local useState, dùng props trực tiếp
  - ReportTemplateEditor: Bỏ local useState `sheets`, dùng `reportCellMapping.sheets` trực tiếp
- [x] **Backend field sync**: Đổi `matching_rules_a1b3` → `matching_rules_b3a1` trong:
  - Models (config.py)
  - Schemas (config.py)
  - Endpoints (configs.py)
  - Database column (ALTER TABLE)

### 8.2. Đang tiến hành 🔄

- [ ] **Test matching engine**: Kiểm tra cấu hình có hoạt động đúng với reconciliation engine
- [ ] Tích hợp upload file sao kê
- [ ] Chạy đối soát và xuất báo cáo

### 8.3. Cần làm tiếp 📋

#### Backend
- [ ] Cập nhật reconciliation_engine.py để đọc cấu hình từ database
- [ ] Implement file_processor.py xử lý file upload
- [ ] Implement report_generator.py xuất báo cáo Excel
- [ ] Kết nối Oracle database cho production

#### Frontend
- [ ] Upload file sao kê (drag & drop)
- [ ] Hiển thị tiến trình đối soát
- [ ] Preview kết quả đối soát
- [ ] Download báo cáo

#### Testing & Documentation
- [ ] Unit tests cho matching engine
- [ ] Integration tests cho API endpoints
- [ ] User documentation

---

## 9. Database Schema Changes Log

| Ngày | Thay đổi | Lý do |
|------|----------|-------|
| 2025-02-05 | Rename column `matching_rules_a1b3` → `matching_rules_b3a1` | Đổi hướng so khớp: B3 là chuẩn, A1 là dữ liệu cần đối chiếu |

---

## 10. Known Issues & Workarounds

| Issue | Status | Workaround |
|-------|--------|------------|
| White screen khi select columns trong Matching Rules | ✅ Fixed | Rewrite MatchingRulesEditor với safe getters |
| JSON preview không sync với UI | ✅ Fixed | Bỏ local useState trong child components |
| Backend không lưu matching_rules_b3a1 | ✅ Fixed | Sync field name giữa FE và BE |

---

## 11. Implementation Notes (Thông tin thực tế hệ thống - Feb 2026)

### 11.1. Cấu trúc thư mục Storage thực tế

```
reconciliation-system/
 storage/                              # Thư mục lưu trữ chính
    uploads/{batch_id}/               # File upload gốc (B1, B2, B3)
       B1_1_{original_filename}
       B1_2_{original_filename}
       B2_1_{original_filename}
       B3_1_{original_filename}
    exports/{batch_id}/               # Kết quả đối soát (A1, A2)
       A1_{batch_id}.csv
       A2_{batch_id}.csv
    mock_data/                        # Data B4 giả lập (khi mock_mode=true)
       SACOMBANK_TOPUP_b4_mock.csv
       VCB_TOPUP_b4_mock.csv
    templates/                        # Template báo cáo Excel
       shared/
           report_topup.xlsx
    sql_templates/                    # SQL query templates
       shared/
           query_b4_topup.sql
    custom_matching/                  # Custom Python matching logic (nếu có)
    processed/                        # [Chưa sử dụng] Cache CSV từ Excel
 backend/
    data/app.db                       # SQLite database
    config.ini                        # Cấu hình DB connections
 frontend/
```

> **Lưu ý**: Thư mục `processed/` được thiết kế để cache file CSV từ Excel cho việc load lại nhanh hơn, nhưng hiện tại **chưa được sử dụng**. Có thể bỏ hoặc giữ cho tương lai.

### 11.2. Batch ID Format

Batch ID được tạo tự động khi tạo batch mới:

```python
batch_id = f"{partner_code}_{service_code}_{date_from.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
```

**Ví dụ**: `SACOMBANK_TOPUP_20260210_180221`
- `SACOMBANK` = partner_code
- `TOPUP` = service_code
- `20260210` = ngày đối soát (period_from)
- `180221` = thời gian tạo (18:02:21)

> **Lưu ý**: Đây là chuỗi text, không phải số tự tăng hay UUID. Cấu trúc này giúp dễ debug và nhận biết batch.

### 11.3. Flow xử lý đối soát

```
User tạo batch  Upload files (B1, B2, B3)
        
Lưu vào storage/uploads/{batch_id}/
        
Load config từ partner_service_config
        
Load data B4:
  - Nếu mock_mode=true  đọc từ mock_data/
  - Nếu mock_mode=false  query Oracle theo data_b4_config
        
Parse files B1, B2, B3 vào DataFrame (memory)
        
Matching Engine thực hiện:
  1. B1  B4  status_b1b4
  2. B1  B2  status_b1b2 (nếu có B2)
  3. B3  A1  status_b3a1 (nếu có B3)
  4. Combine  final_status
        
Export kết quả  storage/exports/{batch_id}/A1.csv, A2.csv
        
Cập nhật reconciliation_logs với đường dẫn file và stats
```

### 11.4. Các thay đổi so với plan ban đầu

| Mục | Plan ban đầu | Thực tế | Lý do |
|-----|--------------|---------|-------|
| Storage structure | `{partner}/{period}/{batch_id}/` | `{batch_id}/` | Đơn giản hóa, batch_id đã chứa đủ thông tin |
| batch_id format | Số tự tăng hoặc UUID | `PARTNER_SERVICE_DATE_TIME` | Dễ debug, dễ nhận biết |
| processed folder | Cache CSV từ Excel | Không sử dụng | Chạy 1 lần, không cần cache |
| config_id tracking | Không đề cập | Đã thêm vào reconciliation_logs | Lưu lại config được áp dụng cho batch |

### 11.5. Database Changes (Feb 2026)

| Bảng | Thay đổi | Mô tả |
|------|----------|-------|
| reconciliation_logs | Thêm `config_id INTEGER` | Lưu ID config được áp dụng khi tạo batch |
| partner_service_config | Rename `matching_rules_a1b3`  `matching_rules_b3a1` | Đổi hướng so khớp B3A1 |

### 11.6. Key Files & Components

| File | Chức năng |
|------|-----------|
| `backend/app/services/reconciliation_engine.py` | Engine matching chính (B1B4, B1B2, B3A1) |
| `backend/app/services/workflow_service.py` | Quản lý batch workflow (create, update status, logs) |
| `backend/app/services/file_processor.py` | Parse Excel/CSV với config (header_row, columns mapping) |
| `backend/app/services/data_loader.py` | Load B4 từ Oracle/mock |
| `backend/app/services/report_generator.py` | Fill template Excel với kết quả |
| `frontend/src/pages/BatchDetailPage.jsx` | Chi tiết batch, preview A1/A2, filters |
| `frontend/src/components/ConfigFormModal.jsx` | Form cấu hình partner/service |

### 11.7. API Endpoints chính

| Method | Endpoint | Chức năng |
|--------|----------|-----------|
| POST | `/api/v1/reconciliation/start` | Tạo batch mới + upload files + chạy đối soát |
| GET | `/api/v1/reconciliation/list` | Danh sách batches |
| GET | `/api/v1/reconciliation/{batch_id}` | Chi tiết batch |
| DELETE | `/api/v1/reconciliation/{batch_id}` | Xóa batch và files |
| GET | `/api/v1/reports/preview/{batch_id}/{file_type}` | Preview A1/A2 với filters |
| GET | `/api/v1/reports/download/{batch_id}/{file_type}` | Download A1/A2 |
| POST | `/api/v1/reports/generate/{batch_id}` | Tạo báo cáo từ template |
| GET | `/api/v1/reports/stats/{batch_id}` | Thống kê batch |

### 11.8. Hướng dẫn chạy development

```bash
# Backend
cd reconciliation-system/backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd reconciliation-system/frontend
npm install
npm run dev
```

Truy cập:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Default login: `admin@example.com` / `admin123`

---

## 12. TODO - Các việc cần làm tiếp

### 12.1. Backend
- [ ] Test với dữ liệu thực (file Excel lớn 1M+ rows)
- [ ] Kết nối Oracle database thật
- [ ] Xử lý timeout cho batch lớn (background task)
- [ ] Cleanup old batches (cron job)

### 12.2. Frontend
- [ ] Hiển thị progress bar khi đang xử lý
- [ ] Retry mechanism khi upload fail
- [ ] Export filtered data (chỉ lỗi, chỉ khớp, ...)

### 12.3. DevOps
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Logging & monitoring
