# Quick health check of every piece of the stack.
$root = "C:\reios-server"
$n = [int]((Get-Content (Join-Path $root "server.env") | Select-String "^API_INSTANCES=(\d+)").Matches[0].Groups[1].Value)
foreach ($port in (1..$n | ForEach-Object { 8000 + $_ })) {
    try { $null = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 3; Write-Host "API $port   OK" -ForegroundColor Green }
    catch { Write-Host "API $port   DOWN" -ForegroundColor Red }
}
try {
    $r = Invoke-WebRequest "http://127.0.0.1:8080/api/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "nginx 8080 OK (served by $($r.Headers['X-Upstream']))" -ForegroundColor Green
    Write-Host ((Invoke-WebRequest "http://127.0.0.1:8080/nginx-status" -UseBasicParsing).Content)
} catch { Write-Host "nginx 8080 DOWN" -ForegroundColor Red }
$urlFile = Join-Path $root "PUBLIC_URL.txt"
if (Test-Path $urlFile) {
    $url = (Get-Content $urlFile).Trim()
    try { $null = Invoke-RestMethod "$url/api/health" -TimeoutSec 10; Write-Host "Public     OK  $url" -ForegroundColor Green }
    catch { Write-Host "Public     DOWN  $url" -ForegroundColor Red }
}
