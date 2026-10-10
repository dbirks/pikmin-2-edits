"""Decisive Candidate-B test: does the uinput gamepad actually drive the game?

Lifecycle (no synthetic events, no popups):
  hold virtual GC pad open -> launch Dolphin (SDL enumerates pad at startup)
  -> wait for 'press any button' warning -> tap Start several times
  -> capture frames and report whether the screen advances.
Guaranteed teardown of both Dolphin and the pad.
"""
from __future__ import annotations
import hashlib, subprocess, time
from pathlib import Path
from evdev import UInput, ecodes as e
import evdev

REPO = Path(__file__).resolve().parents[1]
PROFILE = REPO / "runtime" / "dolphin-agent"
ISO = REPO / "builds" / "pikmin2-lab.iso"
OUT = REPO / "reports" / "runs" / (time.strftime("%Y-%m-%dT%H%M%SZ") + "-pad-drive")

BTN = {"A": e.BTN_SOUTH, "B": e.BTN_EAST, "X": e.BTN_NORTH, "Y": e.BTN_WEST,
       "START": e.BTN_START, "SELECT": e.BTN_SELECT}
ABS = {e.ABS_X: (-32767, 32767, 128, 0), e.ABS_Y: (-32767, 32767, 128, 0),
       e.ABS_RX: (-32767, 32767, 128, 0), e.ABS_RY: (-32767, 32767, 128, 0),
       e.ABS_Z: (0, 255, 0, 0), e.ABS_RZ: (0, 255, 0, 0)}


def configure_sdl_pad(name: str) -> None:
    """Bind emulated GC port A to the SDL joystick. SDL2 indexes unknown
    evdev pads by ascending evdev KEY code in the bitmask, not code math:
    our set {304S,305E,307N,308W,310TL,311TR,314SEL,315STA,316MOD,544..547}
    -> A=0 B=1 X=2 Y=3 L=4 R=5 Select=6 Start=7 Z=8 Dpad=9..12."""
    ini = PROFILE / "Config" / "GCPadNew.ini"
    body = f"""[GCPad1]
Device = SDL0/0/{name}
Buttons/A = `0`
Buttons/B = `1`
Buttons/X = `2`
Buttons/Y = `3`
Buttons/Start = `7`
Buttons/Select = `6`
Buttons/L = `4`
Buttons/R = `5`
Buttons/Z = `8`
Main Stick/Up = `Axis 1-`
Main Stick/Down = `Axis 1+`
Main Stick/Left = `Axis 0-`
Main Stick/Right = `Axis 0+`
Main Stick/Modifier = `None`
C-Stick/Up = `Axis 3-`
C-Stick/Down = `Axis 3+`
C-Stick/Left = `Axis 2-`
C-Stick/Right = `Axis 2+`
Triggers/L-Analog = `Axis 4+`
Triggers/R-Analog = `Axis 5+`
"""
    ini.write_text(body)
    print("wrote", ini)


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
    before = set(evdev.list_devices())
    ui = UInput({e.EV_KEY: list(BTN.values()) + [e.BTN_TL, e.BTN_TR],
                 e.EV_ABS: ABS}, name="pikminlab-virtual-pad")
    new = [p for p in evdev.list_devices() if p not in before]
    print("pad device:", new, "name:", evdev.InputDevice(new[0]).name)

    configure_sdl_pad("pikminlab-virtual-pad")
    env = {"SDL_VIDEODRIVER": "x11", "DISPLAY": ":0", "PATH": "/usr/bin:/bin"}
    import os
    env = {**os.environ, "SDL_VIDEODRIVER": "x11"}
    proc = subprocess.Popen(["dolphin-emu", "-u", str(PROFILE), "-e", str(ISO),
                             "-b", "-v", "Vulkan"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hashes = {}
    try:
        for _ in range(25):
            wid = find_win()
            if wid:
                break
            time.sleep(2)
        print("window:", wid)
        time.sleep(18)                                   # let warning screen settle
        hashes["t0_warning"] = cap(wid, OUT / "t0_warning.png")
        for i in range(1, 4):
            ui.write(e.EV_KEY, e.BTN_START, 1); ui.syn(); time.sleep(0.1)
            ui.write(e.EV_KEY, e.BTN_START, 0); ui.syn()
            time.sleep(3)
            hashes[f"t{i}_after_start"] = cap(wid, OUT / f"t{i}_after_start.png")
    finally:
        proc.kill(); proc.wait(timeout=10)
        ui.close()
    print("screen hashes:", hashes)
    print("DISTINCT STATES:", len(set(hashes.values())))
    print("evidence:", OUT)


if __name__ == "__main__":
    main()
