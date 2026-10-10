"""Numeric frame oracle — how this project judges pixels without eyes.

ADR-0015/0017: the agent session on the headless host has no vision model, and
whole-frame RMSE turned out to be a bad input oracle (the game animates itself).
So frame judgement is centralised here and expressed as statistics a human can
audit: per-tile means, lit-ness, and RMSE against a measured noise band.
"""
from __future__ import annotations
import re, subprocess
from pathlib import Path

_PIX = re.compile(r"(?:gray|srgb|rgb)\(\s*(\d+)")


def _magick(*args: str) -> str:
    return subprocess.run(["magick", *args], capture_output=True, text=True)


def tile_means(path: Path, grid: tuple[int, int] = (4, 3)) -> list[float]:
    """Mean luminance per tile: `-resize GxH!` box-averages each tile.

    History: the first version matched only `srgb(`, but with `-colorspace Gray`
    ImageMagick emits `gray(`, so every tile list came back empty and a probe
    silently reported FAIL with no tile_report at all (ADR-0017). Any empty
    result is now a hard error, not a quiet [].
    """
    r = _magick(str(path), "-colorspace", "Gray", "-resize", f"{grid[0]}x{grid[1]}!",
                "-depth", "8", "-define", "txt:normalize=false", "txt:")
    vals = [int(v) / 255.0 for v in _PIX.findall(r.stdout)]
    if len(vals) != grid[0] * grid[1]:
        raise ValueError(f"tile parse failed for {path}: got {len(vals)} of "
                         f"{grid[0]*grid[1]} (stderr: {r.stderr.strip()[:120]})")
    return vals


def stats(path: Path) -> dict:
    r = _magick("identify", "-format", "%[fx:mean] %k %[fx:w]x%[fx:h]", str(path))
    try:
        mean, colors, size = r.stdout.split()
    except ValueError:
        return {"mean": None, "colors": None, "size": None}
    return {"mean": round(float(mean), 4), "colors": int(colors), "size": size}


def lit(path: Path, min_mean: float = 0.02, min_colors: int = 32) -> bool:
    """A rendered frame, as opposed to a black/idle framebuffer (mean 0, 1 colour)."""
    s = stats(path)
    return bool(s["mean"]) and s["mean"] >= min_mean and s["colors"] >= min_colors


def rmse(a: Path, b: Path, resize: str = "320x240!") -> float:
    r = _magick("compare", "-metric", "RMSE", "-resize", resize, str(a), str(b), "null:")
    try:
        return round(float(r.stderr.split()[0]) / 65535.0, 5)
    except (ValueError, IndexError):
        return -1.0


def median(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs)//2 - 1] + xs[len(xs)//2]) / 2


def reversal_report(base: list[Path], moved: list[Path], returned: list[Path],
                    grid: tuple[int, int] = (4, 3), floor: float = 0.02) -> list[dict]:
    """Per tile: did it move beyond its own dwell noise, and come back?

    Only meaningful on a screen that waits for input — see ADR-0015 for why
    animated scenes make this meaningless (dwell noise there reaches 0.11)."""
    b = [tile_means(p, grid) for p in base]
    m = [tile_means(p, grid) for p in moved]
    r_ = [tile_means(p, grid) for p in returned]
    out = []
    for t in range(grid[0] * grid[1]):
        bt, mt, rt = ([s[t] for s in b], [s[t] for s in m], [s[t] for s in r_])
        noise = max(bt) - min(bt)
        f = max(3 * noise, floor)
        out.append({"tile": t, "base": round(median(bt), 4), "dwell_noise": round(noise, 4),
                    "moved_delta": round(abs(median(mt) - median(bt)), 4),
                    "returned_delta": round(abs(median(rt) - median(bt)), 4),
                    "floor": round(f, 4),
                    "moved": abs(median(mt) - median(bt)) > f,
                    "reversed": abs(median(rt) - median(bt)) <= f})
    return out
