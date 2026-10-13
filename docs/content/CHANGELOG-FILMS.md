# Films changelog

What changed in how the films are made, what was measured before and after, and what could not be done.
The test film is G02 (`greats-02-the-dime`, 28:49, placeholder voice).

## Baseline (G02, before the 2026-10-12 work order)

| Measure | Before |
|---|---|
| Bare openings (film-qa) | 23 |
| Freezes, 4 s or more (film-qa) | 20 |
| Median picture relevance | not measured (no relevance model) |
| Designed effects a minute | 11.7 |
| Longest stretch with nothing designed under the voice | 34.6 s |
| Silence (music and effects out ≥2 s) per chapter | none designed |
| Weighted AI tokens per film | 1.74M spent on G02 (old session path); 163k measured for the plan on the reply path |
| Render time (232 clips, 3 workers) | ~70 min (72 min with draft and film-qa) |

## 1. Packaging first (2026-10-12)

**Changed.**
- **The script.** It needs three titles (`TITLE 1`–`3`) and three thumbnail concepts (`THUMBNAIL 1`–`3`).
  `TITLE` and `THUMBNAIL` must be copied word for word from them. A concept reads
  `<the stakes as a picture> | TEXT: <at most 4 words> [| PICTURE: <shot id or words>]`; a `{{key}}` counts as
  one word, and the number guard covers all six fields. A tier-D script without them is refused, at
  intake and by `script-validate`.
- **The thumbnail builder.** It renders all three concepts (`media/thumb-1..3.png`, plus `thumbnails.json`
  with each one's kind and provenance) and copies the chosen one to `thumbnail.png`.
  - The *figure* kind sets the figure large with the concept's other words, on the film's dark look, with
    the demo label where the figure is demo data.
  - The *stakes* kind uses a frame of one of the film's own shots, exactly as the film shows it: the
    shot named by `PICTURE`, else the world shot whose query, words and picture title best match the
    concept. Its words sit over a darkening toward them. A thumbnail can only use the film's own licensed
    pictures or its stage scenes.
- **film-qa** (advisory) reports when the first 5 s don't pay off the chosen thumbnail: its figure said
  or shown, or its picture (or one of the same subject) on screen.

**Measured on G02.** Three test concepts were added to G02's script: the titles and concepts are mine,
for the test, to be replaced by the founder's. Your narration is untouched. They rendered as two stakes
thumbnails (the opening coin, s005; the Woolworth Building at night, s086) and one figure thumbnail
("more than 50 years / unmoved"). The payoff check flags G02: it opens on a date figure, and the coin
of thumbnail 1 first appears about 20 s in.

**Could not do.** The first attempt at the stakes kind used the raw scan, and a scan on a white studio
background read as a grey haze. It now uses the film's own frame. Uploading all three to YouTube's test
needs the YouTube sign-in, which doesn't exist yet. The ranking by picture relevance arrives with item 2.

## 2. Picture relevance (2026-10-13)

**Changed.**
- **A local image-text model** (SigLIP ViT-B-16, on the GPU, no tokens) scores every passed candidate and
  every picked picture against its shot (`relevance.py`; `hubricon-content relevance <slug>`).
- **Auto-pick** never takes a candidate scoring below 0.00. It orders the rest by relevance, with the
  source's rank adding a little.
- **Doubtful shots go to one capped reply.** A shot whose best candidate scores under 0.05 is sent, with
  the other doubtful shots, to a single visual-pick reply: their contact sheets and words in, a sheet
  number (or none) per shot out. It is capped at 30k weighted tokens, and only as many sheets as fit go. A
  shot the model says has no fit loses its picture, and resolve-gaps absorbs it or sets the film's own
  words. Its answer is saved, so a re-run never pays twice.
- **Auto-prints** also takes the best-scoring of a few acceptable prints, not the first.
- **film-qa** reports the film's median relevance and how many shots a model reviewed.

**Calibration (G02, by its contact sheets).** The text compared is the shot's picture query, then the
words spoken under it, not the spoken words alone as first specified. The spoken words alone barely
separate a right picture from a wrong one (median 0.009, 10th–90th percentile −0.03 to 0.05), being
often abstract ("A test, then a rollout."). The query is the plan's own reading of those words.

With it:
- **Right pictures sit near 0.10:** s125's period grocery interior +0.100, s058's "5 & 10 store" poster
  +0.099.
- **Modern or tangential ones sit near 0.00–0.02.**
- **Wrong ones fall below 0:** a modern winery for "five-and-ten store" −0.054, pancakes for "faded old
  photographs" −0.125.

Rank alone had picked the winery and a modern building for those two shots.

**Measured on G02.**

| | Rank picks | Relevance picks |
|---|---|---|
| Median relevance of picked pictures | 0.055 (36 of 79 under 0.05) | **0.072** |

- 67 shots were re-picked.
- 14 kept their old picture because Wikimedia Commons refused the download (HTTP 429).
- 15 shots stayed doubtful. They went to the visual-pick reply: 15 contact sheets, **18.0k weighted
  tokens** (10.1k in, 1.1k out), inside its 30k cap.

**Could not do.**
- **The picks from that reply were not applied.** A download it triggered hit a 429 that `visual_pick`
  didn't catch. Now fixed (a refusal keeps the picture) and answers are saved. The full G02 re-run below
  repeats the step.
- **The visual-pick reply was first refused** because G02's meter held 1.74M tokens from its old
  planning sessions (2026-10-07), over the film's 1.5M cap. That spend is kept in
  `meter-2026-10-07.json`; G02's test run starts a fresh meter, with the cap unchanged.

**Two side fixes this needed.**
- **Wikimedia Commons originals larger than the grade now download as Wikimedia's own 4,800 px resize**
  (as the Library of Congress via IIIF on 2026-10-07): masters of up to 10,000 × 8,000 px were decoded
  whole in memory.
- **Installing PyTorch with `uv sync` removed packages the project uses but had never declared:** the
  engine, faster-whisper, Kokoro and the sourcing filters. All are restored and declared;
  `install-content-tooling.sh` now installs the filters too and warns never to `uv sync` this
  environment.

## 3. Chapter-level recording (2026-10-13)

**Changed.**
- **The teleprompter** (`record.mjs`) has a chapter mode. "By chapter" shows a whole chapter (the open,
  then each chapter card and its beats) and keeps one take per chapter (`takes/c<K>.wav`). Beat mode stays,
  for a single beat read again.
- **`takes-to-vo`** cuts each chapter take into its beats before anything else (`tts.split_chapters`):
  - faster-whisper times the chapter's words, and the script's own words take those times;
  - each cut falls at the quietest 20 ms in the gap between one beat's last word and the next one's first;
  - a beat's own retake (`takes/b<N>.wav`) wins over its part of a chapter take.

  `timing.json` and everything downstream see one take per beat, exactly as before.
- **Pace** is measured per beat after the split. Beats outside 120–200 words a minute are reported
  (`pace_outside`), not refused.

**Measured on G02.** A chapter take built from G02's own beat recordings (chapter 2, "One price", seven
beats, joined with 0.4 s pauses) split cleanly. The first cut, by the midpoint of the gap, was 0.11–0.23 s
from the true joins, one of them 30 ms into a word's tail. With the quietest-point cut, every cut landed
inside its pause. The teleprompter and the splitter number G02's five chapters identically.

