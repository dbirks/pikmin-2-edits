# ADR-0015: uinput root cause, Vulkan under Xvfb closed out, and why scene-diff is not an input oracle

**Date:** 2026-10-10
**Status:** accepted

Follows ADR-0013/0014 on the headless host. Owner-approved `sudo` use in this
session: `modprobe uinput` + `/etc/modules-load.d/uinput.conf` and
`pacman -S --needed vulkan-intel` (host has passwordless sudo for `david`; the
AGENTS approval gate was satisfied by the owner's explicit instruction).

## 1. uinput: the rule was never the problem — the module wasn't loaded

After the owner's rule file + reboot, `/dev/uinput` was still `0600 root:root`
and evdev still refused it. Diagnosis: `grep uinput /proc/misc` → absent,
`/sys/module/uinput` → absent, `lsmod` → empty, `modules.builtin` → not builtin.
**Arch does not load `uinput` at all by default**, so the device never appears,
no uevent fires, and `99-uinput.rules` has nothing to act on.

```bash
echo uinput | sudo tee /etc/modules-load.d/uinput.conf
sudo modprobe uinput
sudo udevadm trigger --sysname-match=uinput
# crw-rw---- 1 root input 10, 223 /dev/uinput     ← 223 uinput in /proc/misc
```
Verified: `VirtualPad()` creates and closes cleanly (`scripts/pad_visibility_oracle.py`).
This is the missing step ADR-0013 guessed at ("group + rule") — recorded so the
next host build doesn't lose another session to it.

## 2. Vulkan under Xvfb: closed with a cause, not a guess

With `vulkan-intel` installed (`/usr/share/vulkan/icd.d/intel_icd.json` present),
`-v Vulkan` under Xvfb still produces **no render window at all** within 46 s
(`reports/runs/2026-10-10T054914Z-headless-smoke`). Dolphin's own stderr says why:

```
MESA: info: vulkan: No DRI3 support detected - required for presentation
Note: you can probably enable DRI3 in your Xorg config
```

Xvfb implements no DRI3/GLAMOR, so ANV has no way to present into an X window —
the ICD is irrelevant while the *display server* can't carry buffers. Real
options if frame rate ever demands it: Xorg with `dummy`/`modesetting` +
glamor+DRI3 on the render node, or a Wayland composable (Weston headless) with
`SDL_VIDEODRIVER=wayland`. Both are owner-level installs and neither is on the
G3 critical path. **Decision: stay on `-v OpenGL` (llvmpipe), budget ~100 s.**

## 3. Scene-diff as an input oracle: FAILED, results included

`scripts/headless_input_probe.py` alternates DWELL (no input) and PRESS (one GC
button) in one session, expecting presses to beat the dwell noise floor. Reality
(`reports/runs/2026-10-10T060109Z-input-ab/result.json`, disc id `GPVE01`, zero
strays):

```
dwell RMSE (no input): 0.113 0.037 0.057 0.082 0.0004 0.046 0.096
press RMSE (START,START,A,A): 0.005 0.000 0.239 0.291
```

The dwell floor reaches ~11% because the game animates by itself (attract movie,
fades); two presses measured **zero** change because they landed on an already
-transitioning static frame. The signal is unattributable in both directions, so
this run is a **FAIL for input attribution**, not a pass — and the alternation
design must not be reused over animated scenes. A valid behavioural test needs a
scene that waits for input (dialog cursor position, menu → sub-screen), measured
on a fixed crop, not whole-frame RMSE.

## 4. What replaced it: the fd oracle (`scripts/pad_visibility_oracle.py`)

The host-specific unknown was never "does evdev accept our writes" but "does SDL
inside Dolphin see the device under Xvfb". Answered without pixels: SDL opens
every `/dev/input/event*` it may, so read Dolphin's own fd table.

```
pad_event (from /proc/bus/input/devices, handler for "pikminlab-virtual-pad") = event12
dolphin_event_fds = [/dev/input/event12, event3, event5, event6]
pad_opened_by_dolphin = true      → PASS (exit 0), no strays
```
Caveat kept honest: this proves the pad is *opened and mapped* (device-level),
which combined with the laptop's controller-driven E2E proof (ADR-0011/0012) on
the identical stack is strong — but **game-level response on this host is still
NOT_TESTED**, and the pixel oracle for it is an open task.
Also note `UInput.devnode` reports `/dev/uinput`, not the created `eventNN`;
resolve handlers via `/proc/bus/input/devices`.

## 5. Daemon hardening found by these runs

- `PIKMINLAB_XVFB=1` (wrap only the emulator child) is **removed**: `xvfb-run`
  never tells the parent which display it picked, so the daemon's own
  `xdotool`/`magick` capture calls would have no DISPLAY. Correct usage is
  `xvfb-run -a uv run pikminlab serve …`, or pin `PIKMINLAB_DISPLAY`.
- `serve` now fails fast with `NO_DISPLAY: … Run under xvfb-run` instead of
  silently waiting 60 s for a window that can never appear.
- `idle_watchdog` now notices the emulator dying (`proc.poll()`) and runs
  `stop()`: previously an external `kill -KILL` on Dolphin left the daemon
  holding the one-and-only uinput pad with a zombie child (observed: pid 57219
  `Z` while daemon 57213 kept port 38471).
- Readiness must be polled over HTTP: `uv run` leaves `pikminlab` reparented, so
  its stdout pipe EOFs at once — the first probe version reported "daemon never
  served" while the daemon was healthy and listening.

## Evidence / commands

See `reports/runs/2026-10-10T054914Z-headless-smoke/`,
`…T060109Z-input-ab/` (incl. `serve.log` + 12 scene PNGs), the pad-oracle run
dir, and `/proc/bus/input/devices` excerpts above. Scripts:
`scripts/headless_smoke.py`, `scripts/headless_input_probe.py`,
`scripts/pad_visibility_oracle.py`.

## Consequences

- Gate board: G1 input on this host = **device-level PASS / behavioural
  NOT_TESTED**. Next experiment is the crop-based dialog-cursor test, not more
  whole-frame RMSE.
- Anyone reading ADR-0013's "install vulkan-intel and Vulkan may beat llvmpipe"
  should treat it as retired by §2 for the Xvfb case specifically.
