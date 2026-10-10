# ADR-0017: Game-level input on the headless host — proven by a categorical scene-state change, not by frame diffing

**Date:** 2026-10-10
**Status:** accepted

## What closes ADR-0015's open item
`t1` needed proof that our uinput pad actually drives the game on this host
(device-level was already proven: Dolphin has `event12` open). The press
attribution probes all "failed" — but the *route* they ran produced the evidence:

| frame | when | mean | distinct colours |
| --- | --- | --- | --- |
| `boot.png` | t=60 s, **before any input** | 0.0014 | **23** |
| `ready.png` | after START, START, A×10 through the documented route | 0.2212 | **97 901** |

`RMSE(boot, ready) = 0.301`. 23 → 97,901 colours is categorical, not animated
drift: a black pre-title screen became a fully rendered scene. The pad was the
only input source in that process (no `xdotool`, no memory writes, one owned
session), and ADR-0014 establishes that content only appears after the game is
actually past its opening states. Evidence:
`reports/runs/2026-10-10T063539Z-day1-input/result.json` + the frames in
`reports/runs/2026-10-10T023539Z-serve/`.

**Therefore: game-level input lands on this headless host.** G1's behavioural
half is no longer NOT_TESTED.

## What this does NOT prove (stated so nobody over-reads it)
1. **Per-button attribution.** Which of the 12 presses moved which state is
   unknown; the pause-overlay / dialog-cursor test is still the right instrument.
2. **Stick-driven locomotion.** LEFT→RIGHT produced no tile above its own dwell
   floor (deltas ≤0.0157 vs floors 0.02-0.106), and the "dwell" phase itself had
   whole-frame RMSE 0.127 — bigger than base-vs-left (0.122). In a live scene the
   world animates, so that experiment is uninformative, not negative: **NOT
   TESTED for stick**, per ADR-0015's design rule.
3. **Scene identity.** 98k colours means "full-colour content", but which screen
   (gameplay vs cutscene) needs human eyes or a symbol/RAM oracle.

## Tooling bugs found while re-reading that data (both fixed)
- `tile_means()` matched only `srgb(`, but `-colorspace Gray` makes ImageMagick
  print `gray(` → every tile list came back empty, so the probe reported FAIL
  with `tile_report: null` and nobody could tell "no signal" from "no analysis".
  The parser now accepts `gray|srgb|rgb` and **raises** on a short parse.
- Frame judgement was copy-pasted into three scripts; it now lives in
  `pikminlab/frames.py` (`tile_means`, `stats`, `lit`, `rmse`, `median`,
  `reversal_report`) so t5/t6 assert with one shared, tested definition.
- `serve` writes screenshots into its own `-serve` run dir, not the probe's, so a
  probe's `result.json` paths are the authority; the probe dirs contain no PNGs.

## Consequences for the next tasks
- t3/t4 can proceed: the input lane is not a hidden blocker for the cave E2E.
- t5 must use **categorical** oracles (colour count collapse/expansion, tile
  means on wait-states, door/floor transition signatures) rather than
  whole-frame RMSE over animated scenes, and needs the entrance approach
  authored as an explicit input trace with neutral releases.
- Still owed before any G3 claim: per-button attribution + named screens, ideally
  with the owner eyeballing `reports/runs/2026-10-10T023539Z-serve/ready.png`.
