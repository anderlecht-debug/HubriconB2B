# Hubricon video production bible

Fourth companion document. Governs the animated explainer library specified in
`hubricon-learn-build-prompt.md` §5. That document assigns format by job; this one specifies how
the animated format is actually built.

Scope: the explainer library only. The Reimbursement Playbook stays raw screen recording, and
founder-presence video stays unproduced. Nothing here applies to those.

---

## 1 · The central constraint

**The Vox aesthetic comes from real source material with motion applied, not from generated
footage.** Archival stills, document scans, screenshots, maps and charts — pushed, parallaxed,
annotated, cut fast. It reads as journalism because every frame is evidence.

Generated video has a recognizable signature: soft morphing, drifting detail, unnaturally smooth
camera movement. Viewers identify it in under two seconds. On a business whose entire claim is
that every number is checkable, looking synthetic is a specific and expensive failure.

Therefore: **Higgsfield is an atmosphere tool in this pipeline, not the spine.** The spine is real
data and real screenshots.

The advantage this creates is real. Vox must source its data. The engine generates it.

---

## 2 · Screen-time budget

| Layer | Share | Content |
|---|---|---|
| **Engine-rendered charts** | ~40% | Real `MONTE_CARLO.RUN` cash cones, `ELASTICITY.FIT` curves with confidence bands, `MARGIN.DECOMP` waterfalls, `NEWSVENDOR` service-level cost curves. Built progressively, annotated on top. |
| **Real screenshots** | ~25% | Seller Central, live listings, fee reports, reimbursement tables, supplier invoices. Zoomed, highlighted, circled, redacted where needed. This is the archival-footage equivalent. |
| **Kinetic typography** | ~25% | Numbers and short phrases landing in sync with narration. The cheapest thing that makes an explainer read as expensive. |
| **Higgsfield** | ~10% | Textures, chapter-card backgrounds, atmospheric transitions, stylized abstract stills. Never the subject being explained. Never a person. |

---

## 3 · The signature: Manim driven by the engine

Animate charts in **Manim** (Python, built for mathematical animation), not in a motion-graphics
GUI. The engine is already Python, so Manim scenes can be driven directly from real model output
rather than from numbers retyped by hand.

- One Manim scene module per model: cash cone, elasticity curve, fee waterfall, newsvendor curve,
  anomaly timeline.
- Each takes the model's actual output object as input. If the number on screen didn't come out of
  a real run, it doesn't go on screen.
- Export as PNG frame sequences or transparent-background ProRes for compositing.
- Build every chart **progressively** — axes, then data, then the annotation. Never cut to a
  finished chart.
- Annotate on top in the Vox manner: an arrow, a circle, a highlight band, a callout number. The
  annotation is what turns a chart into an argument.

This is the defensible part of the whole production system. A competitor with a motion designer
cannot reproduce it, because the model underneath is the thing they don't have.

---

## 4 · Sound design — the real amateur tell

Mute a Vox video and it collapses. This is the highest-return, lowest-effort upgrade available and
it is almost always the thing missing from a first attempt.

Required layers on every video:

1. **Room tone** under the entire piece, at roughly −45 to −50 dB. A synthetic voice over digital
   silence is the single loudest AI tell there is. Also add a very slight short reverb to the
   narration so it sits in a space.
2. **Data ticks.** A soft, short percussive element each time a data point, bar or annotation
   lands. This is what makes charts feel authored.
3. **Transition whooshes** on chapter changes and whip cuts. Low, brief, not cartoonish.
4. **Music that ducks.** Sidechain or manually duck the bed to roughly −20 dB under narration, then
   let it come up in the gaps between sections. The swell in the silence is where the emotion is.
5. **Narration mastered** to about −16 LUFS integrated, with a gentle de-esser and a light
   compressor. Not loud, just consistent.

---

## 5 · Narration with ElevenLabs

**Voice:** a clone of the founder's own voice, not a stock preset. Train it on 3+ minutes of clean
audio — one microphone, quiet room, no processing, no EQ, no noise reduction. Garbage training
audio cannot be fixed by settings.

**Disclose it.** One line in each description: the narration is a clone of the founder's voice,
the analysis is his. Cheap to say, disproportionately expensive to be caught not saying.

**The script controls the read more than the settings do.** Write for the mouth:
- Short sentences. Fragments are fine.
- Contractions always.
- Ellipses and line breaks to place pauses; the model reads punctuation as timing.
- First person, conversational, curious. Not announcer voice, not corporate.
- State the thesis in the first fifteen seconds, then evidence.
- 700–900 words ≈ 5 minutes.

**Settings and workflow:**
- Stability around 0.35–0.50. High stability flattens the read into robot cadence.
- Generate **per paragraph, not per script.** It lets you re-roll a single bad line and control the
  gap between sections in the edit rather than accepting the model's pacing.
