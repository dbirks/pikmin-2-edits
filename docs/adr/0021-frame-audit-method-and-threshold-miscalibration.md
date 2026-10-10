# ADR-0021: Frame audit method — numeric signatures over 249 captures, and my UI-pulse threshold was wrong

**Date:** 2026-10-10 · **Status:** accepted · Evidence: `reports/frame-audit.json`, `design/anomalies.md`

## Method
No vision model on this session, so "what looks off" is answered by measurable
signatures over every captured PNG (249 frames / 40 run dirs), each with a stated
limit, plus a path-keyed shortlist for human eyes (`scripts/frame_audit.py`).
Rules: `all_black` (mean == 0.0), `black_or_idle` (mean < 0.02 or colours < 32),
`flat_geometry` (colours < 512 with mean ≥ 0.05), `empty_scene` (4x3 tile spread
< 0.05 and colours < 2000), `size_anomaly`, `frozen_frame` (byte-identical
captures), and temporal classes `self_progressing` (RMSE > 0.30), `hud_pulse`
(0.005–0.30), `static`.

## Counts
flat_geometry 86 · hud_pulse 156 · self_progressing 40 pairs · black_or_idle 17 ·
all_black 19 · empty_scene 13 · frozen_frame 3.

## Finding F1 — `flat_geometry` is inconclusive by construction (accepted)
The 86 hits are dominated by 256-colour **text screens** (health warning, MC
banners) — legitimate content that a colour count cannot distinguish from missing
geometry. Rule stays as a *triage* net (it found nothing false-positive-free), and
the audit reports it as "needs eyes", never as a defect. Consequence: never gate on
colour count alone; pair it with a tile-spread + known-screen expectation.

## Finding F5 — my "UI pulse is ~1-2 %" band was miscalibrated (correction)
Median adjacent-frame RMSE per run: 0.051 (`pad-drive`), 0.065, 0.084, 0.063, 0.142,
0.254 — i.e. **5-25 %, not 1-2 %** on real screens. The 1-2 % figure came from a
settled UI in one laptop session and got generalised. Consequences: (a) ADR-0015's
"press delta must exceed dwell noise" needs *per-run measured* dwell baselines, not
a global band — which `frames.reversal_report` already does per tile, and why
single-sample phases give a meaningless floor (noted in ADR-0020); (b) the skill file
is corrected rather than the doc being quietly edited.

## Also recorded
`all_black` was initially labelled `unreadable` because `if not st["mean"]` is true
for the legitimate value 0.0 — the bug hid 19 fully black frames (finding F2) behind
an error label. Fixed to distinguish None (unreadable) from 0.0 (black), which is the
kind of falsy-zero trap worth stating.
