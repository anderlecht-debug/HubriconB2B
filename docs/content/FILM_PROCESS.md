# How Hubricon makes its films: the process as built (2026-10-12)

This describes how a Hubricon video gets made, from script to YouTube, exactly as the system works today.
It is written so another model can audit it for gaps, weak links and wrong assumptions. Where something
is built but not yet proven on a real film, or not built at all, it says so. The questions for an
auditor are at the end.

---

## 0. What we make, and the constraints

- **What:** long educational films for YouTube (tier D, 20–50 minutes), documentary-style, in the
  founder's own recorded voice. They teach e-commerce operators (Amazon and Shopify sellers) a method
  they can use: pricing, inventory, ads, measurement. A historical story may frame a film, but the film
  teaches, and is judged by what a seller learns and does. The first three films (G01–G03, "Greats of
  Commerce") were capability proofs, history-first; future films are education-first.
- **Why:** YouTube is the top of the funnel. Each film points to the free courses at hubricon.com/learn
  and, softly, to booking a call. Links carry a `?src=yt-<id>` code, so booked calls are attributed to
  the film that produced them.
- **Target volume:** 7 films a week, without the AI cost eating the founder's subscription. AI is used
  only where judgment is needed; everything else is code.
- **Hardware:** one PC: Ryzen 7 2700 (16 threads), 15 GB RAM plus 20 GB swap, an RTX 2060 6 GB (NVENC),
  Arch Linux. Everything runs locally; nothing is rendered in the cloud.
- **Honesty rules (non-negotiable):**
  - Nothing untrue on screen.
  - Every figure the voice says comes from a sourced fact.
  - Demo figures are labelled demo data.
  - Pictures are licensed and credited.
  - AI imagery is labelled and declared.
  - A placeholder voice never publishes.

---

## 1. The pipeline at a glance

| # | Stage | Done by | AI tokens |
|---|---|---|---|
| 1 | Script | the founder, drafting outside this machine to a fixed format | his own drafting tool |
| 2 | Intake: check, file, queue | code (`script-in`) | 0 |
| 3 | Voice: his takes at a teleprompter | the founder; code measures pace | 0 |
| 4 | Narration and timing | code (faster-whisper alignment) | 0 |
| 5 | Shot plan: skeleton | code | 0 |
| 6 | Shot plan: decisions | one model reply (Sonnet), capped | ~163k weighted, measured |
| 7 | Plan fill, autofix, validation | code; a second capped reply only if problems remain | 0, rarely a reply |
| 8 | Sourcing pictures and footage | code (public APIs) | 0 |
| 9 | Picking pictures | code (rank-based) | 0 |
| 10 | Rendering one clip per shot | code (headless Chromium, ffmpeg, Manim) | 0 |
| 11 | Sound design and mix | code | 0 |
| 12 | Draft, review sheets, film-qa | code | 0 |
| 13 | Founder watches the draft (gate) | the founder | 0 |
| 14 | Master, captions, thumbnail, description, worksheet, shorts | code | 0 |
| 15 | Final approval (gate), then upload | the founder, then code | 0 |
| 16 | Retention analysis after publishing | code (YouTube Analytics) | 0 |

From the founder's handover, the line runs unattended. A systemd user timer runs a "tick" every
30 minutes. The founder's own steps are: write the script, record the takes, watch the draft, approve
the final.

---

## 2. Each stage in detail

### 2.1 Script (the founder, elsewhere)

The founder drafts scripts outside this machine (for example in a claude.ai project), so drafting
costs nothing here. They follow a written kit (`SCRIPT_KIT.md`) and a generated reference of the names a
script may use (`SCRIPT_REFERENCE.md`: the ~30 visual style names, the chart scenes, and the 223
demo-data figure keys).

**The format:**

- **Header fields:** `SERIES` (optional), `TITLE`, `SHORT`/`SLUG` (optional), `THUMBNAIL`, `PILLAR`, `TIER`,
  `AWARENESS STAGE`, `CTA`, `SPIKY CLAIM`, `MISCONCEPTION`, `RUNTIME`.
- **Hooks:** three hooks, one to be picked.
- **Beats:** `SCRIPT` then timed beats: `[m:ss] NAME`, with `VO:` (narration), `VISUAL:` (a brief naming
  at least one library style), `DATA SOURCE:` (for any chart), `CLIP: yes|no`, `CTA:` (once), `KEEP:` and
  `TRY:`.
- **Chapters:** `[m:ss] CHAPTER — NAME` with `VO: Name.` and `VISUAL: chapter`.
- **Tail:** `RE-HOOK AUDIT:` (timestamps of every re-hook) and `DERIVED ASSETS:`.
- **FACTS block:** at the end, one line per figure: `key | value | label | source`.

**Rules the intake enforces by code** (a refused script gets every problem in one list):

*Figures and sources*
- Every number, currency amount, percentage or dated figure in VO, hooks, title, thumbnail and CTA is a
  `{{key}}` placeholder.
- Every key has a FACTS line with a source. A figure with no source is refused.
- Demo-data keys need no FACTS line; a beat showing one says `DATA SOURCE: demo: …`.

*Structure and length*
- Tier D runs 3,000–7,500 spoken words.
- Three hooks, each under 45 words, with a `{{key}}` in the first sentence.
- At least three `CLIP: yes` beats.
- Exactly one CTA, which points to /learn.
- Re-hooks no more than 40 s apart, per the audit line.
- The banned-phrase list holds: "just", "secret", "hack", "imagine", "let's dive in" and others.
- Every VISUAL names a library style.
- A chart needs a DATA SOURCE saying demo, public-data case study, or published.

*Learning rules (tier D)*
- Chapters run 1.5–6 minutes (225–900 words).
- Every chapter asks the viewer a question before answering it.
- Every chapter ends on one `KEEP:` line: 12 words at most, spoken verbatim in that beat's VO.
- At least one `TRY: yes` beat gives this week's step.
- The last chapter brings back at least 2 of the film's earlier figures.

**What the intake does when clean:** it writes the film's folder (`script.md`, `history.json` from the
FACTS block) and builds `facts.json`: the engine's demo figures plus the film's sourced figures. It then
adds the film to the queue as approved; handing it over is the founder's approval. The film is marked
blocked until his takes exist.

