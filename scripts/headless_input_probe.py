#!/usr/bin/env python3
"""Headless controller-input proof, single session, dwell/press alternation.

Cross-run A/B is not trustworthy under software rendering: wall-clock scene
mapping jitters with frame rate, so a divergence could be timing, not input.
Instead, inside ONE session we alternate DWELL (no input; measures the scene's
own animation/pulse noise floor) with PRESS (one GC button; must produce a
change well above that floor to count as input landing).

  xvfb-run -a -s "-screen 0 1280x960x24" PIKMINLAB_VIDEO_BACKEND=OpenGL \
    uv run python scripts/headless_input_probe.py pikmin2.iso

Exit 0 only if presses move the scene beyond the measured dwell noise.
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PIKMINLAB_PORT", "38471"))
DWELL_S = float(os.environ.get("PROBE_DWELL", "8"))
CYCLES = int(os.environ.get("PROBE_CYCLES", "4"))
BUTTONS = os.environ.get("PROBE_BUTTONS", "START,START,A,A").split(",")


def stats(p: Path) -> dict:
    out = subprocess.run(["magick", "identify", "-format", "%[fx:mean] %k", str(p)],
                         capture_output=True, text=True)
    try:
        mean, colors = out.stdout.split()
        return {"mean": round(float(mean), 4), "colors": int(colors)}
    except ValueError:
        return {"mean": None, "colors": None}


def rmse(a: Path, b: Path) -> float:
    r = subprocess.run(["magick", "compare", "-metric", "RMSE", "-resize", "320x240!",
                        str(a), str(b), "null:"], capture_output=True, text=True)
    try:
        return round(float(r.stderr.split()[0]) / 65535.0, 5)
    except (ValueError, IndexError):
        return -1.0


def drive(act: str, **kw) -> dict:
    if act == "state":
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/state")
    elif act == "shot":
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/screenshot?name={kw['name']}")
    else:
        body = ({"button": kw["button"], "hold": kw.get("hold", 0.8)} if act == "input" else
                {"addr": kw["addr"], "size": kw["size"]} if act == "read" else {})
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/{act}",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main() -> int:
    iso = (REPO / sys.argv[1] if len(sys.argv) > 1 else REPO / "pikmin2.iso").resolve()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run = REPO / "reports" / "runs" / f"{ts}-input-ab"
    run.mkdir(parents=True, exist_ok=True)
    rec = {"iso": str(iso), "display": os.environ.get("DISPLAY"), "port": PORT,
           "video_backend": os.environ.get("PIKMINLAB_VIDEO_BACKEND"), "events": []}

    # NOTE: `uv run` leaves the pikminlab process reparented, so its stdout pipe
    # hits EOF immediately — readiness must be polled over HTTP, not read from
    # the pipe (a pipe read made the first version of this probe report
    # "daemon never served" while the daemon was in fact up and serving).
    dlog = open(run / "serve.log", "w")
    daemon = subprocess.Popen(
        ["uv", "run", "pikminlab", "serve", str(iso), "--port", str(PORT), "--idle", "400"],
        stdout=dlog, stderr=subprocess.STDOUT, text=True, cwd=REPO)
    try:
        served, state = None, None
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                st = drive("state")
                if st.get("alive"):
                    served, state = st, st
                    break
            except Exception:
                pass
            if daemon.poll() is not None:
                break
            time.sleep(3)
        if not served:
            dlog.flush()
            rec.update(status="FAIL", reason="daemon never became ready",
                       serve_log_tail="".join(open(run / "serve.log").readlines()[-8:]))
        else:
            rec["state0"] = state
            prev = None
            for cyc in range(CYCLES):
                for tick in range(2):                    # dwell: two shots, no input
                    name = f"c{cyc}dwell{tick}"
                    d = drive("shot", name=name)
                    cur = Path(d["path"])
                    ev = {"kind": "dwell", "cycle": cyc, "shot": name,
                          "path": str(cur), **stats(cur)}
                    if prev is not None:
                        ev["rmse_vs_prev"] = rmse(prev, cur)
                    rec["events"].append(ev)
                    prev = cur
                    time.sleep(DWELL_S)
                btn = BUTTONS[cyc % len(BUTTONS)]
                drive("input", button=btn, hold=0.8)
                name = f"c{cyc}after_{btn.lower()}"
                time.sleep(3)                             # let the screen react
                d = drive("shot", name=name)
                cur = Path(d["path"])
                ev = {"kind": "press", "cycle": cyc, "button": btn, "shot": name,
                      "path": str(cur), **stats(cur)}
                if prev is not None:
                    ev["rmse_vs_prev"] = rmse(prev, cur)
                rec["events"].append(ev)
                prev = cur
            try:
                rec["disc_id"] = bytes.fromhex(drive("read", addr="0x80000000",
                                                     size=6)["hex"]).decode("ascii", "replace")
            except Exception as exc:
                rec["disc_id"] = f"ERR {type(exc).__name__}"
            try:
                drive("stop")
            except Exception as exc:  # daemon may close the socket on shutdown
                rec["stop_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            daemon.wait(timeout=30)
        except subprocess.TimeoutExpired:
            daemon.kill()
        strays = subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                capture_output=True, text=True).stdout.split()
        rec["stray_pids"] = strays
        dwell = [e["rmse_vs_prev"] for e in rec["events"]
                 if e["kind"] == "dwell" and e.get("rmse_vs_prev", -1) >= 0]
        press = [e["rmse_vs_prev"] for e in rec["events"]
                 if e["kind"] == "press" and e.get("rmse_vs_prev", -1) >= 0]
        rec["dwell_rmse"] = {"max": max(dwell) if dwell else None, "values": dwell}
        rec["press_rmse"] = {"values": press, "min": min(press) if press else None}
        floor = max(dwell) if dwell else 0.0
        rec["input_landing"] = bool(press) and min(press) > max(floor * 3, 0.02)
        rec["status"] = ("PASS" if rec.get("input_landing") and not strays
                         else rec.get("status", "FAIL"))
        (run / "result.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps({"status": rec["status"], "dwell_rmse": rec["dwell_rmse"],
                          "press_rmse": rec["press_rmse"], "disc_id": rec.get("disc_id"),
                          "stray_pids": strays, "result": str(run / "result.json")}))
    return 0 if rec.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
