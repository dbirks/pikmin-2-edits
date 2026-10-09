# ADR-0003: Emulator driver selection deferred to P1 A/B benchmark

**Date:** 2026-09 (spec) / reaffirmed 2026-10-09
**Status:** proposed (decision due after benchmark)
**Context:** Two candidate control planes exist: (A) Felk scripting fork +
`mcp-dolphin >= 0.3.0` — easy frame control but Linux viability on this host
is unproven and pause/resume deadlocks exist; (B) mainline `dolphin-emu` +
`py-dolphin-memory-engine` + uinput/evdev virtual pad + Wayland-aware capture
— higher compatibility, more integration work. Host runs Wayland
(`wayland-0`, XWayland at `:0`), which affects capture and input focus.
**Decision:** No selection yet. Build the common `EmulatorDriver` protocol
first, run both against GPVE01 with identical input scripts (20 launches,
100 input sequences, screenshot freshness, disc-ID read at 0x80000000), and
pick by measured evidence per spec §7 selection rule: A if viable, else B,
C (custom RPC fork) only if both fail.
**Evidence:** To be attached under `reports/runs/` with the benchmark
matrices; this ADR gets amended with the results and flips to `accepted`.
**Consequences:** Code must not hard-depend on either stack before G1. Test
lanes stay driver-agnostic behind the protocol.
