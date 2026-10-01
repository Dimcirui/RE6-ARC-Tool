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


# Resource classes of RE6 and the file extension the GAME uses for each (what sResource puts after the path when it
# loads a loose file): extracted from BH6.exe (Steam build of 2025-08), slot +0x18 of each resource class vtable.
# Columns: type hash (~crc32(class name) & 0x7FFFFFFF), class name, extension. Classes that occur in the retail
# arcs come first; when several classes share an extension the first one wins for extension -> hash.
_ENGINE_CLASSES = (
    (0x241F5DEB, 'rTexture', 'tex'),
    (0x6D5AE854, 'rEffectList', 'efl'),
    (0x2749C8A8, 'rMaterial', 'mrl'),
    (0x58A15856, 'rModel', 'mod'),
    (0x66B45610, 'rAIFSM', 'fsm'),
    (0x76820D81, 'rMotionList', 'lmt'),
    (0x7E33A16C, 'rSoundPackage', 'spc'),
    (0x1BCC4966, 'rSoundRequest', 'srq'),
    (0x4C0DB839, 'rScheduler', 'sdl'),
    (0x2D12E086, 'rSoundRandom', 'srd'),
    (0x15302EF4, 'rLayout', 'lot'),
    (0x4E397417, 'rEffectAnim', 'ean'),
    (0x39C52040, 'rCameraList', 'lcm'),
    (0x5FB399F4, 'rBioSoundSequenceSe', 'bssq'),
    (0x167DBBFF, 'rSoundStreamRequest', 'stq'),
    (0x54DC440A, 'rMotionSequenceList', 'msl'),
    (0x1B520B68, 'rZone', 'zon'),
    (0x7808EA10, 'rRenderTargetTexture', 'rtex'),
    (0x6A9197ED, 'rSoundStreamStructure', 'sst'),
    (0x6E45FABB, 'rAttackParam', 'atk'),
    (0x296BD0A6, 'rHitGeometry', 'hgm'),
    (0x12191BA1, 'rEffectProvider', 'epv'),
    (0x4CA26828, 'rSoundMotionSe', 'mse'),
    (0x276DE8B7, 'rEffect2D', 'e2d'),
    (0x0253F147, 'rHit', 'hit'),
    (0x65B275E5, 'rScenario', 'sce'),
    (0x51FC779F, 'rCollision', 'sbc'),
    (0x0A4280D9, 'rSoundHitData', 'shd'),
    (0x535D969F, 'rCnsTinyChain', 'ctc'),
    (0x266E8A91, 'rLinkUnit', 'lku'),
    (0x2282360D, 'rJointEx', 'jex'),
    (0x02358E1A, 'rShaderPackage', 'spkg'),
    (0x272B80EA, 'rPropParam', 'prp'),
    (0x4EF19843, 'rNavigationMesh', 'nav'),
    (0x1FA8B594, 'rAreaHit', 'ahs'),
    (0x671F21DA, 'rStartPos', 'stp'),
    (0x242BB29A, 'rGUIMessage', 'gmd'),
    (0x07437CCE, 'rSoundAttributeSe', 'ase'),
    (0x039D71F2, 'rSoundReverbTable', 'rvt'),
    (0x3B764DD4, 'rSoundStreamTransition', 'sstr'),
    (0x5F36B659, 'rAIWayPoint', 'way'),
    (0x2A4F96A8, 'rRigidBody', 'rbd'),
    (0x1ED12F1B, 'rGoalPos', 'glp'),
    (0x5802B3FF, 'rAHCamera', 'ahc'),
    (0x285A13D9, 'rFxZone', 'vzo'),
    (0x0026E7FF, 'rChainCol', 'ccl'),
    (0x4B92D51A, 'rLightLinker', 'llk'),
    (0x35BDD173, 'rPosAdjust', 'poa'),
    (0x2C4666D1, 'rScrHiding', 'srh'),
    (0x46FB08BA, 'rBioModelMontage', 'bmt'),
    (0x6A5CDD23, 'rOccluder', 'occ'),
    (0x4B768796, 'rSoundCondition', 'scn'),
    (0x25B4A6B9, 'rSoundBGMControl', 'bgm'),
    (0x45E867D7, 'rMotionListList', 'mll'),
    (0x15155F8A, 'rSMHiding', 'smh'),
    (0x02833703, 'rEffectStrip', 'efs'),
    (0x5175C242, 'rGeometry2', 'geo2'),
    (0x6FE1EA15, 'rSoundPhysicsList', 'spl'),
    (0x1EB3767C, 'rSoundPhysicsRigidBody', 'spr'),
    (0x33046CD5, 'rCameraQFPS', 'qcm'),
    (0x257D2F7C, 'rSwingModel', 'swm'),
    (0x622FA3C9, 'rAIWayPointExpand', 'ewy'),
    (0x601E64CD, 'rSoundZoneSwitch', 'szs'),
    (0x45F753E8, 'rInGameSound', 'igs'),
    (0x0437BCF2, 'rGrassWind', 'grw'),
    (0x1AADF7B7, 'rCameraMotionSdl', 'cms'),
    (0x3B5C7FD3, 'rIdAnim', 'ida'),
    (0x58819BC8, 'rSoundSmOcclusion', 'sso'),
    (0x14EA8095, 'rCnsOffsetSet', 'cos'),
    (0x54E2D1FF, 'rPadData', 'rpd'),
    (0x2F4E7041, 'rSoundGunTool', 'sgt'),
    (0x7D1530C2, 'rSoundSourceMusic', 'sngw'),
    (0x4323D83A, 'rSceneTexture', 'stex'),
    (0x25FA21CB, 'rAIWayPointGraph', 'gway'),
    (0x31EDC625, 'rSoundPhysicsJoint', 'spj'),
    (0x62A68441, 'rThinkTable', 'thk'),
    (0x2D462600, 'rGUIFont', 'gfd'),
    (0x30FC745F, 'rSoundSubMixer', 'smx'),
    (0x538120DE, 'rSoundEngine', 'eng'),
    (0x19F6EFCE, 'rSoundEnemyParam', 'sep'),
    (0x52DBDCD6, 'rRagdoll', 'rdd'),
    (0x46810940, 'rSoundEngineValue', 'egv'),
    (0x628DFB41, 'rGrass2Setting', 'gr2s'),
    (0x11C35522, 'rGrass2', 'gr2'),
    (0x69A5C538, 'rDeformWeightMap', 'dwm'),
    (0x49B5A885, 'rSoundSimpleCurve', 'ssc'),
    (0x2C2DE8CA, 'rAdh', 'adh'),
    (0x245133D9, 'rCameraRail', 'cmr'),
    (0x22948394, 'rGUI', 'gui'),
    (0x02A80E1F, 'rLinkRagdoll', 'lrd'),
    (0x7BEC319A, 'rSoundPhysicsSoftBody', 'sps'),
    (0x56CF93D4, 'rAINavigationMeshList', 'lnv'),
    (0x07F768AF, 'rGUIIconInfo', 'gii'),
    (0x2739B57C, 'rGrass', 'grs'),
    (0x6BB4ED5E, 'rLch', 'lch'),
    (0x4E2FEF36, 'rModelMontage', 'mtg'),
    (0x0ECD7DF4, 'rSoundCurveSet', 'scs'),
    (0x0315E81F, 'rSoundDirectionalSet', 'sds'),
    (0x2B40AE8F, 'rSoundEQ', 'equ'),
    (0x232E228C, 'rSoundReverb', 'rev'),
    (0x358012E8, 'rVibration', 'vib'),
    (0x31A91DA3, 'rAI', 'ais'),
    (0x785E6622, 'rAIConditionTree', 'cdt'),
    (0x7BBF5CB0, 'rAIDynamicLayout', 'dpth'),
    (0x59EE2276, 'rAIFSMList', 'fsl'),
    (0x31AB356C, 'rAIPathBase', 'are'),
    (0x5400CD32, 'rAIPathBaseXml', 'are.xml'),
    (0x3948DD0A, 'rAIPointEvaluaterList', 'pel'),
    (0x476DCE81, 'rAIWayPointExpand::WayPoint', 'ewy_dummy.xml'),
    (0x73850D05, 'rArchive', 'arc'),
    (0x3E363245, 'rChain', 'chn'),
    (0x3D683C5B, 'rCloud', 'cld'),
    (0x4A06C178, 'rCnsJointOffset', 'jof'),
    (0x526665B7, 'rCnsTinyIK', 'tik'),
    (0x2350E584, 'rCollisionObj', 'obc'),
    (0x1EF5E639, 'rConvexHull', 'hul'),
    (0x75967AD6, 'rDynamicSbc', 'dsc'),
    (0x07B8BCDE, 'rFacialAnimation', 'fca'),
    (0x5E4DEF9D, 'rGeometry2Group', 'geog'),
    (0x2672F2D4, 'rGeometry3', 'geo3'),
    (0x6143E1BD, 'rGraphPatch', 'gpt'),
    (0x3FF8D5FD, 'rHDDCacheSettingPS3', 'cst'),
    (0x3CC3B1D9, 'rIdKeyItem', 'idk'),
    (0x2FD6616E, 'rIni', 'ini'),
    (0x748AA719, 'rJointExXml', 'jex.xml'),
    (0x31F693D6, 'rMovieOnDisk', 'wmv'),
    (0x71950384, 'rMovieOnDiskInterMediate', 'wmv'),
    (0x5F84F7C4, 'rMovieOnMemory', 'mem.wmv'),
    (0x17A69ACE, 'rMovieOnMemoryInterMediate', 'mem.wmv'),
    (0x1BA81D3C, 'rNeck', 'nck'),
    (0x18E5033D, 'rParamBase', 'prm'),
    (0x0B52347D, 'rPlParam', 'plm'),
    (0x09E6B5F0, 'rShader2', 'mfx'),
    (0x7ED4C86C, 'rSoundEngineXml', 'eng.xml'),
    (0x04878D6F, 'rSoundProvider', 'spv'),
    (0x79C47B59, 'rSoundSourceADPCM', 'sew'),
    (0x5CBAB342, 'rSoundSourceEnvironment', 'envw'),
    (0x317AB4ED, 'rSoundSourceEnvironmentInterMediate', 'envw'),
    (0x14324F60, 'rSoundSourceMusicInterMediate', 'sngw'),
    (0x255D51CD, 'rSoundSourceOggVorbis', 'sngw'),
    (0x04124E96, 'rSoundSourceSE', 'xsew'),
    (0x39C73911, 'rSoundSourceSEInterMediate', 'xsew'),
    (0x064A3AD8, 'rSoundSpeakerSetXml', 'sss.xml'),
    (0x6E402C69, 'rSoundSubMixerXml', 'smx.xml'),
    (0x14F8098C, 'rTextureChanger', 'txc'),
    (0x46E786DE, 'rTextureChangerList', 'tcl'),
    (0x7E442559, 'rWth', 'wth'),
    (0x5531DE9F, 'uSoundSubMixer', 'smx'),
    (0x5A11B83A, 'uSoundSubMixer::CurrentSubMixer', 'smx'),
)

HASH_TO_EXT: dict[int, str] = {h: e for h, _c, e in _ENGINE_CLASSES}
CLASS_NAMES: dict[int, str] = {h: c for h, c, _e in _ENGINE_CLASSES}
EXT_TO_HASH: dict[str, int] = {}
for _h, _c, _e in _ENGINE_CLASSES:
    EXT_TO_HASH.setdefault(_e.lower(), _h)

_HEX_EXT = re.compile(r"^[0-9a-f]{8}$")


def ext_of(type_hash: int) -> str:
    return HASH_TO_EXT.get(type_hash, f"{type_hash:08x}")


def class_of(type_hash: int) -> str:
    """resource class name of a type hash ('' when it is not known)"""
    return CLASS_NAMES.get(type_hash, "")


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
