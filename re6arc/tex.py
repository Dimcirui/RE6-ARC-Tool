"""RE6 PC .tex (MT Framework texture) parsing, previews and DDS conversion.

A TEX file is:  "TEX\\0" + 12 byte bit-packed header + [108 byte cubemap block when images == 6]
+ u32 mip offsets (absolute, mips * images of them) + raw block-compressed / BGRA payload.

Pixel layout is identified from the payload size (8 byte blocks = BC1/DXT1, 16 byte blocks =
BC3/DXT5, 4 bytes per pixel = BGRA8); the format byte is kept verbatim on write-back.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass

from PIL import Image

try:
    import texture2ddecoder as _td
except ImportError:  # preview falls back to Pillow's DDS reader
    _td = None

TEX_MAGIC = b"TEX\x00"
CUBE_BLOCK = 108

BC1, BC3, BGRA = "BC1", "BC3", "BGRA"
_BLOCK = {BC1: 8, BC3: 16}
_DDS_FOURCC = {BC1: b"DXT1", BC3: b"DXT5"}


class TexError(ValueError):
    pass


@dataclass
class Tex:
    version: int
    unk: int
    attr: int
    prebias: int
    type: int
    mips: int
    width: int
    height: int
    images: int
    fmt: int
    depth: int
    flags: int               # auto_resize | render_target<<1 | use_vtf<<2
    cube: bytes              # 108 bytes for cubemaps, else b""
    offsets: list[int]
    payload_start: int       # offset of first payload byte in the file
    layout: str              # BC1 | BC3 | BGRA

    @property
    def layout_name(self) -> str:
        return {BC1: "DXT1 (BC1)", BC3: "DXT5 (BC3)", BGRA: "BGRA8"}[self.layout]


_FIELDS = (("version", 8), ("unk", 8), ("attr", 8), ("prebias", 4), ("type", 4),
           ("mips", 6), ("width", 13), ("height", 13), ("images", 8), ("fmt", 8),
           ("depth", 13), ("flags", 3))


def level_size(w: int, h: int, layout: str) -> int:
    if layout == BGRA:
        return w * h * 4
    return ((w + 3) // 4) * ((h + 3) // 4) * _BLOCK[layout]


def mip_chain_size(w: int, h: int, mips: int, layout: str) -> int:
    total = 0
    for _ in range(mips):
        total += level_size(w, h, layout)
        w, h = max(1, w // 2), max(1, h // 2)
    return total


def _offset_step(w: int, h: int, layout: str) -> int:
    """Distance between consecutive mip offsets as written by the game's own tools.

    Identical to the block-aligned level size except below 4x4, where the original files advance
    by w * h * bytes-per-pixel (BC1 2x2 -> 2 bytes, BC3 2x2 -> 4 bytes). The payload itself is
    always the standard block-aligned chain; only the offset table has this quirk.
    """
    if layout != BGRA and w < 4 and h < 4:
        return max(1, w * h * _BLOCK[layout] // 16)
    return level_size(w, h, layout)


def _infer_layout(w: int, h: int, mips: int, images: int, payload: int) -> str | None:
    for layout in (BC1, BC3, BGRA):
        if mip_chain_size(w, h, mips, layout) * images == payload:
            return layout
    return None


def parse(data: bytes) -> Tex:
    if len(data) < 16 or data[:4] != TEX_MAGIC:
        raise TexError("Not a TEX file")
    bits = int.from_bytes(data[4:16], "little")
    vals, cur = {}, 0
    for name, n in _FIELDS:
        vals[name] = (bits >> cur) & ((1 << n) - 1)
        cur += n
    mips, images = vals["mips"], vals["images"]
    if not (1 <= mips <= 16 and images >= 1 and vals["width"] and vals["height"]):
        raise TexError("Unsupported TEX header (render target or unknown variant)")
    cube = data[16:16 + CUBE_BLOCK] if images == 6 else b""
    off_pos = 16 + len(cube)
    count = mips * images
    start = off_pos + count * 4
    if len(data) < start:
        raise TexError("Mip offset table exceeds file")
    offsets = list(struct.unpack_from(f"<{count}I", data, off_pos))
    layout = _infer_layout(vals["width"], vals["height"], mips, images, len(data) - start)
    if layout is None:
        raise TexError("Payload size does not match any supported pixel layout")
    return Tex(cube=cube, offsets=offsets, payload_start=start, layout=layout, **vals)


def _pack_header(t: Tex) -> bytes:
    bits, cur = 0, 0
    for name, n in _FIELDS:
        bits |= (getattr(t, name) & ((1 << n) - 1)) << cur
        cur += n
    return TEX_MAGIC + bits.to_bytes(12, "little")


def _mip_slice(data: bytes, t: Tex, mip: int, image: int = 0) -> tuple[bytes, int, int]:
    w, h = t.width, t.height
    for _ in range(mip):
        w, h = max(1, w // 2), max(1, h // 2)
    off = t.offsets[image * t.mips + mip]
    size = level_size(w, h, t.layout)
    chunk = data[off:off + size]
    if len(chunk) != size:
        raise TexError("Mip data exceeds file")
    return chunk, w, h


def decode(data: bytes, max_dim: int | None = None) -> tuple[Image.Image, Tex]:
    """Decode to an RGBA image. With max_dim, use the smallest mip whose long side >= max_dim."""
    t = parse(data)
    mip = 0
    if max_dim:
        for m in range(t.mips):
            if max(t.width >> m, t.height >> m, 1) >= max_dim:
                mip = m
    chunk, w, h = _mip_slice(data, t, mip)
    if t.layout == BGRA:
        img = Image.frombytes("RGBA", (w, h), chunk, "raw", "BGRA")
    elif _td is not None:
        fn = _td.decode_bc1 if t.layout == BC1 else _td.decode_bc3
        img = Image.frombytes("RGBA", (w, h), fn(chunk, w, h), "raw", "BGRA")
    else:
        img = Image.open(io.BytesIO(_dds_header(w, h, 1, t.layout) + chunk)).convert("RGBA")
    return img, t


# --- DDS ---------------------------------------------------------------------

def _dds_header(w: int, h: int, mips: int, layout: str, cubemap: bool = False) -> bytes:
    flags = 0x1 | 0x2 | 0x4 | 0x1000
    caps = 0x1000
    if mips > 1:
        flags |= 0x20000
        caps |= 0x8 | 0x400000
    if layout == BGRA:
        pf = struct.pack("<II4sIIIII", 32, 0x41, b"\0\0\0\0", 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
        pitch = w * 4
        flags |= 0x8
    else:
        pf = struct.pack("<II4sIIIII", 32, 0x4, _DDS_FOURCC[layout], 0, 0, 0, 0, 0)
        pitch = level_size(w, h, layout)
        flags |= 0x80000
    caps2 = (0x200 | 0xFC00) if cubemap else 0
    head = struct.pack("<4s18I", b"DDS ", 124, flags, h, w, pitch, 0, mips, *([0] * 11))
    return head + pf + struct.pack("<5I", caps, caps2, 0, 0, 0)


def to_dds(data: bytes) -> bytes:
    """TEX -> DDS. Cubemaps keep all six faces."""
    t = parse(data)
    body = data[t.payload_start:]
    if t.images == 1:
        return _dds_header(t.width, t.height, t.mips, t.layout) + body
    if t.images == 6:
        return _dds_header(t.width, t.height, t.mips, t.layout, cubemap=True) + body
    raise TexError(f"Cannot convert TEX with {t.images} images to DDS")


def to_png(data: bytes) -> bytes:
    img, _ = decode(data)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@dataclass
class DdsInfo:
    width: int
    height: int
    mips: int
    layout: str
    payload: bytes


def parse_dds(dds: bytes) -> DdsInfo:
    if len(dds) < 128 or dds[:4] != b"DDS ":
        raise TexError("Not a DDS file")
    (hsize, flags, h, w, _pitch, _depth, mips) = struct.unpack_from("<7I", dds, 4)
    pf_flags, fourcc, bits, rmask, gmask, bmask, amask = struct.unpack_from("<I4sIIIII", dds, 80)
    caps2 = struct.unpack_from("<I", dds, 112)[0]
    if hsize != 124:
        raise TexError("Malformed DDS header")
    if caps2 & 0x200 or caps2 & 0x200000:
        raise TexError("Cubemap / volume DDS files are not supported for write-back")
    mips = max(1, mips) if flags & 0x20000 else 1
    if pf_flags & 0x4:
        if fourcc == b"DXT1":
            layout = BC1
        elif fourcc == b"DXT5":
            layout = BC3
        elif fourcc == b"DX10":
            raise TexError("DDS uses a DX10 header; re-save as legacy DXT1/DXT5/BGRA8")
        else:
            raise TexError(f"Unsupported DDS compression {fourcc!r}; use DXT1, DXT5 or BGRA8")
    elif pf_flags & 0x40 and bits == 32 and (rmask, gmask, bmask) == (0xFF0000, 0xFF00, 0xFF):
        layout = BGRA
    else:
        raise TexError("Unsupported DDS pixel format; use DXT1, DXT5 or uncompressed BGRA8 (A8R8G8B8)")
    payload = dds[128:]
    if len(payload) != mip_chain_size(w, h, mips, layout):
        raise TexError(f"DDS payload size mismatch ({len(payload)} bytes for {w}x{h}, {mips} mips, {layout})")
    return DdsInfo(w, h, mips, layout, payload)


def from_dds(original_tex: bytes, dds: bytes) -> bytes:
    """Write a DDS back into an existing TEX, keeping every header field except size/mips/offsets."""
    t = parse(original_tex)
    if t.images != 1:
        raise TexError("Write-back into cubemap TEX files is not supported")
    info = parse_dds(dds)
    if info.layout != t.layout:
        raise TexError(f"Pixel format mismatch: original TEX is {t.layout_name}, "
                       f"DDS is {info.layout}. Re-export the DDS with the same format.")
    t.width, t.height, t.mips = info.width, info.height, info.mips
    if t.width > 8191 or t.height > 8191:
        raise TexError("Texture larger than 8191 px")
    start = 16 + info.mips * 4
    offsets, pos, w, h = [], start, info.width, info.height
    for _ in range(info.mips):
        offsets.append(pos)
        pos += _offset_step(w, h, info.layout)
        w, h = max(1, w // 2), max(1, h // 2)
    return _pack_header(t) + struct.pack(f"<{info.mips}I", *offsets) + info.payload
