# NUMBERS.md: the one place headline numbers are quoted from

`docs/agents/CONTEXT.md` and every text about Hubricon quote numbers from this file and
nowhere else (SUPPLY_VARIABILITY.md, section 5.3). A number that is not a row here does not
go in the shared brief or in front of a client.

```
python3 tools/agent_check.py docs/agents/CONTEXT.md --only numbers
python3 tools/agent_check.py SUPPLY_VARIABILITY.md --section 1 --only numbers
python3 tools/agent_check.py <client text> --client --numbers
```

The first two must exit 0. The third also fails a number whose only status here is
`unverified` or `unverified simulation`.

## How to read a row

- **Number** is the figure as written, with its `$` or `%`. A range is one row, and both
  ends count. The checker matches the value, its decimals and its kind, so `4.0` is not `4`
  and `20%` is not `20`. It does not match what the figure is about. A row is a floor, not a
  proof.
- **Status** is one of the ten words below. Nothing else is accepted.
- **Source or script** is the file that states it or the test that recomputes it. Files in
  Hagen's Claude project (`proof/`, `hubricon-to-4/`, `secret-hunt/`, `sim/`, the problem
  PDF) are not in this repo. Rows that rest on them say so, and none of them can be re-run
  here.
- **Date** is the date on the source. Where the source is not in this repo, it is the date
  of the handoff that records the number, 2026-11-27.

| Status | Meaning | May a client see it? |
|---|---|---|
| proved | Follows by arithmetic or a proof that a test in this repo re-runs | Yes |
| measured | Counted or timed in this repo, by the file or test named | Yes |
| sourced | Stated by a named document. Not re-measured here | Yes, with its source |
| simulated | Came out of a simulation on made-up data. Never evidence of a result (section 4.1) | Only labelled "simulation" |
| estimate | Worked out from stated assumptions. Not measured | Only labelled "estimate" |
| decided | A goal, price or bar Hagen set. Not a fact about the world | Yes, as a goal |
| assumption | A value chosen to make a calculation run | Only labelled "assumed" |
| inference | Reasoned by an agent from the rows above it | Only labelled as inference |
| unverified | Nobody can point to where it came from, or it has been contradicted | No |
| unverified simulation | From a simulation that may have had a bug and cannot be re-run (O2) | No |

No number here is a result on a real brand. Hubricon has no paying customers and no
measured result on a client (CONTEXT.md, "What is true today").

## The goal (27 Nov 2026)

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 300 | cold calls a day | Hagen's daily call target | decided | docs/agents/CONTEXT.md, "The goal, in Hagen's words" | 2026-11-27 |
| 1 | new paying client | The target per day of calls | decided | docs/agents/CONTEXT.md, "The goal, in Hagen's words" | 2026-11-27 |
| $1000 | a month | The new price | decided | docs/agents/CONTEXT.md, "The goal, in Hagen's words" | 2026-11-27 |
| 1000 | paying clients | Where the calls stop | decided | docs/agents/CONTEXT.md, "The goal, in Hagen's words" | 2026-11-27 |
| $6,000 | a month | The flat offer this replaces. Still on the live site until the new pages ship | sourced | HUBRICON.md, "$6,000 a month, flat" | 2026-11-27 |
| 20 to 40 | brands | The first market in the agent files, and the by-hand plan the goal replaces | sourced | .claude/agents/thiel-monopoly-strategist.md and graham-first-customers.md | 2026-11-27 |
| 11 | out of 5 | Hagen's bar for work | decided | SUPPLY_VARIABILITY.md section 7.1, D4 | 2026-11-22 |
| 5 | points | The scale work is graded on | decided | SUPPLY_VARIABILITY.md section 7.1, D4 | 2026-11-22 |

## The engine

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 23 | models | Models one engine run executes on an Amazon client | measured | engine/src/hubricon_engine/cli.py, the `ALL_MODELS` list. Recounted by tools/test_memory.py | 2026-11-28 |
| 22 | models | The same on a Shopify client: fee recovery is skipped | measured | engine/src/hubricon_engine/cli.py and channels.py (`has_recovery`). Recounted by tools/test_memory.py | 2026-11-28 |
| 29 | seconds | A full run on the bench's synthetic catalogue. "About 29" in the source. Not a client's data | sourced | engine/MATH_SCORECARD.md, "What it costs to run" | 2026-09-24 |
| 160 | SKUs | Size of that synthetic catalogue | sourced | engine/MATH_SCORECARD.md, "What it costs to run" | 2026-09-24 |
| 75.5 | seconds | A full run on a larger synthetic catalogue. Not a client's data | sourced | engine/MATH_SCORECARD.md, "What it costs to run" | 2026-09-23 |
| 400 | SKUs | Size of that synthetic catalogue | sourced | engine/MATH_SCORECARD.md, "What it costs to run" | 2026-09-23 |
| 20% | of the lead time | The spread the engine assumes for every supplier, instead of measuring it | assumption | engine/src/hubricon_engine/models/inventory_sim.py, `LEAD_TIME_CV = 0.2`. Pinned by tools/test_memory.py | 2026-11-28 |

