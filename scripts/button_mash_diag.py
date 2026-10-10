"""Dolphin-side input isolation: pad writes are kernel-proven; this tests
whether ANY emulated-pad binding responds. Presses ALL joystick-range
buttons simultaneously per 'press' (covers any index-ordering theory) plus
a stick tilt. If the warning screen still doesn't advance, the config
binding (not the button map) is the fault."""
from __future__ import annotations
import hashlib, os, subprocess, time
from pathlib import Path
import evdev
from evdev import UInput, ecodes as e

REPO = Path(__file__).resolve().parents[1]
PROFILE = REPO / "runtime" / "dolphin-agent"
ISO = REPO / "builds" / "pikmin2-lab.iso"
OUT = REPO / "reports" / "runs" / (time.strftime("%Y-%m-%dT%H%M%SZ") + "-button-mash")

ALL_BTN = list(range(e.BTN_SOUTH, e.BTN_THUMBR + 1))  # 304..317
HAT = [e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT]


def find_win() -> str:
    r = subprocess.run(["xdotool", "search", "--class", "dolphin-emu"],
                       capture_output=True, text=True)
    for wid in r.stdout.split():
        n = subprocess.run(["xdotool", "getwindowname", wid],
                           capture_output=True, text=True).stdout
        if "|" in n:
            return wid
    return ""


def cap(wid: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["magick", "import", "-window", wid, str(dest)], timeout=20)
    return hashlib.sha256(dest.read_bytes()).hexdigest()[:12] if dest.exists() else "-"


def main() -> None:
    ui = UInput({e.EV_KEY: ALL_BTN + HAT,
                 e.EV_ABS: {e.ABS_X: (-32767, 32767, 128, 0),
                            e.ABS_Y: (-32767, 32767, 128, 0),
                            e.ABS_RX: (-32767, 32767, 128, 0),
                            e.ABS_RY: (-32767, 32767, 128, 0),
                            e.ABS_Z: (0, 255, 0, 0), e.ABS_RZ: (0, 255, 0, 0)}},
                name="pikminlab-virtual-pad")
    proc = subprocess.Popen(
        ["dolphin-emu", "-u", str(PROFILE), "-e", str(ISO), "-b", "-v", "Vulkan"],
        env={**os.environ, "SDL_VIDEODRIVER": "x11"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hashes = {}
    try:
        wid = ""
        for _ in range(25):
            wid = find_win()
            if wid: break
            time.sleep(2)
        time.sleep(18)
        hashes["t0"] = cap(wid, OUT / "t0.png")
        for i in range(1, 4):
            for b in ALL_BTN:
                ui.write(e.EV_KEY, b, 1)
            ui.write(e.EV_ABS, e.ABS_X, 25000); ui.write(e.EV_ABS, e.ABS_Y, -25000)
            ui.syn(); time.sleep(0.2)
            for b in ALL_BTN:
                ui.write(e.EV_KEY, b, 0)
            ui.write(e.EV_ABS, e.ABS_X, 0); ui.write(e.EV_ABS, e.ABS_Y, 0)
            ui.syn()
            time.sleep(3)
            hashes[f"mash{i}"] = cap(wid, OUT / f"mash{i}.png")
    finally:
        proc.kill(); proc.wait(timeout=10)
        ui.close()
    print("hashes:", hashes)
    print("DISTINCT:", len(set(hashes.values())), "| evidence:", OUT)


if __name__ == "__main__":
    main()
