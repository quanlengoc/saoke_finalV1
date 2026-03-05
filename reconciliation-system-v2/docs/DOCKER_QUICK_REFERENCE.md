# 🚀 Docker Complete Setup Guide

Quick reference cho tất cả các lệnh Docker cần thiết.

## ⚡ 5 Bước Setup Nhanh

### Windows
```powershell
# 1. Chạy script
.\docker-run.bat

# 2. Chọn option "1"
# 3. Chờ quá trình hoàn thành

# 4. Truy cập
# Frontend: http://localhost:3000
# API Docs: http://localhost:8001/docs
```

### Linux/Mac
```bash
# 1. Cấp quyền
chmod +x docker-run.sh docker-utils.sh

# 2. Setup
./docker-run.sh setup

# 3. Kiểm tra
docker-compose ps

# 4. Truy cập
# http://localhost:3000
```

## 📁 File Structure

```
reconciliation-system-v2/
├── Dockerfile.backend          ← Backend image
├── Dockerfile.frontend         ← Frontend image
├── docker-compose.yml          ← Orchestration
├── .dockerignore                ← Exclude files
├── .env.example                ← Config template
├── docker-run.sh              ← Main script (Linux/Mac)
├── docker-run.bat             ← Main script (Windows)
├── docker-utils.sh            ← Utilities (Linux/Mac)
├── nginx.conf                 ← Reverse proxy config
│
├── DOCKER_SETUP.md            ← Setup guide
├── VOLUMES_GUIDE.md           ← Storage explanation
│
├── backend/
│   ├── data/                  ← Database (mounted)
│   ├── logs/                  ← Logs (mounted)
│   ├── storage/               ← Files (mounted)
│   ├── app/
│   ├── config.ini
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
└── redis/
    └── data/                  ← Cache (mounted)
```

## 🔑 Key Directories (Everything Mounted!)

| Host | Container | Purpose |
|------|-----------|---------|
| `backend/data/` | `/app/data/` | Database (SQLite) |
| `backend/logs/` | `/app/logs/` | Application logs |
| `backend/storage/uploads/` | `/app/storage/uploads/` | User uploads |
| `backend/storage/exports/` | `/app/storage/exports/` | Generated reports |
| `backend/storage/processed/` | `/app/storage/processed/` | Processed files |
| `backend/storage/mock_data/` | `/app/storage/mock_data/` | Test data |
| `redis/data/` | `/data/` | Redis cache |

## 🎮 Command Reference

### Interactive Menu
```bash
# Windows
docker-run.bat

# Linux/Mac
./docker-run.sh
```

### Direct Commands

#### Start/Stop
```bash
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose restart            # Restart all
docker-compose up -d backend      # Start only backend
docker-compose ps                 # Show status
```

#### Build
```bash
docker-compose build              # Build all images
docker-compose build --no-cache   # Rebuild from scratch
docker-compose build backend      # Build only backend
```

#### Logs
```bash
docker-compose logs -f            # All services
docker-compose logs -f backend    # Backend only
docker-compose logs -f frontend   # Frontend only
docker-compose logs -n 100        # Last 100 lines
```

#### Shell Access
```bash
docker-compose exec backend bash        # Backend shell
docker-compose exec frontend sh         # Frontend shell
docker-compose exec redis redis-cli     # Redis CLI
```

#### Cleanup
```bash
docker-compose down               # Stop containers
docker-compose down -v            # Stop + remove volumes
docker system prune               # Remove unused resources
docker system prune -a            # Full cleanup
```

## 🔧 Configuration

### 1. Create .env file
```bash
cp .env.example .env
```

### 2. Edit .env
```env
# Database
DB_TYPE=sqlite                    # or oracle

# For Oracle
ORACLE_HOST=your-server.com
ORACLE_PORT=1521
ORACLE_USER=your_user
ORACLE_PASSWORD=your_pass
ORACLE_SID=ORCL

# API
VITE_API_URL=http://localhost:8001/api
MOCK_MODE=true                    # false untuk production
```

### 3. Create directories
```bash
mkdir -p backend/{data,logs,storage/{uploads,exports,processed,mock_data}}
mkdir -p redis/data
```

## 🚀 First Time Setup

