# The monopoly doctrine

*How Hubricon becomes the only answer in its category, and stays it. Written
2026-09-25 at the founder's instruction: proprietary technology at least ten times
better than the alternatives, network effects, economies of scale, and a brand people
identify with. `HUBRICON.md` says what Hubricon is; `BRAND.md` says how it looks and
sounds; this file says what it is building toward and the rules every piece of work
is held to on the way. Nothing here overrides HUBRICON.md's honesty rules. A
monopoly built on a claim that isn't true is a lawsuit, not a moat.*

---

## The rule this file exists to enforce

**Every piece of work names the moat it deepens.** A commit body carries one line,
`Moat: tech`, `Moat: network`, `Moat: scale`, `Moat: brand`, or `Moat: none (why)`.
"None" is allowed (a legal fix, a bug) and has to say why. Once a quarter the
scoreboard at the end of this file is updated with measured numbers, and a moat with
no commits in the quarter is a finding, not a footnote.

---

## The secret

Peter Thiel's question is what important truth very few people agree with you on.
Hubricon's answer:

> **Nobody in e-commerce services is paid on proof, because nobody can afford to be.**
> Proof needs the number written down before the move and measured afterwards on the
> client's own data, with the misses kept. Only a machine built for that can survive
> the guarantee.

That is why the guarantee is the moat's price of admission, not its marketing. A
competitor can copy the words "or you don't pay" in an afternoon. Copying them without
the measurement engine means going broke on voided invoices or cheating on the
measurement, and cheating shows on a Record the client can export any day. The
guarantee is cheap for Hubricon and ruinous for anyone without the machine.

---

## The council

The founder asked for these principles in the likeness of the people who proved them.
One verdict each, and the decision it produced.

1. **Peter Thiel: own a small market completely, then expand.** The beachhead is
   founder-run, private-label brands at $3M–$20M a year on Amazon and Shopify, with no
   finance function. *Decision:* no feature for anyone outside the beachhead until ten
   brands have closed a Proving Month. Be the last mover. Once the Record is the
   standard, everyone else is compared to it.
2. **Brian Chesky: design the 11-star experience, then build the 7.** *Decision:* the
   ladder below, with stars 6–8 as the next twelve months.
3. **Jeff Bezos: the flywheel, and "your margin is my opportunity."** The agency's
   percentage of spend is Hubricon's opportunity. *Decision:* the price stays flat;
   what automation saves goes into the guarantee's reach and the service, not into
   margin, until the category is ours.
4. **Charlie Munger: incentives, and inversion.** "Show me the incentive and I'll show
   you the outcome." The flat fee and the void gate are the incentive design, and the
   brand is built on them. Inverted: what kills Hubricon? One overclaimed result; the
   founder as the bottleneck; a platform change that breaks ingestion; a rival with
   more data. *Decision:* each has a countermeasure in this file (honesty rules, the
   scale metric, the fleet detector, the pooled book).
5. **Andrew Carnegie: know the cost of every unit.** Carnegie ran steel on cost
   accounting to the ton. *Decision:* founder minutes per account-month is the scale
   metric, measured, not estimated.
6. **Palmer Luckey and Trae Stephens (Anduril): build on your own money, sell the
   product, never the hours; name the villain.** *Decision:* the Proving Month is our own
   money; percent-of-spend is the villain; the manifesto and the named artifacts (the
   Record, the Seal, the Teardown, the Proving Month).
7. **Mike Cessario (Liquid Death): make the boring category an identity; one icon,
   repeated.** *Decision:* the receipt and the stamp; one dry line per page at most.
8. **David Ogilvy: facts sell, and every piece is an investment in the brand's
   personality.** *Decision:* numbers before adjectives, every figure labelled for what it
   is.
9. **Luca Pacioli: double entry.** Five centuries ago every dollar got two entries.
   *Decision:* every move gets two: the call and the measurement, chained by the Seal.
10. **Jim Simons, Ed Thorp and Ken Griffin: the edge is data plus discipline.**
    *Decision:* publish the formulas (the secrets are free; the hands are $6,000), keep
    the data (it compounds), and re-run the pre-registered bench after every model change.
11. **Andy Grove: only the paranoid survive.** The ten-times force is Amazon's own
    pricing and advertising automation. It optimises Amazon's objective and grades
    nobody. *Decision:* stay the seller's side of the table, grade ourselves on the
    seller's exports, keep both platforms, and add a third only after the beachhead.
12. **Sam Walton: pass the savings on.** A scale advantage becomes a moat only when the
    customer gets it, because then a smaller rival cannot match the offer. *Decision:*
    when cost to serve falls far enough, extend the same guarantee downmarket to
    $1M–$3M brands rather than widen the margin.

---

