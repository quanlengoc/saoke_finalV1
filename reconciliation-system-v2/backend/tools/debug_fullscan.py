import sqlite3
import json
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Lấy config B1
cursor.execute('SELECT file_b1_config, data_b4_config FROM partner_service_config LIMIT 1')
row = cursor.fetchone()
b1_config = json.loads(row[0])
b4_config = json.loads(row[1])

# Lấy file B1 từ batch mới nhất
cursor.execute('SELECT files_uploaded FROM reconciliation_logs ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
files = json.loads(row[0])
b1_path = files.get('b1')
if isinstance(b1_path, list):
    b1_path = b1_path[0]

print(f"=== Scanning FULL B1 for unique keys ===")

# Đọc file trực tiếp với pandas - CHỈ CỘT F (index 5 từ C=2)
# Cột F = index 5 (vì bắt đầu từ C=2, D=3, E=4, F=5)
header_row = b1_config.get('header_row', 12)
df = pd.read_excel(b1_path, header=header_row-1, usecols=[5])  # Only column F
print(f"B1 rows: {len(df)}")

# Extract key
col_name = df.columns[0]
b1_keys = df[col_name].astype(str).str[5:17]
b1_unique = set(b1_keys.unique())
print(f"B1 unique keys count: {len(b1_unique)}")
print(f"B1 key range: {sorted(b1_unique)[:5]} ... {sorted(b1_unique)[-5:]}")

# Load FULL B4
print("\n=== Scanning FULL B4 for unique keys ===")
mock_file = b4_config.get('mock_file', 'Findata_1906_B4_30_12.csv')
mock_path = f"../storage/mock_data/{mock_file}"

df_b4 = pd.read_csv(mock_path, usecols=['PARTNER_TRANSACTION_ID'])
df_b4.columns = df_b4.columns.str.lower()
print(f"B4 rows: {len(df_b4)}")

b4_keys = df_b4['partner_transaction_id'].astype(str)
b4_unique = set(b4_keys.unique())
print(f"B4 unique keys count: {len(b4_unique)}")
print(f"B4 key range: {sorted(b4_unique)[:5]} ... {sorted(b4_unique)[-5:]}")

# Tìm intersection
print("\n=== Finding Common Keys ===")
common = b1_unique & b4_unique
print(f"🎯 COMMON KEYS: {len(common)}")

if common:
    print(f"Sample common keys: {list(common)[:20]}")
else:
    print("⚠️ NO COMMON KEYS AT ALL!")
    print("The B1 file and B4 mock file have completely different transaction IDs.")
    print("This is why matching returns 0 matches.")
    print("\nPossible causes:")
    print("1. B4 mock file is from a different date/period than B1")
    print("2. B4 mock file is for a different partner/service")
    print("3. The substring config [5:17] is not correct for this data")

conn.close()
