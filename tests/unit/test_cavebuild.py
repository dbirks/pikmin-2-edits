"""Determinism + safety of the cave compiler (t3). Fixtures are synthetic.

The fixture tree is byte-authored in Shift-JIS with CRLF and Japanese comments so
these tests actually exercise the traps: latin-1 editing (a shift_jis
decode/encode round-trip silently dropped 5 850 bytes of otakara_config.txt),
unbraced ItemInfo rows, and per-floor section association.
"""
import json
from pathlib import Path

import pytest

from pikminlab import cavebuild as cb

FX = Path(__file__).resolve().parents[1] / "fixtures" / "cave" / "tree"
CAVE_REL = "files/user/Mukki/mapunits/caveinfo/synthetic_cave.txt"

DESIGN = {
    "slot": {"stage_id": "f_99", "area": "forest", "entrance_pos": [0.0, 0.0, 0.0],
             "caveinfo": CAVE_REL, "floors": 2},
    "floors": [{"floor": 0, "item_capacity": 1, "items": [{"name": "synth_treasure", "weight": 10}],
                "return_fountain": True, "light": "other_light.ini"}],
    "reskin": [{"treasure": "synth_treasure", "region": "us",
                "archive": "alt_model.szs", "bmd": "alt_model.bmd"}],
    "expect": {"treasures_total": 2},
    "_stem": "synthetic",
}


@pytest.fixture
def tree(tmp_path):
    for p in FX.rglob("*"):
        if p.is_file():
            d = tmp_path / p.relative_to(FX)
            d.parent.mkdir(parents=True, exist_ok=True)
            d.write_bytes(p.read_bytes())
    cb.BACKUP_ROOT = tmp_path / "cave-patches"      # keep tests out of workspace/
    return tmp_path


def test_compile_is_deterministic(tree):
    a = cb.compile_design(DESIGN, tree)
    b = cb.compile_design(DESIGN, tree)
    assert a == b and len(a) == 2
    assert all(v for v in a.values())


def test_edits_are_local_and_bytes_outside_them_are_untouched(tree):
    before = (tree / CAVE_REL).read_bytes()
    after = cb.compile_design(DESIGN, tree)[CAVE_REL]
    assert len(before.splitlines()) + 1 == len(after.splitlines())      # one row added
    # Sequence alignment, not index zip: inserting a row shifts every later line,
    # and set-difference is useless because these files repeat lines (`0 # num`).
    import difflib
    sm = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines())
    gone = [l for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal" for l in before.splitlines()[i1:i2]]
    added = [l for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal" for l in after.splitlines()[j1:j2]]
    assert len(gone) == 4 and len(added) == 5, (gone, added)
    touched = b" ".join(gone + added).decode("latin-1")
    for key in ("f003", "f007", "f009", "# num", "synth_treasure"):
        assert key in touched, key


def test_japanese_comment_bytes_survive_latin1_editing(tree):
    before = (tree / CAVE_REL).read_bytes()
    after = cb.compile_design(DESIGN, tree)[CAVE_REL]
    nonascii = lambda b: sum(1 for c in b if c > 0x7F)
    assert nonascii(after) == nonascii(before)              # no Shift-JIS byte mangled
    comments = lambda b: sorted(l.split("#", 1)[1] for l in b.decode("shift_jis").splitlines() if "#" in l)
    assert comments(after) == comments(before) or len(comments(after)) == len(comments(before)) + 1
    assert b"\t# weight\r\n" in after                        # row comment style preserved
    assert b"\r\n" in after                                  # CRLF preserved


def test_validate_accepts_the_compiled_tree(tree):
    cb.apply_patches(tree, cb.compile_design(DESIGN, tree), "synthetic")
    assert [p for p in cb.validate(DESIGN, tree) if not p["ok"]] == []


def test_validate_catches_capacity_exit_and_unknown_treasure(tree, tmp_path):
    # validate() reads the TREE, so a bad design must be compiled+applied first
    bad = json.loads(json.dumps(DESIGN))
    bad["floors"][0]["item_capacity"] = 0                    # num 1 > capacity 0
    cb.apply_patches(tree, cb.compile_design(bad, tree), "bad-capacity")
    rules = {p["rule"] for p in cb.validate(bad, tree) if not p["ok"]}
    assert "r3-capacity[0:ItemInfo]" in rules, rules
    deeper = json.loads(json.dumps(DESIGN))
    deeper["floors"][0]["items"] = [{"name": "not_a_treasure", "weight": 10}]
    cb.apply_patches(tree, cb.compile_design(deeper, tree), "bad-name")
    rules = {p["rule"] for p in cb.validate(deeper, tree) if not p["ok"]}
    assert "r6-treasures-known" in rules, rules


def test_validate_catches_a_sealed_exit(tree):
    """The return fountain is how you LEAVE a cave; turning the only one off must
    be a static FAIL, not a run that traps the player until a soft-reset."""
    sealed = json.loads(json.dumps(DESIGN))
    sealed["floors"] = [{"floor": 1, "return_fountain": False}]        # the vanilla exit floor
    sealed["slot"]["floors"] = 2
    cb.apply_patches(tree, cb.compile_design(sealed, tree), "sealed")
    rules = {p["rule"] for p in cb.validate(sealed, tree) if not p["ok"]}
    assert "r5b-exit-fountain-present" in rules, rules


def test_restore_returns_pristine_bytes(tree):
    orig = (tree / CAVE_REL).read_bytes()
    cb.apply_patches(tree, cb.compile_design(DESIGN, tree), "synthetic")
    assert (tree / CAVE_REL).read_bytes() != orig
    assert cb.restore(tree, "synthetic")
    assert (tree / CAVE_REL).read_bytes() == orig


def test_entrance_slot_must_match_the_design(tree):
    moved = json.loads(json.dumps(DESIGN))
    moved["slot"]["stage_id"] = "f_00"
    assert any(p["rule"] == "r9-entrance-actor-intact" and not p["ok"] for p in cb.validate(moved, tree))


@pytest.mark.integration
def test_real_design_compiles_and_validates_against_the_extract():
    """GPVE01 data, not the fixture: proves the authored design and the validator
    agree with the real cave. Reversible (apply → validate → restore)."""
    root = Path("workspace/extracted/root")
    design_path = Path("design/caves/forest-3-reprise.yaml")
    if not (root / "files/user/Mukki/mapunits/caveinfo/forest_3.txt").is_file():
        pytest.skip("no local extract (gitignored)")
    design = cb.load(design_path)
    design["_stem"] = design_path.stem
    cb.restore(root, design["_stem"])          # start from true pristine, not last run's leftovers
    pristine = (root / design["slot"]["caveinfo"]).read_bytes()
    try:
        patches = cb.compile_design(design, root)
        assert cb.compile_design(design, root) == patches           # deterministic
        cb.apply_patches(root, patches, design["_stem"])
        problems = cb.validate(design, root)
        assert [p for p in problems if not p["ok"]] == [], problems
        assert (root / design["slot"]["caveinfo"]).read_bytes() != pristine
    finally:
        cb.restore(root, design["_stem"])
        assert (root / design["slot"]["caveinfo"]).read_bytes() == pristine
        # the tree must be back exactly as the extract left it, byte for byte
        bak = cb.BACKUP_ROOT / design["_stem"] / "orig" / design["slot"]["caveinfo"]
        assert bak.read_bytes() == pristine
