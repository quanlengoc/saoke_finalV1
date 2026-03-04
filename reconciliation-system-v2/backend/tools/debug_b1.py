import sqlite3
import json
import pandas as pd

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Lấy batch mới nhất
cursor.execute('SELECT files_uploaded, summary_stats FROM reconciliation_logs ORDER BY id DESC LIMIT 1')
row = cursor.fetchone()
if row:
    files = json.loads(row[0])
    print('Files uploaded:', files)
    
    if row[1]:
        stats = json.loads(row[1])
        print('\n=== SUMMARY STATS ===')
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    b1_path = files.get('b1')
    if b1_path:
        # b1_path là list
        if isinstance(b1_path, list):
            b1_path = b1_path[0]
        print(f'\n=== B1 FILE ===')
        print(f'Path: {b1_path}')
        # Đọc với header row 12 (index 11)
        df = pd.read_excel(b1_path, header=11)
        print(f'Columns: {list(df.columns)}')
        print(f'Rows: {len(df)}')
        
        # Tìm cột F (transaction_remarks theo config)
        # F là cột thứ 6 (index 5) - nhưng config map từ C, nên cần tính lại
        # C=0, D=1, E=2, F=3, G=4, H=5, I=6
        # Nhưng file có thể không bắt đầu từ A
        print(f'\nAll columns with sample:')
        for i, col in enumerate(df.columns[:10]):
            sample = str(df[col].iloc[0])[:50] if len(df) > 0 else ''
            print(f'  [{i}] {col}: {sample}')
        
        # Tìm cột có giá trị như BLX...
        print(f'\nLooking for BLX values...')
        for col in df.columns:
            vals = df[col].astype(str)
            has_blx = vals.str.contains('BLX', na=False).any()
            if has_blx:
                print(f'  Column "{col}" contains BLX')
                sample_blx = vals[vals.str.contains('BLX', na=False)].head(3).tolist()
                print(f'    Sample: {sample_blx}')
                # Test substring
                for v in sample_blx[:2]:
                    print(f'    "{v}"[5:17] = "{v[5:17]}"')

conn.close()
