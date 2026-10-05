---
name: visual-pick
description: Choose the picture for every world shot of one long Hubricon film from its sourced candidates (contact sheets), or take the shot's fallback, then validate the picks. The `pick` step of a tier-D unit.
---

# visual-pick

Input: a `slug` whose `source` step is done. Output: `shots.json` with every world shot's
`asset`, `focus` and `motion` (and `in`/`out` for footage) filled, `assets.json` with one line of
reason per pick, and `hubricon-content shots-validate <slug> --picked` printing `clean`.

Read once a session: `docs/content/VISUAL_SPEC.md` §3 (the look: bright, cool, high-key; the only
saturated blue is money), §6.1 (the concrete-noun rule and the banned clichés), §6.2 (named things
need their own evidence), §6.6 (faces) and, for each style you pick for, its §14 entry, above all
its **Failure looks like** lines: they are your rejection list.

## For each world shot (and each archival paper shot: archive, stack, split)

1. Read the shot's `says` and `intent` in `shots.json`.
2. Open its contact sheet, `content/videos/<slug>/sources/<shot>.jpg`, with the Read tool. Up to
   nine candidates, three frames each for footage; rejected candidates are marked and their
   reasons are in `sources/<shot>.json`.
3. Pick the one that shows the sentence's most concrete noun most plainly, in the look of §3. Refuse:
   - anything that does not show the noun the voice says (a warehouse for "a pallet" is a miss);
   - a cliché (§6.1), a visible logo or brand mark (above all Amazon's), burned-in text, a
     watermark, a face as the subject in stock (any face over 1% of the frame);
   - night, low-key or heavily graded footage, shaky handheld, a cut inside the window you need;
   - for a shot tagged `specific`, anything whose provenance does not name that same thing;
   - anything in the style's "Failure looks like" lines.
4. Set the pick's details:
   - `focus`: where the subject sits, `[x, y]` from 0 to 1 (the push and the crop centre on it);
   - `motion`: `push` or `pull` (still-push), `pan-left` or `pan-right` (still-pan), `reveal`
     (still-reveal), `drift` (texture). Never the same move twice in a row (§3.4);
   - footage `in` (and `out`): a continuous take at least as long as the shot (the candidate's
     `cuts` list where the take has internal cuts); for a process sequence, cut on motion and keep
     screen direction the same across its three shots.
5. Record it: `hubricon-content pick <slug> <shot> <candidate number> --focus x,y --motion m
   [--in seconds] --reason "<one line: why this one shows the words>"`. That fetches the
   full-resolution file, writes the asset's provenance into `shots.json` and the reason into
   `assets.json`.
6. If none fits: re-query once with different concrete nouns (`hubricon-content source <slug>
   --shot <id> --query "<new query>"`), then pick again. If still none, take the shot's fallback:
   `hubricon-content pick <slug> <shot> --none --reason "<why>"` (archival → stock → texture →
   `paper:kinetic`, in the order the plan allows).

## Textures (AI images)

For a `texture` shot, generate four candidates with Higgsfield's `generate_image` tool, each prompt
beginning with the locked preamble of §6.5 verbatim ("Photographic still life, overcast north light,
cool neutral palette, matte surfaces, high-key exposure, shallow depth of field, fine film grain,
35 mm, no people, no hands, no text, no logos, no screens.") followed by the shot's subject. Wait
with `jobs_wait`, look at all four, and keep one or none: never a person or a hand, never a real
place, product or event, never text. Record the job id, model, prompt and seed with `pick --texture`.
Note `balance` before and after for the film's meter. Never generate video.

## Then

Run `hubricon-content shots-validate <slug> --picked` and fix every problem it names. Stop when it
prints `clean`.
