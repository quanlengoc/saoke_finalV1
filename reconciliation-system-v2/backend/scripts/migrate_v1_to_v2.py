"""
Migration Script: V1 to V2 Schema
Migrates SACOMBANK/TOPUP (config id=1) from fixed columns to dynamic tables

This script:
1. Drops old tables and creates new schema
2. Inserts sample SACOMBANK/TOPUP configuration with:
   - Data sources: B1, B2, B3, B4
   - Workflow steps: B1↔B4, B1↔B2, combine, B3↔A1
   - Output configs: A1, A2

Run from backend/: python scripts/migrate_v1_to_v2.py
"""

import sys
import json
from datetime import date
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import sessionmaker

from app.core.database import Base, DatabaseManager
from app.models import (
    PartnerServiceConfig, 
    DataSourceConfig, 
    WorkflowStep, 
    OutputConfig,
    User,
    ReconciliationLog
)


def create_sample_sacombank_config(session):
    """Create sample SACOMBANK/TOPUP configuration for V2 schema"""
    
    # 1. Create main config
    config = PartnerServiceConfig(
        id=1,
        partner_code="SACOMBANK",
        partner_name="Ngân hàng TMCP Sài Gòn Thương Tín",
        service_code="TOPUP",
        service_name="Nạp tiền điện thoại",
        is_active=True,
        valid_from=date(2024, 1, 1),
        valid_to=None,
        report_template_path="templates/shared/REPORT_TEMPLATE.xlsx",
        report_cell_mapping=json.dumps({
            "sheets": [
                {
                    "sheet_name": "Summary",
                    "sql_cells": [
                        {"cell": "C10", "sql": "SELECT COUNT(*) FROM temp_a1"},
                        {"cell": "C11", "sql": "SELECT SUM(amount) FROM temp_a1 WHERE status='MATCHED'"}
                    ]
                }
            ]
        })
    )
    session.add(config)
    session.flush()  # Get the ID
    
    print(f"✓ Created PartnerServiceConfig id={config.id}")
    
    # 2. Create Data Sources
    data_sources = [
        DataSourceConfig(
            config_id=config.id,
            source_name="B1",
            source_type="FILE_UPLOAD",
            display_name="Sao kê ngân hàng (Bank Statement)",
            is_required=True,
            display_order=1,
            file_config=json.dumps({
                "header_row": 1,
                "data_start_row": 2,
                "columns": {
                    "ref_no": "A",
                    "txn_date": "B",
                    "amount": "C",
                    "description": "D"
                },
                "transforms": {
                    "ref_no": ".str.strip().str.upper()",
                    "amount": ".str.replace(',', '').astype(float)"
                }
            })
        ),
        DataSourceConfig(
            config_id=config.id,
            source_name="B2",
            source_type="FILE_UPLOAD",
            display_name="Giao dịch hoàn tiền (Refund)",
            is_required=False,
            display_order=2,
            file_config=json.dumps({
                "header_row": 1,
                "data_start_row": 2,
                "columns": {
                    "original_ref": "A",
                    "refund_date": "B",
                    "refund_amount": "C"
                }
            })
        ),
        DataSourceConfig(
            config_id=config.id,
            source_name="B3",
            source_type="FILE_UPLOAD",
            display_name="Đối chiếu bên thứ 3 (Third-party)",
            is_required=False,
            display_order=3,
            file_config=json.dumps({
                "header_row": 1,
                "data_start_row": 2,
                "columns": {
                    "partner_ref": "A",
                    "partner_amount": "B",
                    "status": "C"
                }
            })
        ),
        DataSourceConfig(
            config_id=config.id,
            source_name="B4",
            source_type="DATABASE",
            display_name="Dữ liệu giao dịch hệ thống (System Data)",
            is_required=True,
            display_order=4,
            db_config=json.dumps({
                "db_connection": "vnptmoney_main",
                "sql_file": "shared/sacombank_topup.sql",
                "sql_params": {},
                "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
            })
        )
    ]
    
    for ds in data_sources:
        session.add(ds)
    session.flush()
    
    print(f"✓ Created {len(data_sources)} DataSourceConfig records")
    
    # 3. Create Workflow Steps
    workflow_steps = [
        WorkflowStep(
            config_id=config.id,
            step_order=1,
            step_name="Match Bank Statement with System",
            left_source="B1",
            right_source="B4",
            join_type="left",
            matching_rules=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "type": "key_match",
                        "left_expr": "LEFT['ref_no'].str.strip()",
                        "right_expr": "RIGHT['trans_id'].str.strip()"
                    },
                    {
                        "type": "amount_match",
                        "left_col": "amount",
                        "right_col": "total_amount",
                        "tolerance": 0
                    }
                ],
                "status_logic": {
                    "key_match_amount_match": "MATCHED",
                    "key_match_amount_mismatch": "AMOUNT_MISMATCH",
                    "no_key_match": "NOT_FOUND"
                }
            }),
            output_name="A1_STEP1",
            is_final_output=False
        ),
        WorkflowStep(
            config_id=config.id,
            step_order=2,
            step_name="Match with Refund",
            left_source="A1_STEP1",
            right_source="B2",
            join_type="left",
            matching_rules=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "type": "key_match",
                        "left_expr": "LEFT['ref_no'].str.strip()",
                        "right_expr": "RIGHT['original_ref'].str.strip()"
                    }
                ],
                "status_logic": {
                    "key_match": "HAS_REFUND",
                    "no_key_match": "NO_REFUND"
                }
            }),
            output_name="A1_STEP2",
            is_final_output=False,
            status_combine_rules=json.dumps({
                "rules": [
                    {"b1b4": "MATCHED", "b1b2": "NO_REFUND", "final": "OK"},
                    {"b1b4": "MATCHED", "b1b2": "HAS_REFUND", "final": "REFUNDED"},
                    {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_MATCHED"},
                    {"b1b4": "AMOUNT_MISMATCH", "b1b2": "*", "final": "AMOUNT_DIFF"}
                ],
                "default": "UNKNOWN"
            })
        ),
        WorkflowStep(
            config_id=config.id,
            step_order=3,
            step_name="Match A1 with Third-party",
            left_source="B3",  # B3 is driver (standard)
            right_source="A1_STEP2",  # Match against combined A1
            join_type="left",
            matching_rules=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "type": "key_match",
                        "left_expr": "LEFT['partner_ref'].str.strip()",
                        "right_expr": "RIGHT['ref_no'].str.strip()"
                    },
                    {
                        "type": "amount_match",
                        "left_col": "partner_amount",
                        "right_col": "amount",
                        "tolerance": 0
                    }
                ],
                "status_logic": {
                    "key_match_amount_match": "MATCHED",
                    "key_match_amount_mismatch": "AMOUNT_MISMATCH",
                    "no_key_match": "NOT_IN_BANK"
                }
            }),
            output_name="A2",
            is_final_output=True
        ),
        WorkflowStep(
            config_id=config.id,
            step_order=4,
            step_name="Final A1 Output",
            left_source="A1_STEP2",
            right_source="B3",  # Just to have a right source
            join_type="left",
            matching_rules=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "type": "key_match",
                        "left_expr": "LEFT['ref_no'].str.strip()",
                        "right_expr": "RIGHT['partner_ref'].str.strip()"
                    }
                ],
                "status_logic": {
                    "key_match": "CONFIRMED",
                    "no_key_match": "NOT_IN_PARTNER"
                }
            }),
            output_name="A1",
            is_final_output=True
        )
    ]
    
    for ws in workflow_steps:
        session.add(ws)
    session.flush()
    
    print(f"✓ Created {len(workflow_steps)} WorkflowStep records")
    
    # 4. Create Output Configs
    output_configs = [
        OutputConfig(
            config_id=config.id,
            output_name="A1",
            display_name="Kết quả đối soát chi tiết",
            display_order=1,
            use_for_report=True,
            columns_config=json.dumps({
                "columns": [
                    {"name": "stt", "source": "auto", "type": "row_number"},
                    {"name": "ref_no", "source": "B1", "column": "ref_no", "display_name": "Số tham chiếu"},
                    {"name": "txn_date", "source": "B1", "column": "txn_date", "display_name": "Ngày giao dịch"},
                    {"name": "amount", "source": "B1", "column": "amount", "display_name": "Số tiền"},
                    {"name": "system_amount", "source": "B4", "column": "total_amount", "display_name": "Số tiền hệ thống"},
                    {"name": "status", "source": "computed", "column": "final_status", "display_name": "Trạng thái"},
                    {"name": "note", "source": "computed", "column": "note", "display_name": "Ghi chú"}
                ]
            }),
            filter_status=None
        ),
        OutputConfig(
            config_id=config.id,
            output_name="A2",
            display_name="Kết quả đối soát bên thứ 3",
            display_order=2,
            use_for_report=True,
            columns_config=json.dumps({
                "columns": [
                    {"name": "stt", "source": "auto", "type": "row_number"},
                    {"name": "partner_ref", "source": "B3", "column": "partner_ref", "display_name": "Mã giao dịch ĐT"},
                    {"name": "partner_amount", "source": "B3", "column": "partner_amount", "display_name": "Số tiền ĐT"},
                    {"name": "bank_ref", "source": "A1", "column": "ref_no", "display_name": "Số tham chiếu NH"},
                    {"name": "bank_amount", "source": "A1", "column": "amount", "display_name": "Số tiền NH"},
                    {"name": "status", "source": "computed", "column": "status", "display_name": "Trạng thái"}
                ]
            }),
            filter_status=None
        )
    ]
    
    for oc in output_configs:
        session.add(oc)
    session.flush()
    
    print(f"✓ Created {len(output_configs)} OutputConfig records")
    
    return config


def migrate():
    """Run the migration"""
    print("=" * 60)
    print("Migration: V1 to V2 Schema")
    print("=" * 60)
    
    # Get engine from DatabaseManager
    engine = DatabaseManager.get_app_engine()
    
    # Create all tables (drops existing)
    print("\n1. Creating new schema...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("✓ Schema created")
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("\n2. Creating sample SACOMBANK/TOPUP config...")
        config = create_sample_sacombank_config(session)
        
        # Commit
        session.commit()
        print("\n✓ Migration completed successfully!")
        
        # Summary
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"  - Config ID: {config.id}")
        print(f"  - Partner: {config.partner_code}/{config.service_code}")
        print(f"  - Data Sources: {len(config.data_sources)}")
        print(f"  - Workflow Steps: {len(config.workflow_steps)}")
        print(f"  - Output Configs: {len(config.output_configs)}")
        print("=" * 60)
        
    except Exception as e:
        session.rollback()
        print(f"\n✗ Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
