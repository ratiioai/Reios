# PowerShell Setup Script for Coding Test Platform
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setting Up Backend Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "1. Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "   Found: $pythonVersion" -ForegroundColor Green

# Create virtual environment if it doesn't exist
if (Test-Path "venv") {
    Write-Host "2. Virtual environment already exists" -ForegroundColor Green
} else {
    Write-Host "2. Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "   Virtual environment created!" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "3. Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip first
Write-Host "4. Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install core dependencies
Write-Host "5. Installing core dependencies..." -ForegroundColor Yellow
pip install -r requirements_core.txt

# Install numpy first (pandas needs it)
Write-Host "6. Installing numpy..." -ForegroundColor Yellow
pip install numpy

# Install pandas
Write-Host "7. Installing pandas (optional, for CSV processing)..." -ForegroundColor Yellow
pip install pandas
Write-Host "   Note: If pandas fails, CSV upload will use basic parsing (works fine)" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run: .\generate_questions_ai.ps1" -ForegroundColor White
Write-Host "2. This will generate 150 questions using Grok AI" -ForegroundColor White
Write-Host ""
