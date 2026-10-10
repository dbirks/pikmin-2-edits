#!/usr/bin/env python3
"""Drive the documented new-game/Day-1 route (skill file) headless, then prove
stick input at game level by reversal: push LEFT, then RIGHT, and find a 4x3
tile whose mean moves beyond its own dwell noise and comes back.

Route (ADR-0011/0012 + skill, tuned for llvmpipe slowness — see ADR-0014):
  lit frame -> START (health warning) -> START (title) -> A (main menu BEGIN)
  -> A taps every ~9 s through story cutscenes -> Day 1.
A PNG is captured at every step so a human with eyes can audit the route; this
agent's model cannot view images (ADR-0015), so the assertion is tile statistics.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \
    uv run python scripts/day1_input_probe.py pikmin2.iso
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PIKMINLAB_PORT", "38471"))
BASE = f"http://127.0.0.1:{PORT}"
TILES = (4, 3)
SPACING = float(os.environ.get("PROBE_SPACING", "6"))
SAMPLES = int(os.environ.get("PROBE_SAMPLES", "3"))
rec: dict = {"tiles_grid": TILES, "steps": [], "log": []}


def get(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(BASE + path,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def shoot(name: str, after_s: float = 0.0) -> Path:
    if after_s:
        time.sleep(after_s)
    p = Path(get(f"/screenshot?name={name}")["path"])
    rec["steps"].append({"step": name, "path": str(p), "tiles": tile_means(p)})
    return p


def press(name: str, button: str, hold: float = 0.8, after_s: float = 0.0) -> None:
    get("/input", {"button": button, "hold": hold})
    rec["steps"].append({"step": name, "input": {"button": button, "hold": hold}})
    if after_s:
        time.sleep(after_s)


def pad_stick(name: str, x: int, y: int = 0, after_s: float = 0.0) -> None:
    get("/stick", {"x": x, "y": y})
    rec["steps"].append({"step": name, "input": {"stick": [x, y]}})
    if after_s:
        time.sleep(after_s)


def tile_means(p: Path) -> list[float]:
    out = subprocess.run(["magick", str(p), "-colorspace", "Gray",
                          "-resize", f"{TILES[0]}x{TILES[1]}!", "-depth", "8",
                          "-define", "txt:normalize=false", "txt:"],
                         capture_output=True, text=True)
    vals = [int(v) / 255.0 for v in re.findall(r"srgb\((\d+),", out.stdout)]
    return vals if len(vals) == TILES[0] * TILES[1] else []


def rmse(a: Path, b: Path) -> float:
    r = subprocess.run(["magick", "compare", "-metric", "RMSE", "-resize", "320x240!",
                        str(a), str(b), "null:"], capture_output=True, text=True)
    try:
        return round(float(r.stderr.split()[0]) / 65535.0, 5)
    except (ValueError, IndexError):
        return -1.0


def phase(tag: str) -> list[Path]:
    paths = []
    for i in range(SAMPLES):
        paths.append(Path(get(f"/screenshot?name={tag}{i}")["path"]))
        if i < SAMPLES - 1:
            time.sleep(SPACING)
    rec["log"].append({"phase": tag,
                       "rows": [{"path": str(p), "tiles": tile_means(p)} for p in paths]})
    return paths


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs)//2 - 1] + xs[len(xs)//2]) / 2


def main() -> int:
    iso = (REPO / (sys.argv[1] if len(sys.argv) > 1 else "pikmin2.iso")).resolve()
    run = REPO / "reports" / "runs" / (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
                                       + "-day1-input")
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

        shoot("boot", 60)                                       # wait for a lit frame
        press("warn_start", "START", after_s=18)                # HEALTH/HARM warning
        press("title_start", "START", after_s=18)               # title card -> main menu
        press("menu_a", "A", after_s=25)                        # BEGIN
        for i in range(10):                                     # story cutscenes
            press(f"cut_{i}", "A", after_s=9)
        shoot("ready", 12)

        base = phase("base")
        pad_stick("push_left", -24000, after_s=1.0)
        pad_stick("neutral_l", 0, after_s=3.5)
        left = phase("left")
        pad_stick("push_right", 24000, after_s=1.0)              # equal and opposite
        pad_stick("neutral_r", 0, after_s=3.5)
        right = phase("right")

        ph = {r["phase"]: r["rows"] for r in rec["log"]}
        for t in range(TILES[0] * TILES[1]):
            b = [r["tiles"][t] for r in ph["base"] if r["tiles"]]
            l = [r["tiles"][t] for r in ph["left"] if r["tiles"]]
            r_ = [r["tiles"][t] for r in ph["right"] if r["tiles"]]
            if not (b and l and r_):
                continue
            noise = max(b) - min(b)
            floor = max(3 * noise, 0.02)
            rec.setdefault("tile_report", []).append({
                "tile": t, "base": round(med(b), 4), "dwell_noise": round(noise, 4),
                "left_delta": round(abs(med(l) - med(b)), 4),
                "right_delta": round(abs(med(r_) - med(b)), 4), "floor": round(floor, 4)})
        moved = [x for x in rec.get("tile_report", []) if x["left_delta"] > x["floor"]]
        reversed_tiles = [x for x in rec.get("tile_report", [])
                          if x["left_delta"] > x["floor"] and x["right_delta"] <= x["floor"]]
        rec["moved_tiles"] = moved
        rec["reversal_tiles"] = reversed_tiles
        rec["frame_rmse"] = {"base_vs_left": rmse(base[-1], left[-1]),
                            "base_vs_right": rmse(base[-1], right[-1])}
        rec["status"] = "PASS" if reversed_tiles else ("PARTIAL" if moved else "FAIL")
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
        print(json.dumps({k: rec.get(k) for k in ("status", "moved_tiles", "reversal_tiles", "tile_report",
                                                  "frame_rmse", "disc_id", "stray_pids")}, indent=1))
        print("result:", run / "result.json")
    return 0 if rec.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
