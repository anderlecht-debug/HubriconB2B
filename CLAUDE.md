# Hubricon — project instructions for Claude Code

Hubricon is a founder-operated Managed Profit service for Amazon and Shopify brands. One
operator: Hagen Simmons. There are no paying clients and no published results yet, and no
surface may imply otherwise.

## Where things are

- Product and operations: `HUBRICON.md`, `OPERATIONS.md`, `GROWTH.md` (not deployed; `*.md` is in `.vercelignore`).
- The engine: `engine/` (Python, `hubricon` CLI). Models in `engine/src/hubricon_engine/models/`.
- The site: root-level `*.html`, deployed by Vercel with `cleanUrls`; `api/*.js` are serverless functions.
- The content pipeline: `content/` (package `hubricon_content`, its own `.venv` on Python 3.13).
  Governing documents in `docs/content/`:
  `hubricon-learn-build-prompt.md`, `hubricon-video-production-bible.md`,
  `hubricon-30-day-content-calendar.md`, `hubricon-video-scripting-doctrine.md`
  (plus the landing and Capital Position prompts for context only).
- Pipeline state: `content/queue.json` (machine), `content/STATE.md` (human rollup),
  `content/REVIEW.md` (the founder's review inbox). Entry point: the `content-next` skill.

## The number-safety rule (non-negotiable)

No digit, currency sign, percent sign, or number word (two, hundred, half, quarter, percent...)
may appear in any narration line, description, thumbnail text, or lesson copy unless it is a
`{{key}}` placeholder drawn from a `facts.json` produced by `hubricon-content facts`, which runs
the engine's own models on data. `hubricon-content script-validate` enforces this with
`hubricon_engine.narrate.validate`; a draft that fails is rewritten, never patched by hand with
a number. Demo figures are always labelled "demo data" on screen and in copy.

## Voice rules for every script and page

Plain declarative sentences. Contractions. Intuition before notation; name a thing after
showing it. One idea per video, one CTA per video chosen by pillar (doctrine §8). Show
uncertainty as bands, not point estimates. No exclamation marks, no rhetorical questions as
headers, no urgency, no scarcity, no countdowns.

Banned: "in today's video", "let's dive in", "game-changer", "secret", "hack", "crazy",
"insane", "simply", "just", "obviously", "of course", "the truth is", "imagine".

## Production rules

- No generated faces, avatars, or synthetic humans anywhere. Higgsfield is for textures only,
  never the subject being explained. Never the faceless-video workflow.
- Every chart is a Manim scene driven by a real engine run. Never hand-draw a chart the engine
  can produce. Charts build progressively and carry an annotation.
- Narration is a clone of the founder's voice when `ELEVENLABS_VOICE_ID` exists; otherwise a
  placeholder voice that never ships. Disclosure line, verbatim, in every description:
  "Narration is an AI clone of Hagen Simmons's voice, used with his permission; the analysis is his."
- The Reimbursement Playbook (course 1) is raw screen recording by the founder. Nothing in it is animated.

## Branch and publishing rules

- Content work happens only on the `content` branch (worktree `HubriconB2B-content`). Never
  `git checkout main`, never `git push` from an unattended run, never touch `main`.
- Commit after every completed step with a full-sentence message in this repo's style
  (see `git log`). One commit per step keeps progress durable across usage-limit resets.
- Nothing renders until the founder has approved the script (`review == approved`). Nothing
  uploads unless `voice == founder`, QA passed, and `approve_final == approved`. Uploads are
  always unlisted with the synthetic-media flag set.
- If a capability is missing (a key, a token, founder audio), mark the step blocked with the
  exact input needed. Never fabricate a capability, a number, a testimonial, or a result.
