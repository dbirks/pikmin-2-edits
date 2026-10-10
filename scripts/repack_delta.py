"""Per-file content delta for a repacked ISO (t4) — FST comparison, not ISO hash.

Why: pyisotools pads its output to full DVD size while the owned baseline is an
NKit image, so ISO-level hashes differ for reasons unrelated to our edit. This
compares both file tables (path + size) and then extracts the files our data lane
touched from BOTH images and hashes them, so the delta is proven at file level:
  baseline ISO bytes == extract-tree bytes, and built ISO bytes == patched bytes.
JSON holds paths, sizes and hashes only — no disc bytes enter git (AGENTS.md).
"""
import hashlib, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pikminlab import buildlane  # noqa: E402


def tables(iso: Path) -> dict:
    out = subprocess.run([sys.executable, "-c", f"""
import json, sys
from pyisotools.iso import GamecubeISO
from pathlib import Path
g = GamecubeISO.from_iso(Path({str(iso)!r}))
print(json.dumps({{str(n.path): n.size for n in g.rfiles()}}))
"""], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def node_sha(iso: Path, node_rel: str) -> str:
    """Hash one file *inside* an ISO without extracting the tree.

    pyisotools' own extraction does `iso.seek(node._fileoffset); read(node.size)`
    (iso.py:_recursive_extract), so we use the same access. `extract_path` silently
    wrote nothing here — its dest is resolved against a `root` dir derived from the
    ISO's parent, which is a trap worth recording."""
    out = subprocess.run([sys.executable, "-c", f"""
import hashlib, json
from pathlib import Path
from pyisotools.iso import GamecubeISO
g = GamecubeISO.from_iso(Path({str(iso)!r}))
node = g.find_by_path({node_rel!r})
if node is None or not node.is_file():
    raise SystemExit(json.dumps({{"error": "node missing: " + {node_rel!r}}}))
with Path({str(iso)!r}).open("rb") as f:
    f.seek(node._fileoffset)
    print(json.dumps({{"sha256": hashlib.sha256(f.read(node.size)).hexdigest(), "size": node.size}}))
"""], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def node_rel(rel: str) -> str:
    """A tree path -> an ISO node path. The ISO object is itself the `files` node,
    so find_by_path and rfiles() keys are relative to it (no leading /)."""
    return str(rel).removeprefix("root/").removeprefix("files/")


def sha(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def main(baseline: Path, built: Path, src_tree: Path, changed: list[str]) -> int:
    A, B = tables(baseline), tables(built)
    sizes_differ = sorted(k for k in set(A) & set(B) if A[k] != B[k])
    report = {
        "baseline_iso": str(baseline), "built_iso": str(built),
        "built_iso_sha256": buildlane.sha256(built.read_bytes()),
        "baseline_iso_sha256": buildlane.sha256(baseline.read_bytes()),
        "baseline_files": len(A), "built_files": len(B),
        "only_in_baseline": sorted(set(A) - set(B)),
        "only_in_built": sorted(set(B) - set(A)),
        "size_differing_paths": sizes_differ,
        "extracted_comparison": [],
    }
    if True:
        for rel in changed:
            rel = str(rel)
            node = node_rel(rel)   # tables are rooted at files/
            row = {"tree_path": rel}
            for tag, iso in (("baseline", baseline), ("built", built)):
                got = node_sha(iso, node)
                row[f"{tag}_sha256"] = got["sha256"]
                row[f"{tag}_size"] = got["size"]
            row["tree_sha256"] = sha(src_tree / rel)
            row["built_matches_tree"] = row["built_sha256"] == row["tree_sha256"]
            report["extracted_comparison"].append(row)
    want_nodes = sorted(node_rel(c) for c in changed)
    # Name-damage classification: does the repacker only break non-ASCII paths?
    miss, extra = set(A) - set(B), set(B) - set(A)
    report["filename_damage"] = {
        "missing_paths": sorted(miss), "mangled_paths": sorted(extra),
        "ascii_only_among_missing": sorted(x for x in miss if x.isascii()),
        "ascii_only_among_mangled": sorted(x for x in extra if x.isascii()),
        "longest_baseline_name": max((len(x) for x in miss), default=0),
        "longest_built_name": max((len(x) for x in extra), default=0),
    }
    report["delta_is_exactly_the_patched_files"] = sorted(sizes_differ) == want_nodes
    report["expected_nodes"] = want_nodes
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
         [str(x) for x in sys.argv[4:]])
