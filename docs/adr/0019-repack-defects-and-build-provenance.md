# ADR-0019: Repack defects found by proving the delta — non-ASCII filename damage, disc padding, and a pre-build tree guard

**Date:** 2026-10-10
**Status:** accepted

## What was required
t4 needs more than "an ISO came out": ISO hash, **per-file delta vs baseline**, and
a headless cold boot of the modified build. Proving the delta is what found two
defects that a boot test alone would have hidden.

## Defect 1 — pyisotools 2.4.7 mangles non-ASCII filenames on build (accepted, contained)
Comparing the FST tables of baseline vs built image (2 768 vs 2 766 files):

* **13 baseline paths vanish**, all with Japanese names (`コピー (2) 〜 0-0.txt`,
  `７種１０本0-0.txt`, `紫１００initgen.txt`, `パンモドキテストcaveinfo.txt`,
  `敵チェックcaveinfo.txt`, four `Nishimura/Camera/*cameraParms.txt`,
  `スナップショット/プロダクト/マリクラ-*-gameConfig.ini`).
* They reappear as **11 concatenated/truncated entries** (longest baseline name 49
  chars → longest built name 92), e.g.
  `caveinfo/パンモドキテス敵チェックcavunits`; two entries degrade to `''` and
  `user/Abe/map/newtest/nonloop/`.
* **Zero of the 13 are referenced by any text data in the tree** (grep across
  `files/user`, `files/message`), and every ASCII-named path survives intact.
  They are Nintendo's dev/test scratch assets, so gameplay is unaffected — but
  **the rebuilt image is not a faithful copy of the disc**, and no claim of that
  will be made. If a future lane ever needs one of those files, the repacker must
  be replaced or the FST patched directly.

## Defect 2 — a green build can be built from an unapplied tree (fixed)
The first ISO of this session was made from a tree that an integration test had
just restored, and it faithfully contained the **pristine** cave: ISO hash changed
(mangling alone) while `size_differing` was empty. Now
`pikminlab build` refuses (`BLOCKED: design NOT applied (pristine bytes in tree)`)
unless `--allow-stale`, by comparing the tree against each
`workspace/cave-patches/*/manifest.json` before repacking.

## Also recorded: sizes and dump verdicts are not comparable across tools
Owned baseline: 995,557,376 bytes; pyisotools output: 1,459,978,240 (= 712,880
sectors, full DVD). Dolphin's own `verify` says the **baseline** is NKit-format
*and* "unusual size", while the built image keeps the NKit note and loses the size
note. So ISO-level hashes differ for reasons unrelated to our edit; the meaningful
comparison is per-file, which is what `scripts/repack_delta.py` produces:

```
size_differing: [user/Abe/Pellet/us/otakara_config.txt,
                 user/Mukki/mapunits/caveinfo/forest_3.txt]   # exactly the patched two
extracted from built ISO: forest_3.txt a202d4a5… -> 02fc11ea…  matches patched tree ✓
                          otakara_config.txt 36de6f3b… -> 73cfe4be… matches ✓
```
(`extract_path` silently wrote nothing — its dest resolves against a `root` dir
derived from the ISO's parent — so the script hashes nodes in place using
pyisotools' own `seek(node._fileoffset); read(node.size)` access.)

## Build gate for this task
`builds/lab-cave.iso` sha256 `6a9da6425949d162c564bf816f92c8197253a8b25e04b8dfa50b8c3fc0f07174`,
12 s repack, manifest `reports/builds/lab-cave.json`, delta
`reports/builds/lab-cave-content-delta.json`.
Headless cold boot (Xvfb + `-v OpenGL`, ADR-0014): window 2 s, lit frame at 30 s
(mean 0.0768, 256 colours = pre-title text screen), two fresh captures
(RMSE 0.0195 — the 1-2 % UI pulse band), `read_bytes(0x80000000,6) == b'GPVE01'`,
clean teardown, `stray_pids: []` —
`reports/runs/2026-10-10T065914Z-headless-smoke/`.
An earlier identical-PASS run of the same ISO is
`reports/runs/2026-10-10T065815Z-headless-smoke/`, whose `shot_rmse` printed
`1005.92`: the script's own RMSE helper never divided by 65535. Fixed by
delegating to `pikminlab.frames.rmse` — evidence numbers must mean the same thing
across runs (ADR-0017).

## Asset-compiler success ≠ in-game success (AGENTS.md lane rule)
Proven here: repack is deterministic-in-content for our two files, the modified
image boots headless and identifies as GPVE01. **Not** claimed: that the authored
cave is playable — that is t5's input-only E2E, in a separate lane.