**Could not do.** No real takes exist yet, so the split has only run on the placeholder voice. A
human reading has messier gaps; the quietest-point cut is meant for that, but it is unproven.

## 4. Rhythm and sound (2026-10-13)

**Changed.**
- **Two script tags, honoured by the skeleton and never changed by the model.** The decision may choose
  their pictures, nothing else.
  - `BREATHE: yes` makes the beat one picture held 12–25 s (split at legal cuts if longer), with no camera
    move, the music 10 dB down and no designed effects.
  - `MONTAGE: yes` cuts the beat every 2–3 s at legal cuts, never inside the 3 s hold after a figure.

  Two styles carry them, `breathe-hold` and `montage-cut`; the validator lets a hold pass the 14 s ceiling.
- **A motivated camera**, behind `FILM_MOTION=motivated` for the founder's verdict:
  - a world still holds unless the plan moves it or it follows a figure;
  - a desk shot's rig moves only when a figure of its own lands. A document's camera still travels to
    the phrase being read, which is motivated by the words.

  The default stays the locked camera.
- **Sound:**
  - a figure's landing is marked only for a shot's first figure and its hero figure, not every figure;
  - designed effects have a ceiling of 10 a minute and no floor; the old "nothing designed for 60 s" rule
    is gone;
  - each chapter gets one silence, music and effects out for 2.2 s just before its KEEP line, or else its
    first hero figure;
  - a BREATHE hold ducks the music 10 dB and carries no effects.
- **film-qa** checks each chapter has its silence, and skips BREATHE spans when it looks for frozen
  pictures.

**Measured on G02** (its existing plan; its BREATHE and MONTAGE markers take effect in the full re-run below).

