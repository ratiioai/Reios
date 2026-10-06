@echo off
REM Run ONCE, as administrator (right-click -> Run as administrator).
REM Lets phones and laptops on the same Wi-Fi reach Reios on port 8000, even on "Public" networks.
net session >nul 2>&1
if errorlevel 1 (
  echo Please right-click this file and choose "Run as administrator".
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="Reios exam server (port 8000)" >nul 2>&1
netsh advfirewall firewall add rule name="Reios exam server (port 8000)" dir=in action=allow protocol=TCP localport=8000 profile=any
echo.
echo Done. Students on the same Wi-Fi can now reach this laptop on port 8000.
pause
