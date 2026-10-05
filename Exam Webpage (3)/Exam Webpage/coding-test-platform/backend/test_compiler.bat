@echo off
echo ========================================
echo Testing Local Code Compiler
echo ========================================
echo.

cd /d "%~dp0"
call venv\Scripts\activate
python code_compiler_tester.py

pause
