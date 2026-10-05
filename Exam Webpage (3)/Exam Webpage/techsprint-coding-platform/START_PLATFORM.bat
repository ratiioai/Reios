@echo off
title TECHSPRINT 2026 - Coding Platform
echo ================================================================================
echo                   TECHSPRINT 2026 - STARTING PLATFORM
echo ================================================================================
echo.

cd /d "%~dp0"
cd backend

echo [1/3] Initializing TECHSPRINT database tables...
venv\Scripts\python.exe -c "from app.database import create_tables; from app.grading_queue import GradingQueueItem; create_tables(); print('TECHSPRINT database tables created successfully!')"

echo.
echo [2/3] Starting Backend Server (Port 8001)...
start "TECHSPRINT Backend Server" cmd /k "venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001"

timeout /t 3 /nobreak >nul

cd ..\frontend
echo.
echo [3/3] Starting Frontend Server (Port 3001)...
start "TECHSPRINT Frontend Server" cmd /k "python -m http.server 3001"

echo.
echo ================================================================================
echo                     TECHSPRINT 2026 PLATFORM STARTED!
echo ================================================================================
echo.
echo   Frontend:  http://localhost:3001
echo   Backend:   http://localhost:8001
echo   API Docs:  http://localhost:8001/api/docs
echo   Health:    http://localhost:8001/api/health
echo.
echo   Admin Login: http://localhost:3001/admin-login.html
echo   Default Admin: admin / admin123
echo.
echo ================================================================================
pause
