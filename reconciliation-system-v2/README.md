# Hệ thống Đối soát Giao dịch

Hệ thống đối soát giao dịch giữa sao kê ngân hàng và dữ liệu VNPT Money.

## Cấu trúc thư mục

```
reconciliation-system/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   ├── core/              # Core config, database, security
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   └── utils/             # Utilities
│   ├── requirements.txt
│   └── config.ini
├── frontend/                   # React + Vite Frontend
│   ├── src/
│   │   ├── pages/             # Page components
│   │   ├── layouts/           # Layout components
│   │   ├── services/          # API services
│   │   └── stores/            # Zustand stores
│   └── package.json
└── storage/                    # Data storage
    ├── uploads/               # Uploaded files
    ├── outputs/               # Generated outputs
    ├── templates/             # Report templates
    ├── mock_data/             # Mock B4 data (dev)
    └── sql_templates/         # SQL query templates
```

## Cài đặt

### Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env
copy .env.example .env  # Sửa các giá trị nếu cần

# Chạy server (V2 dùng port 8001)
uvicorn app.main:app --reload --port 8001
```

### Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy dev server
npm run dev
```

## Sử dụng

1. Truy cập `http://localhost:3000`
2. Đăng nhập với tài khoản demo:
   - Admin: `admin@example.com` / `admin123`
   - User: `user@example.com` / `user123`

## Tính năng

### 1. Đối soát
- Upload file sao kê ngân hàng (B1)
- Upload file hoàn tiền (B2) - tùy chọn
- Upload file chi tiết đối tác (B3) - tùy chọn
- Hệ thống tự động query dữ liệu B4 từ VNPT Money
- Chạy đối soát theo luật cấu hình
- Xuất kết quả A1 (khớp), A2 (lệch)

### 2. Phê duyệt
- Gửi batch đã hoàn thành để phê duyệt
- Phê duyệt/Từ chối batch
- Khóa batch đang chờ duyệt

### 3. Báo cáo
- Xem preview kết quả A1/A2
- Tải xuống CSV/Excel
- Tạo báo cáo theo template

### 4. Quản trị (Admin)
- Quản lý users và phân quyền
- Cấu hình đối soát cho từng đối tác/dịch vụ

## Cấu hình đối soát

Mỗi cặp đối tác/dịch vụ có cấu hình riêng:

- **file_b1_config**: Cấu hình đọc file sao kê (header_row, column_mapping)
- **file_b2_config**: Cấu hình đọc file hoàn tiền
- **file_b3_config**: Cấu hình đọc file chi tiết đối tác
- **data_b4_config**: Cấu hình query B4 (db_connection, sql_file, mock_file)
- **matching_b1_b4_config**: Luật khớp B1↔B4
- **matching_b1_b2_config**: Luật khớp B1↔B2
- **matching_a1_b3_config**: Luật khớp A1↔B3
- **output_a1_columns**: Cột output cho A1
- **output_a2_columns**: Cột output cho A2
- **report_template_path**: Đường dẫn template báo cáo
- **report_output_config**: Cấu hình điền dữ liệu vào template

## Môi trường

### Development (SQLite + Mock data)
```env
DB_TYPE=sqlite
MOCK_MODE=true
```

### Production (Oracle)
```env
DB_TYPE=oracle
MOCK_MODE=false
```

## API Documentation

Sau khi chạy backend, truy cập:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## License

VNPT Money - Internal Use Only
