@echo off
REM Reios exam-day server. Several worker processes so a whole class can sign in and start at once
REM (tested with 300 students). Open http://localhost:8000/app/ or http://<this-PC's-IP>:8000/app/
cd /d "%~dp0backend"

if not exist "..\web\dist\index.html" (
  echo Building the website first...
  pushd ..\web
  call npm install
  call npm run build
  popd
)

venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log
