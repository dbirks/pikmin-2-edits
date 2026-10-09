#!/usr/bin/env bash
# Bootstrap helper for the Pikmin 2 AI Lab (Arch Linux).
# System packages are owner-run (agent sandbox blocks pacman/sudo).
# ALL Python environments and packages go through uv. Never bare pip.
set -euo pipefail

echo "== System packages status =="
cat <<'EOF'
done 2026-10-09: dolphin-emu, dolphin-emu-tool (Dolphin 2606), base-devel, uv,
                 git, python, ninja, cmake, java (jdk-openjdk), ffmpeg
later (only when needed): blender   # P5/P6 custom model + collision work
EOF

echo "== Python env via uv (idempotent) =="
cd "$(dirname "$0")/.."
uv venv .venv
uv pip install --python .venv pyisotools dolphin-memory-engine pytest pyyaml

echo "== Verify =="
command -v dolphin-emu && command -v dolphin-tool
uv --version
.venv/bin/python -c "import pyisotools; print('pyisotools OK')"
echo "Next: .venv/bin/python -m pikminlab doctor"
