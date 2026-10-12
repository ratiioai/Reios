# Quick health check of every piece of the stack.
$root = "C:\reios-server"
$cfg = Get-Content (Join-Path $root "server.env")
$n = [int](($cfg | Select-String "^API_INSTANCES=(\d+)").Matches[0].Groups[1].Value)
$ports = 1..$n | ForEach-Object { 8000 + $_ }
foreach ($port in $ports) {
    try { $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 3; Write-Host "API $port   OK" -ForegroundColor Green }
    catch { Write-Host "API $port   DOWN" -ForegroundColor Red }
}
try {
    $r = Invoke-WebRequest "http://127.0.0.1:8080/api/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "nginx 8080 OK (served by $($r.Headers['X-Upstream']))" -ForegroundColor Green
    Write-Host ((Invoke-WebRequest "http://127.0.0.1:8080/nginx-status" -UseBasicParsing).Content)
} catch { Write-Host "nginx 8080 DOWN" -ForegroundColor Red }
$urlFile = Join-Path $root "PUBLIC_URL.txt"
$url = $null
if (Test-Path $urlFile) {
    $url = (Get-Content $urlFile).Trim()
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try { $null = Invoke-RestMethod "$url/api/health" -TimeoutSec 10; Write-Host ("Public     OK  {0}  ({1} ms round trip)" -f $url, $sw.ElapsedMilliseconds) -ForegroundColor Green }
    catch { Write-Host "Public     DOWN  $url" -ForegroundColor Red }
}

# ---- Is everything on this laptop? (database local, nothing via Render) ----
Write-Host ""
Write-Host "Local-only check:" -ForegroundColor Cyan
$loopback = '^(127\.|::1$|::ffff:127\.)'
$dbPorts  = 5432, 5433, 6543   # PostgreSQL / pooler ports - Render uses 5432

# 1. What the API instances were told to use
$dbUrl = ($cfg | Select-String "^DATABASE_URL=(.*)$").Matches[0].Groups[1].Value
if ($dbUrl -match "@(127\.0\.0\.1|localhost|\[::1\]):5433/") {
    Write-Host "DB setting   LOCAL   127.0.0.1:5433 (server.env)" -ForegroundColor Green
} else {
    Write-Host "DB setting   NOT LOCAL   $($dbUrl -replace '://([^:]+):[^@]*@', '://$1:***@')" -ForegroundColor Red
}

# 2. What the running API instances are actually connected to (catches a stale/other setting)
$apiPids = @(Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue |
             Select-Object -ExpandProperty OwningProcess -Unique)
if ($apiPids) {
    $conns    = @(Get-NetTCPConnection -State Established -OwningProcess $apiPids -ErrorAction SilentlyContinue)
    $localDb  = @($conns | Where-Object { $_.RemotePort -eq 5433 -and $_.RemoteAddress -match $loopback })
    $remoteDb = @($conns | Where-Object { $_.RemotePort -in $dbPorts -and $_.RemoteAddress -notmatch $loopback })
    $outside  = @($conns | Where-Object { $_.RemoteAddress -notmatch $loopback -and $_.RemotePort -notin $dbPorts })
    if ($remoteDb) {
        $where = ($remoteDb | ForEach-Object { "$($_.RemoteAddress):$($_.RemotePort)" } | Select-Object -Unique) -join ", "
        Write-Host "DB live      REMOTE!  API is connected to $where (Render?) - restart with start-server.ps1" -ForegroundColor Red
    } elseif ($localDb) {
        Write-Host "DB live      LOCAL   $($localDb.Count) API connections, all to 127.0.0.1:5433, none remote" -ForegroundColor Green
    } else {
        Write-Host "DB live      no open DB connections yet (API idle)" -ForegroundColor Yellow
    }
    if ($outside) {
        # e.g. Google sign-in key downloads on 443 - not a database, but listed so nothing is hidden
        $where = ($outside | ForEach-Object { "$($_.RemoteAddress):$($_.RemotePort)" } | Select-Object -Unique -First 4) -join ", "
        Write-Host "Other out    $($outside.Count) non-DB outbound from API: $where" -ForegroundColor DarkGray
    }
} else {
    Write-Host "DB live      no API instance listening" -ForegroundColor Red
}

# 3. The local database itself answers
$pwFile = Join-Path $root "db-passwords.txt"
if (Test-Path $pwFile) {
    $env:PGPASSWORD = ((Get-Content $pwFile)[1] -split ": ")[1]
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $q = "SELECT count(*), pg_size_pretty(pg_database_size('reios')) FROM pg_stat_activity WHERE datname = 'reios' AND pid <> pg_backend_pid()"
    $res = & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5433 -U reios -d reios -tA -F "|" -c $q 2>$null
    $ms = $sw.ElapsedMilliseconds
    Remove-Item Env:PGPASSWORD
    if ($LASTEXITCODE -eq 0 -and $res) {
        $c, $size = "$res".Split("|")
        Write-Host "Laptop DB    OK      127.0.0.1:5433 answered in $ms ms - $c sessions, $size" -ForegroundColor Green
    } else {
        Write-Host "Laptop DB    DOWN    127.0.0.1:5433 didn't answer - see logs\postgres.log" -ForegroundColor Red
    }
}

# 4. Where the website sends participants (backend.json committed for Vercel)
$repo = "C:\Users\Dell\Downloads\reios\Reios"
$rel  = "Exam Webpage (3)/Exam Webpage/coding-test-platform/web/public/backend.json"
try {
    $site = ((Get-Content (Join-Path $repo $rel) -Raw | ConvertFrom-Json).api).TrimEnd("/")
    $unpushed = 0
    try { $unpushed = [int](git -C $repo rev-list --count "@{u}..HEAD" -- $rel 2>$null) } catch { }
    if ($site -match "onrender\.com|render\.com") {
        Write-Host "Website      RENDER!  backend.json points at $site" -ForegroundColor Red
    } elseif ($url -and $site -ne $url) {
        Write-Host "Website      MISMATCH  backend.json = $site, tunnel = $url" -ForegroundColor Red
    } elseif ($unpushed -gt 0) {
        Write-Host "Website      laptop tunnel, but backend.json not pushed to GitHub yet" -ForegroundColor Yellow
    } else {
        Write-Host "Website      LOCAL   reios-web.vercel.app -> laptop tunnel (not Render)" -ForegroundColor Green
    }
} catch { Write-Host "Website      can't read backend.json" -ForegroundColor Yellow }
