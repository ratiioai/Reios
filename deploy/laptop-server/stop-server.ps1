# Stops everything start-server.ps1 started (by recorded process id, never by name, so no other
# python/nginx on this machine is touched).
$root    = "C:\reios-server"
$pidFile = Join-Path $root "logs\pids.txt"

$nginxDir = Join-Path $root "nginx"
if (Test-Path (Join-Path $nginxDir "logs\nginx.pid")) {
    Push-Location $nginxDir; & .\nginx.exe -s quit 2>$null; Pop-Location
    Start-Sleep -Seconds 1
}

if (Test-Path $pidFile) {
    foreach ($line in Get-Content $pidFile) {
        $parts = $line -split ":"
        $procId = [int]$parts[2]
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
            & taskkill /PID $procId /T /F 2>$null | Out-Null
            Write-Host "stopped $($parts[0]) $($parts[1]) (pid $procId)"
        }
    }
    Remove-Item $pidFile
}

# Anything still holding our ports (e.g. a crashed run that never wrote pids.txt)
$ports = 8080, 8001, 8002, 8003, 8004, 8005, 8006
foreach ($line in (netstat -ano | Select-String "LISTENING")) {
    $cols = ($line.ToString().Trim() -split "\s+")
    $port = [int](($cols[1] -split ":")[-1])
    if ($ports -contains $port) { & taskkill /PID $cols[-1] /T /F 2>$null | Out-Null; Write-Host "freed port $port" }
}
Write-Host "Stopped."
