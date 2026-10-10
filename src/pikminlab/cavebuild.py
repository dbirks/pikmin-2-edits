"""Compile an authored cave design into the extracted disc tree (data lane, t3).

Design documents (`design/caves/*.yaml`) are the source of truth; this module
turns one into whole-file bytes. Two properties are load-bearing and tested:

1. **Deterministic** — the same design + same tree always produces byte-identical
   output, so a build hash means something (no timestamps, no dict order, no
   "patch the previously patched file" state).
2. **Surgical** — edits happen on the original line list inside the section block
   they belong to. Everything outside those lines is copied verbatim, including
   Shift-JIS bytes, CRLF, tab indentation and trailing spaces. Re-serialising
   parsed structures is forbidden (it silently dropped `{`/`}` lines and header
   counts — ADR-0016/0018).

Nothing here touches the ISO: it reads/writes the extract tree under
`workspace/extracted/root`, and `apply()` first saves the original bytes so
`restore()` can undo a build without re-extracting 1 GB.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from . import cavedata

WORKSPACE = Path("workspace")
BACKUP_ROOT = WORKSPACE / "cave-patches"
BGM_REL = "files/user/Totaka/BgmList.txt"
UNITS_DIR = "files/user/Mukki/mapunits/units"
LIGHT_DIR = "files/user/Abe/cave"
OTAKARA_REL = "files/user/Abe/Pellet/{region}/otakara_config.txt"

_HEADER = re.compile(r"(?P<prefix>\d+)?\s*#\s*"
                     r"(?P<name>CaveInfo|FloorInfo|TekiInfo|ItemInfo|GateInfo|CapInfo)")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Editing uses latin-1 on purpose: it is byte-transparent, so Shift-JIS comment
# bytes (every Japanese comment in these files) survive untouched. Decoding with
# shift_jis/errors="replace" and re-encoding DESTROYED 5 850 bytes of
# otakara_config.txt on the first try — bytes that have no valid Shift-JIS
# round-trip became U+FFFD. Parse with shift_jis when you need to understand the
# text; edit with latin-1 when you need to preserve it.
def _split(raw: bytes) -> list[str]:
    return raw.decode("latin-1").splitlines(keepends=True)


def _join(lines: list[str]) -> bytes:
    return "".join(lines).encode("latin-1")


def _eol(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n"


def blocks(lines: list[str]) -> list[dict]:
    """Section blocks with line spans, in document order.

    `floor` is the index of the FloorInfo block this section belongs to (a cave
    file is CaveInfo, then per floor: FloorInfo + Teki/Item/Gate/CapInfo — each
    floor's own tables, measured on forest_1..4, ADR-0018)."""
    out: list[dict] = []
    cur: dict | None = None
    floor = -1
    cavedata.parse_blocks(b"")            # ensures SECTION_RE is compiled
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            continue
        m = cavedata.SECTION_RE.search(line)
        if m:
            if m.group("name") == "FloorInfo":
                floor += 1
            cur = {"name": m.group("name"), "floor": -1 if m.group("name") == "CaveInfo" else floor,
                   "declared": int(m.group("prefix")) if m.group("prefix") else None,
                   "hdr": i, "body": i + 2}   # header, then '{'
            out.append(cur)
            continue
        if cur is not None and line.strip() == "}":
            cur["close"] = i
            cur = None
    return out


def _block(blks: list[dict], name: str, floor: int = 0) -> dict:
    for b in blks:
        if b["name"] == name and (b["floor"] == floor or name == "FloorInfo" and b["floor"] == floor):
            return b
    raise KeyError(f"no {name} block for floor {floor}")


def _content_lines(b: dict, lines: list[str]) -> list[int]:
    """Line indices of a block's content rows (between '{' and '}').

    FloorInfo rows are braced (`{f007} 4 0`); Teki/Item/Gate/Cap rows are bare
    (`haniwa 10`). Both are content; only the structural `{`, `}` and `{_eof}`
    lines are not. Excluding everything that starts with `{` once made every
    FloorInfo field invisible to the editor."""
    keep = []
    for i in range(b["body"], b.get("close", len(lines))):
        t = lines[i].strip()
        if not t or t in ("{", "}") or t.startswith("{_eof}"):
            continue
        keep.append(i)
    return keep


def set_field(blks: list[dict], lines: list[str], floor: int, key: str, value: str) -> None:
    """Change one braced `{key}` entry's value in floor `floor`'s FloorInfo."""
    b = _block(blks, "FloorInfo", floor)
    hits = [i for i in _content_lines(b, lines) if lines[i].strip().startswith("{" + key + "}")]
    if len(hits) != 1:
        raise ValueError(f"{key}: expected 1 row on floor {floor}, found {len(hits)}")
    i = hits[0]
    # keep the original indentation, type tag, trailing spaces, comment and EOL;
    # swap ONLY the value token (these files are full of meaningful whitespace)
    m = re.match(r"^((?: |	)*\{" + re.escape(key) + r"\} +\S+ +)(\S+)(.*)$", lines[i], re.S)
    if not m:
        raise ValueError(f"{key}: unrecognised row shape: {lines[i]!r}")
    lines[i] = m.group(1) + str(value) + m.group(3)


def set_rows(blks: list[dict], lines: list[str], floor: int, section: str,
             rows: list[str], indent: str = "\t") -> None:
    """Replace a table's content lines, rewriting its leading `N \\t# num` row.

    `rows` are content strings WITHOUT comment (e.g. 'haniwa 10'); the section's
    own comment style is taken from the row it replaces, defaulting to '# weight'
    for ItemInfo / '# type' etc. only where the vanilla line already had one."""
    b = _block(blks, section, floor)
    idx = _content_lines(b, lines)
    if not idx:
        raise ValueError(f"{section} floor {floor}: no content lines to anchor on")
    num_i = idx[0]
    num_line = lines[num_i]
    comment = ""
    if "#" in num_line:
        comment = " \t# " + num_line.split("#", 1)[1].strip()
    eol = _eol(num_line)
    new = [f"{indent}{len(rows)}{comment}{eol}"]
    row_comment = ""
    for i in idx[1:]:
        if "#" in lines[i]:
            row_comment = " \t# " + lines[i].split("#", 1)[1].strip()
            break
    if not row_comment:
        row_comment = " \t# weight" if section == "ItemInfo" else ""
    for r in rows:
        new.append(f"{indent}{r}{row_comment}{eol}")
    lines[idx[0]:idx[-1] + 1] = new


def compile_design(design: dict, root: Path) -> dict[str, bytes]:
    """Pure: design + tree on disk -> {relpath: new bytes}. Call it twice, get the
    same bytes; it never reads a file it is about to write in a later call."""
    rel = design["slot"]["caveinfo"]
    raw = (root / rel).read_bytes()
    lines = _split(raw)
    blks = blocks(lines)

    for f in design.get("floors", []):
        fi = f["floor"]
        if "return_fountain" in f:
            set_field(blks, lines, fi, "f007", "1" if f["return_fountain"] else "0")
            blks = blocks(lines)
        if "light" in f:
            set_field(blks, lines, fi, "f009", f["light"])
            blks = blocks(lines)
        if "item_capacity" in f:
            set_field(blks, lines, fi, "f003", str(f["item_capacity"]))
            blks = blocks(lines)
        if "items" in f:
            rows = [f"{i['name']} {i.get('weight', 10)}" for i in f["items"]]
            set_rows(blks, lines, fi, "ItemInfo", rows)
            blks = blocks(lines)

    patches = {rel: _join(lines)}

    for ed in design.get("reskin", []):
        orel = OTAKARA_REL.format(region=ed["region"])
        otext = (root / orel).read_bytes().decode("latin-1")
        anchor = re.search(rf"name\s+{re.escape(ed['treasure'])}\b", otext)
        if not anchor:
            raise ValueError(f"otakara record {ed['treasure']!r} not found in {orel}")
        end = otext.index("\n}", anchor.start())
        seg = otext[anchor.start():end]
        for field in ("archive", "bmd"):
            if field not in ed:
                continue
            m = re.search(rf"\n(\s*{field}\s+)(\S+)", seg)
            if not m:
                raise ValueError(f"{ed['treasure']}: no {field} field")
            seg = seg[: m.start(2)] + ed[field] + seg[m.end(2):]
        patches[orel] = (otext[: anchor.start()] + seg + otext[end:]).encode("latin-1")
    return {k: patches[k] for k in sorted(patches)}


# ---------------------------------------------------------------- validation

def _treasure_names(root: Path, region: str = "us") -> set[str]:
    text = (root / OTAKARA_REL.format(region=region)).read_text("shift_jis", errors="replace")
    return set(re.findall(r"^\s*name\s+(\S+)", text, re.M))


def validate(design: dict, root: Path) -> list[dict]:
    """Static checks. Each problem is a dict with rule/ok/detail.

    Rules R1/R2 are measured invariants of the *vanilla* data (R2 holds on all 328
    GPVE01 floors; R1 on every cave sampled) — so a compiled cave that breaks them
    is our bug, not the game's quirk. A green board here is a preflight, never an
    in-game pass (ADR-0016/0018)."""
    problems: list[dict] = []

    def check(rule: str, ok: bool, detail: str = "") -> None:
        problems.append({"rule": rule, "ok": bool(ok), "detail": detail})

    rel = design["slot"]["caveinfo"]
    p = root / rel
    check("r0-caveinfo-exists", p.is_file(), str(p))
    if not p.is_file():
        return problems
    lines = _split(p.read_bytes())
    blks = blocks(lines)
    # braced rows of one FloorInfo block -> {key: last token}
    def fields_of(b: dict) -> dict[str, str]:
        out = {}
        for i in _content_lines(b, lines):
            t = lines[i].strip()
            if t.startswith("{"):
                toks = t.split("}", 1)[1].split("#")[0].split()
                out[t.split("}")[0][1:].strip()] = toks[-1] if toks else ""
        return out
    floors = [b for b in blks if b["name"] == "FloorInfo"]
    check("r1-declared-equals-floor-count", floors[0]["declared"] == len(floors),
          f"declared={floors[0]['declared']} blocks={len(floors)}")
    check("r2-slot-floors-unchanged", len(floors) == design["slot"]["floors"],
          f"design={design['slot']['floors']} actual={len(floors)}")

    caps = {"TekiInfo": "f002", "ItemInfo": "f003", "GateInfo": "f004", "CapInfo": "f014"}
    treasures: list[str] = []
    for fi, fb in enumerate(floors):
        fields = fields_of(fb)
        for sec, key in caps.items():
            try:
                b = _block(blks, sec, fi)
            except KeyError:
                continue
            idx = _content_lines(b, lines)
            n = int(lines[idx[0]].split()[0]) if idx else 0
            check(f"r3-capacity[{fi}:{sec}]", n <= int(float(fields[key])),
                  f"num={n} capacity {key}={fields[key]}")
            if sec == "ItemInfo":
                for i in idx[1:]:
                    name = lines[i].split()[0]
                    treasures.append(name)
        for fk in ("f008", "f009"):
            v = fields.get(fk)
            if not v or v == "none":
                continue
            base = root / (UNITS_DIR if fk == "f008" else LIGHT_DIR) / v
            check(f"r4-reference[{fi}:{fk}]", base.is_file(), str(base))
        graph = fields.get("f008")
        if graph and (root / UNITS_DIR / graph).is_file():
            u = cavedata.parse_units((root / UNITS_DIR / graph).read_bytes())
            # Only the record count is asserted: a room's door block length
            # follows num_doors, so the positional door fields are NOT reliable
            # enough to prove connectivity (they made this rule fail on an
            # untouched vanilla file). Room-to-room reachability and "can you get
            # out" are asserted in-game at t5, not statically (ADR-0018).
            check(f"r5-graph[{fi}]", u["declared"] == len(u["rooms"]) > 0,
                  f"{graph}: declared={u['declared']} rooms={len(u['rooms'])}")

    # r5b — exit presence. 帰還噴水 (f007) is the "return fountain": it is what
    # carries Pikmin back to the overworld, and vanilla forest_3 has it on exactly
    # one floor (the deepest). A compiled cave must keep every vanilla exit and
    # still contain at least one, otherwise the E2E run can enter and never leave.
    def fountain_fls(text_lines: list[str]) -> list[int]:
        out = []
        for idx, b in enumerate([x for x in blocks(text_lines) if x["name"] == "FloorInfo"]):
            for i in _content_lines(b, text_lines):
                t = text_lines[i].strip()
                if t.startswith("{f007}"):
                    toks = t.split("}", 1)[1].split("#")[0].split()
                    if toks and toks[-1] == "1":
                        out.append(idx)
        return out
    now_f = fountain_fls(lines)
    orig = BACKUP_ROOT / design.get("_stem", Path(rel).stem) / "orig" / rel
    was_f = fountain_fls(_split(orig.read_bytes())) if orig.is_file() else [len(floors) - 1]
    check("r5b-exit-fountain-present", bool(now_f), f"floors with f007=1: {now_f}")
    check("r5b-exit-fountains-kept", all(f in now_f for f in was_f),
          f"vanilla exits {was_f} still present in {now_f}")
    ladder = []
    for b in [x for x in blks if x["name"] == "FloorInfo"]:
        fl = {}
        for i in _content_lines(b, lines):
            t = lines[i].strip()
            if t.startswith("{f000}") or t.startswith("{f001}"):
                fl[t.split("}")[0][1:].strip()] = t.split("}", 1)[1].split("#")[0].split()[-1]
        ladder.append((int(fl.get("f000", -1)), int(fl.get("f001", -1))))
    check("r5c-floor-ladder", ladder == [(i, i) for i in range(len(ladder))],
          f"floors 0..n-1 contiguous, got {ladder[:3]}…{ladder[-1:]}")

    known = _treasure_names(root)
    unknown = [t for t in treasures if t not in known]
    check("r6-treasures-known", not unknown, f"unknown={unknown[:5]}")
    check("r7-treasure-count>=2", len(treasures) >= 2, f"found={sorted(set(treasures))}")
    expect = design.get("expect", {})
    if "treasures_total" in expect:
        check("r8-expected-treasure-total", len(treasures) == expect["treasures_total"],
              f"actual={len(treasures)} expected={expect['treasures_total']}")

    # the slot we claim to reuse must still be the actor the game loads
    dg = (root / "files/user/Abe/map" / design["slot"]["area"] / "defaultgen.txt")
    txt = dg.read_text("shift_jis", errors="replace")
    ents = cavedata.cave_entrances(dg.read_bytes())
    mine = [e for e in ents if e["stage_id"] == design["slot"]["stage_id"]]
    check("r9-entrance-actor-intact", len(mine) == 1 and mine[0]["caveinfo"] == Path(rel).name,
          f"matches={[(e['stage_id'], e['caveinfo']) for e in mine]}")
    if mine:
        got, want = mine[0]["pos"], tuple(design["slot"]["entrance_pos"])
        check("r10-entrance-pos-matches-design", all(abs(a - b) < 1e-4 for a, b in zip(got, want)),
              f"actor={got} design={want}")
    check("r11-cave-id-untouched", txt.count("{cave}") == len(ents), f"{txt.count('{cave}')} == {len(ents)}")
    bgm = root / BGM_REL
    rows = bgm.read_bytes().count(b"\n") if bgm.is_file() else -1
    check("r12-bgm-cardinality", rows > 0 and "BgmList" not in json.dumps(design.get("floors", [])),
          f"BgmList.txt lines={rows} (design must not change cave BGM list cardinality)")
    return problems


# ---------------------------------------------------------------- apply/undo

def apply_patches(root: Path, patches: dict[str, bytes], stem: str) -> dict:
    """Write compiled bytes into the tree, first backing up originals.

    Backups live in `workspace/cave-patches/<stem>/orig/` (generated data,
    gitignored) so `restore()` reverts without re-extracting the disc."""
    bdir = BACKUP_ROOT / stem / "orig"
    bdir.mkdir(parents=True, exist_ok=True)
    manifest = {"stem": stem, "root": str(root), "files": []}
    for rel in sorted(patches):
        target = root / rel
        cur = target.read_bytes()
        backup = bdir / rel
        if not backup.exists():                     # keep the FIRST (pristine) copy
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(cur)
        target.write_bytes(patches[rel])
        manifest["files"].append({"path": rel, "before_sha256": sha256(cur),
                                  "after_sha256": sha256(patches[rel]),
                                  "bytes_before": len(cur), "bytes_after": len(patches[rel])})
    (BACKUP_ROOT / stem / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def restore(root: Path, stem: str) -> list[str]:
    bdir = BACKUP_ROOT / stem / "orig"
    done = []
    for backup in sorted(bdir.rglob("*")):
        if not backup.is_file():
            continue
        rel = str(backup.relative_to(bdir))
        shutil.copyfile(backup, root / rel)
        done.append(rel)
    return done


def load(design_path: Path) -> dict:
    return yaml.safe_load(design_path.read_text())
