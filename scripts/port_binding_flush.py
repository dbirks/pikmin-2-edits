#!/usr/bin/env python3
"""Ask Dolphin to reveal what it bound Port 1 to, by exiting it politely.

Every previous probe inferred binding state from game behaviour, which the title
screen's animation makes untrustworthy (ADR-0020). Dolphin's own config flush is
direct evidence: on a clean shutdown it rewrites Config/GCPadNew.ini from the devices
it actually enumerated and matched. If the `Device` line survives, Port 1 kept our
string; if it comes back empty/changed, the match failed and every input claim on this
host has been running against an unbound port.

We always SIGKILL in normal operation (guaranteed teardown), but here a TERM first —
then KILL if it lingers — so the config gets flushed. Teardown contract is unchanged:
`/bin/kill -KILL` still runs and `pgrep -x dolphin-emu` must come back empty.

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a uv run python scripts/port_binding_flush.py
"""
from __future__ import annotations
import json, shutil, signal, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import dolphin  # noqa: E402

PROFILE = REPO / "runtime/dolphin-agent"
PAD_INI = PROFILE / "Config/GCPadNew.ini"


def main() -> int:
    iso = REPO / "builds/lab-cave.iso"
    run = REPO / "reports/runs" / (time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()) + "-port-flush")
    run.mkdir(parents=True, exist_ok=True)
    rec: dict = {}
    ses = dolphin.DolphinSession(iso, pad=True)   # writes our template on start()
    template = PAD_INI.read_text()
    rec["template_device_line"] = next(l for l in template.splitlines() if l.startswith("Device"))
    (run / "GCPadNew.template.ini").write_text(template)
    ses.start()
    pid = ses.proc.pid
    rec["pid"] = pid
    try:
        time.sleep(50)                             # enumerate + boot; enough to have matched
        before = PAD_INI.read_text()
        (run / "GCPadNew.during.ini").write_text(before)
        subprocess.run(["/bin/kill", "-TERM", str(pid)])
        t0 = time.time()
        while time.time() - t0 < 25:
            try:
                os_alive = Path(f"/proc/{pid}").exists()
            except OSError:
                os_alive = False
            if not os_alive:
                break
            time.sleep(1)
        rec["exited_cleanly_after_s"] = round(time.time() - t0, 1) if not Path(f"/proc/{pid}").exists() else None
        after = PAD_INI.read_text() if PAD_INI.is_file() else ""
        (run / "GCPadNew.after-flush.ini").write_text(after)
        rec["device_line_after"] = next((l for l in after.splitlines() if l.startswith("Device")), None)
        rec["rewritten_by_dolphin"] = after != before
        rec["sections_after"] = [l for l in after.splitlines() if l.startswith("[")]
        # any other input config Dolphin manages tells the same story
        for other in ("GCKeyNew.ini", "WiimoteNew.ini"):
            p = PROFILE / "Config" / other
            if p.is_file():
                rec[f"{other}_device"] = next((l for l in p.read_text().splitlines()
                                               if l.startswith("Device")), None)
        # An untouched file means NOTHING unless Dolphin actually flushed config on a
        # clean exit; it ignores SIGTERM while emulating, so this oracle usually comes
        # back invalid and must be reported as such instead of as a match (the same
        # trap ADR-0017 fell into with the timed splash).
        flushed = rec["exited_cleanly_after_s"] is not None
        if not flushed:
            rec["verdict"] = ("ORACLE_INVALID: Dolphin ignored SIGTERM, config was never "
                              "rewritten, so the unchanged Device line proves nothing")
        else:
            kept = rec["device_line_after"] == rec["template_device_line"]
            rec["verdict"] = ("DEVICE_STRING_KEPT_BY_DOLPHIN (Port 1 matched our pad)" if kept
                              else "DEVICE_LINE_LOST_OR_REPLACED: " + repr(rec["device_line_after"]))
        rec["log_input_lines"] = []
        if ses.log_path and ses.log_path.is_file():
            rec["log_input_lines"] = [l.strip()[:160] for l in ses.log_path.read_text().splitlines()
                                      if any(k in l.lower() for k in ("input", "sdl", "joystick",
                                                                      "device", "port", "pad"))][:25]
        return 0
    finally:
        subprocess.run(["/bin/kill", "-KILL", str(pid)])
        try:
            ses.proc.wait(timeout=10)
        except Exception:
            pass
        if ses._log_fh:
            ses._log_fh.close()
        (run / "result.json").write_text(json.dumps(rec, indent=2))
        print(json.dumps(rec, indent=1)[:1500])
        print("STRAYS:", subprocess.run(["pgrep", "-x", "dolphin-emu"], capture_output=True)
              .stdout.decode().strip() or "none", "| evidence:", run)


if __name__ == "__main__":
    sys.exit(main())
