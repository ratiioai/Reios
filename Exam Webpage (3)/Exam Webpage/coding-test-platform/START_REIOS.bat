@echo off
REM Reios exam-day server on this laptop. Several worker processes so a whole hall can sign in at once
REM (tested with 300 students). Keep this window open during the exam.
cd /d "%~dp0backend"

if not exist "..\web\dist\index.html" (
  echo Building the website first...
  pushd ..\web
  call npm install
  call npm run build
  popd
)

echo.
echo ============================================================
echo   Reios is starting. Students open one of these addresses:
powershell -NoProfile -Command "Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | ForEach-Object { '     http://' + $_.IPv4Address.IPAddress + ':8000/app/login   (' + $_.InterfaceAlias + ')' }"
echo.
echo   You (admin) can use  http://localhost:8000/app/login
echo   Keep the laptop plugged in and this window open.
echo ============================================================
echo.

venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log
