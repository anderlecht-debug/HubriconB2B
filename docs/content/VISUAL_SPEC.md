# Hubricon films: the documentary visual spec

*For Claude Code, on the `content` branch (worktree `HubriconB2B-content`). Written 2026-10-04
from the founder's call that morning and a read of the branch at `9be90dc`; committed here the
same day with his decisions in §13.1. It covers **visuals only**: the scripts are the founder's and are out
of scope, and nothing here touches `script.md`, the doctrine or the critique of a script.*

*Order of authority: `HUBRICON.md`'s honesty rules, then `HUBRICON_SPEC.md`, then this file, then
`docs/content/hubricon-video-production-bible.md` and `docs/content/PREMIUM-STANDARD.md`. Where
this file and the bible or the premium standard disagree, this file wins (§0 says exactly where).
The number-safety rule in `CLAUDE.md` is unchanged and binds every frame.*

---

## 0. The founder's call (2026-10-04), in his words

- "Mirror it off of a YouTuber called Nic Munoz. He makes historical content, documentary style."
- "This needs to all be automated by AI … through the API keys for image sites and stock footage,
  like Pexels and many others … as well as using the ElevenLabs API, and my voice being cloned."
- "High quality videos at scale, at least one a day … the length of the videos is between 20 to 50
  minutes … the founders will actually be paying attention."
- "The script, the writing and the narrative arc will never be the issue for this business … My only
  bottleneck right now is in fact the visuals."
- "Not going crazy with the visuals. He sometimes has the same thing on the screen for like 10
  seconds and that's okay, because you're listening to him."
- "It makes no sense to use those tools whenever I have a repository with every bit of context about
  my business." (So: no all-in-one video generator. Everything is built here.)

What that changes, explicitly:

| Was | Now |
|---|---|
| Films are type and the three house charts on white (`content/film/scenes.mjs`, seven kinds) | Films have two rooms: **paper** (the existing stage, the proof) and **world** (footage, archival stills, AI textures, the story). §3 |
| Bible §6: cut every 2–4 s, nothing over 6 s | Shots of 7–11 s, up to 14 s; a chart build up to 30 s. Nothing on screen is ever frozen longer than 4 s. §4 |
| Bible §2: Higgsfield ≈10%, real screenshots ≈25% | Stock and archival footage join the mix; AI images stay atmosphere, ≤8%. §5 |
| Bible §7 and PREMIUM-STANDARD "Colour"/"Type": navy, amber, Fraunces, JetBrains Mono | Retired. The site's tokens and Inter, everywhere, including Manim and subtitles. §3.1 |
| Bible §6: subtitles burned in, always | Long-form: an exact caption track uploaded to YouTube, nothing burned. Shorts: burned. §8.6 |
| Tiers A (≈5–7 min), B (≈8–15 min), F (the home-page film) | Add tier **D**: 20–50 minutes. §7.1 |
| BRAND.md "No photographs, no stock, no people" | Still true **of the site**. Films may use footage and archival photographs; still no faces in stock or AI frames, no avatars, no synthetic humans (`CLAUDE.md`). §6.6 |

---

## 1. Why the films look like slides today (read this before changing anything)

1. **Two looks in one pipeline.** The film stage (`content/film/film.css`, `scenes.mjs`) is on the
   site's tokens: white, ink, one blue, Inter. The Manim scenes are still on the retired night system:
   `scenes/base.py` hard-codes `NAVY #050A1F`, `AMBER #FFC000`, `GREEN`, `RED`, Fraunces and
   JetBrains Mono. `subtitles.py` sets `FONT = "JetBrains Mono"` with navy outlines; `stylelock.py`
   writes "subtitles: burned, JetBrains Mono"; the bible §7 and PREMIUM-STANDARD still prescribe navy
   and amber. Any agent reading the branch gets two contradictory briefs. (On `main`,
   `engine/src/hubricon_engine/video.py`, the client Profit Brief video, is also navy, amber and
   Georgia. That is a `main` task for a separate session; this branch never touches `main`.)
2. **No world.** Every scene kind is a line of type, a number, a formula or one of three charts on
   white paper. Forty minutes of that is a webinar, however good the narration.
3. **Frozen frames.** `render.mjs` holds a scene's last frame once its motion ends. The case-study
   board holds `b2` (two lines of type) for 30 s with nothing moving.
4. **Cadence rules that contradict each other.** The bible says nothing holds over 6 s; the boards
   hold 10–30 s; `qa.max_hold` flags 6 s. An agent cannot satisfy all three, so it satisfies none.
5. **No long-form tier.** `script.WORDS` tops out at 2,200 words and `qa.TIER_RANGE` at 900 s, so a
   40-minute script fails validation before a frame is drawn.

Fixing 1, 3, 4 and 5 is small. Fixing 2 is this spec.

---

## 2. What the best documentary-style educators do with the picture

The references, and what each contributes:

| Reference | What it is | What we take |
|---|---|---|
| **Nic Munoz**, *The Greats* | Biographies of history's great builders, lessons drawn from the books | The founder's reference: long, calm, narration-led; an image may sit on screen while the voice carries |
| Modern MBA, MagnatesMedia, ColdFusion | Long business case studies and business documentaries | Footage, archival clips, screenshots, charts and calm narration in one film; documentary pacing |
| Vox, Johnny Harris | Explainers built from evidence | The document on screen with the line highlighted; the map; "every frame is evidence" (bible §1) |
| Fall of Civilizations, Ken Burns | Very long histories | Long holds are fine when something in the frame moves; the slow push toward the subject |

I could not play Nic Munoz's episodes from where this was written. What follows is the grammar of the
genre he works in, taken from documentary craft sources. **Before locking the look (§12, phase 5),
watch one of his episodes beside our visual trial and note anything below that his work contradicts.**

The shared grammar, as rules we can build:

1. **Footage is a character, not wallpaper.** "The danger is to put it up there and just talk"
   (David Grubin). Every world shot shows the thing the sentence is about (§6.1, the concrete-noun rule).
2. **Evidence frames.** The real document, filing, newspaper page or fee card on screen, with the line
   that matters marked. This is Hubricon's natural strength: every move gets a receipt.
3. **Stills are never still.** A slow push or pan toward the subject (the Ken Burns move).
4. **Long holds work when the voice carries,** but something always moves: a push, a drift, a build.
5. **One grade, one grain, one type system** over every source, so a stock clip, a 1930s photograph
   and an engine chart read as one film.
6. **Sound carries the rooms.** A bed felt more than heard, ducked under the voice, swelling in the
   gaps; ambience under footage; ticks under data (bible §4 already has most of it).

**The platform rule this protects us from.** Since July 15, 2025, YouTube calls it "inauthentic
content": "channels that upload slideshows that all have the same narration" and "narrative stories
with only superficial differences between them". Using AI stays eligible. What keeps us clear:
original analysis from the engine, the founder's voice, and **no asset reused across films** (§6.7).

---

## 3. The look: two rooms

**Paper is where we prove. The world is where we tell.**

Every shot in a film is one named **style** from the library in §14: thirty of them, each explained
with its job, when to use it, its exact recipe, how the pipeline builds it and what failure looks
like, most with an example frame. This section sets the rules every style obeys.

- **Paper**: the existing film stage on `/assets/hubricon.css`: charts, numbers, kinetic lines,
  formulas, documents, quotes, chapter cards. Every number on screen lives here and only here.
- **World**: full-bleed footage, archival photographs and AI textures. No figure ever appears in the
  world room (the date in an archival credit or lower third is provenance, not a figure). No headline
  is set over footage.
- **Cuts between rooms are hard cuts on a sentence boundary.** No dissolves, wipes, whips or zooms
  between shots (PREMIUM-STANDARD "Motion").

**The world is bright and cold, not dark and moody.** Three reasons. The brand is a white page with
one cold blue; a dark, warm documentary grade would be a second brand. A cut from a dark warehouse
to a white chart is a flash in the viewer's eyes forty times a film. And the blue means money: if the
footage is graded teal, the blue stops meaning anything. So the world is high-key, overcast,
cool-neutral, desaturated, with blues and cyans pulled down further so the **only saturated blue on
screen is money**.

### 3.1 One source of tokens

- Write `content/film/tokens.mjs`: it parses the custom properties in `/assets/hubricon.css` and
  writes `content/assets/tokens.json` (colours, the two Inter weights, the spacing scale, the radius,
  `--ease-out`). Run it from `render.mjs` and from Python before every render, so a token change on
  the site reaches the films the same day.
- `scenes/base.py`, `subtitles.py`, `thumbnail.py`, `shorts.py` and every new module read colours and
  fonts from `tokens.json`. **No hex literal anywhere in `content/src` or `content/film` except
  `tokens.json` itself.** A test (`content/tests/test_one_look.py`) greps for `#[0-9a-fA-F]{6}`,
  "Fraunces" and "JetBrains" in those trees and fails on any hit outside the archived night-system
  files.
- Add Inter (OFL) as a variable TTF with its optical-size axis to `content/assets/fonts/` and register
  it with manimpango, so Manim draws Inter Display at headline sizes exactly as Chrome does. Leave the
  Fraunces files where they are, unused.
- Values, for reference (the CSS is the source): paper `#ffffff`, paper-2 `#f5f6f8`, ink `#0a0e17`,
  ink-2 `#3b4250`, ink-3 `#636b7a`, rule `#e4e7ec`, rule-2 `#cdd2da`, blue `#0b5fff`; night ground
  `#070a11`, night blue `#5b94ff`. **No red, no green** (BRAND.md): a loss is ink with a minus sign.
  The Manim palette's `GREEN` and `RED` go.

### 3.2 The world grade (locked)

