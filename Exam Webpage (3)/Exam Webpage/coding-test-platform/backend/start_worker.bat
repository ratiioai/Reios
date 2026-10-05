@echo off
echo Starting Grading Worker...
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo Warning: Virtual environment not found. Using global Python.
)

echo.
echo Grading worker will process submissions from the queue
echo Press Ctrl+C to stop
echo.

python grading_worker.py
