import pandas as pd

# Đọc B1 file - chỉ 100 dòng đầu
b1_path = r"D:\AnhTM\VH-Works\PTDL - Quản lý Công việc\Report\FINDATAR_1905\Sokhop_saoke\reconciliation-system\storage\uploads\SACOMBANK\TOPUP\default\SACOMBANK_TOPUP_20260209_172047\B1_1_Sophu_020059785088_251231063006.xlsx"

print("Reading B1...")
df = pd.read_excel(b1_path, header=11, nrows=100)
print(f'Columns: {list(df.columns)}')
print(f'Rows: {len(df)}')

# Tìm cột có giá trị như BLX...
print(f'\nAll columns with sample:')
for i, col in enumerate(df.columns[:10]):
    sample = str(df[col].iloc[0])[:60] if len(df) > 0 else ''
    print(f'  [{i}] {col}: {sample}')

# Tìm cột có BLX
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

# Đọc B4 file
print("\n=== B4 FILE ===")
b4_path = r"D:\AnhTM\VH-Works\PTDL - Quản lý Công việc\Report\FINDATAR_1905\Sokhop_saoke\reconciliation-system\storage\mock_data\Findata_1906_B4_30_12.csv"
df_b4 = pd.read_csv(b4_path, nrows=100)
print(f'Columns: {list(df_b4.columns)}')

# So sánh cột partner_transaction_id
print(f"\nSample PARTNER_TRANSACTION_ID:")
print(df_b4['PARTNER_TRANSACTION_ID'].head(5).tolist())

# Tìm cột transaction_remarks được mapping
# Config: transaction_remarks -> F
# Trong Excel, F là cột thứ 6 (0-indexed = 5) tính từ A
# Nhưng nếu data bắt đầu từ C, thì F = index 3
print("\n=== MATCHING TEST ===")
# Cột 3 theo config C->F mapping
if 'Nội dung GD' in df.columns:
    remark_col = 'Nội dung GD'
elif len(df.columns) > 3:
    remark_col = df.columns[3]  # Cột F tương đối
else:
    remark_col = df.columns[0]

print(f"Using remark column: {remark_col}")
sample_remarks = df[remark_col].head(5).tolist()
for r in sample_remarks:
    key = str(r)[5:17]
    print(f'  "{r}" -> key="{key}"')
