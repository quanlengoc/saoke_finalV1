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

print(f"=== Reading B1 (1000 rows only) ===")

# Đọc file trực tiếp với pandas (chỉ 1000 dòng)
header_row = b1_config.get('header_row', 12)
columns_map = b1_config.get('columns', {})

df = pd.read_excel(b1_path, header=header_row-1, nrows=1000)
print(f"Original columns: {list(df.columns)[:5]}...")

# Map columns
from openpyxl.utils import column_index_from_string
def col_to_idx(letter):
    return column_index_from_string(letter.upper()) - 1

selected_cols = {}
for internal_name, col_letter in columns_map.items():
    col_idx = col_to_idx(col_letter)
    if col_idx < len(df.columns):
        original_col = df.columns[col_idx]
        selected_cols[original_col] = internal_name

df = df[list(selected_cols.keys())]
df = df.rename(columns=selected_cols)

print(f"Renamed columns: {list(df.columns)}")

# Kiểm tra cột transaction_remarks
if 'transaction_remarks' in df.columns:
    print(f"\n✅ Column 'transaction_remarks' EXISTS")
    sample = df['transaction_remarks'].head(5).tolist()
    for s in sample:
        key = str(s)[5:17]
        print(f"  '{s[:50]}...' -> key='{key}'")
else:
    print(f"\n❌ Column 'transaction_remarks' NOT FOUND")

# Load B4
print("\n=== Loading B4 (1000 rows) ===")
mock_file = b4_config.get('mock_file', 'Findata_1906_B4_30_12.csv')
mock_path = f"../storage/mock_data/{mock_file}"

df_b4 = pd.read_csv(mock_path, nrows=1000)
df_b4.columns = df_b4.columns.str.lower()
print(f"B4 columns: {list(df_b4.columns)}")

if 'partner_transaction_id' in df_b4.columns:
    print(f"Sample: {df_b4['partner_transaction_id'].head(5).tolist()}")

# Test matching
print("\n=== Test Matching ===")
if 'transaction_remarks' in df.columns and 'partner_transaction_id' in df_b4.columns:
    # Build key from B1
    b1_keys = df['transaction_remarks'].astype(str).str[5:17]
    b1_unique = b1_keys.unique()
    print(f"B1 unique keys (first 10): {b1_unique[:10].tolist()}")
    
    # B4 keys
    b4_keys = df_b4['partner_transaction_id'].astype(str)
    b4_unique = b4_keys.unique()
    print(f"B4 unique keys (first 10): {b4_unique[:10].tolist()}")
    
    # Tìm intersection
    common = set(b1_unique) & set(b4_unique)
    print(f"\n🎯 Common keys in sample: {len(common)}")
    if common:
        print(f"Sample common keys: {list(common)[:10]}")
    else:
        print("⚠️ NO COMMON KEYS in this sample!")
        print("This may be because B1 and B4 are from different dates/transactions.")

conn.close()
