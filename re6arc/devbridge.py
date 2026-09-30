"""Development-only HTTP bridge so the UI can be driven from a normal browser.

    python app.py --dev            # serves http://127.0.0.1:8765/?dev  (loopback only)

POST /api/<method> with a JSON array of positional args calls Api.<method>. Native dialogs are
replaced by answers queued through POST /api/_dev_answer. Not used by the normal desktop app.
"""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .api import Api


def serve(api: Api, ui_dir: Path, port: int = 8765) -> None:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            rel = self.path.split("?", 1)[0].lstrip("/") or "index.html"
            f = (ui_dir / rel).resolve()
            if ui_dir.resolve() not in f.parents or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))

        def do_POST(self):
            if not self.path.startswith("/api/"):
                return self._send(404, b"", "text/plain")
            name = self.path[5:]
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"[]")
            if name == "_dev_answer":
                api._dev_answers.append(args[0])
                res = {"ok": True, "data": None}
            elif name.startswith("_") or not hasattr(api, name):
                res = {"ok": False, "error": "unknown method"}
            else:
                res = getattr(api, name)(*args)
            self._send(200, json.dumps(res).encode(), "application/json")

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
