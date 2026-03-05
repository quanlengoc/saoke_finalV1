# Docker Setup Guide

Hướng dẫn cài đặt và chạy Reconciliation System trên Docker với data mount.

## ⚡ Quick Start

### Windows
```bash
# 1. Chạy script
docker-run.bat

# 2. Chọn option "1) Setup and Start"
# 3. Truy cập http://localhost:3000
```

### Linux/Mac
```bash
# 1. Cấp quyền execute
chmod +x docker-run.sh

# 2. Chạy script
./docker-run.sh setup

# 3. Truy cập http://localhost:3000
```

## 📁 Cấu trúc Volume Mounts

Tất cả dữ liệu được mount từ **host machine** vào **container**, nên khi container restart, data vẫn không bị mất:

```
Local Machine (Host)           Docker Container
├── backend/data/          →   /app/data
├── backend/logs/          →   /app/logs
├── backend/storage/       →   /app/storage
│   ├── uploads/          →   /app/storage/uploads
│   ├── exports/          →   /app/storage/exports
│   ├── processed/        →   /app/storage/processed
│   └── mock_data/        →   /app/storage/mock_data
└── redis/data/           →   /data (Redis)
```

**Lợi ích:**
- ✅ Dữ liệu vẫn còn khi restart container
- ✅ Dễ backup và restore
- ✅ Dễ debug (xem file trực tiếp trên host)
- ✅ Performance tốt hơn bind mounts

## 🔧 Cấu hình

### 1. Copy .env file

```bash
cp .env.example .env
```

### 2. Sửa .env

```env
# Chọn database type
DB_TYPE=sqlite              # hoặc oracle

# Nếu dùng Oracle
ORACLE_HOST=your-server.com
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_pass
ORACLE_SID=ORCL

# Mock mode
MOCK_MODE=true              # false nếu có DB thực
```

### 3. Tạo thư mục cần thiết

```bash
mkdir -p backend/data
mkdir -p backend/logs
mkdir -p backend/storage/{uploads,exports,processed,mock_data}
mkdir -p redis/data
```

## 🚀 Chạy Docker

### Option 1: Sử dụng Script (Khuyên dùng)

**Windows:**
```bash
docker-run.bat
```

**Linux/Mac:**
```bash
./docker-run.sh
```

Hoặc chạy trực tiếp:
```bash
./docker-run.sh setup      # Full setup
./docker-run.sh start      # Start only
./docker-run.sh stop       # Stop
./docker-run.sh restart    # Restart
./docker-run.sh logs backend  # View logs
```

### Option 2: Sử dụng Docker Compose trực tiếp

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Remove containers & volumes
docker-compose down -v
```

## 📍 Truy cập Ứng dụng

| Service       | URL                           | Port |
|---------------|-------------------------------|------|
| Frontend      | http://localhost:3000         | 3000 |
| Backend API   | http://localhost:8001         | 8001 |
| API Docs      | http://localhost:8001/docs    | 8001 |
| Redis         | localhost:6379 (internal)     | 6379 |

## 📊 Monitoring & Logs

### Xem logs realtime

```bash
# Backend
docker-compose logs -f backend

# Frontend
docker-compose logs -f frontend

# Redis
docker-compose logs -f redis

# Tất cả
docker-compose logs -f
```

### Kiểm tra trạng thái

```bash
docker-compose ps
```

### Vào container để debug

```bash
# Backend
docker-compose exec backend bash

# Frontend
docker-compose exec frontend sh

# Redis
docker-compose exec redis redis-cli
```

## 💾 Backup & Restore

### Backup Data

```bash
# Linux/Mac
tar -czf reconciliation-backup-$(date +%Y%m%d).tar.gz \
  backend/data \
  backend/logs \
  backend/storage \
  redis/data

# Windows PowerShell
$date = Get-Date -Format "yyyyMMdd"
tar -czf "reconciliation-backup-$date.tar.gz" `
  backend/data, `
  backend/logs, `
  backend/storage, `
  redis/data
```

### Restore Data

```bash
# Backup trước khi restore
docker-compose down -v

# Extract
tar -xzf reconciliation-backup-20260305.tar.gz

# Restart
docker-compose up -d
```

## 🔧 Troubleshooting

### Container không khởi động

```bash
# Kiểm tra logs
docker-compose logs backend

# Rebuild images
docker-compose build --no-cache

# Restart all
docker-compose down
docker-compose up -d
```

### Database error

```bash
# Xóa database cũ
rm -rf backend/data/app.db*

# Restart
docker-compose restart backend
```

### Port đang dùng

```bash
# Windows - Tìm process trên port
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :3000
kill -9 <PID>

# Hoặc thay đổi port trong docker-compose.yml
# ports:
#   - "3001:3000"
```

### Memory/Resource issues

```bash
# Kiểm tra resource usage
docker stats

# Limit resources trong docker-compose.yml
# services:
#   backend:
#     deploy:
#       resources:
#         limits:
#           cpus: '1'
#           memory: 1G
#         reservations:
#           cpus: '0.5'
#           memory: 512M
```

## 🔐 Production Configuration

### Sử dụng Nginx Reverse Proxy

Uncomment section nginx trong `docker-compose.yml`:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf:ro
    - ./ssl:/etc/nginx/ssl:ro
  depends_on:
    - backend
    - frontend
```

### Tạo nginx.conf

```nginx
upstream backend {
    server backend:8001;
}

server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
    }

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSL redirect
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://frontend:3000;
    }

    location /api/ {
        proxy_pass http://backend;
    }
}
```

## ✅ Checklist

- [ ] Docker installed (`docker --version`)
- [ ] Docker Compose installed (`docker-compose --version`)
- [ ] `.env` file created and configured
- [ ] Run `docker-compose up -d`
- [ ] Check `docker-compose ps`
- [ ] Access `http://localhost:3000`
- [ ] Check logs: `docker-compose logs -f backend`
- [ ] Verify database: `backend/data/app.db`

## 📚 Useful Commands

```bash
# View all containers
docker ps -a

# Stop all running containers
docker stop $(docker ps -q)

# Remove all exited containers
docker container prune

# View disk usage
docker system df

# Clean up unused resources
docker system prune -a

# Inspect a service
docker-compose exec backend env

# Ping from one container to another
docker-compose exec frontend ping backend
```

## 📖 More Information

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
- [Vite Docker](https://vitejs.dev/guide/ssr.html#setting-up-the-dev-server)

---

**Last Updated:** March 5, 2026
