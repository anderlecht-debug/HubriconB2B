# The film line: a long film for a fraction of the tokens

**Decided 2026-10-07 by the founder.** G01 took a large share of a week's usage. The goal is seven films a week alongside the rest of the business. This document says how a film is made now.

## The magic-wand number

Most of a film costs no tokens. That covers sourcing, grading, the stage render, footage, the mix, captions, the draft and QA, which all run on this PC.

Only judgement needs a model:

| Step | What is decided | Floor |
|---|---|---|
| Shot plan | about 280 shots: what is on screen, when and why | ~0.1M tokens |
| Picks | the picture shots the filters could not rank | ~0.2M |
| Review | one look at the review sheets | ~0.1M |

That makes the floor about 0.4M tokens a film. G01 spent one to two orders of magnitude more. The waste came from four places:

1. building the engine inside the film;
2. open-ended critic, designer and verifier loops that re-read large files every time;
3. the frontier model doing mechanical work;
4. one session left open overnight.

## The rules of the line

1. **The engine is frozen during a film.** content/film/v3 and the grade change only in a separate R&D task with its own budget, never to finish a film. The look is locked (`visual-lock`).
2. **Checks are code, not eyes.** `hubricon-content film-qa <slug>` runs every check the G01 critics ran by eye. It reads the plan, the clips and the stage (`content/film/v3/qa.mjs`): figures before their words, bare openings, labels over lit pictures, text under prints, title-safe and overlaps. It also reads the draft: length, loudness, true peak, black and freezes. It costs no tokens. Run it until it is clean.
3. **Every AI step runs under a hard budget.** Use `hubricon-content ai-step <slug> <step> --prompt-file …`. It counts tokens live, weighted to cost, and stops the run the moment its budget is spent. A film stops starting AI steps once its own total is spent. Budgets and models live in `content/film/budgets.json`: Sonnet for plan, pick, fix and review, and Opus only for a script draft.
4. **One pass per AI step.** There is no multi-agent critique of a film. The validator and film-qa are the critics. A fix pass reads film-qa's punch list, not the film.
5. **Few, whole sessions, never many short ones.** Every `claude` session first loads its system prompt, tools and instructions: measured on 2026-10-07 at about 43k tokens before a word of work, which is about 53k cost-weighted. One planning session plans the whole film. A fix pass takes the whole punch list at once.
6. **The unattended runner is capped too.** `scripts/content-tick.sh` runs each 30-minute tick through `ai-tick`: Sonnet, a cap per tick, per day and per week (`budgets.json` "runner"), and a tick past a cap does not start. Its ledger is `content/.cache/runner-meter.json`.
7. **The meter is read, not guessed.** `hubricon-content film-cost <slug>` gives a film's tokens by step against budget.

## The line, as one command

    hubricon-content film-line <slug> [--placeholder] [--from STEP] [--until STEP]

The steps are `voice`, `skeleton`, `decide`, `fill`, `source`, `pictures`, `render`, `qa`, `draft` and `cost`, in that order. Each runs as its own process and is recorded in `videos/<slug>/line.json`, so a stopped or crashed run resumes where it left off. The line stops with a reason when it can't go on: no voice yet, or a budget spent.

- **`skeleton`:** code drafts the shots.
- **`decide`:** the one model pass.
- **`fill`:** the validator's known mechanical problems are fixed by code (`line.autofix`). A budgeted `fix` pass runs only if real problems remain.
- **`pictures`:** auto-pick, auto-prints and resolve-gaps.
- **`render`:** sizes its workers to free memory.

## The line, in order

| # | Step | Command | Tokens |
|---|---|---|---|
| 1 | Script (the founder's, or a draft he approves) | `ai-step <slug> script` | Opus, budgeted |
| 2 | Timing from his takes | `takes-to-vo`, `timing` | 0 |
| 3 | Shot plan | `ai-step <slug> plan` (shot-plan skill), then `shots-fill`, `shots-validate` | Sonnet, budgeted |
| 4 | Sourcing | `source <slug>` | 0 |
| 5 | Picks | `pick` for the ranked shots, `ai-step <slug> pick` for the rest | Sonnet, budgeted |
| 6 | Render | `render-shots <slug> --workers 4` (unattended, overnight) | 0 |
| 7 | QA | `film-qa <slug>`, then `ai-step <slug> fix` on its list, then render again | fix only |
| 8 | Draft and sheets | `draft <slug>`, `review-sheets <slug>` | 0 |
| 9 | Review | `ai-step <slug> review` on the sheets, then the founder watches | Sonnet, budgeted |

Every command is `hubricon-content <command>` with `FILM_LOOK=v3` set.

A film should cost well under its 1.5M weighted-token cap. The first films on the line are measured with `film-cost`, and the budgets are set from what they actually used.
