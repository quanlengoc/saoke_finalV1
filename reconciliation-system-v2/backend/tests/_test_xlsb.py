"""Test XLSB fix"""
from app.services.data_loaders.file_loader import FileDataLoader

loader = FileDataLoader(
    source_name='B3',
    config={'header_row': 1, 'data_start_row': 2, 'sheet_name': ''},
    file_path=r'D:\AnhTM\VH-Works\PTDL - Quản lý Công việc\Report\FINDATAR_1905\Sokhop_saoke\DL test\202601\FILE 1 01-05.01.2026.xlsb',
    batch_id='test'
)
result = loader.load()
print(f'Success: {result.success}')
if result.success:
    print(f'Rows: {len(result.data)}')
    print(f'Columns: {list(result.data.columns)[:10]}')
    print(result.data.head(2))
else:
    print(f'Error: {result.error_message}')
