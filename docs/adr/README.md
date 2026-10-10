# Architecture Decision Records (ADRs)

Log **every technical decision** made in this project here, including benchmark
results, tool pins, fallbacks, and rejected options. Decisions that were only
"measured" (A/B drivers, codec round-trips) belong here with their evidence.

Rules for every agent session:

1. **Read the existing ADRs first.** Don't relitigate a decision unless new
   evidence appears — and then write a superseding ADR, don't edit history.
2. Write a new ADR whenever you pick between alternatives, pin a tool version,
   accept a workaround, or declare something INCOMPATIBLE.
3. A failed experiment still produces an ADR (record the failure honestly).
4. Status values: `proposed` | `accepted` | `superseded-by-NNNN` | `rejected`.

## Template

```markdown
# ADR-NNNN: <short title>

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded-by-NNNN | rejected
**Context:** what decision was forced and by what constraint
**Decision:** what was chosen
**Evidence:** commands run, hashes, run dirs under reports/runs/, links
**Consequences:** what this locks in, what it forecloses, follow-ups
```

## Index

| ID   | Title                                   | Status   |
| ---- | --------------------------------------- | -------- |
| 0001 | Local Dolphin only, hardware track cut  | accepted |
| 0002 | Target image identified as US GPVE01    | accepted |
| 0003 | Emulator driver selection deferred to A/B benchmark | proposed |
| 0004 | uv is the only Python environment/package tool | accepted |
| 0005 | Source image is NKit-trimmed; repack lane needs standardization | accepted |
| 0006 | G0 partial with waived repeats; launch/capture/stop recipe locked | accepted |
| 0007 | Driver B (stock Dolphin + DME memory + xdotool) proven for state reads | accepted |
| 0008 | pyisotools round-trip proven; dest-relative quirk + padding notes | accepted |
| 0009 | Vendored gclib codec stack; Pikmin text via same-length byte patch | accepted |
| 0010 | Data build lane proven: patch -> repack -> boot | accepted |
| 0011 | Candidate B input fully proven (uinput + SDL3 gamepad recipe) | accepted |
| 0012 | G2 fully closed: single-asset change observed in-game | accepted |
| 0013 | Headless host probe: broken Dolphin libs + uinput perms block runtime; DISPLAY/xvfb plumbing added | accepted |
| 0014 | Headless video backend measured: OpenGL/llvmpipe boots under Xvfb, Vulkan gets no window | accepted |
| 0015 | uinput module (not permissions) was the blocker; Vulkan cannot present under Xvfb; scene-diff is not an input oracle | accepted |
| 0016 | Cave data survey: real paths under `files/`, header prefix is not a row count, edits are in-place patches | accepted |
