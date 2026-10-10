#!/usr/bin/env python3
"""Does ANY host channel reach the emulator? Ask it to save a state and look for the file.

The pad is opened by Dolphin (two fds on /dev/input/eventNN), the SDL device string
and every element name are confirmed correct against Dolphin's own SDLGamepad.h, and
batch mode is exonerated — yet no press produces an attributable effect. So before
blaming the emulated GameCube port, test a channel whose success is a FILE on disk:
Dolphin's GUI hotkey F1 = Save State. If a state file appears, host input reaches
Dolphin at all in this launch mode and the failure is specific to the GC pad path;
if nothing appears, no host input is being consumed in this configuration.

Read-only toward the game: a savestate is an emulator-side file in our own agent
profile, never a memory write and never the owner's profile.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a uv run python scripts/hotkey_channel_probe.py
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import dolphin, frames  # noqa: E402

PROFILE = REPO / "runtime/dolphin-agent"


def snapshot() -> dict:
    """Every file under the profile's state dirs, as {path: (size, mtime)}."""
    out = {}
    for base in (PROFILE / "State", PROFILE / "GameCube" / "States", PROFILE / "States"):
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file():
                    st = p.stat()
                    out[str(p.relative_to(PROFILE))] = [st.st_size, round(st.st_mtime, 3)]
    return out


def main() -> int:
    iso = REPO / "builds/lab-cave.iso"
    run = REPO / "reports/runs" / (time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()) + "-hotkey-channel")
    run.mkdir(parents=True, exist_ok=True)
    rec: dict = {"state_dirs_seen": {str(d): d.is_dir() for d in
                                     (PROFILE / "State", PROFILE / "GameCube" / "States",
                                      PROFILE / "States")},
                 "batch": os.environ.get("PIKMINLAB_BATCH", "1") != "0"}
    ses = dolphin.DolphinSession(iso, pad=True)
    ses.start()
    pid = ses.proc.pid
    try:
        wid = ses.window_id(wait_s=40)
        rec["window"] = wid
        rec["display"] = os.environ.get("DISPLAY")
        time.sleep(35)                      # let the game actually boot before hotkeys
        before = snapshot()
        rec["states_before"] = before

        sends = []

        def send(label: str, argv: list[str]):
            r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
            time.sleep(6)
            now = snapshot()
            new = {k: v for k, v in now.items() if before.get(k) != v}
            sends.append({"label": label, "cmd": " ".join(argv), "rc": r.returncode,
                          "stderr": r.stderr.strip()[:80], "new_or_changed": new})
            return bool(new)

        if wid:
            # window-targeted events do not need a window manager to give focus
            hit = send("F1_window", ["xdotool", "key", "--window", str(wid), "F1"])
            if not hit:
                send("F2_window", ["xdotool", "key", "--window", str(wid), "F2"])
            if not hit:
                send("ctrlF1_window", ["xdotool", "key", "--window", str(wid), "ctrl+F1"])
        send("F1_root", ["xdotool", "key", "F1"])
        send("F1_windowactivate", ["xdotool", "windowactivate", "--sync", str(wid)])
        rec["sends"] = sends
        rec["host_input_reached_dolphin"] = any(s["new_or_changed"] for s in sends)

        # also record the pad channel in the same session for a paired comparison
        ses.gc_tap("START", hold_s=0.2)
        time.sleep(4)
        p = run / "frame.png"
        if wid and ses.capture(wid, p):
            rec["frame"] = {"path": str(p.relative_to(REPO)), **frames.stats(p)}
        # A negative is only meaningful if F1 was actually bound and a state dir existed.
        bound = any((PROFILE / "Config" / f).is_file() for f in ("Hotkeys.ini",)) or \
            "Hotkey" in (PROFILE / "Config/Dolphin.ini").read_text()
        rec["oracle_valid"] = bool(rec["state_dirs_seen"]) and bound
        if rec["host_input_reached_dolphin"]:
            rec["verdict"] = "HOST_INPUT_REACHES_DOLPHIN_via=" + ",".join(
                s["label"] for s in sends if s["new_or_changed"])
        elif rec["oracle_valid"]:
            rec["verdict"] = "NO_HOST_INPUT_CONSUMED: savestate hotkey bound, no file appeared"
        else:
            rec["verdict"] = ("ORACLE_INVALID: no State dir existed and no savestate hotkey "
                             "is bound in this profile, so silence proves nothing")
        return 0
    finally:
        ses.stop()
        subprocess.run(["/bin/kill", "-KILL", str(pid)])
        (run / "result.json").write_text(json.dumps(rec, indent=2))
        for s in rec.get("sends", []):
            print(f"  {s['label']:20s} rc={s['rc']} new={list(s['new_or_changed'])[:2]} err={s['stderr'][:40]}")
        print(json.dumps({k: v for k, v in rec.items() if k not in ("sends", "states_before")}, indent=1))
        print("STRAYS:", subprocess.run(["pgrep", "-x", "dolphin-emu"], capture_output=True)
              .stdout.decode().strip() or "none", "| evidence:", run)


if __name__ == "__main__":
    sys.exit(main())
