# Hubricon landing page rework — build prompt

## Context

You are reworking `index.html` for Hubricon, a founder-operated Managed Profit service for
Amazon and Shopify brands doing $1M–$20M/yr. $6,000/mo flat, month one free, every invoice
after is "proven or void" against the client's Profit Record. Free Profit Teardown delivered
in 24 hours. One operator: Hagen Simmons, Dallas.

The current page is ~8,000 words across ~15 sections. It is rigorous and honest and almost
nobody finishes it. The buyer is a founder doing $1M–$20M who decides in under fifteen seconds
whether this is another agency. Time is the scarcest thing he has.

**Do not change the offer, the pricing, the guarantee structure, or any factual claim.**
This is a compression and sequencing job, not a rewrite of the business.

## The single diagnosis

The page substitutes proof-of-thinking for proof-of-results, because there are no results yet.
Every extra section is an argument compensating for a missing case study. The fix is not better
arguments. The fix is to stop trying to close the $6,000 retainer on the page, and close the
free Teardown instead. The Teardown closes the retainer, on the client's own numbers.

## Hard constraints

- Target: **~1,400 visible words**, eight sections, roughly four desktop screens to the final CTA.
- Nothing is deleted. Everything cut moves to a new `/method` page, linked from the body.
- One primary CTA, repeated: **Get your free Profit Teardown**. No competing CTAs.
- Every claim that survives keeps its existing wording where possible. Compress by removing
  sections and sentences, not by paraphrasing careful language into vague language.
- Keep the existing visual system: dark navy, amber accent, glass panels, Fraunces headings,
  the reveal-on-scroll motion, the sticky mobile CTA.
- Mobile first. Assume the hero is read on a phone in a warehouse.

## Section spec

### 1 · Hero — keep the H1, add the gate
Keep the existing H1 verbatim: *"More than $6,000 a month of profit, found in your account and
proven on your own reports. Or you don't pay."*

Under it: one sentence of mechanism, the four term chips ($6,000/mo flat · Month one free ·
Proven or void · No card), one CTA, then **the qualification line** as the last element:

> We work with private-label brands doing $3M–$20M. Below that, the money we'd find doesn't
> clear our own bar — and we'd rather say so here than bill you for a month we can't prove.

Cut the hero ticker on desktop; it duplicates the chips. Max 70 words below the H1.

**The badge changes from $1M–$20M to $3M–$20M**, everywhere it appears on the site, including
meta description, OG tags, and the fit check.

### 2 · The live 60-second Teardown — NEW POSITION, highest priority change
The interactive teardown tool currently at `/teardown` is linked only from the nav. **Embed it
here, directly under the hero.** Headline along the lines of *"Don't take the math on faith.
Price one of your listings right now."* Input, result, then one line: *"That was one listing off
public pages. The full Teardown runs every SKU you have, in 24 hours."* → CTA.

This is the authority engine. With no clients and no logos, demonstrated competence in the
visitor's browser is worth more than every credential and formula on the page combined.

### 3 · The Profit Record — compress hard
This is the actual differentiator and it currently runs ~700 words. Cut to ~150 plus the sample
table. Keep: the Seller Central vs Profit Record contrast (two short columns), the five-row
demo table with the honest miss, the three totals, and the sentence that the Record is what
voids the invoice. Cut the month-one/month-six paragraph, the "unmeasurable fourth outcome"
paragraph, and the attribution explainer — those move to FAQ.

**Remove "No published result yet" from this position.** Replace with a founding-cohort line
that reads forward, not backward: *"Founding clients. The first published result posts when the
first Proving Month closes."* The published-results link stays.

### 3b · The proof — ONE case study, told in full

This section ships only when a real client's Proving Month has closed and that client has
given written permission to publish. Until then this section does not exist on the page and
nothing stands in its place. Do not write placeholder results, composite clients, or
illustrative examples in this position. Every other section on this page is load-bearing on
the claim that all numbers are checkable; an unverifiable case study here voids all of them.

