# Reconciliation System V2

Hệ thống đối soát giao dịch tự động giữa sao kê ngân hàng và dữ liệu VNPT Money.
Toàn bộ luồng đối soát được **cấu hình động** từ database — không hardcode.

## Tính năng chính

- **Đối soát động**: Cấu hình N nguồn dữ liệu, N bước matching, N output — không giới hạn
- **Đa loại nguồn dữ liệu**: FILE_UPLOAD, DATABASE, SFTP, API
- **Matching engine**: Key match (expression/custom module) + Amount match (tolerance) + 4 loại JOIN
- **Báo cáo Excel**: Upload template + SQL fill dữ liệu vào sheet/cell/dòng
- **Phê duyệt**: Gửi → Duyệt/Từ chối → Mở khóa
- **Phân quyền**: Admin / User / Approver theo partner + service

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, Pandas, Pydantic 2.x |
| Frontend | React 18, Vite, Zustand, Tailwind CSS, React Query |
| Database | SQLite (dev) / Oracle (production) |
| Auth | JWT (python-jose), bcrypt |
| Infra | Docker Compose, Redis, Nginx |

## Cài đặt & Chạy

### Với Docker (khuyến nghị)

```bash
cp .env.example .env
docker compose build
docker compose up -d
# → Frontend: http://localhost:3000
# → API Docs: http://localhost:8001/docs
```

### Không dùng Docker

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate                           # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

**Tài khoản mặc định:** `admin@example.com` / `admin123`

## Cấu trúc thư mục

```
reconciliation-system-v2/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/v2/endpoints/   # API V2 (dùng chính)
│   │   ├── models/             # SQLAlchemy models
│   │   ├── services/           # Business logic
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── core/               # Config, DB, Security
│   │   └── utils/              # Utilities
│   ├── config.ini              # Cấu hình chính
│   └── requirements.txt
├── frontend/                   # React + Vite
│   └── src/
│       ├── pages/              # Page components
│       ├── components/         # Shared components
│       ├── services/api.js     # Axios client (V2 only)
│       └── stores/             # Zustand stores
├── storage/                    # uploads, exports, templates, mock_data
├── docs/                       # Tài liệu
│   ├── DEPLOY.md               # Hướng dẫn deploy server
│   ├── DOCKER.md               # Hướng dẫn Docker
│   └── features/               # Tài liệu theo tính năng/page
├── docker-compose.yml
└── CLAUDE.md                   # Hướng dẫn cho AI assistant
```

## Tài liệu

| File | Nội dung |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Context cho AI assistant — kiến trúc, quy tắc, API |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploy server, sub-path, Oracle, Nginx |
| [docs/DOCKER.md](docs/DOCKER.md) | Docker setup, lệnh thường dùng, volumes |
| [docs/features/RECONCILIATION.md](docs/features/RECONCILIATION.md) | Trang đối soát + danh sách/chi tiết batch |
| [docs/features/CONFIG.md](docs/features/CONFIG.md) | Trang cấu hình (data sources, workflow, output, report) |
| [docs/features/APPROVALS.md](docs/features/APPROVALS.md) | Trang phê duyệt |
| [docs/features/ADMIN.md](docs/features/ADMIN.md) | Trang quản trị user + mock data |

## License

VNPT Money - Internal Use Only
