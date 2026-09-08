"""POLARIS-AI Windows desktop launcher.

The release shell owns the local API and static frontend lifecycles.  PyWebView
is optional in source checkouts; ``--headless`` validates the same handshake
without opening a native window.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "POLARIS-AI"
DEFAULT_PORT = 8000
HEALTH_TIMEOUT_SECONDS = 45


def resources_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    source_root = Path(__file__).resolve().parents[1]
    return Path(os.environ.get("POLARIS_RESOURCES", bundled_root or source_root)).resolve()


def appdata_root() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    return root


def choose_port(preferred: int = DEFAULT_PORT) -> int:
    for port in (preferred, *range(preferred + 1, preferred + 21)):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No available localhost port for the POLARIS backend")


def frontend_server(root: Path) -> tuple[ThreadingHTTPServer, int]:
    dist = root / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise RuntimeError(f"Production frontend assets are missing: {dist}")

    class StaticHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist), **kwargs)

        def log_message(self, format, *args):  # noqa: A002
            logging.getLogger("polaris.desktop.frontend").info(format, *args)

    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
    threading.Thread(target=server.serve_forever, name="polaris-frontend", daemon=True).start()
    return server, server.server_port


def wait_for_backend(port: int, timeout: float = HEALTH_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_error = "backend did not respond"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, urllib.error.URLError) as error:
            last_error = str(error)
        time.sleep(0.25)
    raise RuntimeError(f"Backend startup timeout: {last_error}")


def start_backend(root: Path, port: int, log_path: Path):
    env = os.environ.copy()
    env.update(
        POLARIS_API_HOST="127.0.0.1",
        POLARIS_API_PORT=str(port),
        POLARIS_FRONTEND_ORIGIN=f"http://127.0.0.1:{port}",
    )
    if getattr(sys, "frozen", False):
        import uvicorn

        from backend.app.main import app

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None)
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, name="polaris-backend", daemon=True).start()

        class InProcessBackend:
            def poll(self):
                return None if not server.should_exit else 0

            def terminate(self):
                server.should_exit = True

            def wait(self, timeout=None):
                deadline = time.monotonic() + (timeout or 30)
                while not server.should_exit and time.monotonic() < deadline:
                    time.sleep(0.1)

            def kill(self):
                server.should_exit = True

        return InProcessBackend()
    log_file = log_path.open("a", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    return subprocess.Popen(command, cwd=root, env=env, stdout=log_file, stderr=subprocess.STDOUT)


def verify_model(root: Path) -> dict:
    champion = root / "backend" / "forecasting" / "sea_ice" / "ml" / "champion.json"
    metadata = json.loads(champion.read_text(encoding="utf-8"))
    if metadata.get("model_version") != "v0.3":
        raise RuntimeError("Scientific runtime model mismatch: expected champion v0.3")
    weights = root / metadata["weights_path"]
    if not weights.is_file():
        raise RuntimeError(f"Scientific runtime weights are missing: {weights}")
    import torch

    from backend.forecasting.sea_ice.ml.inference import deterministic_inference, load_model

    model = load_model(weights, context_days=7, hidden_channels=24, forcing_variables=3)
    output = deterministic_inference(model, torch.zeros((1, 23, 4, 4)))
    if tuple(output.shape) != (1, 3, 4, 4):
        raise RuntimeError(f"Scientific runtime inference shape mismatch: {tuple(output.shape)}")
    return metadata


def run(*, headless: bool = False) -> int:
    root = resources_root()
    os.chdir(root)
    log_path = appdata_root() / "logs" / "polaris-desktop.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    backend = None
    frontend = None
    try:
        verify_model(root)
        port = choose_port(int(os.environ.get("POLARIS_API_PORT", DEFAULT_PORT)))
        backend = start_backend(root, port, log_path)
        wait_for_backend(port)
        frontend, frontend_port = frontend_server(root)
        url = f"http://127.0.0.1:{frontend_port}/"
        if headless:
            readiness = {"status": "ready", "backend": port, "frontend": frontend_port, "url": url}
            (appdata_root() / "startup-ready.json").write_text(
                json.dumps(readiness), encoding="utf-8"
            )
            logging.info("desktop ready backend=%s frontend=%s", port, frontend_port)
            print(json.dumps(readiness))
            return 0
        try:
            import webview
        except ImportError as error:
            raise RuntimeError(
                "PyWebView is required for the native Windows desktop shell"
            ) from error
        webview.create_window(APP_NAME, url, width=1600, height=1000, min_size=(1100, 720))
        webview.start()
        return 0
    except Exception as error:
        logging.exception("desktop startup failed")
        print(f"POLARIS-AI startup failed. See {log_path}: {error}", file=sys.stderr)
        return 1
    finally:
        if frontend is not None:
            frontend.shutdown()
            frontend.server_close()
        if backend is not None and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=8)
            except subprocess.TimeoutExpired:
                backend.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="POLARIS-AI desktop shell")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="validate startup without opening a native window",
    )
    return run(headless=parser.parse_args().headless)


if __name__ == "__main__":
    raise SystemExit(main())
