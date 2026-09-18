---
name: critique
description: Critique a Hubricon script (doctrine §14), a rendered video (production bible §11 plus frame review), or learn-page copy (learn doc §7 and the luxury pass). Writes a JSON verdict the pipeline reads.
---

# critique

Usage: `critique script <slug>` · `critique render <slug>` · `critique copy <path>`

## script

1. Run `hubricon-content critique <slug>`. It writes `content/videos/<slug>/critique.json`
   with the mechanical items already judged (number guard, hook length, re-hook gaps, CLIP
   count, CTA by pillar, banned phrases, word count).
2. Read `docs/content/hubricon-video-scripting-doctrine.md` §14 and the script. Judge the
   remaining items yourself and fill them into the same file, one entry per item:
   `{"n": 1, "pass": true|false, "note": "..."}` for all fourteen. Item 14 (a founder outside
   Amazon still gets something) is exempt for pillars 1 and 2.
3. Set the top-level `"pass"` to true only when every item passes. Be specific in notes; the
   drafting skill reads them on the next attempt.

## render

1. Read `content/videos/<slug>/qa.json` (written by `hubricon-content qa`): hold length, cut
   cadence, loudness, room tone, subtitle coverage, duration, disclosure, transcript match.
2. Read every PNG in `content/videos/<slug>/frames/` with the Read tool (one per ten seconds).
   Check, per `docs/content/hubricon-video-production-bible.md` §11: no face or avatar in any
   frame; textures are never the subject; charts build progressively and carry an annotation;
   subtitles are legible; every on-screen number is readable; the "demo data" label is present
   on chart frames; palette and type match `content/assets/style-lock.json` once it exists.
3. Write `content/videos/<slug>/qa.review.json`: `{"pass": bool, "items": [...], "notes": "..."}`.

## copy

For `learn/*.html` and lesson text: banned phrases; "free" at most twice on the page; no
countdown, no "limited", no fake counts, no "coming soon"; the form has six fields and no phone
number; lesson 1 is readable without the form; no sentence claims results, clients or
testimonials that do not exist; every dollar figure in lessons traces to `facts.json` and is
labelled demo. Write the verdict to `content/reviews/copy-<name>.json`.

A failed critique is not a stop: the calling skill revises and re-runs. Three failures on one
step make the unit `stuck`.
