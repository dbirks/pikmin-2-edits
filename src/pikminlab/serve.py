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
import hashlib, json, os, signal, socketserver, subprocess, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from .dolphin import (REPO, PROFILE, GC_MAPPING, GC_PAD_INI, default_video_backend,
                      display_env, find_render_window)
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
        self.snaps: dict[str, tuple] = {}
        self.snap_base = 0x80000000
        (PROFILE / "Config" / "GCPadNew.ini").write_text(GC_PAD_INI)
        env = {**display_env(), "SDL_GAMECONTROLLERCONFIG": GC_MAPPING + "\n"}
        # Headless: wrap the DAEMON (`xvfb-run -a uv run pikminlab serve ...`) or
        # pin PIKMINLAB_DISPLAY, so this process AND the emulator child AND the
        # xdotool/magick capture helpers share one DISPLAY. Wrapping only the
        # child cannot work: xvfb-run never tells us the display it chose.
        from .dolphin import _sh
        geo = _sh("xdotool", "getdisplaygeometry", env=env)
        if geo.returncode != 0:
            raise RuntimeError(f"NO_DISPLAY: DISPLAY={env['DISPLAY']!r} unreachable "
                               f"(xdotool: {geo.stderr.strip()[:80]}). Run under xvfb-run.")
        self.proc = subprocess.Popen(
            ["dolphin-emu", "-u", str(PROFILE), "-e", str(iso), "-b",
             "-v", default_video_backend()],
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

    def snap(self, tag: str, start: int = 0x80000000, size: int = 0x2000000) -> dict:
        """Hash guest RAM into a float32 array kept server-side, for diffing.

        Used to DISCOVER the player-position struct empirically (read-only): walk
        once, diff, keep the floats that moved coherently. Traffic stays small
        because only candidates are returned, never the RAM itself.
        """
        import struct
        arr = bytearray()
        CH = 1 << 20
        for off in range(0, size, CH):
            n = min(CH, size - off)
            try:
                arr += bytes.fromhex(self.read(start + off, n))
            except Exception:                     # noqa: BLE001
                arr += b"\x00" * n
        self.snaps[tag] = struct.unpack(f">{len(arr) // 4}f", bytes(arr))
        while len(self.snaps) > 3:                 # ~64 MB per snapshot; keep the last few
            self.snaps.pop(next(iter(self.snaps)))
        self.snap_base = start
        return {"tag": tag, "floats": len(self.snaps[tag])}

    def snap_triples(self, a: str, b: str, mag_max: float = 6000.0,
                     delta_min: float = 0.5, limit: int = 30,
                     mag_min: float = 0.0) -> dict:
        """Consecutive float32 triples where >=2 components moved coherently.

        A position struct is (x,y,z): walking changes x and z a lot and y little,
        so 2-of-3 movement at world-ish magnitudes is a much sharper net than
        "any float that changed" (water, timers and animation curves also move)."""
        import math
        pa, pb = self.snaps.get(a), self.snaps.get(b)
        if not pa or not pb:
            return {"error": "missing snapshot"}
        out = []
        for i in range(0, len(pa) - 3):
            t = pa[i:i + 3]
            if not all(math.isfinite(v) and abs(v) < mag_max for v in t):
                continue
            # A world coordinate lives in the hundreds-to-thousands (forest spans
            # ~±4000); animation/blend structs sit near 0-3 and moved under stick
            # input in the FIRST attempt, masquerading as a position. Without a
            # floor, "some triple changed and came back" is not a position oracle.
            if max(abs(t[0]), abs(t[2])) < mag_min:
                continue
            moved = sum(1 for k in range(3) if abs(pb[i + k] - t[k]) >= delta_min)
            if moved >= 2:
                out.append({"addr": hex(self.snap_base + i * 4),
                            "a": [round(v, 3) for v in t],
                            "b": [round(pb[i + k], 3) for k in range(3)]})
                if len(out) >= limit:
                    break
        return {"triples": out, "count": len(out)}

    def snap_diff(self, a: str, b: str, mag_max: float = 6000.0,
                  delta_min: float = 0.3, delta_max: float = 400.0, limit: int = 40) -> dict:
        import math
        pa, pb = self.snaps.get(a), self.snaps.get(b)
        if not pa or not pb:
            return {"error": "missing snapshot"}
        out = []
        for i in range(0, len(pa) - 1):
            x, y = pa[i], pb[i]
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            if abs(x) > mag_max or abs(y) > mag_max:
                continue
            d = abs(y - x)
            if delta_min <= d <= delta_max:
                out.append({"addr": hex(self.snap_base + i * 4), "a": round(x, 4), "b": round(y, 4)})
                if len(out) >= limit:
                    break
        return {"candidates": out, "count": len(out)}

    def scan(self, values: list[float], tol: float = 1.0, start: int = 0x80000000,
             size: int = 0x2000000, limit: int = 32) -> dict:
        """Search guest RAM for consecutive float32s matching `values`. READ ONLY.

        Why this exists: "did Olimar actually walk from the Day-1 spawn to the
        cave entrance?" is otherwise unobservable from pixels (ADR-0015/0017 — no
        vision model, and animated scenes defeat frame differencing). The goal's
        boundaries allow telemetry for an otherwise-unobservable assertion. This
        never writes memory and never warps the player, so the input-only lane
        stays intact: input still has to do all the moving; the read only *measures*.

        GameCube is big-endian, so `>f` is the expected layout; `struct.pack('>f', v)`
        is also a substring search on the hex string, which avoids decoding 32 MiB
        of RAM per probe.
        """
        import struct
        out = {"big_endian": [], "little_endian": []}
        CH = 1 << 20
        needles = {}
        for label, endian in (("big_endian", ">"), ("little_endian", "<")):
            pats = [struct.pack(f"{endian}f", v).hex() for v in values]
            needles[label] = pats
        step = 4                                  # float32 alignment
        for off in range(0, size, CH):
            n = min(CH, size - off)
            try:
                chunk = bytes.fromhex(self.read(start + off, n)).hex()
            except Exception:                     # noqa: BLE001 - unmapped page
                continue
            for label, pats in needles.items():
                i = chunk.find(pats[0])
                while i >= 0 and len(out[label]) < limit:
                    ok = True
                    if len(pats) > 1:             # consecutive floats within tol
                        for k, pat in enumerate(pats[1:], 1):
                            if chunk[i + k * 8:i + k * 8 + len(pat)] != pat:
                                ok = False
                                break
                    if ok:
                        out[label].append(hex(start + off + i // 2))
                    i = chunk.find(pats[0], i + step * 2)
                if len(out[label]) >= limit:
                    break
            if any(len(v) for v in out.values()):
                break
        return out

    def read_floats(self, addr: int, count: int = 3, endian: str = "big") -> list[float]:
        """Read `count` float32s at addr (for position tracking during a walk)."""
        import struct
        raw = bytes.fromhex(self.read(addr, 4 * count))
        fmt = (">" if endian == "big" else "<") + f"{count}f"
        return [round(v, 4) for v in struct.unpack(fmt, raw)]

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
            if u.path == "/snap":
                return self._send(200, SESSION.snap(body["tag"],
                                                    int(body.get("start", "0x80000000"), 16),
                                                    int(body.get("size", 0x2000000))))
            if u.path == "/snap_triples":
                return self._send(200, SESSION.snap_triples(body["a"], body["b"],
                                                            float(body.get("mag_max", 6000.0)),
                                                            float(body.get("delta_min", 0.5)),
                                                            30, float(body.get("mag_min", 0.0))))
            if u.path == "/snap_diff":
                return self._send(200, SESSION.snap_diff(body["a"], body["b"],
                                                         float(body.get("mag_max", 6000.0)),
                                                         float(body.get("delta_min", 0.3)),
                                                         float(body.get("delta_max", 400.0))))
            if u.path == "/scan":
                vals = [float(v) for v in body["values"]]
                return self._send(200, SESSION.scan(vals, float(body.get("tol", 1.0)),
                                                    int(body.get("start", "0x80000000"), 16),
                                                    int(body.get("size", 0x2000000))))
            if u.path == "/read_floats":
                return self._send(200, {"values": SESSION.read_floats(
                    int(body["addr"], 16), int(body.get("count", 3)), body.get("endian", "big"))})
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
        # The emulator dying on its own (crash, or someone SIGKILLing it) must
        # not leave a daemon holding the one-and-only uinput pad: /state says
        # alive:false, but only stop() closes the pad and reaps the zombie.
        if SESSION and SESSION.proc.poll() is not None:
            SESSION.stop()
            os._exit(1)
        if SESSION and time.monotonic() - SESSION.last_action > SESSION.idle_timeout_s:
            SESSION.stop()
            os._exit(0)


def run(iso: Path, port: int, idle_timeout_s: float = 300) -> int:
    global SESSION
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)  # bind FIRST
    try:
        SESSION = Session(iso, REPO / "reports" / "runs" /
                          (time.strftime("%Y-%m-%dT%H%M%SZ") + "-serve"), idle_timeout_s)
    except Exception:
        httpd.server_close()
        raise

    def _term(signum, frame):
        # A killed daemon must not orphan the emulator: the child would keep the
        # one-and-only uinput pad and the profile. stop() SIGKILLs+reaps it.
        try:
            SESSION.stop()
        finally:
            os._exit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _term)
    threading.Thread(target=idle_watchdog, daemon=True).start()
    with httpd:
        print(json.dumps({"serving": port, "window": SESSION.window,
                          "run_dir": str(SESSION.run_dir)}), flush=True)
        httpd.serve_forever()
    return 0