| | Before | After |
|---|---|---|
| Designed effects a minute | 11.7 | **9.5** |
| Silence per chapter (music and effects out) | none | **2.2 s in each of the five** (the open included) |
| Voice over music, under speech | 16.0 dB | 16.5 dB |

**The camera comparison** (`media/motion-compare.mp4`, locked on the left, motivated on the right). The
change from the first frame to the last of s014, a world still with no figure before it, fell from
24.5 to 1.1: it holds. s005 (a still after a figure) and s001 (a desk shot with its own figure) push in
both, as designed.

**The look was re-locked** for the two new styles in `styles.json`, the same kind of change as the
2026-10-07 re-lock. Nothing else in the locked files moved. The camera default is not part of the lock
change; it waits for the founder's verdict on the comparison.

**Could not do.** The full visual trial (one shot of every style) was not re-rendered for the re-lock;
the two new styles are in the trial plan and will render with its next run.

## 5. The music library (2026-10-13)

**Changed.**
- **A cue** is any licensed audio file in `assets/music/` with a sidecar: its mood (calm, tension, lift,
  resolve or montage, set by a person), its tempo and key (read by code with librosa), its licence and
  source.
- **`hubricon-content music-tag`** writes the sidecar and refuses a cue without a licence;
  **`music-list`** shows the library.
- **The decision brief** asks one line more: each chapter's mood (`"moods"`). The plan keeps it.
- **The mix** gives each chapter a cue of its mood:
  - never one used twice in a film;
  - never one another film used in the past 7 days (`content/.cache/music-usage.json`);
  - otherwise the chapter keeps the bed's family variation, as before.

  The crossfades at chapter cards are unchanged.

**Measured.** The library holds one cue, the films' existing bed, tagged *calm*. That mood comes from
its description and needs confirming by ear. It reads as A♯ minor; its tempo, 31 BPM, is unreliable,
since a sparse cue gives the beat tracker little to lock onto. On a synthetic A-major chord with a
120 BPM click, the tagger read "A major" at 100–140 BPM.

**Could not do.** No new cues were added (the founder's call: code now, cues later). With one cue, a film
gets at most one library cue a week; every other chapter keeps the family variation.

## 6. Form: teardown, method, story (2026-10-13)

**Changed.**
- **A tier-D script needs `FORM:`**, one of `teardown`, `method` or `story`. The intake holds each form to
  its own profile:
  - *method*: a question before each chapter's answer, the 40 s re-hook, a KEEP per chapter;
  - *teardown*: a KEEP per chapter, and one chapter carried by a single sourced case (three or more of its
    figures from one source, not demo data). No question or re-hook rule;
  - *story*: one KEEP for the film. No question or re-hook rule.

  Every form keeps the chapter length, TRY and recall rules. The intake records the form on the unit.
- **The queue** won't start a film whose line is about to begin when the last film started within 7 days
  had the same form. A start is recorded when his takes become the film's narration.

**Measured on G02.** Given `FORM: story` and test markers (a TRY on "What you can do this week", one KEEP
taken verbatim from "The step", BREATHE on "The return", MONTAGE on "The chain"; the narration untouched),
G02's script fails one rule. Its teaching chapter, "Your dime", runs 11.9 minutes, over the 6-minute
ceiling. Splitting it adds chapter cards and so spoken words, which is the founder's edit to make.

## 7. CTA and worksheet (2026-10-13)

**Changed.**
- **The single CTA must come within 30 s after the TRY beat ends.** A script that places it elsewhere is
  refused. The doctrine (§13), the kit and the script-draft skill now say so: the honest limit, then the
  step to try, then the CTA while the step is fresh (the founder's call, 2026-10-13).
- **`describe` writes `pinned-comment.txt`:** the film's own spoken CTA, then its tracked link
  (`/learn?src=yt-<unit>`).
- **`worksheet`** also writes `worksheet.pdf`. The sheet is set in the site's type and printed by the same
  Chromium that renders the films.

**Measured on G02.** Its CTA (at 28:55) sits 17 s after the TRY beat ends (28:38), so it passes. The pinned
comment reads its spoken CTA, then `https://www.hubricon.com/learn?src=yt-g02`. The worksheet PDF is one
Letter page; the first layout ran to two, so the type was tightened and the sheet no longer calls itself
"one-page".

**Could not do.** Putting the PDF on the matching /learn lesson is a site change, waiting for the founder's go.
YouTube's API can post a comment but not pin it, so pinning stays a click.
