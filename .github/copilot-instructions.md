# Copilot Instructions for Reconciliation System V2

This is a **transaction reconciliation platform** that matches financial data across multiple sources using configurable workflows.

## 🎯 System Overview

**Purpose**: Compare bank statements (B1), system data (B4), and optional data sources (B2, B3) to identify matched, mismatched, and unreconciled transactions.

**Key Concept**: Configuration-driven reconciliation via multi-step workflows defined in the database, not hardcoded.
- Each partner has a `PartnerServiceConfig` defining available data sources
- Each service has `WorkflowStep` records that execute in sequence
- Matching rules are stored as JSON expressions, not code

## 🔄 Core Data Flow

```
User Creates Batch → Uploads Files (B1, B2, B3)
                    ↓
WorkflowExecutor Loads All Data
  - FILE_UPLOAD sources: Read from uploaded files via DataLoaderFactory
  - DATABASE sources: Query Oracle/SQLite using DataSourceConfig (SQL template + cycle params)
                    ↓
Executes Workflow Steps (in step_order):
  Step N: GenericMatchingEngine.match_datasets(left_df, right_df, join_type, rules)
          Returns raw result: [left_idx, right_idx, status, note, amount_diff]
                    ↓
Applies OutputConfig (schema transformation):
  - Renames columns to user-friendly names
  - Applies filters & aggregations
  - Stores intermediate result (e.g., A1_1, A1_2)
                    ↓
Final Output: A1 (matched detail), A2 (summary), reports
```

**Key Datasets**:
- **B1** = Bank/Partner statement (FILE_UPLOAD) - left side of matching
- **B4** = System data (DATABASE) - canonical source
- **B2**, **B3** = Optional data sources (FILE_UPLOAD or DATABASE)
- **A1**, **A2** = Reconciliation output datasets

## 🛠️ Core Services

### WorkflowExecutor (`services/workflow_executor.py`)
**Orchestrates the reconciliation process**
- Loads data from file system or database
- Executes workflow steps in sequence
- Applies output column transformations
- Returns `WorkflowResult` with all datasets and statistics

**Usage**: Called from API endpoint `/batch/{batch_id}/execute`

### GenericMatchingEngine (`services/generic_matching_engine.py`)
**Performs actual dataset matching**
- Accepts two DataFrames, join type, and matching rules
- Matches using configurable rules (expressions + status logic)
- Returns indexed results (left_idx, right_idx, status)

**Matching Rule Structure**:
```json
{
  "match_type": "expression",
  "rules": [
    {"type": "key_match", "left_expr": "...", "right_expr": "..."},
    {"type": "amount_match", "left_col": "...", "right_col": "...", "tolerance": 0.01}
  ],
  "status_logic": {
    "all_match": "MATCHED",
    "key_match_amount_mismatch": "AMOUNT_MISMATCH",
    "no_key_match": "NOT_FOUND"
  }
}
```

### DataLoaderFactory (`services/data_loader.py`)
**Abstracts data loading from multiple sources**
- `FILE_UPLOAD`: Reads CSV/Excel from uploaded files using Pandas
- `DATABASE`: Executes SQL template with cycle parameters (date_from, date_to)
- Applies data transformations (column mapping, type casting)

**Returns**: `DataLoaderResult` with DataFrame, metadata, and execution time

### ReportGenerator (`services/report_generator.py`)
**Generates Excel/CSV exports**
- Uses template from `storage/templates/`
- Maps output DataFrames to template sheets
- Applies formatting, formulas, and filters

### WorkflowService (`services/workflow_service.py`)
**High-level business logic**
- CRUD for batches and workflow configurations
- Status tracking (PENDING → RUNNING → SUCCESS/FAILED)
- Orchestrates executor and report generation

## ⚙️ Configuration Patterns

### PartnerServiceConfig (Database Model)
Defines what a partner service can do:
```python
{
  "partner_code": "SACOMBANK",
  "service_name": "TOPUP",
  "data_sources": [DataSourceConfig, ...],  # Available data sources
  "workflow_steps": [WorkflowStep, ...],    # Execution steps
  "output_configs": [OutputConfig, ...],    # Result schemas
  "status_combine_rules": {...}             # Final status logic
}
```

### DataSourceConfig
Defines how to load a data source:
```python
{
  "source_name": "B4",
  "source_type": "DATABASE",  # or FILE_UPLOAD
  "sql_template": "query_b4.sql",  # For DATABASE type
  "expected_columns": ["txn_id", "amount", ...]
}
```

### WorkflowStep
Defines a matching operation:
```python
{
  "step_order": 1,
  "left_source": "B1",
  "right_source": "B4",
  "join_type": "left",  # left, right, inner, outer
  "matching_rules": {...},  # JSON expression config
  "output_config_id": 1    # Which output schema to apply
}
```

