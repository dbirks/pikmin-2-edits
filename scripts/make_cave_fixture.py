"""Build the synthetic cave tree used by tests/unit/test_cavebuild.py.

Authored deliberately: Shift-JIS Japanese comments, CRLF, tab indentation,
unbraced ItemInfo rows — the traps a naive parser/editor falls into (ADR-0018).
Run `uv run python scripts/make_cave_fixture.py` after editing.
"""
from pathlib import Path

TAIL = ("# TekiInfo\r\n{\r\n\t0 \t# num\r\n}\r\n# ItemInfo\r\n{\r\n\t{num} \t# num\r\n{items}"
        "}\r\n# GateInfo\r\n{\r\n\t0 \t# num\r\n}\r\n# CapInfo\r\n{\r\n\t0 \t# num\r\n}\r\n")


def floor(index: int, item_cap: int, fountain: int, items: str = "") -> str:
    return (
        ("2 # FloorInfo\r\n{" if index == 0 else "# FloorInfo\r\n{") + "\r\n"
        f"\t{{f000}} 4 {index} \t# \u968e\u306f\u3058\r\n"
        f"\t{{f001}} 4 {index} \t# \u968e\u304a\u308f\u308a\r\n"
        "\t{f002} 4 3 \t# \u6575\u6700\u5927\u6570\r\n"
        f"\t{{f003}} 4 {item_cap} \t# \u30a2\u30a4\u30c6\u30e0\u6700\u5927\u6570\r\n"
        "\t{f004} 4 0 \t# \u30b2\u30fc\u30c8\u6700\u5927\u6570\r\n"
        "\t{f014} 4 100 \t# \u30ad\u30e3\u30c3\u30d7\u6700\u5927\u6570\r\n"
        "\t{f005} 4 2 \t# \u30eb\u30fc\u30e0\u6570\r\n"
        f"\t{{f007}} 4 {fountain} \t# \u5e30\u9084\u5674\u6c34\r\n"
        "\t{f008} -1 synthetic_units.txt \t# \u4f7f\u7528\u30e6\u30cb\u30c3\u30c8\r\n"
        "\t{f009} -1 synthetic_light.ini \t# \u4f7f\u7528\u30e9\u30a4\u30c8\r\n"
        "\t{f00A} -1 none \t# VRBOX\r\n\t{f015} 4 1 \t# Version\r\n\t{_eof} \r\n}\r\n"
    ).replace("{num}", str(len(items.splitlines()) if items.strip() else 0)) + items


_items0 = ""
_items1 = "\tsynth_treasure 10 \t# weight\r\n"
CAVE = ("# CaveInfo\r\n{\r\n\t{c000} 4 34 \t# \u3084\u3054\u3068\uff08\u5730\u4e0b\uff09\r\n\t{_eof} \r\n}\r\n"
        + floor(0, 0, 0) + TAIL.replace("{num}", "0").replace("{items}", "")
        + floor(1, 1, 1) + TAIL.replace("{num}", "1").replace("{items}", _items1))

UNITS = (
    "#\r\n#\tunits definition file\r\n#\r\n2 \t# number of units\r\n# room_a\r\n{\r\n"
    "\t1 \t# version\r\n\troom_a \t# foldername\r\n\t1 1 \t# dX/dZ\r\n\t0 \t# room type\r\n"
    "\t0 0 \t# room Flags\r\n\t1 \t# num doors\r\n\t0 \t# index\r\n\t0 0 0 \t# dir/offs/wpindex\r\n"
    "\t1 \t# door links\r\n}\r\n# room_b\r\n{\r\n\t1 \t# version\r\n\troom_b \t# foldername\r\n"
    "\t1 1 \t# dX/dZ\r\n\t0 \t# room type\r\n\t0 0 \t# room Flags\r\n\t1 \t# num doors\r\n"
    "\t0 \t# index\r\n\t1 0 0 \t# dir/offs/wpindex\r\n\t0 \t# door links\r\n}\r\n"
)

OTAKARA = (
    "#\r\n2\t# size of configs\r\n{\r\n\tname\t\tsynth_treasure\r\n\tarchive\t\tsynth_treasure.szs\r\n"
    "\tbmd\t\tsynth_treasure.bmd\r\n\tradius\t\t35\r\n\theight\t\t23\r\n\tmoney\t\t40\r\n}\r\n"
    "{\r\n\tname\t\talt_model\r\n\tarchive\t\talt_model.szs\r\n\tbmd\t\talt_model.bmd\r\n"
    "\tradius\t\t35\r\n\theight\t\t25\r\n\tmoney\t\t90\r\n}\r\n"
)

ENTRANCE = (
    "# forest_synth\r\n{\r\n\t{v0.1} \t# version\r\n\t0 \t# reserved\r\n\t0 \t# respawn\r\n"
    "\t0 0 0 \t# name bytes\r\n\t0.000000 0.000000 0.000000 \t# pos\r\n\t0 0 0 \t# offset\r\n"
    "\t{item} {0002} \t# cave\r\n\t{\r\n\t\t{cave} \t# item id\r\n"
    "\t\t0.000000 0.000000 0.000000 \t# rotation\r\n\t\t{0002} \t# item local version\r\n"
    "\t\tsynthetic_cave.txt \r\n\t\tunits.txt \r\n\t\t{f_99} \t# id (for stages.txt)\r\n\t}\r\n}\r\n"
)

FILES = {
    "files/user/Mukki/mapunits/caveinfo/synthetic_cave.txt": CAVE.encode("shift_jis"),
    "files/user/Mukki/mapunits/units/synthetic_units.txt": UNITS.encode("shift_jis"),
    "files/user/Abe/cave/synthetic_light.ini": b"[light]\n0 0\n",
    "files/user/Abe/cave/other_light.ini": b"[light]\n1 1\n",
    "files/user/Abe/Pellet/us/otakara_config.txt": OTAKARA.encode("shift_jis"),
    "files/user/Abe/map/forest/defaultgen.txt": ENTRANCE.encode("shift_jis"),
    "files/user/Totaka/BgmList.txt": b"a\nb\nc\n",
}


def build(dest: Path) -> int:
    for rel, data in FILES.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return len(FILES)


if __name__ == "__main__":
    n = build(Path("tests/fixtures/cave/tree"))
    print(f"{n} fixture files under tests/fixtures/cave/tree")