## The problem in Hagen's words (section 1.1)

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 6 | shipments a year | How few observations a brand may have from one supplier. Written "six" | sourced | SUPPLY_VARIABILITY.md section 1.1, Hagen's brief | 2026-11-20 |
| 35% | of the sales rate | How uncertain the sales rate must be for demand to outweigh lead time | sourced | SUPPLY_VARIABILITY.md sections 1.1 and 1.2, Hagen's brief and the problem PDF (not in this repo) | 2026-11-20 |
| 3 to 1 | ratio | Demand term against lead-time term at that uncertainty. See the note under the worked example | sourced | SUPPLY_VARIABILITY.md sections 1.1 and 1.2, Hagen's brief and the problem PDF (not in this repo) | 2026-11-20 |

## What supply variability costs (section 1.2)

Every row in this table is stated by SUPPLY_VARIABILITY.md section 1.2, which cites the
problem PDF of 19 Nov 2026. The PDF is not in this repo, so the outside sources it names
(GoFreight, Fulfillmen, Portless, Eightx, IHL) have not been checked here.

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 8 to 12 | times the ocean rate per kg | What air freight costs (GoFreight) | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 15 to 30 | days | Stage 1 of a China to US sea shipment, production (Fulfillmen 2026) | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 1 to 3 | days | Stage 2, pickup | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 3 to 7 | days | Stage 3, booking | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 13 to 16 | days | Stage 4, ocean | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 2 to 5 | days | Stage 5, port | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 1 to 5 | days | Stage 6, customs | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 1 to 4 | days | Stage 7, trucking | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 3 to 5 | days | Stage 8, FBA check-in | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 36 to 70 | days | The total the source gives for the eight stages. It does not match their sum. See "Open discrepancies" | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 39 to 75 | days | What the eight stage ranges above add up to | proved | tools/test_memory.py, `test_the_stage_ranges_sum` | 2026-11-28 |
| 45 | days | The quoted lead time that hides the spread ("about 45 days") | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 20 to 30% | of stock value a year | Holding cost (Portless) | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 10 to 20% | of shoppers | Share who never come back after a stockout (Eightx) | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $1.7 trillion | a year, worldwide | Enterprise retail's inventory distortion (IHL 2026). The category's size, not Hubricon's market | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 12 | requirements | What a fix must meet. Requirement 12 is "Be provable in dollars" | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 8 | tests | Replay, calibration, drift, reconciliation, messy data, split, trust, invoice | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 20% | of recommendations | The trust test's bar: fewer than this overridden | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |

### The worked example

The inputs are the PDF's example, not a brand's data. The results recompute from them, and
`tools/test_memory.py` re-runs the arithmetic.

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 40 | units a day | Example input: the sales rate | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 15 | units a day | Example input as first written: how much daily sales swing | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 15.4 | units a day | The same input as Hagen corrected it ("about 15.4") | assumption | SUPPLY_VARIABILITY.md section 1.2, Hagen's note | 2026-11-20 |
| 45 | days | Example input: the lead time | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 9 | days | Example input: how much the lead time swings | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 1.645 | z | The multiplier for a 95% service level | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |
| 95% | service level | Example input: how sure of not running out | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 10,620 | units squared | The demand term as the source gives it. It needs a swing of about 15.36 units a day: 15 gives 10,125 and 15.4 gives 10,672 | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 129,600 | units squared | The lead-time term, 40 squared times 9 squared | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |
| 12 | times | The lead-time term over the demand term (12.2) | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |
| 2,416 | units | The reorder point at a 95% service level with the inputs above (a swing of 15 gives 2,415) | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |
| 20% | extra | The habitual buffer the example compares against | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 2,160 | units | What that habit gives: 1,800 units plus a fifth | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |
| 256 | units | How far short the habit falls | proved | tools/test_memory.py, `test_the_worked_example_recomputes` | 2026-11-28 |

Note on "3 to 1" [inference]: one reading reproduces it. If the sales rate is uncertain by
35%, the demand term is (0.35 × 40 × 45)² = 396,900 against 129,600, which is 3.06 to 1. That
reading is this file's, not the PDF's, and the test re-runs it only as arithmetic.

### What a brand could recover

These are estimates from stated assumptions. None is measured, and none is a result.

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| $13,000 | a year | Recoverable profit for a brand at $1M revenue | estimate | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $65,000 | a year | The same at $5M revenue | estimate | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $259,000 | a year | The same at $20M revenue | estimate | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $1M | revenue a year | The low end of the band | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $5M | revenue a year | The middle of the band | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| $20M | revenue a year | The high end of the band | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 6.2% | of sales | Share lost to inventory distortion (IHL) | sourced | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 68 | share of the loss | The part that is lost sales, in the 68/32 split | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 32 | share of the loss | The part that is markdowns | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 30% | margin | Assumed for every brand. O20 replaces it with each brand's own cost data | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |
| 40% | of the loss | The cut Hubricon is assumed to recover | assumption | SUPPLY_VARIABILITY.md section 1.2, citing the problem PDF | 2026-11-19 |

## What has been proven, and what has not (section 1.3)

