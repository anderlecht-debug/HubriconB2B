# /learn — free training hub build prompt

Third companion document, alongside `hubricon-landing-rework-prompt.md` and
`hubricon-capital-position-build-prompt.md`.

Reference model: the Acquisition.com free-training pages — a card grid of courses, and inside
each course a three-column layout (left lesson nav, center video, right gated capture form).
Replicate the structure and the discipline, not the visual style. Hubricon's own dark
navy / amber / Fraunces system carries through.

---

## 0 · Why this exists

Three jobs, and every decision on the page should serve all three:

1. **Proof of competence before payment.** With no case studies, teaching the method publicly is
   the strongest authority available.
2. **Capture with routing.** Every course is gated by the four-question application. The revenue
   answer sorts the lead into Managed Profit or Capital Position automatically.
3. **Manufacturing the gap.** Hubricon has a structural advantage Acquisition.com does not: a
   founder who fully understands elasticity estimation, 20,000-path Monte Carlo and
   heteroskedasticity-consistent standard errors still cannot execute them. Teaching the method in
   full does not cannibalize the service — it makes the size of what he's missing legible.

Governing rule: **teach everything the reader can actually do himself, and let it pay him real
money immediately. Then teach the shape of what he can't, in enough detail that he sizes it.**

---

## 1 · Build order — one course, not four

Ship **course 1 only**. A /learn page with one complete artifact reads as more authoritative than
four with "coming soon" badges, and four half-built courses is how a solo operator loses a
quarter.

### Course 1 — The Reimbursement Playbook (build this, alone, first)

Free, gated. Every category Amazon owes money in, how to find each one in the seller's own
reports, how to file, and the exact day each window shuts.

Why this one and not a smarter one:
- It pays the reader in verifiable dollars within a week, and requires zero trust to act on.
- `RECOVERY.EV` already computes it. The content is half-written in the engine.
- **It generates publishable results without a paying client.** "Your free playbook recovered
  $3,400 for us" is a real, named, substantiated testimonial. Twenty of those in a quarter fills
  the proof hole on the main Managed Profit page while the $6,000 offer is still unsold. This is
  the fastest path to the proof that every other project is currently blocked on.

Deliverables, in priority order:
1. **The spreadsheet template** — this is the actual lead magnet. It lives on his hard drive for
   two years with Hubricon's name on it.
2. A written playbook, one page per claim category: what it is, which report reveals it, how to
   compute what's owed at landed cost, how to file, the window.
3. **Raw screen recordings, one per category, 4–8 minutes, unedited.** Real Seller Central, real
   reports, real numbers, cursor visible. **Do not animate this course.** Its entire credibility
   is that the viewer is looking at the actual tab in the actual account. See §5 on format
   assignment — polish actively destroys the proof value here.

**Ask for the result.** Every download's follow-up sequence asks a single question: how much did
you get back? Request permission to publish the number and the brand name. This is the proof
engine, so make the ask explicit and make it easy to answer.

### Courses 2–4 — specified, not built yet

**2 · The Profit Teardown Course.** Computing true net margin per SKU by hand: fee decomposition,
landed cost, honest ad allocation. Genuinely useful, and miserable across 40 SKUs. They complete
it once. That experience sells the service better than any copy on the site.

**3 · The Inventory Capital Course.** Why a flat 95% service level is wrong for most SKUs and how
margin sets your own number; what a stockout actually costs including the rank repurchased with
ad spend; how to read a cash trough. Feeds Capital Position directly.

**4 · Pricing Without Guessing.** Why Amazon price tests are mostly noise, what confounds them,
what sample size would actually be required. This is the course that closes the loop — the
clearest available demonstration that the reader is not going to run this himself.

### The live item — The Teardown Hour

In place of Acquisition.com's in-person workshop. One real brand's numbers torn down live, monthly,
one hour, recorded. A workshop needs a venue and a team; this needs a calendar link. Each session
produces a recording, a case study and a named result. Highest authority-per-hour available to a
one-person firm.

Do not put this on the page until two sessions have actually run.

---

## 2 · Page structure

### `/learn` — the hub
Mirrors the card grid. One card per course, badge on each (`New`, `Free`, `Live monthly`).
**No card for anything not yet built.** Headline states the position plainly — the method is
public, the execution is the product. Under 200 words of page copy total.

### `/learn/<course>` — three columns
- **Left:** lesson nav, sticky, current lesson highlighted. Mirrors the Acquisition.com pattern.
- **Center:** video if it exists, otherwise the written lesson. Template download sits directly
  under it, above the fold, never at the end.
- **Right:** the gated capture form, sticky on desktop, collapsed to a single inline block on
  mobile.

Gate the **template download and lesson 2 onward**. Lesson 1 is fully open. Someone who won't
read one free lesson is not going to fill in a form.

---

## 3 · The form — capture and route in one

Same four questions as the main application: where you sell, annual revenue, business model,
catalog size. Plus first name and email. Nothing else. No phone number — it is the highest-friction
field on a page whose job is list growth, and the revenue band does the qualifying without it.

Routing on submit, from the revenue answer:
- **$3M+, own brand** → template delivered, plus the Managed Profit call offer and the free
  Profit Teardown.
- **Under $3M, or not own brand** → template delivered, plus Capital Position at `/position`.
- **Not a seller / other** → template delivered, nothing offered. Newsletter only.

Every lead lands in the same list with its band, model and catalog size attached, so the outbound
engine can segment without re-asking.

---

## 5 · Production — format assignment and pipeline

