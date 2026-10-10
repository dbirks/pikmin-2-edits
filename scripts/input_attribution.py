#!/usr/bin/env python3
"""Does ANY input reach the game on this headless host? (t5 blocker diagnostic)

Why this exists: attempts 1-3 of the E2E lane showed the Day-1 spawn float struct
present and full-colour scenes, but NO world-scale struct ever moved under stick
input, and no memory-card file was ever written. That is consistent with a far more
basic failure than a broken cave route: the observed scene changes may have been the
game self-progressing through the health warning -> title -> ATTRACT DEMO (which is
recorded forest gameplay, so it explains the spawn literal perfectly), with our pad
delivering nothing. ADR-0017 read a 23 -> 97,901 colour change as proof of input;
on an attract cycle that inference is unsound, and this script settles it.

Method: A/B/A reversal on a screen that WAITS for input (main menu cursor), which is
the only frame-difference oracle ADR-0015 accepts as valid. Also tests the window
focus hypothesis (Xvfb may hand focus elsewhere) by re-activating the emulator
window with xdotool between captures, and reports Dolphin's own controller log.

  PIKMINLAB_VIDEO_BACKEND=OpenGL PIKMINLAB_PORT=38481 \\
    xvfb-run -a -s "-screen 0 1280x960x24" uv run python scripts/input_attribution.py builds/lab-cave.iso
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import frames  # noqa: E402

PORT = int(os.environ.get("PIKMINLAB_PORT", "38481"))
BASE = f"http://127.0.0.1:{PORT}"
FULL = 24000
rec: dict = {"port": PORT, "shots": [], "trace": []}


def get(path: str, body: dict | None = None, timeout: int = 90) -> dict:
    req = urllib.request.Request(BASE + path,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def shoot(name: str, after_s: float = 0.0) -> dict:
    if after_s:
        time.sleep(after_s)
    p = Path(get(f"/screenshot?name={name}")["path"])
    row = {"step": name, "path": str(p), "stats": frames.stats(p), "lit": frames.lit(p),
           "tiles": frames.tile_means(p)}
    rec["shots"].append(row)
    print(f"  {name:22} {row['stats']} lit={row['lit']}", flush=True)
    return row


def btn(name, button, hold=0.6, after_s=0.0):
    get("/input", {"button": button, "hold": hold})
    rec["trace"].append({"step": name, "button": button, "hold": hold})
    if after_s:
        time.sleep(after_s)


def stick(name, x, y, hold=0.3):
    get("/stick", {"x": x, "y": y})
    rec["trace"].append({"step": name, "stick": [x, y], "hold": hold})
    time.sleep(hold)
    get("/stick", {"x": 0, "y": 0})
    time.sleep(0.6)


def focus_window(wid: str) -> str:
    """Attempt the focus repair: activate + focus the emulator window."""
    out = {}
    for cmd in (["xdotool", "windowactivate", "--sync", wid], ["xdotool", "windowfocus", "--sync", wid]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        out[cmd[1]] = {"rc": r.returncode, "err": r.stderr.strip()[:80]}
    rec.setdefault("focus_attempts", []).append(out)
    return json.dumps(out)


def compare(a: dict, b: dict, label: str) -> dict:
    rep = frames.reversal_report([a["path"]], [b["path"]], [a["path"]])
    moved = [r["tile"] for r in rep if r["moved"]]
    rec["comparisons"].append({"label": label, "rmse": frames.rmse(Path(a["path"]), Path(b["path"])),
                               "moved_tiles": moved,
                               "dwell_noise_max": max(r["dwell_noise"] for r in rep),
                               "delta_tiles": {r["tile"]: r["moved_delta"] for r in rep if r["moved_delta"] > 0.005}})
    print(f"  {label:22} rmse={rec['comparisons'][-1]['rmse']} moved_tiles={moved}"
          f" max_dwell_noise={rec['comparisons'][-1]['dwell_noise_max']}", flush=True)
    return rec["comparisons"][-1]


def card_state() -> dict:
    d = REPO / "runtime/dolphin-agent/GC/USA/Card A"
    return {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(d.glob("*")) if p.is_file()}


def main() -> int:
    iso = (REPO / (sys.argv[1] if len(sys.argv) > 1 else "builds/lab-cave.iso")).resolve()
    rec["iso"] = str(iso)
    run = REPO / "reports" / "runs" / (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
                                       + "-input-attribution")
    run.mkdir(parents=True)
    rec["comparisons"] = []
    card0 = card_state()
    dlog = open(run / "serve.log", "w")
    daemon = subprocess.Popen(["uv", "run", "pikminlab", "serve", str(iso), "--port", str(PORT),
                               "--idle", "600"], stdout=dlog, stderr=subprocess.STDOUT, cwd=REPO)
    code = 1
    try:
        for _ in range(100):
            try:
                if get("/state", timeout=10).get("alive"):
                    break
            except Exception:
                pass
            time.sleep(3)
        st = get("/state", timeout=20)
        rec["disc_id"] = st.get("disc_id")
        wid = str(st.get("window"))
        rec["window"] = wid

        # PHASE 1: does a button move the game out of its boot screens? Capture
        # densely so a self-progressing screen is distinguishable from a press.
        a0 = shoot("p1_t0_no_input", 60)
        time.sleep(12)
        a1 = shoot("p1_t1_still_no_input")          # control: self-progress WITHOUT input
        cmp_self = compare(a0, a1, "no_input_12s_gap")
        btn("p1_start", "START", after_s=4)
        a2 = shoot("p1_t2_after_start")
        compare(a1, a2, "start_press")
        btn("p1_start2", "START", after_s=6)
        a3 = shoot("p1_t3_after_start2")
        btn("p1_a", "A", after_s=6)
        a4 = shoot("p1_t4_after_a")

        # PHASE 2: main-menu A/B/A reversal on the stick (the only valid frame oracle)
        m0 = shoot("p2_menu_a", 4)
        focus_window(wid)
        stick("p2_stick_left", -FULL, 0, hold=0.4)
        m1 = shoot("p2_menu_b")
        stick("p2_stick_right", FULL, 0, hold=0.4)
        m2 = shoot("p2_menu_c")
        cmp2 = compare(m0, m1, "menu_stick_left")
        cmp3 = compare(m1, m2, "menu_stick_right_return")

        # PHASE 3: dwell baseline on the menu, to bound the noise floor
        d0 = shoot("p3_dwell0", 3)
        d1 = shoot("p3_dwell1", 3)
        cmp4 = compare(d0, d1, "menu_dwell_3s")

        code = 0
    finally:
        try:
            get("/stop", {}, timeout=30)
        except Exception as ex:                       # noqa: BLE001
            rec["stop_error"] = str(ex)[:120]
        subprocess.run(["/bin/kill", "-KILL", str(daemon.pid)], capture_output=True)
        rec["stray_pids"] = subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                          capture_output=True, text=True).stdout.split()
        rec["card_end"] = {k: list(v) for k, v in card_state().items()}
        rec["card_changed"] = card_state() != card0
        rec["card_before"] = {k: list(v) for k, v in card0.items()}
        (run / "result.json").write_text(json.dumps(rec, indent=2, default=str))
        print(json.dumps({"comparisons": rec["comparisons"], "card_changed": rec["card_changed"],
                          "stray_pids": rec["stray_pids"], "run": str(run)}, default=str)[:1400])
    return code


if __name__ == "__main__":
    sys.exit(main())
