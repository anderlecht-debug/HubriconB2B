# CORRECTIONS.md: what was wrong, and what it became

One entry per correction, newest last (SUPPLY_VARIABILITY.md, sections 5.3 and 5.4). A
correction comes from Hagen, from a client (by client code, never by name), or from the red
team. No client data goes in this file.

Every correction becomes one of three things, in this order of preference:

1. **a check**: a rule in `tools/agent_check.py` or a test, so a script catches it next time;
2. **a data fix**: a change to `docs/agents/NUMBERS.md` or `docs/agents/CONTEXT.md`;
3. **an agent-file line**: only when neither of the first two can hold it.

Each entry has the same six fields: Date, From, What was wrong, What it became, Commit, Why.
`python3 -m unittest tools.test_memory` fails an entry that is missing one. To add an entry,
copy the last one, give it the next number, and open a pull request that says which
correction it answers. A rollback is a `git revert` of that merge, logged here as a new entry.

The first five entries are the corrections the handoff itself records. Nothing in this file
came from a client: Hubricon has none yet.

## C1. The shared brief still called pooled demand the front-runner

- Date: 2026-11-27
- From: the handoff (SUPPLY_VARIABILITY.md section 1.3 and O1), after the secret hunt killed pooled demand as the moat
- What was wrong: `docs/agents/CONTEXT.md` presented pooled, stockout-corrected demand as the current front-runner for the monopoly and described the engine as reorder maths. An agent reading it would build on a direction that had been dropped.
- What it became: data fix. CONTEXT.md gained a dated "Current state" section that wins over the text below it, and the old front-runner paragraph is marked "Superseded 27 Nov 2026". The original text is kept.
- Commit: 74a8ff4
- Why: agents copy whatever they are given. A stale brief had already produced one misreading (the handoff cites ADD_AND_CUT.md C6).

## C2. A simulation that may have had a bug was quoted as a result

- Date: 2026-11-27
- From: the handoff (SUPPLY_VARIABILITY.md section 1.3 and O2), which cites the secret-hunt ledger's note that an earlier simulator had a bug
- What was wrong: "lead-time forecast error fell from 5.7 days to 4.0 days" was written in the brief and in an agent file as if it were evidence. The simulator is not in this repo, so nobody can re-run it or rule the bug out.
- What it became: data fix and check. `docs/agents/NUMBERS.md` carries both figures with the status "unverified simulation", CONTEXT.md says never to quote them as evidence, and the `numbers` rule of `tools/agent_check.py` fails either figure in client text (`--client --numbers`).
- Commit: 0fceda3
- Why: under pay-on-results pricing one number that cannot be reproduced costs more trust than it buys.

## C3. "64 of 96" was quoted where the file says 51 and 80

- Date: 2026-11-27
- From: the handoff (SUPPLY_VARIABILITY.md section 1.3)
- What was wrong: an earlier summary said pooling won in 64 of 96 cells. The results file the handoff cites gives 51 of 96 against a store's own demand and 80 of 96 against own-plus-substitute demand.
- What it became: data fix and check. NUMBERS.md holds 51 and 80 as "simulated" and keeps 64 as "unverified", so the `numbers` rule keeps it out of client text.
- Commit: 0fceda3
- Why: the file wins over a summary of it. Keeping the wrong figure in the register, marked, stops it coming back unnoticed.

## C4. The worked example's daily swing was written as 15, and should read about 15.4

- Date: 2026-11-20
- From: Hagen
- What was wrong: the worked example gave daily sales as 40 units "give or take 15". With 15 the demand term is 10,125 and the reorder point rounds to 2,415, not the 10,620 and 2,416 printed beside it. Hagen noted the brief should read "give or take about 15.4".
- What it became: data fix and check. NUMBERS.md holds both inputs with a note on which one the printed results need, and `tools/test_memory.py` recomputes the example, so a changed figure fails a test. The original wording in the lower half of CONTEXT.md still says 15, because O1 keeps that text as written.
- Commit: 0fceda3
- Why: a reader who redoes the sum has to land on the printed answer, or nothing else on the page is believed.

## C5. "We've already done it" against "no claimed results"

- Date: 2026-11-27
- From: the handoff (O5), resolving a tension between two of Hagen's own instructions
- What was wrong: copy could slide from "we built it" (true of the engine and the Profit Record) to a claim of clients, results or dollars that nobody has measured.
- What it became: check and data fix. The `label` rule of `tools/agent_check.py` fails any number in client text that carries no measured, sourced or inference label, and CONTEXT.md says under "What is true today" that there are no paying customers and no measured result on a real brand.
- Commit: a64361e
- Why: Hagen's own outreach rule (D15). Passing the check shows a claim is labelled, never that it is true, so the red team still reads everything.

## C6. "23 models in about 30 to 75 seconds" was sourced to a file that says neither

- Date: 2026-11-28
- From: the copy chief agent (schwartz-copy-chief), which could not find "23 models" in the file CONTEXT.md named. Not from Hagen, a client or the red team
- What was wrong: CONTEXT.md said the engine "runs 23 models ... in about 30 to 75 seconds [sourced: engine/MATH_SCORECARD.md]". The scorecard states no model count and no such range. It gives two timings on synthetic catalogues, about 29 seconds at 160 SKUs and 75.5 seconds at 400 SKUs, taken in September and not repeated since.
- What it became: data fix and check. CONTEXT.md now says 23 models as counted in the `ALL_MODELS` list of `engine/src/hubricon_engine/cli.py`, 22 on a Shopify run because fee recovery is skipped, and gives the two timings with their catalogue sizes and dates. NUMBERS.md holds each with its true status. `tools/test_memory.py` recounts `ALL_MODELS`, so the count fails a test the day the engine changes, and the `numbers` rule fails any figure in CONTEXT.md that is not a row of NUMBERS.md.
- Commit: 0fceda3
- Why: the count happened to be right and the source was wrong, which is the kind of error that survives review. A label names where a number can be checked, and this one could not be.
