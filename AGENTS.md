# Pikmin 2 AI Lab — AGENTS.md

**Revision:** 0.4 — 2026-10-09 (local repo copy; pristine pack copies live in `docs/`)  
**Primary authority:** `docs/Pikmin2_AI_Lab_Master_Spec.md`  
**Scope:** **Arch Linux + local Dolphin only.** This file is a set of work orders, not evidence that a toolchain has been installed or a modified game has passed testing.

## Mission

Given the human's **existing local Pikmin 2 GameCube image path**, build an autonomous-but-bounded development loop. The agent must be able to edit a cave and at least one treasure, package it, boot it in Dolphin, manipulate the game through controller input, inspect state, capture fresh screenshots, detect/repair errors, and launch the last **verified passing** build so a human can play it.

**No physical GameCube devices, mods, USB/SD/network ISO transfer, burnable discs, ordering, or model-identification requests.** Those ideas are explicitly tracked only in `Pikmin2_AI_Lab_Physical_Hardware_Options.md` and must not block software delivery.

## Confirmed facts — don't ask again

- Host distribution: **Arch Linux**; laptop with graphical session is the initial emulator runner. Headless Linux server is optional for build/static work only.
- Image located and fingerprinted 2026-10-09: `/home/david/dev/pikmin-2-edits/pikmin2.iso`, SHA-256 `5388b54a9c2d156c94bcfa80acd53b513288dc17e88c97a1edfb57ad25db661a`, 995,557,376 bytes. Gitignored; treat as immutable.
- Header disc ID is **GPVE01 (US retail, rev byte 0x00)** — see ADR-0002. Still confirm with `dolphin-tool header/verify` once installed, and keep all tooling region-parameterized.
- P0 audit done (`reports/environment.json`): Wayland session (`wayland-0`, XWayland `:0`); `dolphin-emu`/`dolphin-tool`/`blender` **not installed**; python3/git/ninja/cmake/java/ffmpeg present. Agent sandbox blocks `pacman`/`sudo` — system installs are owner-run (see `scripts/bootstrap.sh`).
- Agent autonomy: **trusted setup**. User-scoped project work is autonomous; `sudo`, `pacman` installation/upgrades, ptrace/uinput/kernel permissions, deletion outside generated artifacts, network exposure, publishing, access to personal save files, and sharing copyrighted bytes require approval.
- Primary UX: **CLI + reports + Dolphin GUI**. No web dashboard required.
- User's end-state goal: new caves, cheeky treasures, eventually replacement overworld and a fifth overworld, with agent-driven observations and regression tests.

## ADRs — mandatory decision log

`docs/adr/` is the project's architecture decision record. Every agent run:

1. Reads `docs/adr/README.md` (index + template) **before** making technical choices.
2. Writes a numbered ADR (`NNNN-short-slug.md`) for every technical decision, tool pin, driver/fork selection, benchmark outcome, workaround, or declared incompatibility — including failed experiments (honesty over erasure).
3. Never edits a superseded ADR's decision text; writes a new ADR that supersedes it.
4. Updates the index table in the README as part of the same commit.

## Git discipline — commit frequently

- Commit as soon as a unit of work is verified: each gate, ADR, working tool, benchmark result, doc fix. Small, coherent commits beat big ones.
- Every commit message states *why*, understandable without the diff.
- **Never stage:** ISOs, extracted proprietary assets, saves/profiles, run evidence binaries (enforced by `.gitignore`; double-check `git status` before each commit).
- Tag verified passing states (e.g. `g0-baseline`) so `pikminlab play --last-passing` can trace provenance.
- Do not push to any remote unless the owner asks.

## First assignment — execute, don't merely restate

