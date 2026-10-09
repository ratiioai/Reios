# Replaces the laptop database with a fresh copy of the Render database.
# Run this right before switching participants to the laptop, so nothing done on Render is lost.
# Afterwards, use ONLY the laptop - anything saved on Render later won't be here.
#   powershell -ExecutionPolicy Bypass -File C:\reios-server\sync-from-render.ps1 -RenderUrl "postgresql://..."
param([Parameter(Mandatory = $true)][string]$RenderUrl)

$ErrorActionPreference = "Stop"
$root = "C:\reios-server"
$pg   = "C:\Program Files\PostgreSQL\18\bin"
if ($RenderUrl -notmatch "sslmode=") { $RenderUrl += $(if ($RenderUrl -match "\?") { "&" } else { "?" }) + "sslmode=require" }
$lines   = Get-Content (Join-Path $root "db-passwords.txt")
$superPw = ($lines[0] -split ": ")[1]
$appPw   = ($lines[1] -split ": ")[1]

$file = Join-Path $root "backups\render-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
Write-Host "Dumping Render..."
& "$pg\pg_dump.exe" --format=custom --no-owner --no-privileges --file=$file $RenderUrl
if ($LASTEXITCODE) { throw "pg_dump failed" }

# Safety copy of the current laptop data before replacing it
$env:PGPASSWORD = $appPw
$safety = Join-Path $root "backups\laptop-before-sync-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
& "$pg\pg_dump.exe" -h 127.0.0.1 -p 5433 -U reios --format=custom --file=$safety reios

Write-Host "Stopping the API so nothing writes during the swap..."
& (Join-Path $root "stop-server.ps1") | Out-Null
if (-not (netstat -ano | Select-String ":5433\s.*LISTENING")) {
    # No -Wait (it would wait for the database server itself, which never exits): start, then poll
    Start-Process -FilePath "$pg\pg_ctl.exe" -WindowStyle Hidden -ArgumentList "-D", "`"$root\pgdata`"", "-l", "`"$root\logs\postgres.log`"", "start"
    $i = 0
    while ($i -lt 120 -and -not (netstat -ano | Select-String ":5433\s.*LISTENING")) { Start-Sleep -Milliseconds 500; $i++ }
}

$env:PGPASSWORD = $superPw
& "$pg\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d postgres -q -v ON_ERROR_STOP=1 `
    -c "DROP DATABASE IF EXISTS reios WITH (FORCE);" -c "CREATE DATABASE reios OWNER reios ENCODING 'UTF8';"
$env:PGPASSWORD = $appPw
& "$pg\pg_restore.exe" -h 127.0.0.1 -p 5433 -U reios -d reios --no-owner --no-privileges --exit-on-error $file
if ($LASTEXITCODE) { throw "pg_restore failed - previous data is in $safety" }

# Sessions started on Render can't be used here (different signing key), but with single-login on
# they'd still block every team from signing in. Start everyone signed out.
& "$pg\psql.exe" -h 127.0.0.1 -p 5433 -U reios -d reios -q -c "UPDATE reios_users SET active_session_expires_at = NULL;"

$q = "SELECT 'users', count(*) FROM reios_users UNION ALL SELECT 'exams', count(*) FROM reios_exams UNION ALL SELECT 'attempts', count(*) FROM reios_attempts UNION ALL SELECT 'answers', count(*) FROM reios_mcq_answers ORDER BY 1"
$renderCounts = & "$pg\psql.exe" $RenderUrl -tA -F "|" -c $q
$localCounts  = & "$pg\psql.exe" -h 127.0.0.1 -p 5433 -U reios -d reios -tA -F "|" -c $q
if (Compare-Object $renderCounts $localCounts) { throw "Row counts differ after sync - check before using" }
Write-Host "Synced. Counts match Render:" -ForegroundColor Green
$localCounts
Set-Content (Join-Path $root "backups\latest.txt") $file
Write-Host "Start the server again with start-server.ps1"
