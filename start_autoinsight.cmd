@echo off
setlocal
set "PROJECT_DIR=%~dp0"

start "AutoInsight Backend" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%PROJECT_DIR%'; python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000"
start "AutoInsight Frontend" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%PROJECT_DIR%frontend'; npm.cmd run dev"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173/"
endlocal