1. Read this and the master spec. Inventory host non-destructively: `uname -a`, `/etc/os-release`, `pacman -Q`, `command -v dolphin-emu`, `command -v dolphin-tool`, GPU/display/session, memory and free storage. Save `reports/environment.json`.
2. Obtain local ISO path (only genuinely missing owner input). Inspect image without mutating it; collect `sha256sum`, game ID, disc revision and Dolphin validation; write immutable `workspace/game-manifest.json`. Save originals outside Git.
3. Create project structure, safe `.gitignore`, dependency pins, `docs/adr/`, `reports/`, and user-owned Dolphin test profiles. Implement `pikminlab doctor`, `pikminlab ingest` before a game mod.
4. If Dolphin is missing, formulate minimal `pacman` install proposal and **get approval**. Prefer Arch official `dolphin-emu` and separate `dolphin-emu-tool`; Python deps in venv. Never do partial Arch repo sync (`pacman -Sy` alone).
5. Boot **unmodified** image in graphical Dolphin with `--user` isolated path and `--exec` image. Capture baseline title/interactive scene; preserve a fixed version record. Never write the owner's main Dolphin saves.
6. Implement common `EmulatorDriver` and test two backends against **the same image and reproducible input script**: (A) Felk Dolphin + `mcp-dolphin` **>=0.3.0**, and (B) mainline Dolphin + native virtual input/process memory reader and screenshot capture. The bridge now claims screenshot support (see v0.3.0 changelog), **not** pause/resume; Linux compatibility of Felk and screenshot freshness must be proven. When A fails, use B; record concrete evidence and ADR, don't repeatedly ping human for preference.
7. Smoke benchmark: press/release GC Start, advance frames, read disc ID at emulated `0x80000000` and a game-state signal, and capture two demonstrably **fresh** PNGs. Maintain per-instance PID, input trace and deadline. Run 20 controlled iterations for the selected driver; log failures, not just successes.
8. Extract the game's filesystem and generate a no-change round-trip image. Prove it boots. Inventory game files, SZS archive boundaries and individual hashes. Confirm archive conversion on a real file; never conflate `arc.szs` and `texts.szs` under cave-unit `mapunits/arc/`.
9. Change exactly **one small cave parameter** (or safe existing-slot text resource if cave file parsing blocks), rebuild, boot, and observe the difference. Separate asset-compiler success from gameplay success.
10. Build first playable vertical slice: reuse a supported cave/treasure slot; put a cave entrance close to an existing area spawn, produce one floor and a named/reskinned treasure. Preserve cave BGM list cardinality, cave IDs and resource references. Use CaveGen seeded preflight and in-game cold-boot smoke tests.
11. Add actual **input-driven** cave entry and treasure collection test, with game-state telemetry or validated symbols. Debug warps/forced treasure flags may establish a *component* test but **must not count** as E2E success. If state is unobservable, implement versioned debug DOL telemetry using decomp C++; test that instrumented mode does not invalidate release behavior.
12. Add deliberate-fault test: insert a safe broken reference in a disposable generated test variant; identify the error, roll back/repair, then re-run same seed. Capture structured failure evidence.
13. Implement `pikminlab play --last-passing`, checking the immutable passed-build manifest/hash before opening **human** Dolphin profile. Expose last report and screenshots via `pikminlab inspect`.

## Important upstream caveats validated in October 2026

- `mcp-dolphin` **0.3.0** changelog adds `dolphin_screenshot`, relying on Felk `event.on_framedrawn`; it may report unavailable in older forks. The project's README and historical changelog sections still contain out-of-date statements. Confirm actual installed version and tools list. Pause/resume MCP deadlocks remain unresolved; restarting a process is often safer than hot-reloading Felk scripts.
- Mainline Dolphin has useful CLI flags but **no upstream scripting RPC**; native input/memory access is an integration task, not a single shell option.
- `--batch` doesn't guarantee graphics-free Dolphin. Run emulation on the laptop's usable display/GPU; put only static/build jobs on a headless server initially.
- `pyisotools` repacks disc filesystems; it is not an SZS/RARC/BMD/BMG converter. Test those tools independently and pin working Linux versions.
- `projectPiki/pikmin2` nonmatching C++ build needs extracted system assets for **actual** game region. US example `python configure.py --non-matching && ninja` is **not** universally valid for PAL/JP without `--version` and corresponding `orig/` data.
- CaveGen simulations are preflight only; passing them does not demonstrate Pikmin can carry a treasure or leave a cave.
- Further references and proposed CLI/error/state schemas live in §§ 15–16 of the master spec.

