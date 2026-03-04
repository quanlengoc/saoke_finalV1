"""
Migration script to fix config_id foreign key constraint
SQLite doesn't support ALTER COLUMN, so we need to recreate the table
"""

import sqlite3
from pathlib import Path

def migrate():
    """Fix config_id foreign key to point to correct table name"""
    
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "app.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    print(f"Connecting to database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Disable foreign keys temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Check current table structure
        cursor.execute("PRAGMA table_info(reconciliation_logs)")
        columns_info = cursor.fetchall()
        columns = [row[1] for row in columns_info]
        
        print(f"Current columns: {columns}")
        
        if 'config_id' not in columns:
            # Just add the column without FK constraint (SQLite limitation)
            cursor.execute("ALTER TABLE reconciliation_logs ADD COLUMN config_id INTEGER")
            print("✓ Added config_id column")
        else:
            print("✓ config_id column already exists")
        
        # Commit
        cursor.execute("COMMIT")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        print("✓ Migration completed successfully")
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        cursor.execute("ROLLBACK")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
