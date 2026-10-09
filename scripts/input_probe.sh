#!/usr/bin/env bash
# One-shot input-drive probe: can scripted keys change the running game?
# Hard-capped session per ADR-0006 policy (<=~70s, SIGKILL teardown).
set -uo pipefail
cd "$(dirname "$0")/.."
PROFILE="$PWD/runtime/dolphin-agent"
OUT="reports/runs/$(date -u +%Y-%m-%dT%H%M%SZ)-inputprobe"; mkdir -p "$OUT"
find_win() {
  local id nm
  for id in $(xdotool search --class dolphin-emu 2>/dev/null); do
    nm=$(xdotool getwindowname "$id" 2>/dev/null)
    case "$nm" in *'|'*) echo "$id"; return;; esac
  done
  return 1
}
press() { # $1 win, $2 keysym
  xdotool key --window "$1" --clearmodifiers "$2" 2>/dev/null
}
capture() { timeout 10 magick import -window "$1" "$2" 2>/dev/null; }

dolphin-emu -u "$PROFILE" -e pikmin2.iso -b -v Vulkan >"$OUT/stdout.log" 2>&1 &
DPID=$!
WIN=""
for _ in $(seq 20); do WIN=$(find_win) && break; sleep 2; done
if [ -z "$WIN" ]; then echo "no window appeared"; /bin/kill -KILL $DPID; exit 1; fi
echo "win=$WIN"
capture "$WIN" "$OUT/cap_title.png"; sleep 2
press "$WIN" Return; sleep 3; capture "$WIN" "$OUT/cap_after_start1.png"
press "$WIN" Return; sleep 3; capture "$WIN" "$OUT/cap_after_start2.png"
press "$WIN" x;      sleep 3; capture "$WIN" "$OUT/cap_after_a.png"
/bin/kill -KILL $DPID; sleep 2
pgrep -x dolphin-emu >/dev/null && echo "STRAY!" || echo "torn down clean"
sha256sum "$OUT"/cap_*.png | sed "s|$OUT/||"
