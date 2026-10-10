"""pikminlab CLI — machine-readable results on stdout (master spec §10)."""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

from . import dolphin


def _emit(status: str, **fields) -> int:
    print(json.dumps({"status": status,
                      "ts": datetime.now(timezone.utc).isoformat(), **fields}))
    return 0 if status == "PASS" else 1


def cmd_doctor(_: argparse.Namespace) -> int:
    rep = dolphin.doctor_report()
    missing = [k for k, v in rep["tools"].items() if not v]
    return _emit("PASS" if not missing else "FAIL", **rep, missing_tools=missing)


def cmd_ingest(args: argparse.Namespace) -> int:
    p = Path(args.iso)
    if not p.is_file():
        return _emit("FAIL", error="INVALID_DISC", path=str(p))
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    head = p.open("rb").read(32)
    game_id = head[:6].decode("ascii", "replace").rstrip("\x00")
    return _emit("PASS", path=str(p), size=p.stat().st_size,
                 sha256=h.hexdigest(), game_id=game_id,
                 note="source treated as immutable; verify with dolphin-tool")


def cmd_probe(args: argparse.Namespace) -> int:
    """Scripted open -> keys -> captures -> guaranteed close (<= cap_s)."""
    run_dir = Path("reports/runs") / (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ") + "-probe")
    keys = args.keys.split(",")
    shots: dict[str, str | None] = {}
    with dolphin.DolphinSession(Path(args.iso)) as ses:
        wid = ses.window_id(wait_s=args.cap_s // 3)
        if not wid:
            return _emit("BLOCKED", error="DRIVER_DISCONNECTED", reason="no render window")
        shots["t0"] = str(run_dir / "t0.png") if ses.capture(wid, run_dir / "t0.png") else None
        for i, k in enumerate(keys, 1):
            ses.press(wid, k.strip())
            import time; time.sleep(args.dwell)
            d = run_dir / f"after{i}_{k.strip()}.png"
            shots[f"after{i}"] = str(d) if ses.capture(wid, d) else None
    ok = [v for v in shots.values() if v]
    import hashlib
    hashes = {k: hashlib.sha256(Path(v).read_bytes()).hexdigest()[:12]
              for k, v in shots.items() if v}
    changed = len(set(hashes.values())) > 1
    return _emit("PASS" if changed else "FAIL", run_dir=str(run_dir),
                 window=wid, captures=hashes,
                 input_causes_scene_change=changed)


def cmd_state(args: argparse.Namespace) -> int:
    """Read known emulated-memory facts from a live session (driver-B proof)."""
    out = []
    with dolphin.DolphinSession(Path(args.iso)) as ses:
        wid = ses.window_id(wait_s=args.cap_s // 3)
        if not wid:
            return _emit("BLOCKED", error="DRIVER_DISCONNECTED", reason="no render window")
        did = ses.memory_read(0x80000000, 6)
        out.append({"addr": "0x80000000", "value": did.decode("ascii", "replace")})
        ok = did == b"GPVE01"
    return _emit("PASS" if ok else "FAIL", window=wid, reads=out,
                 expected="GPVE01", got=did.decode("ascii", "replace"))


def cmd_serve(args: argparse.Namespace) -> int:
    from . import serve
    return serve.run(Path(args.iso), args.port, args.idle)


def _drive(args: argparse.Namespace) -> int:
    import json as _json, urllib.request
    base = f"http://127.0.0.1:{args.port}"
    if args.act == "state":
        req = urllib.request.Request(base + "/state")
    elif args.act == "shot":
        req = urllib.request.Request(base + f"/screenshot?name={args.name or 'shot'}")
    else:
        payload = {"input": {"button": args.button, "hold": args.hold},
                   "stick": {"x": args.x, "y": args.y},
                   "read": {"addr": args.addr, "size": args.size},
                   "stop": {}}[args.act]
        req = urllib.request.Request(base + "/" + args.act,
                                     data=_json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(_json.load(r))
        return 0
    except Exception as ex:
        print({"status": "FAIL", "error": str(ex)})
        return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pikminlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    pi = sub.add_parser("ingest"); pi.add_argument("iso")
    pi.set_defaults(fn=cmd_ingest)
    pp = sub.add_parser("probe")
    pp.set_defaults(fn=cmd_probe)
    pp.add_argument("iso")
    pp.add_argument("--keys", default="Return,Return,x",
                    help="comma-separated xdotool keysyms sent in order")
    pp.add_argument("--dwell", type=float, default=3.0)
    pp.add_argument("--cap-s", type=int, default=60, help="hard session cap")
    ps = sub.add_parser("state")
    ps.add_argument("iso")
    ps.add_argument("--cap-s", type=int, default=60)
    ps.set_defaults(fn=cmd_state)
    sv = sub.add_parser("serve")
    sv.add_argument("iso"); sv.add_argument("--port", type=int, default=38471)
    sv.add_argument("--idle", type=float, default=300)
    sv.set_defaults(fn=cmd_serve)
    dv = sub.add_parser("drive")
    dv.add_argument("act", choices=["state", "shot", "input", "stick", "read", "stop"])
    dv.add_argument("--port", type=int, default=38471)
    dv.add_argument("--button"); dv.add_argument("--hold", type=float, default=0.1)
    dv.add_argument("--x", type=int, default=0); dv.add_argument("--y", type=int, default=0)
    dv.add_argument("--addr", default="0x80000000"); dv.add_argument("--size", type=int, default=6)
    dv.add_argument("--name")
    dv.set_defaults(fn=_drive)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