Every world asset (footage, still, AI image) goes through the same four stages, in this order, in
`content/src/hubricon_content/grade.py`. The chain below runs on ffmpeg 6 as written (tested
2026-10-04 on a synthetic source). Put the numbers in `content/assets/grade.json` so the style lock
can fingerprint them.

1. **Conform.** Scale to cover 1920×1080 around the picked focus point, crop, `fps=30`,
   `setsar=1`, BT.709, TV range.
2. **Normalize.** Measure the chosen window with `signalstats`. Shift `eq=brightness` so the mean
   luma (`YAVG`) lands at **138 ± 10** (of 255), and scale `eq=saturation` so mean saturation lands in
   the target band. If the shift needed is more than ±0.12 brightness, **reject the asset**: it is too
   far from the look to grade honestly.
3. **Grade.**
   `eq=saturation=0.78:contrast=0.94:brightness=0.03:gamma=1.04,colortemperature=temperature=6900:mix=0.6,huesaturation=saturation=-0.55:colors=b+c`
   (soft contrast, lifted shadows, a slight cool shift, blues and cyans pulled down).
4. **Grain.** `noise=alls=6:allf=t+u` on world clips; `noise=alls=2:allf=t+u` on paper clips.
   Grain moves from the master (`assemble.GRAIN`) to the clip, so each room gets its own strength.

Black-and-white archival photographs skip the colour steps: `format=gray`, the same normalize and
the same grain, then back to yuv420p. They stay monochrome; never colourize.

### 3.3 Type in the world room

Only three things are ever set over a world shot, all Inter, all from provenance, never typed:

- **Credit line** (every archival still and document, and stock where the licence asks): bottom right,
  Inter 400, 24 px, white at 70%, e.g. "Library of Congress". Filled from the asset's provenance.
- **Place and date** (archival only, and only when the provenance carries them): bottom left,
  Inter 600 34 px over Inter 400 28 px, white, a 1 px shadow at 35%. Never on stock footage.
- **"Illustration"** on every AI image: the site's label style, small, bottom right
  (BRAND.md: "An illustration says it is one").

Keep everything that matters above the bottom 12% of the frame, where YouTube's controls sit.

### 3.4 Motion

- **Stills** (archival and AI): one move per shot, eased in and out (`cubic-bezier(0.37,0,0.63,1)`):
  push 1.00→1.07, pull 1.07→1.00, or pan up to 5% of the frame width at a fixed 1.08. Toward the
  focus point from the pick. Never over 1.10, except the detail pull-back (§14, W3), which starts at
  1.35 on a source wide enough to stay sharp there. Every move is one of the four in §14 (W1–W4).
- **Footage**: real time, or slowed to 0.8× when the source is 60 fps. Never sped up, never
  time-lapse unless the sentence is about time passing. No digital zoom past 1.10.
- **Paper**: the build as today (axes, data, annotation, then the band), then a drift of the whole
  stage 1.000→1.015 over the rest of the shot, centred on the blue (the riser, the number, the cliff).
  The drift replaces the frozen hold in §1.3.
- **Nothing on screen is frozen longer than 4 s.** QA enforces it with `freezedetect` (§10).
- **Rhythm.** Never two moves of the same kind back to back. Goods moving in a sequence move the same
  way across cuts (left to right). Within a world sequence, wide, then medium, then detail.

---

## 4. Cadence for 20 to 50 minutes

Shots are cut at word boundaries from the narration's alignment, preferably in a pause of at least
120 ms. The founder's ten-second hold is the baseline; the opening is denser because that is where a
long video loses people.

| Rule | Value |
|---|---|
| Shot length, body | target 7–11 s; minimum 3 s (chapter cards and breaths excepted); maximum 14 s |
| Shot length, first 60 s | median ≤ 6 s; nothing over 8 s |
| Chart build on paper | up to 30 s, with something new landing at least every 8 s |
| After a spoken number lands on screen | hold it at least 3 s before the cut |
| Longest stretch in one room | world 90 s, paper 120 s |
| Same shot kind in a row | at most 3 |
| A change of texture (chapter card, document, number, or a room change after a long run) | at least every 3 minutes |
| Chapter card | 2.5 s, typographic, on paper, a whoosh and a bed swell under it |

Rough arithmetic: a 40-minute film is about 2,400 s, so about 250–300 shots.

*Rulings, 2026-10-04, from planning the first approved script: (1) a number must be readable, so
when figures are spoken close together in the first minute, a paper shot may run past 8 s, but only
to the first legal cut after its last figure's 3-second hold, and it does not count toward the
opening median; (2) a chapter card is exactly the timing's card segment (2.5 s on tier D; tiers A
and B keep their 1.1 s).*

---

## 5. Screen-time budget

Two presets, chosen per film in `shots.json` (`"mode"`). The validator holds each share to its range.

| Room | Kind | `explainer` | `history` |
|---|---|---|---|
| Paper | Engine charts (the house visuals and the Manim models) | 30–40% | 15–25% |
| Paper | Numbers, kinetic lines, formulas | 10–15% | 8–12% |
| Paper | Documents (fee cards, filings, newspaper pages) | 8–15% | 10–18% |
| World | Stock footage | 20–30% | 15–25% |
| World | Archival stills and archival film | 3–10% | 20–35% |
| World | AI textures and atmosphere | ≤ 8% | ≤ 8% |
| Paper | Chapter cards | ~2% | ~2% |

---

## 6. Sourcing

### 6.1 What a world shot may show

- **The concrete-noun rule.** A world shot shows the most concrete noun in the sentence it sits
  under: containers for a sentence about containers, a pallet for a sentence about a pallet. If the
  sentence has no concrete noun, the shot goes to paper (a kinetic line, a number, a chart) or, at
  most, a texture.
- **Banned clichés**, never queried and never picked: handshakes, people in suits, laptops or phones
  showing charts, stock tickers, piles or fans of cash, piggy banks, light bulbs, chess pieces, puzzle
  pieces, rockets, generic drone shots of skylines, smiling people at desks, whiteboards, sticky notes,
  glowing "data" particles and networks. They are what makes faceless channels look cheap.
- **Prefer**: daylight, high-key, overcast; tripod or slow gimbal; clean industrial and commercial
  subjects (ports, cranes, trucks, warehouses, conveyors, cartons, tape guns, scales, rulers, printed
  labels, shelves, stores, catalogues, ledgers on a desk, hands at work). 4K sources over 1080p.
