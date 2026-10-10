"""Build lane (Lane A, data-only): apply same-length text patches to a
copy of the extracted tree, repack to ISO. No copyrighted bytes leave the
repo; outputs are gitignored working artifacts.

Safety: every patch MUST be same-length so RARC/BMG structure is untouched
(mesRes message text lives raw inside the decompressed RARC payload).
"""
from __future__ import annotations
import shutil, subprocess, sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from gclib.yaz0_yay0 import Yaz0

REPO = Path(__file__).resolve().parents[2]
ORIG_TREE = REPO / "workspace" / "extracted" / "root"


def apply_text_patch(tree_root: Path, arc_rel: str, entry_name: str,
                     old: bytes, new: bytes) -> tuple[str, int]:
    """Patch one ASCII string inside a text-carrying RARC entry (YAZ0-wrapped).
    Returns (arc_abs_path, bytes_changed). Requires unique, same-length match."""
    if len(old) != len(new):
        raise ValueError("patch must be same-length to preserve archive layout")
    arc = tree_root / arc_rel
    payload = bytearray(Yaz0.decompress(BytesIO(arc.read_bytes())).read())
    n = payload.count(old)
    if n != 1:
        raise ValueError(f"expected exactly 1 occurrence of {old!r}, found {n}")
    i = payload.find(old)
    payload[i:i + len(old)] = new
    changed = sum(a != b for a, b in zip(old, new))
    repacked = Yaz0.compress(BytesIO(bytes(payload))).read()
    arc.write_bytes(repacked)
    return str(arc), changed


def build_iso(extracted: Path, out_iso: Path) -> Path:
    """Repack extracted root -> ISO via pyisotools. Quirk (ADR-0008): dest is
    resolved relative to the root as <root>/<dest>, so we build there then
    relocate to the requested path."""
    out_iso.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = "lab_build.iso"
    subprocess.run([sys.executable, "-m", "pyisotools", str(extracted), "B",
                    "--dest", tmp_name], check=True)
    produced = extracted / tmp_name
    if not produced.exists():
        cands = sorted(extracted.rglob("*.iso"), key=lambda p: p.stat().st_mtime)
        if not cands:
            raise FileNotFoundError("pyisotools produced no ISO")
        produced = cands[-1]
    shutil.move(str(produced), str(out_iso))
    return out_iso
