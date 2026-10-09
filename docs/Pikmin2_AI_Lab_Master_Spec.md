# Pikmin 2 AI Lab — Master Product and Engineering Specification

**Version:** 0.3 local-Dolphin execution specification  
**Date:** 2026-10-09  
**Intended audience:** autonomous coding agent running locally on a Linux laptop; human project owner  
**Status:** researched and specified; no installation, emulator benchmark, modified-game build, or gameplay E2E has yet been executed on the owner’s laptop  
**Non-goals for v0.1:** custom web dashboard, a fifth overworld slot, console hardware/deployment, unbounded autonomous gameplay, distribution of commercial game assets. Hardware/ODE planning has its own independent document.

## Owner-provided configuration (confirmed 2026-10-09)

| Field | Confirmed value | Operational consequence |
|---|---|---|
| OS | **Arch Linux** | Prefer official `extra` repo packages through `pacman`; no Ubuntu `apt` commands. Probe `pacman` availability and user session. |
| Machine | Linux laptop (primary); headless Linux server optional later | Run interactive Dolphin on the laptop. Server must never be assumed to have working GPU/display. |
| Game image | **Already available locally** | Do not schedule or require disc dumping. Agent needs only the local filesystem path; identify and validate GameCube title ID/revision from its header. |
| Agent autonomy | **Trusted setup** | Agent may autonomously run low-risk commands, provision the workspace, install user-scoped software/dependencies, and run tests. Request approval for privilege elevation, pacman system changes, kernel/input security changes, destructive operations, firmware changes, or sending game data externally. |

**Important:** The disc image is available but its **path and game ID/revision remain unknown**. Do not assume US GPVE01. All future automation must be region-aware and protect human save data.

## 0. Executive mandate

Create a local-first, reproducible toolchain that starts with a **user-provided Pikmin 2 GameCube disc image** and can: identify and verify its exact region/revision; stage original assets without modifying the input image; build game-data changes; optionally compile a modded PowerPC DOL with `projectPiki/pikmin2`; launch and control Dolphin; capture screenshots, telemetry, traces and tests; diagnose failures; and open a tested playable build for the human. **The product deliverable is a local Dolphin loop, not original-console deployment.**

**The first end-to-end vertical slice should be a small playable change in an existing overworld:** a cave entrance near the starting point, one short custom cave, and one cheekily named treasure. Reserve a future second track for a custom overworld and, after that works, an independent fifth world on the selection screen.

**Engineering principle:** agent-friendly constraints and game-state observability matter more than autonomous visual exploration. The agent should receive typed tools, schemas, reference fixtures, useful errors, and machine-readable evidence. Vision is a supplementary oracle, never the only oracle.

## 1. Known facts versus assumptions

### Verified upstream capabilities (documentation, not independently executed)

- `projectPiki/pikmin2` supports versions GPVE01 (US retail), GPVP01 (PAL), GPVJ01 (JP), and two US demos. US non-matching builds are documented as functionally equivalent and modifiable in C++ to the project's knowledge. On Linux x86-64, Ninja and a wrapper for the original compiler are documented. Source: <https://github.com/projectPiki/pikmin2>.
- Dolphin supports `--exec/-e`, `--user/-u`, `--movie/-m`, and `--batch/-b`; DolphinTool supports `header`, `verify`, `extract`, and `convert`. `--batch` does **not** prove truly headless graphics operation. Source: <https://github.com/dolphin-emu/dolphin>.
- `pyisotools` documents extracting and building GameCube ISOs via `python -m pyisotools IMAGE E --dest DIR` and `python -m pyisotools ROOT B --dest IMAGE`. It does not natively edit all SZS/RARC archives, so an additional archive tool is necessary. Source: <https://github.com/JoshuaMKW/pyisotools>.
- The Pikmin Technical Knowledge Base documents cave data editing, area generator files, custom BMD models, OBJ collision conversion (`grid.bin`/`mapcode.bin`), carrying routes, treasure configuration, and BMG dialogue. Tool builds may be Windows-centric, requiring Linux source ports or alternative pipelines. Sources: <https://pikmintkb.com/wiki/Pikmin_2_instructions>, <https://pikmintkb.com/wiki/Custom_models>, <https://pikmintkb.com/wiki/Pikmin_2_area_generator_file>.
- The `mcp-dolphin` bridge offers emulated memory reads/writes, virtual GC input, savestate operations, and frame advance **only with Felk's scripting fork**, not mainline Dolphin. Screenshots were added in 0.3.0 (subject to a compatible Felk callback); pause/resume remains unsupported; its Node bridge is CI-tested on Linux, not proof that the emulator fork works locally on Linux. Source: <https://github.com/dmang-dev/mcp-dolphin>, <https://github.com/Felk/dolphin/releases>.
- `py-dolphin-memory-engine` is a Linux-capable candidate for native Dolphin process memory access on x86-64, subject to kernel security policies and version compatibility. Source: <https://github.com/randovania/py-dolphin-memory-engine>.

### Must be proven on the user's machine (not promised)

1. Exact laptop CPU architecture, Arch kernel/version, display server, graphics driver and working Dolphin executable (distro is already confirmed).
2. Game image: US `GPVE01` versus other region/revision; verify using `dolphin-tool header/verify`, not filename alone.
3. Arch Linux stability and suitability of Felk scripting Dolphin and `mcp-dolphin` (including host input and screenshots). If unsuccessful, use standard Dolphin plus process memory + Linux virtual input.
4. Ability to deterministically capture frames and drive frame-accurate virtual input without mixing human and agent input.
5. Linux buildability of the required asset converters. Document each successful binary version and command syntax.
6. Treasures and cave entrances actually working in the running game, not just parseable in editors.
7. Verified build asset mutation in the **user-provided** game revision and actual cave/treasure semantics after cold boot.

**Rule:** distinguish `NOT_TESTED`, `FAIL`, `STATIC_PASS`, `DOLPHIN_BOOT_PASS`, and `GAMEPLAY_E2E_PASS`. A passed asset parser or successful process launch is not proof of gameplay. Owner supplied ISO is locally available; the agent must not ask for a new rip or purchase a ripping accessory.

