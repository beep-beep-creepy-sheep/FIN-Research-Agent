from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_PORT = int(os.getenv("FINRESEARCH_BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FINRESEARCH_FRONTEND_PORT", "3000"))
LOG_DIR = ROOT / "data" / "logs"


def main() -> int:
    print("Fin Research Agent launcher")
    print("=" * 32)
    ensure_dirs()
    ensure_env_files()
    check_command("python3")
    check_command("node")
    check_command("npm")
    ensure_frontend_dependencies()

    processes: list[subprocess.Popen[str]] = []
    try:
        if port_open(BACKEND_PORT):
            print(f"Backend already appears to be running on port {BACKEND_PORT}.")
        else:
            processes.append(start_backend())

        processes.append(start_worker())

        if port_open(FRONTEND_PORT):
            print(f"Frontend already appears to be running on port {FRONTEND_PORT}.")
        else:
            processes.append(start_frontend())

        wait_for_port(BACKEND_PORT, "backend")
        wait_for_port(FRONTEND_PORT, "frontend")
        url = f"http://localhost:{FRONTEND_PORT}"
        print(f"\nReady: {url}")
        print("Press Ctrl+C to stop services.")
        webbrowser.open(url)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for process in processes:
            stop_process(process)
    return 0


def ensure_dirs() -> None:
    for path in (
        ROOT / "data",
        ROOT / "data" / "documents",
        ROOT / "data" / "raw",
        ROOT / "data" / "reports",
        ROOT / "data" / "exports",
        LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def ensure_env_files() -> None:
    copy_if_missing(ROOT / "backend" / ".env.example", ROOT / "backend" / ".env")
    copy_if_missing(ROOT / "frontend" / ".env.local.example", ROOT / "frontend" / ".env.local")


def copy_if_missing(source: Path, target: Path) -> None:
    if source.exists() and not target.exists():
        shutil.copy2(source, target)
        print(f"Created {target.relative_to(ROOT)}")


def check_command(command: str) -> None:
    if shutil.which(command) is None:
        raise RuntimeError(f"Missing command: {command}")


def ensure_frontend_dependencies() -> None:
    node_modules = ROOT / "frontend" / "node_modules"
    if node_modules.exists():
        return
    print("Installing frontend dependencies. This can take a few minutes on first run...")
    run_logged(["npm", "install"], cwd=ROOT / "frontend", log_name="npm-install.log")


def start_backend() -> subprocess.Popen[str]:
    print(f"Starting backend on port {BACKEND_PORT}...")
    return popen_logged(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "finresearch.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=ROOT,
        log_name="backend.log",
        env=python_env(),
    )


def start_worker() -> subprocess.Popen[str]:
    print("Starting worker...")
    return popen_logged(
        [sys.executable, "-m", "finresearch.worker"],
        cwd=ROOT,
        log_name="worker.log",
        env=python_env(),
    )


def start_frontend() -> subprocess.Popen[str]:
    print(f"Starting frontend on port {FRONTEND_PORT}...")
    return popen_logged(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(FRONTEND_PORT)],
        cwd=ROOT / "frontend",
        log_name="frontend.log",
    )


def python_env() -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(ROOT), str(ROOT / "backend" / "src")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env.setdefault("DATA_DIR", str(ROOT / "data"))
    env.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'finresearch.sqlite'}")
    return env


def run_logged(argv: list[str], cwd: Path, log_name: str) -> None:
    with (LOG_DIR / log_name).open("a", encoding="utf-8") as log:
        completed = subprocess.run(argv, cwd=cwd, stdout=log, stderr=log, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(argv)}. See data/logs/{log_name}")


def popen_logged(
    argv: list[str],
    cwd: Path,
    log_name: str,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    log = (LOG_DIR / log_name).open("a", encoding="utf-8")
    return subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=log,
        stderr=log,
        text=True,
        start_new_session=True,
    )


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, label: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_open(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {label} on port {port}")


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=8)
    except Exception:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
