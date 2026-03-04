"""
Test with real data from batch SACOMBANK_TOPUP_20260211_095621
"""
import pandas as pd
import json
from pathlib import Path
from app.services.file_processor import FileProcessor
from app.services.reconciliation_engine import ReconciliationEngine
from app.core.database import DatabaseManager
from sqlalchemy.orm import Session
from app.models.config import PartnerServiceConfig
from app.models.reconciliation import ReconciliationLog
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')

def test_real_data():
    batch_id = 'SACOMBANK_TOPUP_20260211_095621'
    processed_folder = Path(r'd:/AnhTM/VH-Works/PTDL - Quản lý Công việc/Report/FINDATAR_1905/Sokhop_saoke/reconciliation-system/storage/processed/SACOMBANK') / batch_id
    
    # Get config
    engine_db = DatabaseManager.get_app_engine()
    with Session(engine_db) as session:
        config = session.query(PartnerServiceConfig).filter_by(
            partner_code='SACOMBANK', 
            service_code='TOPUP'
        ).first()
        
        if not config:
            print("Config not found!")
            return
        
        b3a1_rules = json.loads(config.matching_rules_b3a1) if config.matching_rules_b3a1 else {}
        a2_output = json.loads(config.output_a2_config) if config.output_a2_config else {}
        
    # Read processed B3.csv and A1.csv
    b3_csv = processed_folder / "B3.csv"
    a1_csv = processed_folder / "A1.csv"
    
    print(f"=== Looking for processed files ===")
    print(f"B3 path: {b3_csv} - exists: {b3_csv.exists()}")
    print(f"A1 path: {a1_csv} - exists: {a1_csv.exists()}")
    print()
    
    if b3_csv.exists():
        df_b3 = pd.read_csv(b3_csv)
        print(f"B3 rows: {len(df_b3)}")
        print(f"B3 columns: {list(df_b3.columns)}")
        print()
        print("B3 sample (first 5 rows):")
        print(df_b3.head())
        print()
        
        if 'TRACE_NO' in df_b3.columns:
            print("=== TRACE_NO sample values ===")
            print(df_b3['TRACE_NO'].head(10).tolist())
    else:
        print("B3.csv not found. Listing processed folder:")
        if processed_folder.exists():
            for f in processed_folder.iterdir():
                print(f"  {f.name}")
        else:
            print(f"  Folder doesn't exist: {processed_folder}")
    
    if a1_csv.exists():
        df_a1 = pd.read_csv(a1_csv)
        print(f"\nA1 rows: {len(df_a1)}")
        print(f"A1 columns: {list(df_a1.columns)}")
        
        if 'transaction_remarks' in df_a1.columns:
            print("\n=== transaction_remarks sample ===")
            print(df_a1['transaction_remarks'].head(10).tolist())

if __name__ == "__main__":
    test_real_data()
