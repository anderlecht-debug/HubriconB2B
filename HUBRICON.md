# What Hubricon is

*The reference answer. If you are an assistant picking this repo up cold, read this
first, then `OPERATIONS.md` for how the machine runs and `GROWTH.md` for where
customers come from. Last rewritten 2026-09-11; the guarantee section 2026-09-25.*

---

## The one-paragraph answer

Hubricon is a done-for-you service that makes the money decisions inside a product
brand's Amazon or Shopify account — what to price, what to stop spending on ads,
what to reorder, what to claim back from Amazon — and records every one of those
decisions with the dollars it was expected to earn before it happened and the
dollars it actually earned afterwards, measured from the client's own later
exports. That record is called the **Profit Record**, and it is the product. The
fee is $6,000 a month, flat. The first month is free. Every invoice after that is
held until the Profit Record shows more value than Hubricon has billed since day
one, and voided unsent if it does not; a client who leaves is trued up to the
Record. It is run by one person.

---

## Who the customer is

A private-label brand doing **$3M–$20M a year** on Amazon, on Shopify, or
on both. Ten or more SKUs. Their own brand, not wholesale or arbitrage. Someone
who owns the goals and is tired of being the only person in the building who runs
the numbers.

The defining feature of this customer is not size, it is **the absence of a finance
function**. At $5M a year they are too big to run the business on instinct and too
small to employ anyone whose job is to know what a SKU actually keeps. So the
numbers exist, in five different reports, and nobody reconciles them.

What they already pay for, and what it does not do:

| They have | What it does | What it doesn't |
|---|---|---|
| Sellerboard, Helium 10, Triple Whale (avg 5.4 tools) | Report what happened | Decide anything, or grade a decision |
| A PPC agency | Runs ads, bills a % of spend | Touch price, inventory or claims; prove what it earned |
| A fractional CFO, sometimes | P&L altitude | SKU-level anything |
| A reimbursement service | Files claims, keeps 20–25% | Everything else |

Nobody in that stack can answer "which decision made the profit". That gap is the
entire business.

**Who it is not for:** someone who wants day-to-day creative campaign management,
or another dashboard subscription. The floor is derived from the guarantee, not
chosen: on the page's own inputs (20% of ad spend leaking, 1% of FBA revenue
recoverable) a $2M brand has roughly $3,600 a month to find and a $3M brand roughly
$5,400, so below $3M every invoice voids and the service runs unpaid. Since
2026-09-18 the site's application books every brand that answers its four
questions; one under $3M or on someone else's label arrives tagged `fit:below` in
the booking's `utm_content`, and Hagen settles it on the call; nothing in the engine
reads that tag, and the hourly operator provisions every non-test booking. The
below-the-bar screen (Teardown, Recovery Only request, position list) is gone from
the site. Recovery Only is offered by Hagen, by email, after the call; `api/gate.js` still
accepts that request, but nothing on the site posts to it.

---

## What Hubricon actually does

Five money decisions, made for the client, inside their own account.

1. **Prices.** Per-SKU demand elasticity with a 95% confidence interval, then the
   profit-maximising price derived from it. Steps are capped at 5% per SKU per
   two-week cycle, and Buy Box share (Amazon) or conversion rate (Shopify) is read
   while the step is live so a step too far is caught in days.
2. **Ads.** Every search term or ad set that spent with zero attributed sales,
   listed in dollars and negative-matched. The account's spend-response curve is
   fitted and the break-even point derived from the client's own margin, rather
   than from a target somebody typed into a tool.
3. **Inventory.** Twenty thousand simulated demand paths per SKU against supplier
   lead times, producing a stockout probability, a reorder date and a quantity.
   The newsvendor critical fractile sets the service level each SKU's margin
   actually justifies, so a 40%-margin SKU and a 6%-margin SKU are not treated
   alike.
4. **Fees.** Robust-z and CUSUM change detection over every fee-per-unit,
   conversion and spend series, so a $0.30 per-unit fee change is caught in the
   cycle it happens rather than the quarter after. Plus size and weight band
   cliffs: the ounce or inch over an edge that is paid on every unit.
5. **Claims (Amazon only).** Four of the client's own exports reconciled against
   what Amazon has already paid, to find what its automatic reimbursement missed
   or underpaid, then filed inside the 60 and 120-day windows.