When the inputs exist, build it to this spec. One client, not a wall.

- **Named brand, with permission on file.** An anonymized case is worth roughly a third of a
  named one and should only be used if the client refuses naming.
- **The founder's before-state, in their own words, about their life and not the P&L.** One
  or two sentences. What they were doing on Sunday nights, what they could not answer when
  their accountant asked, what decision they had been putting off. This is the emotional
  through-line and it belongs before any number.
- **Three checkable numbers**, each with the method beside it: what was found, what was
  proven, what it was measured against. Pull them straight from the real Profit Record.
- **The real Record, redacted.** Same table shape as the demo, real rows, SKU identifiers
  masked. This is the artifact; it carries more weight than the quote.
- **Include a recorded miss.** A case study with an honest under-delivery in it is
  substantially more credible than a clean one, and it is the only version consistent with
  the rest of this page.
- **One short quote**, ≤ 30 words, about what changed in how they operate — not a rating of
  the service.
- Target ~180 words plus the table. Resist adding a second case when a second client closes;
  add it only when the first has been pushed as far as it goes.

Placeholder while empty: nothing. The Record section's founding-cohort line already
communicates the stage honestly.

### 4 · What you get — 3 cards, ~45 words each
Teardown / Moves made in your account / Profit Record. Keep the demo-data visuals. Cut the long
fee enumerations inside each card; the fee detail lives in the FAQ and on /method.

### 5 · How it works — 4 steps, lead with the time cost
Open with the time number, because it is the strongest thing in this section:
*"Your whole time cost: about ninety minutes in month one, then five to ten every two weeks."*
Collapse the current six steps to four: Apply & call → One seat → Teardown in 24 hours →
The Record decides at day 30. Each step ≤ 35 words. The veto mechanics and the 90-day plan
detail move to FAQ.

### 6 · Price and Proven-or-Void — merge into one block
The four guarantee layers become four one-sentence lines with their existing headers.
"Where the $6,000 comes from" becomes a collapsed `<details>` containing the current five-item
breakdown and the full sourcing paragraph. The vendor-stack comparison ($5,700–$15,000 vs
$6,000) stays visible — it is one line and it does real work. The competitive comparison table
moves to /method.

### 7 · The person in your account — rewrite for authority
Keep: one operator, no handoffs, the calendar is the only gate, the export hedge, the photo,
the signature, the four principles as a single row.

**Cut the word "undergraduate."** Do not state enrollment status. Keep the actuarial-science
training and say what it does: it prices uncertainty for a living, and that is what every model
on the page is. Keep the "let the Record grade me every month" paragraph — that is the
authority, not the biography. Target ~120 words.

Merge the fit check into this section as two short lists.

### 8 · FAQ and close
FAQ stays collapsed, twelve items is fine collapsed, absorb the detail cut from sections 3–6.
Close section keeps the two-clocks urgency compressed to one strip (claim windows expiring,
peak fee card October 15) and the application form.

## What moves to /method

Create `/method` and move there intact:
- All eight formula cards and the five supplementary models
- The four-column competitive comparison table
- The full source-provenance paragraph

Link it from the body twice, once from the Profit Record section and once from pricing, with a
single line: *Every formula we run, in the open →*. Do not summarize the formulas on the main
page. Do not tease them. One link.

## Voice rules for any rewritten copy

- Plain declarative sentences. No em-dash asides stacked three to a sentence.
- No hedging clauses inside a value claim. Caveats get their own sentence, after.
- Never explain the mechanism before stating the outcome.
- Keep the existing honesty moves (the recorded miss, "what we do not promise", "if we find
  nothing we tell you"). They are the page's best asset and they are short.

## Qualification — the filter, and where it must not go

The revenue floor moves from $1M to **$3M**. This is not a positioning choice, it is derived
from the guarantee: proven-or-void only lets an invoice stand if the Record covers everything
billed since day one. On the page's own published inputs (20% of ad spend leaking, 1% of FBA
revenue recoverable), a $2M brand yields roughly $3,600/mo findable and a $3M brand roughly
$5,400 — at or under the $6,000 bar. Below $3M the invoice voids structurally and the service
runs free indefinitely. Update the ICP everywhere: badge, meta description, OG tags, fit check,
FAQ, and the outbound engine's `SUPERSEARCH_FILTERS` revenue bands.

