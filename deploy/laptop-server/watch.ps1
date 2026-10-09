# Live log viewer. One mode per window; watch-logs.ps1 opens all three.
#   -Mode requests : every request through nginx (red = server error, yellow = rate-limited)
#   -Mode errors   : only problems - failed requests, nginx errors, API errors from all instances
#   -Mode health   : status of every piece, refreshed every 10 s, plus tunnel/database messages
param([ValidateSet("requests", "errors", "health")][string]$Mode = "requests", [int]$History = 20)

$root   = "C:\reios-server"
$access = "$root\nginx\logs\access.log"
$Host.UI.RawUI.WindowTitle = "Reios - $Mode"

function Write-LogLine([string]$line, [string]$source) {
    $color = "Gray"
    if ($line -match '" 5\d\d ' -or $line -match '\[(error|crit|alert|emerg)\]' -or $line -match 'Traceback|ERROR|Exception') { $color = "Red" }
    elseif ($line -match '" 429 ' -or $line -match '\[warn\]' -or $line -match 'WARNING') { $color = "Yellow" }
    elseif ($line -match '" 2\d\d ') { $color = "Green" }
    $prefix = if ($source) { "[$source] " } else { "" }
    Write-Host "$prefix$line" -ForegroundColor $color
}

# Follows several files at once (Get-Content -Wait only follows one). Files are opened with
# shared access, so nginx/uvicorn keep writing to them normally.
function Follow-Files([string[]]$Patterns, [string]$Filter, [int]$Last) {
    $pos = @{}
    foreach ($f in (Get-ChildItem $Patterns -ErrorAction SilentlyContinue)) {
        $old = Get-Content $f.FullName -Tail $Last -ErrorAction SilentlyContinue |
               Where-Object { $_ -and (-not $Filter -or $_ -match $Filter) }
        foreach ($l in $old) { Write-LogLine $l $f.Name }
        $pos[$f.FullName] = $f.Length
    }
    Write-Host "---- live from here (Ctrl+C to stop) ----" -ForegroundColor Cyan
    while ($true) {
        foreach ($f in (Get-ChildItem $Patterns -ErrorAction SilentlyContinue)) {
            $old = if ($pos.ContainsKey($f.FullName)) { $pos[$f.FullName] } else { 0 }
            if ($f.Length -lt $old) { $old = 0 }             # file was recreated
            if ($f.Length -gt $old) {
                try {
                    $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite, Delete')
                    $null = $fs.Seek($old, 'Begin')
                    $sr = New-Object IO.StreamReader($fs)
                    $text = $sr.ReadToEnd()
                    $sr.Close()
                    $pos[$f.FullName] = $f.Length
                    foreach ($l in ($text -split "`r?`n")) {
                        if ($l -and (-not $Filter -or $l -match $Filter)) { Write-LogLine $l $f.Name }
                    }
                } catch { }
            }
        }
        Start-Sleep -Milliseconds 700
    }
}

switch ($Mode) {
    "requests" {
        Write-Host "Every request (nginx writes in batches, so lines appear within ~5 s)" -ForegroundColor Cyan
        Write-Host "IP  [time]  request  status  size  rt=total time  urt=API time  up=which API copy" -ForegroundColor DarkGray
        Follow-Files @($access) $null $History
    }
    "errors" {
        Write-Host "Problems only: failed/blocked requests, nginx errors, API errors" -ForegroundColor Cyan
        # access.log: only 5xx and 429; API logs: skip routine startup lines
        $problem = '" (5\d\d|429) |\[(warn|error|crit|alert|emerg)\]|Traceback|Error|Exception|ERROR|WARNING|  File "|^\s'
        Follow-Files @($access, "$root\nginx\logs\error.log", "$root\logs\api-*.err.log") $problem $History
    }
    "health" {
        while ($true) {
            Clear-Host
            Write-Host "Reios health - $(Get-Date -Format 'HH:mm:ss')  (refreshes every 10 s, Ctrl+C to stop)" -ForegroundColor Cyan
            Write-Host ""
            & "$root\status.ps1"
            Write-Host ""
            Write-Host "Tunnel (latest):" -ForegroundColor Cyan
            Get-Content "$root\logs\tunnel.log" -Tail 4 -ErrorAction SilentlyContinue | ForEach-Object { Write-LogLine $_ $null }
            Write-Host ""
            Write-Host "Database (latest):" -ForegroundColor Cyan
            Get-Content "$root\logs\postgres.log" -Tail 4 -ErrorAction SilentlyContinue | ForEach-Object { Write-LogLine $_ $null }
            Start-Sleep -Seconds 10
        }
    }
}
