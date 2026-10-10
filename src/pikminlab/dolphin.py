"""Launch/capture/stop recipe for agent-owned Dolphin instances (ADR-0006,
input stack per ADR-0011: uinput gamepad -> SDL3 gamepad mapping -> GC port A)."""
from __future__ import annotations
import subprocess, time, shutil, os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE = REPO / "runtime" / "dolphin-agent"

GC_MAPPING = ("pikminlab-virtual-pad,platform:Linux,xinput,"
              "a:b0,b:b1,x:b2,y:b3,back:b6,start:b7,guide:b8,"
              "leftshoulder:b4,rightshoulder:b5,"
              "dpup:b9,dpdown:b10,dpleft:b11,dpright:b12,"
              "leftx:a0,lefty:a1,rightx:a2,righty:a3,"
              "lefttrigger:a4,righttrigger:a5")

GC_PAD_INI = """[GCPad1]
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
"""


def _sh(*cmd: str, timeout: float = 15, env=None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, **kw)


class DolphinSession:
    """One batch-mode instance with guaranteed teardown. Use as a context
    manager: the owner never sees a stranded window."""

    def __init__(self, iso: Path, video_backend: str = "Vulkan", pad: bool = True):
        self.iso = iso
        self.video_backend = video_backend
        self.use_pad = pad
        self.proc: subprocess.Popen | None = None
        self.pad = None

    def start(self) -> "DolphinSession":
        env = {**os.environ, "SDL_VIDEODRIVER": "x11", "DISPLAY": ":0",
               "SDL_GAMECONTROLLERCONFIG": GC_MAPPING + "\n"}
        if self.use_pad:
            from .vpad import VirtualPad
            self.pad = VirtualPad()
            (PROFILE / "Config" / "GCPadNew.ini").write_text(GC_PAD_INI)
        self.proc = subprocess.Popen(
            ["dolphin-emu", "-u", str(PROFILE), "-e", str(self.iso), "-b",
             "-v", self.video_backend],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self

    # -- real GC pad input via uinput (ADR-0011) ------------------------
    def gc(self, button: str, down: bool) -> None:
        from evdev import ecodes as e
        m = {"A": e.BTN_SOUTH, "B": e.BTN_EAST, "X": e.BTN_NORTH,
             "Y": e.BTN_WEST, "L": e.BTN_TL, "R": e.BTN_TR,
             "Z": e.BTN_MODE, "START": e.BTN_START, "SELECT": e.BTN_SELECT}
        self.pad.button(m[button.upper()], down)

    def gc_tap(self, button: str, hold_s: float = 0.15) -> None:
        self.gc(button, True); time.sleep(hold_s); self.gc(button, False)

    def gc_stick(self, x: int, y: int) -> None:
        from evdev import ecodes as e
        self.pad.stick(e.ABS_X, e.ABS_Y, x, y)

    def window_id(self, wait_s: float = 40) -> str | None:
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            r = _sh("xdotool", "search", "--class", "dolphin-emu")
            for wid in r.stdout.split():
                n = _sh("xdotool", "getwindowname", wid).stdout
                if "|" in n:  # render window: "... | Vulkan | HLE | Pikmin 2 (GPVE01)"
                    return wid
            time.sleep(2)
        return None

    def press(self, wid: str, keysym: str) -> None:
        _sh("xdotool", "key", "--window", wid, "--clearmodifiers", keysym)

    def capture(self, wid: str, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        return _sh("magick", "import", "-window", wid, str(dest), timeout=20).returncode == 0

    def memory_read(self, address: int, size: int) -> bytes:
        import dolphin_memory_engine as dme
        if not dme.is_hooked():
            dme.hook()
        return dme.read_bytes(address, size)

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            import dolphin_memory_engine as dme
            if dme.is_hooked():
                dme.un_hook()
        except Exception:
            pass
        if self.pad:
            self.pad.close(); self.pad = None
        try:
            self.proc.kill()  # SIGKILL: cannot be intercepted by dialogs
            self.proc.wait(timeout=10)
        finally:
            self.proc = None

    def __enter__(self): return self.start()
    def __exit__(self, *exc): self.stop()


def doctor_report() -> dict:
    tools = {t: shutil.which(t) for t in
             ("dolphin-emu", "dolphin-tool", "xdotool", "flameshot", "magick", "java", "ffmpeg")}
    ver = _sh("dolphin-emu", "--version").stdout.strip().splitlines()[-1:] or [None]
    return {"tools": tools, "dolphin_version": ver[0],
            "profile_exists": PROFILE.is_dir()}