**Ways to hand a script over:**
1. Paste it into any Claude Code chat on the machine. A global instruction tells every session to save
   it and run the intake, with no critique and no rewrite.
2. Drop the file in `~/Hubricon/scripts-inbox/`. The runner checks it every tick: clean scripts go to
   `taken/`, refused ones to `refused/` with their problems beside them.
3. Run `hubricon-content script-in <file>` directly.

**Not verified by code:** the sources themselves. URLs are not fetched; a quote is not checked against
its source; the drafter is trusted for factual accuracy.

### 2.2 The runner (unattended)

A systemd user timer runs `scripts/content-tick.sh` every 30 minutes, in its own git worktree on the
`content` branch. In order, it:

1. **Takes a lock** (one tick at a time) and honours a STOP file.
2. **Reads the scripts inbox** (code).
3. **Checks the queue.** If idle (everything blocked on the founder or parked at a gate), it refreshes
   the status files and exits. No AI session starts.
4. **Runs a due film as code.** `line-due` asks whether a long film is ready for its line: tier D, the
   founder's voice, takes or timing present. If so, the whole film line runs as code (`film-line`,
   resumable, 55-minute cap per tick) and the result is committed and pushed.
5. **Otherwise starts one capped Claude session** (`ai-tick`) for queue work that needs judgment. The
   caps are 400k weighted tokens a tick, 1.5M a day and 6M a week, on Sonnet at medium effort.

Weighted tokens: input ×1, cache write ×1.25, cache read ×0.1, output ×5. Output is counted live from the
stream and a session is killed the moment it passes its cap. A film also has a total cap of 1.5M
weighted tokens.

### 2.3 Voice (the founder)

- **Recording:** `node content/film/record.mjs <slug>` opens a local teleprompter in the browser. It
  shows one beat at a time, with record, play back, keep and next. Each kept take is saved per beat as
  48 kHz mono WAV.
- **Pace check:** when a take stops, the page measures it before he decides to keep it: words a minute
  over the voiced span only (leading and trailing silence ignored). Outside 120–200 wpm it says to read
  again ("a little fast… let the figures land" or "a little slow… more drive").
