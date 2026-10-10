# ADR-0009: Vendored gclib as the asset-codec stack; Pikmin text edits via same-length byte patch

**Date:** 2026-10-09
**Status:** accepted
**Context:** P2's asset pipeline needs a Linux-capable YAZ0/RARC/BMG/BTI stack.
The Windows-centric PikminTKB tools are unsuitable to automate headlessly on
this Arch host.
**Decision:**
1. Vendor `gclib` (MIT, LagoLunatic) into `tools/gclib`, pinned to commit
   `4e06db0`, with provenance in `tools/gclib/README.vendored.md`. Its Yaz0
   and RARC codecs are pure Python and cross-platform, closing master-spec
   risk §12 for archive handling.
2. **Project Python is pinned to 3.12** (`.python-version`): gclib's
   `bunfoe` uses the removed `dataclasses._recursive_repr` (gone in 3.14).
   Recorded so future sessions do not "fix" this by editing vendored code.
3. `bmg.BMG` is Wind Waker-specific and raises on Pikmin 2's
   `TextBoxType 255`. Do **not** use it to parse Pikmin text. Pikmin 2 `.bmg`
   message strings are raw ASCII/Shift-JIS in the decompressed RARC payload,
   so the single-asset G2 edit is done as a **same-length byte patch** of the
   decompressed `pikmin2.bmg` inside the RARC, then re-Yaz0-compressed and
   repacked. This keeps archive structure intact and needs no BMG parser.
**Evidence:** `mesRes_eng.szs` = YAZ0(0x3b1c0 -> RARC) with entries
`pikmin2.bmc`(1088) + `pikmin2.bmg`(240768); `Pikmin` ASCII count 237,
`Challenge` 11; cave/otakara configs confirmed plain-text (CRLF, Shift-JIS
comment fields). BMG parse via gclib raised `ValueError: 255 is not a valid
TextBoxType` as expected.
**Consequences:** Asset-codec blocker cleared in Python. Next experiment is
the G2 single-asset in-game observation (cheeky same-length treasure-name
edit). Vendored tree adds ~490 KB to the repo.
