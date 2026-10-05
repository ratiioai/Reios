@echo off
echo Starting Coding Test Platform Server...
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo Warning: Virtual environment not found. Using global Python.
)

echo.
echo Starting Uvicorn server on http://localhost:8000
echo API docs will be available at http://localhost:8000/api/docs
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