The files these rest on are in Hagen's Claude project. None can be re-run from this repo.

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 27% | of slow-seller error | What pooling cut in simulation. baseline: each store's own demand estimate | simulated | SUPPLY_VARIABILITY.md section 1.3, citing proof/METHOD_AND_PROOFS.md (not in this repo) | 2026-11-27 |
| 20 | businesses | Where the pooling gain levels off, and the pool size the simulations used | simulated | SUPPLY_VARIABILITY.md section 1.3, citing proof/METHOD_AND_PROOFS.md (not in this repo) | 2026-11-27 |
| 51 | of 96 cells | Cells where pooling 20 businesses beat a store's own demand | simulated | SUPPLY_VARIABILITY.md section 1.3, citing proof/sweep_results.md (not in this repo) | 2026-11-27 |
| 80 | of 96 cells | The same against own-plus-substitute demand | simulated | SUPPLY_VARIABILITY.md section 1.3, citing proof/sweep_results.md (not in this repo) | 2026-11-27 |
| 96 | cells | The size of that sweep | simulated | SUPPLY_VARIABILITY.md section 1.3, citing proof/sweep_results.md (not in this repo) | 2026-11-27 |
| 64 | of 96 cells | An earlier summary's figure. The file says 51 and 80. Never quote it | unverified | SUPPLY_VARIABILITY.md section 1.3 | 2026-11-27 |
| 5.7 | days | Lead-time forecast error for one brand alone | unverified simulation | SUPPLY_VARIABILITY.md section 1.3 and O2. The simulator (sim/) is not in this repo | 2026-11-27 |
| 4.0 | days | The same with 20 brands pooled | unverified simulation | SUPPLY_VARIABILITY.md section 1.3 and O2. The simulator (sim/) is not in this repo | 2026-11-27 |
| 18 | rounds | The secret hunt, which found no breakthrough | sourced | SUPPLY_VARIABILITY.md section 1.3, citing secret-hunt/ (not in this repo) | 2026-11-27 |
| 2 | out of 5 | Hubricon's score of itself before the Profit Record work | sourced | SUPPLY_VARIABILITY.md section 1.3, Hagen's words | 2026-11-23 |

### The public-data test (T1)

Run on Dominick's grocery data, which is public and is not e-commerce. It shows honest
predictions. It does not show that Hubricon's moves cause profit.

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 11,090 | sealed profit calls | The size of the test | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 83 | stores | The stores in the data | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 86.3% | of actual profit | Share that landed inside the range | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 90% | range | The width of the range the calls were sealed with | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 80% | inside the range | The pass mark, written down first | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 5.9% | over | How far summed predicted profit was from actual | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 15% | either way | The pass mark for that | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 78.6% | of calls | Share with the direction right | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 60% | of calls | The baseline for direction | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 37% | units error | Median error on a single week. The ranges are wide | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |
| 75% | cost share | Where the test fails, because cost was assumed | sourced | SUPPLY_VARIABILITY.md section 1.3, citing hubricon-to-4/t1/RESULTS.md (not in this repo) | 2026-11-27 |

### The fee and the scores

| Number | Unit | What it is | Status | Source or script | Date |
|---|---|---|---|---|---|
| 3,000 | random histories | In none did the high-water-mark fee bill below a previous peak | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |
| 1 to 5 | score | The scale the independent Red Team scores on. Six scores, never averaged | sourced | SUPPLY_VARIABILITY.md section 1.3 | 2026-11-27 |
| 4 | out of 5 | The built app's score on Size, Weak attempts, Why now and Founder fit | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |
| 3 | out of 5 | Its score on Evidence and Cheap test | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |
| 3 to 5 | installs | What lifts Cheap test to 4 | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |
| 8 | sealed moves | The fewest graded moves on a real brand that lift Evidence to 4 (O18) | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |
| 80% | inside the band | The share those moves must reach | sourced | SUPPLY_VARIABILITY.md section 1.3, citing REDTEAM_BUILD.md (not in this repo) | 2026-11-27 |

## Open discrepancies

Nobody has settled these. Each is recorded so no agent picks a side by accident.

- **The stage ranges do not add up to the total quoted beside them.** The eight ranges in
  section 1.2 sum to 39 to 75 days. The same sentence, and CONTEXT.md, say 36 to 70. The PDF
  is not in this repo, so which one is the slip cannot be told here. Until Hagen checks the
  PDF, quote the stages or the total, not both as if one followed from the other.
- **The per-brand estimates do not follow from the four assumptions listed with them.**
  6.2% × 68% × 30% × 40% of $1M is about $5,059, not $13,000. The PDF may use a step the
  handoff leaves out. The dollar figures stay `estimate`, and no derivation is rebuilt here.
- **"64 of 96" against "51 and 80 of 96".** Settled by the handoff itself in favour of the
  file (51 and 80). The 64 row is kept, as `unverified`, so the checker keeps it out of
  client text.
- **The demand term 10,620 and its input.** It matches a daily swing of about 15.36 units.
  The handoff says "about 15.4", which is the same to one decimal, so the reorder point of
  2,416 holds either way.
