#!/usr/bin/env bash
# Bootstrap helper for the Pikmin 2 AI Lab (Arch Linux).
# The agent sandbox blocks pacman/sudo: run the system install yourself, then
# re-run this script to provision user-scoped venv deps.
set -euo pipefail

echo "== System packages (requires your approval, run manually) =="
cat <<'EOF'
sudo pacman -Syu
sudo pacman -S --needed dolphin-emu dolphin-emu-tool git python python-pip ninja cmake base-devel ffmpeg jdk-openjdk
# optional later: blender, mesa-utils, vulkan-tools, python-evdev
EOF

echo "== Python venv (user-scoped, no approval needed) =="
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install pyisotools dolphin-memory-engine pytest pyyaml

echo "== Verify =="
command -v dolphin-emu && command -v dolphin-tool
.venv/bin/python -c "import pyisotools; print('pyisotools OK')"
echo "Now run: .venv/bin/python -m pikminlab doctor"
