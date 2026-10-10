"""Launch/capture/stop recipe for agent-owned Dolphin instances (ADR-0006,
input stack per ADR-0011: uinput gamepad -> SDL3 gamepad mapping -> GC port A)."""
from __future__ import annotations
import os, shutil, subprocess, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE = REPO / "runtime" / "dolphin-agent"

GC_MAPPING = ("pikminlab-virtual-pad,platform:Linux,xinput,"
              "a:b0,b:b1,x:b2,y:b3,back:b6,start:b7,guide:b8,"
              "leftshoulder:b4,rightshoulder:b5,"
              "dpup:b9,dpdown:b10,dpleft:b11,dpright:b12,"
              "leftx:a0,lefty:a1,rightx:a2,righty:a3,"
              "lefttrigger:a4,righttrigger:a5")

# Element names verified against Dolphin's own SDLGamepad.h (s_sdl_button_names /
# s_sdl_axis_names), not by guesswork: Button S/E/W/N, Back, Start, Shoulder L/R,
# Pad N/S/W/E, and axes "Left X+"/"Left Y+" etc. Axis::GetName() inverts the odd
# (vertical) axes "to respect XInput", so `Left Y+` is UP — the original template had
# up/down swapped, which is why a cursor nudge meant "up" moved it down.
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
Main Stick/Up = `Left Y+`
Main Stick/Down = `Left Y-`
Main Stick/Left = `Left X-`
Main Stick/Right = `Left X+`
C-Stick/Up = `Right Y+`
C-Stick/Down = `Right Y-`
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


def default_video_backend() -> str:
    """Dolphin `-v` backend; override with PIKMINLAB_VIDEO_BACKEND (ADR-0013).
    Headless candidates to A/B are Vulkan (ANV or lavapipe) and OpenGL+llvmpipe."""
    return os.environ.get("PIKMINLAB_VIDEO_BACKEND", "Vulkan")


def display_env() -> dict:
    """Environment for an agent-owned Dolphin. On the laptop the render target
    was XWayland at :0 (ADR-0006); a headless host has no :0, so `xvfb-run`
    exports its own DISPLAY and we must inherit it instead of clobbering it
    (ADR-0013). PIKMINLAB_DISPLAY pins a display explicitly."""
    disp = os.environ.get("PIKMINLAB_DISPLAY") or os.environ.get("DISPLAY") or ":0"
    return {**os.environ, "SDL_VIDEODRIVER": "x11", "DISPLAY": disp}


def find_render_window() -> str:
    """The XWayland render window: dolphin-emu-class window whose title
    contains '|' (ADR-0006/0011 recipe). Returns '' if not present."""
    win = ""
    r = _sh("xdotool", "search", "--class", "dolphin-emu")
    for wid in r.stdout.split():
        n = _sh("xdotool", "getwindowname", wid).stdout
        if "|" in n:
            win = wid
    return win


class DolphinSession:
    """One batch-mode instance with guaranteed teardown. Use as a context
    manager: the owner never sees a stranded window."""

    def __init__(self, iso: Path, video_backend: str | None = None, pad: bool = True,
                 log_path: Path | None = None, batch: bool | None = None):
        self.iso = iso
        self.video_backend = video_backend or default_video_backend()
        self.use_pad = pad
        self.proc: subprocess.Popen | None = None
        self.pad = None
        # Dolphin's own stdout/stderr names the input device it opened for each
        # port. Sending it to DEVNULL hid the only log that could say whether our
        # uinput pad ever became Port 1, which is why the t5 blocker took a
        # control-run experiment to characterise (ADR-0020). Keep it per session.
        self.log_path = log_path
        # -b runs the core without the GUI's normal input/idle loop. Every input
        # claim so far was made under -b, so whether batch mode polls host devices
        # at all was never tested (ADR-0020 left it open). PIKMINLAB_BATCH=0 turns
        # it off to separate "device not bound to Port 1" from "nothing is polled".
        self.batch = (os.environ.get("PIKMINLAB_BATCH", "1") != "0") if batch is None else batch
        self._log_fh = None

    def start(self) -> "DolphinSession":
        env = {**display_env(), "SDL_GAMECONTROLLERCONFIG": GC_MAPPING + "\n"}
        if self.use_pad:
            from .vpad import VirtualPad
            self.pad = VirtualPad()
            (PROFILE / "Config" / "GCPadNew.ini").write_text(GC_PAD_INI)
        if self.log_path is None:      # default: every session logs, so the
            # device/port evidence exists even when a call site forgot to ask
            self.log_path = (PROFILE / "Logs" /
                             ("session-" + time.strftime("%Y%m%dT%H%M%SZ") + ".log"))
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_fh = self.log_path.open("ab")
            out = err = self._log_fh
        else:
            out = err = subprocess.DEVNULL
        self.proc = subprocess.Popen(
            ["dolphin-emu", "-u", str(PROFILE), "-e", str(self.iso)] +
            (["-b"] if self.batch else []) +
            ["-v", self.video_backend],
            env=env, stdout=out, stderr=err)
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
            if self._log_fh:
                self._log_fh.close(); self._log_fh = None

    def __enter__(self): return self.start()
    def __exit__(self, *exc): self.stop()


