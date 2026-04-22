from __future__ import annotations

import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    host = "0.0.0.0"
    port = 18003
    httpd = ThreadingHTTPServer((host, port), lambda *a, **k: _Handler(*a, directory=root, **k))
    print(f"[a2-web] serving {root} on http://{host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

