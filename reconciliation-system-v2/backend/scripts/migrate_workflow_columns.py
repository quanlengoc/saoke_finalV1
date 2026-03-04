"""
Migration script to add new columns to workflow_step table
"""
from app.core.database import DatabaseManager
from sqlalchemy import text

engine = DatabaseManager.get_app_engine()
with engine.connect() as conn:
    # Check if columns exist
    result = conn.execute(text('PRAGMA table_info(workflow_step)'))
    columns = [row[1] for row in result]
    print('Existing columns:', columns)
    
    # Add missing columns
    if 'output_type' not in columns:
        conn.execute(text("ALTER TABLE workflow_step ADD COLUMN output_type VARCHAR(20) DEFAULT 'intermediate'"))
        print('Added output_type column')
    else:
        print('output_type already exists')
        
    if 'output_columns' not in columns:
        conn.execute(text("ALTER TABLE workflow_step ADD COLUMN output_columns TEXT"))
        print('Added output_columns column')
    else:
        print('output_columns already exists')
        
    conn.commit()
    print('Migration done!')
