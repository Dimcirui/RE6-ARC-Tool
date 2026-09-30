"""Workspace logic behind the UI (no GUI imports, so it is unit-testable)."""
from __future__ import annotations

import base64
import io
import itertools
import shutil
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import arc, tex

CONVERT_MODES = ("raw", "dds", "png")
HEX_PREVIEW_BYTES = 2048


# --- staged edits ------------------------------------------------------------

@dataclass
class Edit:
    kind: str                  # replace | add | delete
    path: str                  # virtual path with extension
    src: Path | None = None    # file on disk for replace / add


@dataclass
class Loaded:
    id: str
    arc: arc.Archive
    edits: dict[str, Edit] = field(default_factory=dict)   # key = path.lower()

    @property
    def name(self) -> str:
        return self.arc.path.name


# --- tasks -------------------------------------------------------------------

@dataclass
class Task:
    id: str
    title: str
    total: int = 0
    done: int = 0
    current: str = ""
    state: str = "running"     # running | done | error | cancelled
    errors: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    cancel: bool = False

    def snapshot(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "total": self.total, "done": self.done,
                "current": self.current, "state": self.state, "errors": self.errors[-50:],
                "error_count": len(self.errors), "result": self.result}


class _LRU:
    def __init__(self, cap: int):
        self.cap, self.d, self.lock = cap, OrderedDict(), threading.Lock()

    def get(self, k):
        with self.lock:
            if k in self.d:
                self.d.move_to_end(k)
                return self.d[k]

    def put(self, k, v):
        with self.lock:
            self.d[k] = v
            self.d.move_to_end(k)
            while len(self.d) > self.cap:
                self.d.popitem(last=False)


# --- workspace ---------------------------------------------------------------

