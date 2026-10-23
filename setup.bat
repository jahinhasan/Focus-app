@echo off
REM ============================================================
REM Focus V2 - one-command setup for Windows
REM Usage: double-click this file, or run:  setup.bat
REM Creates a virtual environment, installs everything, and
REM launches the app. Safe to re-run any time.
REM ============================================================
cd /d "%~dp0"

echo ==^> [1/5] Checking Python 3.10+ ...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found. Install it from https://www.python.org/downloads/
    echo        IMPORTANT: tick "Add python.exe to PATH" during install!
    pause
    exit /b 1
)
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.10+ required.
    pause
    exit /b 1
)

echo ==^> [2/5] Creating virtual environment (.venv) ...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: could not create the virtual environment.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q

echo ==^> [3/5] Installing Python requirements ...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed - check your internet connection.
    pause
    exit /b 1
)

echo ==^> [4/5] Checking AI support ...
where ollama >nul 2>nul
if errorlevel 1 (
    echo     Ollama not installed ^(optional^). For the local AI:
    echo       1. install from https://ollama.com/download
    echo       2. run:  ollama pull qwen3:4b
    echo     The app works fully without it.
) else (
    echo     Ollama found. If the AI shows offline in the app, run:  ollama serve
    echo     and pull the model with:                                ollama pull qwen3:4b
)

echo ==^> [5/5] Launching Focus ...
python main.py
if errorlevel 1 pause
