# Anomaly audit — every captured frame, numerically (t6)

Machine pass: `scripts/frame_audit.py` over `reports/runs/**.png` (249 frames, 40 run dirs);
full per-run detail in `reports/frame-audit.json`. Findings with decisions:
ADR-0021 (method + threshold miscalibration), ADR-0022 (black captures),
ADR-0023 (duplicate G0 captures). This file is the path-keyed list.

| finding | count | what it can prove | what it cannot |
| --- | --- | --- | --- |
| `all_black` (mean 0.0, 1 colour) | 19 | nothing was rendered in that capture | whether the game was actually broken |
| `black_or_idle` (mean<0.02 or <32 colours) | 17 | a near-black screen | black screen vs shadowed cave |
| `flat_geometry` (<512 colours, mean≥0.05) | 86 | palette collapse | text screen vs missing texture (ADR-0021 F1) |
| `empty_scene` (tile spread<0.05, <2000 colours) | 13 | very low scene variance | flat shading vs empty room |
| `self_progressing` (adjacent RMSE>0.30) | 40 pairs | the scene moves by itself → invalidates frame-delta input oracles (ADR-0020) | whether input also worked |
| `hud_pulse` (0.005–0.30) | 156 pairs | ordinary animation/UI noise | — |
| `frozen_frame` (byte-identical captures) | 3 | a sample is not independent evidence | cause (stale read vs true freeze) |


- `reports/runs/2026-10-09T202546Z-pad-drive/t0_warning.png` — flat/empty scene — needs eyes, mean=0.0734 colours=256 spread=0.098
- `reports/runs/2026-10-09T202546Z-pad-drive/t1_after_start.png` — flat/empty scene — needs eyes, mean=0.067 colours=256 spread=0.1098
- `reports/runs/2026-10-09T202546Z-pad-drive/t2_after_start.png` — flat/empty scene — needs eyes, mean=0.0776 colours=256 spread=0.0902
- `reports/runs/2026-10-09T202546Z-pad-drive/t3_after_start.png` — flat/empty scene — needs eyes, mean=0.0722 colours=256 spread=0.102
- `reports/runs/2026-10-09T202733Z-pad-drive/t0_warning.png` — flat/empty scene — needs eyes, mean=0.0781 colours=256 spread=0.0902
- `reports/runs/2026-10-09T202733Z-pad-drive/t1_after_start.png` — flat/empty scene — needs eyes, mean=0.067 colours=256 spread=0.1098
- `reports/runs/2026-10-09T202733Z-pad-drive/t2_after_start.png` — flat/empty scene — needs eyes, mean=0.0751 colours=256 spread=0.0941
- `reports/runs/2026-10-09T202733Z-pad-drive/t3_after_start.png` — flat/empty scene — needs eyes, mean=0.0728 colours=256 spread=0.098
- `reports/runs/2026-10-09T202936Z-button-mash/mash1.png` — flat/empty scene — needs eyes, mean=0.0663 colours=256 spread=0.1098
- `reports/runs/2026-10-09T202936Z-button-mash/mash2.png` — flat/empty scene — needs eyes, mean=0.0778 colours=256 spread=0.0902
- `reports/runs/2026-10-09T202936Z-button-mash/mash3.png` — flat/empty scene — needs eyes, mean=0.0673 colours=256 spread=0.1098
- `reports/runs/2026-10-09T202936Z-button-mash/t0.png` — flat/empty scene — needs eyes, mean=0.0765 colours=256 spread=0.0941
- `reports/runs/2026-10-09T203342Z-gpad-drive/start1.png` — flat/empty scene — needs eyes, mean=0.0673 colours=256 spread=0.1098
- `reports/runs/2026-10-09T203342Z-gpad-drive/start2.png` — flat/empty scene — needs eyes, mean=0.0776 colours=256 spread=0.0902
- `reports/runs/2026-10-09T203342Z-gpad-drive/start3.png` — flat/empty scene — needs eyes, mean=0.0697 colours=256 spread=0.1059
- `reports/runs/2026-10-09T203342Z-gpad-drive/t0_warning.png` — flat/empty scene — needs eyes, mean=0.0734 colours=256 spread=0.098
- `reports/runs/2026-10-09T203550Z-gpad-drive/t0_warning.png` — flat/empty scene — needs eyes, mean=0.0757 colours=256 spread=0.0941
- `reports/runs/2026-10-09T212441Z-serve/s_menu.png` — flat/empty scene — needs eyes, mean=0.0471 colours=637 spread=0.0157

### Fully black captures (ADR-0022) — every one of these invalidated a 'fresh screenshot' leg

- `reports/runs/2026-10-09T203550Z-gpad-drive/start2.png`
- `reports/runs/2026-10-09T214140Z-serve/g0.png`
- `reports/runs/2026-10-09T221807Z-serve/mc1.png`
- `reports/runs/2026-10-09T222725Z-serve/s1.png`
- `reports/runs/2026-10-09T223119Z-serve/f1.png`
- `reports/runs/2026-10-09T225828Z-inputprobe/cap_title.png`
- `reports/runs/2026-10-09T225921Z-probe/t0.png`
- `reports/runs/2026-10-10T021840Z-serve/a41.png`
- `reports/runs/2026-10-10T045540Z-headless-smoke/shot2.png`
- `reports/runs/g2-header-observe/g1.png`
- `reports/runs/g2-header-observe2/h2.png`
- `reports/runs/g2-header-observe2/hA.png`
- `reports/runs/g2-observe-2/s02.png`
- `reports/runs/g2-observe-2/s05.png`
- `reports/runs/g2-observe-3/f01_START.png`
- `reports/runs/g2-observe-3/f04_START.png`
- `reports/runs/loco-1/c2.png`
- `reports/runs/loco-2/step03.png`
- `reports/runs/loco-2/step06.png`

### Duplicate captures (ADR-0023)
- `reports/runs/2026-10-09T225225Z-g0/run1/capture.png` == `run2/capture.png` (independent G0 starts!)
- `reports/runs/2026-10-10T021234Z-serve/a11.png` == `a20.png`
- `reports/runs/2026-10-10T021840Z-serve/a31.png` == `a40.png`

## Caveats owned by the agent, not the game
- `all_black` was first reported as `unreadable`: `if not st['mean']` is true for 0.0.
- The skill's 'UI pulse ~1-2%' band is wrong on real screens: measured medians 0.051–0.254.
- Colour-count rules cannot separate the health-warning text screen from a missing-geometry bug;
  they triage, they do not adjudicate.
