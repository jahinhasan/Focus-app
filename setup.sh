#!/usr/bin/env bash
# ============================================================
# Focus V2 - one-command setup for Linux / macOS
# Usage:   bash setup.sh        (or: ./setup.sh)
# Creates a virtual environment, installs everything, and
# launches the app. Safe to re-run any time.
# ============================================================
set -e
cd "$(dirname "$0")"

echo "==> [1/5] Checking Python 3.10+ ..."
PY=python3
if ! command -v $PY >/dev/null 2>&1; then
    echo "ERROR: python3 not found. Install Python 3.10+ first:"
    echo "  Debian/Ubuntu : sudo apt install python3 python3-venv python3-pip"
    echo "  Arch          : sudo pacman -S python"
    echo "  Fedora        : sudo dnf install python3"
    exit 1
fi
VERSION_OK=$($PY -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
if [ "$VERSION_OK" != "1" ]; then
    echo "ERROR: Python 3.10+ required, found $($PY --version)"
    exit 1
fi
echo "    Found $($PY --version)"

echo "==> [2/5] Creating virtual environment (.venv) ..."
$PY -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip -q

echo "==> [3/5] Installing Python requirements ..."
pip install -r requirements.txt

echo "==> [4/5] Checking system GUI + AI support ..."
if ! python -c "import tkinter" 2>/dev/null; then
    echo "    WARNING: tkinter (the GUI library) is missing."
    echo "    Debian/Ubuntu : sudo apt install python3-tk"
    echo "    Fedora        : sudo dnf install python3-tkinter"
    echo "    Arch          : sudo pacman -S tk"
    echo "    (install it, then run this script again)"
fi
if ! python -c "import customtkinter" 2>/dev/null; then
    echo "    WARNING: customtkinter import failed - pip install may have failed."
fi
if command -v ollama >/dev/null 2>&1; then
    if curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "    Ollama is running - local AI ready."
    else
        echo "    Ollama found but not running. Start it with:  ollama serve"
        echo "    Then pull the model:                          ollama pull qwen3:4b"
    fi
else
    echo "    Ollama not installed (optional). For the local AI:"
    echo "      1. install from https://ollama.com/download"
    echo "      2. ollama pull qwen3:4b"
    echo "    The app works fully without it."
fi

echo "==> [5/5] Launching Focus ..."
python main.py
