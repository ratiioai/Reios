# Restarts the API instances one at a time (e.g. to load new backend code) with zero downtime:
# while one restarts, nginx sends its traffic to the others.
$root    = "C:\reios-server"
$backend = "C:\Users\Dell\Downloads\reios\Reios\Exam Webpage (3)\Exam Webpage\coding-test-platform\backend"
$python  = Join-Path $backend "venv\Scripts\python.exe"
$logs    = Join-Path $root "logs"
$pidFile = Join-Path $logs "pids.txt"
Get-Content (Join-Path $root "server.env") | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } | ForEach-Object {
    $null = $_ -match "^\s*([A-Z_]+)=(.*)$"; [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process") }

foreach ($line in (Get-Content $pidFile | Where-Object { $_ -like "api:*" })) {
    $parts = $line -split ":"; $port = [int]$parts[1]; $old = [int]$parts[2]
    & taskkill /PID $old /T /F 2>$null | Out-Null
    $p = Start-Process -FilePath $python -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logs "api-$port.log") -RedirectStandardError (Join-Path $logs "api-$port.err.log") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port",
                      "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1", "--no-access-log", "--timeout-keep-alive", "75"
    $ok = $false
    for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
        try { $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2; $ok = $true } catch { Start-Sleep -Milliseconds 500 }
    }
    (Get-Content $pidFile) -replace "^api:${port}:\d+$", "api:${port}:$($p.Id)" | Set-Content $pidFile
    Write-Host ("API {0} restarted (pid {1}) {2}" -f $port, $p.Id, $(if ($ok) { "OK" } else { "NOT HEALTHY - check logs\api-$port.err.log" }))
}
