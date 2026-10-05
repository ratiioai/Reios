@echo off
echo ========================================
echo PostgreSQL Database Setup
echo ========================================
echo.
echo This will create:
echo - Database: coding_test_db
echo - User: coding_test_user
echo - Password: test123
echo.
echo Make sure PostgreSQL is installed and running!
echo.
pause

echo.
echo Running setup...
echo.

psql -U postgres -f setup_database.sql

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next step: Create .env file
echo.
pause
