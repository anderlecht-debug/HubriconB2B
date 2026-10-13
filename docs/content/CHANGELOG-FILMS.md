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