## Moat 1: proprietary technology

### Why it is already more than ten times better

The alternatives answer a different question. An agency reports activity, a dashboard
reports history, a fractional CFO reports the P&L, a reimbursement service works one
lever. None of them can say what any single decision earned. Hubricon makes the
decision, writes down its dollars before it goes live, measures it on the client's own
exports under four guards (capped at the promise, a materiality floor, persistence,
one dollar credited once), keeps the misses, puts an interval on every number, runs a
pre-registered model-risk bench (10/10 on its three tests), and voids its own invoice
in code when the Record falls short. That is not an improvement on the alternatives'
answer. It is an answer they cannot give.

### The 11-star ladder

What the product is at each star, for a founder at $5M a year.

| ★ | The experience | Status |
|---|---|---|
| 1 | An agency's monthly PDF. You can't tell what it earned. It bills a percentage of your spend. | the market |
| 2 | A dashboard. Everything that happened, nothing decided. | the market |
| 3 | A good PPC agency. Better ROAS on ads alone, still paid on spend. | the market |
| 4 | A fractional CFO. A monthly P&L; nothing per SKU, nothing executed. | the market |
| 5 | Five money decisions made in your account, each called in writing before it goes live, measured on your exports, no invoice until the Record covers it. | **live in code** |
| 6 | The engine keeps score of itself, and you can see it: promised against measured for every move (live in the portal), plus a published hit rate, the share of calls whose measured outcome landed inside the promised band. | half live; the hit rate is next |
| 7 | Every call sealed: tamper-evident, time-witnessed pre-registration a buyer or lender can verify without trusting us. | **live 2026-09-25** (`seal.py`, `scripts/verify-record.mjs`; migration applied, first seals with the first real client's first move) |
| 8 | The first move is as good as the hundredth: a platform change caught in one consenting account is flagged in all; day-one promises priced from what every consenting brand's moves actually delivered. | **detector live 2026-09-25**, inert until three clients consent; priors after the bench |
| 9 | The Record is an asset. A diligence-grade export that raises what the brand is worth to a buyer or a lender. | later |
| 10 | The engine runs the P&L to targets you set and you approve by exception; each quarter shows the counterfactual, your brand without the moves. | later |
| 11 | The Record is the standard. Buyers, lenders and platforms ask for it the way a lender asks for a credit score, and a brand without one is priced at a discount. Hubricon is to decision quality what a rating agency is to credit. | the ambition |

### The next three builds, in order

1. **Anchor the Seal outside our own walls.** The Seal is on (2026-09-25): every move
   of a real client is fingerprinted (RFC 8785 canonical JSON, SHA-256, one chain per
   client and one global chain) before its email goes out, the email prints the first
   twelve characters of its seal, every measurement is chained after the promise it
   answers, the table refuses edits and deletions (the service role's included), and
   `hubricon seal verify` or the dependency-free `scripts/verify-record.mjs`
   recomputes all of it from a Record export. What it cannot yet prove (HUBRICON.md
   says so): the head has no external timestamp anchor. Next: OpenTimestamps on the
   daily global head, or a Wayback capture of a GET endpoint serving
   `public_record_seal()`; then the head on /results and the seals in the portal.
2. **The hit rate, published.** Compute `replay.score` per client on every measurement
   pass, store it with the run, and show it in the portal and, once consented, on
   /results: calls scored, band coverage, realisation ratio. Honest from the first
   measured move, labelled "too few to judge" below `MIN_SCORED_FOR_CALIBRATION`.
3. **Time to first proof.** The Teardown's guarantee is 24 hours; the ten-times version
   is the same Teardown the hour the files land. `MATH_SCORECARD.md` owns the model
   work list; this is the product-speed item beside it.

---

## Moat 2: network effects

The honest position: with no clients there is no network yet. The work now is to lay
the pipes so the effect starts with the second account, and to design the consent so
that founders want to join.

**The constraint that shapes all of it.** Terms §10: we never use one client's data to
advise another, except with explicit consent. The `calibration` consent covers the
teardowns' public estimates and nothing else. Every loop below runs only on accounts
that granted the new `network` consent, only on aggregates (a rate, a direction, a
date, a ratio, never a figure of anyone's), and every pooled number says how many
accounts stand behind it.

### The loops, in the order they can start

1. **The fleet detector** (direct, starts at the account floor). A platform-wide change
   (an Amazon fee, a reimbursement rule, a carrier rate) seen in several consenting
   accounts at once is flagged in every account, with how many accounts stand behind
   it and whether it shows yet in the recipient's own data. Each account added raises
   the chance a change is caught in its first week and lowers the false-alarm rate a
   single account lives with. **Built 2026-09-25** (`fleet.py`, `hubricon fleet`; by
   hand until the Monday sweep step on the branch `workflow-fleet` can be pushed): each account's own change-point tests on Amazon's
   FBA fee per unit and referral rate, a declaration only when at least three
   consenting accounts agree inside 45 days at a 1% false-discovery level, and a named
   refusal below any floor. In simulation, a 5% fee step three exports old is declared
   across the book in 80–100% of books, where one account's own sweep reports it about
   31% of the time; forty noise-only books declared nothing. That gap is the network
   effect, in numbers, and it widens with every account added. It switches on when the
   `network` consent and its migration are live. Not covered yet: storage fees (they
   would mistake the Q4 stock build for a platform change), Shopify's fee lines,
   reimbursement rules and carrier rates.
2. **The book's realisation** (indirect). What each kind of move actually delivers
   across consenting accounts, with a band from resampling accounts. **Built
   2026-09-25 as a report only** (`hubricon book`, five accounts and eight measured
   moves before it says anything). It writes nothing and changes no promise until a
   bench-validated change says it should. More accounts, tighter promises, fewer
   voided invoices.
3. **Category priors** (the ten-times lever for thin catalogues). The scorecard's own
   table says a seller with seven months and 10% price variation gets a priced
   destination on one SKU in six. A prior pooled across consenting brands in the same
   category is how the other five get one on day one. It needs the client's category on
   the row (scorecard items 5 and 7) and ten consenting accounts in a category first.
4. **The two-sided standard** (later). The Record read by acquirers and lenders. More
   brands with Records, more buyers who accept them, more brands that want one.
5. **Referral** (live). A founder sent by a client gets the free month; the sender's
   next month is credited when the new brand's first invoice stands.

**The recipient policy is the founder's call** (`fleet.RECIPIENT_POLICY`, set to
`every_client`). Recommendation: keep it. Every client gets the protective alerts,
because a paying client should never be left exposed to a fee change we saw; give-to-get
belongs on the benchmark instead (`models/benchmark.py`: where your numbers sit among
other consenting brands'). That needs one more clause in the `network` consent and
terms §10, because the benchmark today reads the `calibration` consent, which terms §10
limits to the Teardown's public estimates. It is founder-only, so nothing is exposed,
but it must move before its output reaches a client.

---

## Moat 3: economies of scale

**Where cost falls as accounts are added.**

- *The engine* is a fixed cost. The model stack is built once and runs a 400-SKU
  catalogue in about 75 seconds of compute (the run-cost table in `MATH_SCORECARD.md`).
- *Founder time* is the variable cost that matters. Every automation in the operator
  (outbound, replies, bookings, nudges, teardowns, briefs, billing gates) is a scale
  investment; the next ones are execution through the platforms' own APIs (pricing,
  advertising) in place of hands in the seat, and the generated Profit Brief in place of
  a recorded one.
- *Data* compounds. Each consenting account sharpens the book for all (moat 2).
- *Acquisition* amortises. The cold engine prices a public listing at no marginal
  cost; the content pipeline's explainers serve every prospect at once.

**What gets measured.** Carnegie's rule: founder minutes per account-month, cost to
serve, and capacity (accounts per founder-week at the measured minutes). **Built
2026-09-25** (`meter.py`, `economics.py`): tokens, speech characters, emails and engine
seconds are counted where they are incurred and attributed to the account whose work
it was; the founder's minutes come from `hubricon log <client|prospect|all> <minutes>
<what>` and from bookings' own lengths; `hubricon economics [--month YYYY-MM]` prices
it all per account, spreads the fixed base, and states capacity. Every figure is marked
measured or assumed, and a month with nothing recorded shows a dash, never a zero.
Until the founder replaces them, the prices are placeholders (`hubricon economics --set
KEY VALUE`): a $150 shadow hourly rate, a 50-hour week, and about $127 a month of
unverified list-price platform costs.

**What the savings buy.** The price stays $6,000, flat. When cost to serve falls far
enough, the guarantee reaches down to $1M–$3M brands through an automated tier. That is
the Walton move: a scale advantage the customer can see, which a smaller rival cannot
match without the same machine.

---

## Moat 4: brand

The only moat that exists with zero clients, so the first one built. `BRAND.md` holds
the system. The strategy in four lines:

- **Own a word.** *Proof.* "Paid on proof" says the whole business.
- **Own a question.** *"Show me the Record."* Every founder can ask it of anyone they
  pay; only one answer exists.
- **Own an icon.** The receipt and the stamp, repeated until they are the company.
- **Earn it with truth.** The brand's edge over every agency is that nothing on the site
  is inflated: no testimonial nobody gave, no client count, no result that isn't
  consented and measured. The first published Record is the brand's real launch.

**Built 2026-09-25:** the identity, the home page and /apply in it, the founder's photo
off the home page, the manifesto, the film and the stills (Higgsfield), the share card.

---

## The flywheel

```
  Paid on proof (brand) ──────────────► founders book the Proving Month
          ▲                                          │
          │                                          ▼
  Records published, with consent          more accounts on the Record
          ▲                                          │
          │                                          ▼
  more invoices stand ◄── better calls ◄── more measured moves, pooled (network)
          │
          ▼
  cash into automation ──► lower cost per account (scale) ──► same price, wider reach
```

---

## The standing rules

1. **The moat test** on every commit (top of this file).
2. **Truth first.** No claim of a network, a scale, a result or a client that does not
   exist. Future things in the future tense, labelled on the page.
3. **The data is the client's.** Pooling only under the `network` consent, only
   aggregates, and every pooled figure carries its account count.
4. **Flat price.** Economies go to the client and to the guarantee's reach first.
5. **Beachhead first.** Nothing for customers outside $3M–$20M private label until ten
   Proving Months have closed.
6. **Calibrated or silent.** Any model change re-runs the Simons–Thorp–Griffin bench,
   seeds 101/202/303 and 404/505/606, before it ships.

---

## The scoreboard

Update each quarter with measured numbers. A dash means not measured yet.

| Moat | Metric | 2026-09-25 | By 2027-09 |
|---|---|---|---|
| Tech | Stars live on the ladder | 5, with 7 and 8 live and waiting on their first client and first three consents | 8 |
| Tech | Hit rate: calls landing inside the promised band | no measured moves yet | published per client |
| Tech | Bench, three tests / three validation seeds | 10, 10, 10 / 8, 9, 10 | 10 on all six |
| Network | Accounts with the `network` consent | 0 (not yet offered) | 10 |
| Network | Platform changes flagged fleet-wide | 0 | the first |
| Scale | Founder minutes per account-month | — | measured weekly, falling each quarter |
| Scale | Cost to serve, as a share of the fee | — | under 15% |
| Brand | Brands with a published Record | 0 | 3 |
| Brand | Booked calls that name the guarantee or the manifesto as the reason | not tracked | tracked on every booking |

---

## Sequencing

- **Done 2026-09-25.** Ten pending migrations applied to production; the brand, the
  manifesto, the Seal, the network consent and detector, and the unit economics
  deployed; the founder approved every change on the branch.
- **Next 30 days.** The Stripe secrets and `npm run stripe:setup` (`OPERATIONS.md`);
  migration `20260925000004`; real numbers in `hubricon economics`; `hubricon log`
  as a habit; the Seal's external anchor.
- **Next 90 days.** The first five Proving Months. The hit rate in the portal. The first
  consented case study, which is the brand's real launch.
- **Twelve months.** Stars 6 to 8 live. Ten pooled accounts. Category priors validated
  on the bench. Price and ad execution through the platforms' APIs.
- **Thirty-six months.** The Record as an asset (a diligence export, lender and acquirer
  partners), the downmarket tier, and a public index of what the platforms' fees did
  each quarter, built from the fleet detector.

---

## Decisions taken, and the ones still open

**Approved by the founder on 2026-09-25** ("approve every change and go live"): the
`network` consent and the terms §10 and privacy wording; fleet alerts to every client
(`fleet.RECIPIENT_POLICY = "every_client"`), emailed (`hubricon fleet --alert`), at
three accounts, 1% and 45 days; the Seal as built (a
twelve-character seal in the email; a deleted client's hashes kept so the global
chain still verifies, their documents dropped); the /apply welcome video kept until
the sales film exists; the deploy, with the three Stripe and guarantee commits.

**Still open:**

0. Land the Monday sweep step for the fleet detector (the branch `workflow-fleet`): GitHub refused
   it from a token without the `workflow` scope, so the founder chose to ship
   everything else first. `~/.local/bin/gh auth refresh -h github.com -s workflow`,
   then merge the branch and push.

1. Apply `20260925000004_unit_economics.sql` in the Supabase dashboard's SQL editor.
   The session that applied the other ten was not permitted to run this one. Do not
   use `supabase db push`: this project's history records migrations under the time
   they were applied, not their file names, so the CLI would try to run old ones
   again. Until it is applied the meter prints one line per run and counts nothing.
2. The real numbers behind `hubricon economics`: the shadow hourly rate, the working
   week and the fixed monthly costs (placeholders today).
3. The Seal's external timestamp anchor, and where the head and the seals are shown.
4. The benchmark (`models/benchmark.py`) reads the `calibration` consent, which terms
   §10 limits to the Teardown's estimates. It is founder-only; before its output
   reaches a client it needs a clause of its own (the recommendation: add it to the
   `network` consent as the give-to-get).
