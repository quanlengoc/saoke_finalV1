import sqlite3
import json
import pandas as pd
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from app.utils.excel_utils import read_excel_with_config

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Lấy config B1
cursor.execute('SELECT file_b1_config FROM partner_service_config LIMIT 1')
row = cursor.fetchone()
b1_config = json.loads(row[0])
print("=== B1 CONFIG ===")
print(json.dumps(b1_config, indent=2))

# Lấy file B1 từ batch mới nhất
cursor.execute('SELECT files_uploaded FROM reconciliation_logs ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
files = json.loads(row[0])
b1_path = files.get('b1')
if isinstance(b1_path, list):
    b1_path = b1_path[0]

print(f"\n=== Reading B1 with config ===")
print(f"Path: {b1_path}")

# Đọc file bằng hàm read_excel_with_config
df = read_excel_with_config(b1_path, b1_config)
print(f"Columns after config processing: {list(df.columns)}")
print(f"Rows: {len(df)}")

# Kiểm tra cột transaction_remarks
if 'transaction_remarks' in df.columns:
    print(f"\n✅ Column 'transaction_remarks' EXISTS")
    sample = df['transaction_remarks'].head(5).tolist()
    print(f"Sample values:")
    for s in sample:
        key = str(s)[5:17]
        print(f"  '{s}' -> key='{key}'")
else:
    print(f"\n❌ Column 'transaction_remarks' NOT FOUND")
    print(f"Available columns: {list(df.columns)}")

# Load B4
print("\n=== Loading B4 ===")
cursor.execute('SELECT data_b4_config FROM partner_service_config LIMIT 1')
row = cursor.fetchone()
b4_config = json.loads(row[0])
print(f"B4 config: {b4_config}")

mock_file = b4_config.get('mock_file', 'Findata_1906_B4_30_12.csv')
mock_path = f"../storage/mock_data/{mock_file}"

df_b4 = pd.read_csv(mock_path)
df_b4.columns = df_b4.columns.str.lower()
print(f"B4 columns: {list(df_b4.columns)}")

if 'partner_transaction_id' in df_b4.columns:
    print(f"✅ Column 'partner_transaction_id' EXISTS")
    print(f"Sample: {df_b4['partner_transaction_id'].head(5).tolist()}")
else:
    print(f"❌ Column 'partner_transaction_id' NOT FOUND")

# Test matching
print("\n=== Test Matching ===")
if 'transaction_remarks' in df.columns and 'partner_transaction_id' in df_b4.columns:
    # Build key from B1
    b1_keys = df['transaction_remarks'].astype(str).str[5:17]
    print(f"B1 unique keys (first 10): {b1_keys.unique()[:10].tolist()}")
    
    # B4 keys
    b4_keys = df_b4['partner_transaction_id'].astype(str)
    print(f"B4 unique keys (first 10): {b4_keys.unique()[:10].tolist()}")
    
    # Tìm intersection
    common = set(b1_keys.unique()) & set(b4_keys.unique())
    print(f"\n🎯 Common keys: {len(common)}")
    if common:
        print(f"Sample common keys: {list(common)[:10]}")
    else:
        print("⚠️ NO COMMON KEYS FOUND!")
        print("This is why matching returns 0 matches.")

conn.close()
