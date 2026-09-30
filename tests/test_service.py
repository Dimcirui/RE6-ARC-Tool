"""End-to-end workspace tests: extract -> diff folder -> save -> reopen."""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from re6arc import arc, tex  # noqa: E402
from re6arc.service import Workspace  # noqa: E402
from test_core import ARCS  # noqa: E402


def wait(ws: Workspace, tid: str, timeout: float = 120) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        s = ws.task(tid)
        if s["state"] != "running":
            return s
        time.sleep(0.02)
    raise TimeoutError(tid)


@unittest.skipUnless(ARCS, "no sample .arc files found (set RE6_ARC_DIR)")
class WorkspaceFlow(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = Path(self.td.name)
        # a mid-sized archive that has textures and a non-texture
        cands = [p for p in ARCS if p.name == "uPl06HeadAdaA.arc"] or ARCS
        self.src = self.tmp / "work" / cands[0].name
        self.src.parent.mkdir()
        shutil.copy2(cands[0], self.src)
        self.ws = Workspace()
        res = self.ws.open_paths([str(self.src)])
        self.assertEqual(res["errors"], [])
        self.aid = res["opened"][0]

    def tearDown(self):
        self.td.cleanup()

    def _extract(self, convert="raw", paths=None):
        out = self.tmp / f"out_{convert}"
        s = wait(self.ws, self.ws.start_extract([{"archive": self.aid, "paths": paths}], str(out), convert))
        self.assertEqual(s["state"], "done", s["errors"])
        self.assertEqual(s["error_count"], 0, s["errors"])
        return out

    def test_open_folder_and_dedupe(self):
        res = self.ws.open_paths([str(self.src.parent), str(self.src)])
        self.assertEqual(len(res["archives"]), 1)

    def test_extract_raw_then_no_changes(self):
        out = self._extract("raw")
        st = self.ws.stage_folder(self.aid, str(out))
        self.assertEqual((st["modified"], st["new"], st["errors"]), (0, 0, 0), st)
        self.assertEqual(len(self.ws.loaded[self.aid].edits), 0)

    def test_extract_dds_then_no_changes(self):
        out = self._extract("dds")
        st = self.ws.stage_folder(self.aid, str(out))
        self.assertEqual((st["modified"], st["new"], st["errors"]), (0, 0, 0), st)

    def test_extract_png_and_thumb_and_preview(self):
        out = self._extract("png")
        self.assertTrue(list(out.rglob("*.png")))
        rows = self.ws.rows(self.aid)
        tex_path = next(r[0] for r in rows if r[1] == "tex")
        self.assertTrue(self.ws.thumb(self.aid, tex_path, 64).startswith("data:image/png"))
        pv = self.ws.preview(self.aid, tex_path)
        self.assertEqual(pv["kind"], "image")
        other = next(r[0] for r in rows if r[1] != "tex")
        self.assertEqual(self.ws.preview(self.aid, other)["kind"], "hex")

    def test_edit_add_delete_and_save(self):
        out = self._extract("dds")
        rows = self.ws.rows(self.aid)
        tex_rows = [r[0] for r in rows if r[1] == "tex"]
        target = tex_rows[0]
        victim = tex_rows[1]
        dds_path = out / self.src.stem / (target[:-4] + ".dds")
        raw = bytearray(dds_path.read_bytes())
        raw[-1] ^= 0xFF  # flip the last payload byte
        dds_path.write_bytes(bytes(raw))
        newfile = self.tmp / "extra.mod"
        newfile.write_bytes(b"hello-new-file" * 10)

        st = self.ws.stage_folder(self.aid, str(out))
        self.assertEqual(st["modified"], 1, st)
        self.ws.stage_add(self.aid, str(newfile), "data/test/extra.mod")
        self.ws.stage_delete(self.aid, [victim])

        dest = self.tmp / "saved.arc"
        s = wait(self.ws, self.ws.start_save(self.aid, str(dest)))
        self.assertEqual(s["state"], "done", s["errors"])
        self.assertEqual((s["result"]["modified"], s["result"]["added"], s["result"]["removed"]), (1, 1, 1))

        old, new = arc.parse(self.src), arc.parse(dest)
        self.assertEqual(len(new.entries), len(old.entries))  # +1 added, -1 deleted
        by_old = old.by_path()
        for e in new.entries:
            data = arc.read_entry(new, e)
            if e.path == "data/test/extra.mod":
                self.assertEqual(data, newfile.read_bytes())
            elif e.path == target:
                orig = arc.read_entry(old, by_old[target.lower()])
                self.assertEqual(data, tex.from_dds(orig, bytes(raw)))
                self.assertNotEqual(data, orig)
            else:
                self.assertEqual(data, arc.read_entry(old, by_old[e.path.lower()]), e.path)
        self.assertNotIn(victim.lower(), new.by_path())

    def test_save_in_place_makes_backup_and_reloads(self):
        rows = self.ws.rows(self.aid)
        victim = rows[0][0]
        self.ws.stage_delete(self.aid, [victim])
        before = self.src.read_bytes()
        s = wait(self.ws, self.ws.start_save(self.aid, str(self.src)))
        self.assertEqual(s["state"], "done", s["errors"])
        self.assertTrue(s["result"]["reloaded"])
        self.assertEqual(Path(str(self.src) + ".bak").read_bytes(), before)
        self.assertNotIn(victim.lower(), {r[0].lower() for r in self.ws.rows(self.aid)})
        self.assertEqual(len(self.ws.loaded[self.aid].edits), 0)

    def test_bad_dds_is_reported_not_staged(self):
        out = self._extract("dds")
        rows = self.ws.rows(self.aid)
        target = next(r[0] for r in rows if r[1] == "tex")
        (out / self.src.stem / (target[:-4] + ".dds")).write_bytes(b"not a dds at all")
        st = self.ws.stage_folder(self.aid, str(out))
        self.assertEqual(st["errors"], 1, st)
        self.assertEqual(len(self.ws.loaded[self.aid].edits), 0)

    def test_verify(self):
        s = wait(self.ws, self.ws.start_verify(self.aid))
        self.assertEqual((s["state"], s["result"]["bad"]), ("done", 0))


if __name__ == "__main__":
    unittest.main()
