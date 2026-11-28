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

- Node: `npm test`, which is `node --test` from the repo root (under a second: the API
  helpers, the Record verifier, the home page, the tab pages, the lessons and both case
  studies). Give it no folders: `node --test lib/ scripts/` fails on Node 22.
- Engine: `npm run test:engine`, which is
  `cd engine && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest -q` (about 2 minutes).
- Both: `npm run check`.
- A test that reads the clock or a rate card pins the day it means. A test that passes
  today and fails next month is a bug in the test.

## How we ship

1. Work on a branch. Never commit to `main` and never push `main` directly.
2. One change per pull request. Keep it small enough to read in one sitting.
3. Docs the change makes untrue are fixed in the same pull request.
4. Open the pull request. CI (`.github/workflows/ci.yml`) runs the Node tests, the engine
   tests and the agent tools on it. Red means not ready: fix the stale side, never weaken
   the check.
5. Look at the Vercel preview link on the pull request before asking for the merge.
6. Hagen merges to `main`. That merge deploys production.

Run `npm run hooks` once per clone. After that git runs the Node tests before every push,
and the engine tests too when the push goes to `main` (`.githooks/pre-push`).