## 2. Owner decisions and sensible defaults

| Decision | Locked choice or default | Remaining owner input |
|---|---|---|
| Main development computer | Arch Linux laptop; launch native graphical Dolphin | Agent probes CPU/GPU/display, no repeated distro question |
| Input ISO | Already present; immutable read-only source | **Local absolute filesystem path** and, if necessary, explicit permission to open it |
| Disc region | Auto-detect via image header; adapt build to revision | Only if unsupported game revision or mismatched input |
| Saves | Isolated, disposable testing saves; human saves untouched | Completed/progressed save optional, never a prerequisite |
| First demo | Cave entrance near existing spawn + custom cave + cheeky treasure | Creative direction optional |
| New overworld | Future workstream; replacement-slot prototype before fifth slot | No decision needed now |
| Dolphin driver | Empirical A/B test of scripted fork vs native | Agent decides from measured results |
| Human interface | CLI, report artifacts, native Dolphin game window | No site required |
| Agent autonomy | Trusted setup, bounded permissions and explicit risk gates | Approval for `sudo`, system packages, input/kernel policy, firmware, purchases |
| Public release | User-owned game files kept private; patches only if published | Explicit owner approval before any publishing |

## 3. Product scope: local-first execution contract

**In scope:** Arch Linux discovery and installation with approval gates; user's local ISO ingestion; extracted filesystem and patch build; cave generation and treasure edits; launch/control/observe Pikmin 2 in **Dolphin**; automated smoke and E2E tests with evidence; `pikminlab play --last-passing`; optional future replacement overworld and fifth area. No custom web application is required.

**Out of scope:** GameCube hardware procurement/modifications, network/USB/SD deployment, disc burning, power/reset wiring, console capture. See separate `Pikmin2_AI_Lab_Physical_Hardware_Options.md` for that independent research track. Never block local development on physical console information.

**Execution guarantee sought, not yet established:** Given a real, supported ISO and an approved desktop setup, the agent can produce a changed game and give a human a playable Dolphin session; report `BLOCKED` with evidence rather than inventing success if an upstream tool or the game semantics prove incompatible.

**Critical path:** validate input → boot baseline → control/screenshot/state observation → byte-for-byte no-op asset round trip → make one harmless edited asset load → make an existing-slot cave and treasure playable → actual controller-driven collection/exit → human play handoff. Engine telemetry and custom meshes should be pulled in **only when needed to satisfy measured assertions**, not pre-emptively.

## 4. Linux bootstrap, discovery, and safety

The agent must **probe** rather than assume distro, CPU or installed tools:

```bash
uname -a
uname -m
cat /etc/os-release
command -v dolphin-emu || true
command -v dolphin-tool || true
command -v flatpak || true
command -v blender || true
command -v python3 || true
command -v ninja || true
command -v java || true
command -v ffmpeg || true
echo "SESSION=$XDG_SESSION_TYPE DISPLAY=$DISPLAY WAYLAND=$WAYLAND_DISPLAY"
```

Optional display/GPU probes: `glxinfo -B`, `vulkaninfo --summary`, PCI GPU inventory, free RAM/disk, and writable artifact locations. Log detected facts to `reports/environment.json`; never log private paths/secrets unnecessarily.

