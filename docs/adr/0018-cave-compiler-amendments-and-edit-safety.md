# ADR-0018: Cave compiler — corrections to ADR-0016, byte-safe editing, and what "exit present" means

**Date:** 2026-10-10
**Status:** accepted (amends ADR-0016 findings; supersedes nothing in it)

## 1. Two ADR-0016 "findings" were parser artifacts — corrected
The first parser only accepted braced `{key}` rows. Consequences, now measured:
* **The section-header prefix IS meaningful: it is the cave's floor count.**
  `forest_1..4` → declared 5,5,7,7 with 5,5,7,7 FloorInfo blocks;
  `Dam_cave_conc` 2/2; `caveinfo_tsuchi` 5/5. ADR-0016's "prefix is not a row
  count, meaning unresolved" was right only because a *floor* is a whole block
  (18 field rows), not a row. Validator rule `r1` now asserts it.
* "32 of 85 files have no FloorInfo" and "0 files with non-empty ItemInfo" were
  both **false**: `TekiInfo`/`ItemInfo`/`GateInfo`/`CapInfo` rows are *unbraced*
  (`haniwa 10 	# weight`). forest_3 alone holds 5 treasures (diamond_blue_l,
  makigai, dia_a_green, saru_head, haniwa), so treasure placement lives in
  caveinfo after all.

## 2. Per-floor structure (measured, used by the compiler)
`CaveInfo`, then per floor: `FloorInfo` (braced fields) + `TekiInfo` + `ItemInfo`
+ `GateInfo` + `CapInfo`. `f000`/`f001` = this floor's index (階はじめ/階おわり),
contiguous `0..n-1`; `f002/f003/f004/f014` are **capacities** (敵/アイテム/ゲート/
キャップ最大数) and the paired section's leading `# num` must be ≤ them — this
holds on **all 328 vanilla floors**, so it is a hard gate (`r3`), not a guess.
`f005` is not the units file's room count (2 vs 9 observed) — don't assert it.

## 3. Editing these files must be byte-transparent (bug that cost 5 850 bytes)
First reskin attempt decoded `otakara_config.txt` as `shift_jis` with
`errors="replace"` and re-encoded: the file shrank 89 485 → 83 635 bytes. Bytes
without a valid Shift-JIS round-trip became U+FFFD. The compiler therefore edits
through **latin-1** (lossless byte↔char mapping) and only parses with shift_jis
when it needs to *understand* text. Test: `test_japanese_comment_bytes_survive_latin1_editing`
compares non-ASCII byte counts and comment multisets before/after.

## 4. "Exit presence" has a real referent: 帰還噴水 (f007)
Vanilla forest_3 has `f007=1` on exactly one floor (the deepest). That fountain is
how you leave, so the validator asserts (a) at least one floor has it after compile
and (b) no vanilla exit floor lost it (`r5b`), plus ladder contiguity (`r5c`).
A test (`test_validate_catches_a_sealed_exit`) proves turning it off FAILs statically.

## 5. Room graph: count is checkable, connectivity is not (yet)
`declared == parsed room count` holds on every file sampled (27/27, 8/8, 9/9) → `r5`.
A room's door block length follows its `num_doors`, so fixed positions past the
door count are unreliable: a door-position heuristic produced a **false negative on
an untouched vanilla file** (`2_MAT_hit4_nor2_tsuchi.txt`). So room-to-room
reachability and "Pikmin can actually get out" are asserted **in-game at t5**, not
statically. Static green ≠ playable (AGENTS.md lane separation).

## 6. Which slot, and why — measured from the disc, not from memory
`user/Abe/stages.txt` gives the Day-1 (`forest`) course `start = (381.724, -70.880,
2634.461)`. `user/Abe/map/forest/defaultgen.txt` holds exactly 4 cave entrances;
distances to spawn: **f_03 1245.2**, f_02 1741.4, f_04 2092.0, f_01 2653.7. f_03 →
`forest_3.txt`, 7 floors, single units file per floor. So the authored cave reuses
f_03 and needs no new actor data (adding an entrance means binary actor edits —
out of scope). Entrance actor id, caveinfo filename and position are asserted
unchanged (`r9`–`r11`), as is BGM list cardinality (`r12`).

## 7. Decision: compile = line-slice editor, deterministic and reversible
`pikminlab cave compile|validate|apply|restore` (`src/pikminlab/cavebuild.py`):
edits happen on the original line list inside the owning section's span, so
untouched bytes are copied verbatim. `compile_design()` is pure and byte-stable
(twice identical; idempotent on an already-patched tree). `apply()` first stores
pristine bytes under `workspace/cave-patches/<stem>/orig/` and writes a hash
manifest; `restore()` returns byte-identical files — so a failing build never
strands the tree (the ISO stays the only immutable source).
Current build: 62 checks, 0 problems, +22 bytes in `forest_3.txt`, −4 bytes in
`otakara_config.txt` (`reports/cave-compile-forest-3-reprise.json`).
Tests: 18 passed, including 2 integration tests that compile/validate/restore
against the real extract.
