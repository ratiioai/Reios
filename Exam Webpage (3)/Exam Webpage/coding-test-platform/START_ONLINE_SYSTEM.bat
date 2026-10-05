@echo off
title SPEC Industry Hack 2026 - Online Platform Server
echo ========================================================
echo   SPEC INDUSTRY HACK 2026 - FULL SYSTEM STARTUP
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Starting FastAPI Backend on Port 8000...
start "Backend Server (FastAPI)" cmd /k "cd backend && venv\Scripts\activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo [2/3] Starting Background Grading Worker...
start "Grading Worker" cmd /k "cd backend && venv\Scripts\activate && python grading_worker.py"

timeout /t 2 /nobreak > nul

echo [3/3] Starting Cloudflare HTTPS Tunnel...
start "Cloudflare Tunnel (Public HTTPS)" cmd /k "cloudflared.exe tunnel --url http://127.0.0.1:8000"

echo.
echo ========================================================
echo   ALL SERVICES STARTED!
echo   Vercel App: https://spec-industry-hack-2026.vercel.app
echo   Admin Panel: https://spec-industry-hack-2026.vercel.app/admin
echo ========================================================
pause
