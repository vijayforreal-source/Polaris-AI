import urllib.request

from desktop.launcher import frontend_server


def test_packaged_frontend_receives_selected_backend_port(tmp_path):
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html><head></head><body>app</body></html>")
    server, port = frontend_server(tmp_path, 8017)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
            html = response.read().decode()
        assert 'window.POLARIS_API_BASE_URL="http://127.0.0.1:8017"' in html
        assert html.index("POLARIS_API_BASE_URL") < html.index("</head>")
    finally:
        server.shutdown()
        server.server_close()
