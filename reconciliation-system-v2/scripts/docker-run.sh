#!/bin/bash
# ============================================================
# Docker Setup and Run Script for Reconciliation System
# ============================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if Docker is installed
check_docker() {
    print_header "Checking Docker Installation"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        echo "Please install Docker from https://www.docker.com"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed!"
        echo "Please install Docker Compose from https://docs.docker.com/compose/install"
        exit 1
    fi
    
    print_success "Docker is installed: $(docker --version)"
    print_success "Docker Compose is installed: $(docker-compose --version)"
}

# Create directories
create_directories() {
    print_header "Creating Directories"
    
    mkdir -p backend/data
    mkdir -p backend/logs
    mkdir -p backend/storage/uploads
    mkdir -p backend/storage/exports
    mkdir -p backend/storage/processed
    mkdir -p backend/storage/mock_data
    mkdir -p redis/data
    
    print_success "All directories created"
}

# Setup environment file
setup_env() {
    print_header "Setting up Environment File"
    
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success ".env file created from .env.example"
            print_info "Please edit .env file with your configuration"
        else
            print_error ".env.example not found!"
            exit 1
        fi
    else
        print_info ".env file already exists"
    fi
}

# Build Docker images
build_images() {
    print_header "Building Docker Images"
    
    print_info "Building backend image..."
    docker-compose build backend
    print_success "Backend image built"
    
    print_info "Building frontend image..."
    docker-compose build frontend
    print_success "Frontend image built"
}

# Start services
start_services() {
    print_header "Starting Services"
    
    print_info "Starting all services..."
    docker-compose up -d
    print_success "Services started"
}

# Show status
show_status() {
    print_header "Services Status"
    
    docker-compose ps
    
    echo ""
    print_success "Services are running!"
    echo ""
    echo "Access the application:"
    echo -e "  Frontend:  ${GREEN}http://localhost:3000${NC}"
    echo -e "  Backend:   ${GREEN}http://localhost:8001${NC}"
    echo -e "  API Docs:  ${GREEN}http://localhost:8001/docs${NC}"
    echo ""
    echo "View logs:"
    echo -e "  Backend:   ${YELLOW}docker-compose logs -f backend${NC}"
    echo -e "  Frontend:  ${YELLOW}docker-compose logs -f frontend${NC}"
    echo -e "  Redis:     ${YELLOW}docker-compose logs -f redis${NC}"
    echo ""
}

# Main menu
main_menu() {
    print_header "Reconciliation System - Docker Setup"
    
    echo "Select an option:"
    echo "1) Setup and Start (Full setup)"
    echo "2) Start (Already setup)"
    echo "3) Stop Services"
    echo "4) Restart Services"
    echo "5) View Logs"
    echo "6) Cleanup (Remove containers and volumes)"
    echo "7) Exit"
    echo ""
    read -p "Enter option (1-7): " option
    
    case $option in
        1)
            check_docker
            create_directories
            setup_env
            build_images
            start_services
            show_status
            ;;
        2)
            docker-compose up -d
            print_success "Services started"
            docker-compose ps
            ;;
        3)
            docker-compose down
            print_success "Services stopped"
            ;;
        4)
            docker-compose restart
            print_success "Services restarted"
            docker-compose ps
            ;;
        5)
            echo "Select service:"
            echo "1) Backend"
            echo "2) Frontend"
            echo "3) Redis"
            read -p "Enter service number: " service
            
            case $service in
                1) docker-compose logs -f backend ;;
                2) docker-compose logs -f frontend ;;
                3) docker-compose logs -f redis ;;
                *) print_error "Invalid option" ;;
            esac
            ;;
        6)
            print_info "This will remove all containers and volumes"
            read -p "Are you sure? (yes/no): " confirm
            
            if [ "$confirm" = "yes" ]; then
                docker-compose down -v
                print_success "Cleanup complete"
            else
                print_info "Cleanup cancelled"
            fi
            ;;
        7)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid option"
            main_menu
            ;;
    esac
}

# Run main menu
if [ $# -eq 0 ]; then
    # Interactive mode
    main_menu
else
    # Command line mode
    case $1 in
        setup)
            check_docker
            create_directories
            setup_env
            build_images
            start_services
            show_status
            ;;
        start)
            docker-compose up -d
            print_success "Services started"
            docker-compose ps
            ;;
        stop)
            docker-compose down
            print_success "Services stopped"
            ;;
        restart)
            docker-compose restart
            print_success "Services restarted"
            ;;
        logs)
            docker-compose logs -f ${2:-backend}
            ;;
        cleanup)
            docker-compose down -v
            print_success "Cleanup complete"
            ;;
        *)
            echo "Usage: $0 {setup|start|stop|restart|logs|cleanup}"
            exit 1
            ;;
    esac
fi
