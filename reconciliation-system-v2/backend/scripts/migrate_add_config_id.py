"""
Migration script to add config_id column to reconciliation_logs table
Run this script once to add the column to existing database
"""

import sqlite3
import os
from pathlib import Path

def migrate():
    """Add config_id column to reconciliation_logs table"""
    
    # Get database path from config (relative to backend folder)
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "app.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Database will be created when you start the app for the first time.")
        return
    
    print(f"Connecting to database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(reconciliation_logs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'config_id' not in columns:
            # Add the column without foreign key (SQLite limitation)
            cursor.execute("""
                ALTER TABLE reconciliation_logs 
                ADD COLUMN config_id INTEGER
            """)
            conn.commit()
            print("✓ Successfully added 'config_id' column to reconciliation_logs table")
        else:
            print("✓ Column 'config_id' already exists in reconciliation_logs table")
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
