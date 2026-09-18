#!/usr/bin/env bash
# One tick of the unattended content pipeline. Fired by the user systemd timer
# (scripts/systemd/hubricon-content.timer) every 30 minutes; safe to run by hand.
#
# It re-enters cold: reads content/queue.json through the content-next skill,
# advances the queue by as many steps as fit in the budget, commits each one,
# and pushes only the `content` branch. When Claude Code reports a usage limit
# the tick backs off for an hour and the next eligible tick retries, so a reset
# costs one skipped tick and nothing else.
set -uo pipefail
MAIN=/home/lp9/Hubricon/HubriconB2B
WT=/home/lp9/Hubricon/HubriconB2B-content
RUN="$WT/content/.runner"
CLAUDE=/home/lp9/.local/bin/claude
mkdir -p "$RUN"
exec 9>"$RUN/lock"
flock -n 9 || exit 0                                   # a previous tick is still running
[ -e "$RUN/STOP" ] && exit 0                           # founder paused the loop
if [ -f "$RUN/backoff-until" ] && [ "$(date +%s)" -lt "$(cat "$RUN/backoff-until")" ]; then exit 0; fi

# .env may hold unquoted values with spaces; export line by line rather than sourcing it.
if [ -f "$MAIN/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue;; esac
    [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] && export "$line"
  done < "$MAIN/.env"
fi
# The engine's API key is for narrate.py, not for this session: with it set, Claude
# Code would bill an API key that needs a workspace header instead of using the
# subscription login the dry run proved. Ticks never need it.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_WORKSPACE_ID ANTHROPIC_BASE_URL
export HOME=/home/lp9
export PATH="$WT/content/.venv/bin:/home/lp9/.local/bin:/usr/local/bin:/usr/bin:/bin"
cd "$WT" || exit 1
git checkout -q content 2>/dev/null
git fetch -q origin content 2>/dev/null && git merge -q --ff-only origin/content 2>/dev/null

START=$(date +%s)
if [ "${CONTENT_DRY_RUN:-0}" = "1" ]; then
  OUT=$(timeout 5m "$CLAUDE" -p "Reply with the single word OK and nothing else." \
        --settings "$WT/scripts/content-runner.settings.json" --permission-mode acceptEdits \
        --max-turns 2 --output-format json --no-session-persistence --strict-mcp-config 2>&1); RC=$?
else
  OUT=$(timeout 55m "$CLAUDE" -p "Read CLAUDE.md, then follow .claude/skills/content-next/SKILL.md exactly. Stop starting new steps after 40 minutes of work." \
        --settings "$WT/scripts/content-runner.settings.json" --permission-mode acceptEdits \
        --max-turns 300 --output-format json --no-session-persistence --strict-mcp-config 2>&1); RC=$?
fi
SECS=$(( $(date +%s) - START ))
{ printf '%s tick rc=%s secs=%s dry=%s\n' "$(date -Is)" "$RC" "$SECS" "${CONTENT_DRY_RUN:-0}"
  printf '%s\n' "$OUT" | tail -c 20000; printf '\n---\n'; } >> "$RUN/log"

if printf '%s' "$OUT" | grep -qiE "usage limit|rate limit|limit will reset|resets? at|overloaded|status 529|429"; then
  date -d '+60 min' +%s > "$RUN/backoff-until"
  printf '%s backoff until %s\n' "$(date -Is)" "$(date -d '+60 min' -Is)" >> "$RUN/log"
else
  rm -f "$RUN/backoff-until"
fi

# Anything a killed run left uncommitted is still progress.
git add -A content docs .claude CLAUDE.md learn api index.html scripts 2>/dev/null
git diff --cached --quiet || git commit -q -m "Content pipeline: recover partial step state from an interrupted tick"
git push -q origin content 2>/dev/null || true
exit 0
