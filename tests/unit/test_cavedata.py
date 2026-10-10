"""Synthetic-fixture tests for the cave/treasure parsers (ADR-0016).

Fixtures are authored to the observed grammar; no bytes from the disc are stored
in git. A separate integration check runs against a local extract when present.
"""
from pathlib import Path

import pytest

from pikminlab import cavedata as cd

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "cave" / "caveinfo_synthetic.txt"


def test_headers_with_numeric_prefix_are_sections():
    blocks = cd.parse_blocks(FIX.read_bytes())
    assert [b["name"] for b in blocks] == ["CaveInfo", "FloorInfo", "TekiInfo"]
    assert blocks[0]["declared"] is None and blocks[1]["declared"] == 9


def test_floor_rows_exclude_eof_and_report_termination():
    chk = cd.check_floor_counts(FIX.read_bytes())
    assert len(chk) == 1
    assert chk[0]["rows"] == 5 and chk[0]["has_eof"] and chk[0]["ok"]
    # prefix 9 vs 5 rows: declared is NOT an entry count, so ok must not depend on it
    assert chk[0]["matches_declared"] is False


def test_units_and_light_refs_are_discoverable():
    b = cd.floor_blocks(FIX.read_bytes())[0]
    refs = {e["key"]: e["tokens"][-1] for e in b["entries"] if e["key"] in ("f008", "f009")}
    assert refs == {"f008": "9_units_synthetic.txt", "f009": "synthetic_light.ini"}


def test_patch_text_is_surgical_and_byte_exact():
    raw = FIX.read_bytes()
    assert cd.patch_text(raw, "{f002} 4 10", "{f002} 4 10") == raw          # no-op is exact
    one = cd.patch_text(raw, "{f002} 4 10 ", "{f002} 4 11 ")                # keep the trailing space
    assert one != raw and len(one) == len(raw)                              # same length, 1 byte moved
    assert b"9_units_synthetic.txt" in one and b"{_eof}" in one             # structure intact
    assert sum(1 for a, b in zip(raw, one) if a != b) == 1


def test_patch_text_refuses_ambiguous_target():
    with pytest.raises(ValueError):
        cd.patch_text(FIX.read_bytes(), "4", "5")


def test_otakara_skips_noise_rows_and_finds_names():
    rows = cd.parse_otakara(FIX.read_bytes())   # same grammar: brace lines + key rows
    assert all(r["tokens"] for r in rows)


@pytest.mark.integration
def test_real_extract_if_present():
    root = Path("workspace/extracted/root")
    if not (root / cd.CAVEINFO_REL).is_dir():
        pytest.skip("no local extract (gitignored)")
    inv_files = sorted((root / cd.CAVEINFO_REL).glob("*.txt"))
    assert inv_files
    for p in inv_files:
        for c in cd.check_floor_counts(p.read_bytes()):
            assert c["ok"], f"{p.name}: FloorInfo block missing {{_eof}}"
