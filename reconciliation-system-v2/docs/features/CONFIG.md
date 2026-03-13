# Tính năng: Cấu hình đối soát

> Trang quản trị tạo/sửa cấu hình đối soát cho từng cặp partner + service.
> Một page ConfigEditV2Page chứa nhiều tab/section: Thông tin chung, Data Sources, Workflow Steps, Output Configs.

## Pages & Routes

| Route | Page | Mô tả |
|---|---|---|
| `/admin/configs-v2` | `ConfigsV2Page` | Danh sách cấu hình (bảng, pagination) |
| `/admin/configs-v2/:id` | `ConfigDetailV2Page` | Xem chi tiết config (read-only) |
| `/admin/configs-v2/new` | `ConfigEditV2Page` | Tạo config mới |
| `/admin/configs-v2/:id/edit` | `ConfigEditV2Page` | Sửa config |

## Cấu trúc ConfigEditV2Page (1 page, nhiều tab)

```
ConfigEditV2Page
├─ Tab "Thông tin chung"
│   └─ partner_code, partner_name, service_code, service_name
│      valid_from, valid_to, is_active, report_template_path
│
├─ Tab "Nguồn dữ liệu" (Data Sources)
│   └─ CRUD N nguồn: source_name, source_type, display_name, is_required
│      file_config (header_row, columns), db_config (connection, sql_file), etc.
│
├─ Tab "Workflow Steps"
│   └─ CRUD N bước matching tuần tự:
│      ├─ Chọn nguồn: left_source + right_source (dropdown từ data sources + outputs trước đó)
│      ├─ Quy tắc: matching_rules (key_match expression + amount_match tolerance)
│      ├─ Join type: left/inner/right/outer
│      └─ Output: output_name, output_columns, is_final_output (trung gian hay chi tiết)
│
└─ Tab "Output Configs" (Report)
    └─ CRUD cấu hình tạo Report Excel:
       output_name, display_name, columns_config, filter_status, use_for_report
```

## API Endpoints sử dụng

```
Configs:
  GET    /configs/                    → Danh sách configs (pagination)
  GET    /configs/{id}                → Chi tiết 1 config
  POST   /configs/                    → Tạo config
  PATCH  /configs/{id}                → Sửa config
  DELETE /configs/{id}                → Xóa config

Data Sources (per config):
  GET    /data-sources/by-config/{id} → Danh sách sources của config
  POST   /data-sources/               → Tạo source
  PATCH  /data-sources/{id}           → Sửa source
  DELETE /data-sources/{id}           → Xóa source

Workflow Steps (per config):
  GET    /workflows/by-config/{id}    → Danh sách steps của config
  POST   /workflows/                  → Tạo step
  PATCH  /workflows/{id}              → Sửa step
  DELETE /workflows/{id}              → Xóa step

Output Configs (per config):
  GET    /outputs/by-config/{id}      → Danh sách outputs của config
  POST   /outputs/                    → Tạo output config
  PATCH  /outputs/{id}                → Sửa output config
  DELETE /outputs/{id}                → Xóa output config
```

## Frontend files

| File | Vai trò |
|---|---|
| `src/pages/admin/ConfigsV2Page.jsx` | Bảng danh sách configs + delete |
| `src/pages/admin/ConfigDetailV2Page.jsx` | Read-only view config + relations |
| `src/pages/admin/ConfigEditV2Page.jsx` | Form CRUD: 4 tabs (basic, sources, workflow, outputs) |
| `src/components/RuleBuilder/` | Component builder cho matching rules (expression editor) |
| `src/services/api.js` → `configsApi` | CRUD configs |
| `src/services/api.js` → `dataSourcesApi` | CRUD data sources |
| `src/services/api.js` → `workflowsApi` | CRUD workflow steps |
| `src/services/api.js` → `outputsApi` | CRUD output configs |

## Backend files

| File | Vai trò |
|---|---|
| `app/api/v2/endpoints/configs.py` | CRUD PartnerServiceConfig |
| `app/api/v2/endpoints/data_sources.py` | CRUD DataSourceConfig |
| `app/api/v2/endpoints/workflows.py` | CRUD WorkflowStep |
| `app/api/v2/endpoints/outputs.py` | CRUD OutputConfig |
| `app/models/config.py` | Model `PartnerServiceConfig` |
| `app/models/data_source.py` | Model `DataSourceConfig` |
| `app/models/workflow.py` | Model `WorkflowStep` |
| `app/models/output.py` | Model `OutputConfig` |
| `app/schemas/` | Pydantic schemas cho validate request/response |

