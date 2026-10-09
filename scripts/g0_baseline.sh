#!/usr/bin/env bash
# G0 baseline gate: N cold boots of the unmodified image in the isolated
# agent profile, each with a window-targeted capture and forced clean stop.
# NOTE: this shell's `kill` builtin is crippled (mvdan/sh) -> use /bin/kill.
set -uo pipefail
cd "$(dirname "$0")/.."
N="${1:-10}"
DWELL="${2:-45}"
PROFILE="$PWD/runtime/dolphin-agent"
RUN_ID="$(date -u +%Y-%m-%dT%H%M%SZ)-g0"
DIR="reports/runs/$RUN_ID"
mkdir -p "$DIR"

sha256() { sha256sum "$1" | cut -d' ' -f1; }

stop_dolphin() { # $1=pid ; returns 0 if gone
  for sig in TERM TERM KILL; do
    /bin/kill -"$sig" "$1" 2>/dev/null
    for _ in $(seq 12); do
      /bin/kill -0 "$1" 2>/dev/null || return 0
      sleep 1
    done
  done
  return 1
}

capture_window() { # $1=dest.png ; echo method used
  local win
  if command -v xdotool >/dev/null && win=$(xdotool search --name --dolphin "dolphin" 2>/dev/null | tail -1) && [ -n "$win" ]; then
    xdotool windowraise "$win" 2>/dev/null
    sleep 1
    if magick import -window "$win" -silent "$1" 2>/dev/null; then echo "x11-window:$win"; return 0; fi
  fi
  flameshot full -p "$1" 2>/dev/null && echo "flameshot-full-fallback" || echo "CAPTURE_FAILED"
}

{ echo "run_id=$RUN_ID"; echo "n=$N dwell=$DWELL"; echo "started=$(date -u +%FT%TZ)"; } >"$DIR/run.env"
PASS=0
for i in $(seq "$N"); do
  mkdir -p "$DIR/run$i"
  T0=$(date -u +%FT%TZ)
  dolphin-emu -u "$PROFILE" -e pikmin2.iso -b -v Vulkan >"$DIR/run$i/stdout.log" 2>&1 &
  DPID=$!
  sleep "$DWELL"
  ALIVE=no; kill -0 "$DPID" 2>/dev/null && ALIVE=yes
  METH=$(capture_window "$DIR/run$i/capture.png")
  IMG_BYTES=$(stat -c%s "$DIR/run$i/capture.png" 2>/dev/null || echo 0)
  stop_dolphin "$DPID"; STOP_RC=$?
  wait "$DPID" 2>/dev/null; EXIT_RC=$?
  STRAY=$(pgrep -c dolphin-emu || true)
  cp "$PROFILE/Logs/dolphin.log" "$DIR/run$i/dolphin.log" 2>/dev/null || true
  { echo "run=$i start=$T0 alive_at_capture=$ALIVE capture=$METH bytes=$IMG_BYTES stop_rc=$STOP_RC exit=$EXIT_RC strays_after=$STRAY"; } >>"$DIR/results.txt"
  [ "$ALIVE" = yes ] && [ "$STOP_RC" -eq 0 ] && [ "$STRAY" = 0 ] && [ "$IMG_BYTES" -gt 10000 ] && PASS=$((PASS+1))
done
echo "passes=$PASS/$N finished=$(date -u +%FT%TZ)" >>"$DIR/results.txt"
echo "G0 runs: $PASS/$N -> $DIR/results.txt"
