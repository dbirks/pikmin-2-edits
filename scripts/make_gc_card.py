#!/usr/bin/env python3
"""Generate a blank formatted GC memory card .raw compatible with Dolphin.

Derived from dolphin-emu GCMemcard.h/cpp Format():
  block0 Header, block1+2 Directory, block3+4 BlockAlloc, remainder 0xFF.
BLOCK_SIZE=0x2000; a "2043-block" card uses size_mbits field 0x80 and file
size 2048*0x2000 = 16 MB. Checksums are additive over big-endian u16 words
plus the inverse-sum, stored big-endian at block tail (see memcard spec).
"""
from __future__ import annotations
import struct, sys
from datetime import datetime, timezone
from pathlib import Path

BLOCK = 0x2000
NBLOCKS = 2048
SIZE_MBITS_FIELD = 0x80
MC_FST_BLOCKS = 5


def checksums(data: bytes):
    s = 0
    inv = 0
    for i in range(0, len(data) & ~1, 2):
        w = int.from_bytes(data[i:i+2], "big")
        s = (s + w) & 0xFFFF
        inv = (inv + (w ^ 0xFFFF)) & 0xFFFF
    return s, inv


def lcg(seed: int) -> int:
    return ((seed * 0x41C64E6D + 0x3039) >> 16) & 0xFFFFFFFFFFFFFFFF


def header_block(flash_id: bytes, format_time: int) -> bytes:
    b = bytearray(b"\xFF" * BLOCK)
    # HeaderData
    rand = format_time
    serial = bytearray(12)
    for i in range(12):
        rand = lcg(rand)
        serial[i] = (flash_id[i] + rand) & 0xFF
        rand = lcg(rand) & 0x7FFF
    b[0x00:0x0C] = serial
    b[0x0C:0x14] = struct.pack(">Q", format_time)
    b[0x14:0x18] = struct.pack("<I", 0)          # m_sram_bias (host-order in Dolphin struct on LE)
    b[0x18:0x1C] = struct.pack(">I", 1)          # sram_language = English
    b[0x1C:0x20] = struct.pack("<I", 0)          # dtv_status
    b[0x20:0x22] = struct.pack(">H", 0)          # device_id (slot A)
    b[0x22:0x24] = struct.pack(">H", SIZE_MBITS_FIELD)
    b[0x24:0x26] = struct.pack(">H", 0)          # encoding: Windows-1252 (US)
    b[0x1FA:0x1FC] = struct.pack(">H", 0xFFFF)   # update counter
    s, inv = checksums(bytes(b[0x00:0x1FC]))
    b[0x1FC:0x1FE] = struct.pack(">H", s)
    b[0x1FE:0x200] = struct.pack(">H", inv)
    return bytes(b)


def directory_block() -> bytes:
    b = bytearray(b"\xFF" * BLOCK)
    # 127 empty DEntry slots stay 0xFF (invalid = free). update counter @0x1FFA
    b[0x1FFA:0x1FFC] = struct.pack(">h", 0)
    s, inv = checksums(bytes(b[0x00:0x1FFC]))
    b[0x1FFC:0x1FFE] = struct.pack(">H", s)
    b[0x1FFE:0x2000] = struct.pack(">H", inv)
    return bytes(b)


def bat_block(free_blocks: int) -> bytes:
    b = bytearray(b"\x00" * BLOCK)
    s, inv = checksums_placeholder(b)            # checksum computed over data AFTER own slot
    b[0x04:0x06] = struct.pack(">h", 0)          # update counter
    b[0x06:0x08] = struct.pack(">H", free_blocks)
    b[0x08:0x0A] = struct.pack(">H", 4)          # last allocated block
    # alloc map (0x0A..) all zero = none allocated; checksum covers [0x0A, BLOCK)
    s, inv = checksums(bytes(b[0x0A:BLOCK]))
    b[0x00:0x02] = struct.pack(">H", s)
    b[0x02:0x04] = struct.pack(">H", inv)
    return bytes(b)


def checksums_placeholder(_b):  # noqa: ANN001 - symmetry helper
    return 0, 0


def make_folder_card(card_dir: Path) -> int:
    """Modern Dolphin auto memory cards are DIRECTORIES containing an
    MC_SYSTEM_AREA header block (GCMemcardDirectory.cpp MC_HDR). Without it
    the card reports 0 usable blocks and game writes fail silently."""
    fmt_time = (datetime.now(timezone.utc) -
                datetime(2000, 1, 1, tzinfo=timezone.utc)).seconds * 10**9 // 32
    flash_id = bytes([0x00, 0x01, 0x00, 0x81, 0x49, 0x44, 0x00, 0x00,
                      0x00, 0x00, 0x00, 0x00])
    card_dir.mkdir(parents=True, exist_ok=True)
    hdr = card_dir / "MC_SYSTEM_AREA"
    hdr.write_bytes(header_block(flash_id, fmt_time))
    bat = card_dir / "MC_ALLOC_1"   # BAT persistence varies; header is the critical one
    print(f"wrote {hdr} ({hdr.stat().st_size} bytes)")
    return 0


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               "runtime/dolphin-agent/GC/USA/Card A")
    if out.is_dir() or sys.argv[1:2] == ["--folder"] or out.name == "Card A":
        if sys.argv[1:2] == ["--folder"]:
            return make_folder_card(Path(sys.argv[2]))
        return make_folder_card(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fmt_time = (datetime.now(timezone.utc) -
                datetime(2000, 1, 1, tzinfo=timezone.utc)).seconds * 10**9 // 32
    flash_id = bytes([0x00, 0x01, 0x00, 0x81, 0x49, 0x44, 0x00, 0x00,
                      0x00, 0x00, 0x00, 0x00])
    blocks = [header_block(flash_id, fmt_time),
              directory_block(), directory_block(),
              bat_block(NBLOCKS - MC_FST_BLOCKS),
              bat_block(NBLOCKS - MC_FST_BLOCKS)]
    tail = b"\xFF" * (BLOCK * (NBLOCKS - 5))
    out.write_bytes(b"".join(blocks) + tail)
    print(f"wrote {out} ({out.stat().st_size} bytes, "
          f"expect {BLOCK*NBLOCKS})")
    return 0 if out.stat().st_size == BLOCK * NBLOCKS else 1


if __name__ == "__main__":
    sys.exit(main())
