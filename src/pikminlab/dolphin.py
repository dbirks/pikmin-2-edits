"""Launch/capture/stop recipe for agent-owned Dolphin instances (ADR-0006)."""
from __future__ import annotations
import subprocess, time, shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROFILE = REPO / "runtime" / "dolphin-agent"


def _sh(*cmd: str, timeout: float = 15, env=None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, **kw)


class DolphinSession:
    """One batch-mode instance with guaranteed teardown. Use as a context
    manager: the owner never sees a stranded window."""

    def __init__(self, iso: Path, video_backend: str = "Vulkan"):
        self.iso = iso
        self.video_backend = video_backend
        self.proc: subprocess.Popen | None = None

    def start(self) -> "DolphinSession":
        import os
        env = {**os.environ, "SDL_VIDEODRIVER": "x11", "DISPLAY": ":0"}
        self.proc = subprocess.Popen(
            ["dolphin-emu", "-u", str(PROFILE), "-e", str(self.iso), "-b",
             "-v", self.video_backend],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self

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
