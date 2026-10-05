# PowerShell Script to Generate Questions with Grok AI
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI Question Generator (Grok API)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will generate 150 coding questions:" -ForegroundColor Yellow
Write-Host "  - 60 Easy questions (5 marks each)" -ForegroundColor White
Write-Host "  - 60 Medium questions (10 marks each)" -ForegroundColor White
Write-Host "  - 30 Hard questions (20 marks each)" -ForegroundColor White
Write-Host ""
Write-Host "Estimated time: 20-30 minutes" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Start generation? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cancelled." -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "Starting generation..." -ForegroundColor Green
Write-Host ""

# Activate virtual environment and run generator
& .\venv\Scripts\Activate.ps1
python ai_question_generator.py

Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
