#!/usr/bin/env python3
"""Input-only E2E of the authored cave (t5): Day-1 spawn -> f_03 entrance -> floor
transitions -> treasure -> exit, on the built ISO, headless.

No debug warps and no memory writes anywhere in this lane: all movement comes from
the uinput pad. Read-only position telemetry is used for two assertions that pixels
cannot settle on this host (no vision model; animated scenes defeat frame diffing —
ADR-0015/0017): "we are walking" and "we reached the entrance". The float32 struct
is *discovered* from the observed spawn value rather than hardcoded from a symbol
table, and a read is recorded for every walk step, so the trace is auditable.

Stage ladder (each stage's evidence lands in one run dir):
  S1 route      documented new-game route to gameplay
  S2 oracle     locate the position struct at the Day-1 spawn
  S3 calib      measure world delta per stick direction (camera-relative control)
  S4 approach   closed-loop walk to the entrance, logged per step
  S5 enter      A at the entrance; cave-entry = categorical scene collapse
  S6 floors     hunt stairways, count floor transitions
  S7 treasure   pick up / credit a treasure
  S8 exit       leave the cave

  PIKMINLAB_VIDEO_BACKEND=OpenGL xvfb-run -a -s "-screen 0 1280x960x24" \\
    uv run python scripts/e2e_cave_run.py builds/lab-cave.iso
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from pikminlab import frames  # noqa: E402

PORT = int(os.environ.get("PIKMINLAB_PORT", "38471"))
BASE = f"http://127.0.0.1:{PORT}"
SPAWN = (381.724, -70.880, 2634.461)            # forest course `start`, stages.txt
ENTRANCE = (245.330322, 46.056816, 1402.290283)  # f_03 cave-entrance actor, ADR-0018
FULL = 24000
rec: dict = {"spawn": SPAWN, "entrance": ENTRANCE, "trace": [], "shots": [], "stages": []}


def get(path: str, body: dict | None = None, timeout: int = 120) -> dict:
    req = urllib.request.Request(BASE + path,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def stage(name: str, ok: bool, **kw) -> None:
    rec["stages"].append({"stage": name, "ok": bool(ok), **kw})
    print(f"[{name}] {'ok' if ok else 'FAIL'} {json.dumps(kw, default=str)[:180]}", flush=True)


def shoot(name: str, after_s: float = 0.0) -> dict:
    if after_s:
        time.sleep(after_s)
    p = Path(get(f"/screenshot?name={name}")["path"])
    row = {"step": name, "path": str(p), "t": round(time.time() - T0, 1),
           "stats": frames.stats(p), "lit": frames.lit(p)}
    rec["shots"].append(row)
    return row


def btn(name: str, button: str, hold: float = 0.8, after_s: float = 0.0) -> None:
    get("/input", {"button": button, "hold": hold})
    rec["trace"].append({"step": name, "input": {"button": button, "hold": hold},
                         "t": round(time.time() - T0, 1)})
    if after_s:
        time.sleep(after_s)


def stick(name: str, x: int, y: int = 0, hold: float = 0.0) -> None:
    get("/stick", {"x": x, "y": y})
    rec["trace"].append({"step": name, "input": {"stick": [x, y], "hold": hold},
                         "t": round(time.time() - T0, 1)})
    if hold:
        time.sleep(hold)
        get("/stick", {"x": 0, "y": 0})          # neutral release, always
        rec["trace"][-1]["released"] = True
        if hold < 1.0:
            time.sleep(0.4)


def pos() -> list[float] | None:
    if not rec.get("pos_addr"):
        return None
    try:
        return get("/read_floats", {"addr": rec["pos_addr"], "count": 3})["values"]
    except Exception as ex:                       # noqa: BLE001
        rec.setdefault("read_errors", []).append(str(ex))
        return None


def dist(a, b) -> float:
    return (sum((x - y) ** 2 for x, y in zip(a[:3], b[:3]))) ** 0.5


def s1_route() -> bool:
    """Warning -> title -> main menu (documented route, ADR-0011/0012/0014)."""
    shoot("t000-boot", 60)
    btn("warn_start", "START", after_s=18)
    btn("title_start", "START", after_s=18)
    btn("menu_a", "A", after_s=15)
    row = shoot("t005-menu")
    stage("S1_route", bool(row["lit"]), shot=row["path"], stats=row["stats"])
    return bool(row["lit"])


def s1b_new_game() -> bool:
    """Answer the file dialogs blind, with the memory card as the observable.

    This is the step that failed silently on attempts 1-2: the skill says the
    'Create game file?' cursor is NOT where you expect and must be *read*, but this
    host has no vision model and no OCR, so pixels cannot settle it. Instead each
    cursor variant is tried and the CARD is polled — Pikmin 2 writes the file when
    creation succeeds, so a new/changed file under GC/USA/Card A is unambiguous
    proof that we are in a new game (Day 1), not cycling the menu behind an attract
    movie. No new dependency, and read-only on our side.
    """
    before = card_state()
    rec["card_before"] = {k: list(v) for k, v in before.items()}
    variants = {"a_only": [], "up": (0, FULL), "down": (0, -FULL),
                "left": (-FULL, 0), "right": (FULL, 0)}
    for name, nudge in variants.items():
        if nudge:
            stick(f"s1b_nudge_{name}", nudge[0], nudge[1], hold=0.3)
        btn(f"s1b_a_{name}", "A", hold=0.5, after_s=4.0)
        changed = None
        t0 = time.time()
        while time.time() - t0 < 60:
            now = card_state()
            if now != before:
                changed = {k: {"was": list(before.get(k, [0, 0])), "now": list(v)}
                           for k, v in now.items() if before.get(k) != v}
                break
            time.sleep(3)
        row = shoot(f"t006-after-{name}")
        if changed:
            rec["card_change"] = changed
            stage("S1b_new_game", True, variant=name, card_change=changed, shot=row["path"])
            return True
    stage("S1b_new_game", False, tried=list(variants),
          note="no memory-card write from any cursor variant: new game never started")
    return False


def s1c_movies() -> bool:
    """Tap through the Day-1 story movies + ship landing + diagnostics."""
    for i in range(14):
        btn(f"cut_{i}", "A", after_s=8)
    row = shoot("t010-gameplay", 10)
    ok = bool(row["lit"]) and row["stats"].get("colors", 0) > 20000
    stage("S1c_movies", ok, shot=row["path"], stats=row["stats"],
          note="colours>20k = full scene, ~256 = text screen")
    return ok


def s2_oracle() -> bool:
    """Find the position struct: exact triple at the spawn, then per-component
    fallback that re-reads the neighbourhood as (x,y,z)."""
    for body, why in (({"values": list(SPAWN)}, "exact xyz triple"),
                      ({"values": [SPAWN[0]]}, "x component + neighbourhood read")):
        try:
            hits = get("/scan", body, timeout=600)
        except Exception as ex:                     # noqa: BLE001
            stage("S2_oracle", False, error=str(ex)[:160])
            return False
        cand = hits.get("big_endian") or hits.get("little_endian") or []
        rec.setdefault("scan", []).append({"query": body["values"][:1], "why": why,
                                           "big": hits.get("big_endian", [])[:8],
                                           "little": hits.get("little_endian", [])[:8]})
        for label in ("big_endian", "little_endian"):
            for addr in (hits.get(label) or [])[:8]:
                probe = addr if why.startswith("exact") else None
                if probe is None:
                    for delta in (-8, -4, 0):
                        a = hex(int(addr, 16) + delta)
                        vals = get("/read_floats", {"addr": a, "count": 3,
                                                    "endian": "big" if label == "big_endian" else "little"})["values"]
                        if dist(vals, SPAWN) < 1.0:
                            probe = a
                            break
                if probe:
                    rec["pos_addr"], rec["pos_endian"] = probe, label
                    got = pos()
                    ok = dist(got, SPAWN) < 1.5
                    stage("S2_oracle", ok, addr=probe, endian=label, read=got,
                          dist_to_spawn=round(dist(got, SPAWN), 4), method=why)
                    return ok
        if cand:
            continue
    stage("S2_oracle", False, note="no float32 triple near the spawn value",
          scan=rec.get("scan"))
    return False


def snap(tag: str) -> dict:
    return get("/snap", {"tag": tag}, timeout=600)


def triples(a: str, b: str, mag_min: float = 30.0) -> list[dict]:
    """World-scale candidates only (see serve.snap_triples: mag_min filters out the
    0-3 animation structs that produced a false 'live struct' on attempt 2)."""
    return get("/snap_triples", {"a": a, "b": b, "mag_min": mag_min}, timeout=300).get("triples", [])


def card_state() -> dict:
    """Memory-card files as an oracle for 'did a game actually start'.

    Pikmin 2 writes the card on save and on 'Create game file?'; the answer to that
    dialog cannot be read from pixels here (no vision, no OCR installed), so the
    filesystem is the observable. No new dependency, read-only."""
    d = REPO / "runtime/dolphin-agent/GC/USA/Card A"
    return {p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(d.glob("*")) if p.is_file()}


def s3_calibrate(rounds: int = 8) -> bool:
    """Prove control and stick locomotion, then calibrate the four directions.

    Two things get conflated on this host, so both are measured separately:
      * is the game handing control to the player at all? (Day-1 has two dialogs
        whose cursor must be read, then 2-3 min of movies — ADR-0017's route note)
      * does the stick move the *player*, and is the struct we found the live one?
        The float triple that matched stages.txt's spawn could be a course-start
        literal rather than the player, so the live struct is adopted only from a
        triple that MOVES on stick input and then COMES BACK when it is reversed.

    Reversal is the oracle: on an animated scene no pixel metric can attribute a
    change to a button (ADR-0015), but position +x then -x returning to the start
    is self-cancelling, so residual drift proves the stick did the moving.
    """
    spawn_struct_moved = False
    for r in range(rounds):
        snap("A")
        stick(f"handover_{r}_up", 0, FULL, hold=3.5)
        snap("B")
        cands = triples("A", "B")
        if rec.get("pos_addr"):
            a0 = get("/read_floats", {"addr": rec["pos_addr"], "count": 3})["values"]
            spawn_struct_moved = dist(a0, SPAWN) > 0.5
        if cands:
            for c in cands[:6]:
                moved = dist(c["a"], c["b"])
                if moved < 0.8:
                    continue
                stick(f"rev_{r}", 0, -FULL, hold=3.5)             # equal and opposite
                snap("C")
                now = get("/read_floats", {"addr": c["addr"], "count": 3})["values"]
                residual = dist(now, c["a"])
                # third property: a *second* forward push must move again, so a
                # one-shot scripted camera/anim ramp cannot masquerade as control
                stick(f"again_{r}", 0, FULL, hold=2.5)
                again = get("/read_floats", {"addr": c["addr"], "count": 3})["values"]
                removed = dist(again, now)
                row = {"addr": c["addr"], "moved": round(moved, 3),
                       "after_reverse": [round(v, 3) for v in now], "start": c["a"],
                       "residual": round(residual, 3), "moved_again": round(removed, 3),
                       "magnitude": round(max(abs(c["a"][0]), abs(c["a"][2])), 1)}
                if residual < moved * 0.25 and removed > 0.3:      # ours: reversible + live
                    rec["pos_addr"] = c["addr"]
                    rec["live_struct"] = row
                    cal = {"up": {"from": c["a"], "to": c["b"],
                                  "delta": [round(y - x, 3) for x, y in zip(c["a"], c["b"])],
                                  "moved": True}}
                    for name, (x, y) in {"down": (0, -FULL), "left": (-FULL, 0),
                                         "right": (FULL, 0)}.items():
                        a = pos()
                        stick(f"cal_{name}", x, y, hold=1.6)
                        b = pos()
                        cal[name] = {"from": a, "to": b,
                                     "delta": [round(q - w, 3) for q, w in zip(b, a)],
                                     "moved": dist(a, b) > 0.4}
                        time.sleep(0.5)
                    rec["calib"] = cal
                    stage("S3_calibrate", len([k for k, v in cal.items() if v["moved"]]) >= 2,
                          live_struct=row, round=r, spawn_struct_moved=spawn_struct_moved,
                          deltas={k: v["delta"] for k, v in cal.items()},
                          moved=[k for k, v in cal.items() if v["moved"]])
                    return len([k for k, v in cal.items() if v["moved"]]) >= 2
                rec.setdefault("reversal_rejects", []).append(row)
        else:
            btn(f"handover_{r}_a", "A", hold=0.6, after_s=6.0)    # dialog / movie skip
            shoot(f"t011-handover{r}")
    stage("S3_calibrate", False, rounds=rounds, spawn_struct_moved=spawn_struct_moved,
          reversal_rejects=rec.get("reversal_rejects", [])[:4],
          note="no float triple moved-and-returned under stick input: control not handed over")
    return False


def s4_approach(max_steps: int = 90) -> bool:
    """Closed-loop walk: pick the measured stick direction whose delta best aligns
    with the remaining offset to the entrance, re-measuring every 12 steps (the
    camera swings as we travel)."""
    cal = {k: v["delta"] for k, v in rec.get("calib", {}).items() if v["moved"]}
    p = pos()
    if not cal or p is None:
        stage("S4_approach", False, note="no calibration/oracle")
        return False
    stuck, i, best = 0, 0, dist(p, ENTRANCE)
    while i < max_steps:
        i += 1
        off = [ENTRANCE[j] - p[j] for j in range(3)]
        remaining = dist(p, ENTRANCE)
        # score each calibrated direction by projection onto the needed offset
        def score(name):
            d = cal[name]
            n = (d[0] ** 2 + d[2] ** 2) ** 0.5 or 1.0
            return (d[0] * off[0] + d[2] * off[2]) / n
        order = sorted(cal, key=score, reverse=True)
        pick = order[0] if score(order[0]) > 0.2 else order[-1]
        vec = {"up": (0, FULL), "down": (0, -FULL), "left": (-FULL, 0), "right": (FULL, 0)}[pick]
        hold = 1.6 if remaining > 120 else 0.8
        stick(f"walk_{i:03d}_{pick}", vec[0], vec[1], hold=hold)
        q = pos()
        gain = dist(q, p)
        rec["trace"][-1].update({"pos": q, "dist_to_entrance": round(remaining, 1),
                                 "moved": round(gain, 3)})
        if remaining < best * 0.98:
            best, stuck = remaining, 0
        elif gain < 0.4:
            stuck += 1
        p = q
        if i % 15 == 0:
            shoot(f"t020-walk{i:03d}")
        if remaining < 30:
            shoot("t025-near-entrance")
            stage("S4_approach", True, steps=i, dist=round(remaining, 1),
                  start_to_entrance_note="closed-loop, telemetry-confirmed")
            return True
        if stuck >= 8:
            shoot(f"t022-stuck{i:03d}")
            stage("S4_approach", False, steps=i, dist=round(remaining, 1), stuck_in_a_row=stuck,
                  note="terrain/wall: 8 consecutive non-moving steps")
            return False
    stage("S4_approach", False, steps=i, dist=round(dist(p, ENTRANCE), 1), note="step budget")
    return False


def collapse(before: dict, after: dict) -> bool:
    """Categorical scene change: a loading/text screen collapses the palette."""
    return (before.get("colors", 0) > 5000 and after.get("colors", 0) < 1000) or \
           abs(before.get("mean", 0) - after.get("mean", 0)) > 0.15


def s5_enter() -> bool:
    a = shoot("t030-pre-enter")
    for i in range(6):
        btn(f"enter_a_{i}", "A", hold=0.6, after_s=4.0)
        b = shoot(f"t031-enter{i}")
        if collapse(a["stats"], b["stats"]):
            time.sleep(25)                                    # cave load (llvmpipe)
            c = shoot(f"t032-cave{i}")
            rec["cave_entry"] = {"press": i, "collapsed_at": b["path"], "first_cave_frame": c["path"]}
            stage("S5_enter", bool(c["lit"]), presses=i + 1, before=a["stats"],
                  collapse_at=b["stats"], first_cave=c["stats"])
            return True
    stage("S5_enter", False, note="no scene collapse from 6 A presses near the actor position")
    return False


def s6_floors(limit: int = 10) -> bool:
    """Descend: sweep directions and tap A; a floor change is another categorical
    collapse followed by a new rendered scene."""
    transitions = []
    cur = shoot("t040-cave-floor1", 5)
    seq = [(0, FULL), (FULL, 0), (0, -FULL), (-FULL, 0)]
    k = 0
    while len(transitions) < 2 and k < limit * 4:
        k += 1
        x, y = seq[k % 4]
        stick(f"cave_{k:02d}", x, y, hold=1.8)
        btn(f"cave_{k:02d}_a", "A", hold=0.5, after_s=2.0)
        shot = shoot(f"t041-cave{k:02d}")
        if collapse(cur["stats"], shot["stats"]):
            time.sleep(20)
            nxt = shoot(f"t042-after{k:02d}")
            transitions.append({"at_step": k, "collapse": shot["path"], "floor_frame": nxt["path"],
                                "before": cur["stats"], "after": nxt["stats"]})
            cur = nxt
            limit = max(limit, k + 10)
        if k > limit:
            break
    rec["floor_transitions"] = transitions
    stage("S6_floors", len(transitions) >= 2, transitions=len(transitions),
          at=[t["at_step"] for t in transitions])
    return len(transitions) >= 2


def s7_treasure(limit: int = 24) -> bool:
    """Sweep for a reachable treasure and take it. Credit evidence is the
    obtain/registry screen, which is text-on-dark => palette collapse + settle."""
    seen = []
    cur = shoot("t050-pre-treasure")
    for i in range(limit):
        x, y = [(0, FULL), (FULL, FULL), (FULL, 0), (-FULL, FULL)][i % 4]
        stick(f"tr_{i:02d}", x, y, hold=1.4)
        btn(f"tr_{i:02d}_a", "A", hold=0.6, after_s=3.0)
        shot = shoot(f"t051-tr{i:02d}")
        seen.append(shot["stats"])
        if collapse(cur["stats"], shot["stats"]) and shot["stats"].get("colors", 0) < 1000:
            time.sleep(8)
            after = shoot(f"t052-tr{i:02d}-settle")
            rec["treasure"] = {"at_step": i, "screen": shot["path"], "settled": after["path"],
                               "screen_stats": shot["stats"], "settled_stats": after["stats"]}
            stage("S7_treasure", True, at_step=i, screen=shot["path"])
            return True
        cur = shot
    stage("S7_treasure", False, note="no obtain screen in sweep", samples=len(seen))
    return False


def s8_exit() -> bool:
    """Leave the cave: the return fountain (f007, which this build also adds to
    floor 1) or the floor-1 exit doorway. Success = we are back in the overworld,
    proven by the position oracle returning near the entrance actor."""
    cur = shoot("t060-pre-exit")
    for i in range(20):
        x, y = [(0, -FULL), (-FULL, 0), (0, FULL), (FULL, 0)][i % 4]
        stick(f"ex_{i:02d}", x, y, hold=1.6)
        btn(f"ex_{i:02d}_a", "A", hold=0.6, after_s=3.0)
        shot = shoot(f"t061-ex{i:02d}")
        if collapse(cur["stats"], shot["stats"]):
            time.sleep(20)
            back = shoot("t062-back-outside")
            p = pos()
            near = p and dist(p, ENTRANCE) < 400
            rec["exit"] = {"at_step": i, "collapse": shot["path"], "outside": back["path"],
                           "pos_after": p, "near_entrance": bool(near)}
            stage("S8_exit", bool(back["lit"] and near), pos=p,
                  dist_to_entrance=round(dist(p, ENTRANCE), 1) if p else None)
            return bool(back["lit"] and near)
        cur = shot
    stage("S8_exit", False, note="no exit scene change in sweep")
    return False


def main() -> int:
    global T0
    iso = (REPO / (sys.argv[1] if len(sys.argv) > 1 else "builds/lab-cave.iso")).resolve()
    limit = int(os.environ.get("E2E_MAX_STEPS", "90"))
    stage_limit = os.environ.get("E2E_STOP_AFTER")            # e.g. "S3_calibrate"
    run = REPO / "reports" / "runs" / (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ") + "-e2e-cave")
    run.mkdir(parents=True, exist_ok=True)
    rec.update(iso=str(iso), iso_sha256=__import__("hashlib").sha256(iso.read_bytes()).hexdigest())
    dlog = open(run / "serve.log", "w")
    daemon = subprocess.Popen(["uv", "run", "pikminlab", "serve", str(iso), "--port", str(PORT),
                               "--idle", "1200"], stdout=dlog, stderr=subprocess.STDOUT, cwd=REPO)
    code = 2
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                if get("/state", timeout=10).get("alive"):
                    break
            except Exception:
                pass
            if daemon.poll() is not None:
                break
            time.sleep(3)
        st = get("/state", timeout=20)
        rec["disc_id"] = st.get("disc_id")
        T0 = time.time()
        ladder = [(s1_route, "S1_route"), (s1b_new_game, "S1b_new_game"), (s1c_movies, "S1c_movies"),
                  (s2_oracle, "S2_oracle"), (s3_calibrate, "S3_calibrate"),
                  (lambda: s4_approach(limit), "S4_approach"), (s5_enter, "S5_enter"),
                  (s6_floors, "S6_floors"), (s7_treasure, "S7_treasure"), (s8_exit, "S8_exit")]
        done = {}
        for fn, name in ladder:
            try:
                done[name] = fn()
            except Exception as ex:                             # noqa: BLE001
                done[name] = False
                rec.setdefault("errors", []).append({"stage": name, "error": f"{type(ex).__name__}: {ex}"[:200]})
                stage(name, False, exception=f"{type(ex).__name__}: {ex}"[:160])
            if not done[name] or name == stage_limit:
                break
        reached = [n for n, okv in done.items() if okv]
        rec["reached"] = reached
        rec["status"] = ("PASS" if all(done.get(n) for _, n in ladder)
                         else "PARTIAL" if reached else "FAIL")
        code = 0 if rec["status"] == "PASS" else 1
    finally:
        try:
            get("/stop", {}, timeout=30)
        except Exception as ex:                                 # noqa: BLE001
            rec["stop_error"] = str(ex)[:120]
        subprocess.run(["/bin/kill", "-KILL", str(daemon.pid)], capture_output=True)
        rec["stray_pids"] = [p for p in subprocess.run(["pgrep", "-x", "dolphin-emu"],
                                                       capture_output=True, text=True).stdout.split()]
        (run / "result.json").write_text(json.dumps(rec, indent=2, default=str))
        print(json.dumps({k: rec.get(k) for k in ("status", "reached", "disc_id", "iso_sha256",
                                                  "stray_pids")}, default=str))
        print("result:", run / "result.json")
    return code


T0 = time.time()
if __name__ == "__main__":
    sys.exit(main())