- **Reject**: night and low-key footage (mean luma under 0.25), shaky handheld, visible watermarks,
  burned-in text, visible logos or brand marks (above all Amazon's: nothing may suggest affiliation),
  any face as the subject.

### 6.2 Specific things need specific evidence

If the narration names a specific real company, person, place or event, the shot under it is
**archival or a document whose provenance names that same thing, or paper**. Never stock, never AI.
Stock footage is only ever "a warehouse", never "Amazon's warehouse in Kentucky". This is the
honesty rule applied to pictures.

### 6.3 Sources, by tier

All keys live in `.env` (add them to `.env.example`). A missing key marks the `source` step
`blocked` with the key's exact name. Never substitute a source the shot plan did not allow.

| Tier | Source | Access | Limits and rules | Accept |
|---|---|---|---|---|
| Stock footage | **Pexels** | `GET https://api.pexels.com/v1/videos/search`, key `PEXELS_API_KEY` | 200 requests an hour, 20,000 a month by default; a prominent link to Pexels and credit to the creator when possible | Pexels licence |
| Stock footage | **Pixabay** | `GET https://pixabay.com/api/videos/`, key `PIXABAY_API_KEY` | 100 requests per 60 s; **responses cached 24 h**; download, don't hotlink; show the source | Pixabay licence |
| Archival stills | **Library of Congress** | loc.gov JSON (`?fo=json`) | "No known restrictions on publication" only; record the rights text; the Library says the user decides rights, so keep the record | No known restrictions |
| Archival stills | **Smithsonian Open Access** | api.si.edu, key from api.data.gov (`SMITHSONIAN_API_KEY`) | CC0 only | CC0 |
| Archival stills | **Wikimedia Commons** | MediaWiki API, `extmetadata` | Public domain, CC0, CC BY with credit. **Reject** BY-SA, NC, ND, fair use and unknown | PD, CC0, CC BY |
| Archival film | Internet Archive (Prelinger), NARA | their item metadata | public-domain marks only | PD |
| Documents | `ratecard.json`, engine output, SEC EDGAR filings, Library of Congress newspaper pages | typeset from data, or a real page image with provenance | **Never scrape Amazon.** Amazon answers automated reads with a Conditions of Use warning (`HUBRICON_SPEC.md` on `main`, amended 2026-10-01). Amazon's fees are typeset from `ratecard.json`, labelled with the date they were recorded. Seller Central captures come from the founder only | — |
| AI textures | **Higgsfield, through the claude.ai connector** (the founder's call, 2026-10-04; it made the brand stills, whose job ids are in BRAND.md). The runner's Claude calls it; no key in `.env` | the connector's tools | ≤ 8% of runtime, atmosphere only (§6.5) | — |

Cache every API response under `content/.cache/api/` (git-ignored) for 24 h, and every downloaded
asset under `content/.cache/assets/<source>/<id>.<ext>` by its sha256. Plan the queries so a 40-minute
film stays under **150 Pexels requests**: one or two queries per footage shot, `per_page=40`, the same
query string reused across shots.

### 6.4 Automatic filters before anything is picked

`content/src/hubricon_content/sources/filters.py`, applied to every candidate:

- footage at least 1920×1080, at 30 or 60 fps (24 and 25 only when nothing else exists), long enough
  for the shot plus one second, no internal cut in the chosen window (`scdet`);
- stills at least 2,400 px on the long edge (archival at least 1,600, never upscaled past 1.5×);
- luma within the band the grade can reach (§3.2);
- faces: OpenCV's YuNet detector (`cv2.FaceDetectorYN`) on a frame every 2 s; any face over 1% of the
  frame area rejects a stock or AI candidate;
- text and logos: OCR where `tesseract` is installed (more than two words in a frame rejects); the
  visual pick checks again by eye;
- duplicates: perceptual hash against this film's picks and the usage ledger (§6.7);
- licence in the accept list of §6.3, with author, URL and licence text present.

*Rulings, 2026-10-05, from building the filters: (1) archival film is held to the stills' 1.5×
rule, so at least 1280×720 (1080p film scans barely exist), and its 16–24 fps is recorded, not
refused; (2) "24 and 25 only when nothing else exists" is read per shot: a 24/25 (or 50) fps clip
is refused once three passing 30/60 fps clips name as much of the query, and otherwise stays with a
note; (3) text in frame refuses stock only (in an archival photograph a sign is provenance), and
without tesseract the check records "ocr: unavailable" for the pick's eye; (4) Pixabay's search
matches any one tag, so a clip whose tags name fewer than half of the query's nouns is refused, and an
archive searches its whole catalogue text, so an archival record whose title and subjects name none
of them is refused, and an archive that finds nothing is asked once more by the nouns alone; a stock
clip whose title or tags name a banned cliché is refused (an archival record's is noted); (5) the
Internet Archive is read only in the Prelinger Archives and NARA's own uploads (`gov.archives.*`),
never open uploads, and Commons refuses Flickr's "no known copyright restrictions" (the Library of
Congress's own statement is accepted from the Library).*

### 6.5 AI images

- Atmosphere only: an abstract idea, a texture, a still life of objects. **Never the subject being
  explained, never a person or a hand, never a real place, product or event**, never evidence.
- One locked preamble, prepended to every prompt, saved in the style lock with the model, seed and a
  reference image: *"Photographic still life, overcast north light, cool neutral palette, matte
  surfaces, high-key exposure, shallow depth of field, fine film grain, 35 mm, no people, no hands, no
  text, no logos, no screens."*
- Four candidates per shot; the visual pick chooses one or none. Record the job id, model, prompt,
  seed and the date in provenance.
- No generated **video** in this version. The bible's warning stands: generated motion reads as
  synthetic in under two seconds.
- Every AI image carries "Illustration" on screen (§3.3).

### 6.6 Faces and people

`CLAUDE.md` says: no faces, avatars or synthetic humans anywhere. In stock and AI frames that holds
absolutely and the detector enforces it. Hands at work, backs and distant crowds are fine in stock.
Archival portraits of a historical subject: **allowed, credited** (the founder's call, 2026-10-04,
§13.1). A public-domain photograph of the person a film is about may show his or her face, with the
institution and rights statement in the credit line; stock and AI frames stay faceless.

### 6.7 No reuse

`content/assets/usage.json` records every asset each film used. An asset appears **once per film**
and **not again within the next ten films**. The validator and QA both read it.

---

## 7. The pipeline, step by step

### 7.1 Long-form units

- A long-form unit is `kind: "video"` with `tier: "D"`. Add `"D": (3000, 7500)` to `script.WORDS`
  and `"D": (1200, 3000)` to `qa.TIER_RANGE`. That is a length setting, not a script change.
- Its folder `content/videos/<slug>/` gains `shots.json`, `assets.json` (provenance),
  `sources/` (contact sheets), `shots/` (one clip per shot) and `qa/`.

### 7.2 The steps

These replace the `timing → scenes → assemble` stretch of the `produce-video` table for tier D.
Update `.claude/skills/produce-video/SKILL.md` and `state.VIDEO_STEPS` to match (tier A and B units
keep their current steps); every command is idempotent, as now.

| step | command | produces | passes when |
|---|---|---|---|
| tts | `hubricon-content tts <slug>`: the founder's takes from `record.mjs`, aligned with `tts.align` (faster-whisper) | `audio/beat-NN.*`, `alignment/beat-NN.json` | as today. Both voices end in the same two files, so everything after is one path |
| timing | `hubricon-content timing <slug>` | `timing.json` | as today, plus `cutpoints`: every legal cut (sentence ends and pauses ≥ 120 ms) with its time |
| shots | invoke the `shot-plan` skill | `shots.json` | `hubricon-content shots-validate <slug>` prints no problems |
| source | `hubricon-content source <slug>` | `sources/<shot>.jpg` contact sheets, `content/.cache/assets/…` | exit 0; every world shot has at least three candidates after §6.4, or is marked for its fallback tier |
| pick | invoke the `visual-pick` skill | `shots.json` with each `asset`, `focus` and `motion` filled | `hubricon-content shots-validate <slug> --picked` prints no problems |
| render-shots | `hubricon-content render-shots <slug>` | `shots/<id>.mp4`, one per shot, frame-exact | exit 0; every clip is exactly its shot's frame count |
| scenes | `hubricon-content render-scenes <slug>` | the Manim chart shots only, restyled (§8.4) | exit 0 |
| assemble | `hubricon-content assemble <slug>` | `media/master.mp4`, `media/captions.srt` | exit 0 |
| qa | `hubricon-content qa <slug>`, then `critique render <slug>` | `qa.json`, `qa/contact.jpg`, `qa.review.json` | both pass (§10) |
| thumbnail, describe, shorts, approve_final, upload | as today | | as today, plus §8.6 and §11 |

The founder's gates do not move: nothing renders before `review == approved`, nothing uploads before
`approve_final == approved` with a publishable voice.

### 7.3 `shots.json`

```json
{
  "slug": "…",
  "mode": "explainer",
  "fps": 30,
  "shots": [
    {
      "id": "s001",
      "beat": "b01",
      "start": 0.000,
      "end": 5.840,
      "says": "the words spoken under this shot, from the alignment",
      "room": "world",
      "kind": "footage",
      "style": "footage-establish",
      "on": null,
      "params": {},
      "intent": "one line: what the viewer sees and why it fits these words",
      "query": ["container ship berth daylight", "gantry crane unloading containers"],
      "sources": ["pexels", "pixabay"],
      "fallback": "paper:kinetic",
      "motion": null,
      "focus": null,
      "overlay": {"credit": null, "place": null},
      "reveals": [],
      "asset": null
    }
  ]
}
```

- `room`: `paper` or `world`. `kind`, paper: `chart` (with the existing scene spec, e.g.
  `{"scene": "staircase", …}`), `number`, `pair`, `grid`, `kinetic`, `formula`, `document`, `table`,
  `timeline`, `receipt`, `archive`, `stack`, `split`, `quote`, `chapter`, `end`. World: `footage`,
  `still`, `texture`. §14 says which style renders as which kind.
- `style`: one id from §14 (required). `on`: the word or `{{key}}` in `says` that the style's main
  event lands on (the highlight, the second number, the pull-back), resolved to a time from the
  alignment; `null` when the style has no such event. `params`: what that style needs (a document's
  target line, a table's row, a `group` shared by the three shots of a process sequence, the shot a
  `callback` returns to, a `bridge`'s target and shape).
- `reveals`: each `{{key}}` spoken inside the shot with the second it is spoken, from `timing.json`.
  Only paper shots carry reveals.
- `asset`, after the pick: `{"id": "pexels:1234567", "file": "…", "sha256": "…", "licence": "…",
  "author": "…", "url": "…", "retrieved": "2026-10-04", "in": 2.4, "out": 8.2}` for footage, or the
  same without `in`/`out` for a still. AI images add `job`, `model`, `prompt`, `seed`.

### 7.4 What `shots-validate` enforces

1. The shots cover the narration exactly: no gap, no overlap; every cut is a legal cut from `timing`.
2. Every length rule in §4; every share in §5 for the film's mode.
3. Every spoken `{{key}}` is revealed on a paper shot at the second it is spoken (bible §6), and no
   world shot carries a reveal or a figure (provenance dates excepted).
4. No world shot under a sentence that names a specific company, person, place or event unless its
   asset's provenance names the same (§6.2). The skill tags such sentences with `"specific": "<name>"`;
   the validator checks the tag against the provenance.
5. Every world shot has a query with no banned cliché term (§6.1), and every pick passes §6.4.
6. No asset twice in the film or in the usage ledger's window (§6.7).
7. Every AI shot has `overlay.illustration: true`; every proof shot (a case-study figure) carries the
   label "Modeled from public data · Not a client · Not a result"; demo figures say "demo data".
8. Every shot has a `style` that is allowed for its room and kind, every `on` is found in `says`, and
   the film meets the variety rules in §14.8.

### 7.5 The two skills Claude Code runs

**`.claude/skills/shot-plan/SKILL.md`.** Input: `script.md` (read only, never edited), `facts.json`,
`timing.json`, the mode, and §14 of this file. For each beat, walk the sentences; group them into
shots on legal cuts; give each shot a room by the rule *a number, a comparison or a mechanism goes to
paper; a thing, a place or a moment goes to the world*, then a style from the picker (§14.2), reaching
for the sequences (§14.6) where a run of sentences fits one; set `on` and `params`; write the intent; write one or two literal queries
made of the sentence's concrete nouns; set the fallback (archival → stock → texture → paper kinetic).
Then run `shots-validate` and fix until clean.

**`.claude/skills/visual-pick/SKILL.md`.** For each world shot, open its contact sheet
(`sources/<shot>.jpg`, up to nine candidates with three frames each for footage), read `says` and
`intent`, and pick the one that shows the concrete noun most plainly in the look of §3, or none. Set
`focus` (where the subject sits, 0–1 in x and y) and `motion`, and for footage the `in` and `out`
inside a continuous take. If none fits, re-query once with different nouns, then take the fallback.
Write the reason for each pick in one line in `assets.json`. Then run `shots-validate --picked`.

---

## 8. Rendering

### 8.1 New paper and world kinds on the film stage

Add to `content/film/scenes.mjs` and `film.css`, on the tokens, with the existing `.in` entrance and
the corner (label and mark). Each kind serves one or more styles in §14, and every number a style
uses lives in `content/film/styles.json`, never in the CSS. `docs/content/styles/styles-trial.css` is
the reference CSS that drew the example frames; start from it. *(Not in the repo, see §14; build
each kind from its style's recipe.)*

- **`still`** (world): a full-bleed `<img>` on the graded file, `object-fit: cover`, the §3.4 move as a
  CSS animation across the whole shot, the overlays of §3.3.
- **`texture`** (world): as `still`, always with "Illustration".
- **`document`** (paper): the page (a graded page image, or a typeset table drawn from data) in a
  frame with a `--rule` hairline, never a shadow, starting at 0.92 of the stage and pushing toward the
  target line over the first 60% of the shot. Then the mark: a 3 px **blue** underline drawn left to
  right if the line is money, a 2 px ink underline otherwise. A source line underneath, Inter 400
  28 px, ink-3, from provenance, e.g. "Amazon's published fee card, 2026 · as recorded in ratecard.json
  on <date>". A typeset document never imitates Amazon's interface.
- **`quote`** (paper): Inter 600, 64–72 px, ink, at most 22 characters a line; attribution Inter 400
  36 px, ink-3. Only words that exist in a dated source, and the source in the attribution.
- **`chapter`** (paper): a 120 px ink hairline, then the title in Inter 600 at 96 px; 2.5 s; no
  numbering, so no digit reaches the screen outside a placeholder.
- **Drift** on every paper kind (§3.4).
- **`map`** (paper) waits for a later version: Natural Earth (public domain) through `d3-geo`, coasts
  as an ink hairline, the route in ink, the leg that costs money in blue.
- **The library's other paper kinds**, each specified in its style's entry in §14: `pair`
  (`number-pair`), `grid` (`unit-grid`), `table` (`table-scan`), `timeline`, `receipt`, `archive`
  (`archive-framed`), `stack` (`archive-stack`) and `split` (`split-then-now`).

### 8.2 Footage

`content/src/hubricon_content/footage.py`: cut `in`→`out` from the cached source, conform, normalize,
grade, grain (§3.2), slow to 0.8× only from 60 fps, strip the source audio, and write exactly the
shot's frame count (`-frames:v`). One H.264 clip per shot at the master's settings.

### 8.3 One clip per shot, cached and parallel

Change `render.mjs` from one long ffmpeg pipe to **one clip per shot**, at
`content/videos/<slug>/shots/<id>.mp4`, named by a cache key: the sha256 of the shot's spec, its
asset's sha256, `tokens.json`, `grade.json` and the renderer's version. A re-render after a one-line
change rebuilds one clip, not a film. Run N Chrome workers in parallel (default: cores ÷ 2). Moving
shots (every `still`, `texture`, `document`, and every drift) capture every frame; that is the cost of
nothing being frozen, and parallelism pays for it.

### 8.4 Manim, restyled

`scenes/base.py` reads `tokens.json`: paper ground, ink lines, ink-3 axes, blue only on the money and
the band, Inter at the film stage's sizes (heading 72 px, caption 44 px, labels at least 40 px at
1080p), the stage's margins (120/160/132 px) and the corner. Delete `GREEN` and `RED`. A Manim chart
and a film-stage chart in the same film must be indistinguishable in frame, type and colour: put one
frame of each side by side in `qa/` and judge it by eye (Claude Code reads the PNG).

### 8.5 The master

Concatenate the shot clips (same codec settings, so the concat demuxer joins them), re-encode once at
1920×1080, 30 fps, x264 `-crf 16 -preset slow`, BT.709 TV range (as `render.mjs` does today), audio
from the mix (§9). No master-level grain: it is on each clip now.

### 8.6 Captions

For tier D, write `media/captions.srt` from the alignment (the exact script words, sentence case,
at most 42 characters a line and two lines) and upload it as the video's caption track. Nothing is
burned into the long-form master: burned text fights the charts and the numbers on a 40-minute
film, and YouTube's own track is searchable and switchable. Shorts keep burned subtitles, restyled
to Inter (§3.1).

---

## 9. Sound for the two rooms

`audio.py` keeps its levels (room tone −48 dB, bed −32 dB, ducking −20 dB under the voice, ticks
−26 dB, whooshes −22 dB, −16 LUFS integrated). Three additions:

- **World ambience.** Under each footage shot, a short ambience matched to its subject (a port, a
  warehouse, a street) from the sound library, at −40 dB, with a 0.4 s crossfade at the cuts. The
  clips on file were made with ElevenLabs during the paid subscription and stay licensed; nothing new
  is generated (2026-10-06, §13.1). A new clip comes from Freesound (CC0 only) or Pixabay, filed with
  its page and licence (`hubricon-content ambience-add`); a subject with no clip plays room tone alone.
  One ambience per subject, reused within the film so it is consistent.
- **A bed family.** Three or four cues from the same family (sparse piano and low strings, no melody,
  PREMIUM-STANDARD), one per chapter, crossfading under the chapter card.
- **The gap.** After a big reveal or at a chapter's end, 1.5–2 s with no voice: the bed comes up and
  the picture holds a moving shot. Taken from the script's own paragraph breaks, never invented.

---

## 10. QA, by program and by eye

`qa.py` adds, for tier D (thresholds in `qa.json` so the critique can cite them):

| Check | Threshold |
|---|---|
| Duration | within tier D, 1,200–3,000 s |
| Loudness | −16 LUFS ± 1, true peak ≤ −1.5 dBTP |
| Frozen picture | no run over 4.0 s (`freezedetect=n=0.003:d=4`) |
| Shot lengths | from `shots.json`, checked against `scdet` on the master: §4's medians and maxima |
| Rooms | no world run over 90 s, no paper run over 120 s |
| Duplicates | perceptual-hash distance ≥ 10 between any two world shots' middle frames; nothing from the usage window |
| Faces | none over 1% of the frame in any stock or AI shot (a frame every 2 s) |
| World exposure | each world shot's mean luma 128–148 after the grade |
| Blue | saturated blue (hue 212–228°, saturation over 0.6) under 0.5% of the pixels of any world frame; on paper, only in shots that reveal money or the leak |
| Paper | corner samples of paper frames at `#ffffff` ± 3 |
| Black and silence | no black over 0.5 s; no silence over 2 s except under chapter cards |
| Provenance | every asset has a licence on the accept list, author, URL and sha256; the description's credits list them all |
| Labels | proof label on every case-study figure; "Illustration" on every AI shot; "demo data" where the facts are demo |
| Captions | `transcript_match` as today |

Then `qa/contact.jpg`: one frame per shot at its middle, ten across, with the shot id, kind and
source under each, plus a larger sheet of the first minute. The `critique render` skill reads both
against §3 and §6 (the concrete noun, clichés, faces, logos, one grade, blue discipline, layout) and
writes `qa.review.json`. The founder's final review (`approve_final`) shows both sheets at the top of
the `REVIEW.md` block, so approving the picture takes minutes, not forty.

---

## 11. Description and credits

`describe.py` adds, generated from data and exempt from the number guard as scaffolding (as script
timestamps already are):

- **Chapters**, one `M:SS Title` line per chapter card, from `shots.json`.
- **Credits**, from `assets.json` only: "Footage: Pexels (pexels.com) and Pixabay (pixabay.com)",
  then each creator's name; archival items with their institution and rights statement; "Some
  illustrations are AI-generated" when there is one.
- The voice line exactly as `qa.disclosure_for` returns it, and the synthetic-media flag on upload as
  today.

---

## 12. Build order

Each phase ends with its test passing and a commit (with its `Moat:` line). Do them in order.

0. **One look.** `tokens.mjs` and `tokens.json`; Inter for Manim; restyle `scenes/base.py`,
   `subtitles.py`, `stylelock.py`, `thumbnail.py` and `shorts.py`; `test_one_look.py`. Edit the bible
   §6 and §7 and PREMIUM-STANDARD "Colour" and "Type" to say "Superseded by VISUAL_SPEC.md
   (2026-10-04)" with a pointer, rather than deleting them. Add tier D (§7.1).
   *Done when:* a Manim frame and a film-stage frame sit side by side in `qa/` and match.
1. **The shot plan.** `cutpoints` in `timing`, the `shot-plan` skill, `shots-validate` with every rule
   in §7.4 unit-tested.
   *Done when:* an approved script plans and validates clean without a voice (`--estimate` timing
   at 150 words a minute, so planning can be tested before narration exists).
2. **Sourcing.** `sources/` (Pexels, Pixabay, Library of Congress, Smithsonian, Commons; the image
   provider behind one interface), the filters of §6.4, the caches, the contact sheets, `usage.json`.
   *Done when:* a full plan sources inside the rate limits (log the requests used) and every candidate
   has provenance.
3. **The pick.** The `visual-pick` skill and `shots-validate --picked`.
4. **Rendering.** The new kinds, `content/film/styles.json` with every style's numbers, `grade.py`,
   `footage.py`, one clip per shot, the cache, parallel workers, the restyled Manim charts.
5. **The visual trial, then the lock.** A silent trial at `content/videos/visual-trial/` with one
   shot of **every style in §14** (about three minutes), then each sequence in §14.6 once, like the
   style reel. Its contact sheet sits beside `docs/content/styles/contact.png` so the founder can see
   the frames he was promised next to the frames that were built. **The founder watches it** (and one
   Nic Munoz episode beside it, §2). When he approves, extend `lock.mjs`'s `LOOK` with `tokens.json`,
   `grade.json`, `styles.json` and the AI preamble and seed, and lock. Every film after reuses it.
6. **The first long film.** One approved tier-D script through every step, QA and the founder's final
   review. Fix what the first one teaches; re-lock only by a deliberate edit.
7. **One a day.** The overlap of §13.3 in the runner; the meter (§13.4).

Until phase 5 is approved, nothing long renders for publishing.

---

## 13. What the founder decides, and what one a day costs

### 13.1 His decisions (the only blanks)

*Decided 2026-10-04: items 1 and 2, and two more below the list. Item 4 keeps its default (off); 3 and 5 are still his.*

1. **Archival portraits of historical subjects. Decided: allowed, credited.** Public-domain
   photographs of the historical subject a film is about may show a face, credited; stock and AI
   frames stay faceless (§6.6).
2. **The keys**: `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `SMITHSONIAN_API_KEY` (api.data.gov) and
   `CONTENT_CONTACT_EMAIL`, all listed in `.env.example`. **The image provider: Higgsfield through
   the claude.ai connector**; the runner is given that connector and no other.
3. **Approve the visual trial** (§12, phase 5).
4. **Captions burned into long-form?** Default off (§8.6).
5. **A licensed bed family** in `content/assets/music/` (already input 6 in `STATE.md`).

Also decided on 2026-10-04: **long films play on the site as YouTube embeds** (privacy-enhanced,
click to load), since a 40-minute file is too large to self-host.

**The voice, decided 2026-10-06 (the founder's call, superseding the clone of 2026-10-04 and the
library voice "Kevin" chosen that evening): every film is narrated in his own recorded voice. No
ElevenLabs, no clone.** He reads each approved script at the teleprompter (`content/film/record.mjs`);
`takes-to-vo` makes the takes the narration, timed on faster-whisper on this PC
(`docs/content/VOICE-RECORDING.md`). The description says "Narrated by Hagen Simmons, in his own
voice." YouTube's synthetic-media flag is set only when a film shows an AI image. The tick, whoosh,
bed and ambience already on file were made during the paid ElevenLabs subscription and stay licensed
for commercial use; any new sound is Freesound CC0 or Pixabay, with its licence in the manifest.
Nothing in the pipeline calls api.elevenlabs.io or needs an ElevenLabs key.

### 13.2 The real bottleneck for one a day

The picture runs unattended. The voice does not, by the founder's choice: a 30-minute film is
about 30 minutes of reading, roughly an hour at the microphone with retakes. One a day is an hour a
day; three films recorded on a Saturday cover half a week. The pipeline waits on his takes and picks
each film up again the moment they are in.

### 13.3 Time per 40-minute film, unattended

| Step | Rough time |
|---|---|
| Narration (his takes, aligned on faster-whisper) | 5–10 min, after his reading |
| Shot plan | 15–25 min |
| Sourcing (rate-limited) | 45–90 min |
| Pick | 20–40 min |
| Render (four workers) | 60–120 min |
| Assemble, mix, QA, critique | 30–40 min |

About four to five hours. While film N renders, film N+1 sources, so one a day fits overnight.

### 13.4 Running cost

- Narration and sound: nothing. He reads the films himself, and the sound library is on file
  (new clips are Freesound CC0 or Pixabay). The content meter counts image-provider credits and API
  request counts.
- Pexels, Pixabay, the Library of Congress, Smithsonian and Commons cost nothing within their limits.

---

## 14. The style library

A **style** is one named, exact way of putting a sentence on screen. The library exists because an
agent told "make it documentary" produces a stock-footage slideshow, while an agent given a menu of
named styles, each with its recipe and its reasons, produces a series. The `shot-plan` skill picks
one style per shot (§14.2) and writes it to `shots.json`; the renderer reads that style's numbers from
`content/film/styles.json`; the visual trial renders every style once (§12, phase 5); the lock
fingerprints `styles.json`, so the look cannot drift between films.

**Example frames** are in `docs/content/styles/`, one PNG per style at 1920×1080, plus `contact.png`
with all of them on one sheet. *(2026-10-04: the frames and `styles-trial.css` did not arrive with
this file and exist nowhere in the repo. Phase 5 renders them from the built styles, so the founder
sees what was built rather than a promise; until then, each style's written recipe is the
reference.)* They were rendered on 2026-10-04 from the repo's own figures and rate
card on the film stage, with `styles-trial.css` (the reference CSS) for the kinds that do not exist yet.
Each carries an "Example frame" tag that no film ever shows. Grey hatched boxes mark where a sourced,
graded photograph or clip goes: this machine could not reach Pexels or the archives, and a placeholder
is better than a fake.

### 14.1 How to read an entry

- **Seen in**: where the technique comes from, so the agent can recognise it.
- **Job**: what it does in the viewer's head. A style used without its job in mind is decoration.
- **Use when / Never when**: the sentence that calls for it, and the sentences it would harm.
- **Recipe**: the layers from back to front, the motion with its numbers, the timing against the
  narration, the type and the colour.
- **Build**: the kind it renders as (§8), the source tier (§6.3), anything special.
- **Shot**: the fields it adds to a `shots.json` entry.
- **Failure looks like**: what to reject at the pick or in QA.

Timing words: **t0** is the shot's first frame and **t1** its last; **on** is the start time of the
word or `{{key}}` named in the shot's `on` field, from the alignment. **ease-io** is
`cubic-bezier(0.37, 0, 0.63, 1)` (slow in, slow out, for camera moves); **ease-out** is the site's
`--ease-out` (fast start, soft landing, for things arriving). Sizes are pixels at 1920×1080.

### 14.2 The picker

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
| names a real historical person, place or company | `still-push` on archival | `archive-framed` | stock, AI (§6.2) |
| lists several real examples | `archive-stack` | `still-pan` | stock, AI |
| contrasts then and now | `split-then-now` | two `archive-framed` | |
| describes a place or opens a chapter | `footage-establish` | `still-pan` | a generic skyline |
| describes a physical process | `footage-process` | `footage-insert` | |
| names a small physical object | `footage-insert` | `still-reveal` | |
| moves from a detail to the whole | `still-reveal` | `still-pan` | |
| reasons for 10 s or more with no new noun or number | `footage-observe` | `texture` | a frozen frame |
| is abstract, with no concrete noun | `kinetic-thesis` (if it is the chapter's claim) | `texture` | stock clichés (§6.1) |
| is the chapter's central claim | `kinetic-thesis` | | |
| quotes a dated source verbatim | `quote` | `doc-clipping` | paraphrase in quote marks |
| explains how Hubricon counts a dollar | `receipt` | `doc-highlight` (the terms) | |
| follows a big reveal | `breath` | | |
| resolves something set up earlier | `callback` | | |

### 14.3 World styles

#### W1 · The slow push · `still-push`

*Example: `moves.png`, first panel.*

- **Seen in:** Ken Burns's films, which gave the move its name; Vox ("hero images slowly push in");
  every history channel.
- **Job:** a photograph becomes a moment you step into, and the eye goes to one subject without an
  arrow pointing at it.
- **Use when:** the sentence is about a specific person, place or thing that an archival photograph
  shows (§6.2), or an AI texture sits under an abstract line (W12 borrows the move).
  **Never when:** the image has no single subject (use W2), or it is under 2,000 px on its long edge.
- **Recipe:** one layer, the graded image (§3.2), covering the frame. Scale 1.00 at t0 to 1.07 at t1,
  `transform-origin` at the picked `focus`, ease-io. A shot over 12 s ends at 1.08, never more.
  Archival: the credit, bottom right, for the whole shot; the place and date lower third from t0+0.5
  to t0+4.5, arriving with the `.in` entrance and leaving on a 400 ms fade.
- **Build:** film-stage `still`; a CSS animation from `scale(1)` to `scale(1.07)` lasting exactly the
  shot, every frame captured (§8.3). Sources: Library of Congress, Smithsonian, Commons, or the image
  provider for a texture.
- **Shot:** `"style": "still-push", "motion": "push", "focus": [0.62, 0.41]`
- **Failure looks like:** the push moving in visible steps (a small source, or ffmpeg's `zoompan`
  without subpixel motion: use the Chrome stage); the push heading into empty sky (wrong focus); two
  pushes back to back (§3.4).

#### W2 · The survey pan · `still-pan`

*Example: `moves.png`, second panel.*

- **Seen in:** history documentaries moving across wide paintings, panoramas and crowd photographs.
- **Job:** "there is a great deal of this": breadth, scale, a row of things, while the voice lists.
- **Use when:** the sentence enumerates or describes scale ("aisle after aisle"), or the image is
  wider than 16:9 (a panorama, an aerial). **Never when:** the image has one subject (W1).
- **Recipe:** the image at a fixed 1.08; it travels sideways by at most 5% of the frame's width per
  shot, or, for a panorama wider than 2:1, up to a quarter of the image's own width. Direction follows
  the sentence: left to right for goods moving, for time passing. Ease-io. The seven-second rule from
  cinematography: anything crossing the frame takes at least 7 s, so never faster than 270 px a second.
- **Build:** film-stage `still` with `motion` `pan-left` or `pan-right`; vertical pans only for tall
  images.
- **Shot:** `"style": "still-pan", "motion": "pan-right", "focus": [0.3, 0.5]`
- **Failure looks like:** judder from a pan that is too fast; a pan across a single subject.

#### W3 · The detail pull-back · `still-reveal`

*Example: `moves.png`, third panel.*

- **Job:** starts on the detail the voice names, then shows its context: one price tag, then the shelf
  of ten thousand. It is the lesson in miniature: the small thing belongs to a big system.
- **Use when:** the sentence moves from one to many, or from part to whole.
  **Never when:** the detail is unreadable at 1.35 (the source must be at least 2,600 px wide).
- **Recipe:** hold at 1.35 on the `focus` from t0 until **on** (the word that names the whole), then
  pull to 1.00 over the next 70% of the remaining time on ease-out, then drift 1.00 to 1.01.
- **Build:** film-stage `still`, `motion` `reveal`, with `on`.
- **Shot:** `"style": "still-reveal", "on": "shelf", "focus": [0.71, 0.55]`
- **Failure looks like:** the pull starting at t0, so the reveal arrives before its word.

#### W4 · The depth push (2.5D) · `still-depth`

*Example: `moves.png`, fourth panel. Built after the trial (§12): it needs segmentation.*

- **Seen in:** MagnatesMedia ("3D camera motion and parallax"); history channels' "2.5D" photographs.
- **Job:** gives a flat archival photograph a sense of space. The strongest single signal that a still
  was handled with care, and the easiest one to overdo.
- **Use when:** an archival photograph with one clear subject in front of a background, at a hinge
  moment (a chapter's first archival image). At most one per chapter.
  **Never when:** faces (unless §13.1 allows portraits), crowds, text, busy scenes.
- **Recipe:** two layers. Cut the subject out with a matting model (rembg or SAM) with a 2 px feathered
  edge; fill the hole it leaves in the background (OpenCV `inpaint` for small holes, a learned
  inpainter for large ones). Background 1.00 to 1.04, subject 1.00 to 1.09 around the same focus,
  ease-io. The subject never moves more than 2.5% of the frame's width relative to the background.
- **Build:** film-stage `still` with `layers` in the asset; the pick rejects any cut-out with a halo.
- **Shot:** `"style": "still-depth", "params": {"layers": ["bg.png", "subject.png"]}`
- **Failure looks like:** halos, smeared background where the subject stood, or the subject sliding
  like a sticker. Layers moving at nearly the same speed look flat, which is why the gap starts at
  1.04 against 1.09. On any doubt, fall back to W1.

#### W5 · The archive on the desk · `archive-framed`

*Example: `archive-framed.png`.*

- **Seen in:** documentaries that hold a photograph up as an object. Ours is the clean version.
- **Job:** the archival image appears inside the paper room, framed and credited, so it reads as
  evidence held up rather than mood. It also softens the cut between the two rooms.
- **Use when:** the photograph supports a claim ("this is what a chain store looked like then"), or
  next to paper shots in a history run. Archival film at 4:3 plays here, inside the frame.
  **Never when:** the image is stock or AI.
- **Recipe:** paper ground; the image in a box up to 1180×760 at its own aspect (archival is never
  cropped to fill), centred, with a 1 px `--rule-2` border; 20 px beneath it, the place and date on the
  left and the institution on the right, Inter 400 at 28 px in ink-3, from provenance; the mono grade;
  the whole stage drifting 1.00 to 1.03.
- **Build:** a paper kind `archive`; archival sources only.
- **Shot:** `"style": "archive-framed", "room": "paper", "kind": "archive"`
- **Failure looks like:** archival cropped to fill the box; a credit typed by hand.

#### W6 · The photo stack · `archive-stack`

*Example: `archive-stack.png`.*

- **Seen in:** Johnny Harris's still-photo reveals with a camera click; a photographer's contact sheet.
- **Job:** "there were many of these", with evidence: several real photographs, each landing as named.
- **Use when:** the sentence lists or counts real examples, three to five.
  **Never when:** the images are stock or AI (a stack claims a set of real things).
- **Recipe:** paper ground; three to five photographs in one row (or two by two), 32 px gutters, mono,
  1 px `--rule-2` borders, equal heights. Each arrives with the `.in` rise (20 px over 700 ms) at its
  word, or every 1.6 to 2.4 s if the voice does not name them, with the soft tick from `audio.py` as it
  lands: our only camera click. When the voice settles on one, the others fade to 40% over 400 ms and
  that one gains a 2 px ink outline, 8 px out. The stage pushes 1.00 to 1.04.
- **Build:** a paper kind `stack`; `asset` is a list.
- **Shot:** `"style": "archive-stack", "on": "Woolworth", "params": {"focus_index": 2}`
- **Failure looks like:** photographs from different eras that clash (the mono grade and one grain fix
  most); more than five.

#### W7 · The establishing shot · `footage-establish`

- **Seen in:** every documentary; ColdFusion's footage-led openings.
- **Job:** tells the viewer where we are before anything is explained. A breath of space.
- **Use when:** a chapter opens, the story moves to a new place or trade, or after a chapter card.
  **Never when:** the only footage is a generic skyline (§6.1).
- **Recipe:** one wide shot, 6 to 10 s, real time, static or a slow push or drone glide; ambience at
  −40 dB fading in over 0.5 s; nothing over stock footage.
- **Build:** `footage`; queries from the place's concrete nouns ("container port cranes daylight wide").
- **Shot:** `"style": "footage-establish", "query": ["container port gantry cranes daylight wide"]`
- **Failure looks like:** handheld shake; a city that could be anywhere; night.

#### W8 · The process sequence · `footage-process`

- **Seen in:** industrial documentaries; the footage runs in ColdFusion and MagnatesMedia.
- **Job:** shows how something physically happens in three steps (where, what, the moment), so the
  mechanism in the voice feels real.
- **Use when:** the narration describes a physical process: goods arriving, stored, picked, packed,
  shipped.
- **Recipe:** three shots of the same process, 3 to 5 s each, about 10 to 13 s across one or two
  sentences: wide, then medium, then detail. Cut on motion: each `in` point sits mid-movement, so every
  cut lands while something moves. Screen direction stays the same across the three. One ambience runs
  under all three, crossfaded.
- **Build:** three entries sharing `params.group`; the pick chooses them together, for matching light
  and colour.
- **Shot:** `"style": "footage-process", "params": {"group": "pack", "step": "wide"}` (then `medium`,
  `detail`)
- **Failure looks like:** three warehouses that obviously differ; motion that flips direction.

#### W9 · The observational hold · `footage-observe`

- **Seen in:** slow cinema; the founder's description of Nic Munoz: "the same thing on the screen for
  like ten seconds, and that's okay, because you're listening".
- **Job:** lets the viewer listen. The picture sets a mood and gets out of the way while the voice
  carries the reasoning.
- **Use when:** the narration reasons for 10 to 14 s with no new number and no new noun, often after a
  dense run of paper shots. At most one per 90 s.
- **Recipe:** one locked-off shot, 10 to 14 s, with gentle motion inside the frame (a conveyor running,
  rain on a loading dock, trucks passing); real time; ambience up to −36 dB; nothing overlaid.
- **Build:** `footage`, preferring tripod shots (the pick checks for a still camera).
- **Shot:** `"style": "footage-observe", "query": ["loading dock rain trucks static"]`
- **Failure looks like:** a shot with no motion in it at all (QA's `freezedetect` fails it); a number
  spoken under it (numbers belong on paper).

#### W10 · The detail insert · `footage-insert`

- **Job:** punctuates one noun with a close-up (a tape gun, a postal scale, a label printer, a barcode
  scanner), so the viewer sees the exact object as it is named.
- **Use when:** a sentence names a small physical object, or between paper shots to keep the world
  present. At most two in a row. With the shots of a process sequence (W8), the only footage under
  6 s after the first minute.
- **Recipe:** a close-up of 3 to 5 s, real time or 0.8× from a 60 fps source, cut in on **on**.
- **Shot:** `"style": "footage-insert", "on": "scale", "query": ["postal scale parcel close up"]`
- **Failure looks like:** an insert that does not show the object named (§6.1).

#### W11 · Then and now · `split-then-now`

*Example: `split-then-now.png`.*

- **Seen in:** history documentaries' comparison frames.
- **Job:** makes change over time visible in one glance: what it was, what it is.
- **Use when:** a sentence contrasts past and present (the mail-order catalogue then, the marketplace
  now). The left image must be archival with a date in its provenance.
- **Recipe:** paper ground; two panels of the same size (880×620) with a 40 px gutter and 1 px
  `--rule-2` borders; above each, a label in Inter 600 at 26 px, tracked, ink-3: the year from
  provenance on the left, "Today" on the right. The left is archival in mono; the right is present-day
  footage in the world grade, playing. The left lands at t0, the right at **on** ("today", "now") or
  at t0+1.2 s.
- **Build:** a paper kind `split` with two assets.
- **Shot:** `"style": "split-then-now", "on": "today"`
- **Failure looks like:** a "then" with no dated provenance; panels of different sizes.

#### W12 · The texture · `texture`

- **Job:** holds an abstract idea (time passing, uncertainty, cost piling up) with atmosphere, when
  there is no concrete noun and one more paper shot would be one too many.
- **Use when:** as the picker says, and inside the 8% ceiling (§5). Never two in a row.
  **Never when:** the sentence states a fact about a specific thing.
- **Recipe:** an AI still life made with the locked preamble (§6.5), the world grade, a drift of 1.00
  to 1.03 or W1's push, the "Illustration" label bottom right; 6 to 10 s.
- **Build:** film-stage `texture`; the image provider.
- **Shot:** `"style": "texture", "overlay": {"illustration": true}`
- **Failure looks like:** anything that could pass for a real place, product or person; text or a logo
  generated into the image.

### 14.4 Paper styles

#### P1 · The document highlight · `doc-highlight`

*Example: `doc-highlight.png`.*

- **Seen in:** Vox (the highlighter drawn behind or across text; "headlines get a red underline swipe",
  where ours is blue or ink);
  Johnny Harris's documents; every investigative explainer.
- **Job:** proves the claim with the source itself: here is the line, in its own words, and here is
  the number that matters. Hubricon's "every move gets a receipt" as a shot.
- **Use when:** the sentence cites a rule, a fee, a schedule, a filing or a published statement.
  **Never when:** the document would be invented or reconstructed and passed off as real, or would
  imitate Amazon's interface.
- **Recipe:** paper; the page (a real page image with provenance, or a typeset rendering of engine
  data) inside a 1 px `--rule-2` border with a 4 px radius. From t0 the whole page shows at 0.92; from
  t0+1.2 to t0+3.2 the stage pushes toward the target line (to about 1.15, origin on the line),
  ease-io. At **on** the mark draws left to right over 400 ms: a 3 px blue underline, with the text
  turning blue, if it is money; a 2 px ink underline otherwise. From on+0.2 every other line fades to
  45% over 400 ms. Then hold, drifting. The source line underneath (Inter 400, 26 to 28 px, ink-3,
  from provenance) is always visible.
- **Build:** a paper kind `document`; typeset from `ratecard.json` or engine output, or a page image
  from the Library of Congress or EDGAR.
- **Shot:** `"style": "doc-highlight", "on": "{{aged_rate_after}}", "params": {"line": 4}`
- **Failure looks like:** the mark landing before the words; more than about eight lines on screen
  (crop to the paragraph); a typeset page dressed up to look like Amazon's.

#### P2 · The clipping · `doc-clipping`

- **Seen in:** MagnatesMedia's headlines; ColdFusion; history channels.
- **Job:** "this was public, it was news, on this date": the outside world confirming the story.
- **Use when:** a sentence refers to a dated public event. Sources: the Library of Congress's
  digitized newspapers, or a filing.
- **Recipe:** paper; the headline or one paragraph cropped from a page scan, mono, at most 1,400 px
  wide, inside a 1 px border; beneath it, the paper's name and the date from provenance; a push of 1.00
  to 1.04; at **on**, a 2 px ink underline under the key phrase. Never rotated, never torn edges, never
  a red marker.
- **Build:** a paper kind `document` with `params.clipping: true`.
- **Shot:** `"style": "doc-clipping", "on": "catalogue"`
- **Failure looks like:** a scan nobody can read (the pick rejects it: if the agent cannot read it,
  neither can the viewer); a screenshot of a modern article whose site forbids it.

#### P3 · The table scan · `table-scan`

*Example: `table-scan.png`, drawn from `ratecard.json`'s 2026 non-peak large-standard rows.*

- **Job:** finds the one row that matters inside a published table, so the viewer sees the whole system
  and exactly where this listing sits in it.
- **Use when:** the sentence locates something in a schedule or list ("this listing pays the third
  row").
- **Recipe:** paper; a 72 px heading; a typeset table of at most 10 rows on screen, Inter 40 px with
  tabular figures, right-aligned numbers, a header row in 24 px tracked ink-3 over a 2 px ink rule, row
  hairlines in `--rule`. At **on** a `--paper-2` band slides to the row (500 ms, ease-out) and the row
  turns ink 600; 200 ms later the money cell turns blue. Longer tables pan down at no more than 120 px
  a second to the row before it is marked. The source line beneath.
- **Build:** a paper kind `table`, typeset from data.
- **Shot:** `"style": "table-scan", "on": "third", "params": {"row": 3, "cell": 2}`
- **Failure looks like:** more than one row marked; numbers not right-aligned.

#### P4 · The receipt · `receipt`

- **Job:** Hubricon's own method as an object: the move, how we know, called before, measured after.
  The brand's icon as a shot.
- **Use when:** the narration explains how the guarantee or the Record counts a dollar.
  **Never when:** it could read as a real client's result. Only demo data labelled "demo data", or a
  client's consented Record (none exists yet).
- **Recipe:** the site's `.rcpt` piece at film size; each line lands with its words; money in blue;
  the "demo data" label always on.
- **Build:** a paper kind `receipt`, filled from facts.
- **Shot:** `"style": "receipt", "params": {"demo": true}`

#### P5 · The number landing · `number-land`

*Example: `number-land.png` (the existing `number` scene).*

- **Job:** puts one figure in the viewer's memory. One number per screen.
- **Use when:** the sentence's point is one figure or one range.
- **Recipe:** the existing `number` scene: 168 px Inter 600 with proportional figures, blue for money
  and ink for anything else, the "estimate" tag when it is one. It appears at the instant its
  `{{key}}` is spoken, never before; the sub-line follows 600 ms later; it holds at least 3 s; then it
  drifts.
- **Shot:** `"style": "number-land", "on": "{{leak_p10}}"`
- **Failure looks like:** the number on screen before it is said; two numbers on one screen (use P6).

#### P6 · The comparison pair · `number-pair`

*Example: `number-pair.png`, from the store study (`data/store-study.json` on `main`).*

- **Job:** makes a comparison instant: called against happened, before against after. The second
  number landing is the payoff.
- **Use when:** two figures are compared in one or two sentences.
- **Recipe:** the question in 44 px Inter 600 ink; two columns, each a label (26 px, tracked, ink-3)
  over a figure (150 px, 600); the first lands at its word, the second at its own; under them, one line
  in 40 px ink-2 saying what the gap means; blue only if they are money.
- **Shot:** `"style": "number-pair", "on": "{{measured}}"`
- **Failure looks like:** both figures on screen before the second is said.

#### P7 · The count · `unit-grid`

*Example: `unit-grid.png`: one dot per brand modeled, the ones that showed nothing in ink.*

- **Seen in:** data journalism's unit charts.
- **Job:** makes a share felt as a quantity: "1,473 of 1,856" becomes a field of dots, most of them
  filled. It is also the honesty line made visible.
- **Use when:** a share of a countable set (brands, SKUs, months), up to about 2,000 units; beyond
  that, one dot per ten, and the caption says so.
- **Recipe:** a heading stating the count; a grid of 14 px dots with 5 px gaps; all in `--rule-2` at
  t0; at **on** the counted dots fill with ink in reading order over 1.5 s; a caption saying what one
  dot is and when it was measured. Blue only if the dots are dollars.
- **Shot:** `"style": "unit-grid", "on": "{{brands_silent}}"`
- **Failure looks like:** dots under 10 px, unreadable on a phone.

#### P8 · The progressive build · `chart-build`

*Example: `chart-build.png` (the aging cliff, the site's own chart).*

- **Seen in:** Vox ("motion to carry information", every element answering the voice); the bible §3.
- **Job:** the chart arrives in the order the argument does (the frame, the data, the point), so the
  viewer reads it at the speed of the voice.
- **Use when:** a mechanism or a relationship over a variable (fees by weight, cost by age, profit by
  price).
- **Recipe:** axes over 0.9 s, data over 2.2 s, annotation over 0.55 s (the values in `STYLE.chart`),
  the annotation landing at **on**; a second annotation at its own word when the shot runs long; then
  the drift. Up to 30 s, with something new at least every 8 s. Manim charts and the house charts keep
  the same timing and the same frame (§8.4).
- **Shot:** `"style": "chart-build", "chart": {"scene": "aging"}, "on": "{{aged_rate_after}}"`
- **Failure looks like:** a cut to a finished chart; an annotation before its words.

#### P9 · The counterfactual · `counterfactual`

*Example: `counterfactual.png` (the staircase).*

- **Job:** Hubricon's signature argument as one picture: what is (the solid dot), the same thing one
  step the other way (the hollow dot), and the gap between them in blue, which is the finding. It is
  the line that removes the shame: a cliff is only visible as a counterfactual.
- **Use when:** the sentence says what one small change would have cost or saved.
- **Recipe:** the house staircase, or any step chart: the solid dot first; the hollow dot at the words
  for "the other way"; the blue riser and its label at the money `{{key}}`; hold at least 4 s.
- **Shot:** `"style": "counterfactual", "chart": {"scene": "staircase"}, "on": "{{step_np}}"`
- **Failure looks like:** the riser drawn before the money is said. (The current staircase still
  carries a two-line legend; label the lines directly, per PREMIUM-STANDARD.)

#### P10 · The range · `range-band`

*Example: `range-band.png`.*

- **Job:** honesty made visible: a band that openly includes the bad end, never one triumphant number.
- **Use when:** a forecast, a simulation, any estimate.
- **Recipe:** the house Monte Carlo: paths draw over 2 s, the band fills over 0.4 s, the P90, median
  and P10 labels land at their words; the share of losing months is stated.
- **Shot:** `"style": "range-band", "chart": {"scene": "montecarlo"}, "on": "{{mc_p10}}"`
- **Failure looks like:** a single forecast line with no band.

#### P11 · The timeline · `timeline`

*Example: `timeline.png`, Amazon's 2026 fee calendar from the rate card's dates.*

- **Seen in:** history documentaries; MagnatesMedia ("headlines, timelines").
- **Job:** puts events in order and at their distance; shows that things are dated, and that some are
  coming.
- **Use when:** two or more dated events are mentioned; most history chapters.
- **Recipe:** one 2 px ink axis; each event a 2 px by 50 px tick, its date above (34 px, 600, ink) and a
  label of at most four words below (34 px, ink-2), on two levels when events sit close (the example
  needed it); each event lands at its word; a span wider than the frame tracks along at no more than
  120 px a second; a "today" marker in ink-3 where it matters; money in a label is blue; every date from
  facts or provenance.
- **Build:** a paper kind `timeline`, from facts.
- **Shot:** `"style": "timeline", "params": {"events": ["fees_new", "surcharge", "peak_on", "peak_off"]}`
- **Failure looks like:** overlapping labels; events appearing before they are said.

#### P12 · The formula build · `formula-build`

*Example: `formula-build.png`.*

- **Job:** shows that the arithmetic is simple and checkable: the terms in words, arriving as they are
  said.
- **Use when:** the narration defines a quantity by its parts.
- **Recipe:** a `--paper-2` panel with a 16 px radius; terms in Inter 600 at 60 px, operators in ink-3
  at 400; each term lands at its word; the result term blue if it is money; a 44 px ink-2 caption.
  At most five terms.
- **Shot:** `"style": "formula-build", "on": "landed cost"`
- **Failure looks like:** symbols where a founder expects words; a sixth term.

#### P13 · The thesis line · `kinetic-thesis`

*Example: `kinetic-thesis.png` (the existing `kinetic` scene).*

- **Job:** states the chapter's claim in the voice's own words, large, once.
- **Use when:** the chapter's central sentence. At most one every three minutes.
- **Recipe:** the existing `kinetic` scene: twelve words at most, two lines at most, 104 px; the first
  line at the sentence's first word, the second line at its own first word. The words on screen are
  exactly the words spoken.
- **Shot:** `"style": "kinetic-thesis", "on": null`
- **Failure looks like:** wording that differs from the narration (the viewer then reads one sentence
  and hears another); a thesis line used as filler.

#### P14 · The quote · `quote`

*Example: `quote.png` (a layout: the brackets mark what the source fills).*

- **Job:** lets a primary source speak for itself.
- **Use when:** the script quotes a dated source word for word.
- **Recipe:** Inter 600 at 72 px in ink, lines of at most 24 characters; the attribution in 36 px ink-3:
  the name, the year, and the source the words were printed in; it appears as the narration begins the
  quote and holds until one second after it ends.
- **Shot:** `"style": "quote", "params": {"source": "provenance id"}`
- **Failure looks like:** a paraphrase inside quote marks; a quote without its printed source.

#### P15 · The chapter card · `chapter`

*Example: `chapter.png`.*

- **Recipe:** as §8.1: a 120 px ink hairline, the title at 96 px, 2.5 s, a whoosh and a bed swell, no
  numbering.

### 14.5 Connective styles

#### C1 · The bridge · `match-bridge`

- **Seen in:** the match cut, film's oldest trick; Johnny Harris's match cuts on text.
- **Job:** carries the viewer from the world to the paper on a shape they are already looking at: a
  staircase in a building becomes Amazon's fee staircase; rows of shelving become a table's rows; a road
  becomes the timeline's axis.
- **Use when:** the shape genuinely matches. At most one per chapter, and optional.
- **Recipe:** the world shot's last frame and the paper shot's first share the shape at the same place
  and angle on screen, within 5% of the frame's width; a hard cut on the word that names the idea.
- **Build:** the shot plan marks `"params": {"bridge": {"to": "s041", "shape": "steps"}}`; the pick
  chooses footage by that shape; the renderer offsets and scales the paper scene's opening to align.
- **Failure looks like:** a forced bridge. Shapes that nearly match read as an accident; when in doubt,
  leave it out.

#### C2 · The breath · `breath`

- **Job:** a pause after a big reveal, so it lands; and the space where the music lives (bible §4).
- **Recipe:** 1.5 to 2 s with no narration, taken from the script's own paragraph breaks; a moving world
  shot (W9) or the paper shot still drifting; the bed comes up 6 dB. At most one every two minutes.
- **Shot:** `"style": "breath"`

#### C3 · The callback · `callback`

- **Job:** an earlier picture returns with new meaning: the chart from minute four comes back at minute
  eighteen with the answer marked. A long film needs this to feel built rather than strung together.
- **Use when:** a chapter's end resolves something set up earlier.
- **Recipe:** the earlier shot's exact scene and framing, with one new annotation landing at its word.
- **Shot:** `"style": "callback", "params": {"callback": "s042"}, "on": "{{leak_p90}}"`

### 14.6 Sequences: styles in combination

A sequence is a run of styles that works as a unit, the way a paragraph does. They are patterns to
reach for, not quotas; the times are typical.

1. **The evidence run** (explainer, about 50 s): `footage-establish` 8 s → `footage-process` 12 s →
   `doc-highlight` 10 s → `chart-build` 14 s → `number-land` 6 s. Place, mechanism, source, model,
   number: the viewer believes the number because they watched it being earned.
2. **The history open** (history, about 70 s): `still-push` on an archival photograph 10 s →
   `doc-clipping` 8 s → `archive-stack` 12 s → `timeline` 16 s → `split-then-now` 10 s →
   `kinetic-thesis` 7 s. A person and a date, proof it was public, how many, in what order, what it
   became, and why it matters.
3. **The counterfactual reveal** (about 40 s): `footage-insert` of the product type 4 s → `table-scan`
   10 s → `counterfactual` 14 s → `number-pair` 8 s → `breath` 2 s. The thing, where it sits in the
   rules, what one step costs, the two numbers, and a pause for it to land.
4. **The honest limit** (about 35 s): `range-band` 14 s → `unit-grid` 10 s → `footage-observe` 12 s.
   What we don't know, how often there is nothing to find, and room to think about it.
5. **The chapter turn** (about 14 s): `breath` 2 s → `chapter` 2.5 s → `footage-establish` 8 s.
6. **The return** (a film's end, about 25 s): `callback` 12 s → `kinetic-thesis` 6 s → the existing
   `end` card 6 s.

### 14.7 Styles we do not use, and why

Each is good work somewhere else. None fits an instrument that has to be trusted with money.

- **Red-string evidence boards, torn-paper collage, halftone cut-outs** (the Vox collage look): red,
  and they read as a scrapbook or a conspiracy, not a measurement.
- **Film burns, light leaks, dust overlays** (Johnny Harris's texture layers): decoration. Our one
  grain does the unifying.
- **The 12 fps "stutter" in animation** (Vox): a hand-made signature that is theirs. Ours is smooth
  and eased.
- **The dark cinematic grade** (MagnatesMedia): see §3.
- **3D fly-throughs with blur transitions, whip pans, zoom punches, speed ramps, shake, glitch.**
- **Sepia, vignettes, colourized archival photographs.**
- **Google Earth fly-overs** (their licence terms) and spinning globes.
- **Word-by-word captions in the middle of the frame; emoji, memes, sound-effect gags.**
- **Generated video, talking avatars, synthetic presenters** (§6.5, §6.6).
- **The stock clichés** (§6.1).

### 14.8 What the library adds to the pipeline

- `content/film/styles.json`: every number in this section (scales, durations, easings, opacities,
  sizes, levels), one object per style id. `film.css`, `scenes.mjs` and `footage.py` read it; nothing
  hard-codes a style's numbers; `lock.mjs` fingerprints it.
- `shots.json` gains `style`, `on` and `params` (§7.3).
- `shots-validate` checks that every `style` is allowed for its room and kind, that every `on` occurs in
  `says` and resolves to a time, and the **variety rules** for a film: at least 10 different styles in
  any 20 minutes; no style over 15% of the runtime except `chart-build` (25%); never the same style
  three shots running; `texture` within 8%; one `kinetic-thesis` at most every three minutes; one
  `footage-observe` at most every 90 s; one `breath` at most every two minutes; one `match-bridge` and
  one `still-depth` at most per chapter.
  *(2026-10-04: a process sequence, W8, is one shot in three parts and counts once toward "never the
  same style three shots running"; the spec's own W8 is three `footage-process` entries in a row.)*
- The `visual-pick` skill reads each style's "Failure looks like" lines as its rejection list.
- The `critique render` skill checks each shot on the contact sheet against its style's recipe.
- `docs/content/styles/` holds the example frames, `contact.png` and `styles-trial.css`.


---

## 15. Sources

- Pexels API documentation (limits, attribution, the video search): https://www.pexels.com/api/documentation/
- Pixabay API documentation (limits, 24-hour caching, hotlinking, the videos endpoint): https://pixabay.com/api/docs/
- ElevenLabs, create speech with timing (character alignment, `previous_text`/`next_text`): https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- Library of Congress, rights and restrictions: https://www.loc.gov/research-centers/prints-and-photographs/researcher-resources/copyright-and-rights-and-restrictions-information/
- Smithsonian Open Access API (api.data.gov key): https://github.com/Smithsonian/smithsonian-openaccess
- YouTube's inauthentic-content update, July 15, 2025: https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/
- "No Longer Just Wallpaper", International Documentary Association, on archival footage: https://www.documentary.org/feature/no-longer-just-wallpaper-archival-footage-can-inform-and-shape-your-films-story
- Nic Munoz, about: https://www.nicmunoz.com/about
- Faceless business case-study channels (Modern MBA, MagnatesMedia, ColdFusion): https://www.overseeros.com/blog/top-faceless-business-case-study-youtube-channels
- How Vox-style edits are built (the highlighter, motion carrying information, the 12 fps stutter): https://earnedits.com/how-vox-style-edits-are-built/
- How to make a Vox-style explainer (one graphic idea and one number per scene, the underline swipe, the slow push): https://korpi.ai/blog/how-to-make-vox-style-explainer-videos
- Three Johnny Harris-style documentary tips (photo reveals with a camera click, match cuts on text, textures): https://motionarray.com/learn/premiere-pro/edit-documentary-in-premiere-pro/
- The 2.5D photo effect (segmentation, background fill, layers at different speeds): https://analoghq.ai/blog/en/the-2-5d-effect-how-to-animate-photos-and-create-a-parallax-shift/
- Faceless finance documentary channels (MagnatesMedia's headlines and timelines, ColdFusion's footage-led pacing): https://faceless.my/youtube/faceless-finance-documentary-channels/
- A MagnatesMedia-style editing brief (parallax, kinetic type, archival, a dark grade): https://www.fiverr.com/bimdasboy420/magnates-media-style-documentary-youtube-video-editing
- The example frames in `docs/content/styles/`, rendered on 2026-10-04 from `ratecard.json`, `data/case-study.json`, `data/montecarlo.json` and the store study (`data/store-study.json` on `main`).
- The branch itself: `content/film/*`, `content/src/hubricon_content/*`, `docs/content/hubricon-video-production-bible.md`, `docs/content/PREMIUM-STANDARD.md`, `content/STATE.md`, at `9be90dc`.
