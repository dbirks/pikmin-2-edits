#!/usr/bin/env python3
"""Game-level input proof: find a screen that WAITS for input, show it reacts to
a button, then show a 4x3 tile moves with the stick LEFT and comes BACK with
RIGHT. Animation does not revert on command; a cursor/character does.

Why not whole-frame RMSE (ADR-0015): dwell deltas reached 0.113 with no input at
all (attract movie, fades) while two presses scored 0.000 — unattributable.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \
    uv run python scripts/crop_input_probe.py pikmin2.iso

Exit 0 = button-responsive screen found AND a tile reversed on stick LEFT/RIGHT.
Everything measured is kept in reports/runs/<ts>-crop-input/result.json.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PIKMINLAB_PORT", "38471"))
BASE = f"http://127.0.0.1:{PORT}"
SETTLE_MAX = float(os.environ.get("PROBE_SETTLE_MAX", "0.020"))
RESP_MULT = float(os.environ.get("PROBE_RESP_MULT", "3"))     # response vs dwell noise
REACT_FLOOR = 0.02
ATTEMPTS = int(os.environ.get("PROBE_ATTEMPTS", "10"))
SPACING = float(os.environ.get("PROBE_SPACING", "5"))
TILES = (4, 3)
SAMPLES = int(os.environ.get("PROBE_SAMPLES", "3"))
rec: dict = {"tiles_grid": TILES, "settle_max": SETTLE_MAX, "log": []}


def get(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(BASE + path,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def shot(tag: str) -> Path:
    return Path(get(f"/screenshot?name={tag}")["path"])


def rmse(a: Path, b: Path) -> float:
    r = subprocess.run(["magick", "compare", "-metric", "RMSE", "-resize", "320x240!",
                        str(a), str(b), "null:"], capture_output=True, text=True)
    try:
        return round(float(r.stderr.split()[0]) / 65535.0, 5)
    except (ValueError, IndexError):
        return -1.0


def tiles(p: Path) -> list[float]:
    """12 tile means 0..1: `-resize 4x3!` box-averages each tile."""
    out = subprocess.run(["magick", str(p), "-colorspace", "Gray",
                          "-resize", f"{TILES[0]}x{TILES[1]}!", "-depth", "8",
                          "-define", "txt:normalize=false", "txt:"],
                         capture_output=True, text=True)
    vals = [int(v) / 255.0 for v in re.findall(r"srgb\((\d+),", out.stdout)]
    return vals if len(vals) == TILES[0] * TILES[1] else []


def phase(tag: str, n: int = SAMPLES) -> list[dict]:
    rows = []
    for i in range(n):
        p = shot(f"{tag}{i}")
        rows.append({"phase": tag, "i": i, "path": str(p), "tiles": tiles(p),
                     "mean": round(sum(tiles(p)) / max(len(tiles(p)), 1), 4)})
        if i < n - 1:
            time.sleep(SPACING)
    rec["log"].extend(rows)
    return rows


def dwell(tag: str) -> tuple[float, Path]:
    a = phase(tag, 2)
    return rmse(Path(a[0]["path"]), Path(a[1]["path"])), Path(a[1]["path"])


def settle(tag: str, budget_s: float = 420) -> tuple[float, Path] | None:
    """Wait until the frame stops moving on its own (a screen that waits for us).
    Story cutscenes run for minutes and advance on A (skill: tap every ~7-12 s),
    so nudge with A between samples instead of giving up on the first quiet gap."""
    end = time.monotonic() + budget_s
    while time.monotonic() < end:
        d, last = dwell(tag)
        rec["settle_checks"] = rec.get("settle_checks", []) + [d]
        if 0 <= d < SETTLE_MAX:
            return d, last
        get("/input", {"button": "A", "hold": 0.8})   # skip cutscene beat
        time.sleep(SPACING)
    return None


def med(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs)//2 - 1] + xs[len(xs)//2]) / 2


def main() -> int:
    iso = (REPO / (sys.argv[1] if len(sys.argv) > 1 else "pikmin2.iso")).resolve()
    rec["iso"] = str(iso)
    rec["display"] = os.environ.get("DISPLAY")
    rec["video_backend"] = os.environ.get("PIKMINLAB_VIDEO_BACKEND")
    run = REPO / "reports" / "runs" / (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
                                       + "-crop-input")
    run.mkdir(parents=True, exist_ok=True)
    dlog = open(run / "serve.log", "w")
    daemon = subprocess.Popen(["uv", "run", "pikminlab", "serve", str(iso),
                               "--port", str(PORT), "--idle", "900"],
                              stdout=dlog, stderr=subprocess.STDOUT, text=True, cwd=REPO)
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                if get("/state").get("alive"):
                    break
            except Exception:
                pass
            if daemon.poll() is not None:
                break
            time.sleep(3)
        else:
            rec.update(status="FAIL", reason="daemon never became ready")
            return 2
        rec["state0"] = get("/state")

        # (1) find a settled screen that RESPONDS to a button
        found = None
        for attempt in range(ATTEMPTS):
            time.sleep(SPACING)
            d, last = dwell(f"a{attempt}")
            if not (0 <= d < SETTLE_MAX):
                get("/input", {"button": "START", "hold": 0.8})   # still animating: skip
                rec["log"].append({"attempt": attempt, "dwell": d, "action": "START(skip)"})
                continue
            for btn in ("A", "START"):
                get("/input", {"button": btn, "hold": 0.8})
                time.sleep(3)
                after = shot(f"a{attempt}_{btn}")
                resp = rmse(last, after)
                floor = max(RESP_MULT * d, REACT_FLOOR)
                rec["log"].append({"attempt": attempt, "dwell": d, "button": btn,
                                   "response_rmse": resp, "floor": round(floor, 4)})
                if resp > floor:
                    found = {"attempt": attempt, "button": btn, "dwell": d,
                             "response_rmse": resp}
                    break
            if found:
                break
        if not found:
            rec.update(status="BLOCKED", reason="no settled screen responded to A/START",
                       settle_checks=rec.get("settle_checks"))
            return 2
        rec["responsive_screen"] = found

        # (2) after that transition, get back to a settled screen, then stick A-B-A
        s = settle("s")
        if not s:
            rec.update(status="BLOCKED", reason="post-button scene never settled",
                       settle_checks=rec.get("settle_checks"))
            return 2
        rec["settled_again_rmse"] = s[0]
        base = phase("base")
        get("/stick", {"x": -24000, "y": 0}); time.sleep(0.8); get("/stick", {"x": 0, "y": 0})
        time.sleep(3)
        left = phase("left")
        get("/stick", {"x": 24000, "y": 0}); time.sleep(0.8); get("/stick", {"x": 0, "y": 0})
        time.sleep(3)
        right = phase("right")

        tsets = {k: [r["tiles"] for r in rec["log"] if r["phase"] == k and r["tiles"]]
                 for k in ("base", "left", "right")}
        for t in range(TILES[0] * TILES[1]):
            b, l, r = ([ts[t] for ts in tsets[k]] for k in ("base", "left", "right"))
            if not (b and l and r):
                continue
            noise = max(b) - min(b)
            floor = max(3 * noise, REACT_FLOOR)
            moved, back = abs(med(l) - med(b)), abs(med(r) - med(b))
            rec.setdefault("tile_report", []).append(
                {"tile": t, "base": round(med(b), 4), "dwell_noise": round(noise, 4),
                 "left_delta": round(moved, 4), "right_delta": round(back, 4),
                 "floor": round(floor, 4)})
        rev = next((row for row in rec.get("tile_report", [])
                    if row["left_delta"] > row["floor"] and row["right_delta"] <= row["floor"]),
                   None)
        rec["reversal"] = rev
        rec["status"] = "PASS" if rev else "FAIL"
        try:
            rec["disc_id"] = bytes.fromhex(get("/read", {"addr": "0x80000000",
                                                         "size": 6})["hex"]).decode("ascii", "replace")
        except Exception as exc:
            rec["disc_id"] = f"ERR {type(exc).__name__}"
        try:
            get("/stop")
        except Exception as exc:
            rec["stop_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        # SIGTERM is handled by serve (it SIGKILLs+reaps the emulator and frees
        # the pad); SIGKILL only as a last resort, then clean any exact stray.
        if daemon.poll() is None:
            daemon.terminate()
        try:
            daemon.wait(timeout=45)
        except subprocess.TimeoutExpired:
            daemon.kill()
            for pid in subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                      capture_output=True, text=True).stdout.split():
                subprocess.run(["/bin/kill", "-KILL", pid])
        time.sleep(2)
        rec["stray_pids"] = subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                          capture_output=True, text=True).stdout.split()
        if rec["stray_pids"]:
            rec["status"] = "FAIL"
        (run / "result.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps({k: rec.get(k) for k in ("status", "display", "video_backend",
                                                  "responsive_screen", "settled_again_rmse",
                                                  "reversal", "tile_report", "disc_id",
                                                  "stray_pids")}, indent=1))
        print("result:", run / "result.json")
    return 0 if rec.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
