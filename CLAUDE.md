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
  `/apply`), under about 900 visible words, no proof that does not exist.
  `scripts/build-home.test.mjs` checks all three.
- **No number is typed into the home page.** Figures and charts come from `data/` through
  `node scripts/case-study.mjs` then `node scripts/build-home.mjs`; the test fails a stale page.
- **One design system.** Every page reads `/assets/hubricon.css`. No page keeps a private
  palette. Blue is for money and the leak, nothing else.
- **Model changes re-run the bench.** Any change to elasticity, pricing, forecast,
  inventory, the ad models or measurement re-runs `engine/bench` on seeds 101/202/303
  and 404/505/606.
- **Pushing `main` deploys production** (Vercel builds from GitHub). Push only on the
  founder's go.

## Tests

- Engine: `cd engine && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest -q` (about 5 minutes).
- Node: `node --test lib/ scripts/` (the API helpers, the Record verifier, the home page
  and the public-data case study).
