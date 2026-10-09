# ADR-0007: Driver B (stock Dolphin + DME memory + xdotool input) proven for G1 observation

**Date:** 2026-10-09
**Status:** accepted (G1 state-observation leg proven; A/B vs Felk still open)
**Context:** G1 needs the agent to control the game and read validated game
state. The Felk/MCP path (ADR-0003, Candidate A) is still untested on Linux.
Candidate B (stock Dolphin 2609 + a process-memory library + virtual input)
is now demonstrated working on this Arch/GNOME host.
**Decision:** Adopt Candidate B as the driver that unlocks P2+ content work,
while leaving Candidate A unproven (do not claim A/B completeness). Concretely
locked:
- **Launch** a Dolphin child process we own (ADR-0006 recipe) so `py-dolphin-
  memory-engine` can `process_vm_readv` it — this is required because host
  Yama is `ptrace_scope=1`, which forbids a *sibling* from attaching. Memory
  reads therefore must run in the SAME process that spawned Dolphin.
- **State** read via `dolphin_memory_engine` (`hook`/`read_bytes`), not the
  Dolphin TCP handler (port 25113 never opened in 2609 build).
- **Input** via `xdotool key` to the XWayland render window (Dolphin's own
  keyboard->GC pad mapping).
- **Capture** via `magick import -window <id>`.
- **Teardown** SIGKILL the child; un_hook first.
**Evidence:** `pikminlab state pikmin2.iso` ->
`{"status":"PASS","reads":[{"addr":"0x80000000","value":"GPVE01"}]}`; the
window id is our spawn (yama-compliant) and `no-strays` after teardown.
Input leg proven earlier (title -> warning -> continue, ADR-0006 context).
**Consequences:** G1 state-observation is real, so cave/treasure assertions
can read ground truth from RAM instead of only screenshots. Constraint for
the harness author: the runner must be Dolphin's parent process. The Felk
Candidate A remains untested; a later session may still benchmark it.