- **Narration and timing:** once every beat has a take, `takes-to-vo` turns the takes into the
  narration files and aligns every word with faster-whisper on the GPU. `timing` then builds the film's
  word-level timeline.
- **Placeholder voice:** a local TTS (Kokoro) can stand in to preview a film before his takes exist.
  A placeholder film can never be published. Its timing is marked `voice: placeholder`, and the line
  re-times the film from his takes when they arrive. Without takes it stops rather than build on the
  preview.

### 2.4 Timing

`timing.json` holds:

- **Segments:** one per beat and one per chapter card, each card a fixed 2.5 s.
- **Words:** every word's start and end.
- **Spoken figures:** every mention of every `{{key}}`, with its time.
- **Chapters.**
- **CLIP spans.**
- **Legal cutpoints:** where a picture cut may land. These are segment boundaries, sentence ends,
  pauses of 120 ms or more, and the word boundary just before every spoken figure ("cut on the
  figure"), so a figure's shot can open as the figure is said.

An end card holds 4 s after the narration.

### 2.5 The shot plan

A film of 29 minutes has about 230–280 shots. The plan is split so code does the mechanical part and
one model reply does the judgment.

**1. Skeleton (code).** It walks the cutpoints:

- **Length:** target shot length 6.5 s (5 s in the first minute), ceiling 8 s (7.5 s), floor 3.5 s.
- **Holds:** never cut within 3 s after a figure lands.
- **Cut scoring:** each candidate cut is scored by distance from the target plus a penalty for how
  long the next shot would wait on bare paper for its figure. This prefers cuts on the figure's word.
- **Kind:** a shot with spoken figures becomes "paper" (one figure: number; two: pair; three or more:
  timeline/ledger). Otherwise it is "world" (a still picture pushed in).
- **Fixed shots:** chapter cards, and each `KEEP` sentence as a kinetic-thesis card spanning exactly
  its words. The model never changes these.

**2. Brief (code).** A compact document holds:

- the shot-plan rules;
- a table of the plan fields the renderer honours;
- the styles, one line each;
- the figures the voice says;
- every drafted shot, one line each: id, time, room, kind, style, figures, the words spoken under it.

It runs to about 78 KB for a 29-minute film.

**3. Decisions (one model reply).** The brief goes to Claude Sonnet as a single reply: no tools, a
one-line system prompt, a working directory outside the repo (so no project files or memory load),
the prompt on stdin.

- **What it decides per shot:** kind, style, landing word, params (layout, a companion print), picture
  search queries (2–4 words), sources, fallback, intent.
- **Cost:** about 31k tokens in and 25k out (including some thinking), 163k weighted, 150 s, on G02.
  The budget is 400k.
- **What it replaced:** a full Claude Code session, which cost 1.3M on the same plan.

**4. Apply (code).** The decisions merge into the skeleton. Params are merged, never replaced, and
fixed shots are skipped. Code then derives the room from the style, and a landing word where a style
requires one.

**5. Fill and autofix (code).** Fill snaps cuts and copies the words and figures under each shot.
Autofix fixes known mechanical problems:

- a shot with nothing to draw gets its content back from the figures or words spoken under it;
- a figure or pair opens on a context line from its fact label;
- a thesis card over 12 words, a pan too short to pan, and missing landing words are corrected.

**6. Validation (code).** The validator checks the plan against the narration:

- contiguity and legal cuts;
- shot lengths, and holds after figures;
- known styles for the room and kind;
- every paper shot has something to draw;
- the first minute's median shot length;
- variety rules (no style three times in a row and similar);
- screen-mix shares by category. These are advisory only.

**7. Fix (one more model reply, only if needed).** If validator problems remain after autofix, one capped
reply receives the problems and the shots they name (with one shot either side) and returns field
patches. Whatever it can't fix stops the line with the list. No open-ended agent session ever runs
unattended.

### 2.6 Sourcing

For every world shot and every companion print, code searches public sources:

- **Sources:** Pexels and Pixabay (stock video and photos); the Library of Congress, Smithsonian,
  Wikimedia Commons, Internet Archive and NARA (archival).
- **Queries:** shortened by code to 2–4 words, because archive titles are short.

**Licence accept-list:** public domain, CC0, CC BY, the stock sites' own licences, and "No (known)
restrictions" archival records (the founder's decision, 2026-10-07). It refuses CC BY-SA, NC, and any
"may be restricted" statement. Every asset keeps its full provenance: source, URL, author, licence,
rights text.

**Filters (code):**
- resolution;
- frame rate and internal cuts (footage);
- brightness band;
- faces detected by YuNet: rejected on stock and AI imagery; allowed on archival photos of the film's
  own historical subject;
- perceptual-hash duplicates;
- the licence list;
- a print-size rule.

**Large masters:** a Library of Congress image larger than the grade's 4,800 px is fetched through
its IIIF service at that size, about 2 MB instead of a 300–700 MB TIFF.

**Caching and robustness:** API answers are cached for 24 h and assets by sha256. Network errors are
retried 3 times.

### 2.7 Picking

- **Auto-pick (code):** each picture shot takes the top-ranked candidate that passed the filters, never
  reusing an asset within a film.
- **Auto-prints (code):** a type shot that wants a companion picture on the desk gets one the same way.
- **Resolve-gaps (code):** a picture shot with no usable candidate is absorbed into a neighbour (up to
  14 s) or becomes a typed card of the film's own words, labelled "As this film states it".

**There is no semantic check that a picture matches its sentence.** The filters judge quality and
rights, not subject. Picture relevance rests on the query and the source's ranking. An earlier
`visual-pick` skill for a model to choose from contact sheets exists, but the line no longer runs it,
to save tokens.

### 2.8 Rendering

Every shot renders to its own clip (`shots/<id>.mp4`, 1080p30). The look is locked: a "v3 archive at
night" look, with fixed tokens, grade, typefaces and motion numbers.

**Paper shots** (type, figures, pairs, timelines, formulas, documents, quotes, tables, charts) are
drawn by a web stage, HTML/CSS/JS rendered frame by frame in headless Chromium:

- Figures land on their spoken word.
- A slow camera push and drift run through every shot, about 1% a second.
- Labels and the honesty labels sit in a fixed slot.
- A figure's context line, and a pair's labels, are set at the cut, so a shot opens on what is coming.
- A type shot that follows a picture holds that picture behind it, dimmed, until its first figure
  lands ("backdrop").

**World shots:**
- Stills are graded (a locked four-stage colour chain) and pushed or panned.
- Footage is graded and trimmed with ffmpeg.
- A few engine charts render in Manim.

**Cache:** a clip's cache key is the sha256 of its resolved job, its assets, the stage's files and the
renderer version. Checking tools are left out of the key, so editing QA doesn't re-render anything.
Only changed shots re-render.

**Workers and batches:** workers are sized to free memory (1–4, about 3 GB each at peak). Since
2026-10-07 the stage renders in batches of 12, each batch recorded as it finishes, so an interruption
loses at most one batch.

**Running it:** long renders run detached from any chat session (`systemd-run --user`) with a 10 GB
memory cap, so a runaway render is killed instead of freezing the PC.

**Measured:** a full G02 render (232 clips, 29 minutes of film) takes 67–72 minutes on 3 workers, with
a 7.9 GB memory peak.

### 2.9 Sound design and mix (code)

Built from named principles (Murch, Burtt, Rydstrom; documented in `SOUND_DESIGN.md`).

**The voice:**
- A chain: rumble cut, gentle noise reduction, de-ess, a mud cut, presence, air, two compressors, a
  limiter.
- Breaths between words are pulled down 9 dB on 20 ms ramps, never cut to silence.
- A real voice gets no added reverb.

**Music:**
- One licensed bed (generated with ElevenLabs on a paid plan), varied into a family of cues, one per
  chapter, crossfading at chapter cards.
- Levelled by its average, not its peaks.
- Under speech its voice band (250 Hz–5 kHz) drops 12 dB and the rest 4 dB.
- It dips 7 dB for the quarter second before each hero figure, and swells 8 dB while a chapter card
  holds.

**Effects:**
- A tick when a figure lands.
- A low hit under hero figures.
- Whooshes when the picture changes room (paper to world).
- Paper foley three frames before a print lands.
- A riser into each chapter card.
- Each instance gets its own pitch and level.
- Effects within 0.35 s of each other are thinned by priority (Murch's "two and a half").

**Ambience and room tone:**
- Each footage shot gets its place's sound from a library of 17 ElevenLabs-generated ambiences. It
  starts 0.5 s before the cut and tails 0.35 s after.
- Room tone runs under the whole film.

**Stereo:** mid/side, mono-safe. Voice and low hits sit dead centre; music, place and room are widened
by all-pass side signals; ticks and paper are panned slightly. Folded to mono, the mix is identical.

**Loudness:** −16 LUFS integrated, −2 dBTP before the AAC encode, a loudness range a documentary
breathes in.

**Measured into the mix's own record:** voice over music under speech (≥15 dB), designed effects a
minute (2–14), longest stretch with nothing designed (≤60 s), and side level under the centre (≥6 dB).
G01 measured 16.1 dB, 12.1 a minute, 22.7 s, and side 21.4 dB under.

Memory: about 4.3 GB peak for a 31-minute film (float32, filters in chunks).

### 2.10 Draft, review and QA (code)

- **Draft:** the clips are joined and the mix laid under, NVENC-encoded, and the length is checked
  against the narration. Captions (`captions.srt`) are written from the narration's own words.
- **Review sheets:** 39 contact sheets for G02, 6 shots each at 3 moments, with the words spoken.

**film-qa** (`qa/film-qa.json`) runs every check as code, with no AI critics:

*Plan checks*
- The validator's problems.
- Every clip exists and is the right length.

*Stage checks* (the stage renders each shot's DOM at sample times)
- A figure readable before it is said.
- A bare opening: a shot whose first frame has almost nothing lit, no held picture, and no line of 3+
  words.
- A label on a lit area.
- Text running under the companion print.
- Text outside title-safe.
- Overlapping text.

*Media checks* (on the draft)
- Length.
- Integrated loudness (−17 to −15 LUFS), true peak (≤ −1.5 dBTP), loudness range (2–12 LU).
- Black frames.
- Frozen picture of 4 s or more.
- The mix's sound measures.
- Mono safety.

*Learning checks*
- At least 70% of figure shots open within 0.6 s of their figure's word.
- No chapter over 6.5 minutes.
- His pace per beat, 120–200 wpm, once the takes are his.

**Current G02 numbers (placeholder voice):** 49 problems, down from 87 on 2026-10-07. They are 23 bare
openings (mostly quotes and timelines), 20 freezes, 2 title-safe, 3 learning and 1 plan. G02 was planned
before the cut-on-the-figure change, so it doesn't benefit from it.

**The founder's review:** he watches the draft. This is a gate (`approve_final`): nothing publishes
without it. Earlier films went through rounds of multi-agent AI critique; those were stopped because
they consumed most of a weekly usage limit.

### 2.11 Master and publishing (code, after approval)

- **Master:** clips joined once at the master's settings, the mix underneath, nothing burned in.
- **Captions:** the `.srt`, uploaded as YouTube's caption track (no burned-in subtitles on long films).
- **Thumbnail:** built from a fact (figure and label) on the brand look. Not yet run on a tier-D film.
- **Description:** chapters from the timing, every picture's credit from its provenance, and links to
  /learn and /apply with `?src=yt-<id>`.
- **Worksheet:** a one-page sheet per film: its KEEP lines, the TRY beat as numbered steps, and the
  figures with sources (demo figures marked). Not yet published anywhere; putting it on /learn waits
  for the founder.
- **Shorts:** vertical cuts from CLIP markers. Built for the earlier, shorter tiers; not yet run on a
  tier-D film.
- **Upload:** through the YouTube Data API as unlisted, with the synthetic-media flag set only when a
  film contains AI imagery. Writes `published.json`.

**Not done yet:**
- The Google OAuth client and sign-in don't exist, so no upload has happened.
- Google's API audit, needed for public uploads, hasn't been requested.
- The site does not yet embed YouTube films.

### 2.12 Measurement and learning loop

- **Meter:** every AI step is metered per film (weighted tokens by step against budget);
  `film-cost <slug>` reads it.
- **Retention (built, waiting on the YouTube sign-in):** pulls each published film's audience-retention
  curve (100 points). It reports the steepest drops past the first 30 s, each named by time, shot,
  style, beat and words, plus the rewatched moments. `retention-patterns` ranks every style by
  viewers lost per minute while on screen, relative to its film, across films. This is meant to replace
  AI critique with what viewers actually do.
- **Attribution:** `?src=yt-<id>` links flow through to booked calls in the operator's digest.

---

## 3. Cost and time per film (measured where stated)

| Item | Cost |
|---|---|
| Script | the founder's drafting elsewhere (counts against the same subscription if drafted in claude.ai) |
| AI on this machine | ~0.16M weighted tokens for the plan decision (measured), plus a fix reply only if needed |
| Founder's time | reading the script at the teleprompter (about the film's length plus retakes), watching the draft, approving |
| Render | ~70 min for a 29-min film (measured), unattended |
| Mix | ~3 min, 4.3 GB peak (measured on G01) |
| Draft encode + film-qa | ~10 min |

A film's AI cap is 1.5M weighted tokens. G02 actually spent 1.74M, all of it on the old,
pre-reply planning path; the new path measured 163k on the same plan.

---

## 4. Status: what is real, what is built but unproven, what is missing

**Proven on real films:**
- the intake (on G02's script);
- placeholder-voiced timing;
- skeleton, decide reply, fill, autofix and validation;
- sourcing and picking;
- rendering;
- the mix;
- the draft;
- film-qa (G01 and G02 drafts exist);
- the founder loved G01's fifth draft.

**Built, not yet exercised end to end:**
- His own voice: no takes recorded yet, so every film so far is placeholder-voiced.
- `takes-to-vo` and the pace meter on real takes.
- The film line running unattended from takes to draft.
- The master, thumbnail, shorts and upload on a tier-D film.
- Retention analysis.

**Not built:**
- The site's YouTube embeds and the worksheet on /learn.
- A semantic check that pictures match their sentences.
- Source verification for script facts.
- AI-generated textures, planned through a Higgsfield connector; the line does not generate them.

---

## 5. Known gaps and risks (as we see them)

1. **Picture relevance.** Nothing checks that a picture shows what the sentence is about. Rank-based
   auto-pick plus short queries can pick a well-licensed but off-topic image.
2. **Fact accuracy.** Sources are required but never fetched or checked; a wrong value with a real
   citation passes.
3. **Dead air remains:** 20 freezes and 23 bare openings on G02. Timelines and documents hold still
   between landings; quotes open before their first word.
4. **One music bed** varied into cue families. Over 7 films a week it may become recognisably
   repetitive.
5. **The ambience library** has 17 sounds; a subject outside it gets room tone only.
6. **The thumbnail** is a formula (a figure and a label), unproven against click-through.
7. **No real voice yet.** The whole timing and pace system has only run on a synthetic voice.
8. **Founder time is the bottleneck at 7 a week:** about 3.5 hours of reading plus retakes and
   watching drafts, every week.
9. **Render capacity:** ~70 minutes per film, one machine. Seven films is about 8 hours of rendering a
   week, plus re-renders after fixes. The PC hard-rebooted twice on the evening of 2026-10-07, once mid-render;
   cause unknown, and no out-of-memory record was found.
10. **Publishing is blocked** on the Google OAuth setup and API audit. Until the audit passes, uploads
    may be forced private.
11. **Third-party claims:** stock footage can draw Content ID claims. Provenance is kept for disputes.
12. **The learning rules are new:** calibrated on three history-first pilots, not on an education-first
    film or on viewer data.
13. **One reply plans 250 shots.** A bad reply (malformed JSON, poor choices) is caught only by the
    validator and film-qa, not judged for taste.

---

## 6. Questions for an auditor

1. What stage, if it failed silently, would ship a wrong or embarrassing film? How would we know?
2. Is the cost model right? Where will tokens or hours actually go at 7 films a week?
3. What do the best educational YouTube channels do in their production process that this one lacks
   (research, scripting, editing, packaging, testing)?
4. Are the learning rules the right ones, and are any thresholds wrong?
5. Is relying on code checks plus retention data, instead of AI or human critique rounds, sound? What
   would it miss?
6. What single change would most improve viewer retention?
7. What legal, licensing or platform-policy exposure is unaddressed (YouTube's policies on repetitive
   or mass-produced content, Content ID, archival rights, AI disclosure)?
8. What is the weakest link between a finished film and a booked call?
