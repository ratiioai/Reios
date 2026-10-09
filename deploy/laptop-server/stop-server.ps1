# Stops everything start-server.ps1 started. Safe to run any time - including after the laptop has
# restarted, when the recorded process ids may belong to other programs: a process is only stopped
# after checking it really is one of ours (by its program and command line).
$ErrorActionPreference = "Continue"   # a "not running" message from nginx must not abort the caller
$root     = "C:\reios-server"
$pidFile  = Join-Path $root "logs\pids.txt"
$nginxDir = Join-Path $root "nginx"

function Test-Ours([int]$procId, [string]$kind) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    if (-not $p) { return $false }
    switch ($kind) {
        "api"    { return $p.Name -eq "python.exe" -and $p.CommandLine -like "*uvicorn*app.main:app*" }
        "nginx"  { return $p.Name -eq "nginx.exe" -and $p.ExecutablePath -like "$nginxDir*" }
        "tunnel" { return $p.Name -eq "cloudflared.exe" -and $p.ExecutablePath -like "$root*" }
    }
    return $false
}

# nginx: graceful quit only if our nginx is actually running; otherwise just clear the stale pid file
$ngPidFile = Join-Path $nginxDir "logs\nginx.pid"
if (Test-Path $ngPidFile) {
    $ngPid = [int](Get-Content $ngPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($ngPid -and (Test-Ours $ngPid "nginx")) {
        Push-Location $nginxDir; & .\nginx.exe -s quit 2>&1 | Out-Null; Pop-Location
        Start-Sleep -Seconds 1
    }
    Remove-Item $ngPidFile -ErrorAction SilentlyContinue
}

if (Test-Path $pidFile) {
    foreach ($line in Get-Content $pidFile) {
        $parts = $line -split ":"
        $kind = $parts[0]; $procId = [int]$parts[2]
        if (Test-Ours $procId $kind) {
            & taskkill /PID $procId /T /F 2>&1 | Out-Null
            Write-Host "stopped $kind $($parts[1]) (pid $procId)"
        }
    }
    Remove-Item $pidFile
}

# Anything of ours still holding our ports (e.g. a crashed run that never wrote pids.txt).
# Only our own python/nginx/cloudflared processes are touched - never another program on 8080.
$ports = 8080, 8001, 8002, 8003, 8004, 8005, 8006
foreach ($line in (netstat -ano | Select-String "LISTENING")) {
    $cols = ($line.ToString().Trim() -split "\s+")
    $port = [int](($cols[1] -split ":")[-1]); $procId = [int]$cols[-1]
    if ($ports -contains $port) {
        $ours = (Test-Ours $procId "api") -or (Test-Ours $procId "nginx")
        if (-not $ours) {   # the venv launcher's child interpreter: check its parent
            $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
            $ours = $p -and $p.Name -eq "python.exe" -and (Test-Ours ([int]$p.ParentProcessId) "api")
        }
        if ($ours) { & taskkill /PID $procId /T /F 2>&1 | Out-Null; Write-Host "freed port $port" }
        else { Write-Host "port $port is used by another program - left alone" -ForegroundColor Yellow }
    }
}
Write-Host "Stopped."
