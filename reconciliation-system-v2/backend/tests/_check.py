import sqlite3, json

conn = sqlite3.connect('data/app.db')
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cur.fetchall()])

# Check data source configs 
try:
    cur.execute("SELECT source_name, file_config, db_config FROM data_source_config WHERE config_id = 1 ORDER BY display_order")
    for row in cur.fetchall():
        print(f"\n=== {row[0]} ===")
        if row[1]:
            try:
                cfg = json.loads(row[1])
                print(f"  file_config: {json.dumps(cfg, indent=2)}")
            except:
                print(f"  file_config: {row[1]}")
except Exception as e:
    print(f"Error querying data_source_config: {e}")

# Check reconciliation_logs
try:
    cur.execute("SELECT batch_id, status, error_message, files_uploaded FROM reconciliation_logs ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    print(f"\n=== Batches ({len(rows)}) ===")
    for r in rows:
        err = r[2][:120] if r[2] else None
        files = r[3][:200] if r[3] else None
        print(f"  {r[0]} | {r[1]} | err={err}")
        print(f"    files={files}")
except Exception as e:
    print(f"Error querying reconciliation_logs: {e}")

conn.close()
