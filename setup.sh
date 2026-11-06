#!/usr/bin/env bash
# Wrapper for Focus Agent V2 One-Click Auto-Setup & Launcher (Linux / macOS)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/run_linux.sh" "$@"