**Arch Linux bootstrap** (owner confirmed Arch; commands are proposed, not executed on the owner's laptop). First record packages and available binaries without changing the system:

```bash
cat /etc/os-release
uname -m
pacman -Q dolphin-emu dolphin-emu-tool git python python-pip ninja cmake ffmpeg jdk-openjdk blender 2>/dev/null || true
pacman -Ss '^dolphin-emu$|^dolphin-emu-tool$'
command -v dolphin-emu; command -v dolphin-tool
```

With **explicit owner approval for system changes**, install the minimal initial development set from official Arch repositories:

```bash
sudo pacman -Syu
sudo pacman -S --needed \
  dolphin-emu dolphin-emu-tool git python python-pip \
  ninja cmake base-devel ffmpeg jdk-openjdk
```

Install Blender, GUI diagnostics (`mesa-utils`, `vulkan-tools`), virtual controller (`python-evdev` or scoped venv package) and extra build-time packages **only when needed** and after the applicable approval. Confirm package names with `pacman -Si` first. Use `python -m venv .venv` and `.venv/bin/python -m pip` for Python isolation. Do not globally `pip install` into Arch's system Python or casually use `pacman -Sy` without full upgrade. Arch official packages verified on 2026-10-09: `dolphin-emu` and separately `dolphin-emu-tool` in Extra; `dolphin-tool` belongs to the second package. Sources: <https://archlinux.org/packages/extra/x86_64/dolphin-emu/>, <https://archlinux.org/packages/extra/x86_64/dolphin-emu-tool/>, <https://wiki.archlinux.org/title/Dolphin_emulator>.

**Trusted-setup permission model:** agent can edit/create files under its project workspace, create venvs, run approved build/test tools, open a dedicated Dolphin process, and benchmark user-scoped methods without confirmation for every operation. It must obtain owner approval before `sudo`/`pacman -Syu`, installing system packages, kernel/ptrace/uinput policy changes, accessing important private files beyond the provided ISO, overwriting saves, opening LAN services, deletion outside disposable workspace, or disclosing game data to an external service. Avoid system-wide ptrace security relaxation. For a known-good UI fallback, official Dolphin Flatpak is optional, not the initial native-tool driver.

Use a pinned version/revision after a smoke test. Do not download unsigned binaries from arbitrary mirrors without provenance. Python packages belong in a venv and Node dependencies should use a lockfile (Node 22/24 when evaluating `mcp-dolphin`).

### Repo layout

```text
pikmin2-ai-lab/
  AGENTS.md                       # operational policy and work orders
  pyproject.toml / lockfiles
  config/lab.yaml                 # host config with explicit paths
  design/worlds/*.yaml           # agent-authored semantic descriptions
  design/caves/*.yaml
  design/treasures/*.yaml
  src/pikminlab/                 # CLI, build, drivers, telemetry
  src/pikminlab/drivers/         # felk_mcp.py, native.py
  tools/                         # pinned tool wrappers and licenses
  vendor/pikmin2-decomp/         # reference to pinned upstream checkout
  patches/                       # generated original-asset-free edits
  tests/unit/
  tests/integration/
  tests/e2e/
  tests/fixtures/               # metadata only; no licensed assets in VCS
  docs/adr/                     # architecture decisions and benchmark results
  workspace/original/           # immutable image, ignored by git
  workspace/extracted/          # user-owned game files, ignored
  workspace/modified/           # generated private working tree, ignored
  builds/                        # ISOs/DOLs, private/ignored
  reports/runs/<run-id>/         # manifests, JSONL events, images, logs
  scripts/bootstrap.sh
```

All game media, extracted proprietary assets, emulator memory cards, personal information and full ISOs **must be ignored by Git**. Never upload or publish them by default. Make builds and tests idempotent, restartable, and fail-closed.

## 5. Disc-image ingestion and provenance

Input contract:

```yaml
image:
  path: /absolute/path/to/user-owned/pikmin2.iso
  expected_title: Pikmin 2
  requested_region: auto
  immutable: true
  verify_against_redump: optional
```

Run `stat`, `sha256sum`, `dolphin-tool header -i IMAGE`, and `dolphin-tool verify -i IMAGE`. Use `dolphin-tool verify -i IMAGE -a sha1` for a digest if supported by installed release. Capture exit codes and stdout. Inspect actual game ID rather than inferred names. Require user-approved correct image when unsupported region/revision is detected; do **not** silently use GPVE01 assets/build assumptions for PAL/JP.

Archive original ISO read-only. Extract into fresh per-version trees. Reconstruct game only from verified input + declarative patch overlay. Initial packaging candidate:

```bash
python -m pyisotools /path/to/pikmin2.iso E --dest workspace/extracted
python -m pyisotools workspace/modified B --dest builds/pikmin2-lab.iso
```

Pin tested tool version and verify extracted root contains `sys` and game-data files. `pyisotools` is for disc file structure, **not** a universal SZS/RARC/BMD/BMG converter. Provide separate archive and asset adapters. A rebuild must be booted in Dolphin and inspected, not considered valid merely because a nonzero ISO file exists. Optionally use Dolphin's extracted-files workflow for fast development, but verify the exact supported directory structure.

The owner has already supplied that an image exists locally. Do not ask for dumping hardware or procedures in this project. Do not upload the ISO or original asset bytes to a third-party service. Confirm local path and applicable permissions only.

## 6. Build lanes and asset pipeline

Two independent lanes plus optional world-gen lane:

**Lane A — Data-only:** work from original game content; modify cave definitions/area generator/treasure assets/text/config; reserialize archives; repack ISO; run Dolphin. This should be first.

**Lane B — Engine debug/mod:** use `projectPiki/pikmin2`, run `python configure.py --non-matching`, then `ninja` after extracting system data to the correct `orig/<version>/sys/main.dol` path (for US retail: `orig/GPVE01/sys/main.dol`). Output `build/GPVE01/main.dol` for US. Stage only on supported/tested versions; track decomp commit and toolchain versions. Use for telemetry, test-only stage load, free camera, debug HUD, extra stage integration, and other engine modifications.

**Lane C — Custom overworld:** Blender scripted generation to render model `.bmd` (SuperBMD or tested equivalent), separate simplified collision `grid.bin`/`mapcode.bin` (obj2grid), route graph, object generators, spawn/day cycle configs and stage references. Stage replaces an existing world until proven; fifth-map UI/progression must be a separate research task.

All lanes require reversible mod patches, a baseline/modified comparison, per-file provenance, and round-trip tests (parse → serialize → parse, where possible).

### Suggested agent-facing design schemas (invented project format)

```yaml
cave:
  id: lab_intro
  target_existing_slot: true
  floors:
    - theme: garden
      room_budget: 5
      treasures: [{id: circuit_token, quantity: 1}]
      enemies: [{id: dwarf_bulborb, quantity: 2}]
      exit_required: true
      seed_policy: deterministic_test_matrix
```

```yaml
treasure:
  id: circuit_token
  display_name: Pocket Memory Monolith
  source_object: usb_drive
  nominal_poko_value: 80
  carry_weight: 5
  journal: "A remarkable relic from a forgotten civilization."
  ship_pitch: "Thousands of memories, not one available without an adapter!"
  asset_generation: lowpoly_blender
```

These YAML examples are **not Pikmin-native formats** and must be compiled with validated converters. Preserve character encoding and resource alignment. Start with reskinned existing slots; only then attempt new internal IDs and asset tables. Inventory names and Treasure Hoard descriptions can have separate UI paths, so assert both. See the treasure page <https://pikmintkb.com/wiki/Pikmin_2_otakara_config.txt> and game text <https://pikmintkb.com/wiki/BMG_file>.

## 7. Emulator-driver interface: must exist before content automation

Define a typed Python protocol so candidate implementations can be evaluated and swapped:

```python
class EmulatorDriver(Protocol):
    async def launch(self, executable_or_iso: Path, user_dir: Path) -> None: ...
    async def health(self) -> dict: ...
    async def input(self, port: int, buttons: list[str], stick: tuple[float,float], frames: int) -> None: ...
    async def frame_advance(self, frames: int) -> None: ...
    async def read_memory(self, address: int, size: int) -> bytes: ...
    async def snapshot(self) -> Path: ...  # optional savestate, capability-gated
    async def screenshot(self) -> Path: ...
    async def reset(self) -> None: ...
    async def stop(self) -> None: ...
```

Support optional capabilities (`savestate`, `write_memory`, `pause`, `video`, `overlay`, `deterministic_input`, `screenshot`) returned from `health`; do not expose a method as fully working when it isn't. Implement adapter-specific deadline/retry strategy and never retry arbitrary stateful input without idempotency safeguards.

### A/B spike: Dolphin automation

**Candidate A: Felk scripting fork + mcp-dolphin**

Hypothesis: frame-accurate input and memory control is substantially easier through its built-in bridge. Steps: acquire and verify a Linux-compatible release/build; bring up Felk; load bridge; confirm game ID at emulated address `0x80000000` (expected 6-byte GameCube disc ID); press Start; advance 60 frames; inspect a stable state field; capture image through separate screenshot path if MCP lacks it. Known limitation: bridge pause/resume deadlock; `dolphin_screenshot` was added in 0.3.0, but requires a compatible Felk frame callback; Linux viability still unproven on this host. Sources: <https://github.com/dmang-dev/mcp-dolphin>, <https://github.com/Felk/dolphin/releases>.

**Candidate B: stock/native Dolphin + Python Dolphin Memory Engine + virtual Linux input**

Hypothesis: native Dolphin has higher Linux compatibility; process memory reads may be sufficient for ground-truth telemetry. Steps: discover the Dolphin process; test pointer/memory library; configure dedicated virtual controller via `uinput`/evdev or equivalent; map GC buttons/analog axes; run fixed action script; capture screenshot through Dolphin hotkey or window capture. Account for Wayland focus/input constraints. Use same-user process where possible, minimize ptrace privileges, don't run test runner as root.

**Candidate C: Dolphin fork with purpose-built local RPC** (only after A/B failures).

Evaluation matrix: startup reproducibility (20 launches), input success (100 sequences), state reads (100), screenshot freshness, frame variance, crash rate, dependency churn, licensing/build complexity, operator burden, Wayland vs X11 behavior. Test on a pinned baseline image; generate ADR including data and rationale. **Selection rule:** prefer A if Linux viability and deterministic control are demonstrated; otherwise B; C only if neither meets requirements. Do not select based on hype or README claims.

### Human playback

A separate `pikminlab play` command must launch the **last passing build** in a fresh human-specific Dolphin user directory, with an explicit expected game image and gamepad settings. Never overwrite active gameplay saves or close a human emulator process to satisfy automated tests. For native Dolphin:

```bash
dolphin-emu --user "$HOME/pikmin2-ai-lab/runtime/human" \
  --exec "$HOME/pikmin2-ai-lab/builds/pikmin2-lab.iso"
```

Adapt binary location to machine. `--batch` is not an automatic license to rely on displayless GPU performance. If there's no working graphical desktop, allow server build/static tests but defer emulator gameplay execution to laptop.

## 8. Observability and model success

### Preferred debug-game telemetry protocol

The modded DOL will optionally write versioned telemetry into a fixed, discoverable region of emulated MEM1, as a fixed-layout binary structure with magic, schema version, build ID, total size, sequence number, timestamp/frame and CRC/sequence-lock fields. Discover address via link map/symbol rather than magic hardcoding unsupported addresses. Telemetry updates at the frame boundary; external reader requires matching build/schema IDs and detects torn reads.

Minimum state:

- process/game scene; stage/cave/floor ID; load transition; active save profile; current in-game day
- frame counter, simulation health heartbeat and fatal/error flags
- captain world pose/camera pose; field Pikmin total/following/carrying/lost by type
- objects with stable test-assigned IDs, type, coordinates, carried-by count, spawn/despawn states
- treasure states: discovered, actively carried, entered collection state, counted in progression
- nav route graph connectivity, active route segment, no-progress watchdog and stuck entity counters
- cave entry/exit transition events; collected treasure list; debug scene-load result

All telemetry emitted in a compact `state.json` and `events.jsonl` stream with schema validated in CI; full RAM dumps only by user opt-in and **never** include arbitrary memory contents in prompts/logs.

### Instrumentation UX

Toggle debug features via tool/keyboard: `overlay.labels`, `overlay.routes`, `overlay.collision`, `overlay.spawn`, `overlay.camera`, `overlay.performance`, `overlay.clean`. Render numbered IDs and relevant state near entities. When projecting 3D→2D positions use game camera projection + clipping; a simpler screen-edge/entity-list overlay is acceptable MVP. Capture both **clean** and **annotated** screenshots at known frame IDs. Debug mode must not silently change game physics or award pickups.

### Action/test evidence structure

```text
reports/runs/2026-10-09T140000Z-abc123/
  manifest.json           # code revision, game ID/digest, tool versions, seed
  environment.json
  steps.jsonl             # intended input, frame ranges, status
  events.jsonl            # schema-versioned telemetry
  assertions.json         # pass/fail/skip and reason
  logs/{build,dolphin,bridge}.log
  captures/{clean,debug}/*.png
  video/test.mp4          # when enabled
  crash/                  # GPU/DOL crash reports as available
  summary.md
```

Never mark a test passed just because Dolphin launched or the entity appeared in a screenshot. Require game-state assertions and progression checks.

## 9. Testing hierarchy, A/B testing, and quality gates

**Tier 0 — preflight:** OS/GPU tools present; working permissions; disc game ID/verified image; free storage; pin versions; no unsafe target paths.

**Tier 1 — fast unit tests:** schema validation, codec round-trip, valid treasure IDs, message encoding, collision graph connectivity, patch manifests, archive checksums, overlay transform tests, CLI error contracts.

**Tier 2 — randomized static/procedural:** CaveGen supported caves + custom definitions; generate bounded seeds and inspect exit/hole/treasure placement and room budget; log pathological seeds for regression. CaveGen: <https://github.com/JHaack4/CaveGen>.

**Tier 3 — emulator integration:** every build boots to menu, loads selected area without hang, controlled input affects captain, valid stage/frame telemetry, cave entrance activated, cave loads, new treasure spawns, no missing textures/model crashes, return/exit works.

**Tier 4 — real-input game E2E:** no debug teleport, no write-memory state mutation. Starting from known legitimate save and exact controller trace, Pikmin gather treasure, carry it to ship, and actual collection/progression is confirmed. Additional cases: replay after cold restart, enter/exit cave with squad, game over/day-end, save/load and reload changed content.

**Tier 5 — visual review:** anchored clean + debug image comparisons and LLM visual observations; compare scene attributes rather than use only pixel-perfect golden snapshots across different GPU backends. Vision-generated verdicts are observations, not assertions about game state.

### Example contract for first real smoke test

| Step | Check | Failure evidence |
|---|---|---|
| Boot | title/menu reached within frame budget | screenshot + transition log |
| Enter area | valid player + area IDs | state snapshot |
| Find entrance | matching cave object ID near landing position | entity dump + screenshot |
| Enter cave | cave floor loaded, safe arrival | transition events + frame timing |
| See new treasure | correct treasure ID, name, mesh loaded | entity/config validation + clean image |
| Collect via controls | treasure returned to ship and credited in progression | input trace + collected event |
| Return | no crash on cave exit | transition events |
| Reboot | modified game boots and expected state persists | fresh-process assertion |

### A/B rules for content and software

- Compare **one primary hypothesis per experiment**, e.g. candidate model/room budgets, two types of arrival geometry, or two Dolphin adapters.
- Hold game revision, ISO, emulator version, random seeds, initial save and fixture constant. Use paired seeds (e.g. same 100 seeds) for cave-design comparisons.
- State expected measurable outcomes *before* running: completion rate, crash rate, stuck percentage, median frames to treasure, loading time, asset sizes. Preserve baseline A and candidate B manifests and failure seeds.
- Static and game-state metrics are necessary; creative/art quality still needs owner judgment. Never let the model optimize solely for easiest automated test if it degrades gameplay.
- A failed candidate produces an ADR and a narrower follow-up experiment, not an undocumented tool swap.

### Acceptance gates

- **G0 Host:** stable Dolphin boot of original image on laptop, identical input 10 repeated runs, evidence directory generated.
- **G1 Driver:** input + screenshot + at least one validated memory-state observation; 20 stable launches; no stale screenshots.
- **G2 Data pipeline:** original disc extracts and rebuilds; modified ISO boots; patch reversible and per-file delta known.
- **G3 Vertical slice:** a new cave entrance triggers a reachable floor and one renamed/custom treasure is collected via real input, with fresh clean screenshot, screenshot annotated in post-processing if useful, controller trace, and assertions. An in-game HUD is optional until G4.
- **G4 Agent self-repair:** deliberately break route or object reference; validator/test identifies failure; agent corrects it; G3 succeeds.
- **G5 World:** small replacement overworld with independent BMD, collision and route assets; Pikmin can carry an item home, exit day and save/reload.
- **G6 New fifth area:** original four worlds intact, independent menu point/unlock, stage IDs and save semantics, test from fresh/complete files.

## 10. Agent task interface and human handoff

Proposed CLI (to be implemented):

```text
pikminlab doctor
pikminlab ingest /path/to/owned.iso
pikminlab bootstrap
pikminlab build --lane data
pikminlab test --suite smoke
pikminlab test --suite cave-seeds --seeds 100
pikminlab test --suite e2e --case intro-treasure
pikminlab inspect --run <id>
pikminlab play --last-passing
pikminlab export --format iso --last-passing
```

Every command must print a machine-readable result record: status, artifact paths, tool versions, next action. `doctor` must be read-only. `ingest` should copy or link the image read-only and validate it. `play` must use last **accepted passing build**, not an arbitrary unvalidated latest artifact. The export is strictly local; there is no hardware deploy command in this spec.

The agent should have narrow tools such as `build_asset`, `compile_cave`, `patch_image`, `launch_dolphin`, `press_gc_buttons`, `advance_frames`, `inspect_state`, `capture_frame`, `run_assertion`, `summarize_failure`, and `publish_human_build`. Shell access is a fall-back, not the main long-term interface.

### Approval policy

Allowed without further approval: Git writes inside repo, read-only inspection, tool installation into workspace-controlled venv, generation of derived files, launching/terminating **agent-owned** Dolphin process, local automated tests, rewriting generated files, opening a playable Dolphin window for owner on request.

Require explicit approval: `sudo`/kernel permissions, modifying or factory-resetting original memory cards/saves, contacting new external services with game assets, deleting non-generated data, publishing source/game files, or overwriting user's manually edited assets.

### Status semantics

Agent returns one of `PASS`, `FAIL`, `BLOCKED`, `NOT_TESTED`, `NEEDS_HUMAN`, `INCOMPATIBLE`; no blanket 'done' claims when only static parsing works. End every milestone with reproduction steps, test evidence, what changed and what remains unverified.

## 11. Detailed phase/work breakdown

### Phase P0 — machine + image audit

- Inventory Linux machine, graphical session, gamepad, free disk, image ownership/region, no console information requirements.
- Make repo, ignore proprietary/media paths, implement `doctor` and `ingest` dry-run.
- Verify unmodified Pikmin 2 boots in an isolated Dolphin user profile, capture title-screen screenshot manually/automatically.
- Outputs: host inventory, game provenance manifest, pinned Dolphin version, baseline screenshot.
- Gate: G0.

### Phase P1 — automation benchmark (parallel branches, then choose)

- Branch A: Felk scripting Dolphin + MCP bridge on Linux (check Linux binary/build viability).
- Branch B: stock Dolphin + python memory engine + virtual GC controller + screenshot hotkey/capture.
- Develop common driver interface and capability matrix before connecting either to high-level tests.
- Run repeatability and input/screenshot/state tests; record ADR.
- Gate: G1. **This is the highest uncertainty and should be done before modding content.**

### Phase P2 — data/build compiler

- Wrap `pyisotools` extraction/build and SZS/RARC archive conversion; detect region-sensitive paths.
- Establish semantic schemas and reversible patch bundles.
- Prove ISO round-trip, then change one low-risk text/data asset and boot.
- Gate: G2.

### Phase P3 — smallest playable cave

- Using existing cave slot and generated cave file, place cave entrance near an existing overworld landing area.
- Reuse an existing treasure slot at first; add custom name and ship text, then optionally custom low-poly model.
- Validate cave seed layouts and sound/music references; test stage and cave transition.
- Instrument cave ID, treasure ID, and collected status. Write first e2e controller trace.
- Gate: G3.

### Phase P4 — game-observability enhancements

- Compile debug DOL with fixed-layout telemetry, debug labels and test-only stage loader (guarded by build flag).
- Add event logs, stuck detection and rich automated screenshot annotations.
- Verify debug instrumentation does not accidentally change release gameplay results.
- Gate: G4 after negative test/self-repair.

### Phase P5 — custom content generator

- Build Blender headless scripts for low-poly treasures; test geometry/material/size budgets.
- Generate witty text + BMG config and in-game menu icon. Add schema validators and model viewing screenshots.
- Use original-asset-only patches for distribution; maintain content IDs and compatibility matrices.
- Accept content as iterative pull requests subject to unit/integration tests.

### Phase P6 — custom overworld

- First replace one original map slot in a special debug build, not additive fifth slot.
- Generate BMD visuals, simplified collision, route graph, generator placements and stage settings using shared coordinates.
- Test walkable paths, water/hazards, Pikmin carrying, cave entry, day end and save/reload; observe memory/performance in Dolphin.
- Gate: G5.

### Phase P7 — independent fifth world (later)

- Research and patch hardcoded area count, stage loader, menu widgets, planet-map marker, unlock gating, treasures, cave IDs, music and persistence.
- Introduce a development unlock/complete-save fixture, but ensure normal progression works without it.
- Gate: G6. Original-console topics belong to the standalone hardware document and are not work orders here.

## 12. Risks and mitigation backlog

| Risk | Impact | Mitigation |
|---|---|---|
| Unsupported disc region/revision | Wrong offsets/assets, boot failure | Detect actual disc ID and gate per region |
| Felk Linux fork won't run | Agent cannot use existing MCP | A/B native driver fallback |
| Stock Dolphin virtual input nondeterminism | Flaky tests | Frame/clock instrumentation, capture input traces, restrict focus changes |
| Memory engine fails due to ptrace/sandbox | Missing telemetry | Native build, guarded capabilities, debug DOL, no global security disable |
| Output ISO builds but doesn't boot | False-positive pipeline | Mandatory Dolphin boot and file reference tests |
| Shift-JIS/SZS/headers wrong | Crashes or silent parse failures | Round-trip codecs, golden baselines, binary diff |
| Cave floor added without associated music/config | Game crash | Cross-resource validation prior to packaging |
| Custom models/collision too large | Performance or boot issues | Budgets + small vertical slice + Dolphin memory/frame checks |
| Save-state incompatibility | False regression or corrupt fixture | Cold-boot smoke tests; pinned revisions; isolated saves |
| Model accidentally writes a passing state | False confidence | Keep debug-assisted and real-input E2E lanes separate |
| Fifth area count/save logic hardcoded | Long R&D cycle | Separate milestone, existing-slot development |
| Copyright / anti-circumvention / distribution | Legal risk | User-provided own dump, private assets, patch-only sharing |

## 13. Research backlog — the remaining unknowns

1. **Felk scripting Dolphin release on Linux:** check published assets and attempt source build; inventory required Python runtime + crash workarounds. Capture actual test results before choosing.
2. **Dolphin driver screenshot implementation:** assess official screenshot hotkey, Felk frame data, GPU/window capture and freshness metadata on Wayland and X11.
3. **Pikmin 2 per-region symbol map/telemetry:** find safe memory-section allocation, stable test entity IDs, and high-signal state hooks in the C++ source.
4. **Working CLI paths to SZS/RARC/BMD/BMG conversion on Linux:** audit source licenses, test against extracted assets, fix platform-only GUI assumptions.
5. **Data-only cave-entry path for target stage:** exercise generator `{cave}` object, stage table cross-reference, BGM lists and save behavior with a test ISO.
6. **Treasure slot expansion:** distinguish retexturing/replacing vs appending a new ID; test BMG and Treasure Hoard entries, collectible persistence and collision.
7. **Custom world map constraints:** verify graphics and collision size/format budgets on target GameCube, route behavior with carried objects.
8. **True fifth world engine audit:** global max stage count, selection menu, area unlocks, filesystems, save representation, entrance/cave identity.

Each item should be a timed research spike with: hypothesis, setup, commands, reproducible proof, source links, outcome, fallback and ADR.

## 14. Definition of success for v0.1

A human can provide an ISO path, authorize local dependency installation where needed, and tell the agent *"make me a one-floor cave and a silly treasure near the start."* The agent:

1. verifies game version and archives the untouched image;
2. validates/rebuilds the editable game assets;
3. boots original and modified versions in Dolphin with isolated profiles;
4. reaches the newly exposed cave via actual controller input;
5. enters the cave and demonstrates the treasure's identity and eventual collection through game-state telemetry;
6. captures at least two clean screenshots, optionally post-processes an annotated diagnostic view, plus test log and input trace;
7. reports explicit pass/fail with build manifest and leaves the **last passing build** launchable through `pikminlab play`;
8. does not harm original disc data, main human saves, or original game assets;
9. uses **no original-console dependencies** to declare success.

A run that cannot do any of these steps must stop at the correct failed gate, with a reproducible explanation; the agent should iterate locally until the gate passes or a clearly documented human blocker remains.


## 15. Implementation-grade missing pieces / revised research (2026-10-09)

The original 0.2 spec established architecture but **did not** supply enough low-level detail to guarantee a fully autonomous run. The following engineering controls are now mandatory before declaring the agent's loop complete.

### 15.1 Current Dolphin MCP reality and version-detection test

`mcp-dolphin` **0.3.0 (2026-07-19)** added `dolphin_screenshot` with inline PNG via Felk's frame-drawn callback. Its README and older CHANGELOG sections still contain older "no screenshot tool" statements. Treat the dated v0.3.0 changelog as the feature claim and dynamically prove capability at runtime. The bridge still requires Felk's fork, which has not been established to build/run on this owner's Arch Linux machine; pause/resume over the bridge remains infeasible without upstream architectural changes (the coroutine stops responding when emulation is paused). Removing scripts from the Felk Preview 4 scripting UI can crash; prefer fresh emulator processes. The MCP Node process has Linux CI but **that does not verify the emulator itself**.

Work order: query installed bridge version and `tools/list`; request `dolphin_screenshot` twice after controlled frame changes, check both PNG decoders, dimensions, image hashes/frame IDs and no stale read; record capability false if absent or stale. Never claim screen observation just because PNG bytes were returned. Sources: <https://github.com/dmang-dev/mcp-dolphin/blob/main/CHANGELOG.md> and <https://github.com/Felk/dolphin/releases>.

### 15.2 Exact first-party integration seam

Dolphin mainline documents `--user`, `--exec`, `--save_state`, `--movie`, `--debugger`, `--logger`, `--batch`, and `--video_backend`; this is **not** a native frame-control or RPC API. `--batch` may still require a functional graphical backend, so don't equate it with true headless automation. The Arch official repo provides `dolphin-emu` and `dolphin-emu-tool` separately. Prove mainline can launch the extracted-game directory by following the technical wiki's **Extract Entire Disc → add extracted `sys` to Dolphin game paths** workflow; do not assume the `--exec` argument accepts an arbitrary extracted-root directory. Build a fast-lane wrapper that uses a discovered executable game entry, and an ISO export lane for reproducible release candidates.

**Minimum input experiment** on both driver candidates: known baseline, press Start for 2 emulated frames, release for 15 frames, advance another 30 frames, read disc ID at `0x80000000`, capture a screenshot; repeat after cold restart. Make button clearing and stick-neutral state explicit. Record whether frame advancement is deterministic or only elapsed/real-time timeboxed. Source: <https://github.com/dolphin-emu/dolphin/blob/master/Readme.md>.

### 15.3 Region/data manifest and extracted asset verification

Read region/version at the disc header and confirm with `dolphin-tool header/verify` as offered by the locally installed build; command flags must be discovered from its own `--help`. The decomp supports `GPVE01`, `GPVP01`, `GPVJ01`, and demos; the default nonmatching example assumes `GPVE01`. Verify stage/content paths against the **actual** extracted files, not inferred filenames. Technical wiki identifies cave generation data under `user/Mukki/caveinfo/`, cave units `user/Mukki/units/`, mapunit data under `user/Mukki/mapunits/arc/`, and sound lists under `user/Totaka/`. The `arc.szs` and `texts.szs` mapunit archives have distinct contents and **must not be rebuilt as one combined archive**. Preserve path case and ordering when serialization requires it. Sources: <https://pikmintkb.com/wiki/Pikmin_2_directory_tree>, <https://pikmintkb.com/wiki/Cave_unit_generation>, <https://pikmintkb.com/wiki/Pikmin_2_instructions>.

**Round-trip ladder:** (a) ISO integrity verified; (b) extract filesystem inventory and hashes; (c) repack without changes and boot; (d) open/parse/serialize one archive without semantic changes and boot; (e) change exactly one cave parameter and observe in game; (f) only then change area generator, treasure text, and/or executable. Require before/after file diffs and a provenance/ownership manifest. A CRC/hash mismatch is not automatically a failure if compression/order differs, but unexplained semantic differences are.

### 15.4 Deterministic cave simulation is preflight, not proof of real gameplay

CaveGen requires a prepared configuration/assets directory and provides CLI flags for `seed`, `num`, `consecutiveSeeds`, custom cave `.txt` files, `region`, and image/stat output. Its documented argument convention is command style, not standardized `--flag` syntax. **Do not hard-code an example without executing `java -jar CaveGen.jar` and verifying invocation plus outputs.** Use 20 fixed seeds for a first check and 100+ after the pipeline stabilizes; record seeds, generated images and simulator version. Validate resources/cave ID consistency, presence of an exit, room graph and audio BgmList cardinality; then still boot actual game and enter/leave the cave. Source: <https://github.com/JHaack4/CaveGen>.

### 15.5 Test harness architecture: separate five oracles

A test may have multiple independent evidence channels:

1. **Process oracle:** correct emulator PID, binary, game region, alive/fault state, stderr/stdout and frame heartbeat.
2. **Asset oracle:** compiled cave/treasure/stage references, round-tripped archives, expected hashes and decompressed sizes.
3. **Game-state oracle:** verified RAM symbol or versioned debug telemetry: scene/stage/cave ID, player active, treasure picked up, progression credited, exits.
4. **Interaction oracle:** controller traces with start/end frame, neutral releases and action outcomes; a real-input test cannot be 'passed' using direct memory writes or forced game events.
5. **Visual oracle:** PNG taken after expected frame and correct instance, crop/overlay metadata, frame ID, camera/scene; a vision-model note is not equivalent to treasure-state proof.

**Attribution rule:** the modification must be demonstrated against an *unmodified* game using identical test setup. If a treasure was present in the baseline as well, your change must be corroborated by its new text, model, placement or state, not merely its presence. A brand-new ID isn't required for MVP; replacing an existing slot is expressly allowed.

### 15.6 State machine, retries, failure classes, and agent termination

Implement a runner state machine: `DISCOVERED → INGESTED → BASELINE_BOOTED → DRIVER_PROVEN → ASSETS_READY → BUILT → STATIC_PASSED → DOLPHIN_BOOTED → SCENE_CONFIRMED → GAMEPLAY_PASSED → HUMAN_READY`. Every transition emits JSON with `{run_id, build_id, state_before, state_after, monotonic_ns, evidence_paths, errors}`. No skip from `BUILT` directly to `HUMAN_READY`.

Define typed errors: `INVALID_DISC`, `REGION_UNSUPPORTED`, `ASSET_CODEC_FAILURE`, `REBUILD_FAILURE`, `EMULATOR_CRASH`, `DRIVER_DISCONNECTED`, `STALE_SCREENSHOT`, `FRAME_STALL`, `STATE_UNKNOWN`, `GAMEPLAY_TIMEOUT`, `TEST_ORACLE_MISMATCH`, `HUMAN_APPROVAL_REQUIRED`.

Retry transient emulator starts at most 2 times with a **fresh test profile** and same immutable build; never auto-retry stateful controller sequences within a running game unless reinitialized. Stop and report after 3 failed attempts at one stage, or after a configurable compute/time budget; preserve a minimal reproducible test and issue. No loops with unbounded self-repair or unbounded vision token usage.

### 15.7 Golden test fixtures and reproducible mod-output contract

- `tests/fixtures/baseline/`: no copyrighted game bytes; store region-specific IDs, screenshot scene descriptions, reproducible movement traces and hash fingerprints only where permitted.
- `tests/fixtures/saves/`: locally derived and gitignored; generated by a baseline playthrough or owner-provided save, not pulled from an unknown build. Ensure deterministic player, day, Pikmin counts, cave unlocks and start positions.
- `manifest.json`: `{schema_version, run_id, input_image_sha256, game_id, disc_revision, dolphin_binary_sha256, dolphin_version, mod_git_sha, archive_tool_versions, random_seeds, test_fixture_id, output_sha256, timestamp_utc, pass_gates}`.
- Test reports include `failure_kind`, expected and actual values, controller trace, game-state snapshot, last two screenshots, stdout/stderr and exact repro CLI.
- `pikminlab play --last-passing` reads an atomically written manifest pointer, checks build existence/hash and then launches **human profile**; never deploy an untested `latest.iso` on success based only on build output.

### 15.8 Measurable acceptance criteria for first playable demo

1. **Baseline:** 10 cold starts on the user image successfully identify game, reach a visible controllable scene, and exit cleanly (or log failures with reproducibility). This must be proven on the laptop.
2. **Driver:** 20 repeatable input/screenshot/game-state observation runs; at least one input causally changes game state; screenshot freshness tied to frame/scene; zero unexplained stuck instances during accepted benchmark.
3. **Data:** untouched repackaged game boots; one purposeful data change is observable, with patch diff and archive validation.
4. **Vertical slice:** input-driven start → reach entrance → cave load → actual treasure collection → progression credited → cave exit, captured in at least 3 distinct cold launches. Debug warp may be used for setup/unit verification, **never** to claim the real-input journey passed.
5. **Agent repair:** intentionally inject one *safe, local* bad reference/route into a generated test asset; test fails with correct error attribution; agent repairs it; same seed/fixture then passes.
6. **Handoff:** commands and report allow owner to play last passing build in Dolphin without breaking personal Dolphin config or saves. A human can inspect failures when a milestone is blocked.

The acceptance criteria represent intended tests, **not claims they have been run**.

### 15.9 Practical implementation choices to defer

- Decide engine instrumentation vs RAM-symbol map based on missing game-state values measured in a prototype, not imagined future requirements.
- A visually perfect overworld or additional fifth map is not necessary for the cave-and-treasure acceptance gate.
- Never require fully autonomous visual navigation if authored controller traces suffice; a model may design routes while deterministic navigation verifies them.
- Do not ask for a web UI; Markdown reports, PNGs, logs, and CLI launch are sufficient.
- Keep all hardware/ODE/USB/Raspberry Pi work in `Pikmin2_AI_Lab_Physical_Hardware_Options.md`, not the local AI Lab critical path.

## 16. Sources verified for this revision

- `mcp-dolphin` 0.3.0 screenshot added, pause/resume limitation: <https://github.com/dmang-dev/mcp-dolphin/blob/main/CHANGELOG.md>
- Dolphin CLI options: <https://github.com/dolphin-emu/dolphin/blob/master/Readme.md>
- Arch emulator packages: <https://archlinux.org/packages/extra/x86_64/dolphin-emu/>, <https://archlinux.org/packages/extra/x86_64/dolphin-emu-tool/>
- Extracted filesystem testing: <https://pikmintkb.com/wiki/General_instructions>
- Game resource directory map: <https://pikmintkb.com/wiki/Pikmin_2_directory_tree>
- Cave unit SZS distinctions: <https://pikmintkb.com/wiki/Cave_unit_generation>
- Cave simulation CLI/seed options: <https://github.com/JHaack4/CaveGen>
- Pikmin 2 decomp build: <https://github.com/projectPiki/pikmin2>

## 17. Primary research/source links

- Decompilation and Linux build: <https://github.com/projectPiki/pikmin2>
- Dolphin mainline CLI and `dolphin-tool`: <https://github.com/dolphin-emu/dolphin>
- Official Dolphin Linux releases: <https://flatpak.dolphin-emu.org/download/>
- Experimental MCP bridge: <https://github.com/dmang-dev/mcp-dolphin>
- Python scripting fork: <https://github.com/Felk/dolphin/releases>
- Linux-compatible process memory library candidate: <https://github.com/randovania/py-dolphin-memory-engine>
- Disc packaging: <https://github.com/JoshuaMKW/pyisotools>
- Cave generation simulator: <https://github.com/JHaack4/CaveGen>
- Cave editor: <https://github.com/Drought-Ender/Drought-Cave-Creator>
- Pikmin technical wiki: <https://pikmintkb.com/wiki/Pikmin_2_instructions>
- Custom model/collision instructions: <https://pikmintkb.com/wiki/Custom_models>
- Area generator documentation: <https://pikmintkb.com/wiki/Pikmin_2_area_generator_file>
- Treasure configuration: <https://pikmintkb.com/wiki/Pikmin_2_otakara_config.txt>
- Game messages: <https://pikmintkb.com/wiki/BMG_file>
- Arch official Dolphin package: <https://archlinux.org/packages/extra/x86_64/dolphin-emu/>
- Arch official Dolphin CLI-tool package: <https://archlinux.org/packages/extra/x86_64/dolphin-emu-tool/>

---

**Working-document rule:** Update the 'known facts vs assumptions' section and issue log after every spike. Do not rewrite failed experiments out of the record. Prefer validated working behaviors over ambitious undocumented integrations.
