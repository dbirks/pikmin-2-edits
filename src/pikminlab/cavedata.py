"""Pikmin 2 cave + treasure data parsers (data lane, P3).

Format facts measured on the verified GPVE01 extract (ADR-0016) — the master
spec's `user/Mukki/mapunits/caveinfo/` is real, but the whole tree hangs under
`files/`, so the actual path is:

    files/user/Mukki/mapunits/caveinfo/*.txt      (cave + floor definitions)
    files/user/Mukki/mapunits/... units .txt      (room layouts, referenced by floor key f008)
    files/user/Abe/Pellet/<region>/otakara_config.txt

`caveinfo.txt` is Shift-JIS text with CRLF, made of `# Section` blocks of
`{key} <type> <value> \t# comment` lines plus a `{_eof}` terminator. Types seen:
`4` (int), `-1` (string path), `4 0.000000` (float in an int-tagged field).
Floor keys of interest: f000 floor id?, f008 units file, f009 light ini,
f00A VRBOX flooring, f015 version.

No copyrighted bytes ship with this repo: the parsers take paths, and the unit
test fixture is a synthetic file authored to the same grammar.
"""
from __future__ import annotations
import json
from pathlib import Path

CAVEINFO_REL = Path("files/user/Mukki/mapunits/caveinfo")
OTAKARA_REL_TMPL = Path("files/user/Abe/Pellet/{region}/otakara_config.txt")
EOF = "{_eof}"


def parse_sections(raw: bytes) -> dict[str, list[dict]]:
    """Split a caveinfo-style file into {section_name: [entry, ...]}.

    Entries keep their raw tokens so unknown keys survive a parse→write round
    trip byte-for-byte (the build lane must not reformat untouched lines)."""
    text = raw.decode("shift_jis", errors="replace")
    sections: dict[str, list[dict]] = {}
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("{"):
            current = stripped.lstrip("#").strip()
            sections.setdefault(current, [])
            continue
        if stripped.startswith("{") and current is not None:
            if "}" not in stripped:
                continue          # bare '{' / '}' structural lines, not entries
            key = stripped.split("}")[0][1:].strip()
            body = stripped.split("}", 1)[1]
            comment = ""
            if "#" in body:
                body, comment = body.split("#", 1)
                comment = comment.strip()
            tokens = body.split()
            sections[current].append({"key": key, "tokens": tokens, "comment": comment,
                                      "raw": line})
    return sections


def patch_text(raw: bytes, old: str, new: str) -> bytes:
    """Surgical substring edit inside ONE line; every other byte is untouched.

    Substring (not whole-line) semantics on purpose: these files are tab-indented
    with trailing spaces, and the first version asked callers for the full line
    and quietly destroyed that whitespace. Uniqueness is enforced, so an edit can
    never hit the wrong floor by accident. `render_sections`-style re-serialising
    is NOT offered: it dropped the bare `{`/`}` lines and the `34 # FloorInfo`
    numeric prefix, i.e. it restructured the file (found by a test, not in game).
    """
    text = raw.decode("shift_jis", errors="replace")
    if text.count(old) != 1:
        raise ValueError(f"expected exactly 1 occurrence of {old!r}, found {text.count(old)}")
    if "\n" in old or "\n" in new:
        raise ValueError("patch_text edits one line at a time; add/remove rows explicitly")
    return text.replace(old, new, 1).encode("shift_jis", errors="replace")


def floors(sections: dict[str, list[dict]]) -> list[dict]:
    """Floor entries as dicts of key -> value tokens (excluding {_eof})."""
    rows = []
    for sec in ("FloorInfo",):
        for e in sections.get(sec, []):
            if e["key"] == EOF[1:-1] or e["key"] == "_eof":
                continue
            rows.append(e)
    return rows


def cave_summary(path: Path) -> dict:
    sections = parse_sections(path.read_bytes())
    fl = floors(sections)
    units = [e["tokens"][-1] for e in fl if e["key"] == "f008" and e["tokens"]]
    return {"file": path.name,
            "sections": {k: len(v) for k, v in sections.items()},
            "floors": len(fl),
            "units_files": sorted({u for u in units if u}),
            "light_inis": sorted({e["tokens"][-1] for e in fl if e["key"] == "f009" and e["tokens"]}),
            "has_eof": any(e["key"] == "_eof" for e in sections.get("FloorInfo", [])),
            "other_sections": sorted(k for k in sections if k != "FloorInfo")}


