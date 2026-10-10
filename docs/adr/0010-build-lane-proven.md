# ADR-0010: Data build lane proven: patch -> repack -> boot

**Date:** 2026-10-09
**Status:** accepted
**Context:** Master spec work order 9 demands separating asset-compiler
success from gameplay success for any modification.
**Decision / evidence:** `pikminlab.buildlane` implements Lane A mechanics:
1. Same-length byte patch of the ONE unique occurrence of
   "Welcome to Challenge Mode! Find" inside decompressed
   `pikmin2.bmg` @17385 in `mesRes_eng.szs` (11 bytes changed,
   structure untouched; enforced uniqueness + equal length by code).
2. `Yaz0.compress` (fast backend `pyfastyaz0yay0`, build flags per
   README.vendored) -> repacked szs -> `pyisotools` rebuild ->
   `builds/pikmin2-modified.iso` (1,459,978,240 B, sha256 9dd74856…).
3. Modified ISO cold-boots in the isolated profile; live RAM read at
   0x80000000 returns GPVE01; capture saved
   (`reports/runs/modified-boot-evidence/modified_title.png`).
**Explicitly NOT yet claimed:** in-game observation of the patched string
(Challenge Mode is locked; reaching it is gameplay-E2E work under P3/G3
input traces, or a main-menu string chosen for the next experiment).
**Consequences:** STATIC_PASSED -> BUILT -> DOLPHIN_BOOTED state-machine
rung is now real automation. The deliberate-fault test (G4) can reuse the
same lane with a broken-reference patch.
