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
# The allow list in .claude/settings.json only applies once this workspace is trusted.
# Until then every hubricon-content, git add and git commit call inside a tick waits
# for an approval nobody is there to give (the log line "Ignoring 38 permissions.allow
# entries" is the symptom). A tick cannot fix this itself: Claude Code refuses to let a
# session edit its own permission settings. The founder does one of these once:
#   * run `claude` interactively in /home/lp9/Hubricon/HubriconB2B and accept the trust
#     dialog, or set projects["/home/lp9/Hubricon/HubriconB2B"].hasTrustDialogAccepted
#     to true in /home/lp9/.claude.json;
#   * or copy the "allow" list from .claude/settings.json into
#     scripts/content-runner.settings.json, which is passed with --settings and trusted.
export HOME=/home/lp9
export PATH="$WT/content/.venv/bin:/home/lp9/.local/bin:/usr/local/bin:/usr/bin:/bin"
cd "$WT" || exit 1
git checkout -q content 2>/dev/null
git fetch -q origin content 2>/dev/null && git merge -q --ff-only origin/content 2>/dev/null

# Scripts the founder drafted elsewhere and dropped in the inbox become films (docs/content/SCRIPT_KIT.md):
# each is checked and filed by code, for no tokens. A clean one waits on his takes and is moved to taken/;
# a refused one goes to refused/ with its problems beside it, never retried until he drops a new copy.
INBOX="${CONTENT_INBOX:-$HOME/Hubricon/scripts-inbox}"
mkdir -p "$INBOX/taken" "$INBOX/refused"
TOOK=""
for F in "$INBOX"/*.md "$INBOX"/*.txt; do
  [ -f "$F" ] || continue
  [ "${CONTENT_DRY_RUN:-0}" = "1" ] && break
  RES=$(cd "$WT/content" && .venv/bin/python -m hubricon_content.cli script-in "$F" 2>&1 | tail -1)
  B=$(basename "$F"); STAMP=$(date +%Y%m%d-%H%M%S)
  if printf '%s' "$RES" | grep -q '"status": "ok"'; then
    mv "$F" "$INBOX/taken/$STAMP-$B"; TOOK="$TOOK $B"
  else
    mv "$F" "$INBOX/refused/$STAMP-$B"; printf '%s\n' "$RES" > "$INBOX/refused/$STAMP-$B.problems.json"
  fi
  printf '%s script-in %s: %s\n' "$(date -Is)" "$B" "$RES" >> "$RUN/log"
done
if [ -n "$TOOK" ]; then
  cd "$WT" || exit 0
  git add -A content docs 2>/dev/null
  git diff --cached --quiet || git commit -q -m "Content pipeline: a founder's script taken in:$TOOK" \
    -m "Moat: brand (the founder's own films, filed the moment he hands them over)"
  git push -q origin content 2>/dev/null || true
fi

# An idle queue (everything parked for the founder or blocked on an input) needs no
# Claude session at all; the state files are refreshed and the tick ends.
if [ "${CONTENT_DRY_RUN:-0}" != "1" ] && "$WT/content/.venv/bin/hubricon-content" next --dry 2>/dev/null | grep -q '"idle": true'; then
  "$WT/content/.venv/bin/hubricon-content" status --md >/dev/null 2>&1
  # A rollup that only moved its own timestamps is not news: put the files back, commit nothing.
  if [ -z "$(git diff -U0 -- content | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)' | grep -vE 'Updated [0-9]{4}-[0-9]{2}-[0-9]{2}T|"updated_at":')" ]; then
    git checkout -q -- content 2>/dev/null
  fi
  git add -A content 2>/dev/null; git diff --cached --quiet || git commit -q -m "Content pipeline: the state rollup after an idle tick"
  git push -q origin content 2>/dev/null || true
  printf '%s tick idle (no session started)\n' "$(date -Is)" >> "$RUN/log"
  exit 0
fi

# A long film whose next step is one of the line's runs as code, outside any AI session (the founder's
# call of 2026-10-07, docs/content/FILM_LINE.md): film-line is one resumable command, and only its own
# decide and fix passes use a model, under their budgets. Only a film read in his own voice qualifies.
DUE=$(cd "$WT/content" && .venv/bin/python -m hubricon_content.cli line-due 2>/dev/null | tail -1)
SLUG=$(printf '%s' "$DUE" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read() or "{}").get("slug",""))' 2>/dev/null)
if [ -n "$SLUG" ] && [ "${CONTENT_DRY_RUN:-0}" != "1" ]; then
  START=$(date +%s)
  OUT=$(cd "$WT/content" && CLAUDE_BIN="$CLAUDE" timeout 55m .venv/bin/python -m hubricon_content.cli film-line "$SLUG" 2>&1); RC=$?
  { printf '%s film-line %s rc=%s secs=%s\n' "$(date -Is)" "$SLUG" "$RC" "$(( $(date +%s) - START ))"
    printf '%s\n' "$OUT" | tail -c 4000; printf '\n---\n'; } >> "$RUN/log"
  cd "$WT" || exit 0
  git add -A content docs 2>/dev/null; git diff --cached --quiet || git commit -q -m "Content pipeline: the film line advanced $SLUG"
  git push -q origin content 2>/dev/null || true
  exit 0
fi

# A real tick sees the claude.ai connectors so it can reach Higgsfield for the films'
# texture stills (the founder's call, 2026-10-04). scripts/content-runner.settings.json
# allows five Higgsfield tools and denies every other connector by name; anything not
# allowed is refused in a headless session anyway. The dry run stays strict.
START=$(date +%s)
if [ "${CONTENT_DRY_RUN:-0}" = "1" ]; then
  OUT=$(timeout 5m "$CLAUDE" -p "Reply with the single word OK and nothing else." \
        --settings "$WT/scripts/content-runner.settings.json" --permission-mode acceptEdits \
        --max-turns 2 --output-format json --no-session-persistence --strict-mcp-config 2>&1); RC=$?
else
  # Every tick runs under the runner's token caps (content/film/budgets.json "runner", the
  # founder's call of 2026-10-07): Sonnet, a cap per tick, per day and per week, the session
  # stopped the moment one is spent; a tick past the day's or the week's cap does not start.
  # It prints the session's result object, so the checks below read it as before.
  OUT=$(cd "$WT/content" && CLAUDE_BIN="$CLAUDE" timeout 55m .venv/bin/python -m hubricon_content.cli ai-tick \
        --prompt "Read CLAUDE.md, then follow .claude/skills/content-next/SKILL.md exactly. Stop starting new steps after 40 minutes of work." \
        -- --settings "$WT/scripts/content-runner.settings.json" --permission-mode acceptEdits \
        --max-turns 300 --no-session-persistence 2>&1); RC=$?
fi
SECS=$(( $(date +%s) - START ))
{ printf '%s tick rc=%s secs=%s dry=%s\n' "$(date -Is)" "$RC" "$SECS" "${CONTENT_DRY_RUN:-0}"
  printf '%s\n' "$OUT" | tail -c 20000; printf '\n---\n'; } >> "$RUN/log"

if printf '%s' "$OUT" | grep -q '"permission_denials":\[{'; then
  printf '%s WARNING: the tick was denied a tool call; check the allow list in scripts/content-runner.settings.json\n' "$(date -Is)" >> "$RUN/log"
fi
# Back off only on a real limit: the result object's own error fields, never a
# substring somewhere in a transcript that happens to mention a status code.
LIMIT=$(printf '%s' "$OUT" | python3 -c '
import json, re, sys
raw = sys.stdin.read()
try:
    obj = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
except Exception:
    print("unparsed"); sys.exit()
status = obj.get("api_error_status")
text = str(obj.get("result", ""))[:2000] if obj.get("is_error") else ""
if status in (429, 529) or re.search(r"usage limit|rate limit|limit will reset|resets? at|overloaded", text, re.I):
    print("limit")
' 2>/dev/null)
if [ "$LIMIT" = "limit" ]; then
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