Prices and ads are executed by Hubricon under a standing mandate the client sets
at kickoff. Reorders and claims are prepared, dated and valued, and wait for an
explicit yes. Everything else — a bigger price step, a new campaign, anything
touching inventory orders — needs written approval.

**Access.** One permissions-scoped user on Seller Central with exactly four
permissions (Business Reports view, Fulfillment reports view, Pricing edit,
Campaign Manager edit), or one Shopify collaborator account limited to Orders,
Products, Analytics, Reports, Marketing and Discounts. Neither can touch banking,
tax, payouts or account settings. Revocable in one click. Clients who prefer not
to grant a seat can send CSV exports through a secure upload page instead.

---

## The Profit Record, which is the actual product

This is the thing to understand. Everything else follows from it.

Ad attribution tools answer "which ad made the sale". Nothing answers "which
decision made the profit". A brand owner raises a price in March, cuts a campaign
in April, reorders early in May, and next month's payout is one number that hides
whether any of it worked.

The Profit Record fixes that. Before a move goes live it is written down with the
dollars Hubricon expects it to earn. Afterwards it is measured from the client's
own Seller Central or Shopify exports and graded by **how we know**:

- **direct** — confirmed by the platform's own record (Amazon paid the claim)
- **isolated** — measured on the exact line the move named
- **attributable** — measured against a stated counterfactual
- **unmeasurable** — we could not isolate it, so nothing is banked and the row says so

Four guards apply to every measurement, enforced centrally in
`measurement.py::_verdict` so no new measurement family can skip them:

1. **Capped at the promise.** An isolated or attributable result is banked at the
   expected figure; any excess is recorded and named, never totalled. (Direct is
   exempt: a claim pays what Amazon pays.)
2. **Materiality floor.** Under a threshold the move closes rather than banking noise.
3. **Persistence.** The effect must still be present in the latest export. One
   lucky period is not a result.
4. **One dollar, one move.** The same SKU-period movement is credited once.

Misses stay on the record. A move that came in under its expectation is shown at
what it actually earned. This is deliberate: the record is the only thing on the
page that can cost Hubricon money, so it is the one number that cannot be inflated.

The record separates two states:

- **Proven** — measured on the client's own later exports, or paid by Amazon.
- **Found, not yet banked** — a move actually executed at its expected dollars but
  not yet measured, plus a claim actually filed but not yet paid. Strictly that:
  a move merely *issued* does not count, and a claim merely *detected* does not
  count (`value.py`, `IDENTIFIED_CLAIM_STATES = ("filed",)`).

The client can export the whole record, free, within one working day, any day,
including the day they cancel.

---

## Why it is priced the way it is

**$6,000 a month, flat. One plan. No tiers, no setup fee, never a percentage of
spend.**

Four reasons, in order of importance.

**1. The fee has to be small against the arithmetic.** On a $5M brand, the low end
of two industry numbers Hubricon did not invent is about $9,000 a month leaking or
owed before a price is touched: roughly $5,000 of non-converting ad spend on a
$25k ad account, and roughly $4,000 a month of recoverable FBA revenue. Those are
labelled on the site as arithmetic from named, interested sources, not as results.

**2. Flat fee removes the incentive problem that gets agencies fired.** A PPC
agency billing a percentage of spend profits when spend goes up. Hubricon's advice
can never inflate its own invoice, which is why "flat fee, never a % of your ad
spend" is a headline term rather than a footnote.

**3. It replaces a stack that costs more and measures nothing.** Assembled
separately — tools, a PPC agency, a recovery service taking a cut, a fractional
CFO — the same functions run $5,700 to $15,000+ a month, and none of those vendors
executes across all of it or grades any of it.

**4. It is a one-person service.** The person who builds the models makes the moves
and takes the calls. There is no account manager and no support tier. That caps
how many accounts can run at once, but no ceiling is published and no brand is
refused, because the founder takes every call.

### The guarantee: Proven or Void

Rebuilt on 2026-09-25 as a stack of four named guarantees, each answering one
fear a founder brings to a stranger's $6,000 invoice. All four are in
`terms.html` and all four are enforced in code; `hubricon promises` names any
that cannot run for want of a secret.

- **Month one is free.** Thirty days of the full service, unconditionally.
  No card exists to charge.
