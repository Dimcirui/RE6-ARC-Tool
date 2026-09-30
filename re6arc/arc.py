"""RE6 (PC, MT Framework) ARC container: parse, extract, and rebuild.

Layout (version 7, all little-endian), verified against real game archives:

    0x00  "ARC\\0"           magic
    0x04  u16 version       7
    0x06  u16 file_count
    0x08  file_count * 0x50 entries:
              char[64] name         backslash path without extension, NUL padded
              u32      type_hash    ~crc32(class name) & 0x7FFFFFFF
              u32      comp_size    size of the zlib stream in the archive
              u32      size_flags   bits 0-28 = uncompressed size, bits 29-31 = flags (always 2)
              u32      offset       absolute offset of the zlib stream
    ....  zero padding up to 0x8000 alignment
    ....  zlib streams, back to back, no gaps

The entry table has no sort order; the original order is kept on rebuild.
"""
from __future__ import annotations

import os
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

ARC_MAGIC = b"ARC\x00"
ARC_VERSION = 7
HEADER_SIZE = 8
ENTRY_SIZE = 0x50
NAME_SIZE = 0x40
DATA_ALIGNMENT = 0x8000
SIZE_MASK = 0x1FFFFFFF
FLAG_SHIFT = 29
DEFAULT_FLAGS = 2


class ArcError(RuntimeError):
    pass


# --- type hash <-> extension -------------------------------------------------

def type_hash_of(class_name: str) -> int:
    return (~zlib.crc32(class_name.encode("ascii"))) & 0x7FFFFFFF


# extension -> MT Framework resource class name
_EXT_CLASSES = {
    "tex": "rTexture", "mod": "rModel", "mrl": "rMaterial", "lmt": "rMotionList",
    "efl": "rEffectList", "ean": "rEffectAnim", "rtex": "rRenderTargetTexture",
}

# hashes whose class names were not derived from a name, taken from known RE6 archives
_EXTRA_EXTS = {
    0x0026E7FF: "ccl", 0x0437BCF2: "grw", 0x07437CCE: "base", 0x0A4280D9: "shd",
    0x12191BA1: "epv", 0x15302EF4: "lot", 0x1BCC4966: "srq", 0x2282360D: "jex",
    0x272B80EA: "prp", 0x296BD0A6: "hgm", 0x2D12E086: "srd", 0x39C52040: "lcm",
    0x4C0DB839: "sdl", 0x4CA26828: "mse", 0x4EF19843: "nav", 0x535D969F: "ctc",
    0x65B275E5: "sce", 0x66B45610: "fsm", 0x6E45FABB: "atk", 0x7E33A16C: "spc",
}

HASH_TO_EXT: dict[int, str] = {type_hash_of(c): e for e, c in _EXT_CLASSES.items()}
HASH_TO_EXT.update(_EXTRA_EXTS)
EXT_TO_HASH: dict[str, int] = {e: h for h, e in HASH_TO_EXT.items()}

_HEX_EXT = re.compile(r"^[0-9a-f]{8}$")


def ext_of(type_hash: int) -> str:
    return HASH_TO_EXT.get(type_hash, f"{type_hash:08x}")


def hash_of_ext(ext: str) -> int:
    ext = ext.lower().lstrip(".")
    if ext in EXT_TO_HASH:
        return EXT_TO_HASH[ext]
    if _HEX_EXT.match(ext):
        return int(ext, 16)
    raise ArcError(f"Unknown file extension '{ext}': cannot derive an ARC type hash")


# --- data model --------------------------------------------------------------

@dataclass(slots=True)
class Entry:
    index: int
    name: str            # forward-slash path, no extension
    type_hash: int
    comp_size: int
    size: int
    flags: int
    offset: int

    @property
    def ext(self) -> str:
        return ext_of(self.type_hash)

    @property
    def path(self) -> str:
        """Virtual path with extension, forward slashes."""
        return f"{self.name}.{self.ext}"


@dataclass(slots=True)
class Archive:
    path: Path
    size: int
    version: int
    entries: list[Entry] = field(default_factory=list)

    def by_path(self) -> dict[str, Entry]:
        return {e.path.lower(): e for e in self.entries}


def _align(v: int, a: int) -> int:
    return (v + a - 1) // a * a


def data_start(count: int) -> int:
    end = HEADER_SIZE + count * ENTRY_SIZE
    return _align(end, DATA_ALIGNMENT) if count else end


def _decode_name(raw: bytes) -> str:
    raw = raw.split(b"\x00", 1)[0]
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return text.replace("\\", "/").lstrip("/")


def _encode_name(name: str) -> bytes:
    raw = name.replace("/", "\\").encode("ascii")
    if len(raw) >= NAME_SIZE:
        raise ArcError(f"Entry name too long ({len(raw)} bytes, max {NAME_SIZE - 1}): {name}")
    return raw.ljust(NAME_SIZE, b"\x00")


