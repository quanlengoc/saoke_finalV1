# Volume Mounts - Chi tiết Kỹ thuật

## 📌 Giới thiệu About Volumes

Volumes là cơ chế Docker để **lưu trữ dữ liệu bền vững**. Nếu không có volumes, khi container bị xóa hoặc restart, tất cả dữ liệu bên trong container sẽ mất!

## 🎯 Tại sao cần Volumes?

```
❌ KHÔNG có volumes:
  Container restart/remove → ALL DATA LOST!
  
✅ CÓ volumes:
  Container restart/remove → DATA preserved on host
```

## 📁 So sánh 3 loại Storage

| Loại | Nơi lưu | Persistence | Performance | Use Case |
|------|---------|-------------|-----------|----------|
| **Volumes** | Docker managed | ✅✅ Tốt | ✅✅✅ Nhanh | Database, App data |
| **Bind Mounts** | Host directory | ✅✅ Tốt | ✅ Trung bình | Dev, configs |
| **tmpfs** | RAM | ❌ Mất | ✅✅✅ Nhanh | Temp data |

## 🔧 Cấu hình Volumes trong docker-compose.yml

### 1. Named Volumes (Khuyên dùng)

```yaml
volumes:
  backend-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./backend/data

services:
  backend:
    volumes:
      - backend-data:/app/data
```

**Ưu điểm:**
- ✅ Docker quản lý
- ✅ Dễ backup/restore
- ✅ Dễ di chuyển giữa máy
- ✅ Cross-platform

### 2. Bind Mounts (Phát triển)

```yaml
services:
  backend:
    volumes:
      - ./backend/data:/app/data:ro  # read-only
      - ./backend/config.ini:/app/config.ini
```

**Ưu điểm:**
- ✅ Thấy file trực tiếp trên host
- ✅ Dễ edit và debug

### 3. Read-only Volumes

```yaml
volumes:
  - backend-config:/app/config:ro  # Read-only
```

## 📊 Cấu trúc Data trong Project

```
Project Root/
├── backend/
│   ├── data/                    ← Database
│   │   ├── app.db              (SQLite)
│   │   ├── app.db-wal
│   │   └── app.db-shm
│   │
│   ├── logs/                    ← Application logs
│   │   ├── app.log
│   │   ├── api.log
│   │   └── reconciliation.log
│   │
│   ├── storage/                 ← User data
│   │   ├── uploads/             (Files uploaded by users)
│   │   ├── exports/             (Generated reports)
│   │   ├── processed/           (Processed files)
│   │   └── mock_data/           (Test data)
│   │
│   ├── config.ini               ← Config file
│   └── app/
│       └── main.py
│
├── redis/
│   └── data/                    ← Redis persistence
│
└── docker-compose.yml
```

## 🚀 Workflow: Từ Host → Container → Host

```
HOST MACHINE                    DOCKER CONTAINER
┌──────────────────┐            ┌──────────────────┐
│ backend/data/ ──────bind────→ │ /app/data/       │
│ app.db           │            │ app.db           │
│ app.db-wal       │←──────────── │ app.db-wal       │
│ app.db-shm       │            │ app.db-shm       │
└──────────────────┘            └──────────────────┘
      ↑                                  ↑
      │                                  │
   Dữ liệu vẫn ở đây           Ứng dụng làm việc
```

## 💾 Volume Lifecycle

### 1. Create Volume
```bash
docker-compose up -d
# → Tự động tạo volumes (nếu không tồn tại)
```

### 2. Write Data
```bash
# App ghi dữ liệu vào /app/data trong container
# → Data tự động sync sang backend/data trên host
```

### 3. Read Data
```bash
# Host đọc dữ liệu từ backend/data
# → Hoặc container đọc từ /app/data
# → Dữ liệu **luôn đồng bộ**
```

### 4. Persist After Shutdown
```bash
docker-compose down
# → Dữ liệu vẫn lưu ở backend/data

docker-compose up -d
# → Container mở lại, dữ liệu vẫn có
```

## ⚙️ Cấu hình Chi tiết

### Backend Data Volume

```yaml
volumes:
  backend-data:
    driver: local
    driver_opts:
      type: none
      o: bind,uid=1000,gid=1000
      device: ${PWD}/backend/data

services:
  backend:
    volumes:
      - backend-data:/app/data
```

**Giải thích:**
- `type: none` - Host path mount
- `device: ./backend/data` - Thư mục tương ứng trên host
- `uid=1000, gid=1000` - Linux permissions (optional)

### Multiple Volumes

