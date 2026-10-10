#!/usr/bin/env python3
"""Does Dolphin actually CONSUME our uinput events? (mechanism probe, no game claims)

ADR-0015 proved the pad's event fd appears in Dolphin's /proc/<pid>/fd, and ADR-0020
proved frame deltas cannot attribute input. Both left the real question untouched:
is our input merely *openable* or is it being *read* by the input layer while the
emulator runs? evdev answers that without strace (which isn't installed, and would
need your approval to add): /proc/<pid>/fdinfo/<fd> for an evdev fd exposes the
consumer's event index, which advances only when someone reads the device.

If the index advances while we press, the pad path is alive and the t5 failure is
UPSTREAM of input (the screens we reach never act on input). If it never advances,
input polling itself is dead in this launch mode — a different, smaller bug.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a uv run python scripts/pad_consumption_probe.py
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import dolphin, frames  # noqa: E402
from pikminlab.vpad import VirtualPad  # noqa: E402
from evdev import ecodes as e  # noqa: E402


def pad_fds(pid: int, devnode: str) -> list[int]:
    out = []
    for fd in os.listdir(f"/proc/{pid}/fd"):
        try:
            if os.readlink(f"/proc/{pid}/fd/{fd}") == devnode:
                out.append(int(fd))
        except OSError:
            pass
    return out


def fdinfo(pid: int, fd: int) -> dict:
    """Kernel's evdev consumer state. `idx` is the next event slot to read."""
    try:
        txt = Path(f"/proc/{pid}/fdinfo/{fd}").read_text()
    except OSError as exc:
        return {"error": str(exc)}
    d = dict(re.findall(r"^(\w+):\s+(\S+)", txt, re.M))
    d["raw"] = txt.strip().replace("\n", " | ")
    return d


def main() -> int:
    iso = REPO / "builds/lab-cave.iso"
    run = REPO / "reports/runs" / (time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()) + "-pad-consume")
    run.mkdir(parents=True, exist_ok=True)
    # The pad must exist BEFORE Dolphin starts: SDL enumerates at startup and this
    # host gave us no evidence that it hotplugs (the real harness creates it first).
    ses = dolphin.DolphinSession(iso, pad=True)
    ses.start()
    pad = ses.pad
    pid = ses.proc.pid
    # ui.devnode is /dev/uinput (the WRITER). The node Dolphin reads is the created
    # /dev/input/eventNN, found by name; open/close per lookup so we never sit on a
    # reader of our own while measuring Dolphin's consumption.
    import evdev
    def node_for(name: str) -> str | None:
        for path in evdev.list_devices():
            d = evdev.InputDevice(path)
            try:
                if d.name == name:
                    return path
            finally:
                d.close()
        return None
    t0 = time.time()
    node = None
    while time.time() - t0 < 15 and not node:
        node = node_for(pad.name)
        time.sleep(0.5)
    rec = {"pid": pid, "pad_name": pad.name, "event_node": node,
           "uinput_writer": pad.ui.devnode, "dolphin_args": " ".join(ses.proc.args)}
    if not node:
        rec["verdict"] = "PAD_NODE_NEVER_APPEARED"
        return 1
    try:
        t0 = time.time()
        fds: list[int] = []
        while time.time() - t0 < 60 and not fds:
            fds = pad_fds(pid, node)
            time.sleep(1)
        rec["pad_fds_in_dolphin"] = fds
        rec["seconds_to_open"] = round(time.time() - t0, 1)
        if not fds:
            rec["verdict"] = "NO_FD"
            return 1
        fd = fds[0]
        rec["fdinfo_shape"] = fdinfo(pid, fd)

        def sample():
            return {f: fdinfo(pid, f) for f in fds}

        idle_a, idle_b = sample(), None
        time.sleep(5.0)
        idle_b = sample()

        def idx(d):
            return {f: (v.get("idx"), v.get("pos")) for f, v in d.items()}
        rec["idle_window_5s"] = {"idx_a": idx(idle_a), "idx_b": idx(idle_b)}

        # press hard: 6 taps + a held stick, then a long dwell to separate
        # "consumed" from "consumed but ignored by the game"
        for _ in range(6):
            pad.button(e.BTN_SOUTH, True); time.sleep(0.12)
            pad.button(e.BTN_SOUTH, False); time.sleep(0.18)
        pad.stick(e.ABS_X, e.ABS_Y, 30000, 0); time.sleep(1.2)
        pad.neutral()
        pressed = sample()
        time.sleep(5.0)
        after = sample()
        rec["after_press"] = idx(pressed)
        rec["after_press_plus_5s"] = idx(after)

        def advanced(before, later):
            return {str(f): (later[f].get("idx"), before[f].get("idx")) for f in before}
        rec["press_window_delta_idx"] = advanced(idle_b, pressed)
        consumed = any(str(a) != str(b) for a, b in rec["press_window_delta_idx"].values())
        rec["events_consumed_during_press"] = bool(consumed)
        shot = run / "frame.png"
        wid = ses.window_id(wait_s=20)
        rec["window"] = wid
        if wid and ses.capture(wid, shot):
            rec["frame"] = {"path": str(shot.relative_to(REPO)), **frames.stats(shot)}
        rec["verdict"] = "INPUT_REACHES_DOLPHIN" if consumed else "INPUT_NOT_CONSUMED"
        return 0
    finally:
        ses.stop()          # closes the pad it owns
        subprocess.run(["/bin/kill", "-KILL", str(pid)])
        (run / "result.json").write_text(json.dumps(rec, indent=2))
        print(json.dumps({k: rec[k] for k in rec if k != "fdinfo_shape"}, indent=1)[:1800])
        strays = subprocess.run(["pgrep", "-x", "dolphin-emu"], capture_output=True).stdout.decode()
        print("STRAYS:", strays.strip() or "none", "| evidence:", run)


if __name__ == "__main__":
    sys.exit(main())
