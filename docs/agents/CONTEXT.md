# Hubricon: shared context for every agent

Read this before any task. It is the brief every agent on the team shares.

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
