"""Core round-trip tests against real RE6 archives.

Set RE6_ARC_DIR to a folder containing RE6 PC .arc files, e.g.
    set RE6_ARC_DIR=...\Resident Evil 6\nativePC\arc\DX9
Without it the default Steam install path is tried; with no archives found the tests are skipped.
Run:  python -m unittest discover -s tests -v   (from the project root)
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from re6arc import arc, tex  # noqa: E402

SAMPLE = Path(os.environ.get(
    "RE6_ARC_DIR",
    r"C:/Program Files (x86)/Steam/steamapps/common/Resident Evil 6/nativePC/arc/DX9"))
ARCS = sorted(SAMPLE.glob("*.arc")) if SAMPLE.is_dir() else []


@unittest.skipUnless(ARCS, "no sample .arc files found (set RE6_ARC_DIR)")
class ArcRoundTrip(unittest.TestCase):
    def test_all_entries_inflate(self):
        for p in ARCS:
            a = arc.parse(p)
            with p.open("rb") as fh:
                for e in a.entries:
                    arc.read_entry(a, e, fh)  # raises on size/zlib mismatch

    def test_rebuild_reusing_streams_is_byte_identical(self):
        for p in ARCS:
            a = arc.parse(p)
            with p.open("rb") as fh:
                items = [arc.Item(e.name, e.type_hash, e.size, e.flags, raw_comp=arc.read_raw(fh, e))
                         for e in a.entries]
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / p.name
                arc.write_archive(out, items)
                self.assertEqual(out.read_bytes(), p.read_bytes(), p.name)

    def test_rebuild_recompressing_keeps_content(self):
        p = min(ARCS, key=lambda x: x.stat().st_size)
        a = arc.parse(p)
        items = [arc.Item(e.name, e.type_hash, 0, e.flags, data=arc.read_entry(a, e)) for e in a.entries]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / p.name
            arc.write_archive(out, items)
            b = arc.parse(out)
            self.assertEqual([e.path for e in b.entries], [e.path for e in a.entries])
            for ea, eb in zip(a.entries, b.entries):
                self.assertEqual(arc.read_entry(a, ea), arc.read_entry(b, eb))


@unittest.skipUnless(ARCS, "no sample .arc files found")
class TexRoundTrip(unittest.TestCase):
    def _textures(self):
        for p in ARCS:
            a = arc.parse(p)
            with p.open("rb") as fh:
                for e in a.entries:
                    if e.ext == "tex":
                        yield p.name, e.path, arc.read_entry(a, e, fh)

    def test_dds_writeback_is_identity(self):
        n = 0
        for arcname, path, data in self._textures():
            try:
                t = tex.parse(data)
            except tex.TexError:
                continue
            if t.images != 1:
                continue
            with self.subTest(tex=f"{arcname}:{path}"):
                self.assertEqual(tex.from_dds(data, tex.to_dds(data)), data)
            n += 1
        self.assertGreater(n, 50)

    def test_preview_decodes(self):
        n = 0
        for _, path, data in self._textures():
            try:
                img, t = tex.decode(data, max_dim=128)
            except tex.TexError:
                continue
            self.assertEqual(img.mode, "RGBA")
            n += 1
        self.assertGreater(n, 50)

    def test_format_mismatch_is_rejected(self):
        seen = {}
        for _, _, data in self._textures():
            try:
                t = tex.parse(data)
            except tex.TexError:
                continue
            if t.images == 1:
                seen.setdefault(t.layout, data)
        if len(seen) >= 2:
            (l1, d1), (l2, d2) = list(seen.items())[:2]
            with self.assertRaises(tex.TexError):
                tex.from_dds(d1, tex.to_dds(d2))


class Hashes(unittest.TestCase):
    def test_known_hashes(self):
        self.assertEqual(arc.hash_of_ext("tex"), 0x241F5DEB)
        self.assertEqual(arc.hash_of_ext("mod"), 0x58A15856)
        self.assertEqual(arc.hash_of_ext("lmt"), 0x76820D81)
        self.assertEqual(arc.ext_of(0x7808EA10), "rtex")
        # the game's own names (BH6.exe), not guesses
        self.assertEqual(arc.ext_of(0x5FB399F4), "bssq")              # rBioSoundSequenceSe
        self.assertEqual(arc.hash_of_ext("lku"), 0x266E8A91)          # rLinkUnit
        self.assertEqual(arc.hash_of_ext("sst"), 0x6A9197ED)          # rSoundStreamStructure
        self.assertEqual(arc.hash_of_ext("sstr"), 0x3B764DD4)         # rSoundStreamTransition
        self.assertEqual(arc.ext_of(0x12345678), "12345678")          # an unknown hash stays hexadecimal
        self.assertEqual(arc.hash_of_ext("5fb399f4"), 0x5FB399F4)

    def test_class_table_is_consistent(self):
        shared = {}
        for h, cls, ext in arc._ENGINE_CLASSES:
            self.assertEqual(arc.type_hash_of(cls), h, cls)
            self.assertEqual(arc.class_of(h), cls)
            shared.setdefault(ext.lower(), []).append(h)
        for ext, hs in shared.items():
            self.assertEqual(arc.hash_of_ext(ext), hs[0], ext)
        # only sound / movie intermediate classes (never in arcs) share an extension with another class
        self.assertEqual({e for e, hs in shared.items() if len(hs) > 1},
                         {"smx", "mem.wmv", "wmv", "sngw", "envw", "xsew"})

    def test_safe_join_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(arc.ArcError):
                arc.safe_join(Path(td), "../evil.txt")
            with self.assertRaises(arc.ArcError):
                arc.safe_join(Path(td), "C:/evil.txt")
            arc.safe_join(Path(td), "data/chara/a.tex")


if __name__ == "__main__":
    unittest.main()