## Standard output interface

Implement and document (do not pretend they already exist):

```text
pikminlab doctor                         # read-only env check
pikminlab ingest /abs/path/owned.iso     # protect and verify local input
pikminlab build --lane data              # deterministic game-data build
pikminlab test --suite smoke             # boot/scene and asset checks
pikminlab test --suite cave-seeds --seeds 100
pikminlab test --suite e2e --case intro-treasure
pikminlab inspect --latest               # static report path + screenshots
pikminlab play --last-passing            # launch human GUI profile
pikminlab export --format iso --last-passing
```

Agent internal `EmulatorDriver` capabilities: `launch`, `input`/neutral release, `frame_advance` or documented real-time wait, `read_memory`, `screenshot`, `reset`, `health`, `stop`; support `savestate`, `write_memory`, and `overlay` conditionally. Missing capabilities return typed `UNAVAILABLE`, not success.

## Pass gates / strict honesty

| Gate | What *must* be demonstrated |
|---|---|
| G0 | Original image verified and boots in isolated Dolphin on 10 fresh starts |
| G1 | Driver controls game and captures fresh screenshot/verified state repeatedly (target 20 test runs) |
| G2 | Round-trip image boots; known single-file modification is observed in-game |
| G3 | Input-only entrance → cave → treasure → credited collection → exit across 3 cold launches |
| G4 | Safe injected failure detected, diagnosed, repaired and re-tested |
| G5 | Later: playable replacement overworld with collisions/carry paths and save/reload |
| G6 | Much later: independent fifth selectable world without deleting four originals |

A test is `PASS` only if the asserted behavior is observed with matching build, scene and game-state evidence. Otherwise emit `FAIL`, `BLOCKED`, `NOT_TESTED`, `NEEDS_HUMAN` or `INCOMPATIBLE`. No claims of having built, tested, or played game content before local runtime evidence exists.

## Session budget and failure discipline

- **No infinite agent loops.** Default: at most 3 repair attempts per failed gate; 2 transient emulator restarts with isolated fresh profile; then concise blocker report, reproducible commands, and best fallback.
- Give every action a deadline, expected frame/scene, neutral controller release, and log.
- Do not retry input in-place if it may duplicate a stateful action; restart from fixture.
- Preserve a known-good baseline and last passing build, do not overwrite them on a failing run.
- Perform paired A/B tests under identical game version, seed, fixture and emulator build, when possible.
- Keep **static**, **debug-assisted** and **real-controller E2E** test lanes separate.

## End-of-session report template

```text
Status: PASS | FAIL | BLOCKED | NOT_TESTED | NEEDS_HUMAN | INCOMPATIBLE
Highest proven gate: G0/G1/... or none
Host / image region / version: ...
Files changed: ...
Commands run + exit status: ...
Built artifacts and hashes: ...
Tests run, assertions and repeatability: ...
Screenshot, telemetry, input trace, logs: ...
Unverified assumptions / root cause / next 3 actions: ...
Minimal human input or approval genuinely needed: ...
```

## Sources

- <https://github.com/projectPiki/pikmin2>
- <https://github.com/dmang-dev/mcp-dolphin/blob/main/CHANGELOG.md>
- <https://github.com/Felk/dolphin/releases>
- <https://github.com/dolphin-emu/dolphin/blob/master/Readme.md>
- <https://github.com/randovania/py-dolphin-memory-engine>
- <https://github.com/JHaack4/CaveGen>
- <https://pikmintkb.com/wiki/Pikmin_2_instructions>
- <https://pikmintkb.com/wiki/Pikmin_2_directory_tree>
- <https://pikmintkb.com/wiki/Cave_unit_generation>
- <https://archlinux.org/packages/extra/x86_64/dolphin-emu/>
- <https://archlinux.org/packages/extra/x86_64/dolphin-emu-tool/>