**Delete these lines entirely.** They contradict the position:
- "Every brand that applies gets the call" (appears three times)
- "Under $1M, or not private label? Book the call anyway — the Teardown is free, and we'll
  tell you straight on the call whether the fee makes sense for you."
- "peak fees in 34 days" in the sticky CTA

**Filter the page, not the application.** With no clients yet, Teardown volume is the growth
engine — it produces the testimonials, the published results, and the cold-email proof. The
price above the fold and the stated floor do the qualifying before anyone clicks. Do not add
manual review, do not add questions, do not add a waitlist.

Application behaviour, unchanged for qualified visitors:
- Same four questions (where you sell, revenue, model, catalog size), same instant calendar,
  same answers riding along on the booking. A $5M founder reaches a booked call in under two
  minutes.
- **One new branch:** if revenue is under $3M, or the brand is not their own private label, the
  calendar does not render. Show instead a short screen — one paragraph saying the bar can't be
  cleared at that size and why, no apology — that routes to **Capital Position** at `/position`,
  the $6,000/yr tier specified in `hubricon-capital-position-build-prompt.md`. A rejection
  becomes a rung. Until that tier is built, the screen carries the 60-second Teardown tool and
  an email capture for the free weekly position page.
- No exceptions UI. If the founder wants to make an exception, he does it by email.

## The luxury pass

Run this over the whole page after the structural work. The reference is Acquisition.com's
restraint, not Hyros's proof-stacking — Hyros derives authority from a client roster, which
Hubricon does not have and must not simulate. Restraint costs zero clients.

- **Cap "free" at two occurrences on the page.** Once in the hero, once at the final CTA.
  Everywhere else the Teardown is described by what it is, not by what it costs.
- **Never defend the price.** $6,000/mo flat is stated and not justified in the open. The
  five-item value breakdown and the vendor-stack comparison live inside the collapsed
  `<details>` for the one visitor who asks.
- **Remove all countdown framing.** Delete "peak fees in 34 days" from the sticky CTA. The
  claim-window and October 15 facts stay as facts in the close strip; no timers, no
  diminishing counters, no "only X left".
- **State the filter flatly.** Rewrite the fit check as a plain boundary: $3M–$20M, 10+ SKUs,
  real pricing power, own brand. No apology line, no "book the call anyway", no softening.
- **State the scarcity once, as fact.** One operator, one kickoff at a time, booked in order.
  One sentence, surrounded by whitespace, never repeated.
- **Increase vertical rhythm.** Section padding up, max line length ~60ch, headline sizes hold
  or grow while body copy shrinks in volume. Air is the format's luxury signal.
- **No exclamation marks, no "imagine", no rhetorical questions as headers.**
- **Delete "undergraduate."** See section 7.

## Acceptance check

Before shipping, verify:
1. A visitor can get from the top of the page to a booked call having read under 400 words.
2. The 60-second Teardown is reachable without scrolling past two screens.
3. No sentence on the page tells a stranger the service has no track record.
4. The word "undergraduate" does not appear.
5. Total visible word count is under 1,600.
6. Every removed claim exists verbatim on /method, /terms, or in the FAQ.
7. "$1M" appears nowhere on the site, including meta tags and the outbound engine's filters.
8. "Every brand that applies gets the call" appears nowhere.
9. The word "free" appears at most twice on the visible page.
10. A qualified visitor still reaches a booked call in under two minutes and four questions.
11. No countdown, timer, or diminishing-availability element exists anywhere.
12. Capital Position is referenced nowhere on this page except the footer link and the
    sub-$3M application branch. It never appears as a second column or a price comparison.
