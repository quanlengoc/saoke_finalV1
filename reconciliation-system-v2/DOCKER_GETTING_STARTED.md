# 🚀 Quick Start Guide

Tất cả các setup scripts và docs được organize gọn gàng vào các thư mục:

```
├── docker/                 ← Dockerfile, nginx config
├── scripts/                ← Setup & utility scripts
└── docs/                   ← Documentation
```

## ⚡ Quick Commands

### Windows
```bash
# Run setup script
.\scripts\docker-run.bat
```

### Linux/Mac
```bash
# Make executable
chmod +x scripts/docker-run.sh scripts/docker-utils.sh

# Run setup
./scripts/docker-run.sh setup

# Or other commands
./scripts/docker-run.sh start
./scripts/docker-run.sh stop
./scripts/docker-utils.sh health
```

---

## 📁 Folder Structure

| Folder | Purpose |
|--------|---------|
| **docker/** | All Docker-related files (Dockerfiles, nginx.conf) |
| **scripts/** | Automation scripts (setup, utilities) |
| **docs/** | Complete documentation & guides |
| **backend/** | Python FastAPI application |
| **frontend/** | React/Vite web application |
| **redis/** | Redis cache data (mounted volume) |

---

## 📚 Documentation

### Getting Started
- 👉 **[DOCKER_QUICK_REFERENCE.md](docs/DOCKER_QUICK_REFERENCE.md)** - Cheat sheet lệnh
- 📖 **[DOCKER_SETUP.md](docs/DOCKER_SETUP.md)** - Chi tiết setup
- 💾 **[VOLUMES_GUIDE.md](docs/VOLUMES_GUIDE.md)** - Volume mounts & data persistence

---

## 🎯 Common Tasks

### Setup for first time
```bash
# Windows
.\scripts\docker-run.bat
# Choose option 1

# Linux/Mac
./scripts/docker-run.sh setup
```

### Start services
```bash
docker-compose up -d
```

### View logs
```bash
docker-compose logs -f backend
```

### Backup data
```bash
# Windows PowerShell
$date = Get-Date -Format "yyyyMMdd"
tar -czf "backup-$date.tar.gz" backend/data, backend/logs, backend/storage, redis/data

# Linux/Mac
./scripts/docker-utils.sh backup
```

### Stop services
```bash
docker-compose down
```

---

## 🌐 Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |

---

## 🆘 Need Help?

1. Check [docs/DOCKER_QUICK_REFERENCE.md](docs/DOCKER_QUICK_REFERENCE.md) for all commands
2. View logs: `docker-compose logs -f backend`
3. Rebuild: `docker-compose build --no-cache && docker-compose up -d`

---

**Created:** March 5, 2026
