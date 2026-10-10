"""Passed-build manifest is immutable per hash and `play` verifies before launching."""
import hashlib, json
from pathlib import Path

import pytest

from pikminlab import cli


class A:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
def pinned(tmp_path, monkeypatch, capsys):
    iso = tmp_path / "build.iso"
    iso.write_bytes(b"GC-ISO-ish" * 100)
    ev = tmp_path / "evidence.json"
    ev.write_text("{}")
    monkeypatch.setattr(cli, "PIN_FILE", tmp_path / "last-passing.json")
    rc = cli.cmd_pin(A(build=str(iso), level="boot", evidence=[str(ev)], note="n"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == "PASS" and out["verified_level"] == "boot"
    sha = json.loads(cli.PIN_FILE.read_text())["entries"][0]["sha256"]
    return tmp_path, iso, ev, sha


def test_manifest_records_hash_and_evidence(pinned):
    tmp, iso, ev, sha = pinned
    man = json.loads(cli.PIN_FILE.read_text())
    ent = man["last_passing"]
    assert ent["sha256"] == hashlib.sha256(iso.read_bytes()).hexdigest()
    assert ent["bytes"] == iso.stat().st_size
    assert str(ev) in ent["evidence"]
    assert ent["verified_level"] == "boot"          # never inflated to "play"


def test_repinning_at_equal_or_lower_level_is_refused(pinned, capsys):
    tmp, iso, ev, sha = pinned
    rc = cli.cmd_pin(A(build=str(iso), level="data", evidence=[str(ev)], note="demote"))
    assert rc != 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status"] == "REFUSED"
    man = json.loads(cli.PIN_FILE.read_text())
    assert len(man["entries"]) == 1 and man["entries"][0]["verified_level"] == "boot"


def test_higher_evidence_level_may_amend_but_never_demote(pinned, capsys):
    tmp, iso, ev, sha = pinned
    rc = cli.cmd_pin(A(build=str(iso), level="play", evidence=[str(ev)], note="if ever played"))
    assert rc == 0
    capsys.readouterr()
    assert json.loads(cli.PIN_FILE.read_text())["last_passing"]["verified_level"] == "play"
    rc = cli.cmd_pin(A(build=str(iso), level="boot", evidence=[str(ev)], note=""))
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status"] == "REFUSED"


def test_pin_requires_existing_evidence(tmp_path, monkeypatch):
    iso = tmp_path / "b.iso"; iso.write_bytes(b"x" * 32)
    monkeypatch.setattr(cli, "PIN_FILE", tmp_path / "m.json")
    rc = cli.cmd_pin(A(build=str(iso), level="boot", evidence=["nope.json"], note=""))
    assert rc != 0
    assert not (tmp_path / "m.json").exists()      # a manifest is never written from missing evidence


def test_play_refuses_when_bytes_no_longer_match_the_manifest(pinned, monkeypatch, capsys):
    tmp, iso, ev, sha = pinned
    iso.write_bytes(iso.read_bytes() + b"tampered")          # e.g. a failing run overwrote it
    monkeypatch.setattr(cli.os, "environ", {})               # no DISPLAY: report instead of exec
    rc = cli.cmd_play(A(last_passing=True, dry_run=False))
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc != 0 and out["status"] == "FAIL"
    assert "mismatch" in out["reason"] and out["expected"] != out["got"]


def test_play_dry_run_hands_the_human_the_command_not_the_agent_profile(pinned, capsys):
    tmp, iso, ev, sha = pinned
    cli.cmd_play(A(last_passing=True, dry_run=True))
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # NEEDS_HUMAN is the correct end state of a dry run: the agent is headless, so
    # the deliverable is the exact command + verified hash for a human to run.
    assert out["status"] == "NEEDS_HUMAN"
    assert "-u" not in out["command"] and "runtime/dolphin-agent" not in out["command"]
    assert out["verified_level"] == "boot"
