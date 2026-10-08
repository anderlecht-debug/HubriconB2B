# Learning design: how the films teach, as checks

The films exist to teach a seller something they can use. Every rule below comes from research on how
people learn from narrated pictures, and each is checked by code, for no tokens: in the script, when it is
taken in (`script-in`, `script.learning`), and in the film (`film-qa`, `film_qa.learning`).
This file sits beside SOUND_DESIGN.md.

## The principles, and the rule each became

| Principle | From | The rule | The number | Checked |
|---|---|---|---|---|
| **Segmenting.** People learn more from a lesson in short parts than from one long run. | Mayer, *Multimedia Learning*; Guo, Kim & Rubin 2014 (6.9M edX sessions: median engagement ~100% under 6 min, ~50% at 9–12 min, ~20% beyond) | A chapter runs 1.5 to 6 minutes. A long teaching section is split at its steps. | 225–900 words; 6.5 min in the film | script, film |
| **A guess before the answer.** Being asked first, even when the guess is wrong, makes the answer stick. | the pretesting effect (Richland, Kornell & Kao 2009; Kornell, Hays & Bjork 2009) | Every chapter asks the viewer a question before it answers. | at least one `?` a chapter | script |
| **Signaling.** Mark what matters as it is said. | Mayer | Each chapter closes on its takeaway: one sentence, spoken, and set on screen word by word as it is said (a fixed kinetic-thesis card). | `KEEP:`, 12 words at most, said verbatim | script, plan |
| **Temporal contiguity.** A picture teaches best when it arrives with its words. | Mayer | A figure's shot opens on the figure's word: the timing adds a legal cut before every spoken figure, and the skeleton prefers it. | 70% of figure shots within 0.6 s | film |
| **Redundancy.** Narration plus a picture beats narration plus a picture plus the same words printed. | Mayer | On screen goes the figure or the key phrase, never the sentence being read. A thesis card holds 12 words at most. | 12 words | plan (validator) |
| **Retrieval.** Recalling something strengthens it more than hearing it again. | Roediger & Karpicke 2006 | The last chapter brings back the film's earlier figures. | at least 2 | script |
| **Transfer.** A method is learned when it is used. | worked-example research (Sweller; Renkl) | One beat gives the step to do this week, marked `TRY: yes`. | at least one | script |
| **A voice that is clear and alive.** Viewers stay with a speaker who is fast and enthusiastic, not slow and flat. | Guo, Kim & Rubin 2014 | Each beat of his reading sits between 120 and 200 words a minute; a beat outside it is read again. | 120–200 wpm | film (his own takes only) |
| **No dead air.** Something on screen responds to the words every few seconds; a chart a viewer must read holds still. | retention editing practice; Mayer's coherence principle | No 4 s frozen picture; no type shot with nothing to draw; no shot opening on bare paper. | freeze 4 s; `shots.CONTENT` | film |

## What the three pilots showed (2026-10-07)

The checks were calibrated on G01–G03, the capability proofs:

- In all three, the teaching chapter ("The card you pay now", "Your dime", "Your calendar") ran 9.4 to 11.9
  minutes in one block. That is the part a seller needs, in the shape least watched.
- 8 of the 17 chapters asked the viewer nothing.
- G03's ending brought back one earlier figure.
- Only 30–33% of figure shots opened on their figure's word. With the figure cut it is 76% on G02's timing.

## Next, when worth it

- **Retention from YouTube.** The real signal: each video's audience-retention curve, mapped onto its
  beats and shots, so a dip names the sentence and the picture it happened on. Needs the Google Cloud
  OAuth setup and public uploads.
- **Pace at the teleprompter.** `record.mjs` shows each take's words a minute and the pause before its
  key figure, so a fast beat is read again on the spot.
- **A worksheet per film.** The TRY beat's steps, with the same demo numbers, as a one-page sheet on the
  matching /learn lesson (a site change, for the founder's go).
