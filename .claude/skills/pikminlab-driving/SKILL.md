---
name: pikminlab-driving
description: Use whenever you need to drive Pikmin 2 live in Dolphin for exploration or E2E testing — start the session daemon, screenshot-and-look loops, press GC buttons, read emulated RAM, and guarantee teardown. Captures the hard-won recipes (SDL3 gamepad config, screen flow timings) so no session is wasted re-deriving them.
---

# Driving Pikmin 2 agentically

## Golden rules
- ONE owned session at a time: the `serve` daemon holds Dolphin + the
  uinput pad; never hand-launch `dolphin-emu`.
- Screenshot -> LOOK at the image (view tool) -> then act. Never blind-fire
  key sequences; menu state is only trustworthy from pixels.
- Every session tears down: `drive stop`, then `pgrep -x dolphin-emu`
  must be empty. Host quirk: use `/bin/kill -KILL` (the agent shell's
  `kill` builtin silently fails).

## Session lifecycle
```bash
nohup uv run pikminlab serve builds/pikmin2-modified.iso --idle 300 >/tmp/serve.out 2>&1 &
# wait for {"serving": ...} line (~40-70 s to window+title; pad/ini/env auto-provisioned)
uv run pikminlab drive state                 # {alive, window, disc_id}
uv run pikminlab drive shot --name s1        # writes PNG under the run dir
uv run pikminlab drive input --button A --hold 0.8     # hold >=0.5 s on dialogs!
uv run pikminlab drive stick --x 0 --y -30000          # y- is UP; neutral = 0 0
uv run pikminlab drive read --addr 0x80000000 --size 6 # disc ID hex
uv run pikminlab drive stop
```
Viewing screenshots: downscale first, `ffmpeg -i shot.png -vf scale=900:-1 -q:v 5 shot.jpg`
(the viewer rejects large PNGs).

## Verified input stack (do not re-derive; ADR-0011)
- uinput pad `pikminlab-virtual-pad` (owner is in `input` group; no sudo).
- Dolphin 2609 needs **SDL3 gamepad** visibility: `SDL_GAMECONTROLLERCONFIG`
  mapping is exported by the daemon (see `pikminlab.serve`).
- GCPadNew.ini device string MUST be `SDL/0/pikminlab-virtual-pad` with
  canonical names (`Button S/E/W/N`, `Start`, `Left X/Y±`...). Wrong device
  id or names fail SILENTLY — screens just ignore everything.

## Known screen flow (fast path)
boot ~17 s -> HEALTH warning -> START -> title card -> START -> main menu
(BEGIN highlighted) -> A -> memory-card flow. Dialogs: use hold 0.5-0.8 s.
New-game route without a save file: "Create game file?" -> the emulator has
no GC memory card, answer leads to "cannot be saved. continue without
saving?" -> Yes -> Day 1. Expect intermediate MC-check banner screens
between transitions; they are transitions, not stuck states — recapture
after ~5 s before reacting.

## RESOLVED 2026-10-09: memory card + Day-1 route (verified end-to-end)
1. Modern Dolphin auto-cards are DIRECTORIES (`GC/USA/Card A/`) that need an
   `MC_SYSTEM_AREA` header block — an empty dir reads as 0 blocks and all
   game writes silently fail. Generate: `uv run python
   scripts/make_gc_card.py runtime/dolphin-agent/GC/USA/Card A`
   (restart the daemon afterwards; card state is loaded at boot).
2. Proven new-game path: warning -> START -> title -> START -> main menu ->
   A (BEGIN) -> "Create game file?" -> verify cursor is on **Yes** (yellow;
   it does NOT default where you expect — capture first!) -> A ->
   "A file has been created." -> "Choose a Ship's Log" (NEW orbs,
   "This is a new Ship's Log.") -> A -> story cutscenes (~2-3 min; tap A
   every ~7-12 s, capture to follow) -> ship landing -> diagnostics ->
   tutorial gameplay with full control.
3. Locomotion VERIFIED (visual oracle): stick up 3 s -> camera orbit + world
   translation (RMSE ~20%, vs ~1-2% pulsing-UI noise). RAM-symbol assertions
   still pending a decomp build — pixel-oracle only until then.
4. Save fixture lives at `runtime/dolphin-agent/GC/USA/Card A/*.gci`
   (gitignored, persists across sessions).

## BLOCKERS for reaching Day-1 gameplay (open, as of 2026-10-09)
1. ~~No GC memory card~~ RESOLVED — see above.
2. **No position symbols**: `pikmin2UP.MAP` extracts as 0 bytes. Locomotion
   RAM assertions need `projectPiki/pikmin2` (gpve01) addresses or
   decomp-built telemetry. Do not claim movement from pixel-diff alone —
   the health-warning/attract screens pulse and produce false deltas.

## Do NOT
- Blind-cycle Yes/No memory-card dialogs hoping to land in-game: capture,
  read the actual text, then one input. If a dialog is up 3x in a row, stop
  and fix the underlying state (save file, timing) rather than re-pressing.
- Run a session with no plan for the next assertion; that wastes the owner's
  screen and their patience.

## Evidence discipline
- Screenshots live under `reports/runs/...` (gitignored binaries; commit
  conclusions as ADRs, small JPEGs only with intent).
- A screen "changed" hash proves nothing alone (attract animations/pulses
  differ per frame); assert on what the IMAGE shows after looking at it.
- Negative results (wrong mapping, stuck dialog) belong in ADRs too.

## Open questions (update this skill when answered)
- RAM position/symbol addresses (needs projectPiki decomp build).
- Button(s) that skip story cutscenes wholesale vs per-line A.
