@echo off
REM =============================================================================
REM Focus Agent V2 — One-Click Launcher for Windows
REM Double-click this file (run_windows.bat) to install everything & start!
REM =============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   Focus Agent V2 — Automatic Setup ^& Launcher (Windows)
echo ========================================================================

REM 1. Check if Python is installed; if not, install via winget
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [Setup] Python not found. Attempting automatic install via winget...
    where winget >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    ) else (
        echo [Error] Python 3 is not installed. Please install Python 3.11+ from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

REM 2. Run the universal setup and launcher script
python "%~dp0setup_and_run.py" %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [Notice] Process exited with code %ERRORLEVEL%.
    pause
)
endlocal

