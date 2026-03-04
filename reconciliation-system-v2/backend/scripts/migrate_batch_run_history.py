"""
Migration script: Add batch_run_history table & migrate step_logs to files.

What this does:
1. Creates batch_run_history table
2. For each existing reconciliation_logs row that has step_logs JSON:
   - Writes the JSON to a file: logs/batches/{batch_id}/run_1.json
   - Updates step_logs column to the file path
   - Inserts a row into batch_run_history

Run: python -m scripts.migrate_batch_run_history
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime


def migrate():
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "app.db"
    logs_base = backend_dir / "logs" / "batches"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Database will be created when you start the app for the first time.")
        return

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # ── 1. Create batch_run_history table ──────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_run_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id      VARCHAR(100) NOT NULL REFERENCES reconciliation_logs(batch_id),
                run_number    INTEGER NOT NULL,
                triggered_by  VARCHAR(20) NOT NULL DEFAULT 'initial',
                status        VARCHAR(20) NOT NULL DEFAULT 'PROCESSING',
                started_at    DATETIME,
                completed_at  DATETIME,
                duration_seconds REAL,
                log_file_path VARCHAR(500),
                summary_stats TEXT,
                file_results  TEXT,
                error_message TEXT
            )
        """)
        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_history_batch
            ON batch_run_history(batch_id, run_number)
        """)
        conn.commit()
        print("✓ Created batch_run_history table")

        # ── 2. Migrate existing step_logs to files ─────────────────────
        cursor.execute("""
            SELECT id, batch_id, status, step_logs, summary_stats,
                   file_results, error_message, created_at, updated_at
            FROM reconciliation_logs
            WHERE step_logs IS NOT NULL AND step_logs != ''
        """)
        rows = cursor.fetchall()
        migrated = 0
        skipped = 0

        for row in rows:
            batch_id = row["batch_id"]
            step_logs_raw = row["step_logs"]

            # Skip if already migrated (step_logs is a file path, not JSON array)
            if step_logs_raw and not step_logs_raw.strip().startswith("["):
                skipped += 1
                continue

            # Parse JSON
            try:
                logs_data = json.loads(step_logs_raw)
            except (json.JSONDecodeError, TypeError):
                skipped += 1
                continue

            if not isinstance(logs_data, list):
                skipped += 1
                continue

            # Write to file
            batch_log_dir = logs_base / batch_id
            batch_log_dir.mkdir(parents=True, exist_ok=True)
            log_file = batch_log_dir / "run_1.json"
            log_file.write_text(json.dumps(logs_data, ensure_ascii=False, indent=2), encoding="utf-8")

            # Relative path from backend dir
            rel_path = str(log_file.relative_to(backend_dir)).replace("\\", "/")

            # Update step_logs to file path
            cursor.execute(
                "UPDATE reconciliation_logs SET step_logs = ? WHERE id = ?",
                (rel_path, row["id"])
            )

            # Check if run_history already exists for this batch
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM batch_run_history WHERE batch_id = ?",
                (batch_id,)
            )
            existing_count = cursor.fetchone()["cnt"]
            if existing_count == 0:
                # Determine timing from logs
                started_at = row["created_at"]
                completed_at = row["updated_at"]
                duration = None
                if started_at and completed_at:
                    try:
                        t1 = datetime.fromisoformat(started_at)
                        t2 = datetime.fromisoformat(completed_at)
                        duration = (t2 - t1).total_seconds()
                    except:
                        pass

                status = row["status"]
                # Map batch status to run status
                run_status = status
                if status in ("COMPLETED", "APPROVED"):
                    run_status = "COMPLETED"
                elif status in ("FAILED", "ERROR"):
                    run_status = "FAILED"
                elif status == "PROCESSING":
                    run_status = "PROCESSING"
                else:
                    run_status = "COMPLETED"  # default for old data

                cursor.execute("""
                    INSERT INTO batch_run_history
                        (batch_id, run_number, triggered_by, status,
                         started_at, completed_at, duration_seconds,
                         log_file_path, summary_stats, file_results, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, 1, "initial", run_status,
                    started_at, completed_at, duration,
                    rel_path, row["summary_stats"], row["file_results"],
                    row["error_message"]
                ))

            migrated += 1

        conn.commit()
        print(f"✓ Migrated {migrated} batches (step_logs → files), skipped {skipped}")

        # ── 3. Migrate files_uploaded to compact format ─────────────────
        cursor.execute("""
            SELECT id, batch_id, partner_code, files_uploaded
            FROM reconciliation_logs
            WHERE files_uploaded IS NOT NULL AND files_uploaded != ''
        """)
        rows = cursor.fetchall()
        migrated_fu = 0

        for row in rows:
            raw = row["files_uploaded"]
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            # Skip if already in new format
            if "batch_folder" in data:
                continue

            # Old format: {"B1": ["/full/path/file1.xlsx", ...], ...}
            if not isinstance(data, dict):
                continue

            # Detect batch_folder from first file path
            batch_folder = ""
            sources_info = {}
            for source_name, file_list in data.items():
                if isinstance(file_list, list) and file_list:
                    # Extract folder info
                    first_file = file_list[0]
                    source_dir = os.path.dirname(first_file)
                    source_folder = os.path.basename(source_dir)
                    if not batch_folder:
                        # Walk up one level: .../uploads/PARTNER/batch_folder/source_name/file
                        batch_folder = os.path.basename(os.path.dirname(source_dir))
                    sources_info[source_name] = {
                        "folder": source_folder,
                        "file_count": len(file_list)
                    }
                else:
                    sources_info[source_name] = {
                        "folder": source_name.lower(),
                        "file_count": 0
                    }

            new_data = {
                "batch_folder": batch_folder,
                "sources": sources_info
            }
            cursor.execute(
                "UPDATE reconciliation_logs SET files_uploaded = ? WHERE id = ?",
                (json.dumps(new_data, ensure_ascii=False), row["id"])
            )
            migrated_fu += 1

        conn.commit()
        print(f"✓ Migrated {migrated_fu} batches (files_uploaded → compact format)")

        print("\n✓ Migration complete!")

    except Exception as e:
        print(f"✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