## Database Models & Quan hệ

```
PartnerServiceConfig (1)
├── DataSourceConfig (N)      ← source_name, source_type, file_config, db_config...
├── WorkflowStep (N)          ← step_order, left_source, right_source, matching_rules, output_name
└── OutputConfig (N)          ← output_name, columns_config, use_for_report
```

## Matching Rules — 2 chế độ cấu hình

Mỗi workflow step có phần **Quy tắc Matching** (`matching_rules`) hỗ trợ 2 chế độ UI:

### Chế độ Đơn giản (Simple)
- User chọn cột, transform (strip, upper, lower...), cấu hình nâng cao (substring, regex, replace) qua giao diện kéo thả
- Frontend tự sinh expression từ UI config
- Dữ liệu lưu trong `key_match.left`, `key_match.right`, `amount_match.left_column`, `amount_match.right_column`...
- Backend (`GenericMatchingEngine._match_by_structured_config`) đọc trực tiếp từ cấu hình structured này

### Chế độ Nâng cao (Advanced / Raw Expression)
- User bật checkbox "Mode nâng cao (raw expression)"
- Hiển thị textarea để nhập trực tiếp expression Pandas, VD:
  ```
  LEFT['Mô tả'].str.extract(r'HD:(.*?)(?:;|$)') == RIGHT['Mã khách hàng'].astype(str)
  ```
- Dữ liệu lưu vào `key_match.expression` và `amount_match.expression`
- Backend (`GenericMatchingEngine._match_by_expression`) parse expression để matching

### Lưu trữ mode preference

- `matching_rules.mode` = `'advanced'` hoặc `'simple'` (hoặc không có = mặc định simple)
- Field này dùng để **restore đúng chế độ UI** khi user mở lại trang config
- Frontend component `MatchingRulesEditorV2` đọc `matching_rules.mode` khi init để set `showAdvanced`

### Cấu trúc JSON `matching_rules`

```json
{
  "mode": "advanced",           // UI mode preference (simple | advanced)
  "match_type": "expression",   // Backend matching strategy
  "rules": [],                  // Legacy rules array (V1 compat)
  "key_match": {
    "left": { "parts": [...], "transforms": [...] },   // Simple mode config
    "right": { "parts": [...], "transforms": [...] },   // Simple mode config
    "expression": "LEFT[...] == RIGHT[...]"             // Advanced mode expression
  },
  "amount_match": {
    "left_column": "Ghi có",      // Simple mode
    "right_column": "Số tiền",    // Simple mode
    "left": { "numberTransform": {...}, "transforms": [...] },
    "right": { "numberTransform": {...}, "transforms": [...] },
    "expression": "normalize_number(...) == normalize_number(...)"  // Advanced mode
  },
  "status_logic": {
    "all_match": "MATCHED",
    "key_match_amount_mismatch": "MISMATCH",
    "no_key_match": "NOT_FOUND"
  }
}
```

### Lưu ý khi sửa code

- **Frontend**: `MatchingRulesEditorV2` trong `ConfigEditV2Page.jsx` (dòng ~2557) quản lý cả 2 mode
- **Backend**: `GenericMatchingEngine` có 2 path: `_match_by_structured_config` (simple) và `_match_by_expression` (advanced/rules)
- Khi toggle mode, `matching_rules.mode` được cập nhật → lưu cùng workflow step → restore khi load lại
- Cả 2 mode đều lưu song song (simple config + expression) — không xóa config của mode kia khi chuyển

## Lưu ý khi nâng cấp

- **Tên source/output là convention**: B1, B4, A1, A2 chỉ là ví dụ — hệ thống chấp nhận bất kỳ tên nào
- **Source types**: FILE_UPLOAD (user upload), DATABASE (query SQL), SFTP, API — mỗi loại có config riêng
- **Workflow step chaining**: `left_source`/`right_source` có thể là data source gốc HOẶC output_name của step trước
- **is_final_output**: `true` = output chi tiết xuất ra cho user + dùng cho report; `false` = output trung gian chỉ dùng nội bộ workflow
- **OutputConfig ≠ matching output**: OutputConfig là cấu hình **tạo Report Excel** (template + SQL), không phải kết quả matching
- **Validity period**: Mỗi config có valid_from/valid_to — khi chạy đối soát, system chọn config đúng thời kỳ
- **Column config**: Lưu dạng JSON object `{alias: source}` — ConfigEditV2Page convert qua lại giữa array ↔ object
