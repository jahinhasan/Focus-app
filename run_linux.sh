#!/usr/bin/env bash
# =============================================================================
# Focus Agent V2 — One-Click Launcher for Linux & macOS
# Usage:
#   ./run_linux.sh              (Installs everything needed + launches the app)
#   ./run_linux.sh --setup-only (Only installs dependencies & AI model)
#   ./run_linux.sh --test       (Runs 227 unit tests + 49/49 benchmark)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "  🚀 Focus Agent V2 — Automatic Setup & Launcher (Linux / macOS)"
echo "========================================================================"

# 1. Ensure Python 3 & Tkinter are present on Linux
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 not found. Installing Python 3..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip python3-tk curl flac
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-tkinter curl flac
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm python python-pip tk curl flac
    fi
fi

# Check if python3-tk is available; install if missing on Debian/Ubuntu
CHECK_PY="python3"
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    CHECK_PY="$SCRIPT_DIR/.venv/bin/python"
fi
if ! "$CHECK_PY" -c "import tkinter" >/dev/null 2>&1; then
    echo "Installing python3-tk and python3-venv..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -y && sudo apt-get install -y python3-tk python3-venv flac
    fi
fi

# 2. Hand off to universal Python setup & launcher
exec "$CHECK_PY" "$SCRIPT_DIR/setup_and_run.py" "$@"
