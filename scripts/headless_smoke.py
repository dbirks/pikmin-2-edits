#!/usr/bin/env python3
"""Handoff §8.1 headless validation, controller-free: boot the verified ISO in
an agent-owned Dolphin under Xvfb, prove a *fresh* window exists, capture two
screenshots and prove they differ (staleness oracle), read the disc ID out of
emulated RAM, and leave no stray process behind.

Input (uinput) is intentionally NOT exercised: /dev/uinput perms are an owner
action (ADR-0013), and nothing in this check needs a pad. Run it wrapped so the
child inherits a display:

  xvfb-run -a -s "-screen 0 1280x960x24" \
    PIKMINLAB_VIDEO_BACKEND=OpenGL uv run python scripts/headless_smoke.py pikmin2.iso

Exit 0 = PASS, 2 = FAIL/BLOCKED with a reason in the JSON record.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pikminlab import frames  # noqa: E402
from pikminlab.dolphin import DolphinSession, default_video_backend, display_env  # noqa: E402

MEM1_DISC_ID = 0x80000000


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else ""


def stats(p: Path) -> dict:
    """Numeric scene oracle. This host's agent session has no vision (model
    rejects images), so 'is a real frame on screen?' is answered with pixels:
    mean brightness + distinct-colour count. Black/absent render = mean~0,
    colors<=2; a lit scene = mean>0.05 and thousands of colours."""
    out = subprocess.run(["magick", "identify", "-format",
                          "%[fx:mean] %k %[fx:maxima]", str(p)], capture_output=True, text=True)
    try:
        mean, colors, maxima = out.stdout.split()
        return {"mean": round(float(mean), 4), "colors": int(colors), "max": round(float(maxima), 3)}
    except ValueError:
        return {"mean": None, "colors": None, "max": None}


def lit(st: dict, min_mean: float = 0.02, min_colors: int = 32) -> bool:
    return bool(st["mean"]) and st["mean"] >= min_mean and (st["colors"] or 0) >= min_colors


def rms(a: Path, b: Path) -> float:
    """Delegates to pikminlab.frames so every script reports the SAME scale.

    This local copy forgot to divide ImageMagick's RMSE by 65535, so the headless
    gate printed `shot_rmse: 1005.92` — a number on a 0..1 scale that read like a
    catastrophe and meant ~1.5% (UI pulse band). Evidence numbers must be
    comparable across runs, hence one implementation (ADR-0017/0019)."""
    return frames.rmse(a, b)


def main() -> int:
    iso = Path(sys.argv[1] if len(sys.argv) > 1 else "pikmin2.iso").resolve()
    wait_win = float(os.environ.get("SMOKE_WAIT_WINDOW", "150"))
    settle = float(os.environ.get("SMOKE_SETTLE", "30"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run = Path(__file__).resolve().parents[1] / "reports" / "runs" / f"{ts}-headless-smoke"
    run.mkdir(parents=True, exist_ok=True)
    rec: dict = {"iso": str(iso), "display": os.environ.get("DISPLAY"),
                 "video_backend": default_video_backend(), "run_dir": str(run),
                 "pad_used": False, "steps": []}

    if not os.environ.get("DISPLAY"):
        rec.update(status="BLOCKED", reason="NO_DISPLAY: run under xvfb-run")
        print(json.dumps(rec)); return 2

    sess = DolphinSession(iso, pad=False)
    sess.start()
    try:
        rec["pid"] = sess.proc.pid
        t0 = time.monotonic()
        wid = sess.window_id(wait_s=wait_win)
        rec["window"] = wid
        rec["window_wait_s"] = round(time.monotonic() - t0, 1)
        rec["steps"].append(["render_window", bool(wid)])
        if not wid:
            rec.update(status="FAIL", reason="no dolphin-emu render window under Xvfb")
            return 2

        time.sleep(settle)  # software GL renders slowly; then poll for a lit frame
        ready = None
        for poll in range(int(os.environ.get("SMOKE_LIT_POLLS", "24"))):
            p0 = run / f"probe{poll}.png"
            if sess.capture(wid, p0) and lit(stats(p0)):
                ready = {"poll": poll, "after_s": round(settle + poll * 10, 1), **stats(p0)}
                p0.rename(run / "scene.png")
                break
            (run / f"probe{poll}.png").unlink(missing_ok=True)
            time.sleep(10)
        rec["scene_ready"] = ready
        rec["steps"].append(["lit_frame", bool(ready)])
        if not ready:
            rec.update(status="FAIL", reason="render window stayed black: no lit frame")
            return 2

        s1 = run / "shot1.png"
        ok1 = sess.capture(wid, s1)
        time.sleep(6)
        s2 = run / "shot2.png"
        ok2 = sess.capture(wid, s2)
        fresh = bool(ok1 and ok2 and s1.is_file() and s2.is_file() and sha(s1) != sha(s2)
                     and lit(stats(s1)) and lit(stats(s2)))
        rec["shots"] = [{"path": str(s1), "sha": sha(s1), **stats(s1)},
                        {"path": str(s2), "sha": sha(s2), **stats(s2)}]
        # Freshness must be lit AND different. A 1-colour black capture next to a
        # lit one passes a hash comparison and proves nothing about rendering
        # (finding F2, ADR-0022: 19 black captures across 15 past runs).
        both_lit = frames.lit(s1) and frames.lit(s2)
        rec["both_shots_lit"] = both_lit
        fresh = fresh and both_lit
        rec["shot_rmse"] = rms(s1, s2) if fresh else None
        rec["steps"].append(["fresh_screenshot", fresh])

        disc = ""
        for attempt in range(5):  # DME hook can race emulator boot
            try:
                disc = sess.memory_read(MEM1_DISC_ID, 6).decode("ascii", "replace")
                break
            except Exception as exc:
                rec["mem_error"] = f"{type(exc).__name__}: {exc}"
                time.sleep(4)
        rec["disc_id"] = disc
        rec["steps"].append(["ram_disc_id", disc == "GPVE01"])
        rec.update(status="PASS" if fresh and disc == "GPVE01" else "FAIL")
    finally:
        sess.stop()
        time.sleep(2)
        strays = subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                capture_output=True, text=True).stdout.split()
        rec["stray_pids"] = strays
        rec["steps"].append(["clean_teardown", not strays])
        (run / "result.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps(rec))
    return 0 if rec.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
