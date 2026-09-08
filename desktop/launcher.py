"""POLARIS-AI Windows desktop launcher.

The release shell owns the local API and static frontend lifecycles.  PyWebView
is optional in source checkouts; ``--headless`` validates the same handshake
without opening a native window.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
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


def frontend_server(root: Path, api_port: int = DEFAULT_PORT) -> tuple[ThreadingHTTPServer, int]:
    dist = root / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise RuntimeError(f"Production frontend assets are missing: {dist}")

    class StaticHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist), **kwargs)

        def do_GET(self):
            if self.path in {"/", "/index.html"}:
                content = (dist / "index.html").read_text(encoding="utf-8")
                config = f'<script>window.POLARIS_API_BASE_URL="http://127.0.0.1:{api_port}";</script>'
                body = content.replace("<head>", "<head>" + config).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

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
        POLARIS_FRONTEND_ORIGIN=os.environ.get("POLARIS_FRONTEND_ORIGIN", f"http://127.0.0.1:{port}"),
    )
    if getattr(sys, "frozen", False):
        os.environ.update(env)
        import uvicorn

        from backend.app.main import app

        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name="polaris-backend", daemon=True)
        thread.start()

        class InProcessBackend:
            def poll(self):
                return None if not server.should_exit else 0

            def terminate(self):
                server.should_exit = True

            def wait(self, timeout=None):
                thread.join(timeout=timeout or 30)
                if thread.is_alive():
                    raise subprocess.TimeoutExpired("packaged backend", timeout)

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
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    if digest != "aba2c90463130dae416658715f64a07a7643b89f4514045dedc8744d479e0cc7":
        raise RuntimeError("Champion weights checksum mismatch")
    import torch

    from backend.forecasting.sea_ice.ml.inference import deterministic_inference, load_model

    model = load_model(weights, context_days=7, hidden_channels=24, forcing_variables=3)
    output = deterministic_inference(model, torch.zeros((1, 23, 4, 4)))
    if tuple(output.shape) != (1, 3, 4, 4):
        raise RuntimeError(f"Scientific runtime inference shape mismatch: {tuple(output.shape)}")
    logging.info(
        "model verified version=v0.3 sha256=%s output_shape=%s forcing_variables=3",
        digest, tuple(output.shape),
    )
    return metadata


def run(*, headless: bool = False) -> int:
    started = time.monotonic()
    mutex = None
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = kernel.CreateMutexW(None, False, "Local\\POLARIS-AI-Desktop")
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle(mutex)
            return 0
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
        frontend, frontend_port = frontend_server(root, port)
        os.environ["POLARIS_FRONTEND_ORIGIN"] = f"http://127.0.0.1:{frontend_port}"
        backend = start_backend(root, port, log_path)
        wait_for_backend(port)
        logging.info("backend ready seconds=%.3f", time.monotonic() - started)
        url = f"http://127.0.0.1:{frontend_port}/"
        readiness = {"status": "ready", "backend": port, "frontend": frontend_port, "url": url}
        (appdata_root() / "startup-ready.json").write_text(
                json.dumps(readiness), encoding="utf-8"
            )
        logging.info("desktop ready backend=%s frontend=%s", port, frontend_port)
        if headless:
            print(json.dumps(readiness))
            return 0
        try:
            import webview
        except ImportError as error:
            raise RuntimeError(
                "PyWebView is required for the native Windows desktop shell"
            ) from error
        window = webview.create_window(APP_NAME, url, width=1600, height=1000, min_size=(1100, 720))
        def loaded():
            logging.info("native frontend loaded seconds=%.3f", time.monotonic() - started)
        window.events.loaded += loaded
        webview.start(storage_path=str(appdata_root() / "webview"))
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
        if mutex is not None:
            kernel.CloseHandle(mutex)
        logging.info("desktop shutdown complete")


def main() -> int:
    parser = argparse.ArgumentParser(description="POLARIS-AI desktop shell")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="validate startup without opening a native window",
    )
    parser.add_argument("--validate-demo", action="store_true",
                        help="run isolated synthetic release checks and exit")
    args = parser.parse_args()
    if args.validate_demo:
        from desktop.release_validation import run_demo
        os.chdir(resources_root())
        result = run_demo()
        (appdata_root() / "demo-validation.json").write_text(json.dumps(result), encoding="utf-8")
        return 0
    return run(headless=args.headless)


if __name__ == "__main__":
    raise SystemExit(main())
