#!/usr/bin/env bash
# G0 component test: batch boot, flameshot capture, forced clean shutdown.
set -uo pipefail
cd "$(dirname "$0")/.."
PROFILE="$PWD/runtime/dolphin-agent"
OUT=/tmp/g0_component; rm -rf "$OUT"; mkdir -p "$OUT"

# ensure profile settings exist (idempotent merge)
python - "$PROFILE/Config/Dolphin.ini" <<'PY'
import sys, configparser
p = sys.argv[1]
c = configparser.ConfigParser(); c.read(p)
for sect, key, val in [('General','ConfirmStop','False'),
                       ('Core','AutoPlay','True'),
                       ('Log','EnableFileLogging','True')]:
    if sect not in c: c.add_section(sect)
    c[sect][key] = val
with open(p, 'w') as f: c.write(f)
PY

dolphin-emu -u "$PROFILE" -e pikmin2.iso -b -v Vulkan >"$OUT/stdout.log" 2>&1 &
DPID=$!
echo "dolphin pid=$DPID"
sleep 25

# capture attempt
flameshot full -p "$OUT/flameshot.png" 2>"$OUT/flameshot.err"; echo "flameshot exit=$?"
ls -la "$OUT"

# shutdown sequence with hard cap
shutdown() { # mvdan/sh kill builtin is crippled -> /bin/kill
  for sig in TERM TERM KILL; do
    /bin/kill -"$sig" "$DPID" 2>/dev/null
    for _ in $(seq 12); do /bin/kill -0 "$DPID" 2>/dev/null || return 0; sleep 1; done
  done
  echo "STUCK PROCESS $DPID"; exit 1
}
shutdown
wait "$DPID"; echo "dolphin exit=$?"
pgrep -a dolphin-emu && echo "STRAY REMAINING" || echo "all dolphin processes gone"
echo "=== log lines ==="; wc -l "$PROFILE/Logs/dolphin.log"; tail -5 "$PROFILE/Logs/dolphin.log"