Available: Higgsfield (image and video generation, batch), ElevenLabs (voice), plus the engine's
own chart renderers. This permits a Vox-grade explainer library from a solo operator. It also
permits a fast, expensive mistake, so assign format by job before producing anything.

### Format is assigned by what the lesson has to accomplish

| Job | Format | Why |
|---|---|---|
| **Concept / abstraction** — why flat 95% service level is wrong, what a stockout really costs once rank repurchase is counted, why an Amazon price test is mostly noise | **Animated Vox-style explainer** | No natural footage exists. Motion on real numbers beats a founder at a whiteboard. |
| **Procedure / proof** — the Reimbursement Playbook, anything that shows where a number hides in Seller Central | **Raw, unedited screen recording** | Credibility comes entirely from the viewer seeing the real tab. Polish reads as advertisement and destroys it. |
| **Promise / operator presence** — founder note, Teardown Hour, client walkthroughs | **Founder's real voice and face, unproduced** | The brand is one named human. This is the one place production value is a liability. |

Getting this backwards produces something beautiful that converts worse than a laptop screen
capture. Courses 2–4 are largely animated. Course 1 is not animated at all.

### The differentiator: animate real model output

Vox has to source its data. The engine generates it. `MONTE_CARLO.RUN` produces the cash cone,
`ELASTICITY.FIT` the demand curve with its confidence band, `MARGIN.DECOMP` the fee waterfall,
`NEWSVENDOR` the service-level cost curve — all already rendered in the portal.

Render these as frame sequences from real model runs on demo data and animate the actual output.
Do not hand-draw an illustration of a chart the engine can produce. This makes the visuals both
better than a motion designer's and structurally impossible for a competitor to copy, because the
model is the thing they don't have. It is the series' signature.

### Pipeline

1. **Script first.** 700–900 words ≈ 5 minutes. One thesis stated in the first fifteen seconds,
   then evidence. Chapter cards. Real dollar figures on screen as spoken.
2. **Engine renders the data visuals** as PNG frame sequences from actual model runs.
3. **Higgsfield** for abstract motion, transitions, texture and b-roll only.
4. **ElevenLabs** narration on a clone of the founder's own voice.
5. **Assembly**, then the same three-column lesson page.

### Hard prohibitions

- **No synthetic humans, avatars, or generated faces anywhere.** The brand is one named operator
  who signs his name. A fabricated person implying a team destroys the only asset the business
  has. Higgsfield is for graphics, never people.
- **Voice clone must be the founder's own**, not a stock narrator, so the library sounds like the
  person on the invoice.
- **Disclose it.** One line in each description: the narration is a clone of the founder's voice,
  the analysis is his. On a business whose entire claim is verifiability, undisclosed synthetic
  narration is a disproportionately cheap thing to be caught on.
- **No generated data, ever.** Every number in every visual comes from a real model run on real or
  clearly-labeled demo data. Same standard as §3b of the landing prompt.

### Style lock and volume

Produce the first explainer, then **freeze the style** — palette, type, motion timing, chart
treatment, intro card, narration pacing — and reuse it across every subsequent video. Save the
Higgsfield reference/preset. Unlocked style produces a pile of videos; locked style produces a
series, and only a series compounds.

The real advantage here is cadence, not polish. An afternoon per explainer instead of a studio day
means weekly output is achievable, and weekly is the threshold where search and YouTube begin
working for a solo operator. Twenty explainers in six months is a category-defining library in
Amazon-seller content.

Repurpose each explainer: three vertical cuts for shorts, one native LinkedIn upload, one
newsletter section, one embed on the relevant lesson page. The `video-script-generator` skill
already in the workspace handles the shorts adaptation.

## 6 · Rules

- **Teach completely.** No withheld steps, no "the rest is in the paid version." The service is
  execution, and every gap left in the teaching weakens the authority the page exists to build.
- **Ship the document and the template before the video.** Production capacity makes video cheap
  but not instant; a lesson that can ship as a written page plus a spreadsheet ships that way and
  gets its video in the next pass. This is a sequencing rule, not a preference for text.
- **No hype furniture.** No countdowns, no "limited spots", no fake enrollment counts. /learn runs
  under the same luxury pass as the main page.
- **`/learn` is linked from the main page's nav and footer only** — never inside the Managed
  Profit body copy, which stays at its reduced word count.
- One CTA per course page. The form is it.
- Every published result from the playbook goes into the main page's proof section under the rules
  in `hubricon-landing-rework-prompt.md` §3b: named with permission, checkable numbers, method
  shown. A recovered-claim result is a legitimate published result even though the reader did the
  filing.

---

## 7 · Acceptance check

1. `/learn` shows only courses that exist in full. No "coming soon" cards.
2. The Reimbursement Playbook ships with a working spreadsheet template before any video exists.
3. The Reimbursement Playbook's videos are raw screen recordings. Nothing in course 1 is animated.
4. No generated face, avatar or synthetic human appears anywhere in any asset.
5. Narration is a clone of the founder's own voice, and every description discloses it.
6. Every number in every animated visual traces to a real model run; demo data is labeled as such.
7. The visual style is frozen after the first explainer and the preset is saved.
8. Lesson 1 of every course is readable without a form.
9. The form has six fields and no phone number.
10. Revenue band routes to Managed Profit or Capital Position with no manual sorting.
11. The follow-up sequence asks for the recovered amount and for permission to publish it.
12. No lesson withholds a step or refers to a paid version for the rest of the method.
13. The Managed Profit page's visible word count is unchanged by this project.
