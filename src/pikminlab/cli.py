"""pikminlab CLI — machine-readable results on stdout (master spec §10)."""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

from . import dolphin


def _emit(status: str, **fields) -> int:
    print(json.dumps({"status": status,
                      "ts": datetime.now(timezone.utc).isoformat(), **fields}))
    return 0 if status == "PASS" else 1


def cmd_doctor(_: argparse.Namespace) -> int:
    """Read-only environment check. PASS only when the tools exist, actually
    exec, and a render display + uinput are reachable."""
    rep = dolphin.doctor_report()
    problems, warnings = [], []
    for tool in dolphin.REQUIRED_TOOLS:
        if not rep["tools"][tool]:
            problems.append({"code": "TOOL_MISSING", "tool": tool})
    for tool, probe in rep["binaries"].items():
        if probe["path"] and not probe["runnable"]:
            problems.append({"code": "TOOL_BROKEN", "tool": tool, "detail": probe["error"],
                             "hint": "Arch partial upgrade: owner runs 'sudo pacman -Syu'"})
    if rep["display"]["headless"] and not rep["display"]["xvfb_run"]:
        problems.append({"code": "NO_DISPLAY_NO_XVFB",
                         "hint": "install xorg-server-xvfb, launch via PIKMINLAB_XVFB=1"})
    if rep["uinput"]["present"] and not rep["uinput"]["writable"]:
        problems.append({"code": "UINPUT_NOT_WRITABLE", "detail": rep["uinput"],
                         "hint": "owner: udev rule KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\" + usermod -aG input"})
    elif not rep["uinput"]["present"]:
        problems.append({"code": "UINPUT_MISSING", "hint": "modprobe uinput (owner)"})
    if rep["disk_free_gb"] is not None and rep["disk_free_gb"] < 6:
        warnings.append({"code": "LOW_DISK", "disk_free_gb": rep["disk_free_gb"],
                         "hint": "extract+repack lane needs ~3x ISO size"})
    status = "PASS" if not problems else "FAIL"
    return _emit(status, **rep, problems=problems, warnings=warnings)


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


def cmd_extract(args: argparse.Namespace) -> int:
    """Guarded full-tree extract (disk-headroom check lives in buildlane)."""
    from . import buildlane
    try:
        root = buildlane.extract_tree(Path(args.iso).resolve(),
                                       Path(args.dest) if args.dest else None)
    except RuntimeError as exc:            # INSUFFICIENT_DISK
        return _emit("BLOCKED", error=str(exc))
    except subprocess.CalledProcessError as exc:
        return _emit("FAIL", error=f"pyisotools exit {exc.returncode}")
    return _emit("PASS", disc_root=str(root),
                 free_gib_after=round(shutil.disk_usage(str(root)).free / 2**30, 2))


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


def cmd_build(args: argparse.Namespace) -> int:
    """Repack the extracted tree into builds/<name>.iso and record provenance.

    `--lane data` is the only implemented lane: text/asset edits only, never the
    decomp C++ lane. The ISO is gitignored; the *manifest* (hashes, sizes,
    per-file delta) is committed under reports/builds/ so a passing build stays
    traceable without shipping disc bytes (AGENTS.md)."""
    import json
    from . import buildlane, cavebuild
    if args.lane != "data":
        return _emit("NOT_TESTED", lane=args.lane, reason="only --lane data is implemented")
    tree = Path(args.root)
    if not tree.is_dir():
        return _emit("BLOCKED", reason=f"no extract tree at {tree}; run `pikminlab extract`")
    try:
        free = buildlane.require_headroom(tree.parent)
    except RuntimeError as ex:
        return _emit("BLOCKED", reason=str(ex))
    # Guard: a build must carry the design the human thinks it carries. An
    # integration test that restores the tree had silently produced a *pristine*
    # ISO from a patched-looking working directory, so the tree's current hashes
    # are checked against the patch manifests before a single byte is repacked.
    stale = []
    for m in sorted(cavebuild.BACKUP_ROOT.glob("*/manifest.json")):
        mm = json.loads(m.read_text())
        for f in mm["files"]:
            tp = tree / f["path"]
            if not tp.is_file():
                continue
            now = buildlane.sha256(tp.read_bytes())
            if now not in (f["after_sha256"], f["before_sha256"]):
                stale.append({"path": f["path"], "tree_sha256": now[:16]})
            if now == f["before_sha256"]:
                stale.append({"path": f["path"], "state": "design NOT applied (pristine bytes in tree)"})
    if stale and not args.allow_stale:
        return _emit("BLOCKED", stage="pre-build", stale_or_unapplied=stale,
                     hint="run `pikminlab cave apply <design>` (or pass --allow-stale)")

    out = Path(args.out)
    try:
        buildlane.build_iso(tree, out)
    except Exception as ex:                                # noqa: BLE001 - report, don't crash
        return _emit("FAIL", stage="repack", error=f"{type(ex).__name__}: {ex}")
    data = out.read_bytes()
    baseline = Path(args.baseline)
    man = {"iso": str(out), "iso_bytes": len(data), "iso_sha256": buildlane.sha256(data),
           "lane": args.lane, "built_by": "pikminlab build --lane data",
           "baseline_iso": str(baseline) if baseline.is_file() else None,
           "baseline_sha256": buildlane.sha256(baseline.read_bytes()) if baseline.is_file() else None,
           "free_gib_before": round(free / 1024**3, 2),
           "video_backend": "OpenGL under Xvfb (headless, ADR-0014)",
           "source_tree": str(tree)}
    stem = out.stem
    # per-file delta vs baseline comes from the patch manifests the data lane wrote
    delta: list[dict] = []
    for m in sorted(cavebuild.BACKUP_ROOT.glob("*/manifest.json")):
        mm = json.loads(m.read_text())
        for f in mm["files"]:
            if f["before_sha256"] != f["after_sha256"]:
                delta.append({"patched_by": m.parent.name, **{k: f[k] for k in
                            ("path", "before_sha256", "after_sha256", "bytes_before", "bytes_after")}})
    man["file_delta"] = delta
    Path("reports/builds").mkdir(parents=True, exist_ok=True)
    Path(f"reports/builds/{stem}.json").write_text(json.dumps(man, indent=2, sort_keys=True) + "\n")
    return _emit("PASS", stage="repack", iso=str(out), iso_sha256=man["iso_sha256"],
                 iso_bytes=man["iso_bytes"], delta_files=len(delta),
                 baseline_sha256=man["baseline_sha256"], manifest=f"reports/builds/{stem}.json")


