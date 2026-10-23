"""PassPortIQ Desktop GUI Launcher.

Launches the unified PassPortIQ application inside a native desktop window:
- Embedded FastAPI backend (OCR, MRZ & VIZ extraction pipeline)
- Embedded React frontend Single Page Application
- Native desktop window powered by Edge WebView2 / pywebview (with fallback)
"""

from __future__ import annotations

import os
import sys
import time
import socket
import threading
import urllib.request
import webbrowser
import subprocess

# PyInstaller windowed mode (noconsole) nullifies stdout and stderr on Windows
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure backend package is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    BUNDLE_DIR = BASE_DIR

BACKEND_DIR = os.path.join(BUNDLE_DIR, "backend")
if os.path.isdir(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
elif BUNDLE_DIR not in sys.path:
    sys.path.insert(0, BUNDLE_DIR)


def find_available_port(default_port: int = 8000) -> int:
    """Check if default_port is available; otherwise find a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", default_port))
            return default_port
        except OSError:
            pass

    # Find free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_server(url: str, timeout_seconds: float = 15.0) -> bool:
    """Poll health endpoint until backend server is responsive."""
    health_url = f"{url}/health/live"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def start_backend_server(host: str, port: int) -> None:
    """Run uvicorn server in background thread."""
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )


def open_fallback_window(target_url: str) -> None:
    """Fallback if pywebview native window is unavailable: open browser app mode."""
    # Try opening Edge in PWA/App mode (borderless standalone app window)
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for edge in edge_paths:
        if os.path.isfile(edge):
            try:
                subprocess.Popen([edge, f"--app={target_url}"])
                return
            except Exception:
                pass

    # Generic browser open
    webbrowser.open(target_url)


def main() -> None:
    host = "127.0.0.1"
    port = find_available_port(8000)
    target_url = f"http://{host}:{port}"

    # Start FastAPI server in daemon thread
    server_thread = threading.Thread(
        target=start_backend_server,
        args=(host, port),
        daemon=True,
    )
    server_thread.start()

    # Wait for server ready
    server_ok = wait_for_server(target_url, timeout_seconds=20.0)
    if not server_ok:
        print("Warning: Backend took longer than expected to report ready; launching window anyway.")

    # Try pywebview native window
    use_native_window = True
    try:
        import webview

        window = webview.create_window(
            title="PassPortIQ — Intelligent Passport Data Extraction & Verification",
            url=target_url,
            width=1320,
            height=900,
            min_size=(980, 650),
            confirm_close=False,
        )
        webview.start()
    except Exception as exc:
        use_native_window = False
        print(f"pywebview unavailable or failed ({exc}). Launching fallback browser window...")
        open_fallback_window(target_url)
        # Keep main thread alive while background server runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
