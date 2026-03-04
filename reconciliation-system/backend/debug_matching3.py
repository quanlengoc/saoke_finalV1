import sqlite3
import json
import pandas as pd

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Tìm table batches
tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

# Tìm batch table
batch_table = None
for t in tables:
    if 'batch' in t.lower() or 'reconcil' in t.lower():
        batch_table = t
        print(f"Found batch table: {t}")
        cursor.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Columns: {cols}")
        break

# Lấy file B1 config
cursor.execute("SELECT file_b1_config FROM partner_service_config LIMIT 1")
b1_config = json.loads(cursor.fetchone()[0])
print("\n=== B1 CONFIG ===")
print(json.dumps(b1_config, indent=2))

# Tìm file B1 và B4 đường dẫn
# Từ storage
import os

storage_path = os.path.join(os.path.dirname(__file__), '..', 'storage')
print(f"\nStorage path: {os.path.abspath(storage_path)}")

# Tìm file excel trong uploads
uploads_path = os.path.join(storage_path, 'uploads')
if os.path.exists(uploads_path):
    print(f"\nFiles in uploads:")
    for f in os.listdir(uploads_path)[:5]:
        print(f"  {f}")

# Mock data path
mock_path = os.path.join(storage_path, 'mock_data')
if os.path.exists(mock_path):
    print(f"\nFiles in mock_data:")
    for f in os.listdir(mock_path):
        print(f"  {f}")
        
# Đọc B4 mock file để kiểm tra
b4_files = [f for f in os.listdir(mock_path) if 'B4' in f.upper()]
if b4_files:
    b4_path = os.path.join(mock_path, b4_files[0])
    print(f"\n=== B4 FILE: {b4_files[0]} ===")
    df_b4 = pd.read_csv(b4_path)
    print(f"Columns: {list(df_b4.columns)}")
    print(f"Rows: {len(df_b4)}")
    if 'partner_transaction_id' in df_b4.columns:
        print(f"\nSample partner_transaction_id:")
        print(df_b4['partner_transaction_id'].head(10).tolist())
        # Tìm BLX040213120
        matches = df_b4[df_b4['partner_transaction_id'].astype(str).str.contains('BLX040213120', na=False)]
        print(f"\nRows matching BLX040213120: {len(matches)}")
        if not matches.empty:
            print(matches[['partner_transaction_id']].head())

conn.close()
