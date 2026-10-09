# ADR-0008: Data pipeline works end-to-end; pyisotools quirks documented

**Date:** 2026-10-09
**Status:** accepted
**Context:** P2 requires extract -> modify -> repack -> boot -> observe, with
honest accounting of how the tool behaves on our NKit source (ADR-0005).
**Decision / findings:**
1. `pyisotools 2.4.7` (`uv run python -m pyisotools IMG E --dest DIR`) extracts
   the NKit image fine: 2774 files, `sys/main.dol` 5,209,600 B, full `files/`
   tree including `pikmin2UP.MAP` (retail symbol map — promising for G1
   state hooks without building the decomp).
2. **Quirk:** for builds, `--dest` is resolved *relative to the extracted root*
   (`iso.py: build() -> Path(self.root / fmtpath)`), so `B --dest builds/x.iso`
   writes inside the tree; we relocate afterward. Wrapper must hide this.
3. Extract+rebuild produces a **full-size 1,459,978,240-byte** image
   (NKit padding zero-filled). It boots; `pikminlab` session reads
   `GPVE01` at `0x80000000` from the rebuilt disc's live RAM.
4. `dolphin-tool verify` on the rebuilt ISO still warns "NKit format"
   (Low) because of null padding — cosmetically noisy, functionally fine.
   The byte-for-byte ladder rung (b) is therefore "semantic inventory
   equality", not identical digests; new SHA1 `c26fd14e…` recorded as the
   lab build baseline digest.
**Evidence:** extract rc=0 tree in `workspace/extracted` (gitignored);
rebuilt `builds/pikmin2-lab.iso` boots with DISC_ID GPVE01 via context-managed
session, `no-strays`; verify output above.
**Consequences:** G2 essentially proven pending the one-modification-observed
rung (change one text/asset, see it in game). Next experiment uses MAP/symbol
lookups or a BMG string edit. ADR-0005's "standardization prerequisite" is
satisfied implicitly by the pipeline itself.
