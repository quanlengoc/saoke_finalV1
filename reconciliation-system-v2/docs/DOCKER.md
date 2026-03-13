# Docker - Hướng dẫn sử dụng

## Quick Start

```bash
# 1. Tạo .env
cp .env.example .env

# 2. Tạo thư mục cần thiết
mkdir -p backend/{data,logs} redis/data
mkdir -p backend/storage/{uploads,exports,processed,mock_data,templates,sql_templates,custom_matching}

# 3. Build & chạy
docker compose build
docker compose up -d

# 4. Kiểm tra
docker compose ps
```

**Truy cập:**

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8001 |
| API Docs (Swagger) | http://localhost:8001/docs |

**Tài khoản mặc định:** `admin@example.com` / `admin123`

---

## Cấu hình `.env`

```ini
DB_TYPE=sqlite                # sqlite (dev) hoặc oracle (prod)
MOCK_MODE=true                # true = dùng mock data, false = kết nối DB thật

# Oracle (khi DB_TYPE=oracle)
ORACLE_HOST=your-server.com
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_pass
ORACLE_SID=ORCL

# Security
SECRET_KEY=your-super-secret-key    # Đổi cho production!
CORS_ORIGINS=http://localhost:3000,http://localhost:8001
```

---

## Lệnh thường dùng

```bash
# Start / Stop
docker compose up -d              # Chạy tất cả
docker compose down               # Dừng tất cả
docker compose restart backend    # Restart 1 service

# Logs
docker compose logs -f backend    # Log backend realtime
docker compose logs -f frontend   # Log frontend realtime
docker compose logs --tail=100    # 100 dòng cuối

# Build lại sau khi sửa code
docker compose build backend && docker compose up -d backend

# Vào shell container
docker compose exec backend bash
docker compose exec frontend sh
docker compose exec redis redis-cli

# Kiểm tra resource
docker stats
docker system df
```

---

## Volume Mounts

Dữ liệu được mount từ host vào container — không mất khi restart/xóa container:

```
Host (máy local)                  Container
backend/data/              →      /app/data/          (SQLite DB)
backend/logs/              →      /app/logs/          (Log files)
backend/storage/uploads/   →      /app/storage/uploads/
backend/storage/exports/   →      /app/storage/exports/
backend/storage/processed/ →      /app/storage/processed/
backend/storage/mock_data/ →      /app/storage/mock_data/
backend/config.ini         →      /app/config.ini     (read-only)
redis/data/                →      /data/              (Redis cache)
```

---

## Backup & Restore

```bash
# Backup
tar -czf backup-$(date +%Y%m%d).tar.gz \
  backend/data backend/logs backend/storage redis/data

# Restore
docker compose down
tar -xzf backup-20260305.tar.gz
docker compose up -d
```

---

## Troubleshooting

| Vấn đề | Giải pháp |
|---|---|
| Container không start | `docker compose logs backend` để xem lỗi |
| Port đang bị chiếm | `lsof -i :3000` (Linux) hoặc `netstat -ano \| findstr :3000` (Windows) |
| Database locked | `rm -f backend/data/app.db-wal backend/data/app.db-shm` rồi restart |
| Build lỗi | `docker compose build --no-cache` để build sạch |
| Dữ liệu không sync | Kiểm tra thư mục tồn tại + permission: `ls -la backend/data/` |

> Hướng dẫn deploy production (Nginx, Oracle, sub-path) → xem [DEPLOY.md](DEPLOY.md)
