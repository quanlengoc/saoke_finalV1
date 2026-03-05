#!/bin/bash
# ============================================================
# Utility Script for Docker Management
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

# 1. Health check
health_check() {
    print_header "Checking Services Health"
    
    echo "Frontend:"
    if curl -s http://localhost:3000 > /dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
    
    echo -e "\nBackend:"
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
    
    echo -e "\nRedis:"
    if docker-compose exec redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
}

# 2. Database backup
backup_database() {
    print_header "Backing up Database"
    
    local backup_name="reconciliation-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p backups
    
    echo "Creating backup..."
    tar -czf "backups/${backup_name}.tar.gz" \
        backend/data \
        backend/logs \
        backend/storage \
        redis/data 2>/dev/null || true
    
    echo -e "${GREEN}✓ Backup created: backups/${backup_name}.tar.gz${NC}"
}

# 3. Database restore
restore_database() {
    if [ -z "$1" ]; then
        print_header "Available Backups"
        ls -lh backups/ 2>/dev/null || echo "No backups found"
        return
    fi
    
    print_header "Restoring Database"
    
    if [ ! -f "backups/$1" ]; then
        echo -e "${RED}✗ Backup not found: $1${NC}"
        return
    fi
    
    echo -e "${YELLOW}⚠ Stopping services...${NC}"
    docker-compose down
    
    echo "Removing old data..."
    rm -rf backend/data backend/logs backend/storage redis/data
    
    echo "Extracting backup..."
    tar -xzf "backups/$1"
    
    echo "Starting services..."
    docker-compose up -d
    
    echo -e "${GREEN}✓ Restore complete${NC}"
}

# 4. Database info
db_info() {
    print_header "Database Information"
    
    if [ -f "backend/data/app.db" ]; then
        echo "Database size:"
        ls -lh backend/data/app.db | awk '{print "  " $5}'
        
        echo -e "\nDatabase tables:"
        docker-compose exec backend sqlite3 data/app.db ".tables" 2>/dev/null || echo "  SQLite not available"
    else
        echo "Database not found at backend/data/app.db"
    fi
}

# 5. Container shell
shell_access() {
    if [ -z "$1" ]; then
        echo "Usage: $0 shell <service>"
        echo "Services: backend, frontend, redis"
        return
    fi
    
    docker-compose exec "$1" bash || docker-compose exec "$1" sh
}

# 6. View real-time stats
stats() {
    print_header "Docker Container Stats"
    docker stats
}

# 7. Clean up
clean_all() {
    print_header "Cleaning Up"
    
    echo -e "${YELLOW}⚠ This will remove all containers, images, and volumes${NC}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        docker-compose down -v
        docker image prune -f
        echo -e "${GREEN}✓ Cleanup complete${NC}"
    fi
}

# 8. View network
network_info() {
    print_header "Docker Network Information"
    
    echo "Running containers:"
    docker-compose ps
    
    echo -e "\nNetwork details:"
    docker network inspect reconciliation-system-v2_reconciliation-network 2>/dev/null || echo "Network not found"
}

# 9. File sync (if needed)
sync_files() {
    print_header "File Synchronization"
    
    echo "Copying files from container to host..."
    
    # Backend logs
    docker-compose exec backend cp -r logs/* /app/logs/ 2>/dev/null || true
    
    # Backend data
    docker cp reconciliation-backend:/app/data ./backend/ 2>/dev/null || true
    
    echo -e "${GREEN}✓ Sync complete${NC}"
}

# 10. Performance stats
performance_stats() {
    print_header "Performance Statistics"
    
    echo "Docker system usage:"
    docker system df
    
    echo -e "\nDisk space:"
    du -sh backend/data backend/logs backend/storage redis/data 2>/dev/null || echo "Directories not found"
}

# Main
case "$1" in
    health)
        health_check
        ;;
    backup)
        backup_database
        ;;
    restore)
        restore_database "$2"
        ;;
    db-info)
        db_info
        ;;
    shell)
        shell_access "$2"
        ;;
    stats)
        stats
        ;;
    clean)
        clean_all
        ;;
    network)
        network_info
        ;;
    sync)
        sync_files
        ;;
    perf)
        performance_stats
        ;;
    *)
        echo "Docker Utilities"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  health              - Check services health"
        echo "  backup              - Backup database and data"
        echo "  restore [backup]    - Restore from backup"
        echo "  db-info             - Show database information"
        echo "  shell <service>     - Enter container shell"
        echo "  stats               - Show container stats"
        echo "  clean               - Clean up containers and images"
        echo "  network             - Show network information"
        echo "  sync                - Sync files from container"
        echo "  perf                - Show performance stats"
        echo ""
        echo "Examples:"
        echo "  $0 health"
        echo "  $0 backup"
        echo "  $0 restore reconciliation-backup-20260305-120000.tar.gz"
        echo "  $0 shell backend"
        ;;
esac
