# ADR-0024: Input path narrowed against Dolphin's source; two of my own oracles were invalid

**Date:** 2026-10-10 · **Status:** accepted · Refines ADR-0020 (supersedes nothing)
**Evidence:** `reports/runs/2026-10-10T080150Z-pad-consume/`, `T080231Z-attract-stop/`,
`T080552Z-attract-stop-nobatch/`, `T081020Z-hotkey-channel/`, `T081205Z-port-flush/`

## What was measured
1. **Pad consumption probe** (`scripts/pad_consumption_probe.py`): Dolphin holds **two**
   fds on our created node (`/dev/input/event12`), so the device is opened. This kernel's
   evdev `fdinfo` exposes only `pos/flags/mnt_id/ino` — no `idx` counter — so *consumed vs
   merely open* stayed unmeasured. My first attempt read `pad.ui.devnode` (= `/dev/uinput`,
   the writer) instead of the created node, and created the pad *after* launch; both fixed.
2. **SDL3 enumeration probe**: `idx=0 id=1 is_gamepad=True`,
   `joystick_name == gamepad_name == 'pikminlab-virtual-pad'`, `path ==
   '/dev/input/event12'`, mapping auto-applied. Our config string
   `SDL/0/pikminlab-virtual-pad` is therefore exactly right.
   Traps recorded: SDL3 renamed the API to `SDL_Get*ForID` / `SDL_GetJoysticks(&count)`,
   `SDL_INIT_GAMEPAD` is `0x2000` (SDL2's `0x200` fails init), **`SDL_Init` returns bool
   TRUE on success** — the SDL2 idiom `if (SDL_Init(...))` inverts it and produced a fake
   `SDL_Init failed: ?` — and `SDL_GetError` needs `restype = c_char_p`.
3. **Element names verified against source, not memory**
   (`InputCommon/ControllerInterface/SDL/SDLGamepad.h|.cpp`): `s_sdl_button_names` =
   `Button S/E/W/N, Back, Guide, Start, Thumb L/R, Shoulder L/R, Pad N/S/W/E, …`;
   `s_sdl_axis_names` = `Left X, Left Y, Right X, Right Y, Trigger L, Trigger R` with `+`/`-`
   suffixes, and `Axis::GetName()` inverts **odd (vertical)** axes —
   `// Respect XInput: the vertical axes are inverted on SDL`.
   **Finding: our template had `Main Stick/Up = `Left Y-``, which is *down* (same for the
   C-stick). Up/down were swapped in every session ever run on this host.** Fixed to
   `Left Y+` / `Right Y+`. Buttons, shoulders, triggers and D-pad were already correct.
4. **Batch-mode A/B**: the press-vs-dwell result was the same with and without `-b`, so
   "`-b` disables input" is unsupported — with the caveat in §Caveats below.

## Two oracles I designed and now report as INVALID (AGENTS.md records failures)
- **F1 savestate → look for a state file** (`hotkey_channel_probe.py`): all candidate
  dirs were absent (`State`, `GameCube/States`, `States` = `false`) and this profile binds
  no savestate hotkey, so silence carries no information. The script nevertheless printed
  `NO_HOST_INPUT_CONSUMED` — an over-claim of exactly the ADR-0017 kind. It now returns
  `ORACLE_INVALID` unless a state dir exists *and* a hotkey is bound.
- **Graceful-exit config flush** (`port_binding_flush.py`): Dolphin **ignored SIGTERM** for
  the full 25 s (then SIGKILL, teardown verified), so `GCPadNew.ini` was never rewritten and
  "Device line unchanged" proved nothing. The verdict now requires a confirmed clean exit.

## Caveat that limits conclusion 4
Pikmin 2's title screen is a **live animated** scene, so "RMSE collapsed ⇒ input registered"
is unsafe in both directions: the metric can falsify "this screen is static" but cannot
confirm input actuation. The only oracle trusted for "input reached this game" remains a
**memory-card write**, and that test needs blind cursor navigation — which the stick-sign
bug above actively sabotaged.

## Decision
- Ship the corrected template; any future input claim must use the card-write oracle with
  the corrected signs, then the 3-cold-launch E2E.
- The stick inversion explains a *navigation* failure but not "no write from any of five
  variants", so the card evidence remains negative and t5 stays blocked.
- Stop spending emulator sessions on inference-based oracles. What is missing is
  perception of the current screen — one human glance, or OCR — which is the ask in
  `reports/BLOCKER-t5-input-lane.md`.
