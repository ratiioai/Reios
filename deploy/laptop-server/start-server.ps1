# Starts the whole Reios stack on this laptop:
#   API instances (ports 8001..) -> nginx (port 8080) -> Cloudflare quick tunnel (public https URL)
# Run:  powershell -ExecutionPolicy Bypass -File C:\reios-server\start-server.ps1
#       add -NoTunnel to keep it on this machine/LAN only (for testing)
param([switch]$NoTunnel)

$ErrorActionPreference = "Stop"
$root    = "C:\reios-server"
$backend = "C:\Users\Dell\Downloads\reios\Reios\Exam Webpage (3)\Exam Webpage\coding-test-platform\backend"
$python  = Join-Path $backend "venv\Scripts\python.exe"
$logs    = Join-Path $root "logs"
$pidFile = Join-Path $logs "pids.txt"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (Test-Path $pidFile) {
    Write-Host "A previous run is still recorded - stopping it first." -ForegroundColor Yellow
    & (Join-Path $root "stop-server.ps1")
}

# Load settings into this process; the API instances inherit them (backend/.env never overrides them).
Get-Content (Join-Path $root "server.env") | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } | ForEach-Object {
    $null = $_ -match "^\s*([A-Z_]+)=(.*)$"
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
}
if ($env:DATABASE_URL -match "CHANGE_ME") { throw "Set the database password in server.env first." }

# Reios' own PostgreSQL (port 5433, data in C:\reios-server\pgdata)
$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$pgData = Join-Path $root "pgdata"
if (-not (netstat -ano | Select-String ":5433\s.*LISTENING")) {
    # Start-Process (not a direct call) so the console doesn't wait on the server's inherited handles
    Start-Process -FilePath (Join-Path $pgBin "pg_ctl.exe") -WindowStyle Hidden -Wait `
        -ArgumentList "-D", "`"$pgData`"", "-l", "`"$(Join-Path $logs 'postgres.log')`"", "-w", "start"
    if (-not (netstat -ano | Select-String ":5433\s.*LISTENING")) { throw "PostgreSQL didn't start - see logs\postgres.log" }
}
Write-Host "  PostgreSQL ready on 127.0.0.1:5433" -ForegroundColor Green
$count = [int]$env:API_INSTANCES
$ports = 1..$count | ForEach-Object { 8000 + $_ }

$pids = @()
foreach ($port in $ports) {
    $p = Start-Process -FilePath $python -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs "api-$port.log") -RedirectStandardError (Join-Path $logs "api-$port.err.log") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port",
                      "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1",
                      "--no-access-log", "--timeout-keep-alive", "75"
    $pids += "api:${port}:$($p.Id)"
}

Write-Host "Waiting for $count API instances..."
foreach ($port in $ports) {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        try { $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2; $ok = $true; break } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ok) { Set-Content $pidFile $pids; throw "API on port $port didn't start - see logs\api-$port.err.log" }
    Write-Host "  API $port ready" -ForegroundColor Green
}

$nginxDir = Join-Path $root "nginx"
$ng = Start-Process -FilePath (Join-Path $nginxDir "nginx.exe") -WorkingDirectory $nginxDir -WindowStyle Hidden -PassThru
$pids += "nginx:8080:$($ng.Id)"
Start-Sleep -Seconds 1
$null = Invoke-RestMethod "http://127.0.0.1:8080/api/health" -TimeoutSec 5
Write-Host "  nginx ready on http://localhost:8080" -ForegroundColor Green

if (-not $NoTunnel) {
    $tunLog = Join-Path $logs "tunnel.log"
    Remove-Item $tunLog -ErrorAction SilentlyContinue
    $cf = Start-Process -FilePath (Join-Path $root "cloudflared.exe") -WindowStyle Hidden -PassThru `
        -ArgumentList "tunnel", "--url", "http://localhost:8080", "--no-autoupdate", "--logfile", $tunLog
    $pids += "tunnel:0:$($cf.Id)"
    $url = $null
    for ($i = 0; $i -lt 60 -and -not $url; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $tunLog) {
            $m = Select-String -Path $tunLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
            if ($m) { $url = $m.Matches[0].Value }
        }
    }
    if ($url) {
        Set-Content (Join-Path $root "PUBLIC_URL.txt") $url
        Write-Host ""
        Write-Host "  PUBLIC URL:  $url" -ForegroundColor Cyan
        Write-Host "  Participants sign in at $url/login"
    } else {
        Write-Host "  Tunnel didn't report a URL yet - check logs\tunnel.log" -ForegroundColor Yellow
    }
}

Set-Content $pidFile $pids
Write-Host ""
Write-Host "Running. Stop everything with: powershell -ExecutionPolicy Bypass -File C:\reios-server\stop-server.ps1"
