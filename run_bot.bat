@echo off
title Digital Mart - Telegram Bot
cd /d "%~dp0"

echo ========================================================
echo   Digital Mart - Telegram Bot Runner (aiogram 3)
echo ========================================================
echo.

if exist "backend\venv\Scripts\python.exe" (
    echo [*] Menggunakan Python Virtual Environment (backend\venv)...
    "backend\venv\Scripts\python.exe" backend\main.py
) else (
    echo [*] Menggunakan Python Sistem...
    python backend\main.py
)

pause
