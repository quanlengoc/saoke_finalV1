import sqlite3
import json

print("=== DB CŨ (backend/data/app.db) - ĐÂY LÀ DB CẦN GIỮ ===")
conn1 = sqlite3.connect('d:/AnhTM/VH-Works/PTDL - Quản lý Công việc/Report/FINDATAR_1905/Sokhop_saoke/reconciliation-system/backend/data/app.db')
cur1 = conn1.cursor()
cur1.execute('SELECT data_b4_config FROM partner_service_config WHERE partner_code="SACOMBANK"')
row1 = cur1.fetchone()
if row1:
    config1 = json.loads(row1[0])
    print('  mock_file:', config1.get('mock_file'))
    print('  columns:', config1.get('columns', [])[:4])
conn1.close()

print("\n=== DB MỚI (reconciliation-system/data/app.db) - CẦN XÓA ===")
conn2 = sqlite3.connect('d:/AnhTM/VH-Works/PTDL - Quản lý Công việc/Report/FINDATAR_1905/Sokhop_saoke/reconciliation-system/data/app.db')
cur2 = conn2.cursor()
cur2.execute('SELECT data_b4_config FROM partner_service_config WHERE partner_code="SACOMBANK"')
row2 = cur2.fetchone()
if row2:
    config2 = json.loads(row2[0])
    print('  mock_file:', config2.get('mock_file'))
    print('  columns:', config2.get('columns', [])[:4])
conn2.close()
