"""Candidate-B end-to-end: SDL3 gamepad -> Dolphin emulated GC port A.

Pad is registered via SDL_GAMECONTROLLERCONFIG (mapping proven accepted by
SDL3 in sdl3_pad_probe.py). Dolphin's SDL Gamepad backend device id is
SDL/<instance>/<name> with SDL3 instance ids starting at 1.
"""
from __future__ import annotations
import hashlib, os, subprocess, time
from pathlib import Path
from evdev import UInput, ecodes as e

REPO = Path(__file__).resolve().parents[1]
PROFILE = REPO / "runtime" / "dolphin-agent"
ISO = REPO / "builds" / "pikmin2-lab.iso"
OUT = REPO / "reports" / "runs" / (time.strftime("%Y-%m-%dT%H%M%SZ") + "-gpad-drive")

GC_BUTTONS = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL,
              e.BTN_TR, e.BTN_SELECT, e.BTN_START, e.BTN_MODE,
              e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT]
ABS = {code: (-32767, 32767, 128, 0) for code in (e.ABS_X, e.ABS_Y, e.ABS_RX, e.ABS_RY)}
ABS.update({e.ABS_Z: (0, 255, 0, 0), e.ABS_RZ: (0, 255, 0, 0)})
MAP = ("pikminlab-virtual-pad,platform:Linux,xinput,"
       "a:b0,b:b1,x:b2,y:b3,back:b6,start:b7,guide:b8,"
       "leftshoulder:b4,rightshoulder:b5,"
       "dpup:b9,dpdown:b10,dpleft:b11,dpright:b12,"
       "leftx:a0,lefty:a1,rightx:a2,righty:a3,"
       "lefttrigger:a4,righttrigger:a5")


def configure_sdl_gamepad() -> None:
    """Names verified against Dolphin SDLGamepad.h s_sdl_button_names /
    s_sdl_axis_names; device id defaults to 0 (Core::Device::GetId)."""
    ini = PROFILE / "Config" / "GCPadNew.ini"
    ini.write_text("""[GCPad1]
Device = SDL/0/pikminlab-virtual-pad
Buttons/A = `Button S`
Buttons/B = `Button E`
Buttons/X = `Button W`
Buttons/Y = `Button N`
Buttons/Start = `Start`
Buttons/Select = `Back`
Buttons/L = `Shoulder L`
Buttons/R = `Shoulder R`
Main Stick/Up = `Left Y-`
Main Stick/Down = `Left Y+`
Main Stick/Left = `Left X-`
Main Stick/Right = `Left X+`
C-Stick/Up = `Right Y-`
C-Stick/Down = `Right Y+`
C-Stick/Left = `Right X-`
C-Stick/Right = `Right X+`
Triggers/L-Analog = `Trigger L`
Triggers/R-Analog = `Trigger R`
D-Pad/Up = `Pad N`
D-Pad/Down = `Pad S`
D-Pad/Left = `Pad W`
D-Pad/Right = `Pad E`
""")
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
    ui = UInput({e.EV_KEY: GC_BUTTONS, e.EV_ABS: ABS}, name="pikminlab-virtual-pad")
    configure_sdl_gamepad()
    env = {**os.environ, "SDL_VIDEODRIVER": "x11", "SDL_GAMECONTROLLERCONFIG": MAP + "\n"}
    proc = subprocess.Popen(
        ["dolphin-emu", "-u", str(PROFILE), "-e", str(ISO), "-b", "-v", "Vulkan"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hashes = {}
    try:
        wid = ""
        for _ in range(25):
            wid = find_win()
            if wid: break
            time.sleep(2)
        print("window:", wid)
        time.sleep(18)
        hashes["t0_warning"] = cap(wid, OUT / "t0_warning.png")
        for i in range(1, 4):
            ui.write(e.EV_KEY, e.BTN_START, 1); ui.syn(); time.sleep(0.12)
            ui.write(e.EV_KEY, e.BTN_START, 0); ui.syn()
            time.sleep(3)
            hashes[f"start{i}"] = cap(wid, OUT / f"start{i}.png")
    finally:
        proc.kill(); proc.wait(timeout=10)
        ui.close()
    print("hashes:", hashes)
    print("DISTINCT:", len(set(hashes.values())), "| evidence:", OUT)


if __name__ == "__main__":
    main()
