"""Reset batch bi treo o trang thai PROCESSING ve FAILED"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db'))
print(f"DB: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

engine = create_engine(f"sqlite:///{db_path}")
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT id, batch_id, status FROM reconciliation_logs WHERE status = 'PROCESSING'"
    )).fetchall()

    if not rows:
        print("Khong co batch nao dang PROCESSING")
    else:
        for row in rows:
            print(f"Reset batch: {row[1]} (id={row[0]})")
            conn.execute(text(
                "UPDATE reconciliation_logs SET status = 'FAILED', error_message = 'Bi gian doan do restart server' WHERE id = :id"
            ), {"id": row[0]})
        conn.commit()
        print(f"Da reset {len(rows)} batch ve FAILED")

    # Also reset batch_run_history
    try:
        runs = conn.execute(text(
            "SELECT id, batch_id FROM batch_run_history WHERE status = 'PROCESSING'"
        )).fetchall()
        if runs:
            for run in runs:
                conn.execute(text(
                    "UPDATE batch_run_history SET status = 'FAILED', error_message = 'Bi gian doan do restart server' WHERE id = :id"
                ), {"id": run[0]})
            conn.commit()
            print(f"Da reset {len(runs)} run history ve FAILED")
    except Exception as e:
        print(f"batch_run_history: {e}")

print("Done!")