REQUIRED_TOOLS = ("dolphin-emu", "dolphin-tool", "xdotool", "magick")
# Reported, never fatal: flameshot was a laptop-only capture fallback; java is
# P3 CaveGen-only; xvfb-run/Xvfb matter only on a host with no display.
OPTIONAL_TOOLS = ("flameshot", "java", "ffmpeg", "xvfb-run", "Xvfb")
UINPUT = Path("/dev/uinput")


def _run_probe(tool: str) -> dict:
    """PATH presence alone lies on Arch: a package pulled from a synced DB but
    run against an un-upgraded glibc/ffmpeg exists and then dies at exec
    ('error while loading shared libraries', GLIBC_x not found). Actually exec
    the emulator binaries so `doctor` catches the partial-upgrade case (ADR-0013)."""
    path = shutil.which(tool)
    if not path:
        return {"path": None, "runnable": False, "error": "NOT_INSTALLED"}
    try:
        r = _sh(tool, "--version", timeout=30)
    except Exception as exc:  # pragma: no cover - diagnostics only
        return {"path": path, "runnable": False, "error": str(exc)[:160]}
    if r.returncode != 0:
        first = next((ln.strip() for ln in (r.stderr + r.stdout).splitlines() if ln.strip()), "")
        return {"path": path, "runnable": False, "error": (first or f"exit {r.returncode}")[:200]}
    out = (r.stdout + r.stderr).strip().splitlines()
    return {"path": path, "runnable": True, "version": out[-1][:80] if out else None}


def doctor_report() -> dict:
    tools = {t: shutil.which(t) for t in REQUIRED_TOOLS + OPTIONAL_TOOLS}
    probes = {t: _run_probe(t) for t in ("dolphin-emu", "dolphin-tool")}
    disp = os.environ.get("DISPLAY")
    try:
        free_gb = round(shutil.disk_usage(str(REPO)).free / 2**30, 2)
    except OSError:
        free_gb = None
    uinput = {"path": str(UINPUT), "present": UINPUT.exists(),
              "writable": UINPUT.exists() and os.access(UINPUT, os.W_OK)}
    try:
        st = UINPUT.stat()
        uinput.update({"mode": oct(st.st_mode & 0o777), "gid": st.st_gid})
    except OSError:
        pass
    ptrace = None
    try:
        ptrace = Path("/proc/sys/kernel/yama/ptrace_scope").read_text().strip()
    except OSError:
        pass
    return {"tools": tools, "binaries": probes, "dolphin_version": probes["dolphin-emu"].get("version"),
            "profile_exists": PROFILE.is_dir(),
            "display": {"DISPLAY": disp, "wayland": os.environ.get("WAYLAND_DISPLAY"),
                        "session_type": os.environ.get("XDG_SESSION_TYPE"),
                        "headless": not disp and not os.environ.get("WAYLAND_DISPLAY"),
                        "xvfb_run": bool(shutil.which("xvfb-run"))},
            "uinput": uinput, "yama_ptrace_scope": ptrace,
            "disk_free_gb": free_gb, "repo": str(REPO)}
