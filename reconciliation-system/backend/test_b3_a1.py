"""
Test B3↔A1 matching with swapped left/right
"""
import pandas as pd
import json
import logging
from app.services.reconciliation_engine import ReconciliationEngine
from app.services.file_processor import FileProcessor
from app.core.database import DatabaseManager
from sqlalchemy.orm import Session
from app.models.config import PartnerServiceConfig

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger(__name__)

def test_b3_a1_matching():
    """Test matching B3 (left) with A1 (right)"""
    
    # Get config from database
    engine_db = DatabaseManager.get_app_engine()
    with Session(engine_db) as session:
        config = session.query(PartnerServiceConfig).filter_by(
            partner_code='SACOMBANK', 
            service_code='TOPUP'
        ).first()
        
        if not config:
            print("Config not found!")
            return
        
        # Parse matching rules for B3↔A1
        b3a1_rules = json.loads(config.matching_rules_b3a1) if config.matching_rules_b3a1 else {}
        a2_output = json.loads(config.output_a2_config) if config.output_a2_config else {}
        
        print("=== B3-A1 matching rules ===")
        print(f"Expression: {b3a1_rules.get('key_expression', 'N/A')}")
        print()
    
    # Create mock data that should MATCH
    # B3 - Partner feedback (LEFT side)
    # TRACE_NO after replace EWX->BLX = BLX123456789012
    # This should match A1 where transaction_remarks[5:17] = BLX123456789
    b3_data = pd.DataFrame({
        'TrxnDate': ['2025-12-30', '2025-12-30', '2025-12-30'],
        'TRACE_NO': ['BLX123456789', 'BLX999888777', 'EWX111222333'],  # 12 char to match substring
        'remainAmt': [20000, 50000, 100000]
    })
    
    # A1 - Our result (RIGHT side)
    # transaction_remarks[5:17] = position 5 to 17 (12 chars)
    # "NAP  BLX123456789 TOPUP"[5:17] = "BLX123456789"
    a1_data = pd.DataFrame({
        'transaction_id': ['TXN001', 'TXN002', 'TXN003'],
        'transaction_remarks': ['NAP  BLX123456789 TOPUP', 'NAP  BLX987654321 TOPUP', 'NAP  BLX555666777 TOPUP'],
        'credit_amount': ['20,000', '30,000', '40,000'],
        'transaction_date': ['2025-12-30', '2025-12-30', '2025-12-30'],
        'final_status': ['MATCHED', 'MATCHED', 'NOT_FOUND']
    })
    
    print("=== Mock Data ===")
    print("B3 (LEFT):")
    print(b3_data)
    print()
    print("A1 (RIGHT):")
    print(a1_data)
    print()
    
    # Show what we expect
    print("=== Expected matching ===")
    print("B3 TRACE_NO (after replace EWX->BLX):")
    for i, row in b3_data.iterrows():
        key = str(row['TRACE_NO']).replace('EWX', 'BLX')
        print(f"  {i}: {row['TRACE_NO']} -> {key}")
    print()
    print("A1 transaction_remarks[5:17]:")
    for i, row in a1_data.iterrows():
        key = str(row['transaction_remarks'])[5:17]
        print(f"  {i}: '{row['transaction_remarks']}' -> '{key}'")
    print()
    
    # Test matching
    engine = ReconciliationEngine()
    
    print("=== Running match_b3_a1 ===")
    result = engine.match_b3_a1(b3_data, a1_data, b3a1_rules)
    print("\nMatch result:")
    print(result)
    print()
    
    # Summary
    print("=== Summary ===")
    print(f"B3 total: {len(b3_data)}")
    print(f"Matched in A1: {(result['status'] == 'MATCHED').sum()}")
    print(f"NOT_FOUND in A1: {(result['status'] == 'NOT_FOUND').sum()}")

if __name__ == "__main__":
    test_b3_a1_matching()
