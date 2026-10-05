@echo off
echo ========================================
echo AI Question Generator
echo ========================================
echo.
echo This will generate 150 coding questions using Grok AI
echo Estimated time: 20-30 minutes
echo.
pause

cd /d "%~dp0"
call venv\Scripts\activate
python ai_question_generator.py

pause
