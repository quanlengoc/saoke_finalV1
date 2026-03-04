"""
Fix SQLite foreign key constraint on config_id column
This recreates the reconciliation_logs table without the broken FK constraint
"""

import sqlite3
from pathlib import Path

def fix_database():
    """Fix the broken FK constraint by recreating the table"""
    
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "app.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    print(f"Connecting to database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Disable foreign keys
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Get current table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reconciliation_logs'")
        result = cursor.fetchone()
        
        if not result:
            print("Table reconciliation_logs not found")
            return
        
        print("Current table schema:")
        print(result[0])
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Create new table without the broken FK
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reconciliation_logs_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id VARCHAR(100) NOT NULL UNIQUE,
                partner_code VARCHAR(50) NOT NULL,
                service_code VARCHAR(50) NOT NULL,
                config_id INTEGER,
                period_from DATE NOT NULL,
                period_to DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'UPLOADING' NOT NULL,
                created_by INTEGER NOT NULL REFERENCES users(id),
                approved_by INTEGER REFERENCES users(id),
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
        
        # Drop old table
        cursor.execute("DROP TABLE reconciliation_logs")
        
        # Rename new table
        cursor.execute("ALTER TABLE reconciliation_logs_new RENAME TO reconciliation_logs")
        
        # Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_reconciliation_logs_batch_id ON reconciliation_logs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_partner_service ON reconciliation_logs(partner_code, service_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_period ON reconciliation_logs(period_from, period_to)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recon_status ON reconciliation_logs(status)")
        
        # Commit
        cursor.execute("COMMIT")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        print("✓ Table recreated successfully without broken FK constraint")
        
        # Verify
        cursor.execute("PRAGMA table_info(reconciliation_logs)")
        columns = cursor.fetchall()
        print("\nNew table columns:")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        cursor.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    fix_database()
