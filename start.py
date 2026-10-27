"""Start the whole app with one command: backend (FastAPI, :5000) and frontend (Vite, :3000).

    python start.py        (or the Run / Play button in VS Code on this file)

Both run in this one terminal; Ctrl+C (or closing the terminal) stops both. The backend reloads by
itself after changes in server/ (--reload). Needs only the standard library - the backend runs on
server/venv when it exists, otherwise on the Python that started this script.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER, CLIENT = ROOT / "server", ROOT / "client"
BACKEND_PORT, FRONTEND_PORT = 5000, 3000
WINDOWS = os.name == "nt"


def server_python() -> str:
    venv = SERVER / "venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
    return str(venv) if venv.exists() else sys.executable


def port_busy(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def stop(process: subprocess.Popen) -> None:
    """Stop the process with its children (npm -> node, uvicorn reloader -> worker)."""
    if process.poll() is not None:
        return
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    busy = [port for port in (BACKEND_PORT, FRONTEND_PORT) if port_busy(port)]
    if busy:
        print(f"Port {', '.join(map(str, busy))} is already in use - the app (or something else) is probably "
              "running already. Stop it first.")
        return 1
    npm = shutil.which("npm")
    if npm is None:
        print("npm not found - install Node.js (https://nodejs.org) and open a new terminal.")
        return 1
    if not (CLIENT / "node_modules").exists():
        print("First start: installing the frontend packages (npm install)...")
        subprocess.run([npm, "install"], cwd=CLIENT, check=True)

    processes = {
        # an open app keeps connections alive (price polling) - without a timeout a reload never finishes
        "backend": subprocess.Popen([server_python(), "-m", "uvicorn", "main:app", "--port", str(BACKEND_PORT),
                                     "--reload", "--timeout-graceful-shutdown", "3"], cwd=SERVER),
        "frontend": subprocess.Popen([npm, "run", "dev"], cwd=CLIENT),
    }
    print(f"\n  App:     http://localhost:{FRONTEND_PORT}\n  Backend: http://localhost:{BACKEND_PORT}/docs\n"
          "  Ctrl+C stops both.\n", flush=True)
    try:
        while True:
            ended = [name for name, p in processes.items() if p.poll() is not None]
            if ended:
                print(f"\n{ended[0]} stopped (code {processes[ended[0]].returncode}) - stopping the rest.")
                return 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for process in processes.values():
            stop(process)


if __name__ == "__main__":
    sys.exit(main())
