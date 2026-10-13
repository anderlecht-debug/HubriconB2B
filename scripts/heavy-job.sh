#!/usr/bin/env bash
# One heavy job at a time (a render, a re-pick, a full test run), detached from any chat, capped so the PC
# stays up, with its temperatures logged beside it. The PC powered off hard three times under combined
# CPU+GPU load (2026-10-07 twice, 2026-10-12) with nothing in its logs: a hardware cut-out. This keeps the
# load under the line and leaves a record if it happens again.
#   scripts/heavy-job.sh <name> <workdir> <command...>   (a film command sets its own env: env FILM_LOOK=v3 ...)
# Log: ~/Hubricon/jobs/<name>.log (the job) and ~/Hubricon/jobs/<name>.thermal.log (every 15 s).
set -euo pipefail
NAME="$1"; WD="$2"; shift 2
J="$HOME/Hubricon/jobs"; mkdir -p "$J"
if systemctl --user list-units --state=active --no-legend 'heavy-*' | grep -q .; then
  echo "another heavy job is running: $(systemctl --user list-units --state=active --no-legend 'heavy-*' | awk '{print $1}')" >&2; exit 1
fi
CMD=$(printf '%q ' "$@")
systemctl --user reset-failed "heavy-$NAME" 2>/dev/null || true
systemd-run --user --collect --unit="heavy-$NAME" -p CPUQuota=1000% -p MemoryMax=10G -p MemorySwapMax=2G \
  --working-directory="$WD" --setenv=HOME="$HOME" --setenv=PATH="$PATH" --setenv=PYTHONWARNINGS=ignore \
  --setenv=OMP_NUM_THREADS=4 \
  bash -c "{ date -Is; $CMD; echo \"DONE rc=\$? \$(date -Is)\"; } > '$J/$NAME.log' 2>&1"
# the thermal log runs until the job ends
nohup bash -c "while systemctl --user is-active -q heavy-$NAME; do
  printf '%s cpu %s gpu %s\n' \"\$(date +%H:%M:%S)\" \"\$(sensors 2>/dev/null | awk '/Tctl/{print \$2}')\" \
    \"\$(nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu --format=csv,noheader 2>/dev/null)\" >> '$J/$NAME.thermal.log'
  sleep 15; done" >/dev/null 2>&1 &
echo "heavy-$NAME started; log $J/$NAME.log, temperatures $J/$NAME.thermal.log"
