# ADR-0004: uv is the only Python environment/package tool

**Date:** 2026-10-09
**Status:** accepted
**Context:** Owner explicitly mandated uv for all venv/package work; Arch's
system Python must never be touched and bare pip is banned by preference.
**Decision:** All Python work uses `uv venv .venv` + `uv pip` / `uv add` with
`pyproject.toml` and a committed `uv.lock`. `scripts/bootstrap.sh` is updated
accordingly; CI/test instructions must invoke `.venv/bin/python`, never pip.
**Evidence:** Owner instruction 2026-10-09; `uv` installed from Arch official
repo (`/usr/bin/uv`) same day.
**Consequences:** Reproducible locks for pyisotools / dolphin-memory-engine
etc.; pip-only snippets in the master spec are read as uv equivalents.
Exception requires explicit owner approval.
