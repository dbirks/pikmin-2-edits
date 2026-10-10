# ADR-0011: Candidate B input fully proven — exact Dolphin SDL3 gamepad binding recipe

**Date:** 2026-10-09
**Status:** accepted (supersedes the input portion of ADR-0006/0007 caveats)

## Correction (honesty rule)
The "title -> warning -> continue" progression seen earlier (input_probe,
G1 notes) was the game's automatic boot-attract timing, NOT our XSendEvent
keypresses. xdotool/`import -window` remain valid for *raise+capture*, but
were never an input path. The real input proof is this ADR.

## What was actually wrong (two stacked mistakes)
1. Device id: Dolphin `Core::Device::GetId()` defaults to 0, so the ini
   device string is `SDL/0/<name>` (we tried `SDL0/0/<name>` and `SDL/1/<name>`).
2. Input names: Dolphin 2609's SDL3 *Gamepad* backend uses canonical names
   from `SDLGamepad.h` (`Button S/E/W/N`, `Start`, `Back`, `Shoulder L/R`,
   `Pad N/S/W/E`, axes `Left X/Y±`, `Right X/Y±`, `Trigger L/R`), not the
   `Button A`/`Axis Y-` style guessed from screenshots.

## Why the earlier backend appeared deaf
Dolphin 2609 drives controllers through SDL3's **gamepad** API, which only
exposes devices matched by SDL's gamepad database. A raw uinput pad is not
in the DB, so it was invisible until we supplied our own mapping through
`SDL_GAMECONTROLLERCONFIG` in the environment of the Dolphin process.

## The exact working recipe (verified)
- uinput device: name `pikminlab-virtual-pad`, EV_KEY BTN_SOUTH..BTN_DPAD_*
  in ascending evdev order, EV_ABS ABS_X/Y/RX/RY (+ABS_Z/RZ triggers).
- SDL3 mapping string (also in scripts/gpad_drive_test.py MAP):
  `pikminlab-virtual-pad,platform:Linux,xinput,a:b0,b:b1,x:b2,y:b3,back:b6,
  start:b7,guide:b8,leftshoulder:b4,rightshoulder:b5,dpup:b9,dpdown:b10,
  dpleft:b11,dpright:b12,leftx:a0,lefty:a1,rightx:a2,righty:a3,
  lefttrigger:a4,righttrigger:a5`
- Launch Dolphin with SDL_GAMECONTROLLERCONFIG=<that> in env; pad must
  exist before launch.
- GCPadNew.ini `[GCPad1] Device = SDL/0/pikminlab-virtual-pad` with the
  canonical names above.

## Evidence
`reports/runs/2026-10-09T203550Z-gpad-drive/`: warning screen
(`t0_warning`) -> after Start taps the game reached **PRESS START**
(`start3` visually confirmed; `start2` hash matches the title card from an
earlier capture). Zero strays after SIGKILL teardown. Negative controls:
with wrong device id/names, four hash "changes" were only the pulsing
"Press any Button" text — recorded here so nobody re-reads them as input.

## Consequences
- G1 input leg now genuinely proven (warning-dismiss is a weak assertion
  on its own; next trace should prove stick locomotion via RAM pose reads).
- `pikminlab` must own this whole stack (pad creation + env + ini) in the
  session harness before any P3 gameplay work.
