---
name: content-next
description: Advance the Hubricon content queue by one or more steps. The unattended continuation entry point; also usable interactively as /content-next.
---

# content-next

You are advancing `content/queue.json` on the `content` branch. Work in small, committed steps.
Read `CLAUDE.md` first if you have not this session.

## Loop

1. `git status --short`. If the tree is dirty, commit it now with the message
   "Content pipeline: recover partial step state from an interrupted tick".
2. Run `hubricon-content next`. It prints one JSON line: `{"unit": ..., "kind": ..., "step": ...}`
   or `{"idle": true, "reason": ...}`.
   - Idle: run `hubricon-content status --md` (regenerates `content/STATE.md` and `content/REVIEW.md`),
     commit if anything changed, and stop.
3. Dispatch on `kind`:
   - `setup` or `learn`: open the unit's `checklist` in `queue.json`; do the next unchecked item
     exactly as written there; for page copy run the `critique` skill in `copy` mode before marking.
   - `video`: invoke the `produce-video` skill for that single `unit` and `step`.
4. Record the outcome: `hubricon-content mark <unit> <step> done` or
   `hubricon-content mark <unit> <step> failed "<one-line reason>"` or
   `hubricon-content mark <unit> <step> blocked "<the exact input a human must supply>"`.
5. `hubricon-content status --md`, then `git add -A content docs learn api index.html .claude` and
   commit with one full sentence describing what the step produced (match the style in `git log`).
6. If fewer than 40 minutes have passed since you started (check `date`), go to 2.

## Hard rules

- Never `git push`, never `git checkout`, never touch `main`. The runner pushes the `content` branch.
- One unit in progress at a time. Units parked at `awaiting` (founder review) do not count.
- Never fabricate a capability. Missing key, token, audio or texture means `blocked` with the
  exact input needed, not a workaround.
- Never write a number into narration, a description, a thumbnail or lesson copy. Placeholders
  from `facts.json` only. `hubricon-content script-validate` is the judge.
- A step that fails three times becomes `stuck`; move on and leave the reason in the log.
- If `hubricon-content` is not on PATH, use `content/.venv/bin/hubricon-content`.