```bash
# 1. Clone / Navigate
cd reconciliation-system-v2

# 2. Create environment
cp .env.example .env
# Edit .env as needed

# 3. Create directories
mkdir -p backend/{data,logs,storage/{uploads,exports,processed,mock_data}} redis/data

# 4. Build images
docker-compose build

# 5. Start services
docker-compose up -d

# 6. Check status
docker-compose ps

# 7. View logs
docker-compose logs -f backend

# 8. Access
# Frontend: http://localhost:3000
# API: http://localhost:8001
# Docs: http://localhost:8001/docs
```

## 📊 Useful Utilities

### Windows
Use `docker-run.bat` menu for most operations.

### Linux/Mac
Use utilities script:
```bash
chmod +x docker-utils.sh

./docker-utils.sh health              # Check services
./docker-utils.sh backup              # Backup data
./docker-utils.sh restore <backup>    # Restore data
./docker-utils.sh db-info             # Database info
./docker-utils.sh shell backend       # Backend shell
./docker-utils.sh stats               # Resource stats
./docker-utils.sh perf                # Performance stats
```

## 🔍 Debugging

### Check if services are running
```bash
docker-compose ps
# or
docker ps | grep reconciliation
```

### View detailed logs
```bash
docker-compose logs backend --tail=50
```

### Enter container
```bash
docker-compose exec backend bash
# Inside container:
# ls /app/data           # Check database
# tail /app/logs/*       # View logs
# python app/main.py     # Run manually
```

### Check resource usage
```bash
docker stats
# or
docker system df
```

### Inspect volume
```bash
docker volume inspect reconciliation-system-v2_backend-data
```

## 💾 Backup & Restore

### Backup everything
```bash
# Linux/Mac
tar -czf backup-$(date +%Y%m%d).tar.gz \
  backend/data \
  backend/logs \
  backend/storage \
  redis/data

# Windows PowerShell
$date = Get-Date -Format "yyyyMMdd"
tar -czf "backup-$date.tar.gz" `
  backend/data, backend/logs, backend/storage, redis/data
```

### Restore
```bash
# Stop services
docker-compose down

# Remove old data
rm -rf backend/{data,logs,storage} redis/data

# Extract backup
tar -xzf backup-20260305.tar.gz

# Start services
docker-compose up -d
```

## 🌐 Access Points

| Service | URL | Port |
|---------|-----|------|
| Frontend | http://localhost:3000 | 3000 |
| Backend API | http://localhost:8001 | 8001 |
| API Docs | http://localhost:8001/docs | 8001 |
| API ReDoc | http://localhost:8001/redoc | 8001 |
| Redis | localhost:6379 (internal) | 6379 |

## 🚨 Common Issues & Solutions

### Port already in use
```bash
# Linux/Mac
lsof -i :3000
kill -9 <PID>

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
# ports:
#   - "3001:3000"
```

### Database locked
```bash
rm -f backend/data/app.db-wal backend/data/app.db-shm
docker-compose restart backend
```

### Container won't start
```bash
# Check logs
docker-compose logs backend

# Remove and rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check again
docker-compose logs backend
```

### Connection refused
```bash
# Wait for services to start
sleep 10
docker-compose ps

# Or check logs
docker-compose logs
```

### Memory issues (Docker Desktop)
- Increase Docker memory in settings
- Or restart Docker daemon: `docker system prune -a`

## 🔒 Production Checklist

- [ ] Use `DB_TYPE=oracle` (not SQLite)
- [ ] Set strong `SECRET_KEY` in .env
- [ ] Enable SSL/HTTPS in nginx.conf
- [ ] Set `MOCK_MODE=false`
- [ ] Configure proper `CORS_ORIGINS`
- [ ] Set up regular backups
- [ ] Monitor logs and resource usage
- [ ] Use environment-specific .env files
- [ ] Enable health checks in docker-compose
- [ ] Set resource limits (CPU, memory)

## 📚 More Information

- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Detailed setup guide
- [VOLUMES_GUIDE.md](VOLUMES_GUIDE.md) - Storage explanation
- [docker-compose.yml](docker-compose.yml) - Full configuration
- [Official Docker Docs](https://docs.docker.com)

## 🆘 Need Help?

1. Check logs: `docker-compose logs -f`
2. Verify config: `docker-compose config`
3. Rebuild: `docker-compose build --no-cache && docker-compose up -d`
4. Check resources: `docker stats`
5. Read documentation in this folder

---

**Last Updated:** March 5, 2026
**Version:** 1.0
