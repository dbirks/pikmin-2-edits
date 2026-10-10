# ADR-0012: G2 fully closed — single-asset change observed in-game via controller trace

**Date:** 2026-10-09
**Status:** accepted

## What was demonstrated
1. `apply_text_patch` changed exactly one unique occurrence in
   `pikmin2.bmg`: "MEMORY CARD CHECK" -> "LABORATORY CHECK!" (15 byte flips,
   same length, archive structure untouched).
2. `build_iso` repacked the modified tree to
   `builds/pikmin2-modified.iso` (sha256 differs from baseline by design).
3. Cold boot with the uinput gamepad attached (ADR-0011 stack); scripted
   START/A taps advanced warning -> title -> main menu -> memory-card flow.
4. Screenshot evidence `reports/runs/g2-header-observe2/hB.png`: the banner
   now reads "PIKMIN 2 LABORATORY CHECK!" on every screen of that flow
   (scrolling banner clips the '!'); body text unmodified elsewhere —
   attribution rule satisfied (baseline shows MEMORY CARD CHECK in the
   same capture slot: g2-observe-1/s6_after_a.png).

## Gate status effect
- **G2 = PASS**: round-trip boot (ADR-0008/0010) + single-file modification
  observed in-game, patch reversible (working copy only), per-file delta
  known (11 -> 15 bytes, message archive only).
- Bonus: first controller-driven multi-screen navigation trace; input
  assertions now include menu cursor movement (visual) and screen identity
  (screenshot), still no RAM-level scene oracle yet.

## Honest notes
- Earlier same-trace attempts this session failed on unpatched builds
  because SDL binding names/ids were wrong; those runs correctly recorded
  negative controls in ADR-0011.
- Challenge-mode "CHALLENGE MODE!" patch from ADR-0010 remains unobserved
  in-game (gated); superseded as the G2 exemplar by this experiment.
