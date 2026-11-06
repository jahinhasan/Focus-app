#!/usr/bin/env python3
"""
=============================================================================
Focus Agent V2 — Universal One-Click Auto-Installer & Launcher
Works on both Windows and Linux with zero manual configuration.
=============================================================================
What this script does automatically:
1. Creates a local Python virtual environment (.venv) if not present.
2. Upgrades pip and installs all required Python packages (requirements.txt).
3. Checks if Ollama (Local LLM Engine) is installed; installs it if missing.
4. Starts the Ollama background server (http://localhost:11434) if not running.
5. Pulls the default local AI model (qwen3:4b) if not already downloaded.
6. Launches Focus Agent V2 (main.py).
"""

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import json

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT_DIR, ".venv")
REQ_FILE = os.path.join(ROOT_DIR, "requirements.txt")
MAIN_FILE = os.path.join(ROOT_DIR, "main.py")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"


def banner(msg: str) -> None:
    print(f"\n{'=' * 72}\n[Focus Agent Setup] {msg}\n{'=' * 72}", flush=True)


def get_venv_python() -> str:
    if platform.system().lower().startswith("win"):
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def ensure_venv() -> str:
    """Create .venv if missing and return path to the venv python executable."""
    vpy = get_venv_python()
    if os.path.exists(vpy):
        print(f"✓ Virtual environment found at: {VENV_DIR}")
        return vpy

    banner("Step 1/5: Creating Python Virtual Environment (.venv)...")
    try:
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
    except subprocess.CalledProcessError:
        if platform.system().lower() == "linux" and shutil.which("apt-get"):
            print("Installing python3-venv and python3-tk via apt...")
            subprocess.call(["sudo", "apt-get", "update", "-y"])
            subprocess.call(["sudo", "apt-get", "install", "-y", "python3-venv", "python3-tk", "flac"])
            subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
        else:
            raise
    return vpy


def ensure_requirements(vpy: str) -> None:
    """Install all dependencies from requirements.txt into .venv."""
    stamp_file = os.path.join(VENV_DIR, ".deps_installed.stamp")
    req_mtime = os.path.getmtime(REQ_FILE) if os.path.exists(REQ_FILE) else 0
    if os.path.exists(stamp_file):
        try:
            if os.path.getmtime(stamp_file) >= req_mtime:
                print("✓ Python dependencies are already up to date.")
                return
        except OSError:
            pass

    banner("Step 2/5: Installing Python Dependencies from requirements.txt...")
    subprocess.call([vpy, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    subprocess.check_call([vpy, "-m", "pip", "install", "-r", REQ_FILE])
    try:
        with open(stamp_file, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except OSError:
        pass
    print("✓ All Python requirements installed successfully.")


def find_ollama_bin() -> str | None:
    """Locate the ollama binary across PATH and standard Windows/Linux install paths."""
    found = shutil.which("ollama")
    if found:
        return found
    if platform.system().lower().startswith("win"):
        local_app = os.environ.get("LOCALAPPDATA", "")
        win_path = os.path.join(local_app, "Programs", "Ollama", "ollama.exe")
        if os.path.exists(win_path):
            return win_path
    else:
        for p in ("/usr/local/bin/ollama", "/usr/bin/ollama", os.path.expanduser("~/.local/bin/ollama")):
            if os.path.exists(p):
                return p
    return None


def install_ollama() -> str | None:
    """Automatically download and install Ollama if it is not installed."""
    existing = find_ollama_bin()
    if existing:
        print(f"✓ Ollama is installed ({existing})")
        return existing

    banner("Step 3/5: Installing Ollama (Local AI Engine)...")
    sys_name = platform.system().lower()
    try:
        if sys_name.startswith("linux") or sys_name == "darwin":
            subprocess.check_call("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
        elif sys_name.startswith("win"):
            if shutil.which("winget"):
                print("Installing Ollama via winget...")
                subprocess.call([
                    "winget", "install", "-e", "--id", "Ollama.Ollama",
                    "--accept-package-agreements", "--accept-source-agreements"
                ])
            if not find_ollama_bin():
                installer_path = os.path.join(ROOT_DIR, "OllamaSetup.exe")
                print("Downloading OllamaSetup.exe from https://ollama.com/download/OllamaSetup.exe ...")
                urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", installer_path)
                print("Running Ollama installer...")
                subprocess.call([installer_path, "/SILENT"])
                try:
                    os.remove(installer_path)
                except OSError:
                    pass
    except Exception as exc:
        print(f"⚠ Could not auto-install Ollama ({exc}). App will still run with deterministic/hybrid fallback.")
    return find_ollama_bin()


def ollama_server_alive() -> tuple[bool, list[str]]:
    """Return (alive, list_of_installed_model_names)."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
                models = [m.get("name", "") for m in payload.get("models", [])]
                return True, models
    except Exception:
        pass
    return False, []


def ensure_ollama_running_and_model(ollama_bin: str | None) -> None:
    """Start `ollama serve` if needed and pull `qwen3:4b` if missing."""
    alive, models = ollama_server_alive()
    if not alive and ollama_bin:
        banner("Step 4/5: Starting Ollama Local AI Server...")
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if platform.system().lower().startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen([ollama_bin, "serve"], **kwargs)
            for _ in range(15):
                time.sleep(1)
                alive, models = ollama_server_alive()
                if alive:
                    break
        except Exception as exc:
            print(f"⚠ Could not start ollama serve automatically: {exc}")

    if not alive:
        print("ℹ Ollama server is not running; Focus Agent will use its built-in Deterministic + Online Hybrid mode.")
        return

    print(f"✓ Ollama server is online at {OLLAMA_URL}")
    target_base = DEFAULT_MODEL.split(":")[0]
    has_model = DEFAULT_MODEL in models or any(m.split(":")[0] == target_base for m in models)
    if has_model:
        print(f"✓ Local AI model '{DEFAULT_MODEL}' is ready.")
        return

    if ollama_bin:
        banner(f"Step 5/5: Downloading Local AI Model '{DEFAULT_MODEL}' (first-time setup)...")
        try:
            subprocess.check_call([ollama_bin, "pull", DEFAULT_MODEL])
            print(f"✓ Model '{DEFAULT_MODEL}' downloaded and ready!")
        except Exception as exc:
            print(f"⚠ Could not pull '{DEFAULT_MODEL}' ({exc}). Continuing with fallback parser.")


def main() -> int:
    os.chdir(ROOT_DIR)
    args = sys.argv[1:]

    vpy = ensure_venv()
    ensure_requirements(vpy)
    ollama_bin = install_ollama()
    ensure_ollama_running_and_model(ollama_bin)

    if "--setup-only" in args:
        banner("Setup Complete! Ready to run Focus Agent V2.")
        return 0

    if "--test" in args:
        banner("Running Automated Test Suite & Evaluation Benchmark...")
        rc1 = subprocess.call([vpy, "-m", "pytest", "tests/", "-q"])
        rc2 = subprocess.call([vpy, "evaluate.py"])
        return rc1 or rc2

    banner("Launching Focus Agent V2...")
    return subprocess.call([vpy, MAIN_FILE])


if __name__ == "__main__":
    sys.exit(main())

