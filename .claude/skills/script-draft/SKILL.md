---
name: script-draft
description: Draft one Hubricon video script from a unit's facts.json, following the scripting doctrine, with every figure as a {{key}} placeholder. Produces content/videos/<slug>/script.md and validates it.
---

# script-draft

Input: a unit id from `content/queue.json` (it names the day, title, pillar, tier, slug and models).

## Before writing

1. Read `docs/content/hubricon-video-scripting-doctrine.md` in full. §12 is the template you
   must fill; §13 is the brief; §14 is the check.
2. Read `content/videos/<slug>/facts.json`. Every figure you may use is a key there, with its
   label and the model run it came from. If a figure you want is missing, describe it without a
   number or leave it out. Never invent a key.
3. Read `content/videos/<slug>/brief.md` if it exists (the founder's rejection notes live there).

## Order of work (doctrine §2)

1. Title (search phrase plus a number or a named misconception) and thumbnail concept first:
   one `{{key}}` figure and one chart fragment, no face, no arrows.
2. Three hooks, each under 45 spoken words, a `{{key}}` in the first sentence, the
   misconception in the second, the loop opened in the third.
3. The script in the §12 template, at `content/videos/<slug>/script.md`:
   - Every number, currency, percentage or number word in a `VO:` line is a `{{key}}`.
   - Every chart beat carries `VISUAL:` naming the Manim scene (`waterfall`, `cash_cone`,
     `elasticity`, `newsvendor`, `paths`, `sample_size`, `kinetic`, `chapter_card`) and
     `DATA SOURCE:` naming the model run from `facts.json` ("demo data" is part of the name).
   - `CLIP: yes` on at least three self-contained moments.
   - Exactly one CTA, chosen by pillar from `content/calendar.json` → `cta_by_pillar`.
   - Tier A: 700–900 rendered words, 5–7 minutes. Tier B: doctrine §10, procedural, 8–14 minutes,
     visuals limited to engine charts and kinetic type.
   - Re-hook at least every 40 seconds; fill the `RE-HOOK AUDIT` line honestly.
4. Run `hubricon-content script-validate <slug>`. Fix every reported problem and re-run, at most
   three passes. Do not remove a placeholder to satisfy the guard; rewrite the sentence.

## The brief (doctrine §13, verbatim)

Open with the misconception, not the answer. The viewer must commit to the intuitive model
before it's dismantled. Title and thumbnail first; the script delivers the title's promise.
Three hook options, under 45 words each, concrete number in sentence one. Intuition before any
notation. One idea per video. Show uncertainty, not point estimates. Teach the method completely;
withhold nothing. Close with the honest limit — what this can't do and what that needs — then
exactly one CTA. One spiky, disputable claim. Every on-screen number names the model run it comes
from; demo data is labelled as demo data. Re-hook at least every 40 seconds. Mark CLIP at every
self-contained moment. Observe the banned-phrase list. Deliver in the §12 template.
