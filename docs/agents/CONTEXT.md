# Hubricon: shared context for every agent

Read this before any task. It is the brief every agent on the team shares.

## Current state (27 Nov 2026)

This section is newer than everything below it. Where the two disagree, this section wins.

### The goal, in Hagen's words (27 Nov 2026)
- "The new goal is going to be 300 cold calls a day and 1 new client paying $1000/mo." "We will do this until there is 1000 paying clients."
- "We need to re-engineer the website to be perfect for such a client. We need to target a painpoint That they have."
- "we will need to have a landing page without calendly where they just pay on the spot and get instant set up and value."
- "Painless set up $1000/mo pricing."
- "The initial target audience will be us niching down in increments when we're finding the numbers. The client we will be looking to call will be operators who answer their phone. We need zero onboarding friction and they must not need a committe approval."
- "Before we make that happen we need to fix the way I've been engeering to ship better code FASTER."
- "Don't tell me what we can and cant do or what is acheiveable. Nothing will change the fact that the 300 cold calls will be happening."
- Hagen gets the phone numbers himself. Agents do not source them.

What this replaces: the $6,000 a month offer sold on a booked call (still on the live site until the new pages ship), and the first-customers agent's "20 to 40 brands by hand" plan. The buyer is now one person who answers their own phone and can pay on that call without asking anyone.

