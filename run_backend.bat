@echo off
title Digital Mart - Backend FastAPI
cd /d "%~dp0"

echo ========================================================
echo   Digital Mart - Server Backend (FastAPI + Uvicorn)
echo ========================================================
echo.

if exist "backend\venv\Scripts\python.exe" (
    echo [*] Menggunakan Python Virtual Environment (backend\venv)...
    "backend\venv\Scripts\python.exe" backend\backend.py
) else (
    echo [*] Menggunakan Python Sistem...
    python backend\backend.py
)

pause