### OutputConfig
Defines result DataFrame schema and transformations:
```python
{
  "output_name": "A1_1",
  "columns": [
    {"source_column": "b1_index", "output_column": "txn_id", "transforms": ["strip"]},
    {...}
  ],
  "filters": [{"column": "status", "operator": "in", "values": ["MATCHED", "MISMATCH"]}]
}
```

## 📁 File Organization

```
reconciliation-system-v2/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI endpoints
│   │   │   ├── v1/           # Legacy endpoints
│   │   │   └── v2/           # Current endpoints (batch, workflow, config)
│   │   ├── models/           # SQLAlchemy models (config, batch, step)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic (executor, engine, loaders)
│   │   ├── core/             # Database, config, logging
│   │   └── utils/            # Helpers (file processing, formatting)
│   ├── storage/
│   │   ├── uploads/          # User-uploaded files (B1, B2, B3)
│   │   ├── exports/          # Generated reports (CSV, Excel)
│   │   ├── templates/        # Report templates (.xlsx)
│   │   ├── mock_data/        # Test data files
│   │   ├── sql_templates/    # SQL queries for database sources
│   │   └── custom_matching/  # Custom Python matching modules
│   └── data/
│       └── app.db            # SQLite database (or Oracle for production)
├── frontend/
│   └── src/
│       ├── pages/            # Page components (Batch, Config, Results)
│       ├── components/       # Reusable UI components
│       ├── services/         # API client services
│       └── stores/           # State management (Pinia/Zustand)
├── docker/                   # Docker configuration
├── scripts/                  # Setup and utility scripts
└── docs/                     # Documentation
```

## 🔑 Key Patterns & Conventions

### 1. Data Transformation Pipeline
All data flows through transformations:
- **Load**: File or database → Raw DataFrame
- **Normalize**: Apply column mappings, type casting
- **Match**: Apply matching rules
- **Resolve**: Apply OutputConfig to rename/filter columns
- **Export**: Format for Excel/CSV

### 2. Status Lifecycle
Transactions flow through status values defined in `status_logic`:
- `MATCHED`: All matching rules pass
- `AMOUNT_MISMATCH`: Key matches but amount differs
- `NOT_FOUND`: No matching record in right dataset
- Custom statuses per partner (e.g., `REFUNDED`, `OK`)

### 3. Configuration Over Code
**Don't hardcode matching logic.** Always use:
- `PartnerServiceConfig` for partner-specific setup
- `WorkflowStep` for step execution order
- `matching_rules` JSON for matching logic
- `OutputConfig` for result schema

### 4. Error Handling
- All operations return `WorkflowResult` with `success: bool` and `error_message`
- Step logs capture detailed execution info: time, rows processed, matches found
- Use `BatchLogger` to track per-batch execution

### 5. Storage Paths
Always use paths from `CoreConfig`:
- `UPLOAD_PATH`: Incoming files
- `OUTPUT_PATH`: Finished reports
- `TEMPLATE_PATH`: Report templates
- `SQL_TEMPLATES_PATH`: SQL files
- `MOCK_DATA_PATH`: Test data

## 🚀 Development Workflows

### Add New Matching Rule Type
1. Define rule structure in plan docs (e.g., `plan_v2_final.md`)
2. Add handling in `GenericMatchingEngine.match_datasets()`
3. Add UI config mapping if applicable
4. Test with mock data in `storage/mock_data/`

### Add Custom Data Loader
1. Create loader class extending base in `data_loaders/`
2. Register in `DataLoaderFactory.create_loader()`
3. Add corresponding `DataSourceConfig.source_type`

### Add New Partner Service
1. Create `PartnerServiceConfig` record via API or `init_db.py`
2. Create SQL templates in `storage/sql_templates/{partner_code}/`
3. Define `WorkflowStep` records with matching rules
4. Define `OutputConfig` for result schemas
5. Test with sample data via POST `/api/v2/batch` endpoint

### Database Re-initialization
```bash
# For SQLite development
python -c "from app.init_db import init_database; init_database()"

# For Oracle, run migrations manually with init_db.py setup
```

## 🧪 Testing Patterns

- **Unit**: Mock DataFrames and matching rules in `backend/tests/test_engine.py`
- **Integration**: Use mock data from `storage/mock_data/` with real executor
- **End-to-end**: POST batch, execute, verify output matches expected schema

Use `MOCK_MODE=true` in `.env` to load B4 from `mock_data/` instead of database.

## 📊 Database Schema Highlights

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `partner_service_config` | Partner service definition | partner_code, service_name |
| `data_source_config` | Data source definition | source_type (FILE_UPLOAD/DATABASE), sql_template |
| `workflow_step` | Matching step | step_order, left_source, right_source, matching_rules |
| `output_config` | Result schema | output_name, columns (JSON), filters (JSON) |
| `batch` | Reconciliation run | status, start_time, end_time, stats |
| `batch_file` | Uploaded file reference | source_name, file_path, file_size |

---

**Last Updated**: March 5, 2026
**Use for**: Code generation, debugging, architecture questions about reconciliation workflows
