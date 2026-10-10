# ADR-0023: G0 evidence defect — two "fresh starts" produced byte-identical captures

**Date:** 2026-10-10 · **Status:** accepted

## Finding F3
`reports/runs/2026-10-09T225225Z-g0/run1/capture.png` and `run2/capture.png` are
**byte-identical** (same SHA-256). G0's claim is "boots in an isolated Dolphin on 10
fresh starts" with a captured frame per start; identical captures across independent
runs mean at least one sample is not evidence of its own boot — the frame could have
been re-read from a stale buffer, or the two runs truly froze on the same frame.
Two more byte-identical pairs exist inside single runs
(`2026-10-10T021234Z-serve/a11 == a20`, `021840Z-serve/a31 == a40`, 9 steps apart),
consistent with a frozen scene rather than a live render.

## Decision
1. The G0 board stays as recorded (boots verified) but its *capture* evidence is
   annotated as insufficient: ADR-0006 waived the 10-repeat; the repeats that exist
   are not independent frames.
2. Gate harnesses must (a) assert `lit()` on every sample (ADR-0022), (b) assert
   cross-run capture hashes differ, and (c) stamp each sample with its PID/window and
   build hash so a collision is attributable instead of silent.
3. No future gate may count a sample that duplicates another sample's hash.

## Honest scope
This does not show the emulator failed to boot twice — window creation and disc-ID
reads were separate legs. It shows the screenshot leg cannot distinguish two boots,
which is exactly the kind of weak evidence the audit exists to catch.
