# ADR-0005: Source image is NKit-trimmed; repack lane needs standardization

**Date:** 2026-10-09
**Status:** accepted
**Context:** `dolphin-tool verify` on the owner ISO (SHA-256
`5388b54a…db661a`, 995,557,376 bytes) reports Low-severity findings: the
image is in **NKit format** (trimmed, unusual size ~0.93 GB vs full ~1.4 GB
GC disc). Dolphin emulates NKit transparently, but disc-repack tooling
(pyisotools), byte-exact round-trip proofs, movie/NetPlay compatibility, and
any future redump comparison all assume a standard dump layout.
**Decision:**
1. Accept this image for G0 baseline boot, driver work, and read-only
   extraction (Dolphin handles NKit natively).
2. Before any P2 ISO **repack** claims, convert to a standardized full
   GameCube image (NKit recovery, e.g. `libnkit`-based nkit2gcm applied to a
   standard template) and re-fingerprint; or prove the extracted-directory
   boot lane (PikminTBK "Extract Entire Disc" workflow) as the primary
   dev loop and treat ISO export as a later packaging step.
3. Do not call any round-trip "byte-for-byte" against this image; the ladder
   (§15.3) starts at the standardized copy.
**Evidence:** `dolphin-tool header`: GPVE01, Revision 0, NTSC-U/USA.
`dolphin-tool verify`: CRC32 3541416b, SHA1 c5e9fe751731da3db7a103272e6f05eee90fe6e9,
"Problems Found: Yes — NKit format" (2 Low findings, 2026-10-09).
**Consequences:** ADR-0002's region facts stand. P2 gains one extra
prerequisite (standardization spike). Nothing in G0/G1 is blocked. If the
owner can re-rip a standard dump later, prefer it; never demand console
hardware from the owner as a blocker (spec §3).
