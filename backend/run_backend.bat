@echo off
title Digital Mart - Backend FastAPI
cd /d "%~dp0"

echo ========================================================
echo   Digital Mart - Server Backend (FastAPI + Uvicorn)
echo ========================================================
echo.

if exist "venv\Scripts\python.exe" (
    echo [*] Menggunakan Virtual Environment (venv)...
    "venv\Scripts\python.exe" backend.py
) else (
    echo [*] Menggunakan Python Sistem...
    python backend.py
)

pause
