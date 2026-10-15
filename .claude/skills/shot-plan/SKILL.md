---
name: shot-plan
description: Write the shot plan (shots.json) for one long Hubricon film from its approved script and its timing, choosing one style from the VISUAL_SPEC.md library per shot, then fill and validate it until clean. The `shots` step of a tier-D unit.
---

# shot-plan

Input: a `slug` whose script is approved. Output: `content/videos/<slug>/shots.json` that
`hubricon-content shots-validate <slug>` passes. You decide what the viewer sees; the tools copy
the times, the words and the figures.

Read once a session: `docs/content/VISUAL_SPEC.md` §3 (the two rooms), §4 (cadence), §5 (screen
time), §6.1–6.2 (what a world shot may show), §7.3 (the schema) and §14 (the styles). The numbers
the validator holds you to are in `content/film/styles.json`.

## Never

- Edit `script.md`, `facts.json` or the timing. The script is the founder's.
- Put a number in the world room. A number, a comparison or a mechanism goes to paper.
- Show a named company, person, place or event with stock or AI (§6.2): archival with that name
  in its provenance, or paper.
- Query a cliché (§6.1): handshakes, suits, laptops or phones with charts, tickers, cash, piggy
  banks, light bulbs, chess, puzzles, rockets, skylines, smiling people at desks, whiteboards,
  sticky notes, glowing particles or networks.

## Steps

1. **Timing.** Use `timing.json`. Before narration exists, run
   `hubricon-content timing <slug> --estimate` (writes `timing.estimate.json` at 150 words a
   minute; it never replaces a real timing). Its `cutpoints` are the only places a cut may fall.
2. **Mode.** `explainer` when the film teaches the method and the engine's models; `history` when
   it tells the story of real companies and people. The mode sets the screen-time ranges (§5).
3. **Walk the beats, sentence by sentence.** For each sentence decide the room by the rule *a
   number, a comparison or a mechanism goes to paper; a thing, a place or a moment goes to the
   world*. Then pick its style with the table below, reaching for a sequence where a run of
   sentences fits one. Group sentences into shots of 7 to 11 s (3 s at least, 14 s at most; a chart
   up to 30 s with something new every 8 s), cutting at sentence ends. The first minute is quicker:
   median 6 s or less, nothing over 8 s.
