# Opens three live log windows: Requests, Errors, Health.
#   powershell -ExecutionPolicy Bypass -File C:\reios-server\watch-logs.ps1
foreach ($mode in "requests", "errors", "health") {
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass",
        "-File", "C:\reios-server\watch.ps1", "-Mode", $mode
}
