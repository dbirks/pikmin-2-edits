# ADR-0006: G0 partially proven with owner-waived repeat count; capture/stop recipe locked

**Date:** 2026-10-09
**Status:** accepted
**Context:** The 10-repeat cold-boot loop (spec §15.8 criterion 1) produced
owner-visible churn: an unbound-variable bug skipped shutdown on six runs,
and even with `ConfirmStop=False`, TERM on a batched instance with a visible
window still surfaced close dialogs. The owner waived the 10-repeat
requirement as operator-hostile for now.
**Decision:**
1. G0 recorded as **PARTIAL (5/10 clean boot→capture→auto-close cycles,
   evidence in `reports/runs/*-g0/`)**; remaining repeats deferred to an
   automated nightly once drivers exist, not run interactively.
2. Locked automation recipe: launch with `SDL_VIDEODRIVER=x11` (render
   window lands on XWayland), find it via
   `xdotool search --class dolphin-emu` + title-contains-`|`, capture with
   `magick import -window <id>`, stop agent-owned instances with **SIGKILL
   first** (`/bin/kill -KILL`) — no signal that can raise a dialog.
3. Agent policy: every Dolphin launch is script-owned with a hard total
   duration cap and guaranteed teardown, ≤60 s unless the owner asks for a
   session; never launch outside a start/stop harness.
**Evidence:** runs `2026-10-09T22*Z-g0` results.txt (4/10 + 1/1 + partial
third batch), window capture of title screen verified by inspection, zero
strays after KILL-first teardown.
**Consequences:** G1 work can proceed on a stable launch/capture/stop core.
"HIGH proven gate" reporting must say G0-partial until repeats complete.
