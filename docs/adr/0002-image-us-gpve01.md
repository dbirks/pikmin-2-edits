# ADR-0002: Working image is US retail GPVE01 (rev 0x00)

**Date:** 2026-10-09
**Status:** accepted (dolphin-tool confirmation completed 2026-10-09; see amendment)
**Context:** Spec forbade assuming a region. Header inspection of the
owner-provided ISO resolved the question before any tooling was installed.
**Decision:** All build/asset assumptions target US retail `GPVE01`:
`projectPiki/pikmin2` `python configure.py --version gpve01 --non-matching`,
`orig/GPVE01/sys/main.dol`, and US-relative paths verified against the actual
extracted tree.
**Evidence:**
- Path: `/home/david/dev/pikmin-2-edits/pikmin2.iso` (gitignored, immutable)
- Size: 995,557,376 bytes
- SHA-256: `5388b54a9c2d156c94bcfa80acd53b513288dc17e88c97a1edfb57ad25db661a`
- Header bytes: disc ID `GPVE01`, revision byte `0x00`, internal name
  "PIKMIN2 for GAMECUBE"
**Consequences:** Region branching is deferred, not deleted — every tool still
takes an explicit game-ID parameter and must fail loudly on mismatch. Open
item: overlay `dolphin-tool header/verify` digests (and optionally redump
hashes) once the package is installed, and record them as an amendment here.

**Amendment (same day):** `dolphin-tool header` → GPVE01, Revision 0,
NTSC-U/USA. `dolphin-tool verify` → CRC32 3541416b, SHA1
c5e9fe751731da3db7a103272e6f05eee90fe6e9, flagged **NKit-trimmed format**
(see ADR-0005 for repack-lane consequences).