def cmd_cave(args: argparse.Namespace) -> int:
    """Author-side cave work: compile a design into the extract tree, validate, undo.

    Everything here is data-lane and reversible: `apply` backs up pristine bytes
    under workspace/cave-patches/, `restore` puts them back. Nothing touches the ISO.
    """
    import json
    from . import cavebuild
    root = Path(args.root)
    design = cavebuild.load(Path(args.design))
    design["_stem"] = Path(args.design).stem
    if not root.is_dir():
        return _emit("BLOCKED", reason=f"extract tree missing: run `pikminlab extract` first ({root})")
    if args.act == "compile":
        patches = cavebuild.compile_design(design, root)
        out = {k: {"sha256": cavebuild.sha256(v), "bytes": len(v)} for k, v in patches.items()}
        if args.out:
            Path(args.out).write_bytes(next(iter(patches.values())))
        return _emit("PASS", design=str(args.design), patches=out)
    if args.act == "validate":
        problems = cavebuild.validate(design, root)
        bad = [p for p in problems if not p["ok"]]
        # validate() reads the TREE. If the design is not applied, its own expects
        # (e.g. treasure totals) fail for that reason alone — say so instead of
        # letting a human read "5 != 6" as a data bug.
        want = cavebuild.compile_design(design, root)
        applied = all((root / k).read_bytes() == v for k, v in want.items())
        return _emit("PASS" if not bad else "FAIL", checks=len(problems), problems=bad,
                     design_applied=applied,
                     hint=None if applied else "design not applied to the tree; run `pikminlab cave apply`")
    if args.act == "apply":
        patches = cavebuild.compile_design(design, root)
        man = cavebuild.apply_patches(root, patches, design["_stem"])
        problems = [p for p in cavebuild.validate(design, root) if not p["ok"]]
        return _emit("PASS" if not problems else "FAIL",
                     manifest=str(cavebuild.BACKUP_ROOT / design["_stem"] / "manifest.json"),
                     files=man["files"], problems=problems)
    if args.act == "restore":
        return _emit("PASS", restored=cavebuild.restore(root, design["_stem"]))
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pikminlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    pi = sub.add_parser("ingest"); pi.add_argument("iso")
    pi.set_defaults(fn=cmd_ingest)
    pe = sub.add_parser("extract")
    pe.add_argument("iso"); pe.add_argument("--dest")
    pe.set_defaults(fn=cmd_extract)
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
    pb = sub.add_parser("build")
    pb.add_argument("--lane", default="data", choices=["data", "decomp"])
    pb.add_argument("--root", default="workspace/extracted/root")
    pb.add_argument("--out", default="builds/lab-cave.iso")
    pb.add_argument("--baseline", default="pikmin2.iso")
    pb.add_argument("--allow-stale", action="store_true",
                    help="build even if the tree does not carry an applied cave design")
    pb.set_defaults(fn=cmd_build)

    pc = sub.add_parser("cave")
    pc.add_argument("act", choices=["compile", "validate", "apply", "restore"])
    pc.add_argument("design")
    pc.add_argument("--root", default="workspace/extracted/root")
    pc.add_argument("--out", default=None)
    pc.set_defaults(fn=cmd_cave)

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
