import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "app.db"
print(f"Connecting to: {db_path}")

if not db_path.exists():
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Disable foreign keys
cursor.execute("PRAGMA foreign_keys = OFF")
cursor.execute("BEGIN TRANSACTION")

# Check if new table already exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reconciliation_logs_new'")
if cursor.fetchone():
    cursor.execute("DROP TABLE reconciliation_logs_new")
    print("Dropped existing reconciliation_logs_new")

# Create new table without broken FK
cursor.execute("""
CREATE TABLE reconciliation_logs_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id VARCHAR(100) NOT NULL UNIQUE,
    partner_code VARCHAR(50) NOT NULL,
    service_code VARCHAR(50) NOT NULL,
    config_id INTEGER,
    period_from DATE NOT NULL,
    period_to DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'UPLOADING' NOT NULL,
    created_by INTEGER NOT NULL,
    approved_by INTEGER,
    approved_at DATETIME,
    step_logs TEXT,
    files_uploaded TEXT,
    file_result_a1 VARCHAR(500),
    file_result_a2 VARCHAR(500),
    file_report VARCHAR(500),
    summary_stats TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
print("Created new table")

# Copy data
cursor.execute("""
INSERT INTO reconciliation_logs_new 
SELECT id, batch_id, partner_code, service_code, config_id,
       period_from, period_to, status, created_by, approved_by,
       approved_at, step_logs, files_uploaded, file_result_a1,
       file_result_a2, file_report, summary_stats, error_message,
       created_at, updated_at
FROM reconciliation_logs
""")
print("Copied data")

# Drop old table
cursor.execute("DROP TABLE reconciliation_logs")
print("Dropped old table")

# Rename new table
cursor.execute("ALTER TABLE reconciliation_logs_new RENAME TO reconciliation_logs")
print("Renamed new table")

# Recreate indexes
cursor.execute("CREATE INDEX IF NOT EXISTS ix_reconciliation_logs_batch_id ON reconciliation_logs(batch_id)")

cursor.execute("COMMIT")
cursor.execute("PRAGMA foreign_keys = ON")
conn.close()

print("Database fixed successfully!")
