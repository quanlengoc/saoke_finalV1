import sqlite3
import json
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Lấy batch mới nhất
cursor.execute("SELECT summary_stats, files_uploaded FROM reconciliation_logs WHERE batch_id='SACOMBANK_TOPUP_20260209_173827'")
row = cursor.fetchone()

print("=== BATCH SACOMBANK_TOPUP_20260209_173827 ===")
if row:
    if row[0]:
        stats = json.loads(row[0])
        print("SUMMARY_STATS:")
        print(json.dumps(stats, indent=2))
        
        if 'matching_stats' in stats:
            print("\n✅ matching_stats EXISTS!")
        else:
            print("\n❌ matching_stats NOT FOUND in summary_stats")
    
    if row[1]:
        files = json.loads(row[1])
        print("\nFILES:")
        print(json.dumps(files, indent=2))
else:
    print("Batch not found!")

conn.close()

# Test matching với 100 dòng đầu
print("\n=== TEST MATCHING 100 ROWS ===")
from app.utils.excel_utils import read_excel_with_config

# B1 config
b1_config = {
    "header_row": 12,
    "data_start_row": 13,
    "columns": {
        "transaction_id": "C",
        "transaction_date": "D",
        "value_date": "E",
        "transaction_remarks": "F",
        "debit_amount": "G",
        "credit_amount": "H",
        "running_balance": "I"
    }
}

# Đọc B1 - lấy từ files
conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()
cursor.execute("SELECT files_uploaded FROM reconciliation_logs WHERE batch_id='SACOMBANK_TOPUP_20260209_173827'")
row = cursor.fetchone()
files = json.loads(row[0])
b1_path = files['b1'][0] if isinstance(files['b1'], list) else files['b1']
conn.close()

print(f"B1 path: {b1_path}")

# Đọc 100 dòng đầu
df_b1 = read_excel_with_config(b1_path, b1_config)
df_b1 = df_b1.head(100)
print(f"B1 rows: {len(df_b1)}")
print(f"B1 columns: {list(df_b1.columns)}")

# B1 key = transaction_remarks[5:17]
b1_keys = df_b1['transaction_remarks'].astype(str).str[5:17]
print(f"\nB1 first 5 keys: {b1_keys.head(5).tolist()}")

# Load B4
b4_path = "../storage/mock_data/Findata_1906_B4_30_12.csv"
df_b4 = pd.read_csv(b4_path)
df_b4.columns = df_b4.columns.str.lower()
print(f"B4 rows: {len(df_b4)}")

# B4 key = partner_transaction_id
b4_keys = df_b4['partner_transaction_id'].astype(str)
print(f"B4 first 5 keys: {b4_keys.head(5).tolist()}")

# Tìm match
print("\n=== FINDING MATCHES ===")
b1_key_set = set(b1_keys.tolist())
b4_key_set = set(b4_keys.tolist())

common = b1_key_set & b4_key_set
print(f"Common keys in first 100 B1 rows: {len(common)}")
if common:
    print(f"Sample matches: {list(common)[:10]}")
    
    # Hiển thị dòng match
    for key in list(common)[:3]:
        b1_row = df_b1[b1_keys == key].iloc[0]
        b4_row = df_b4[b4_keys == key].iloc[0]
        print(f"\n  Key: {key}")
        print(f"  B1 transaction_remarks: {b1_row['transaction_remarks'][:60]}...")
        print(f"  B4 partner_transaction_id: {b4_row['partner_transaction_id']}")
else:
    print("No matches found in first 100 rows!")
