import sqlite3
import json
import pandas as pd

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Liệt kê tables
print("=== TABLES ===")
tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(tables)

# Lấy config - tìm đúng tên table
for table in tables:
    if 'config' in table.lower():
        print(f"\n=== TABLE: {table} ===")
        cursor.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"Row length: {len(row)}")
            # Tìm cột chứa JSON
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cursor.fetchall()]
            print(f"Columns: {cols}")
            # In từng cột
            for i, col in enumerate(cols):
                val = row[i]
                if isinstance(val, str) and val.startswith('{'):
                    try:
                        parsed = json.loads(val)
                        print(f"\n{col} (JSON):")
                        # In matching_rules nếu có
                        if 'matching_rules' in parsed:
                            print("matching_rules.b1_b4:", json.dumps(parsed['matching_rules'].get('b1_b4', {}), indent=2))
                        if 'key_match' in parsed:
                            print("key_match:", json.dumps(parsed['key_match'], indent=2))
                    except:
                        pass

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
    # Tìm cột có chứa 'nội dung' hoặc 'remark'
    for col in df_b1.columns:
        if 'nội dung' in str(col).lower() or 'remark' in str(col).lower() or 'gd' in str(col).lower():
            print(f"\nColumn '{col}' sample values:")
            print(df_b1[col].head(5).tolist())
except Exception as e:
    print(f"Error: {e}")

print("\n=== SAMPLE B4 DATA ===")
try:
    df_b4 = pd.read_csv(batch[2])
    print(f"Columns: {list(df_b4.columns)}")
    # Tìm cột partner_transaction_id
    for col in df_b4.columns:
        if 'partner' in str(col).lower() or 'transaction' in str(col).lower():
            print(f"\nColumn '{col}' sample values:")
            print(df_b4[col].head(5).tolist())
except Exception as e:
    print(f"Error: {e}")
