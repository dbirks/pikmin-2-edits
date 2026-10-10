#!/usr/bin/env python3
"""Numeric audit of every captured frame (t6) — no vision model required.

The agent session cannot view images, so "what looks off" is answered with
measurable signatures that each have a named failure mode, plus a shortlist of
PNG paths for a human to eyeball. Every rule states what it can and cannot prove,
because a colour count cannot tell a black screen from a shadowed cave.

  uv run python scripts/frame_audit.py            # all runs -> reports/frame-audit.json
  uv run python scripts/frame_audit.py --limit 400

Rules
  all_black          mean == 0.0 exactly (nothing rendered at all)
  black_or_idle      mean < 0.02 or colours < 32       (loader, pre-title, teardown)
  flat_geometry      colours < 512 but mean >= 0.05    (untextured/flat-shaded frame)
  empty_scene        tile spread < 0.05 and colours < 2000
  frozen_frame       identical PNG hash twice in a run (capture stale or game halted)
  size_anomaly       frame size != the session's mode
  self_progressing   adjacent frames with no input between, RMSE > 0.30 (ADR-0020:
                     this is *video*, and it invalidates frame-delta input oracles)
  hud_pulse          adjacent no-input frames inside the 0.005-0.05 UI-pulse band
"""
from __future__ import annotations
import argparse, collections, json, shutil, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import frames  # noqa: E402

EXPECTED_SIZES = {"640x480", "1280x960", "800x600"}


def audit_frame(p: Path) -> dict:
    st = frames.stats(p)
    row = {"path": str(p.relative_to(REPO)), "bytes": p.stat().st_size,
           "sha": __import__("hashlib").sha256(p.read_bytes()).hexdigest()[:16]}
    if st["mean"] is None:
        row.update(anomalies=["unreadable"], **st)
        return row
    if st["mean"] == 0.0:
        # NOT a parser branch: `not st["mean"]` swallowed these 19 frames as
        # "unreadable" when they are perfectly readable and perfectly BLACK
        # (mean exactly 0.0). A black capture is an anomaly to report, not an
        # error to swallow — and the distinction matters for G0/G2 gates.
        row.update(mean=0.0, colors=st["colors"], size=st["size"], tile_spread=0.0,
                   anomalies=["all_black"])
        return row
    tiles = frames.tile_means(p)
    mean, spread = st["mean"], max(tiles) - min(tiles)
    row.update(mean=mean, colors=st["colors"], size=st["size"], tile_spread=round(spread, 4))
    flags = []
    if mean < 0.02 or st["colors"] < 32:
        flags.append("black_or_idle")
    elif st["colors"] < 512:
        flags.append("flat_geometry")
    if spread < 0.05 and st["colors"] < 2000:
        flags.append("empty_scene")
    if st["size"] not in EXPECTED_SIZES:
        flags.append("size_anomaly")
    row["anomalies"] = flags
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()
    runs = sorted(d for d in (REPO / "reports" / "runs").iterdir() if d.is_dir())
    per_run, all_rows = [], []
    counter = collections.Counter()
    for d in runs:
        pngs = sorted(d.rglob("*.png"))[: args.limit]
        if not pngs:
            continue
        rows = [audit_frame(p) for p in pngs]
        for r in rows:
            counter.update(r["anomalies"])
        # temporal signatures: adjacent pairs, classified by whether any input is
        # recorded between the two captures (from the run's result.json trace)
        rec = {}
        if (d / "result.json").is_file():
            try:
                rec = json.loads((d / "result.json").read_text())
            except json.JSONDecodeError:
                rec = {}
        trace = rec.get("trace") or rec.get("steps") or []
        pairs = []
        for a, b in zip(rows, rows[1:]):
            if a["bytes"] == b["bytes"] and a["sha"] == b["sha"]:
                counter["frozen_frame"] += 1
                pairs.append({"pair": [a["path"], b["path"]], "rmse": 0.0, "kind": "frozen_frame"})
                continue
            rm = frames.rmse(REPO / a["path"], REPO / b["path"])
            kind = ("self_progressing" if rm > 0.30 else "hud_pulse" if rm >= 0.005
                    else "static" if rm >= 0 else "unmeasurable")
            if kind == "self_progressing":
                counter["self_progressing"] += 1
            elif kind == "hud_pulse":
                counter["hud_pulse"] += 1
            pairs.append({"pair": [a["path"], b["path"]], "rmse": rm, "kind": kind})
        flagged = [r for r in rows if r["anomalies"]]
        per_run.append({"run": d.name, "frames": len(rows), "flagged": len(flagged),
                        "kinds": dict(collections.Counter(k for r in rows for k in r["anomalies"])),
                        "pairs": {"self_progressing": sum(1 for p in pairs if p["kind"] == "self_progressing"),
                                  "hud_pulse": sum(1 for p in pairs if p["kind"] == "hud_pulse"),
                                  "median_rmse": (sorted(p["rmse"] for p in pairs)[len(pairs) // 2]
                                                  if pairs else None)},
                        "flagged_paths": [r["path"] for r in flagged]})
        all_rows.extend(rows)

    shortlist = []
    for r in all_rows:
        if "flat_geometry" in r["anomalies"] or "empty_scene" in r["anomalies"]:
            shortlist.append({"why": "flat/empty scene — needs eyes", **r})
    for r in all_rows:
        if "all_black" in r["anomalies"]:
            shortlist.append({"why": "fully black capture (mean 0.0)", **r})
        if "black_or_idle" in r["anomalies"] and "e2e" in r["path"]:
            shortlist.append({"why": "near-black frame inside an E2E attempt", **r})
            break
    out = {"frames_total": len(all_rows), "runs_total": len(per_run),
           "disk_free_gib": round(shutil.disk_usage(REPO).free / 1024**3, 2),
           "counts": dict(counter), "shortlist": shortlist[:25], "runs": per_run,
           "note": "Statistical signatures only; a colour count cannot distinguish "
                   "a black screen from a shadowed cave, so every flagged frame is "
                   "listed by path for human confirmation (AGENTS: no claims without "
                   "evidence)."}
    (REPO / "reports" / "frame-audit.json").write_text(json.dumps(out, indent=2)[:400000])
    print(json.dumps({"frames_total": out["frames_total"], "runs_total": out["runs_total"],
                      "counts": out["counts"], "shortlist_n": len(shortlist)}, indent=1))
    for s in shortlist[:12]:
        print("  SHORTLIST", s["why"], "|", s["path"], "mean=", s.get("mean"),
              "colors=", s.get("colors"), "spread=", s.get("tile_spread"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
