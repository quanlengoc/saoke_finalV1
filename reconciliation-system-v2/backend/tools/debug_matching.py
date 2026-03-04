import sqlite3
import json
import pandas as pd

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Lấy config
cursor.execute("SELECT config_json FROM partner_configs WHERE partner_code = 'SACOMBANK' AND service_type = 'TOPUP'")
row = cursor.fetchone()
if row:
    config = json.loads(row[0])
    print("=== MATCHING RULES B1_B4 ===")
    print(json.dumps(config.get('matching_rules', {}).get('b1_b4', {}), indent=2, ensure_ascii=False))
    
    print("\n=== KEY MATCH CONFIG ===")
    print(json.dumps(config.get('key_match', {}), indent=2, ensure_ascii=False))

# Lấy batch mới nhất
cursor.execute("SELECT batch_id, file_b1, file_b4, summary_stats FROM reconciliation_batches ORDER BY id DESC LIMIT 1")
batch = cursor.fetchone()
print(f"\n=== BATCH MỚI NHẤT ===")
print(f"Batch ID: {batch[0]}")
print(f"File B1: {batch[1]}")
print(f"File B4: {batch[2]}")

if batch[3]:
    stats = json.loads(batch[3])
    print(f"\n=== SUMMARY STATS ===")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

conn.close()

# Thử đọc sample data
print("\n=== SAMPLE B1 DATA ===")
try:
    df_b1 = pd.read_excel(batch[1], header=11)  # header_row = 12 -> index 11
    print(f"Columns: {list(df_b1.columns)}")
    print(f"Sample transaction_remarks:")
    if 'transaction_remarks' in df_b1.columns:
        print(df_b1['transaction_remarks'].head(10))
    elif 'Nội dung GD' in df_b1.columns:
        print("Column 'Nội dung GD' found:")
        print(df_b1['Nội dung GD'].head(10))
except Exception as e:
    print(f"Error: {e}")

print("\n=== SAMPLE B4 DATA ===")
try:
    df_b4 = pd.read_csv(batch[2])
    print(f"Columns: {list(df_b4.columns)}")
    print(f"Sample partner_transaction_id:")
    if 'partner_transaction_id' in df_b4.columns:
        print(df_b4['partner_transaction_id'].head(10))
except Exception as e:
    print(f"Error: {e}")