- **No bill until the Record covers it.** Every retainer invoice is held at
  draft by the webhook (`lib/stripe_events.js`) until the operator's gate has
  judged it: if what the Profit Record has proven, plus what it has found and
  filed, is more than everything billed since day one (that invoice included),
  it is sent; if not, it is voided before it reaches the client. At day 30 the
  code that would start billing checks the Record first, so below the bar **no
  subscription exists at all**. The bar is cumulative. The work does not stop
  while the Record catches up. If an invoice ever reaches a client before the
  check and they paid it, it is **refunded to their bank, never credited**.
- **Leave any day, trued up.** Cancel by one email, effective immediately, no
  notice, no fee. `hubricon cancel` ends the subscription; the next operator
  pass checks the Record once more against everything billed and not refunded,
  voids anything unpaid, and refunds any gap left (terms §5, within seven days).
  Found dollars that carried an invoice and later measured short come back
  here. Data and the full Record export free, any day.
- **Late Teardown, free month.** A Teardown more than 24 hours after the
  client's first readable upload (or first seat pull) adds a second free month,
  once, whatever the Record shows. The client is told; they do not ask.

Also: if the email announcing a planned move does not go out, nothing moves.
The veto window only opens on a sent notice, which is code, not policy.

What is explicitly **not** promised: a result. Forecasts are probabilities and
Amazon changes its fees without asking. The promise is that the invoice can
never outrun the proof, and that nobody leaves having paid more than the
Record shows.

**The price of the free month** is a short testimonial and permission to publish an
anonymised result — asked once, on a private page, each a separate yes. Plus a
referral link: a founder sent gets the same free month, and when their first
invoice stands, the referrer's next month is credited.

**The downsell**, offered by email only and never on the site: Recovery Only. No
monthly fee, 25% of reimbursements Amazon actually pays on claims Hubricon filed.

---

## What the client actually experiences

| When | What happens | Their time |
|---|---|---|
| Day 0 | Four-question application, then book the 20-minute call on the spot | 2 + 20 min |
| Day 0 | Grant one seat, or send ~15 min of exports, plus a one-row-per-SKU cost sheet | 2–20 min |
| Within 24h | **Profit Teardown**: every SKU's true net margin, stockout odds, demand curves, ad break-even, dated claims. Written report plus a recorded walkthrough. Baseline recorded before anything is touched. | — |
| Kickoff | 90-day plan presented: quarterly targets and the three or four moves that get there. Standing mandate agreed. | 45 min |
| Every cycle | One email three days **before** anything moves, listing each planned move with its expected dollars. Reply no to any of them. | 5–10 min |
| Every 2 weeks | **Profit Brief**: a short video plus a written letter — what was found, what moved, what it earned, and the running record | — |
| Weekly | Sweep: re-ingest, re-run models, re-measure the record, raise alerts | — |
| Day 30 | The record decides. Below $6,000 proven and found, no invoice exists. | — |

Total client time: about ninety minutes in month one, then five to ten minutes
every two weeks.

---

## How it is built

**Engine** — Python, in `engine/src/hubricon_engine/`. Around 770 tests.

- `models/` — margin, elasticity, pricing_engine, ad_efficiency, inventory_sim,
  inventory_econ, recovery, anomaly, forecast, cashflow, risk, health_score,
  fee_schedule
- `ingest/` — twenty parsers for Amazon and Shopify exports (business reports, SKU
  economics, PPC search terms, FBA inventory/returns/reimbursements, settlement
  transactions, Shopify orders/products/payouts/inventory, Meta and Google Ads, COGS)
- `value.py` / `measurement.py` / `billing.py` — the record, the grading, the gate
- `directives.py` / `issue.py` — moves drafted, emailed before they go live, veto windows
- `operator.py` / `cli.py` — the funnel machine and about forty commands
- `cold/` — the outbound engine that prices a public listing and writes to its seller

**Data** — Supabase Postgres, 42 migrations, ~55 tables, row-level security. Model
tables are service-role only; the client portal reads through RPCs.

