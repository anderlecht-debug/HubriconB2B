# The golden set

Past questions with their accepted answers (SUPPLY_VARIABILITY.md, section 5.5). Before a
change to an agent file, `docs/agents/CONTEXT.md`, `docs/agents/NUMBERS.md` or the checker is
kept, every answer here must still pass the checker and keep its verdict.

```
python3 tools/check_golden.py
```

It prints one line per case and exits 1 if an answer fails the checker, if its verdict is no
longer the one recorded, or if a case is not marked as made-up or public data. The question
and the answer must each open by saying which: "Made-up data. Not a client. Not a result." or
"Public data. Not a client. Not a result." A change that turns a case red is flagged in its
pull request.

## What is here today

Three seed cases, written on 2026-11-28 to give the check something to hold. **None has been
reviewed by Hagen**, and each `meta.json` says so. They become accepted answers when he says
so, and the field changes then. None uses a client's data, and none is a result.

| Case | Agent | Data | What it holds still |
|---|---|---|---|
| `physicist-worked-example` | factory-physicist | made-up | The per-product table, a reorder point with its service level and inputs, a lead time said to be assumed |
| `red-team-section-1-3` | feynman-red-team | public | The verdict table and its one-line verdict, on the claims of section 1.3 of the handoff |
| `client-view-made-up` | none, a client view | made-up | The three depths in plain words, opening with "Made-up data. Not a client. Not a result." |

## A case is a folder

```
agents/golden/<case>/
  question.md   what was asked
  answer.md     the accepted answer, exactly as it passed
  meta.json     how to check it
```

`meta.json`:

| Field | Meaning |
|---|---|
| `agent` | The agent whose required sections the answer must have, or `null` |
| `client` | `true` when the answer is client text and is checked with `--client` |
| `numbers` | `true` when every number in the answer must be a row of `docs/agents/NUMBERS.md` |
| `verdict` | `ship`, `fix first` or `stop` for a red-team answer, otherwise `null` |
| `data` | `made-up` or `public`. Anything else fails: client data never goes into git |
| `accepted` | Who accepted the answer and when, or that nobody has yet |

## Adding a case

Take the question and the answer from a run that ended clean, strip anything that came from a
client (use a made-up or public stand-in, and say which), run `python3 tools/check_golden.py`,
and open a pull request. Never a brand name, never a client code, never a client's figures.
