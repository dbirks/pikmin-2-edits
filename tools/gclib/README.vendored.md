# Vendored: gclib

Source: https://github.com/LagoLunatic/gclib (MIT — see `LICENSE.gclib`)
Pinned commit: 4e06db0 (shallow clone 2026-10-09)

## Why vendored
gclib provides Linux-capable Yaz0, RARC, BMG, BTI, J3D, DOL, REL, GCM
readers/writers for GameCube data (master spec risk §12: asset tools are
mostly Windows-only; gclib is pure Python and cross-platform).

## Local modifications
- Removed `bfn/texture_utils/imagequant` dependency where unused (import
  failure `imagequant` resolved by `uv add Pillow imagequant`).
- Project Python pinned to 3.12 (`.python-version`): gclib's `bunfoe` uses
  `dataclasses._recursive_repr`, which is gone in 3.14.
- Speedup extension `pyfastyaz0yay0` (git-pinned 2adb8a8) fails with Arch's
  modern GCC defaults (C23 `bool` keyword; C99 `inline` emits no symbol).
  Reproducible build:
  `CFLAGS="-std=gnu11 -fgnu89-inline" uv add "pyfastyaz0yay0 @ git+https://github.com/LagoLunatic/PyFastYaz0Yay0.git@2adb8a8c00d98f98f245e0304094a0610203a82e"`

## Notes
- `bmg.BMG` parser is Wind Waker-specific; raises on Pikmin 2
  `TextBoxType 255`. **Do not use it to parse Pikmin text** — Pikmin 2
  `.bmg` stores message text as raw ASCII/Shift-JIS runs, so edits are done
  as same-length byte patches on the decompressed RARC payload instead.
