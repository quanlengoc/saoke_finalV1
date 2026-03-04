"""Check output_config and workflow_step in DB."""
import sqlite3, json

conn = sqlite3.connect('data/app.db')

print("=== OUTPUT CONFIG ===")
for r in conn.execute('SELECT output_name, columns_config FROM output_config WHERE config_id=1'):
    print(f"\n--- {r[0]} ---")
    print(json.dumps(json.loads(r[1]), indent=2, ensure_ascii=False))

print("\n=== WORKFLOW STEPS ===")
for r in conn.execute('SELECT step_order, left_source, right_source, output_name, is_final_output FROM workflow_step WHERE config_id=1 ORDER BY step_order'):
    print(f"Step {r[0]}: {r[1]} ↔ {r[2]} → {r[3]} (final={r[4]})")
