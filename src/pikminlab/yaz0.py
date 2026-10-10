"""Yaz0 (Nintendo) (de)compression, pure Python, for GC/Wii .szs payloads.

Round-trip identity is the contract: decode(encode(x)) == x and, for
unchanged payloads, encode(decode(y)) is byte-identical to y when the
encoder reproduces the classic greedy matcher. We only *guarantee* the
self-consistency direction and validate against Dolphin at boot time.
"""
from __future__ import annotations
import struct

MAGIC = b"Yaz0"


def decode(data: bytes) -> bytes:
    if data[:4] != MAGIC:
        raise ValueError("not Yaz0")
    out_size = struct.unpack_from(">I", data, 4)[0]
    src = 16
    dst = bytearray()
    while len(dst) < out_size:
        if src >= len(data):
            raise ValueError("truncated Yaz0 stream")
        group = data[src]; src += 1
        for bit in range(8):
            if len(dst) >= out_size:
                break
            if group & 0x80:          # literal
                dst.append(data[src]); src += 1
            else:                     # back-reference
                pair = struct.unpack_from(">H", data, src)[0]; src += 2
                length = (pair >> 12) + 3
                if length == 18:      # extended length follows
                    length = data[src] + 0x12; src += 1
                offset = (pair & 0xFFF) + 1
                start = len(dst) - offset
                for i in range(length):
                    dst.append(dst[start + i])
            group <<= 1
    return bytes(dst[:out_size])


def encode(raw: bytes) -> bytes:
    """Classic greedy LZ77 + 8-bit group control, Yaz0 framing."""
    out = bytearray()
    # token buffer: list of ('lit', byte) | ('ref', off, len)
    tokens: list[tuple] = []
    i, n = 0, len(raw)
    WINDOW, MINDIST, MAXMATCH = 0x1000, 1, 0xF + 3
    while i < n:
        best_len, best_off = 0, 0
        start = max(0, i - WINDOW)
        end = min(n, i + MAXMATCH)
        for cand in range(start, i):
            l = 0
            while l < end - i and raw[cand + l] == raw[i + l]:
                l += 1
            if l >= 3 and l > best_len:
                best_len, best_off = l, i - cand
                if best_len == MAXMATCH:
                    break
        if best_len >= 3:
            tokens.append(("ref", best_off, best_len))
            i += best_len
        else:
            tokens.append(("lit", raw[i]))
            i += 1

    body = bytearray()
    for chunk_start in range(0, len(tokens), 8):
        group = tokens[chunk_start:chunk_start + 8]
        ctl = 0
        payload = bytearray()
        for k, tok in enumerate(group):
            if tok[0] == "lit":
                ctl |= 0x80 >> k
                payload.append(tok[1])
            else:
                _, off, ln = tok
                if ln <= 0xF:
                    payload += struct.pack(">H", ((ln - 3) << 12) | (off - 1))
                else:
                    payload += struct.pack(">H", 0xF000 | (off - 1))
                    payload.append(ln - 0x12)
        body.append(ctl); body += payload

    return MAGIC + struct.pack(">I", len(raw)) + b"\x00\x00\x00\x00\x00\x00\x00\x00" + bytes(body)
