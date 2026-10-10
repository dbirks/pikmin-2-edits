# ADR-0016: Cave/treasure data survey — real paths, grammar, and what the compiler must not do

**Date:** 2026-10-10
**Status:** accepted

## Context
Task t2 of the active goal: parse the real cave + treasure data so a multi-floor
cave can be compiled into the extracted tree instead of guessed from wiki pages.

## Measured against the verified GPVE01 extract (guarded, 13.5 GiB free after)
* Paths: `files/user/Mukki/mapunits/caveinfo/*.txt` (spec omitted the `files/`
  prefix), room layouts referenced per floor by `f008`, light ini by `f009`,
  treasures at `files/user/Abe/Pellet/{us,jpn,pal}/otakara_config.txt`.
  Two caveinfo filenames are Japanese → no ASCII-path assumptions.
* Grammar: Shift-JIS, CRLF, repeated `# CaveInfo` / `N # FloorInfo` blocks of
  `{key} <type> <value>` rows ending `{_eof}`.
* Counts: 85 files, 328 FloorInfo blocks, 5456 floor rows, **0** blocks missing
  `{_eof}`. 32 files have no FloorInfo of their own (`vs_*`, several `ch_*`) —
  they are not "empty caves", their floors live elsewhere; don't infer emptiness.
* **Open question, recorded honestly:** the numeric prefix on a section header is
  *not* the entry count (declared 2 vs 15 rows in `Dam_cave_conc.txt`; declared
  34 vs 19 in `caveinfo.txt`). Meaning unresolved; the first version of
  `check_floor_counts` asserted `declared == rows` and would have flagged 85/85
  files as broken. It now asserts only `{_eof}` termination and reports
  `matches_declared` as data.

## Decision
* Editors are **in-place substring patches** (`cavedata.patch_text`, unique-match
  enforced). A `render_sections` re-serialiser existed for ~10 minutes and was
  deleted: it dropped the bare `{`/`{}` structure lines and the header numeric
  prefix, i.e. it silently restructured real game files. A test now pins that a
  no-op patch is byte-identical and that a digit edit moves exactly one byte.
* Safety gates for the compile step (t3): floor row count only changes together
  with existing `f008`/`f009` resources; encoding/CRLF/tabs preserved; static
  validation before repack; static validation never counts as an in-game pass.

## Room-layout files (`mapunits/units/*.txt`), also surveyed
`N # number of units` then one `{ ... }` record per room with positional fields
(version, foldername, dX/dZ, room type, flags, num doors, index,
dir/offs/wpindex, door links). Here the header count IS the record count
(`all_units_tsuchi.txt`: declared 27, rooms 27) — unlike the caveinfo prefix.
Because a record's door block length follows `num_doors`, fixed positions past
the door count must not be over-trusted; `cavedata.ROOM_FIELDS` is documented as
best-effort and the validator treats door data as a token tail.

## Evidence
`design/caves/inventory.md`, `design/caves/caveinfo-inventory.json`,
`src/pikminlab/cavedata.py`, `tests/unit/test_cavedata.py` (7 passed; fixture is
synthetic — no disc bytes in git; integration test skips without a local extract).

## Consequences
Reuse targets are known and small (`caveinfo_*`, `kfes_*`, 12–60 rows, single
units file each). Unknowns deferred to t3: prefix semantics, how a cave's floors
are selected for a given cave ID, and which field places the entrance.