### The product
- The product is the **Profit Record**: every move is written down with its expected dollars before it goes live, measured on the brand's own later reports, and sealed so anyone can check it at hubricon.com/verify. Sealed predictions, held-back tests, and (on the branch `app/shopify-profit-record`) a fee only on new highs of proven profit.
- **Pooled demand is a supporting method** for slow sellers and short histories. It is not the moat. In simulation its gain was narrow and levelled off near 20 businesses.
- **Measured supplier lead times** (two dates per order, read from the brand's own orders) is the supply-variability fix inside the product. It is partly built: the Late Supplier spreadsheet and `/lateness` collect the dates, and the engine does not read them yet.
- The engine is more than reorder maths. It reads Amazon and Shopify exports and runs 23 models in one pass (margin, price, forecast, inventory, ads, fee recovery and cash among them) [measured: counted in the `ALL_MODELS` list of engine/src/hubricon_engine/cli.py]. A Shopify run skips fee recovery, so it runs 22 [measured: the same file].
- How long a run takes has been timed on synthetic catalogues only, never on a client's data: about 29 seconds at 160 SKUs and 75.5 seconds at 400 SKUs [sourced: engine/MATH_SCORECARD.md, "What it costs to run", timed 2026-09-24 and 2026-09-23]. Nobody has re-timed it since.

### What is true today
- No paying customers. No measured result on a real brand. Say so plainly, every time.
- Claim only what is built and measured. Never a client, result or dollar figure that has not been measured (SUPPLY_VARIABILITY.md, O5).
- The lead-time simulation result "5.7 days to 4.0 days" is an **unverified simulation**. Never quote it as evidence (O2).
- Hagen sends every message and makes every call himself. Agents draft and check (O23).

### Where things are in this repo
- The handoff and every decision: `SUPPLY_VARIABILITY.md` (section 7 for decisions, section 9 for answered questions).
- Headline numbers and their status: `docs/agents/NUMBERS.md`. Quote from there and nowhere else. `python3 tools/agent_check.py docs/agents/CONTEXT.md --only numbers` fails any number in this file that is not a row of it.
- Corrections and what each became: `agents/CORRECTIONS.md`. Past questions with their accepted answers: `agents/golden/`.
- What the business says about itself today: `HUBRICON.md`, `HUBRICON_SPEC.md`, `BRAND.md`, `MONOPOLY.md`. Parts of these still describe the $6,000 offer.
- The problem PDF, `sim/`, `landing/` and `education/` named below are not in this repo. Use SUPPLY_VARIABILITY.md section 1 instead.

## The business
- **Hubricon** (hubricon.com, repo `anderlecht-debug/HubriconB2B`) is a B2B business for e-commerce brands and other businesses that hold stock ahead of demand.
- Founder: **Hagen**, solo, unfunded, no customers yet. Every recommendation must be doable by one person with no capital, starting this week.
- The engine already reads Amazon and Shopify exports, computes reorder points (textbook ROP with demand and lead-time variance as a cross-check), and sizes safety stock from each product's margin. Its known weakness: it **assumes** supplier lead times (one typed-in value, assumed 20% spread) instead of measuring them.
- Pricing model: paid a percentage of the results it produces, so every claim must be provable in dollars.

## The problem (see `/mnt/project-files/The Problem Supply Variability.pdf`)
- Brands that import pay for supply variability and cannot see the bill. Three sources stack: demand swings, supply swings (a "45-day" China to US lead time really spans roughly 36 to 70 days), and the brand's own ordering (bullwhip, panic orders, tariff front-running).
- Factory Physics says variability is always buffered by inventory, capacity or time. An importer cannot add factory capacity, so it pays in inventory (cash, dead stock) and time (stockouts, lost rank), or buys late speed with air freight.
- Worked example: 40 units/day ±15, 45-day lead time ±9 days needs ROP of 2,416; the habitual "20% extra" gives 2,160, 256 short. But if the sales rate itself is uncertain by ~35%, demand uncertainty dominates. So: compare how much lead time swings against how well the sales rate is known.
- Size of prize: roughly $13,000 to $259,000 a year in recoverable profit for brands from $1M to $20M revenue, plus one-off cash released from trimmed stock.

## The current front-runner for the monopoly (from the "Find the monopoly problem" thread)
> **Superseded 27 Nov 2026.** Kept for the record. Pooled demand is a supporting method, not the moat, and the 5.7 to 4.0 days figure is an unverified simulation. See "Current state" above.

**True demand, corrected for stockouts and pooled across businesses**, built on Stein's paradox (Stein 1956; James and Stein 1961): when you estimate many similar quantities at once, shrinking each toward the group beats estimating each from its own data.
- Merchants already name the pain: tools count sales speed over days the item was sold out, so best sellers look slow and get under-ordered.
- A single store with shifting demand cannot learn true demand from censored (sold-out) sales; a pool of similar stores can.
- Nobody sells it: Shopify, Amazon Restock, Prediko, Inventory Planner each forecast from one store's data. Shopify is the biggest threat (it already benchmarks stores).
- A project simulation: lead-time forecast error fell from 5.7 days (one brand alone) to 4.0 days (20 brands pooled).
- Day-one monopoly plan: one product category from one sourcing region, 20 to 40 brands. Signing most of them is the monopoly in miniature.
- Runner-up: pooling small brands' orders to meet factory minimums (needs a factory partner and escrow).

## Hagen's standards
- **"11 out of 5."** Good is not the bar. Grade work on a 5-point scale and aim past the top of it.
- **"If physics allows it, pursue it."** The only hard limits are physical and mathematical ones. Everything else (habit, convention, "that's how the industry does it") is a requirement to question.
- **Monopoly from day one**, in the *Zero to One* sense.
- People Hagen has named as models: Peter Thiel, Elon Musk, Steve Jobs, Alex Hormozi, the copywriter Alex Cattoni, Terry LaCore, and *Factory Physics* (Hopp and Spearman).

## How every agent writes
- Lead with the answer or the decision. Plain, full sentences. Numbers with units and sources.
- Separate what is **measured**, what is **sourced**, and what is **your inference**. Label inference as inference.
- **Quote policy.** Only quote a person's words when you can name the source (book, essay, talk, letter, with year). Keep quotes short. If you cannot source it, paraphrase and say it is a paraphrase, or leave it out. Never invent a quote. The quotes in these agent files have been checked; do not embellish them.
- End with the one next action Hagen can take this week.

## Where things are
- Project files: `/mnt/project-files/` (problem PDF, `sim/` simulations, `landing/` and `education/` screenshots).
- The team: `/mnt/project-files/agents/` (this folder). See `README.md`.
