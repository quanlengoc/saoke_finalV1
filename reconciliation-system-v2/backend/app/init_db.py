"""
Database initialization script - V2
Creates tables and inserts sample data using new dynamic schema
"""

import json
from datetime import date, datetime

from app.core.database import DatabaseManager, Base
from app.core.security import get_password_hash
from app.models import (
    User, 
    UserPermission, 
    PartnerServiceConfig, 
    DataSourceConfig,
    WorkflowStep,
    OutputConfig,
    ReconciliationLog
)


def init_database():
    """Initialize database with tables and sample data"""
    
    # Create all tables
    engine = DatabaseManager.get_app_engine()
    Base.metadata.create_all(bind=engine)
    
    print("✓ Database tables created")
    
    # Insert sample data
    with DatabaseManager.session_scope() as session:
        # Check if data already exists
        existing_user = session.query(User).filter_by(email="admin@vnpt.vn").first()
        if existing_user:
            print("✓ Sample data already exists, skipping...")
            return
        
        # ====================================================================
        # Create Users
        # ====================================================================
        admin_user = User(
            email="admin@vnpt.vn",
            password_hash=get_password_hash("admin123"),
            full_name="Admin System",
            is_admin=True,
            is_active=True
        )
        session.add(admin_user)
        
        user1 = User(
            email="user1@vnpt.vn",
            password_hash=get_password_hash("user123"),
            full_name="Nguyễn Văn A",
            is_admin=False,
            is_active=True
        )
        session.add(user1)
        
        user2 = User(
            email="user2@vnpt.vn",
            password_hash=get_password_hash("user123"),
            full_name="Trần Thị B",
            is_admin=False,
            is_active=True
        )
        session.add(user2)
        
        session.flush()  # Get IDs
        
        print(f"✓ Created users: admin (id={admin_user.id}), user1 (id={user1.id}), user2 (id={user2.id})")
        
        # ====================================================================
        # Create Permissions
        # ====================================================================
        permissions = [
            UserPermission(user_id=user1.id, partner_code="SACOMBANK", service_code="TOPUP", can_reconcile=True, can_approve=False),
            UserPermission(user_id=user1.id, partner_code="SACOMBANK", service_code="PAYMENT", can_reconcile=True, can_approve=False),
            UserPermission(user_id=user1.id, partner_code="VCB", service_code="TOPUP", can_reconcile=True, can_approve=True),
            UserPermission(user_id=user2.id, partner_code="BIDV", service_code="TOPUP", can_reconcile=True, can_approve=True),
            UserPermission(user_id=user2.id, partner_code="SACOMBANK", service_code="TOPUP", can_reconcile=True, can_approve=True),
        ]
        session.add_all(permissions)
        
        print(f"✓ Created {len(permissions)} user permissions")
        
        # ====================================================================
        # Create Partner Service Config - V2 Schema
        # ====================================================================
        
        # 1. SACOMBANK TOPUP Config (main config only)
        sacombank_topup = PartnerServiceConfig(
            partner_code="SACOMBANK",
            partner_name="Ngân hàng Sacombank",
            service_code="TOPUP",
            service_name="Nạp tiền",
            is_active=True,
            valid_from=date(2025, 1, 1),
            valid_to=None,
            report_template_path="shared/report_topup.xlsx",
            report_cell_mapping=None
        )
        session.add(sacombank_topup)
        session.flush()  # Get ID
        
        # 2. Add Data Sources for SACOMBANK TOPUP
        data_sources = [
            DataSourceConfig(
                config_id=sacombank_topup.id,
                source_name="B1",
                source_type="FILE_UPLOAD",
                display_name="Sao kê ngân hàng",
                is_required=True,
                display_order=1,
                file_config=json.dumps({
                    "header_row": 1,
                    "data_start_row": 2,
                    "columns": {
                        "txn_id": "A",
                        "txn_date": "B",
                        "amount": "C",
                        "description": "D",
                        "status": "E"
                    },
                    "transforms": {
                        "txn_id": ".str.strip().str.upper()",
                        "amount": ".str.replace(',', '').astype(float)"
                    }
                })
            ),
            DataSourceConfig(
                config_id=sacombank_topup.id,
                source_name="B2",
                source_type="FILE_UPLOAD",
                display_name="File hoàn tiền",
                is_required=False,
                display_order=2,
                file_config=json.dumps({
                    "header_row": 1,
                    "data_start_row": 2,
                    "columns": {
                        "refund_id": "A",
                        "original_txn_id": "B",
                        "refund_amount": "C",
                        "refund_date": "D"
                    }
                })
            ),
            DataSourceConfig(
                config_id=sacombank_topup.id,
                source_name="B3",
                source_type="FILE_UPLOAD",
                display_name="Chi tiết đối tác",
                is_required=False,
                display_order=3,
                file_config=json.dumps({
                    "header_row": 1,
                    "data_start_row": 2,
                    "columns": {
                        "partner_txn_id": "A",
                        "bank_ref": "B",
                        "amount": "C"
                    }
                })
            ),
            DataSourceConfig(
                config_id=sacombank_topup.id,
                source_name="B4",
                source_type="DATABASE",
                display_name="VNPT Money System",
                is_required=True,
                display_order=4,
                db_config=json.dumps({
                    "db_connection": "vnptmoney_main",
                    "sql_file": "shared/query_b4_topup.sql",
                    "sql_params": {
                        "service_id": "TOPUP_001",
                        "partner_id": "SACOM_01"
                    },
                    "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
                })
            )
        ]
        session.add_all(data_sources)
        
        # 3. Add Workflow Steps for SACOMBANK TOPUP
        workflow_steps = [
            WorkflowStep(
                config_id=sacombank_topup.id,
                step_order=1,
                step_name="Đối soát B1-B4",
                left_source="B1",
                right_source="B4",
                join_type="left",
                matching_rules=json.dumps({
                    "match_type": "expression",
                    "rules": [
                        {
                            "type": "key_match",
                            "left_expr": "b1['txn_id'].str.strip().str.upper()",
                            "right_expr": "b4['transaction_ref'].str.strip().str.upper()"
                        },
                        {
                            "type": "amount_match",
                            "left_col": "amount",
                            "right_col": "total_amount",
                            "tolerance": 0.01
                        }
                    ],
                    "status_logic": {
                        "all_match": "MATCHED",
                        "key_match_amount_mismatch": "AMOUNT_MISMATCH",
                        "no_key_match": "NOT_FOUND"
                    }
                }),
                output_name="A1_B1B4",
                is_final_output=False
            ),
            WorkflowStep(
                config_id=sacombank_topup.id,
                step_order=2,
                step_name="Kiểm tra hoàn tiền",
                left_source="A1_B1B4",  # Use output from step 1
                right_source="B2",
                join_type="left",
                matching_rules=json.dumps({
                    "match_type": "expression",
                    "rules": [
                        {
                            "type": "key_match",
                            "left_expr": "a1['txn_id']",
                            "right_expr": "b2['original_txn_id']"
                        }
                    ],
                    "status_logic": {
                        "found_refund": "REFUNDED",
                        "no_refund": "NO_REFUND"
                    }
                }),
                output_name="A1_REFUND",
                is_final_output=False
            ),
            WorkflowStep(
                config_id=sacombank_topup.id,
                step_order=3,
                step_name="Mapping đối tác",
                left_source="A1_REFUND",
                right_source="B3",
                join_type="left",
                matching_rules=json.dumps({
                    "match_type": "expression",
                    "rules": [
                        {
                            "type": "key_match",
                            "left_expr": "a1['txn_id']",
                            "right_expr": "b3['bank_ref']"
                        }
                    ],
                    "status_logic": {
                        "found": "PARTNER_MAPPED",
                        "not_found": "NO_PARTNER"
                    }
                }),
                output_name="A1_PARTNER",
                is_final_output=False
            ),
            WorkflowStep(
                config_id=sacombank_topup.id,
                step_order=4,
                step_name="Tổng hợp kết quả cuối",
                left_source="A1_PARTNER",
                right_source="",  # No right source - just combine statuses
                join_type="left",
                matching_rules=json.dumps({
                    "match_type": "status_combine"
                }),
                output_name="A1_FINAL",
                is_final_output=True,
                status_combine_rules=json.dumps({
                    "rules": [
                        {"conditions": {"b1b4": "MATCHED", "refund": "*"}, "final": "OK"},
                        {"conditions": {"b1b4": "NOT_FOUND", "refund": "*"}, "final": "NOT_IN_SYSTEM"},
                        {"conditions": {"b1b4": "AMOUNT_MISMATCH", "refund": "*"}, "final": "AMOUNT_ERROR"},
                        {"conditions": {"b1b4": "*", "refund": "REFUNDED"}, "final": "REFUNDED"}
                    ],
                    "default": "UNKNOWN"
                })
            )
        ]
        session.add_all(workflow_steps)
        
        # 4. Add Output Configs for SACOMBANK TOPUP
        output_configs = [
            OutputConfig(
                config_id=sacombank_topup.id,
                output_name="A1_FINAL",
                display_name="Kết quả đối soát",
                columns_config=json.dumps({
                    "columns": [
                        {"name": "stt", "source": "auto", "type": "row_number", "display_name": "STT"},
                        {"name": "txn_id", "source": "B1", "column": "txn_id", "display_name": "Mã GD"},
                        {"name": "txn_date", "source": "B1", "column": "txn_date", "display_name": "Ngày GD"},
                        {"name": "amount_b1", "source": "B1", "column": "amount", "display_name": "Số tiền sao kê"},
                        {"name": "amount_b4", "source": "B4", "column": "total_amount", "display_name": "Số tiền hệ thống"},
                        {"name": "difference", "source": "computed", "expression": "amount_b1 - amount_b4", "display_name": "Chênh lệch"},
                        {"name": "status_b1b4", "source": "system", "column": "match_status_b1b4", "display_name": "Trạng thái B1-B4"},
                        {"name": "status_refund", "source": "system", "column": "match_status_refund", "display_name": "Trạng thái hoàn tiền"},
                        {"name": "final_status", "source": "system", "column": "final_status", "display_name": "Kết luận"}
                    ]
                }),
                filter_status=None,  # All statuses
                use_for_report=True,
                display_order=1
            ),
            OutputConfig(
                config_id=sacombank_topup.id,
                output_name="A2_ERRORS",
                display_name="Giao dịch lỗi",
                columns_config=json.dumps({
                    "columns": [
                        {"name": "stt", "source": "auto", "type": "row_number", "display_name": "STT"},
                        {"name": "txn_id", "source": "B1", "column": "txn_id", "display_name": "Mã GD"},
                        {"name": "txn_date", "source": "B1", "column": "txn_date", "display_name": "Ngày GD"},
                        {"name": "amount_b1", "source": "B1", "column": "amount", "display_name": "Số tiền sao kê"},
                        {"name": "amount_b4", "source": "B4", "column": "total_amount", "display_name": "Số tiền hệ thống"},
                        {"name": "final_status", "source": "system", "column": "final_status", "display_name": "Lỗi"}
                    ]
                }),
                filter_status=json.dumps({
                    "match_status": ["NOT_FOUND", "AMOUNT_MISMATCH", "UNKNOWN"]
                }),
                use_for_report=True,
                display_order=2
            )
        ]
        session.add_all(output_configs)
        
        print("✓ Created partner service config: SACOMBANK/TOPUP (V2 schema)")
        print(f"  - Data sources: {len(data_sources)}")
        print(f"  - Workflow steps: {len(workflow_steps)}")
        print(f"  - Output configs: {len(output_configs)}")
        
        session.commit()
        print("\n✓ Database initialization completed!")


if __name__ == "__main__":
    init_database()
