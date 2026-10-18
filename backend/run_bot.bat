@echo off
title Digital Mart - Telegram Bot
cd /d "%~dp0"

echo ========================================================
echo   Digital Mart - Telegram Bot Runner (aiogram 3)
echo ========================================================
echo.

if exist "venv\Scripts\python.exe" (
    echo [*] Menggunakan Virtual Environment (venv)...
    "venv\Scripts\python.exe" main.py
) else (
    echo [*] Menggunakan Python Sistem...
    python main.py
)

pause
