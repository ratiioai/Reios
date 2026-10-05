@echo off
echo ================================================================================
echo SPEC INDUSTRY HACK - STARTING PLATFORM
echo ================================================================================
echo.

cd backend

echo [1/3] Creating database tables...
venv\Scripts\python.exe -c "from app.database import create_tables; from app.grading_queue import GradingQueueItem; create_tables(); print('Tables created!')"

echo.
echo [2/3] Starting backend server (port 8000)...
start "Backend Server" cmd /k "venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

cd ..\frontend
echo.
echo [3/3] Starting frontend server (port 3000)...
start "Frontend Server" cmd /k "python -m http.server 3000"

echo.
echo ================================================================================
echo PLATFORM STARTED!
echo ================================================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo Docs:     http://localhost:8000/docs
echo.
echo Admin Login: admin / admin123
echo Team Login: [team_name] / [phone]
echo.
echo Press any key to continue...
pause >nul
