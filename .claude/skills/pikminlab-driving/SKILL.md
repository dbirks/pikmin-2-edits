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

## Headless launch (no monitor, no display server) — ADR-0013/0014/0015
```bash
# ONLY proven combo: OpenGL (llvmpipe) under Xvfb. Budget ~100 s, not 17 s.
PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \
  uv run pikminlab serve <iso> --idle 300          # wrap the DAEMON
PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \
  uv run python scripts/headless_smoke.py <iso>    # gate probe (JSON verdict)
```
- Wrap the **daemon**, never just the child: `xvfb-run` doesn't tell the parent
  which display it chose, so `xdotool`/`magick` in the daemon would be blind.
  `PIKMINLAB_DISPLAY=:99` pins a display you started yourself.
- `-v Vulkan` is a dead end under Xvfb even with `vulkan-intel` installed:
  `MESA: info: vulkan: No DRI3 support detected - required for presentation` →
  no render window ever. Don't re-test; use OpenGL.
- Boot phases (llvmpipe): window ~2 s → dark screen w/ warning text ~30 s →
  full-colour content ~100-160 s. Never assert before the frame is *lit*.
- Fresh Arch hosts need **`modprobe uinput`**, not just permissions: Arch never
  loads it, so `/dev/uinput` may exist as a stale `0600 root:root` node, no
  uevent ever fires, and a `99-uinput.rules` file does nothing.
  `echo uinput | sudo tee /etc/modules-load.d/uinput.conf && sudo modprobe uinput`
  → then the rule applies: `crw-rw---- root input`. Check with
  `grep uinput /proc/misc` (absent = module not loaded).
- `dolphin-emu` must *exec*: `libavformat.so.63 not found` / `GLIBC_2.44 not
  found` = partial upgrade → owner runs `sudo pacman -Syu`. `doctor` exec-probes.
- Readiness for the daemon is polled over HTTP (`GET /state`), never by reading
  the child's stdout: `uv run` reparents pikminlab and the pipe EOFs instantly.
- If Dolphin is killed from outside, the old daemon kept the uinput pad with a
  zombie child; `idle_watchdog` now detects `proc.poll()` and runs `stop()`.

## Numeric scene oracle (for sessions whose model cannot see images)
If the reviewer model rejects image input (e.g. `qwen3-8-flash-next` here), the
LOOK step is impossible; assert on statistics and keep the PNGs for a human:
```bash
magick identify -format "mean=%[fx:mean] colors=%k max=%[fx:maxima]\n" shot.png
# black/idle framebuffer: mean=0 colors=1  -> NOT a frame
# lit text screen:        mean>0.05 colors=256  (bright-content bbox via -threshold 60% -format "%@")
# full scene:             mean~0.28 colors>100000
magick compare -metric RMSE -resize 320x240! a.png b.png null:   # 1-2% = UI pulse band
```
Freshness = different sha256 **and** both frames `lit`: a hash-only check passed
bogus "fresh" captures of a still-black framebuffer.

## Proving input landed (ADR-0015/0017)
- **Categorical beats differential.** Compare a frame before any input with one
  after the route: distinct-colour count collapsing (≈256 = text screen) or
  exploding (≈100k = full scene) is proof; whole-frame RMSE between two live
  frames is not (dwell reached 0.127, larger than a press delta of 0.122).
- Use `pikminlab.frames` (`tile_means/stats/lit/rmse/reversal_report`) — not
  per-script copies. `tile_means` must accept `gray(` as well as `srgb(` and it
  raises on a short parse; an empty tile list once silently turned a good run
  into an unexplained FAIL.
- Screenshots land in the *daemon's* `reports/runs/<ts>-serve/` dir, not the
  probe's dir; `result.json` paths are the authority.
- **Device-level (fast, reliable):** `scripts/pad_visibility_oracle.py` reads
  Dolphin's own `/proc/<pid>/fd` — SDL opens every `/dev/input/event*`, so if our
  pad's `eventNN` (resolved from `/proc/bus/input/devices` by device name;
  `UInput.devnode` lies, it reports `/dev/uinput`) is in that list, the pad is
  live. Verified here: `pad_opened_by_dolphin=true`.
- **Whole-frame RMSE is NOT an input oracle.** Measured on this host: dwell
  (no input) deltas up to 0.113 because the attract movie animates itself, while
  two presses scored 0.000 and 0.005 because they landed mid-transition. Design
  behavioural assertions only on screens that *wait* for input, on a fixed crop
  (dialog cursor highlight, menu → subscreen), never whole-frame diffs over video.

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
  **Headless hosts are NOT by default**: `/dev/uinput` is `0600 root:root` and
  systemd ships no group rule for it — needs an owner udev rule + `input`
  membership (ADR-0013). `pikminlab doctor` reports `UINPUT_NOT_WRITABLE`.
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
