# ADR-0001: Local Dolphin only; physical GameCube track cut from v0.1

**Date:** 2026-10-09
**Status:** accepted
**Context:** Owner decided the project runs entirely on an Arch Linux laptop
with Dolphin. Console mods, USB/SD/network transfer, disc burning, and capture
hardware would add blockers unrelated to the software mission.
**Decision:** `Pikmin2_AI_Lab_Physical_Hardware_Options.md` (kept in `docs/`
for reference only) is out of scope. No work order, gate, or report may block
on physical hardware. All gates G0-G6 are proven in Dolphin.
**Evidence:** Owner instruction 2026-10-09; master spec §3 "Out of scope".
**Consequences:** Faster critical path; original-console behavior (timing,
memory limits) is approximated by Dolphin accuracy settings and revisited only
if owner later re-enables the hardware track.