- Re-roll any line where emphasis lands on the wrong word. It's faster than fixing it in the DAW.
- Keep the takes. A consistent voice library across twenty videos is part of the series feel.

---

## 6 · Edit rules

- **Cut every 2–4 seconds.** Nothing holds longer than about six. A first attempt at this style
  typically holds shots for eight and feels like a webinar.
- Motion on every still: slow push, slight parallax on layered elements, or a subtle drift. No
  static frames.
- Whip pan or hard cut between chapters, never a dissolve.
- Chapter cards with large type, held one second, over a Higgsfield texture.
- On-screen numbers appear the instant they're spoken, never before, never after.
- Subtitles burned in, always. Most of the audience watches muted on a phone.
- Subtle grain over the whole timeline. It unifies mixed source material more than anything else
  and it is the single most effective trick for making generated and real footage sit together.
- 16:9 master at 1080p minimum. Shoot the vertical cuts separately from the same assets rather
  than cropping the master.

---

## 7 · Style lock

Produce one explainer end to end. Then **freeze** and reuse across all subsequent videos:

- Palette: the Hubricon dark navy and amber, plus one off-white for chart grounds. Three colors
  total, nothing else.
- Type: Fraunces for chapter cards and headlines; one grotesque for data labels and annotations.
- Intro card, outro card, chapter-card layout, lower-third layout.
- Chart treatment: axis weight, grid opacity, annotation style, build timing.
- Narration pacing and the ElevenLabs settings used.
- Music bed family and the SFX set.
- **Save the Higgsfield preset or reference set** so texture generation is reproducible.

Unlocked style produces a pile of videos. Locked style produces a series, and only a series
compounds into an audience.

---

## 8 · Tool stack

| Need | Tool |
|---|---|
| Chart animation | Manim, driven by engine output |
| Edit and composite | DaVinci Resolve (free; Fusion covers the motion graphics) |
| Voice | ElevenLabs, founder voice clone |
| Textures, backgrounds, abstract stills | Higgsfield |
| Music and SFX | Epidemic Sound or Artlist; Freesound for one-shots |
| Screen capture | OBS at 60fps, then retime |
| Subtitles | Resolve's built-in transcription, manually corrected |

---

## 9 · The five-minute template

Reuse this structure for every explainer.

1. **Hook, 0:00–0:15.** One concrete dollar figure and the claim. *"The average $5M seller leaves
   about $48,000 a year on the table in one specific place. Here's how to find it."*
2. **Stakes, 0:15–0:45.** Why the intuitive approach fails. Real screenshot of the intuitive
   approach failing.
3. **Chapter 1 — the mechanism, 0:45–2:00.** First engine chart, built progressively, annotated.
4. **Chapter 2 — the counterintuitive part, 2:00–3:30.** Second chart. This is the section that
   earns the subscribe.
5. **Chapter 3 — what to actually do, 3:30–4:30.** Concrete and self-executable. Template link.
6. **The honest limit, 4:30–5:00.** What this method can't do and what it would take. No pitch, no
   CTA beyond the free template and the course page. The limit *is* the pitch.

---

## 10 · YouTube as outreach

- **Title for search, not for cleverness.** Amazon sellers search real phrases: reimbursement,
  FBA fees, safety stock, storage fees, price testing. Put the phrase in the title.
- **Thumbnail:** a real number and a real chart fragment. No face, no arrows, no shock expression.
  The restraint is the differentiator in this niche, where everything looks like a get-rich course.
- **Set YouTube's synthetic-media disclosure** where the narration is AI-generated. The content is
  original analysis, so this is a formality — but an undisclosed one becomes a story.
- **Do not build a faceless content farm.** Twenty original analytical explainers is a library.
  Two hundred reworded ones is the pattern YouTube actively suppresses and the pattern that would
  destroy the brand's credibility.
- Description carries: the template link, the course page, the disclosure line, and the method
  page. Pin a comment with the template link.
- Every video's assets get repurposed: three vertical cuts, one native LinkedIn upload, one
  newsletter section, one embed on the matching lesson page.

---

## 11 · Acceptance check

1. No generated face, avatar or synthetic human appears in any frame.
2. Higgsfield output never depicts the subject being explained, only atmosphere.
3. Every number on screen traces to a real model run; demo data is labeled as demo data.
4. Charts are Manim scenes driven by engine output, not hand-rebuilt.
5. Every chart builds progressively and carries an annotation.
6. Room tone, data ticks, transition SFX and a ducking music bed are present on every video.
7. Narration is the founder's voice clone, disclosed in the description and in YouTube's
   synthetic-media setting.
8. No shot holds longer than six seconds.
9. Subtitles are burned in.
10. The style lock exists as a written spec plus a saved Higgsfield preset before video two.
11. The Reimbursement Playbook remains unanimated raw screen capture.
