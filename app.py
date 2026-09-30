"""RE6 ARC Studio - entry point.

    python app.py [file.arc | folder ...]
    python app.py --dev            # browser-driven UI on http://127.0.0.1:8765/?dev (development only)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# PyInstaller onefile unpacks bundled data under sys._MEIPASS
ROOT = Path(getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent)
UI = ROOT / "ui"

sys.path.insert(0, str(ROOT))

from re6arc.api import Api  # noqa: E402


def main(argv: list[str]) -> int:
    dev = "--dev" in argv
    paths = [a for a in argv if not a.startswith("--")]
    api = Api(initial_paths=[str(Path(p).resolve()) for p in paths if Path(p).exists()])

    if dev:
        from re6arc.devbridge import serve
        print("dev bridge on http://127.0.0.1:8765/?dev  (Ctrl+C to stop)")
        serve(api, UI)
        return 0

    import webview
    from webview.dom import DOMEventHandler

    window = webview.create_window(
        "RE6 ARC Studio", str(UI / "index.html"), js_api=api,
        width=1360, height=840, min_size=(980, 620), background_color="#0b0b0f")
    api._bind(window)

    def on_drop(e):
        files = (e.get("dataTransfer") or {}).get("files") or []
        dropped = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if dropped:
            window.evaluate_js(f"App.onDropped({json.dumps(dropped)})")

    def ready():
        doc = window.dom.document
        doc.events.dragover += DOMEventHandler(lambda e: None, True, True)
        doc.events.drop += DOMEventHandler(on_drop, True, True)

    webview.start(ready)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
