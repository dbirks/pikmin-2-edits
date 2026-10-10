#!/usr/bin/env python3
"""Device-level input oracle: does the emulator actually OPEN our uinput pad?

Scene-diff is a bad input oracle under software rendering — the game animates on
its own (attract movie, fades), so dwell frames differ by up to ~11% RMSE while
a press can land on a static transition and differ by 0.0. This check answers
the host-specific question instead, with no pixels: SDL opens every
/dev/input/event* it is allowed to, so if Dolphin's own fd table contains our
pad's event node, the input stack is live on this host.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \
    uv run python scripts/pad_visibility_oracle.py pikmin2.iso

Exit 0 = Dolphin has our pad open. (Game-level response still needs a static
wait-state test; see ADR-0015.)
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab.dolphin import (GC_MAPPING, GC_PAD_INI, PROFILE, default_video_backend,  # noqa: E402
                               display_env)
from pikminlab.vpad import NAME, VirtualPad  # noqa: E402


def pad_event_handler() -> str | None:
    """eventNN backing our uinput device, via /proc/bus/input/devices.
    (python-evdev's UInput.devnode reports /dev/uinput, not the created node.)"""
    for blk in Path("/proc/bus/input/devices").read_text().split("\n\n"):
        if NAME in blk:
            m = re.search(r"H: Handlers=(\S+)", blk)
            if m:
                return next((h for h in m.group(1).split() if h.startswith("event")), None)
    return None


def main() -> int:
    iso = (REPO / (sys.argv[1] if len(sys.argv) > 1 else "pikmin2.iso")).resolve()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run = REPO / "reports" / "runs" / f"{ts}-pad-oracle"
    run.mkdir(parents=True, exist_ok=True)
    rec: dict = {"iso": str(iso), "display": os.environ.get("DISPLAY"),
                 "video_backend": default_video_backend()}

    pad = VirtualPad()
    time.sleep(1.0)
    rec["pad_event"] = pad_event_handler()
    (PROFILE / "Config" / "GCPadNew.ini").write_text(GC_PAD_INI)
    env = {**display_env(), "SDL_GAMECONTROLLERCONFIG": GC_MAPPING + "\n"}
    proc = subprocess.Popen(["dolphin-emu", "-u", str(PROFILE), "-e", str(iso), "-b",
                             "-v", default_video_backend()], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(float(os.environ.get("PAD_ORACLE_SETTLE", "30")))
        fds = set()
        for f in Path(f"/proc/{proc.pid}/fd").iterdir():
            try:
                tgt = os.readlink(f)
            except OSError:
                continue
            if "/dev/input/event" in tgt:
                fds.add(tgt)
        rec["dolphin_event_fds"] = sorted(fds)
        rec["pad_opened_by_dolphin"] = f"/dev/input/{rec['pad_event']}" in fds
        rec["status"] = "PASS" if rec["pad_opened_by_dolphin"] else "FAIL"
    finally:
        proc.kill()
        proc.wait(timeout=15)
        pad.close()
        time.sleep(1)
        rec["stray_pids"] = subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                          capture_output=True, text=True).stdout.split()
        if rec["stray_pids"]:
            rec["status"] = "FAIL"
        (run / "result.json").write_text(json.dumps(rec, indent=1))
        print(json.dumps(rec))
    return 0 if rec.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
