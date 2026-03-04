"""Quick DB health check script"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db')
conn = sqlite3.connect(DB_PATH, timeout=5)

# Journal mode
mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
print(f'Journal mode: {mode}')

# Integrity
integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
print(f'Integrity: {integrity}')

# Table counts
tables = ['users', 'partner_service_config', 'data_source_config', 'workflow_step', 'output_config', 'reconciliation_logs']
print('\n=== TABLE COUNTS ===')
for t in tables:
    try:
        cnt = conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
        print(f'  {t}: {cnt}')
    except Exception as e:
        print(f'  {t}: ERROR - {e}')

# Configs
print('\n=== CONFIGS ===')
for r in conn.execute('SELECT id, partner_code, service_code, is_active FROM partner_service_config').fetchall():
    print(f'  id={r[0]} | {r[1]}/{r[2]} | active={r[3]}')

# Output configs (dynamic column query)
print('\n=== OUTPUT CONFIGS ===')
cols_info = conn.execute('PRAGMA table_info(output_config)').fetchall()
col_names = [c[1] for c in cols_info]
for r in conn.execute(f'SELECT {",".join(col_names)} FROM output_config').fetchall():
    row = dict(zip(col_names, r))
    print(f'  id={row["id"]}, config={row.get("config_id")}, name={row.get("output_name")}, order={row.get("display_order")}')

# Workflow steps
print('\n=== WORKFLOW STEPS ===')
cols_info = conn.execute('PRAGMA table_info(workflow_step)').fetchall()
col_names = [c[1] for c in cols_info]
for s in conn.execute(f'SELECT {",".join(col_names)} FROM workflow_step ORDER BY step_order').fetchall():
    row = dict(zip(col_names, s))
    final = " FINAL" if row.get('is_final_output') else ""
    print(f'  id={row["id"]}, config={row.get("config_id")}, order={row.get("step_order")}, {row.get("left_source")} x {row.get("right_source")} -> {row.get("output_name")}{final}')

# Recent batches
print('\n=== RECENT BATCHES ===')
for r in conn.execute('SELECT batch_id, status, substr(coalesce(error_message,""),1,60), created_at FROM reconciliation_logs ORDER BY created_at DESC LIMIT 5').fetchall():
    print(f'  {r[0]} | {r[1]} | {r[3]} | {r[2]}')

conn.close()
print('\nDB OK')
