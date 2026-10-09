# Failover drill: after $AfterSeconds, kill the API instance on $Port (as if it crashed), then
# restart it $DownSeconds later. nginx should route around it with no visible errors.
param([int]$Port = 8002, [int]$AfterSeconds = 200, [int]$DownSeconds = 60)

$backend = "C:\Users\Dell\Downloads\reios\Reios\Exam Webpage (3)\Exam Webpage\coding-test-platform\backend"
$python  = Join-Path $backend "venv\Scripts\python.exe"
$logs    = "C:\reios-server\logs"

Start-Sleep -Seconds $AfterSeconds
$line = netstat -ano | Select-String ":$Port\s.*LISTENING" | Select-Object -First 1
$procId = ($line.ToString().Trim() -split "\s+")[-1]
& taskkill /PID $procId /T /F | Out-Null
"$(Get-Date -Format HH:mm:ss) killed API $Port (pid $procId)" | Tee-Object -Append "$logs\failover.txt"

Start-Sleep -Seconds $DownSeconds
Get-Content "C:\reios-server\server.env" | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } | ForEach-Object {
    $null = $_ -match "^\s*([A-Z_]+)=(.*)$"; [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process") }
$p = Start-Process -FilePath $python -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$logs\api-$Port.log" -RedirectStandardError "$logs\api-$Port.err.log" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port",
                  "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1", "--no-access-log", "--timeout-keep-alive", "75"
"$(Get-Date -Format HH:mm:ss) restarted API $Port (pid $($p.Id))" | Tee-Object -Append "$logs\failover.txt"
# keep stop-server.ps1 able to find it
$pidFile = "$logs\pids.txt"
(Get-Content $pidFile) -replace "^api:${Port}:\d+$", "api:${Port}:$($p.Id)" | Set-Content $pidFile