4. **Write each shot** (ids `s001`, `s002`, …) with `start` and `end` (close to a cutpoint; the fill
   step snaps them), `beat`, `room`, `kind`, `style`, `on`, `params`, `intent` (one line: what the
   viewer sees and why it fits these words), and:
   - a world shot or an archival paper shot: `query` (one or two literal queries made of the
     sentence's concrete nouns, e.g. `"container port gantry cranes daylight wide"`), `sources`
     (`pexels`, `pixabay`; archival: `loc`, `smithsonian`, `commons`, `archive`, `nara`;
     a texture: `higgsfield`), `fallback` (archival → stock → texture → `paper:kinetic`);
   - a texture: `"overlay": {"illustration": true}`;
   - a sentence naming a real company, person, place or event: `"specific": "<the name>"`;
   - a chart style: `"chart": {"scene": "<staircase|montecarlo|aging|waterfall|cash_cone|…>"}` and,
     past 14 s, `params.builds` (the seconds where something new lands);
   - `on`: the word, or `{{key}}`, the style's main event lands on (§14.1). Leave it `null` for
     styles without one (`kinetic-thesis`, `chapter`, `footage-establish`, …).
5. **Fill:** `hubricon-content shots-fill <slug>` snaps every cut to the nearest legal one and
   writes `says`, the reveals (paper only) and the labels from the timing and the facts.
6. **Validate:** `hubricon-content shots-validate <slug>`. Fix every problem it names by changing
   the plan (move a cut, change a style, move a figure to paper) and fill again. Stop when it prints
   `clean`.

## What the first Greats film taught (2026-10-06)

- **Picture first.** Aim for at least 45% of the runtime led by a picture (footage, a still, a framed
  photograph, a stack, a split). A sentence with no figure is a chance for the world: never leave
  more than about 45 s of paper in a row when one of its sentences carries no figure.
- **`specific` is for a name the sentence says.** Tag a shot only when the voice names that
  particular company, person, place or event ("Sears", "Batavia, Ohio", "the Joint Committee").
  A generic noun ("a country post office", "an express wagon", "a farmer") is not specific: query
  it from the archival libraries without the tag, or the record filter refuses every good photograph
  that does not repeat the word.
- **Archival queries are file titles.** Write the words a Wikimedia Commons or LOC file title would
  carry ("Rural free delivery wagon", "Sears Roebuck plant Chicago 1906", "farmer plowing horses"),
  not the sentence.

## The picker (VISUAL_SPEC.md §14.2)

| The sentence… | First choice | Second choice | Never |
|---|---|---|---|
| cites a rule, fee, schedule, filing or published line | `doc-highlight` | `table-scan` | a stock shot |
| locates something in a list or schedule | `table-scan` | `doc-highlight` | |
| states one figure or range | `number-land` | `range-band` | footage with a number over it |
| compares two figures | `number-pair` | `counterfactual` | |
| says what one small change would cost or save | `counterfactual` | `number-pair` | |
| explains a mechanism or a relationship | `chart-build` | `formula-build` | |
| defines a quantity by its parts | `formula-build` | `chart-build` | |
| is a forecast, an estimate, uncertainty | `range-band` | `number-land` with "estimate" | a single line |
| gives a share of a countable set | `unit-grid` | `number-pair` | |
| names dated events or an order of events | `timeline` | `doc-clipping` | |
| refers to a dated public event or report | `doc-clipping` | `archive-framed` | |
| names a real historical person, place or company | `still-push` on archival | `archive-framed` | stock, AI |
| lists several real examples | `archive-stack` | `still-pan` | stock, AI |
| contrasts then and now | `split-then-now` | two `archive-framed` | |
| describes a place or opens a chapter | `footage-establish` | `still-pan` | a generic skyline |
| describes a physical process | `footage-process` (three shots: wide, medium, detail) | `footage-insert` | |
| names a small physical object | `footage-insert` | `still-reveal` | |
| moves from a detail to the whole | `still-reveal` | `still-pan` | |
| reasons for 10 s or more with no new noun or number | `footage-observe` | `texture` | a frozen frame |
| is abstract, with no concrete noun | `kinetic-thesis` (the chapter's claim) | `texture` | stock clichés |
| is the chapter's central claim | `kinetic-thesis` | | |
| quotes a dated source verbatim | `quote` | `doc-clipping` | paraphrase in quote marks |
| explains how Hubricon counts a dollar | `receipt` | `doc-highlight` (the terms) | |
| follows a big reveal | `breath` (only where the narration pauses) | | |
| resolves something set up earlier | `callback` (`params.callback`: the earlier shot) | | |

`still-depth` waits for its build after the visual trial; do not plan it yet.

## Sequences (VISUAL_SPEC.md §14.6)

1. **Evidence run** (explainer, ~50 s): `footage-establish` 8 → `footage-process` 12 →
   `doc-highlight` 10 → `chart-build` 14 → `number-land` 6.
2. **History open** (history, ~70 s): `still-push` 10 → `doc-clipping` 8 → `archive-stack` 12 →
   `timeline` 16 → `split-then-now` 10 → `kinetic-thesis` 7.
3. **Counterfactual reveal** (~40 s): `footage-insert` 4 → `table-scan` 10 → `counterfactual` 14 →
   `number-pair` 8 → `breath` 2.
4. **Honest limit** (~35 s): `range-band` 14 → `unit-grid` 10 → `footage-observe` 12.
5. **Chapter turn** (~14 s): `breath` 2 → `chapter` 2.5 → `footage-establish` 8.
6. **Return** (the end, ~25 s): `callback` 12 → `kinetic-thesis` 6 → `end` 6.

## Variety the validator enforces (§14.8)

At least 10 styles in any 20 minutes; no style over 15% of the runtime (`chart-build` 25%,
`texture` 8%); never one style three shots running (a process sequence counts once); one
`kinetic-thesis` per three minutes, one `footage-observe` per 90 s, one `breath` per two minutes;
one `match-bridge` per chapter; no two textures together; at most two inserts together; at most
three shots of one kind in a row; a world run of 90 s and a paper run of 120 s at most; a change of
texture (a chapter card, a document, a number) at least every three minutes.
