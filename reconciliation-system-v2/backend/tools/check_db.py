import sqlite3
import json
import os
import glob

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Get B1B2 config
cursor.execute("SELECT matching_rules_b1b2 FROM partner_service_config LIMIT 1")
row = cursor.fetchone()
config = json.loads(row[0])
print("B1B2 Config:")
print("  Key expression:", config.get('key_expression', 'N/A'))
print("  Rules[0].expression:", config['rules'][0]['expression'] if config.get('rules') else 'N/A')

# Find recent B2 upload
uploads_dir = 'storage/uploads'
b2_files = glob.glob(os.path.join(uploads_dir, '**/B2*.csv'), recursive=True)
if not b2_files:
    b2_files = glob.glob(os.path.join(uploads_dir, '**/*B2*.csv'), recursive=True)
if not b2_files:
    b2_files = glob.glob(os.path.join(uploads_dir, '**/*.csv'), recursive=True)

print(f"\nRecent CSV files in uploads:")
for f in sorted(b2_files, key=os.path.getmtime, reverse=True)[:5]:
    print(f"  {f}")
    
# Check B1 and B2 file configs
cursor.execute("SELECT file_b1_config, file_b2_config FROM partner_service_config LIMIT 1")
row = cursor.fetchone()
b1_config = json.loads(row[0])
b2_config = json.loads(row[1])
print(f"\nB1 config: data_start_row={b1_config.get('data_start_row')}, columns={list(b1_config.get('columns', {}).keys())}")
print(f"B2 config: data_start_row={b2_config.get('data_start_row')}, columns={list(b2_config.get('columns', {}).keys())}")
