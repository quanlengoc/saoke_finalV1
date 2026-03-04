"""Check exported CSV files"""
import os, pandas as pd

base = r'D:\AnhTM\VH-Works\PTDL - Quản lý Công việc\Report\FINDATAR_1905\Sokhop_saoke\reconciliation-system-v2\storage\exports'
for root, dirs, files in os.walk(base):
    for f in files:
        if f.endswith('.csv'):
            fp = os.path.join(root, f)
            df = pd.read_csv(fp, nrows=2, encoding='utf-8-sig')
            print(f'{f}: cols={list(df.columns)}')
            if len(df) > 0:
                print(f'  row0: {df.iloc[0].to_dict()}')
            print()