**Client-facing** — static pages on Vercel: `index.html` (landing), `portal.html`
(the client's own sign-in, called simply *Hubricon*), `welcome.html`, `terms.html`,
`privacy.html`, `results.html`, `teardown.html` (a browser calculator), `intake.html`
(secure upload). Serverless routes in `api/` for intake, consent, teardown and the
Stripe webhook.

**Scheduled** — GitHub Actions. An hourly operator (outbound, replies, bookings,
nudges, teardowns, billing gates), a daily issue job (Profit Briefs and the Buy Box
watch), a Monday sweep (ingest, models, measurement, and the move queue).

**Billing** — Stripe, invoiced by email, ACH, net-7. No card on file, ever.

---

## How customers arrive

1. **The 60-second Teardown** at `/teardown` — a browser calculator that prices one
   listing off Amazon's or USPS's published rate card. No call, nothing stored
   unless asked. Solves one narrow problem completely and reveals the next.
2. **The 90-second demo** — built into the site and behind a single constant until
   the video exists (see `OPERATIONS.md`). The red button is the only solid fill
   and the only red on the site, deliberately.
3. **The free Profit Teardown** — the whole catalogue, back in 24 hours, kept
   whether or not they engage.
4. **The Proving Month** — thirty days of the full service, free.
5. **Paid**, month to month, proven or void.

Outbound is a cold engine that harvests public Amazon and Shopify sellers, prices a
real finding on one of their listings, and writes about that finding. Role inboxes
are never cold-emailed — that is a standing founder decision.

---

## The vocabulary, and why it matters

These names are in force on every client surface. They came out of three judged
rounds against Hormozi's and Becker's standards plus a burned-seller read.

| Term | Means |
|---|---|
| **Managed Profit** | The paid engagement. Always said near "prices, ads, inventory, Amazon claims" — alone it reads as bookkeeping |
| **The Profit Record** | The ledger. "Every move gets a receipt" |
| **Hubricon** | The client's portal, said the way a seller says "open Seller Central" |
| **The Proving Month** | Month one, free |
| **Profit Brief No. NNN** | The fortnightly letter |
| **Before it goes live** | The veto queue |
| **Proven or Void** | The guarantee |
| **found / proven** | The two states of a dollar |
| **Recovery Only** | The downsell. Emails and terms only, never the site |

**Retired, and never to be reintroduced in client copy:** desk, ledger (the terms
define it once), quantitative, retainer (the terms keep it once as the legal noun),
engagement, directive, "three-minute brief", "40+ fee types", "you never log in
anywhere", "the gate is fit, not slots". The seller judge closes the tab on these.

---

## What is true today, and what is not

This matters more than anything else in this document, because the entire offer is
built on not overstating.

**True and verifiable in code:** the measurement grading and its four guards; the
void gate; the veto that cannot open on an unsent email; claims counted only when
Amazon actually pays; the 24-hour Teardown clock; the free export; the daily Buy
Box check; Amazon's 2026 peak fee card, verified against Amazon's own announcement.

**Not true, and never to be implied:** there are **zero paying customers and zero
published results**. `results.html` reads zero honestly and says so. No testimonial,
logo, client count or dollar result may appear until a real one exists. Industry
statistics on the site are labelled as arithmetic from named, interested sources,
because research found no independent study behind any of them — and one claim
("40% of reimbursements die unfiled") was deleted outright because its citation
chain is broken.

Every judge across three rounds named the same thing as the largest remaining gap:
the empty results wall. No copy closes it. Only the first five brands do.

**Known gaps that are founder actions, not code problems** — see the full table in
`OPERATIONS.md`: `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID` need adding to GitHub's
Production environment before the operator can bill, hold, void or refund (as of
2026-09-25 they are absent; Vercel's webhook has its keys); `npm run stripe:setup`
must run once to subscribe the webhook to every invoice event and rename the
product; `hubricon stripe-smoke` with a test key proves the Stripe calls; the
four-permission seat cannot open a support case, so claims are filed with the
client's yes.

---

## Where to look

| Question | File |
|---|---|
| How the machine runs, and the ten decisions taken on 2026-09-11 | `OPERATIONS.md` |
| Where leads come from, free | `GROWTH.md` |
| The offer, as a stranger reads it | `index.html` |
| What a client is owed, legally | `terms.html` |
| The record, graded | `engine/src/hubricon_engine/{value,measurement}.py` |
| The gate that voids an invoice | `engine/src/hubricon_engine/billing.py` |
| Turning on the 90-second demo | `OPERATIONS.md`, one constant in two files |

---

*Founder: Hagen Simmons, Dallas, Texas. Applied mathematics at the University of
North Texas, minor in actuarial science. One person, every account.*