def inventory(caveinfo_dir: Path) -> dict:
    """Numeric inventory of every caveinfo file: floor counts + referenced units.

    Floor count is the single most important safety number for the build lane:
    Pikmin 2 indexes a cave's floors from one table, so a cave whose floor count
    changes without the matching unit/light resources is how you get the
    black-screen and crash behaviours the master spec warns about."""
    out = {"dir": str(caveinfo_dir), "caves": [], "total_floors": 0}
    for p in sorted(caveinfo_dir.glob("*.txt")):
        s = cave_summary(p)
        out["caves"].append(s)
        out["total_floors"] += s["floors"]
    out["max_floors"] = max((c["floors"] for c in out["caves"]), default=0)
    return out


def parse_otakara(raw: bytes) -> list[dict]:
    """Treasure table rows: `<id> <item> <price> <drop> <flags...>` style lines.

    Kept deliberately token-level (see ADR-0016): the wiki documents column
    meanings but our first build only needs to locate and change one existing
    slot without disturbing column count or encoding."""
    rows = []
    for line in raw.decode("shift_jis", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("*"):
            continue
        rows.append({"raw": line, "tokens": s.split()})
    return rows


def write_json(obj: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(obj, indent=1, ensure_ascii=False))


SECTION_RE = None  # compiled lazily


def parse_blocks(raw: bytes) -> list[dict]:
    """Document-order blocks: `# CaveInfo` / `34 # FloorInfo` headers introduce a
    block whose entries run to the next header. Headers carry an optional integer
    PREFIX (the count of entries that follow) — that pairing is the invariant the
    build lane must preserve, and a plain name-keyed dict loses it.

    Note: section headers are not always at column 0; `34 # FloorInfo` is real and
    caused the first version of this parser to mis-file floor rows as CaveInfo
    entries (ADR-0016)."""
    global SECTION_RE
    import re
    if SECTION_RE is None:
        SECTION_RE = re.compile(r"(?P<prefix>\d+)?\s*#\s*"
                                r"(?P<name>CaveInfo|FloorInfo|TekiInfo|ItemInfo|GateInfo|CapInfo)")
    text = raw.decode("shift_jis", errors="replace")
    blocks: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        m = SECTION_RE.search(line)
        if m and not line.strip().startswith("{"):
            cur = {"name": m.group("name"),
                   "declared": int(m.group("prefix")) if m.group("prefix") else None,
                   "raw_header": line, "entries": []}
            blocks.append(cur)
            continue
        stripped = line.strip()
        if cur is None or not stripped.startswith("{") or "}" not in stripped:
            continue
        key = stripped.split("}")[0][1:].strip()
        body = stripped.split("}", 1)[1]
        comment = ""
        if "#" in body:
            body, comment = body.split("#", 1)
            comment = comment.strip()
        cur["entries"].append({"key": key, "tokens": body.split(), "comment": comment, "raw": line})
    return blocks


def floor_blocks(raw: bytes) -> list[dict]:
    return [b for b in parse_blocks(raw) if b["name"] == "FloorInfo"]


def check_floor_counts(raw: bytes) -> list[dict]:
    """Per FloorInfo block: the header's numeric PREFIX vs the rows parsed.

    IMPORTANT, measured (ADR-0016): the prefix is NOT an entry count — e.g.
    Dam_cave_conc.txt declares 2 and holds 15 `{fNNN}` rows; caveinfo.txt's first
    FloorInfo block declares 34 and holds 19. Its meaning is an open question, so
    `ok` here asserts only the one invariant that DOES hold everywhere: the block
    is terminated by `{_eof}`. Do not gate the build lane on declared==rows."""
    out = []
    for b in floor_blocks(raw):
        rows = [e for e in b["entries"] if e["key"] != "_eof"]
        out.append({"declared": b["declared"], "rows": len(rows),
                    "has_eof": any(e["key"] == "_eof" for e in b["entries"]),
                    "matches_declared": b["declared"] == len(rows),
                    "ok": any(e["key"] == "_eof" for e in b["entries"])})
    return out
