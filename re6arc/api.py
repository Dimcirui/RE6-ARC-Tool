"""JS-facing API. Every public method returns {"ok": bool, "data": ..., "error": str}."""
from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .service import Workspace

SETTINGS_DEFAULTS: dict[str, Any] = {
    "lang": "zh", "theme": "auto", "view": "details", "convert": "raw", "subfolder": True,
    "overwrite": True, "last_open_dir": "", "last_out_dir": "", "recursive": True,
    "preview": True, "recent": [],
}


def _settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "RE6ArcStudio" / "settings.json"


def safe(fn):
    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        try:
            return {"ok": True, "data": fn(self, *a, **kw)}
        except Exception as ex:  # noqa: BLE001 - surfaced to the UI as a message
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}" if not str(ex) else str(ex)}
    return wrapper


class Api:
    """Public methods are exposed to JavaScript; internals are underscore-prefixed on purpose."""

    def __init__(self, initial_paths: list[str] | None = None):
        self._ws = Workspace()
        self._window = None
        self._initial = initial_paths or []
        self._settings = self._load_settings()
        self._dev_answers: list[Any] = []   # used only by the dev bridge in place of native dialogs

    # -- plumbing ---------------------------------------------------------------

    def _bind(self, window) -> None:
        self._window = window

    def _load_settings(self) -> dict[str, Any]:
        s = dict(SETTINGS_DEFAULTS)
        try:
            s.update(json.loads(_settings_path().read_text("utf-8")))
        except (OSError, ValueError):
            pass
        return s

    def _dialog(self, kind: str, **kw) -> list[str]:
        if self._dev_answers:
            ans = self._dev_answers.pop(0)
            return ans if isinstance(ans, list) else [ans]
        if self._window is None:
            return []
        import webview
        res = self._window.create_file_dialog(getattr(webview.FileDialog, kind), **kw)
        if not res:
            return []
        return [res] if isinstance(res, str) else list(res)

    @safe
    def log_js(self, message: str) -> None:
        """Append a front-end error to ui.log next to the settings file."""
        p = _settings_path().with_name("ui.log")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except OSError:
            pass

    # -- settings / info --------------------------------------------------------

    @safe
    def app_info(self) -> dict[str, Any]:
        return {"settings": self._settings, "initial": self._initial, "version": "1.0.0"}

    @safe
    def set_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        self._settings.update({k: v for k, v in patch.items() if k in SETTINGS_DEFAULTS})
        p = _settings_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self._settings, ensure_ascii=False, indent=2), "utf-8")
        except OSError:
            pass
        return self._settings

    # -- dialogs ------------------------------------------------------------------

    @safe
    def pick_arcs(self) -> list[str]:
        d = self._settings.get("last_open_dir") or ""
        res = self._dialog("OPEN", allow_multiple=True, directory=d,
                           file_types=("ARC archives (*.arc)", "All files (*.*)"))
        if res:
            self.set_settings({"last_open_dir": str(Path(res[0]).parent)})
        return res

    @safe
    def pick_folder(self, remember: str = "last_out_dir") -> str:
        d = self._settings.get(remember) or self._settings.get("last_open_dir") or ""
        res = self._dialog("FOLDER", directory=d)
        if res and remember in self._settings:
            self.set_settings({remember: res[0]})
        return res[0] if res else ""

    @safe
    def pick_file(self, kind: str = "any") -> str:
        types = {"tex": ("Textures (*.dds;*.tex)", "All files (*.*)"),
                 "any": ("All files (*.*)",)}.get(kind, ("All files (*.*)",))
        res = self._dialog("OPEN", allow_multiple=False,
                           directory=self._settings.get("last_open_dir") or "", file_types=types)
        return res[0] if res else ""

    @safe
    def pick_save(self, default_name: str = "out.arc") -> str:
        res = self._dialog("SAVE", save_filename=default_name,
                           directory=self._settings.get("last_open_dir") or "",
                           file_types=("ARC archives (*.arc)",))
        return res[0] if res else ""

    @safe
    def reveal(self, path: str) -> None:
        p = Path(path)
        if sys.platform == "win32":
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(p))  # noqa: S606 - user-chosen local folder

    # -- workspace ----------------------------------------------------------------

    @safe
    def open_paths(self, paths: list[str]) -> dict[str, Any]:
        return self._ws.open_paths(paths)

    @safe
    def close_archive(self, aid: str) -> list[dict[str, Any]]:
        self._ws.close(aid)
        return self._ws.archive_list()

    @safe
    def archives(self) -> list[dict[str, Any]]:
        return self._ws.archive_list()

    @safe
    def rows(self, aid: str) -> list[list[Any]]:
        return self._ws.rows(aid)

    @safe
    def thumb(self, aid: str, path: str, size: int = 128) -> str | None:
        return self._ws.thumb(aid, path, int(size))

    @safe
    def preview(self, aid: str, path: str) -> dict[str, Any]:
        return self._ws.preview(aid, path)

    # -- extract / edit / save ------------------------------------------------------

    @safe
    def extract(self, items: list[dict[str, Any]], out_dir: str, convert: str, subfolder: bool,
                overwrite: bool) -> str:
        self.set_settings({"convert": convert, "subfolder": subfolder, "overwrite": overwrite,
                           "last_out_dir": out_dir})
        return self._ws.start_extract(items, out_dir, convert, subfolder, overwrite)

    @safe
    def stage_replace(self, aid: str, path: str, src: str) -> None:
        self._ws.stage_replace(aid, path, src)

    @safe
    def stage_add(self, aid: str, src: str, virtual_path: str) -> None:
        self._ws.stage_add(aid, src, virtual_path)

    @safe
    def stage_delete(self, aid: str, paths: list[str]) -> None:
        self._ws.stage_delete(aid, paths)

    @safe
    def unstage(self, aid: str, paths: list[str] | None = None) -> None:
        self._ws.unstage(aid, paths)

    @safe
    def stage_folder(self, aid: str, folder: str, include_new: bool = True) -> dict[str, Any]:
        return self._ws.stage_folder(aid, folder, include_new)

    @safe
    def pending(self, aid: str) -> list[dict[str, Any]]:
        l = self._ws.get(aid)
        return [{"kind": e.kind, "path": e.path, "src": str(e.src) if e.src else ""}
                for e in l.edits.values()]

    @safe
    def save(self, aid: str, out_path: str, backup: bool = True) -> str:
        return self._ws.start_save(aid, out_path, backup)

    @safe
    def verify(self, aid: str) -> str:
        return self._ws.start_verify(aid)

    @safe
    def task(self, tid: str) -> dict[str, Any]:
        return self._ws.task(tid)

    @safe
    def cancel(self, tid: str) -> None:
        self._ws.cancel(tid)