```yaml
services:
  backend:
    volumes:
      # Database
      - backend-data:/app/data
      
      # Logs
      - backend-logs:/app/logs
      
      # Uploads
      - backend-uploads:/app/storage/uploads
      
      # Exports
      - backend-exports:/app/storage/exports
      
      # Config (read-only)
      - ./backend/config.ini:/app/config.ini:ro
      
      # Mock data (read-only)
      - ./backend/storage/mock_data:/app/storage/mock_data:ro
```

## 🔍 Monitoring Volumes

### Xem danh sách volumes
```bash
docker volume ls
docker volume ls --filter name=reconciliation
```

### Thông tin chi tiết
```bash
docker volume inspect reconciliation-system-v2_backend-data
```

### Tìm vị trí trên host
```bash
# Docker Desktop Windows/Mac:
# Volumes stored in: 
# Windows: \\wsl$\docker-desktop-data\version-pack-data\community\docker\volumes
# Mac: ~/Library/Containers/com.docker.docker/Data/vms/0/data/DockerVolumes

# Linux:
# /var/lib/docker/volumes/<volume_name>/_data
```

### Kiểm tra dung lượng
```bash
docker system df
docker system df -v
```

## 🛠️ Các tác vụ Thường gặp

### 1. Backup một volume

```bash
# Tạo backup archive
docker run --rm \
  -v reconciliation-system-v2_backend-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar -czf /backup/backup-$(date +%Y%m%d).tar.gz -C /data .

# Hoặc từ host trực tiếp
tar -czf backup-$(date +%Y%m%d).tar.gz backend/data
```

### 2. Restore từ backup

```bash
docker-compose down

rm -rf backend/data/*

tar -xzf backup-20260305.tar.gz -C backend/data

docker-compose up -d
```

### 3. Copy file từ container sang host

```bash
# Copy một file
docker-compose cp backend:/app/data/app.db ./backend/data/

# Copy thư mục
docker-compose cp backend:/app/logs ./backend/
```

### 4. Clear volume

```bash
# ⚠️ Xóa dữ liệu trong volume
docker-compose down -v
# or
docker volume rm reconciliation-system-v2_backend-data

# Tạo lại
docker-compose up -d
```

### 5. Inspect volume trực tiếp

```bash
# Vào container xem dữ liệu
docker-compose exec backend ls -la /app/data/

# Xem kích thước
docker-compose exec backend du -sh /app/data/
```

## 🚨 Troubleshooting

### Problem: Dữ liệu không sync

```bash
# Kiểm tra volume mount
docker inspect reconciliation-backend | grep -A 20 Mounts

# Kiểm tra permission
ls -la backend/data/
chmod 755 backend/data

# Restart
docker-compose down
docker-compose up -d
```

### Problem: Database locked

```bash
# Xóa lock file
rm -f backend/data/app.db-wal backend/data/app.db-shm

# Restart
docker-compose restart backend
```

### Problem: Volume không tạo được

```bash
# Kiểm tra thư mục tồn tại
mkdir -p backend/data backend/logs backend/storage

# Kiểm tra docker-compose syntax
docker-compose config

# Rebuild
docker-compose down
docker-compose up -d
```

### Problem: Quyền (Permission) denied

```bash
# Linux - thay đổi owner
sudo chown -R $USER:$USER backend/data backend/logs

# Docker - chạy as user
services:
  backend:
    user: "${UID}:${GID}"
```

## 📈 Performance Tips

### 1. Use native volumes (Docker Desktop)
- Windows: WSL 2 backend (tốt hơn Hyper-V)
- Mac: Apple Silicon support

### 2. Optimize mount options
```yaml
volumes:
  backend-data:
    driver: local
    driver_opts:
      type: none
      o: bind,cached  # macOS optimization
      device: ${PWD}/backend/data
```

### 3. Exclude từ sync
```yaml
# .dockerignore
__pycache__
*.pyc
.pytest_cache
node_modules
```

## 🔐 Security

### 1. Read-only volumes
```yaml
volumes:
  - ./config/:/app/config:ro  # Read-only
```

### 2. Named volumes chỉ có quyền cần thiết
```bash
chmod 700 backend/data
```

### 3. Don't store secrets
```yaml
# ❌ KHÔNG làm này:
volumes:
  - ./secrets.txt:/app/secrets.txt

# ✅ Làm cách này:
environment:
  - API_KEY=${API_KEY}  # Từ .env
```

## 📚 Tham khảo Thêm

- [Docker Volumes Documentation](https://docs.docker.com/storage/volumes/)
- [Bind Mounts](https://docs.docker.com/storage/bind-mounts/)
- [tmpfs mounts](https://docs.docker.com/storage/tmpfs/)
- [Storage drivers](https://docs.docker.com/storage/storagedriver/)

---

**Created:** March 5, 2026
