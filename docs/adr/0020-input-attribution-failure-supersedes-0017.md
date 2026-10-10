# ADR-0020: Game-level input on the headless host is UNATTRIBUTABLE — ADR-0017's PASS was a false positive

**Date:** 2026-10-10
**Status:** superseded-by: none. **Supersedes:** ADR-0017 (its conclusion only; its
tooling findings stand). ADR-0015's method was right; ADR-0017 broke it.

## What ADR-0017 claimed, and why it was wrong
ADR-0017 read `boot.png` (23 distinct colours, before any input) → `ready.png`
(97,901 colours after START, START, A×10) as a categorical, therefore
input-caused, scene transition. That is exactly the mistake ADR-0015 warned about:
it compared *time-adjacent* states and credited the button. **A control run with
zero input at all shows the same jump** — Pikmin 2's health warning is a timed
splash that auto-advances into the title and then the attract demo (recorded
Forest-of-Hope gameplay):

| capture (no input between them) | mean | distinct colours |
| --- | --- | --- |
| `p1_t0_no_input` (t=60 s) | 0.0023 | **38** |
| `p1_t1_still_no_input` (t=72 s, **nothing pressed**) | 0.3104 | **86,819** |

Whole-frame RMSE across that 12 s of no input: **0.3477**, with all 12 tiles moved.
So the earlier 23 → 97,901 observation is fully explained by the game self-progressing.

## What has actually been proven on this host
| claim | status | evidence |
| --- | --- | --- |
| pad device is created and opened by Dolphin | PASS | `/proc/<pid>/fd` contains our `eventNN` (ADR-0015) |
| SDL3 accepts our `SDL_GAMECONTROLLERCONFIG` mapping | PASS | ctypes probe: `SDL_IsGamepad=True`, `SDL_OpenGamepad` OK, name `pikminlab-virtual-pad` (SDL 3.4.18, Dolphin links `libSDL3.so.0`) |
| any button reaches the *game* | **UNATTRIBUTABLE** | press deltas are smaller than no-input deltas on every screen reached |
| stick moves the player | **NOT PROVEN** | stick left/right produced RMSE 0.103 with **0** tiles moved, while a 3 s no-input dwell produced RMSE 0.133 with 2 tiles moved (`menu_dwell_3s`) — i.e. input changed *less* than doing nothing |
| a new game was ever started | **NO** | memory-card oracle: `01-GPVE-Pikmin2_SaveData.gci` unchanged (sha `f25273f1…`) across 4 sessions; with the card emptied, five cursor variants (`A` alone, stick up/down/left/right → `A`) produced **no card write in 60 s each** |

The card oracle is the decisive one: creating a game file *requires* input and
*must* write the card. It never wrote. Every screen we reached was either a timed
splash or attract footage, so pixels could never settle the question either way —
which is why ADR-0015's "use a screen that waits for input" rule exists.

## Consequences
1. **t5 (input-only cave E2E) is BLOCKED**, not failed-by-design: the authored cave
   compiles, validates, repacks and boots (t2–t4 all pass), but the input lane
   cannot yet move the player. No E2E claim of any kind is made.
2. The G1 board reads: device-level PASS, mapping-level PASS, **game-level
   UNATTRIBUTABLE**, and any earlier G1 "game-level" claim is withdrawn.
3. Frames already captured are still valid evidence for the anomaly audit (t6),
   which needs no input — that lane continues.
4. `pikminlab build` now refuses to repack a tree that doesn't carry the applied
   design (an earlier ISO in this session was silently pristine).

## Named failing condition (the one sentence to reproduce)
Under Xvfb on `delightful-goose`, with Dolphin 2609, `-v OpenGL`, our uinput pad
visible to Dolphin and mapped by SDL3: **input given via `/dev/uinput` produces no
change distinguishable from no input, and the new-game memory-card write that would
require input never occurs.** Evidence: `reports/runs/2026-10-10T073030Z-input-attribution/`
(control run), `reports/runs/2026-10-10T07{05,14}53Z-e2e-cave/`,
`reports/runs/2026-10-10T070242Z-e2e-cave/` (E2E attempts 1-3).

## Most likely root cause, and the cheap test
`GCPadNew.ini` hardcodes `Device = SDL/0/pikminlab-virtual-pad`. The `SDL/0` index
is an *enumeration position*, and this host has more input devices than the laptop
did; if our pad is not SDL index 0, Dolphin binds Port 1 to something else and
silently ignores everything — while the fd and mapping probes still pass, which is
precisely the pattern we observe. Fix candidates, in cost order:
1. **Owner check, seconds:** Settings → Controllers → Port 1 device name in the
   GUI (or look at one supplied PNG and say which screen it is — the route's
   interpretation depends on it).
2. Bind Port 1 by device **name** (`SDL/…/pikminlab-virtual-pad`) or iterate
   `SDL/0…SDL/3` until the game responds, using the card-write oracle as the
   pass/fail signal.
3. Replace the SDL channel with a **keyboard-bound** GC pad in `GCPadNew.ini` and
   drive it with `xdotool key --window <id>` — synthetic events go to the window
   regardless of focus, removing both the SDL-index and focus hypotheses at once.
   (An `xdotool windowactivate` attempt already failed with rc=1 under Xvfb;
   `windowfocus` returned 0, so focus is a plausible secondary contributor.)

## Also corrected
`dwell_noise_max = 0.0` in `reversal_report` when given single-sample phases: with
no dwell spread the floor falls back to 0.02, which is fine but must not be read as
"noise measured zero". The report now needs ≥2 samples per phase to claim a floor.
