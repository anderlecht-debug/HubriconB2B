# Working in the Hubricon repo

Read these before changing anything, in this order:

1. `HUBRICON.md`: what Hubricon is, the honesty rules and the client vocabulary. These
   override everything below.
2. `MONOPOLY.md`: what the business is building toward (proprietary technology,
   network effects, economies of scale, brand) and the rules every change is held to.
3. `BRAND.md`: how every page, email and asset looks and sounds.

`OPERATIONS.md` says how the machine runs. Read `engine/MATH_SCORECARD.md` before any
model change.

## Non-negotiables

- **Nothing untrue on a client surface.** No result, testimonial, client count, logo or
  capability that does not exist in production. Future things go in the future tense,
  labelled on the page.
- **The moat test.** Every commit body carries `Moat: tech`, `network`, `scale`,
  `brand`, or `none (why)`.
- **One client's data never advises another** without the consent the terms name (§10).
- **The home page meets the Hormozi standard:** one action ("Start your free Proving
  Month"), under about 900 visible words, no proof that does not exist.
- **Model changes re-run the bench.** Any change to elasticity, pricing, forecast,
  inventory, the ad models or measurement re-runs `engine/bench` on seeds 101/202/303
  and 404/505/606.
- **Pushing `main` deploys production** (Vercel builds from GitHub). Push only on the
  founder's go.

## Tests

- Engine: `cd engine && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest -q` (about 5 minutes).
- Node: `node --test lib/ scripts/` (the API helpers and the Record verifier).
