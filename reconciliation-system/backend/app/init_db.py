"""
Database initialization script
Creates tables and inserts sample data
"""

import json
from datetime import date, datetime

from app.core.database import DatabaseManager, Base
from app.core.security import get_password_hash
from app.models import User, UserPermission, PartnerServiceConfig, ReconciliationLog


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
        # Create Partner Service Configs
        # ====================================================================
        
        # SACOMBANK TOPUP Config
        sacombank_topup_config = PartnerServiceConfig(
            partner_code="SACOMBANK",
            partner_name="Ngân hàng Sacombank",
            service_code="TOPUP",
            service_name="Nạp tiền",
            is_active=True,
            valid_from=date(2025, 1, 1),
            valid_to=None,
            
            file_b1_config=json.dumps({
                "header_row": 1,
                "data_start_row": 2,
                "columns": {
                    "txn_id": "A",
                    "txn_date": "B",
                    "amount": "C",
                    "description": "D",
                    "status": "E"
                }
            }),
            
            file_b2_config=json.dumps({
                "header_row": 1,
                "data_start_row": 2,
                "columns": {
                    "refund_id": "A",
                    "original_txn_id": "B",
                    "refund_amount": "C",
                    "refund_date": "D"
                }
            }),
            
            file_b3_config=None,
            
            data_b4_config=json.dumps({
                "db_connection": "vnptmoney_main",
                "sql_file": "shared/query_b4_topup.sql",
                "sql_params": {
                    "service_id": "TOPUP_001",
                    "partner_id": "SACOM_01"
                },
                "mock_file": "SACOMBANK_TOPUP_b4_mock.csv"
            }),
            
            matching_rules_b1b4=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "rule_name": "key_match",
                        "type": "expression",
                        "expression": "b1['txn_id'].str.strip().str.upper() == b4['transaction_ref'].str.strip().str.upper()"
                    },
                    {
                        "rule_name": "amount_match",
                        "type": "expression",
                        "expression": "abs(b1['amount'].astype(float) - b4['total_amount'].astype(float)) <= 0.01"
                    }
                ],
                "status_logic": {
                    "all_match": "MATCHED",
                    "key_match_amount_mismatch": "MISMATCH",
                    "no_key_match": "NOT_FOUND"
                }
            }),
            
            matching_rules_b1b2=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "rule_name": "key_match",
                        "type": "expression",
                        "expression": "b1['txn_id'].str.strip() == b2['original_txn_id'].str.strip()"
                    }
                ],
                "status_logic": {
                    "all_match": "MATCHED",
                    "no_key_match": "NOT_FOUND"
                }
            }),
            
            matching_rules_b3a1=None,
            
            status_combine_rules=json.dumps({
                "rules": [
                    {"b1b4": "MATCHED", "b1b2": "NOT_FOUND", "final": "OK"},
                    {"b1b4": "MATCHED", "b1b2": "MATCHED", "final": "REFUNDED"},
                    {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_IN_SYSTEM"},
                    {"b1b4": "MISMATCH", "b1b2": "*", "final": "AMOUNT_ERROR"}
                ],
                "default": "UNKNOWN"
            }),
            
            output_a1_config=json.dumps({
                "columns": [
                    {"name": "txn_id", "source": "B1", "column": "txn_id"},
                    {"name": "txn_date", "source": "B1", "column": "txn_date"},
                    {"name": "amount_b1", "source": "B1", "column": "amount"},
                    {"name": "description", "source": "B1", "column": "description"},
                    {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
                    {"name": "channel", "source": "B4", "column": "channel", "default": ""},
                    {"name": "refund_amount", "source": "B2", "column": "refund_amount", "default": 0},
                    {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
                    {"name": "status_b1b2", "source": "_SYSTEM", "column": "status_b1b2"},
                    {"name": "final_status", "source": "_SYSTEM", "column": "final_status"},
                    {"name": "amount_diff", "source": "_SYSTEM", "column": "amount_diff"},
                    {"name": "note", "source": "_SYSTEM", "column": "note"}
                ]
            }),
            
            output_a2_config=None,
            
            report_template_path="shared/report_topup.xlsx",
            
            report_cell_mapping=json.dumps({
                "sheets": [
                    {
                        "sheet_name": "Tổng hợp",
                        "static_cells": {
                            "B2": "{partner_name}",
                            "B3": "{period_from} - {period_to}",
                            "B4": "{created_date}",
                            "B5": "{created_by}"
                        },
                        "sql_cells": [
                            {"cell": "C10", "sql": "SELECT COUNT(*) FROM temp_a1"},
                            {"cell": "C11", "sql": "SELECT COUNT(*) FROM temp_a1 WHERE final_status='OK'"},
                            {"cell": "C12", "sql": "SELECT COUNT(*) FROM temp_a1 WHERE final_status='NOT_IN_SYSTEM'"},
                            {"cell": "C13", "sql": "SELECT COUNT(*) FROM temp_a1 WHERE final_status='AMOUNT_ERROR'"},
                            {"cell": "C14", "sql": "SELECT COUNT(*) FROM temp_a1 WHERE final_status='REFUNDED'"},
                            {"cell": "D11", "sql": "SELECT COALESCE(SUM(amount_b1),0) FROM temp_a1 WHERE final_status='OK'"},
                            {"cell": "D12", "sql": "SELECT COALESCE(SUM(amount_b1),0) FROM temp_a1 WHERE final_status='NOT_IN_SYSTEM'"}
                        ]
                    },
                    {
                        "sheet_name": "Chi tiết",
                        "data_start_cell": "A5",
                        "data_sql": "SELECT txn_id, txn_date, amount_b1, status_b1b4, status_b1b2, final_status, note FROM temp_a1 ORDER BY txn_date, txn_id",
                        "columns": ["A", "B", "C", "D", "E", "F", "G"]
                    }
                ]
            })
        )
        session.add(sacombank_topup_config)
        
        # VCB TOPUP Config (simpler example)
        vcb_topup_config = PartnerServiceConfig(
            partner_code="VCB",
            partner_name="Ngân hàng Vietcombank",
            service_code="TOPUP",
            service_name="Nạp tiền",
            is_active=True,
            valid_from=date(2025, 1, 1),
            valid_to=None,
            
            file_b1_config=json.dumps({
                "header_row": 2,
                "data_start_row": 3,
                "columns": {
                    "txn_id": "B",
                    "txn_date": "C",
                    "amount": "D"
                }
            }),
            
            file_b2_config=None,
            file_b3_config=None,
            
            data_b4_config=json.dumps({
                "db_connection": "vnptmoney_main",
                "sql_file": "shared/query_b4_topup.sql",
                "sql_params": {"service_id": "TOPUP_001", "partner_id": "VCB_01"},
                "mock_file": "VCB_TOPUP_b4_mock.csv"
            }),
            
            matching_rules_b1b4=json.dumps({
                "match_type": "expression",
                "rules": [
                    {
                        "rule_name": "key_match",
                        "type": "expression",
                        "expression": "b1['txn_id'].str.strip() == b4['transaction_ref'].str.strip()"
                    },
                    {
                        "rule_name": "amount_match",
                        "type": "expression",
                        "expression": "b1['amount'].astype(float) == b4['total_amount'].astype(float)"
                    }
                ],
                "status_logic": {
                    "all_match": "MATCHED",
                    "key_match_amount_mismatch": "MISMATCH",
                    "no_key_match": "NOT_FOUND"
                }
            }),
            
            matching_rules_b1b2=None,
            matching_rules_b3a1=None,
            
            status_combine_rules=json.dumps({
                "rules": [
                    {"b1b4": "MATCHED", "b1b2": "*", "final": "OK"},
                    {"b1b4": "NOT_FOUND", "b1b2": "*", "final": "NOT_IN_SYSTEM"},
                    {"b1b4": "MISMATCH", "b1b2": "*", "final": "AMOUNT_ERROR"}
                ],
                "default": "UNKNOWN"
            }),
            
            output_a1_config=json.dumps({
                "columns": [
                    {"name": "txn_id", "source": "B1", "column": "txn_id"},
                    {"name": "txn_date", "source": "B1", "column": "txn_date"},
                    {"name": "amount_b1", "source": "B1", "column": "amount"},
                    {"name": "amount_b4", "source": "B4", "column": "total_amount", "default": 0},
                    {"name": "status_b1b4", "source": "_SYSTEM", "column": "status_b1b4"},
                    {"name": "final_status", "source": "_SYSTEM", "column": "final_status"}
                ]
            }),
            
            output_a2_config=None,
            report_template_path="shared/report_topup.xlsx",
            report_cell_mapping=None
        )
        session.add(vcb_topup_config)
        
        print("✓ Created partner service configs: SACOMBANK/TOPUP, VCB/TOPUP")
        
        session.commit()
        print("\n✓ Database initialization completed!")


if __name__ == "__main__":
    init_database()