def parse(path: str | os.PathLike) -> Archive:
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as fh:
        head = fh.read(HEADER_SIZE)
        if len(head) < HEADER_SIZE:
            raise ArcError("File too small to be an ARC")
        magic, version, count = struct.unpack("<4sHH", head)
        if magic != ARC_MAGIC:
            raise ArcError(f"Not an ARC file (magic {magic!r})")
        if version != ARC_VERSION:
            raise ArcError(f"Unsupported ARC version {version}; only RE6 PC (version 7) is supported")
        table = fh.read(count * ENTRY_SIZE)
    if len(table) != count * ENTRY_SIZE:
        raise ArcError("Truncated entry table")
    arc = Archive(path=path, size=size, version=version)
    for i in range(count):
        raw, th, csize, sz_raw, off = struct.unpack_from("<64sIIII", table, i * ENTRY_SIZE)
        e = Entry(i, _decode_name(raw), th, csize, sz_raw & SIZE_MASK, sz_raw >> FLAG_SHIFT, off)
        if off + csize > size:
            raise ArcError(f"Entry {i} ({e.path}) points past end of file")
        arc.entries.append(e)
    return arc


def read_raw(fh, e: Entry) -> bytes:
    fh.seek(e.offset)
    data = fh.read(e.comp_size)
    if len(data) != e.comp_size:
        raise ArcError(f"Unexpected EOF reading {e.path}")
    return data


def inflate(raw: bytes, e: Entry) -> bytes:
    try:
        data = zlib.decompress(raw)
    except zlib.error:
        if len(raw) != e.size:
            raise
        data = raw  # stored without zlib
    if len(data) != e.size:
        raise ArcError(f"Size mismatch for {e.path}: header {e.size}, actual {len(data)}")
    return data


def read_entry(arc: Archive, e: Entry, fh=None) -> bytes:
    if fh is not None:
        return inflate(read_raw(fh, e), e)
    with arc.path.open("rb") as f:
        return inflate(read_raw(f, e), e)


# --- path safety -------------------------------------------------------------

def safe_join(root: Path, rel: str) -> Path:
    """Join an archive-relative path under root, refusing traversal."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." or ":" in p for p in parts):
        raise ArcError(f"Unsafe path in archive: {rel}")
    out = root.joinpath(*parts)
    root_r = root.resolve()
    if root_r != out.resolve() and root_r not in out.resolve().parents:
        raise ArcError(f"Unsafe path in archive: {rel}")
    return out


# --- rebuild -----------------------------------------------------------------

@dataclass(slots=True)
class Item:
    """One entry to write. Exactly one of raw_comp / data is set."""
    name: str
    type_hash: int
    size: int
    flags: int = DEFAULT_FLAGS
    raw_comp: bytes | None = None   # already-compressed stream, reused verbatim
    data: bytes | None = None       # uncompressed payload, compressed on write


def compress(data: bytes) -> bytes:
    return zlib.compress(data, 9)


def write_archive(out_path: str | os.PathLike, items: list[Item],
                  progress: Callable[[int, int], None] | None = None) -> None:
    """Write an ARC atomically (temp file + replace)."""
    out_path = Path(out_path)
    if len(items) > 0xFFFF:
        raise ArcError("Too many entries for one ARC (max 65535)")
    streams: list[bytes] = []
    for i, it in enumerate(items):
        if it.raw_comp is not None:
            streams.append(it.raw_comp)
        elif it.data is not None:
            if len(it.data) > SIZE_MASK:
                raise ArcError(f"{it.name} is too large for an ARC entry")
            streams.append(compress(it.data))
        else:
            raise ArcError(f"Item {it.name} has no payload")
        if progress:
            progress(i + 1, len(items))
    start = data_start(len(items))
    table = bytearray()
    offset = start
    for it, s in zip(items, streams):
        size = len(it.data) if it.data is not None else it.size
        table += struct.pack("<64sIIII", _encode_name(it.name), it.type_hash, len(s),
                             (size & SIZE_MASK) | (it.flags << FLAG_SHIFT), offset)
        offset += len(s)
    tmp = out_path.with_name(out_path.name + ".tmp")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tmp.open("wb") as fh:
            fh.write(struct.pack("<4sHH", ARC_MAGIC, ARC_VERSION, len(items)))
            fh.write(table)
            fh.write(b"\x00" * (start - HEADER_SIZE - len(table)))
            for s in streams:
                fh.write(s)
        os.replace(tmp, out_path)
    finally:
        if tmp.exists():
            tmp.unlink()


def split_path(virtual: str) -> tuple[str, int]:
    """'a/b/c.tex' -> ('a/b/c', type_hash)."""
    virtual = virtual.replace("\\", "/").lstrip("/")
    base, dot, ext = virtual.rpartition(".")
    if not dot or not base or "/" in ext:
        raise ArcError(f"File has no extension: {virtual}")
    return base, hash_of_ext(ext)
