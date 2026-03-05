@echo off
REM ============================================================
REM Docker Setup and Run Script for Reconciliation System
REM Windows Version
REM ============================================================

setlocal enabledelayedexpansion

REM Colors and styles
cls

:menu
cls
echo.
echo ============================================================
echo Reconciliation System - Docker Setup (Windows)
echo ============================================================
echo.
echo Select an option:
echo.
echo   1) Setup and Start (Full setup)
echo   2) Start (Already setup)
echo   3) Stop Services
echo   4) Restart Services
echo   5) View Logs
echo   6) Rebuild Images
echo   7) Cleanup (Remove containers and volumes)
echo   8) Open Browser
echo   9) Exit
echo.
set /p option="Enter option (1-9): "

if "%option%"=="1" goto setup
if "%option%"=="2" goto start
if "%option%"=="3" goto stop
if "%option%"=="4" goto restart
if "%option%"=="5" goto logs
if "%option%"=="6" goto rebuild
if "%option%"=="7" goto cleanup
if "%option%"=="8" goto browser
if "%option%"=="9" goto end
echo Invalid option!
timeout /t 2 /nobreak
goto menu

:setup
cls
echo.
echo ============================================================
echo Checking Docker Installation...
echo ============================================================
echo.

docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH!
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    goto menu
)
echo [OK] Docker is installed

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed!
    echo It should be included with Docker Desktop
    pause
    goto menu
)
echo [OK] Docker Compose is installed
echo.

echo Creating directories...
if not exist "backend\data" mkdir "backend\data"
if not exist "backend\logs" mkdir "backend\logs"
if not exist "backend\storage\uploads" mkdir "backend\storage\uploads"
if not exist "backend\storage\exports" mkdir "backend\storage\exports"
if not exist "backend\storage\processed" mkdir "backend\storage\processed"
if not exist "backend\storage\mock_data" mkdir "backend\storage\mock_data"
if not exist "redis\data" mkdir "redis\data"
echo [OK] Directories created
echo.

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env"
        echo [OK] .env file created from .env.example
        echo [INFO] Please edit .env file with your configuration
    ) else (
        echo [ERROR] .env.example not found!
        pause
        goto menu
    )
) else (
    echo [INFO] .env file already exists
)
echo.

echo Building Docker images...
echo [*] Building backend image...
docker-compose build backend
if errorlevel 1 (
    echo [ERROR] Failed to build backend image!
    pause
    goto menu
)
echo [OK] Backend image built
echo.

echo [*] Building frontend image...
docker-compose build frontend
if errorlevel 1 (
    echo [ERROR] Failed to build frontend image!
    pause
    goto menu
)
echo [OK] Frontend image built
echo.

echo Starting services...
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start services!
    pause
    goto menu
)
echo [OK] Services started
echo.

timeout /t 3 /nobreak
goto status

:start
echo.
echo Starting services...
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start services!
    pause
    goto menu
)
echo [OK] Services started
echo.
timeout /t 2 /nobreak
goto status

:stop
echo.
echo Stopping services...
docker-compose down
echo [OK] Services stopped
echo.
timeout /t 2 /nobreak
goto menu

:restart
echo.
echo Restarting services...
docker-compose restart
echo [OK] Services restarted
echo.
timeout /t 2 /nobreak
goto status

:logs
cls
echo.
echo Select service to view logs:
echo.
echo   1) Backend
echo   2) Frontend
echo   3) Redis
echo   4) All services
echo   5) Back to menu
echo.
set /p svc="Enter service number (1-5): "

if "%svc%"=="1" (
    docker-compose logs -f backend
) else if "%svc%"=="2" (
    docker-compose logs -f frontend
) else if "%svc%"=="3" (
    docker-compose logs -f redis
) else if "%svc%"=="4" (
    docker-compose logs -f
) else if "%svc%"=="5" (
    goto menu
)
goto logs

:rebuild
echo.
echo Rebuilding Docker images...
docker-compose build --no-cache
if errorlevel 1 (
    echo [ERROR] Failed to rebuild images!
    pause
    goto menu
)
echo [OK] Images rebuilt
echo.
timeout /t 2 /nobreak
goto menu

:cleanup
echo.
echo WARNING: This will remove all containers, networks and volumes!
set /p confirm="Are you sure? (yes/no): "
if /i "%confirm%"=="yes" (
    docker-compose down -v
    echo [OK] Cleanup complete
) else (
    echo [INFO] Cleanup cancelled
)
echo.
timeout /t 2 /nobreak
goto menu

:browser
echo.
echo Opening browser...
start http://localhost:3000
echo [OK] Browser opened
echo.
timeout /t 2 /nobreak
goto menu

:status
cls
echo.
echo ============================================================
echo Services Status
echo ============================================================
echo.
docker-compose ps
echo.
echo ============================================================
echo Access the application:
echo ============================================================
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8001
echo   API Docs:  http://localhost:8001/docs
echo.
echo View logs:
echo   Backend:   docker-compose logs -f backend
echo   Frontend:  docker-compose logs -f frontend
echo   Redis:     docker-compose logs -f redis
echo.
echo ============================================================
echo.
pause
goto menu

:end
echo.
echo Goodbye!
echo.
exit /b 0
