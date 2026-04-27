from __future__ import annotations

import os
from urllib.parse import quote
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        # Short invite link: /i/<CODE> -> 302 to index.html with invite param.
        try:
            path = str(self.path or "")
            if path.startswith("/i/"):
                code = path[len("/i/") :]
                code = code.split("?", 1)[0].split("#", 1)[0]
                code = code.strip().upper()
                # Basic sanity: allow only A-Z0-9 and length 2..32
                safe = "".join([c for c in code if ("A" <= c <= "Z") or ("0" <= c <= "9")])
                if len(safe) < 2 or len(safe) > 32:
                    self.send_response(302)
                    self.send_header("Location", "/index.html?mode=register")
                    self.end_headers()
                    return
                self.send_response(302)
                self.send_header("Location", f"/index.html?mode=register&i={quote(safe)}")
                self.end_headers()
                return
        except Exception:
            pass
        return super().do_GET()


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    host = "0.0.0.0"
    port = 18001
    httpd = ThreadingHTTPServer((host, port), lambda *a, **k: _Handler(*a, directory=root, **k))
    print(f"[a1-web] serving {root} on http://{host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

