#!/usr/bin/env python3
"""Press START at the ATTRACT screen and see if the video stops (diagnostic #2).

ADR-0020 withdrew the input claim, but every sample in it was taken at 256-colour
frames — i.e. during the health-warning splash, before the title/attract screen
exists. The attract demo is recorded *gameplay video*, so while it runs, RMSE over
no-input windows is large (measured 0.3477/12 s). That gives an attribution signal
the splash could never give: if START registers, the movie stops and the screen goes
quiet while still showing a real scene (colours stay high). Press-window RMSE
collapsing below the dwell-window RMSE at high colour count is attributable input;
nothing else about this test is inferred.

No game claims, no memory writes: this asks one question about the input path.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a uv run python scripts/attract_stop_probe.py
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import dolphin, frames  # noqa: E402

SCENE_COLOURS = 20_000        # below this we are on a splash/text screen, not attract


def main() -> int:
    iso = REPO / "builds/lab-cave.iso"
    tag = "attract-stop" if os.environ.get("PIKMINLAB_BATCH", "1") != "0" else "attract-stop-nobatch"
    run = REPO / "reports/runs" / (time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()) + "-" + tag)
    run.mkdir(parents=True, exist_ok=True)
    rec: dict = {"iso_sha256_first16": None, "windows": [],
             "batch": os.environ.get("PIKMINLAB_BATCH", "1") != "0"}
    ses = dolphin.DolphinSession(iso, pad=True)
    ses.start()
    pid = ses.proc.pid
    try:
        import hashlib
        rec["iso_sha256_first16"] = hashlib.sha256(iso.read_bytes()).hexdigest()[:16]
        wid = ses.window_id(wait_s=40)
        rec["window"] = wid
        if not wid:
            rec["verdict"] = "NO_WINDOW"
            return 1

        def shot(name):
            p = run / f"{name}.png"
            return p if ses.capture(wid, p) else None

        # 1) wait for the attract screen (real scene, many colours)
        t0, scene, first = time.time(), None, None
        while time.time() - t0 < 120:
            p = shot("wait")
            if p:
                st = frames.stats(p)
                if (st["colors"] or 0) > SCENE_COLOURS:
                    scene, first = st, p
                    break
            time.sleep(6)
        rec["reached_scene"] = {"after_s": round(time.time() - t0, 1), **(scene or {})}
        if not scene:
            rec["verdict"] = "NEVER_REACHED_ATTRACT"
            return 1

        def window(tag, presses):
            """Capture over `n` intervals, optionally pressing between them."""
            a, prev = shot(f"{tag}_a"), None
            times, rms, kinds = [], [], []
            for i in range(3):
                time.sleep(8)
                b = shot(f"{tag}_{i}")
                if a and b:
                    rms.append(round(frames.rmse(a, b), 4))
                    kinds.append(frames.stats(b)["colors"])
                    a = b
                if presses:
                    fn = presses[i % len(presses)]
                    fn()
            return {"rms": rms, "colors": kinds}

        rec["windows"].append({"tag": "dwell_no_input", **window("dwell", None)})
        rec["windows"].append({"tag": "press_start", **window(
            "pstart", [lambda: ses.gc_tap("START", hold_s=0.2),
                       lambda: ses.gc_tap("START", hold_s=0.2),
                       lambda: ses.gc_tap("A", hold_s=0.2)])})
        rec["windows"].append({"tag": "press_start_then_A", **window(
            "psa", [lambda: (ses.gc_tap("START", 0.2), time.sleep(1.0), ses.gc_tap("A", 0.2)),
                    lambda: ses.gc_tap("A", 0.2),
                    lambda: ses.gc_tap("A", 0.2)])})

        def med(w):
            v = sorted(w["rms"])
            return v[len(v) // 2] if v else None
        dw, ps, sa = (med(rec["windows"][i]) for i in range(3))
        rec["medians"] = {"dwell": dw, "press_start": ps, "start_then_A": sa}
        quiet = lambda m: m is not None and m < 0.05
        rec["verdict"] = ("INPUT_REGISTERED_ATTRACT_STOPPED" if (quiet(ps) or quiet(sa)) and dw and dw > 0.15
                          else "ATTRACT_KEPT_RUNNING_INPUT_UNSEEN")
        return 0
    finally:
        ses.stop()
        subprocess.run(["/bin/kill", "-KILL", str(pid)])
        (run / "result.json").write_text(json.dumps(rec, indent=2))
        print(json.dumps({k: v for k, v in rec.items() if k != "windows"}, indent=1))
        for w in rec["windows"]:
            print(" ", w["tag"], "rms=", w["rms"], "colors=", w["colors"])
        print("STRAYS:", subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                        capture_output=True).stdout.decode().strip() or "none",
              "| evidence:", run)


if __name__ == "__main__":
    sys.exit(main())
