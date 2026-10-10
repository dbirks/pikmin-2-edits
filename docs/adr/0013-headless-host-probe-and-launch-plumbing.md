# ADR-0013: Headless host probe — what actually breaks the loop, and the launch plumbing to fix it

**Date:** 2026-10-10
**Status:** accepted (see ADR-0014 for the headless video-backend measurement this plumbing made possible)

## Context

Handoff issue #1 §3 says the new machine is headless Arch and that the first job
is to prove one short `xvfb-run` session and pick a video backend. This ADR
records the first non-destructive inventory of the new host
(`delightful-goose`) and the code changes made to make the existing
laptop-proven stack capable of running there at all.

Full machine record: `reports/environment-headless.json`.

## Measured facts (not assumptions)

| Item | Result |
|---|---|
| ISO identity | `pikmin2.iso` = 995,557,376 bytes, sha256 `5388b54a…db661a` — **matches** the handoff §1.1 known-good image |
| Save fixture | `runtime/dolphin-agent/GC/USA/Card A/` came across with `MC_SYSTEM_AREA` + `01-GPVE-Pikmin2_SaveData.gci` (handoff §1.3 satisfied; §5 regeneration not needed) |
| Python env | `uv sync --frozen` clean; `.python-version` 3.12 respected; `pikminlab` entry point runs |
| Machine | bare metal (`systemd-detect-virt=none`), 8 cores, 15 GiB RAM, **Intel Kaby Lake HD Graphics 630** with `/dev/dri/card0` + `renderD128` |
| Session | no `DISPLAY`, no `WAYLAND_DISPLAY`, no `XDG_SESSION_TYPE` → truly display-less; `Xvfb` + `xvfb-run` installed |
| Yama | `ptrace_scope=1` (same as laptop — DME works when the reader is Dolphin's parent, i.e. the daemon) |
| Disk | **3.4 GiB free** on `/` (`/home` same LVM root, 98% full) |

## Blockers found (all owner-run, all `sudo`-scoped)

1. **`dolphin-emu` and `dolphin-tool` do not exec.** Not a config problem:
   `ldd` shows `libavformat.so.63/libavcodec.so.63/libswscale.so.10/libavutil.so.61
   => not found`, plus `GLIBC_2.44` and `GLIBCXX_3.4.35` not found in the
   installed `libm.so.6` / `libstdc++.so.6`. The box has `glibc 2.43`,
   `gcc-libs 15.2.1`, `ffmpeg 2:8.1`, `mesa 26.0.3`, while the sync DB offers
   `glibc 2.44`, `gcc-libs 16.2.1`, `ffmpeg 2:9.0.2`, `mesa 1:26.2.4`.
   Classic Arch partial upgrade: Dolphin was installed from a synced DB against
   an un-upgraded system. **Owner fix: `sudo pacman -Syu` (full upgrade, never
   `-Sy` alone).** Until then every runtime gate is `BLOCKED`, and no amount of
   agent-side code changes will help.
2. **`/dev/uinput` is `0600 root:root` and `david` is not in `input`.**
   Modern systemd ships no udev rule granting the `input` group on uinput, so
   group membership alone is not enough — a rule is required. **Owner fix:**
   write `/etc/udev/rules.d/99-uinput.rules` containing
   `KERNEL=="uinput", GROUP="input", MODE="0660"`, `sudo usermod -aG input david`,
   reload udev + re-login. Without this the *entire verified input stack*
   (ADR-0011) is dead: the game ignores synthetic `xdotool` keys, so there is no
   fallback.
3. **Disk headroom.** The build lane writes a full 1,459,978,240-byte repacked
   image plus an extracted tree (ADR-0008), i.e. ~3-4 GiB transient. At 3.4 GiB
   free the extract→repack→boot loop will thrash or fail. Needs cleanup or a
   larger volume before P3/G3 work.
4. Optional, untested: there is **no Vulkan ICD on this box at all** —
   `/usr/share/vulkan/icd.d` does not exist, and `pacman -Ql mesa` ships no ICD
   manifest, so the handoff's `-v Vulkan` plan cannot even enumerate a device
   today. Handoff §3 also assumed Mesa's software **lavapipe** would be
   available; no package named `lavapipe`/`vulkan-mesa-drivers` exists in the
   enabled DBs (only `vulkan-intel`, `vulkan-radeon`, `vulkan-virtio`,
   `vulkan-mesa-layers`, `vulkan-mesa-implicit-layers`). This host has a real
   Intel iGPU + DRI nodes, so **`vulkan-intel` (ANV) is the better first
   candidate than software rendering**. If ANV fails under Xvfb, fall back to
   `-v OpenGL` (llvmpipe via `mesa`).
   > **Retired by ADR-0015 §2:** `vulkan-intel` was installed and ANV still
   > cannot present under Xvfb (Xvfb implements no DRI3). OpenGL/llvmpipe is
   > the working headless backend; budget ~100 s for content to appear.

## Decision: launch plumbing (agent-side, in this commit)

- `dolphin.display_env()` **inherits `DISPLAY`** instead of hardcoding `:0`
  (and honours `PIKMINLAB_DISPLAY`); the laptop path is unchanged because
  `:0` remains the fallback when nothing is exported. Without this, `xvfb-run`
  wraps the daemon and then Dolphin still tries to open a nonexistent `:0`.
- `PIKMINLAB_XVFB=1` makes `pikminlab serve` launch the emulator through
  `xvfb-run -a -s "-screen 0 1280x960x24"`. Wrapping the *child* rather than
  the daemon keeps the daemon's HTTP port bound on the real environment and
  lets the child's exported `DISPLAY` propagate to `xdotool`/`magick import`
  for capture.
- `PIKMINLAB_VIDEO_BACKEND=<Vulkan|OpenGL…>` selects `-v`; default stays
  `Vulkan`. This is the A/B knob for the measurement still owed by §3.
- `pikminlab doctor` no longer reports "tool on PATH" as health. It now
  **exec-probes** `dolphin-emu`/`dolphin-tool`, and reports display/headless
  state, uinput presence+writability, `ptrace_scope`, and free disk, returning
  typed `problems[]` (`TOOL_BROKEN`, `UINPUT_NOT_WRITABLE`,
  `NO_DISPLAY_NO_XVFB`, `UINPUT_MISSING`) and `warnings[]` (`LOW_DISK`). The
  old check passed on a machine where the emulator could not start, and failed
  on a missing laptop-only `flameshot` fallback; both are wrong signals.

## Evidence

- `uv run pikminlab doctor` → `status: FAIL` with the two `TOOL_BROKEN`
  problems and `UINPUT_NOT_WRITABLE`; captured verbatim in
  `reports/environment-headless.json` (includes `pacman -Q`/`-Sl` versions,
  GPU/DRI inventory, ISO hash).
- `ldd /usr/bin/dolphin-emu | grep 'not found'` → the four ffmpeg sonames above.
- `sha256sum pikmin2.iso` → `5388b54a9c2d156c94bcfa80acd53b513288dc17e88c97a1edfb57ad25db661a`.

## Consequences

- **G0/G1 headless re-proof is `BLOCKED`, not `FAIL`** — the emulator binary
  cannot exec, and input cannot be opened. No game was launched on this host in
  this session; nothing in §8.1 of the handoff has been demonstrated yet.
- The env-var plumbing is *written but unexecuted*; it gets validated in the
  same 2-minute session that answers the backend question, which will supersede
  this ADR's `proposed` status with concrete flags + timings.
- Static work (P3 cave/treasure parsing, `design/caves/*.yaml` compile step,
  schema/validation, CaveGen preflight) does **not** depend on any of this and
  is the right work to queue while waiting for owner action — except that it
  still wants disk headroom for extracted assets.
