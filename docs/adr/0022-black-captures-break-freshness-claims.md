# ADR-0022: 19 fully black captures — "fresh screenshot" was satisfiable without a rendered frame

**Date:** 2026-10-10 · **Status:** accepted

## Finding F2 (from the t6 audit)
19 PNGs have `mean == 0.0` and **1 distinct colour** — nothing was rendered — spread
across 15 runs, including gate evidence:
`2026-10-10T045540Z-headless-smoke/shot2.png`, `2026-10-09T225828Z-inputprobe/cap_title.png`,
`2026-10-09T225921Z-probe/t0.png`, `2026-10-09T203550Z-gpad-drive/start2.png`,
`g2-observe-2/s02,s05`, `g2-observe-3/f01_START,f04_START`, `g2-header-observe2/h2,hA`,
`loco-1/c2`, `loco-2/step03,step06`, plus 4 `*-serve` frames.

## Why this matters for the gates
`headless_smoke` asserted freshness as *different hashes* between two captures. A
black frame next to a lit one satisfies that, so the G0/G1/G2 "fresh screenshot"
assertion was satisfiable with **no rendering evidence at all** on the second sample.
The boot gates still stand on their other legs (window mapped, first capture lit,
disc-ID read at `0x80000000`, clean teardown), but the freshness claim was weaker
than documented, and any past statement leaning on it alone is downgraded.

## Decision
Freshness now requires **`frames.lit()` on both captures** *and* differing bytes
(`both_shots_lit` recorded in the result JSON). Capture is also taken after a settle
delay rather than on a fixed timer where the caller can choose.

## Root cause, as far as evidence goes (not settled)
Two plausible mechanisms, both consistent with 1-colour output: capturing while the
Xvfb window is unmapped/occluded or during a fade, and racing Dolphin's first
present after resume. Correlation supports the fade/timing family: the black frames
cluster at *transition* points (`cap_title`, `start2`, `f01_START`, `step03`) rather
than being random. Not proven; a capture-side retry-on-black is the cheap mitigation
next time a gate needs a fresh pair.
