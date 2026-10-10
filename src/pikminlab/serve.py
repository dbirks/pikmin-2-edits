"""pikminlab serve — a persistent, agent-driveable Dolphin session daemon.

Playwright-style: one long-lived process owns the game child + virtual GC
pad + memory reader and exposes a localhost JSON API. Each CLI call is a
discrete action; the agent (me) can screenshot, *look* at the image with my
vision tools, then decide the next input — real closed-loop exploration
instead of pre-scripted state machines.

API (JSON over http://127.0.0.1:<port>):
  GET  /state                 -> {alive, window, disc_id, scene_sha, ts}
  GET  /screenshot[?name=x]   -> writes PNG, returns {path, sha}
  POST /input  {button, hold} -> presses a GC button (A/B/X/Y/START/...)
  POST /stick  {x, y}         -> main-stick vector (-32767..32767), 0,0 to release
  POST /read   {addr, size}   -> hex dump of emulated MEM1
  POST /frame  {n}            -> advance n frames (if backend supports; else timed wait)
  POST /stop                  -> SIGKILL dolphin, close pad, daemon exits
The daemon also auto-exits after `idle_timeout_s` of inactivity (safety).
"""
from __future__ import annotations
import hashlib, json, os, socketserver, subprocess, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from .dolphin import REPO, PROFILE, GC_MAPPING, GC_PAD_INI, find_render_window
from .vpad import VirtualPad

GC_BUTTON_MAP = None  # populated lazily (evdev import)


def _btn_map():
    global GC_BUTTON_MAP
    if GC_BUTTON_MAP is None:
        from evdev import ecodes as e
        GC_BUTTON_MAP = {"A": e.BTN_SOUTH, "B": e.BTN_EAST, "X": e.BTN_NORTH,
                         "Y": e.BTN_WEST, "L": e.BTN_TL, "R": e.BTN_TR,
                         "Z": e.BTN_MODE, "START": e.BTN_START,
                         "SELECT": e.BTN_SELECT}
    return GC_BUTTON_MAP


class Session:
    """The single owned Dolphin + pad + memory handle."""
    def __init__(self, iso: Path, run_dir: Path, idle_timeout_s: float):
        self.iso, self.run_dir = iso, run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.pad = VirtualPad()
        (PROFILE / "Config" / "GCPadNew.ini").write_text(GC_PAD_INI)
        import os
        env = {**os.environ, "SDL_VIDEODRIVER": "x11", "DISPLAY": ":0",
               "SDL_GAMECONTROLLERCONFIG": GC_MAPPING + "\n"}
        self.proc = subprocess.Popen(
            ["dolphin-emu", "-u", str(PROFILE), "-e", str(iso), "-b", "-v", "Vulkan"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.window = ""
        for _ in range(30):
            self.window = find_render_window()
            if self.window: break
            time.sleep(2)
        self.last_action = time.monotonic()
        self.idle_timeout_s = idle_timeout_s
        self._lock = threading.Lock()
        self.alive = True

    def touch(self): self.last_action = time.monotonic()

    def screenshot(self, name: str) -> Path:
        import subprocess as sp
        dest = self.run_dir / f"{name}.png"
        sp.run(["magick", "import", "-window", self.window, str(dest)], timeout=20)
        return dest

    def input_button(self, button: str, hold: float) -> None:
        b = _btn_map()[button.upper()]
        self.pad.button(b, True); time.sleep(hold); self.pad.button(b, False)

    def stick(self, x: int, y: int) -> None:
        from evdev import ecodes as e
        self.pad.stick(e.ABS_X, e.ABS_Y, x, y)

    def read(self, addr: int, size: int) -> str:
        import dolphin_memory_engine as dme
        if not dme.is_hooked():
            dme.hook()
        return dme.read_bytes(addr, size).hex()

    def scene_sha(self) -> str:
        try:
            return hashlib.sha256(self.read(0x80000000, 6)).hexdigest()[:12]
        except Exception:
            return "-"

    def stop(self):
        if not self.alive:
            return
        self.alive = False
        try:
            import dolphin_memory_engine as dme
            if dme.is_hooked(): dme.un_hook()
        except Exception:
            pass
        try: self.pad.close()
        except Exception: pass
        try: self.proc.kill(); self.proc.wait(timeout=10)
        except Exception: pass


SESSION: Session | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        global SESSION
        u = urllib.parse.urlparse(self.path)
        if SESSION is None or not SESSION.alive:
            return self._send(503, {"error": "no session"})
        SESSION.touch()
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/state":
            return self._send(200, {"alive": SESSION.proc.poll() is None,
                                    "window": SESSION.window,
                                    "disc_id": SESSION.read(0x80000000, 6) if SESSION.window else "-"})
        if u.path == "/screenshot":
            p = SESSION.screenshot(q.get("name", ["shot"])[0])
            return self._send(200, {"path": str(p),
                                    "sha": hashlib.sha256(p.read_bytes()).hexdigest()[:12]})
        return self._send(404, {"error": "unknown"})

    def do_POST(self):
        global SESSION
        u = urllib.parse.urlparse(self.path)
        if SESSION is None:
            return self._send(503, {"error": "no session"})
        body = self._body()
        if u.path == "/stop":
            SESSION.stop()
            self._send(200, {"stopped": True})
            threading.Thread(target=_shutdown_server, daemon=True).start()
            return
        if not SESSION.alive:
            return self._send(503, {"error": "session ended"})
        SESSION.touch()
        try:
            if u.path == "/input":
                SESSION.input_button(body["button"], float(body.get("hold", 0.1)))
                return self._send(200, {"ok": True})
            if u.path == "/stick":
                SESSION.stick(int(body["x"]), int(body["y"]))
                return self._send(200, {"ok": True})
            if u.path == "/read":
                return self._send(200, {"hex": SESSION.read(int(body["addr"], 16),
                                                            int(body["size"]))})
            if u.path == "/frame":
                time.sleep(float(body.get("n", 1)) / 60.0)  # timed wait (no frame-advance in mainline)
                return self._send(200, {"ok": True, "approx_frames": body.get("n")})
        except Exception as ex:
            return self._send(500, {"error": f"{type(ex).__name__}: {ex}"})
        return self._send(404, {"error": "unknown"})


def _shutdown_server():
    time.sleep(0.2)
    import os
    os._exit(0)


def idle_watchdog():
    while SESSION and SESSION.alive:
        time.sleep(5)
        if SESSION and time.monotonic() - SESSION.last_action > SESSION.idle_timeout_s:
            SESSION.stop()
            os._exit(0)


def run(iso: Path, port: int, idle_timeout_s: float = 300) -> int:
    global SESSION
    SESSION = Session(iso, REPO / "reports" / "runs" /
                      (time.strftime("%Y-%m-%dT%H%M%SZ") + "-serve"), idle_timeout_s)
    threading.Thread(target=idle_watchdog, daemon=True).start()
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as httpd:
        print(json.dumps({"serving": port, "window": SESSION.window,
                          "run_dir": str(SESSION.run_dir)}), flush=True)
        httpd.serve_forever()
    return 0
