import pandas as pd
import os
import glob
import sqlite3
import json

# Get B2 file config
conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()
cursor.execute('SELECT file_b2_config, matching_rules_b1b2 FROM partner_service_config LIMIT 1')
row = cursor.fetchone()
b2_config = json.loads(row[0])
b1b2_rules = json.loads(row[1])

print("=== B2 Config ===")
print(f"header_row: {b2_config.get('header_row')}")
print(f"data_start_row: {b2_config.get('data_start_row')}")
print(f"columns: {b2_config.get('columns')}")

print("\n=== B1B2 Rules ===")
print(f"Key expression: {b1b2_rules.get('rules', [{}])[0].get('expression', 'N/A')}")

# Tìm file A1 mới nhất
a1_path = 'd:/AnhTM/VH-Works/PTDL - Quản lý Công việc/Report/FINDATAR_1905/Sokhop_saoke/reconciliation-system/storage/exports/SACOMBANK/TOPUP/default/SACOMBANK_TOPUP_20260209_220639/A1_SACOMBANK_TOPUP_20260209_220639.csv'

df = pd.read_csv(a1_path, encoding='utf-8')

# Tạo match key từ transaction_remarks
df['_match_key'] = df['transaction_remarks'].astype(str).str[5:17]
print('\n=== Sample B1 match keys (first 10) ===')
print(df['_match_key'].head(10).tolist())

# Check step logs for this batch
cursor.execute('SELECT step_logs FROM reconciliation_logs WHERE batch_id = ?', ('SACOMBANK_TOPUP_20260209_220639',))
row = cursor.fetchone()
logs = json.loads(row[0]) if row and row[0] else []
print("\n=== Step Logs ===")
for l in logs:
    print(f"{l.get('step')}: {l.get('status')} - {l.get('message')}")