class Workspace:
    def __init__(self):
        self.loaded: dict[str, Loaded] = {}
        self.tasks: dict[str, Task] = {}
        self._ids = itertools.count(1)
        self._thumbs = _LRU(768)
        self._lock = threading.RLock()

    # -- archives -------------------------------------------------------------

    def open_paths(self, paths: list[str]) -> dict[str, Any]:
        """Open .arc files and folders (folders are scanned recursively for .arc)."""
        found: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                found.extend(sorted(p.rglob("*.arc")))
            elif p.is_file():
                found.append(p)
        opened, errors = [], []
        have = {l.arc.path.resolve(): l.id for l in self.loaded.values()}
        for p in found:
            try:
                key = p.resolve()
                if key in have:
                    opened.append(have[key])
                    continue
                a = arc.parse(p)
                lid = f"a{next(self._ids)}"
                with self._lock:
                    self.loaded[lid] = Loaded(lid, a)
                have[key] = lid
                opened.append(lid)
            except Exception as ex:  # noqa: BLE001 - reported to the UI per file
                errors.append(f"{p.name}: {ex}")
        return {"opened": opened, "errors": errors, "archives": self.archive_list()}

    def close(self, aid: str) -> None:
        with self._lock:
            self.loaded.pop(aid, None)

    def get(self, aid: str) -> Loaded:
        try:
            return self.loaded[aid]
        except KeyError:
            raise arc.ArcError("Archive is not open") from None

    def archive_list(self) -> list[dict[str, Any]]:
        return [{"id": l.id, "name": l.name, "path": str(l.arc.path), "size": l.arc.size,
                 "count": len(l.arc.entries), "edits": len(l.edits)} for l in self.loaded.values()]

    def rows(self, aid: str) -> list[list[Any]]:
        """[path, ext, comp_size, size, offset, status] per entry, in ARC order, then added files."""
        l = self.get(aid)
        out = []
        for e in l.arc.entries:
            ed = l.edits.get(e.path.lower())
            status = "" if ed is None else ("deleted" if ed.kind == "delete" else "modified")
            out.append([e.path, e.ext, e.comp_size, e.size, e.offset, status])
        for ed in l.edits.values():
            if ed.kind == "add":
                size = ed.src.stat().st_size if ed.src and ed.src.exists() else 0
                out.append([ed.path, ed.path.rpartition(".")[2].lower(), 0, size, 0, "added"])
        return out

    # -- reading --------------------------------------------------------------

    def _entry(self, l: Loaded, path: str) -> arc.Entry:
        e = l.arc.by_path().get(path.lower())
        if e is None:
            raise arc.ArcError(f"Not in archive: {path}")
        return e

    def read(self, aid: str, path: str) -> bytes:
        l = self.get(aid)
        ed = l.edits.get(path.lower())
        if ed and ed.kind == "add" and ed.src:
            return ed.src.read_bytes()
        return arc.read_entry(l.arc, self._entry(l, path))

    def thumb(self, aid: str, path: str, size: int = 128) -> str | None:
        l = self.get(aid)
        key = (l.arc.path, l.arc.size, path.lower(), size)
        hit = self._thumbs.get(key)
        if hit is not None:
            return hit or None
        result = ""
        try:
            img, _ = tex.decode(self.read(aid, path), max_dim=size)
            img.thumbnail((size, size))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            result = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:  # noqa: BLE001 - not previewable; cache the miss
            result = ""
        self._thumbs.put(key, result)
        return result or None

    def preview(self, aid: str, path: str) -> dict[str, Any]:
        data = self.read(aid, path)
        info: dict[str, Any] = {"path": path, "size": len(data), "magic": _magic(data)}
        if path.lower().endswith(".tex"):
            try:
                img, t = tex.decode(data, max_dim=1024)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                info.update(kind="image", width=t.width, height=t.height, mips=t.mips,
                            images=t.images, format=t.layout_name, format_code=t.fmt,
                            shown=f"{img.width}x{img.height}",
                            image="data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
                return info
            except tex.TexError as ex:
                info["note"] = str(ex)
        info.update(kind="hex", hex=_hexdump(data[:HEX_PREVIEW_BYTES]),
                    truncated=len(data) > HEX_PREVIEW_BYTES)
        return info

    # -- extraction -----------------------------------------------------------

    def start_extract(self, items: list[dict[str, Any]], out_dir: str, convert: str = "raw",
                      subfolder: bool = True, overwrite: bool = True) -> str:
        """items: [{"archive": id, "paths": [...] | None}] (None = every entry)."""
        if convert not in CONVERT_MODES:
            raise arc.ArcError(f"Unknown conversion mode: {convert}")
        out_root = Path(out_dir)
        jobs: list[tuple[Loaded, list[str]]] = []
        for it in items:
            l = self.get(it["archive"])
            paths = it.get("paths")
            if paths is None:
                paths = [e.path for e in l.arc.entries]
            jobs.append((l, list(paths)))
        task = self._new_task("extract", sum(len(p) for _, p in jobs))
        threading.Thread(target=self._run_extract, daemon=True,
                         args=(task, jobs, out_root, convert, subfolder, overwrite)).start()
        return task.id

    def _run_extract(self, task, jobs, out_root, convert, subfolder, overwrite):
        written = skipped = 0
        try:
            for l, paths in jobs:
                base = out_root / l.arc.path.stem if subfolder else out_root
                by_path = l.arc.by_path()
                with l.arc.path.open("rb") as fh:
                    for p in paths:
                        if task.cancel:
                            task.state = "cancelled"
                            return
                        task.current = p
                        try:
                            e = by_path[p.lower()]
                            data = arc.inflate(arc.read_raw(fh, e), e)
                            rel = e.path
                            if e.ext == "tex" and convert != "raw":
                                try:
                                    data = tex.to_dds(data) if convert == "dds" else tex.to_png(data)
                                    rel = e.name + "." + convert
                                except tex.TexError:
                                    pass  # keep the raw .tex when it cannot be converted
                            dest = arc.safe_join(base, rel)
                            if dest.exists() and not overwrite:
                                skipped += 1
                            else:
                                dest.parent.mkdir(parents=True, exist_ok=True)
                                dest.write_bytes(data)
                                written += 1
                        except Exception as ex:  # noqa: BLE001
                            task.errors.append(f"{p}: {ex}")
                        task.done += 1
            task.result = {"written": written, "skipped": skipped, "out_dir": str(out_root)}
            task.state = "done"
        except Exception as ex:  # noqa: BLE001
            task.errors.append(str(ex))
            task.state = "error"

    # -- staged edits ---------------------------------------------------------

    def stage_replace(self, aid: str, path: str, src: str) -> None:
        l = self.get(aid)
        srcp = Path(src)
        if not srcp.is_file():
            raise arc.ArcError(f"File not found: {src}")
        e = l.arc.by_path().get(path.lower())
        if e is None:
            raise arc.ArcError(f"Not in archive: {path}")
        self._check_replacement(l, e, srcp)
        l.edits[path.lower()] = Edit("replace", e.path, srcp)

    def stage_add(self, aid: str, src: str, virtual_path: str) -> None:
        l = self.get(aid)
        virtual_path = virtual_path.replace("\\", "/").lstrip("/")
        arc.split_path(virtual_path)  # validates extension
        if not Path(src).is_file():
            raise arc.ArcError(f"File not found: {src}")
        if virtual_path.lower() in l.arc.by_path():
            raise arc.ArcError(f"Already in archive, use Replace: {virtual_path}")
        l.edits[virtual_path.lower()] = Edit("add", virtual_path, Path(src))

    def stage_delete(self, aid: str, paths: list[str]) -> None:
        l = self.get(aid)
        exist = l.arc.by_path()
        for p in paths:
            k = p.lower()
            if k in exist:
                l.edits[k] = Edit("delete", exist[k].path)
            elif k in l.edits and l.edits[k].kind == "add":
                del l.edits[k]

    def unstage(self, aid: str, paths: list[str] | None = None) -> None:
        l = self.get(aid)
        if paths is None:
            l.edits.clear()
        for p in paths or []:
            l.edits.pop(p.lower(), None)

    def _check_replacement(self, l: Loaded, e: arc.Entry, src: Path) -> None:
        """Fail early with a readable message if the replacement cannot be written."""
        self._replacement_bytes(l, e, src)

    def _replacement_bytes(self, l: Loaded, e: arc.Entry, src: Path) -> bytes:
        data = src.read_bytes()
        if e.ext == "tex" and src.suffix.lower() == ".dds":
            return tex.from_dds(arc.read_entry(l.arc, e), data)
        return data

    def stage_folder(self, aid: str, folder: str, include_new: bool = True) -> dict[str, Any]:
        """Compare an extracted folder with the archive and stage every difference."""
        l = self.get(aid)
        root = Path(folder)
        if not root.is_dir():
            raise arc.ArcError(f"Not a folder: {folder}")
        if (root / l.arc.path.stem).is_dir():
            root = root / l.arc.path.stem
        entries = l.arc.entries
        known = {e.path.lower() for e in entries}
        claimed: set[Path] = set()
        results: list[dict[str, Any]] = []
        l.edits.clear()
        with l.arc.path.open("rb") as fh:
            for e in entries:
                cand = None
                for rel in (e.path, e.name + ".dds" if e.ext == "tex" else None):
                    if rel is None:
                        continue
                    try:
                        c = arc.safe_join(root, rel)
                    except arc.ArcError:
                        continue
                    if c.is_file():
                        cand = c
                        break
                if cand is None:
                    continue
                claimed.add(cand.resolve())
                row = {"path": e.path, "src": str(cand), "status": "unchanged", "error": ""}
                try:
                    orig = arc.inflate(arc.read_raw(fh, e), e)
                    new = cand.read_bytes()
                    if cand.suffix.lower() == ".dds" and e.ext == "tex":
                        try:
                            same = tex.to_dds(orig) == new
                        except tex.TexError:
                            same = False
                        if not same:
                            tex.from_dds(orig, new)  # validate
                    else:
                        same = orig == new
                    if not same:
                        row["status"] = "modified"
                        l.edits[e.path.lower()] = Edit("replace", e.path, cand)
                except Exception as ex:  # noqa: BLE001
                    row.update(status="error", error=str(ex))
                results.append(row)
        ignored = 0
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.resolve() in claimed:
                continue
            rel = f.relative_to(root).as_posix()
            if rel.lower() in known or f.suffix.lower() in (".txt", ".json", ".bak", ".png"):
                ignored += 1
                continue
            try:
                arc.split_path(rel)
                ascii_ok = rel.isascii()
            except arc.ArcError:
                ascii_ok = False
            if not ascii_ok:
                ignored += 1
                continue
            row = {"path": rel, "src": str(f), "status": "new" if include_new else "ignored", "error": ""}
            if include_new:
                l.edits[rel.lower()] = Edit("add", rel, f)
            else:
                ignored += 1
            results.append(row)
        return {"root": str(root), "results": results, "ignored": ignored,
                "modified": sum(r["status"] == "modified" for r in results),
                "new": sum(r["status"] == "new" for r in results),
                "errors": sum(r["status"] == "error" for r in results)}

    # -- saving ---------------------------------------------------------------

    def start_save(self, aid: str, out_path: str, backup: bool = True) -> str:
        l = self.get(aid)
        task = self._new_task("save", len(l.arc.entries) + sum(e.kind == "add" for e in l.edits.values()))
        threading.Thread(target=self._run_save, daemon=True, args=(task, l, Path(out_path), backup)).start()
        return task.id

    def _run_save(self, task: Task, l: Loaded, out: Path, backup: bool):
        try:
            items: list[arc.Item] = []
            changed = removed = added = 0
            with l.arc.path.open("rb") as fh:
                for e in l.arc.entries:
                    task.current = e.path
                    ed = l.edits.get(e.path.lower())
                    if ed and ed.kind == "delete":
                        removed += 1
                    elif ed and ed.kind == "replace":
                        data = self._replacement_bytes(l, e, ed.src)
                        items.append(arc.Item(e.name, e.type_hash, len(data), e.flags, data=data))
                        changed += 1
                    else:
                        items.append(arc.Item(e.name, e.type_hash, e.size, e.flags, raw_comp=arc.read_raw(fh, e)))
                    task.done += 1
            for ed in l.edits.values():
                if ed.kind != "add":
                    continue
                task.current = ed.path
                name, th = arc.split_path(ed.path)
                data = ed.src.read_bytes()
                items.append(arc.Item(name, th, len(data), arc.DEFAULT_FLAGS, data=data))
                added += 1
                task.done += 1
            if not items:
                raise arc.ArcError("Nothing to write: every entry was deleted")
            same_file = out.exists() and out.resolve() == l.arc.path.resolve()
            bak = None
            if same_file and backup:
                bak = out.with_name(out.name + ".bak")
                if not bak.exists():
                    shutil.copy2(out, bak)
            arc.write_archive(out, items)
            if same_file:
                l.arc = arc.parse(out)
                l.edits.clear()
            task.result = {"out": str(out), "modified": changed, "added": added, "removed": removed,
                           "entries": len(items), "size": out.stat().st_size,
                           "backup": str(bak) if bak else "", "reloaded": same_file}
            task.state = "done"
        except Exception as ex:  # noqa: BLE001
            task.errors.append(str(ex))
            task.state = "error"

    # -- verification -----------------------------------------------------------

    def start_verify(self, aid: str) -> str:
        l = self.get(aid)
        task = self._new_task("verify", len(l.arc.entries))

        def run():
            bad = 0
            try:
                with l.arc.path.open("rb") as fh:
                    for e in l.arc.entries:
                        task.current = e.path
                        try:
                            arc.inflate(arc.read_raw(fh, e), e)
                        except Exception as ex:  # noqa: BLE001
                            bad += 1
                            task.errors.append(f"{e.path}: {ex}")
                        task.done += 1
                task.result = {"checked": len(l.arc.entries), "bad": bad}
                task.state = "done"
            except Exception as ex:  # noqa: BLE001
                task.errors.append(str(ex))
                task.state = "error"

        threading.Thread(target=run, daemon=True).start()
        return task.id

    # -- tasks ----------------------------------------------------------------

    def _new_task(self, title: str, total: int) -> Task:
        t = Task(f"t{next(self._ids)}", title, total)
        self.tasks[t.id] = t
        return t

    def task(self, tid: str) -> dict[str, Any]:
        t = self.tasks.get(tid)
        return t.snapshot() if t else {"id": tid, "state": "error", "errors": ["Unknown task"]}

    def cancel(self, tid: str) -> None:
        t = self.tasks.get(tid)
        if t:
            t.cancel = True


# --- helpers -----------------------------------------------------------------

def _magic(data: bytes) -> str:
    head = data[:4]
    return head.decode("ascii") if head and all(32 <= b < 127 for b in head) else head.hex()


def _hexdump(data: bytes) -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in chunk).ljust(47)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hx}  {asc}")
    return "\n".join(lines)
