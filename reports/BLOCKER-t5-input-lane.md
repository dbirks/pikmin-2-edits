# BLOCKER — t5 input-only cave E2E (status: BLOCKED, not FAILED-by-design)

**Build under test:** `builds/lab-cave.iso` sha256 `6a9da6425949d162c564bf816f92c8197253a8b25e04b8dfa50b8c3fc0f07174` (pinned at `verified_level: boot`)
**Host:** `delightful-goose`, Arch, Dolphin `1:2609-1`, `-v OpenGL` under Xvfb, uinput pad
**Attempts used:** 3 E2E cold launches + 1 attribution control run (limit: 3 + 2 restarts)
**Evidence:** `reports/runs/2026-10-10T070242Z-e2e-cave/`, `T070554Z-e2e-cave/`, `T071453Z-e2e-cave/`, `T073030Z-input-attribution/`, `reports/frame-audit.json`

## Exact failing condition (one sentence)
Input written to `/dev/uinput` produces **no change distinguishable from no input**, and
the one state transition that *requires* input — Pikmin 2 writing a new game file to the
memory card — never occurred in four sessions.

## What rules out the easy explanations
| checked | result |
| --- | --- |
| pad created + opened by Dolphin | PASS (`/proc/<pid>/fd` shows our `eventNN`, ADR-0015) |
| SDL3 accepts our mapping | PASS (ctypes: `SDL_IsGamepad=True`, `SDL_OpenGamepad` OK, `sdl3 3.4.18`, Dolphin links `libSDL3.so.0`) |
| pad is SDL index 0 (the `Device = SDL/0/…` assumption) | **PASS** — probe saw exactly one joystick, ours, index 0 |
| game waits for input on the screens we reached | **NO** — with nothing pressed, 12 s took the frame from 38 colours to 86,819 (RMSE 0.3477, all 12 tiles moved): the health warning is a timed splash and the title screen plays an **attract demo of recorded Forest gameplay** |
| stick moved the player | 0 tiles moved on left/right; a 3 s no-input dwell moved 2 (RMSE 0.133 vs 0.103) |
| world-scale float triple moved under input | none — only 0–3 magnitude animation structs moved |
| `.gci` written after card emptied + 5 cursor variants (A alone, stick up/down/left/right then A) | **no write within 60 s each**; fixture sha `f25273f1…` restored afterwards |

The attract demo also explains the earlier false positive: the Day-1 spawn float triple
`[381.724, -70.880, 2634.461]` (exactly `stages.txt`) sits in RAM at `0x8092dca4` during
attract playback, so "spawn struct present" is not evidence of a started game. ADR-0017's
PASS was withdrawn for this reason (ADR-0020).

## Unblocked-by-design parts (all verified this session)
Cave authored + compiled deterministically (62 validator checks, 0 problems), repacked with
byte-exact per-file delta, boots headless (`GPVE01` read, lit + fresh captures, clean
teardown, zero strays), anomaly audit over 249 frames done, build pinned with honest level.

## Minimal human input genuinely needed (pick any one)
1. **Look at two PNGs and say what you see** (~10 s, resolves the ambiguity):
   - `reports/runs/2026-10-10T073030Z-input-attribution/…/p1_t3_after_start2.png`
   - `…/p2_menu_a.png`
   If both are attract/footage rather than a menu, our blind route never reaches a
   screen that waits for input, and the route (not the pad) is the thing to fix.
2. **Run the build yourself and tell me if the pad works:**
   `uv run pikminlab play --last-passing --dry-run` prints the exact command
   (`dolphin-emu -e …/builds/lab-cave.iso`, your own profile; hash verified first).
   If *you* can walk into the f_03 cave and see a haniwa ring + a fountain on floor 1 and
   a duck-shaped "Makigai", the build is playable and only the agent's input channel is broken.
3. **Approve one of** (a) `tesseract` (pacman) so dialogs/`Yes/No` cursors become readable
   to the agent, or (b) letting me bind the GC pad to the **keyboard** in `GCPadNew.ini`
   and drive it with `xdotool key --window <id>`, which removes SDL enumeration *and*
   window-focus as explanations in one test.

## Added this turn (ADR-0024) — the picture sharpened; no new capability
- Dolphin's SDL **element names in our template are correct** (checked against
  `SDLGamepad.h`), and `SDL/0/pikminlab-virtual-pad` matches SDL3's own report exactly
  (name `pikminlab-virtual-pad`, path `/dev/input/event12`, `is_gamepad=True`); Dolphin
  holds two fds on that node.
- **One genuine bug found: main-stick and C-stick up/down were inverted** (`Left Y-` is
  down, because Dolphin inverts vertical axes to respect XInput). Fixed in `GC_PAD_INI`.
  Every earlier cursor nudge meant the opposite direction — a plausible cause of the failed
  blind file-create navigation, though not of "no card write at all", since all four
  directions were tried.
- Two probes were **invalid oracles** and now self-report that instead of a verdict: F1 →
  savestate (no `State/` dir existed, no hotkey bound) and the SIGTERM config flush
  (Dolphin ignores SIGTERM, so nothing was rewritten). Batch mode is only *weakly*
  exonerated, because that A/B used an RMSE oracle that cannot confirm input on a
  live-animated title screen.
- Consequence: the next input test must use the **card-write oracle with corrected stick
  signs**, and a human glance (or OCR) is still the cheapest way to learn which screen we
  are actually on.

## Next 3 agent actions once any answer arrives
1. Re-run `scripts/input_attribution.py` with the chosen channel; require the no-input
   control pair to stay static while the press pair changes (ADR-0020's rule).
2. Re-run `scripts/e2e_cave_run.py` × 3 cold launches; S1b now gates on the card write,
   so "new game started" is proven before any walking is claimed.
3. Then t5 can be verified honestly and the pin can be amended to `verified_level: play`.
