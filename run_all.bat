@echo off
title Digital Mart - Master Launcher
cd /d "%~dp0"

echo ========================================================
echo   Menjalankan Digital Mart Backend & Bot Telegram...
echo ========================================================
echo.

start "Digital Mart Backend" cmd /k call "%~dp0run_backend.bat"
timeout /t 2 /nobreak >nul
start "Digital Mart Bot" cmd /k call "%~dp0run_bot.bat"

echo.
echo [OK] Backend dan Bot sudah dinyalakan di jendela masing-masing!
echo - Backend API & Admin Web : http://127.0.0.1:8000
echo - Swagger API Docs        : http://127.0.0.1:8000/docs
echo.
pause
