# Working in the Hubricon repo

Read these before changing anything, in this order:

1. `HUBRICON_SPEC.md`: the rebuild's source of truth (2026-09-27). Where it and the repo
   disagree, the spec wins, except that nothing in it licenses an untrue claim.
2. `HUBRICON.md`: what Hubricon is, the honesty rules and the client vocabulary. The
   honesty rules override everything, the spec included.
3. `MONOPOLY.md`: what the business is building toward (proprietary technology,
   network effects, economies of scale, brand) and the rules every change is held to.
4. `BRAND.md`: how every page, email and asset looks and sounds.

`OPERATIONS.md` says how the machine runs. Read `engine/MATH_SCORECARD.md` before any
model change.

## Non-negotiables

- **Nothing untrue on a client surface.** No result, testimonial, client count, logo or
  capability that does not exist in production. Future things go in the future tense,
  labelled on the page. Every case-study figure says "estimate"; every proof screen says
  "Modeled from public data · Not a client · Not a result".
- **The moat test.** Every commit body carries `Moat: tech`, `network`, `scale`,
  `brand`, or `none (why)`.
- **One client's data never advises another** without the consent the terms name (§10).
- **The home page meets the Hormozi standard:** one action ("Book your call →", to
  `/apply`, the only button), no proof that does not exist, and since 2026-10-01 evening (the
  founder's call, recorded in `HUBRICON_SPEC.md`, "Amended by the founder") a short first page:
  five bands (the promise, the proof, the offer, the library strip, the call), its own words
  capped by the test. Every other section lives on the page under its tab: Proof is
  `/case-study`, How it works is `/how-it-works`, The offer is `/offer`, Education is `/learn`,
  Trust opens the pages that say it. No results wall and no Results tab until a client's dated
  consent fills a frame. A planned course says Planned and links nowhere; an empty video slot
  says what will play there; the course's optional email lives on `/learn` and the course
  pages, never the home page; and nothing that moves is ever blank before it plays.
  `scripts/build-pages.test.mjs` and `scripts/site-blocks.test.mjs` check all of it.
- **No number is typed into the home page.** Figures and charts come from `data/` through
  `node scripts/case-study.mjs` (the Amazon listing) and `engine/scripts/store_case_study.py`
  (the store study), then `node scripts/build-pages.mjs`; the test fails a stale page.
- **One design system.** Every page reads `/assets/hubricon.css`. No page keeps a private
  palette. Blue is for money and the leak, nothing else.
- **Model changes re-run the bench.** Any change to elasticity, pricing, forecast,
  inventory, the ad models or measurement re-runs `engine/bench` on seeds 101/202/303
  and 404/505/606.
- **Pushing `main` deploys production** (Vercel builds from GitHub). Push only on the
  founder's go.

## Tests

- Engine: `cd engine && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest -q` (about 5 minutes).
- Node: `node --test lib/ scripts/` (the API helpers, the Record verifier, the home page,
  the tab pages and both case studies).

## The content pipeline (worktree `HubriconB2B-content`, branch `content`)

`HUBRICON_SPEC.md` ("Content engine", "Education", "Channel decision") governs it; where the
older documents in `docs/content/` disagree with the spec, the spec wins.

- Package `content/src/hubricon_content`, its own `.venv` (Python 3.13). State:
  `content/queue.json` (machine), `content/STATE.md` (human rollup), `content/REVIEW.md` (the
  founder's review inbox). Entry point: the `content-next` skill. `content/.runner/STOP` pauses
  the 30-minute timer.

### The number-safety rule (non-negotiable)

No digit, currency sign, percent sign, or number word (two, hundred, half, quarter, percent...)
may appear in any narration line, description, thumbnail text, or lesson copy unless it is a
`{{key}}` placeholder drawn from a facts file the engine produced (`hubricon-content facts`, or
the case study's `data/case-study.json` and `ratecard.json` through `hubricon-content facts
--case-study`). `hubricon-content script-validate` enforces it; a draft that fails is
rewritten, never patched by hand with a number. Demo figures are labelled "demo data" on
screen and in copy; case-study figures carry "Modeled from public data · Not a client · Not a
result".

### Voice rules for every script

The spec's three beats: the hook opens in their frustration and removes the shame; the teach
gives the real insight away; one calm soft close ("You can build this yourself. If you're doing
real volume and want it run with rigor, this is what I do, and I only get paid when it works.").
Every piece points to `/learn`. Plain declarative sentences, contractions, intuition before
notation, uncertainty as bands. No exclamation marks, urgency, scarcity or countdowns.

Banned: "in today's video", "let's dive in", "game-changer", "secret", "hack", "crazy",
"insane", "simply", "just", "obviously", "of course", "the truth is", "imagine".

### Production rules

- The look is the site's: `/assets/hubricon.css` (white, ink, one cold blue for money and the
  leak, Inter). The house visuals are `/assets/charts.mjs`: the staircase, the Monte Carlo band,
  the aging cliff. A video scene draws them from the same code, never a redrawing of them.
- No faces, avatars or synthetic humans anywhere. Higgsfield is for textures only.
- Voice: the founder's own recorded voice, and only that (his call, 2026-10-06: no ElevenLabs,
  no clone). He reads each approved script at `content/film/record.mjs`; `takes-to-vo` makes the
  takes the narration. The description says "Narrated by Hagen Simmons, in his own voice." Nothing
  in the pipeline calls ElevenLabs; new sound is Freesound CC0 or Pixabay, with its licence.
- The Reimbursement Playbook draft is parked (it needs the seller's own reports, so it is not
  the public-data first course); its pages are in `archive/`.

### Branch and publishing rules

- Content work happens only on the `content` branch. Never `git checkout main`, never `git push`
  from an unattended run, never touch `main`.
- Commit after every completed step with a full-sentence message in this repo's style, and the
  `Moat:` line.
- Nothing renders until the founder has approved the script (`review == approved`). Nothing
  uploads unless the voice is the founder's, QA passed, and `approve_final == approved`.
  Uploads are unlisted until he publishes them.
- If a capability is missing (a key, a token, founder audio), mark the step blocked with the
  exact input needed. Never fabricate a capability, a number, a testimonial, or a result.
