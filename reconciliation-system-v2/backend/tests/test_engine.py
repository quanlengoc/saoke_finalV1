"""Test engine matching directly"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

import json
import sqlite3
import pandas as pd
from app.services.reconciliation_engine import ReconciliationEngine
from app.utils.excel_utils import read_excel_with_config

# Load config
conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

cursor.execute("SELECT matching_rules_b1b4, file_b1_config, data_b4_config FROM partner_service_config LIMIT 1")
row = cursor.fetchone()
matching_rules = json.loads(row[0])
b1_config = json.loads(row[1])
b4_config = json.loads(row[2])

cursor.execute("SELECT files_uploaded FROM reconciliation_logs WHERE batch_id='SACOMBANK_TOPUP_20260209_173827'")
row = cursor.fetchone()
files = json.loads(row[0])
b1_path = files['b1'][0]
conn.close()

print("=== Testing Engine Matching ===")
print(f"Expression: {matching_rules['rules'][0]['expression']}")

# Load data (just 100 rows for testing)
df_b1 = read_excel_with_config(b1_path, b1_config).head(100)
print(f"B1: {len(df_b1)} rows, columns: {list(df_b1.columns)}")

df_b4 = pd.read_csv("../storage/mock_data/" + b4_config.get('mock_file', 'Findata_1906_B4_30_12.csv'))
df_b4.columns = df_b4.columns.str.lower()
print(f"B4: {len(df_b4)} rows, columns: {list(df_b4.columns)}")

# Create engine
engine = ReconciliationEngine("SACOMBANK", "TOPUP", "TEST")

# Call match directly
print("\n=== Calling match_b1_b4 ===")
result = engine.match_b1_b4(df_b1, df_b4, matching_rules)

print(f"Result shape: {result.shape}")
print(f"Result columns: {list(result.columns)}")
print(f"\nStatus value counts:")
if 'status' in result.columns:
    print(result['status'].value_counts())
else:
    print("NO 'status' column!")
    print(f"Available columns: {list(result.columns)}")

print(f"\nFirst 10 rows of result:")
print(result.head(10))

print("\n=== Step logs ===")
for log in engine.step_logs:
    print(f"[{log['step']}] {log['status']}: {log['message']}")
