# The Hubricon brand

*The brand system, for whoever touches a page, an email, a deck or an asset next.
Read `HUBRICON.md` first: the honesty rules and the vocabulary there bind everything
here. Written 2026-09-25, when the founder's photo came off the home page and the
brand replaced it. The strategy it serves is in `MONOPOLY.md`. Rebuilt 2026-09-30 from
`HUBRICON_SPEC.md`: the spine, the voice and the visual system below are the spec's,
and where this file and the spec disagree, the spec wins.*

---

## The spine (2026-09-27)

**Precision in service of trust.** What the buyer pays for is trust with someone close
to their money, so every decision gets one test: does this make us more trustworthy to a
skeptical operator, or less? The feeling in the first three seconds is excitement and
relief, and it comes from clarity and exact numbers, never hype. Hubricon is the calm
adult in a room of shouting salesmen: the guru with a course, the agency with a dashboard
of nonsense, the gut feel with no math behind it.

Lead with the after-state, never the category. Not a software, a dashboard or an agency:
what becomes true is that the client always knows exactly where their money is made and
lost, stops losing it, and sees it proven every month or does not pay.

- **Signature line:** Your mental model is linear. Amazon's cost structure is a staircase.
- **The line that removes the shame:** A P&L is an average. A cliff is only visible as a
  counterfactual, and no report anyone sells contains one.
- **Honesty as an asset:** most brands we model from public data show nothing worth fixing,
  and we say so. Measured, not guessed: 1,473 of 1,856 on 2026-09-30
  (`engine/scripts/silence_rate.py`).

## The one idea

**Paid on proof.**

Everything else is that idea said again in a different place. It names the enemy
without naming anyone (agencies are paid on spend, software is paid to report,
consultants are paid by the hour), it states the guarantee in three words, and it
hands every founder a question to ask anyone they pay. A brand owns a category when
it owns the question; ours is *"show me the Record."*

| Layer | Line | Where it lives |
|---|---|---|
| Brand line | **Paid on proof.** | Hero stamp, footer motto, seal ring, share image, manifesto title |
| The creed | Your agency is paid on spend. Your software is paid to report. We're paid on proof. | Home page, manifesto §I |
| The method | Called before. Measured after. | Seal ring, manifesto §III |
| The product | Every move gets a receipt. | The offer section, the receipts |
| The guarantee | Proven or Void. | Unchanged; the guarantee's name |
| The ambition | That "show me the Record" becomes the question every brand asks anyone it pays. | Manifesto §V only |

The offer headline stays the offer: *More profit than our bill every month, or you
don't pay.* Since 2026-09-30 "Paid on proof" is a line in words only: the stamp and the
seal that carried it are retired with the night system. The home page is judged by the
Hormozi standard: one action, and no proof that does not exist. Since 2026-10-01 evening it is
also short, the founder's call ("a short first page, not a lot of scrolling … the rest on the
tabs"): five bands, its own words capped, and every other section on the page under its tab.
The creed opens /offer, in three lines, the third in ink: *Your agency is paid on spend. Your software is paid to report. We're paid on
proof.* The method names the Profit Record's section: *Called before. Measured after.* And
the product is shown, not said: every move on the scoreboard illustration has its receipt.

## Positioning

For private-label brands doing $1M–$30M a year on Amazon and Shopify (the band since
2026-09-27; it was $3M–$20M), who have no
finance function and five tools that report but never decide, Hubricon is the only
service that makes the money decisions inside the account and is paid only on proof:
each move called in writing before it goes live, measured on the owner's own reports,
and no month billed unless its own Record cleared the fee.

## The enemy

Not a company. A way of getting paid. **Percent-of-spend** is to e-commerce what
cost-plus contracting is to defense: the vendor earns more when the client spends
more, so the incentive is broken before any work is done. Anduril built its brand
against cost-plus by building products on its own money and selling what worked;
Hubricon's version is the free Proving Month and the invoice that voids itself.

Second enemy: **the after-the-fact explanation.** The monthly deck, the attribution
screenshot, the story told once the number is known. Our answer is the call made in
writing before the move. Never mock a person or a named competitor; mock the model.

## What we took from the two references

**Anduril** — a mission with a villain, stated in one line; a manifesto long enough
to mean it; product names that sound like objects, not features; cinematic, dark,
exact imagery; confidence without adjectives. Taken: the manifesto (`/manifesto`),
the dark industrial film, the numbered doctrine, the names (the Record, the Seal,
the Proving Month, the Teardown). Not taken: military language, secrecy.

**Liquid Death** — a boring category made into an identity; one visual icon repeated
until it is the brand; humour that is deadpan and exact rather than zany; merch as
media. Taken: the icon (the receipt and the stamp), one dry joke per page at most
("the only invoice that voids itself"), the stamp as something a founder would put on
their desk. Not taken: shock, skulls, anything that makes a $6,000 decision feel like a
novelty. We are a high-ticket service; the humour lives in the precision.

## Voice

- Cold, matter-of-fact, a little unbothered: a doctor reading a scan, not a closer.
- Scarcity and urgency only as facts of how the practice runs and how the client's
  economics work ("one operator means a limited number of accounts at once"; a dated fee
  step, named). Never a countdown, a "spots left", a timer or "act now".
- Short declaratives. Numbers before adjectives. A figure always says what it is
  (our price, a vendor's price list, arithmetic from a named source, demo data).
- Contempt for vagueness, never for people.
- No hype words: revolutionary, unlock, leverage, game-changer, AI-powered, supercharge.
- One dry line per page, at most.
- Future things in the future tense, labelled. Nothing is described as live until it
  is live in production (the manifesto's section V carries a "not live yet" tag and a
  footer line for exactly this reason).
- HUBRICON.md's retired words stay retired: desk, ledger, quantitative, retainer,
  engagement, directive, and the rest of that list.

## The visual system (since 2026-09-30)

Decided in `HUBRICON_SPEC.md` ("Visual direction") and built in `/assets/hubricon.css`,
which every page reads. A page keeps its layout inline and its colours nowhere: no page
has a private palette (`scripts/build-pages.test.mjs` fails the home page if it tries).
Think a quant fund or Stripe, not a private bank.

### Colour

| Token | Value | Role |
|---|---|---|
| `--paper` | `#ffffff` | Every page's ground. A lot of air |
| `--paper-2` | `#f5f6f8` | A quiet panel (the scoreboard, the booking form). Never a shadow |
| `--ink` | `#0a0e17` | Headlines, the button, every chart's lines |
| `--ink-2` / `--ink-3` | `#3b4250` / `#636b7a` | Body / captions, labels, axes (5.3:1 on paper) |
| `--rule` / `--rule-2` | `#e4e7ec` / `#cdd2da` | Hairlines, gridlines, chip borders |
| `--blue` | `#0b5fff` | **The one accent, used only on money and the leak.** The client's dollars, a range, the riser that is the finding. Never a button, a link, a heading or decoration. 5.1:1 on paper |
| `.night` | `#070a11` ground, `#5b94ff` blue | A dark section is the same tokens swapped; it separates acts and never decorates |

No red, no green. A loss is ink with a minus sign; the cool accent reads as an instrument,
a warm one as retail urgency. Our own price is ink: the blue is for the client's money.

### Type

One sans, two weights: **Inter** 400 and 600, from Google Fonts, always loaded with its
optical-size axis (`family=Inter:opsz,wght@14..32,400;14..32,600`) so text from about 20px
up takes **Inter Display**, the cut Inter draws for large sizes: tighter, crisper. Requested
without that axis, every headline falls back to the small-text cut and reads generic (found
and fixed 2026-09-30, the founder's pick of four on real frames). Headlines at -0.032em,
balanced. Every number tabular (`font-variant-numeric: tabular-nums`) on figures, money,
charts and every `data-fill` value, but not on prose: Inter's tabular feature also widens
the hyphen, and "founder-operated" would read "founder - operated". A figure standing alone
at display size in a film takes proportional digits; tabular digits are for columns.

### Space and layout

One spacing scale (4, 8, 12, 16, 24, 32, 48, 64, 96, 128 px), one content width (1120 px),
one radius (10 px). One idea per screen. The button is ink, always reads **Book your call →**,
and always goes to `/apply`.

**The bar (since 2026-10-01, the founder's call: "we are mimicking Apple's .com with the
education tab").** Every public page opens with one bar: the mark, the tabs **Proof · How it
works · The offer · Education · Trust**, each a page of its own (`/case-study`,
`/how-it-works`, `/offer`, `/learn`, and Trust's panel), and the call. No Results tab until a
client fills one (the founder, 2026-10-01 evening). Education and Trust open a
panel the width of the window, Apple's way: large links in the first column, the rest
quieter, the page behind it blurred. On a phone the tabs fold into one menu of large links.
The glass is white over whatever scrolls under it; a hairline appears once the page moves.
`/apply` keeps no bar: once someone is booking, nothing else is offered. The footer is the
same on every page: the mark, *Paid on proof.*, four columns, the one legal line.

### The mark

The ring and geometric H, now in ink; the wordmark is "Hubricon" in Inter 600 with no
coloured letter. Favicon: the white mark on an ink rounded square.

```html
<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>
```

### Data is the only imagery

No photographs, no stock, no people. The pictures are the house visuals, drawn from real
numbers by `/assets/charts.mjs`:

- **The staircase.** Amazon's published fee card as steps, one real listing as a solid dot,
  the same listing one step down as a hollow dot, and the riser between them in blue: the
  finding is the only thing in the accent.
- **Ten thousand years.** The Monte Carlo: faint paths from today fanning out, settling into
  P10, median and P90 and a soft band that openly includes the bad end. Never converges on
  one triumphant number.
- **The aging cliff.** Storage plus the aged-inventory surcharge by age, the day-271 step in
  blue.

Every chart is baked into the page as its finished still frame (`scripts/build-pages.mjs`),
so a visitor without scripts sees the result. Line weights, the band's wash and timings are
tokens (`--line-*`, `--mc-*`).

### Motion

One draw-in, then still. A chart plays once when it scrolls into view: paths sketch in
left to right over about two seconds on an ease-out, fade back to almost nothing, then the
band fills over 0.4 s. It never loops and never asks for attention again. Under
`prefers-reduced-motion`, or when the page's script never arrives, the still frame is all
there is.

The same rule, since 2026-10-01, for everything else that moves (`/assets/site.js`): a
section's parts rise into place once as they arrive (`data-reveal`, 20 px, under a second,
staggered a beat apart); the true-today numbers and the scoreboard's total count up once to
the figure the page already prints (`data-count`); the scoreboard's bar fills to the bill
and past it; each course cover draws its line. Nothing loops and nothing moves again.

**Nothing is ever blank for want of a scroll** (the spec's contract for the Monte Carlo:
"before it fires, show the finished still frame"). Every chart, section and number is in the
HTML as its finished still frame. The script puts one back to its start only while it is
still below the screen, within a screen of arriving, and plays it as it arrives; what is
on screen at load, or what a visitor jumps past, stays as it is. The hero's chart is the one
that draws as the page opens (`data-play="load"`). `scripts/build-pages.test.mjs` fails any
rule that hides content without that.

### The pieces a page is built from (since 2026-10-01)

In `/assets/hubricon.css`, so every page draws them the same way:

- **The exhibit** (`.exhibit`, `-head`, `-body`, `-cap`): a chart framed as an instrument, with a
  header row that numbers and names it ("Fig. 2 · Ten thousand years of this one listing") and
  carries its label box. A hairline, never a shadow.
- **The proof strip** (`.numbers`): four numbers that are true today, each saying what it counts.
  Never a client count or a result until one exists.
- **The go-card** (`.go-card`, `.go-k`, `.go-to`, `.go-badge`): a card that links somewhere. Only
  the call is a button (`.btn`, `.btn-lg`); everything else that goes somewhere is a card or a link.
- **Two-tone headlines** (`.tone`): the claim in ink, the turn after it a step quieter.
- **The display-xl size** (`--t-display-xl`): the one or two lines a page is remembered by.

The home page's hero carries the Monte Carlo as mood, wide and muted behind the headline, and the
case study's third visual is the aging strip (`agingStripSVG`): one unit's clock from today,
the day-271 band in the accent, the visitor's own calendar dates under the day marks.

Built from data in `scripts/site-blocks.mjs` (since 2026-10-01):

- **The course tile** (`.tile`, `.tile-cover`, `.tile-feature`): a night cover drawn from the
  house visuals in miniature, then the facts. One cover per course, one motif each: the
  staircase (fees), the waterfall with one bar in blue (the money you can't see), the cash
  trough below zero in blue (capital and cash), the profit curve with its peak in blue
  (pricing), the fan (decisions under uncertainty), the margin bars with the gap in blue (the
  operator's math). A live course is a link; a planned one is labelled Planned and links nowhere.
- **The video slot** (`.film`, `.lesson-video`): the space a video will fill. Empty, it says
  what will play there, in the future tense, and names its chapters (the case-study film's
  five beats, from `data/library.json`) rather than redrawing a chart the visitor has just
  read; full, it plays.
- **The results wall** (`.wall-frames`, `.frame`): a client's own words beside their Record,
  with consent. Off every page since 2026-10-01 evening (the founder: a wall that reads zero
  "only hurts us" for now); the piece is kept, and goes up with the first client who says yes.
- **The call** (`.calls`, `.call`): a call the engine made and what happened after, side by
  side in display type, the store study's three on the home page and on `/case-study`. A miss
  is stated beside it, never left out.
- **The course strip** (`.lib-strip`, `.strip-tile`): every live course as a small cover and a
  title, the home page's education band; on a phone, one row that swipes inside its own box.
- **The receipt** (`.rcpt`): a move, how we know, the dollars called before, measured after,
  and what they count for under the rules.
- **A hash** (`.hash`, on `/verify` and the printed Record): set in Inter with
  `font-feature-settings: "zero"` and tabular numerals, in groups of eight; never a monospace face.
- **The course's email field** (`.join-tile`): optional, since every lesson is open (the
  founder's call, 2026-10-01). On /learn's featured course card under "Start lesson 1, no email
  needed", under each course's start and at the end of its last lesson; never on the home page. One field marked
  Optional, its own outline button ("Send it to me →"), one line of what follows and the privacy
  link. It never moves the reader; it says what happened. The call is the only button on the
  home page, which carries no form.

### Labels that never come off

Every proof screen carries **Modeled from public data · Not a client · Not a result**.
Every estimate says "estimate" beside it. Ranges, never points, rounded down. An
illustration says it is one.

### Email (since 2026-10-01)

Every client email has one look, the site's in an inbox: set in Inter, -apple-system,
'Segoe UI', Roboto, Helvetica, Arial, sans-serif; ink #0a0e17 on white, #3b4250 for what is
secondary; one hairline #e4e7ec before the sign-off; the button in ink with the one 10px
radius; 520px wide; Hagen's signature. No blue except on money. The values live in one place
per language: `lib/tool_email.js` (EMAIL_*) and `engine/src/hubricon_engine/onboarding.py`
(EMAIL_*).

## Retired 2026-09-30: the night system

From 2026-09-25 to 2026-09-30 the site ran on Night `#050A1F`, Signal amber `#FFC000`,
receipt paper, Anton and IBM Plex Mono, with the stamp, the seal, the receipt and the
low-key still life as its icons. The spec retired it for the funnel ("the Rockefeller
reading a ledger feeling"). The old home page and /apply are in `archive/`; the full
description is in this file's git history (`git show ea46b1b:BRAND.md`). Every served
page is on the tokens now (/manifesto was the last, rebuilt 2026-10-01; /method and /results
redirect). The assets below are kept for the archive and the content pipeline, and since
2026-10-01 they are not deployed (`.vercelignore`: `brand`, and `hagen.jpg`, because the
founder is off camera).

## The asset inventory

All in `brand/`, generated with Higgsfield on 2026-09-25 (≈50 credits in all). Job ids
let anyone regenerate or vary them.

| File | What | Higgsfield job |
|---|---|---|
| `hero-printer.mp4` / `.webm` | The hero film: a receipt printing, 6.5 s seamless loop, 533 / 270 KB | `65e6b47d-0fc0-4a13-8a67-2a6ac4c66b22` (Kling 3.0 pro) |
| `hero-printer.webp`, `-960.webp` | The film's first frame, the poster | from the film |
| `stamp-proven.webp` | A receipt stamped PROVEN | `434319cf-beef-4c62-9540-3b748160a897` |
| `stamp-void.webp` | An invoice stamped VOID | `d29eefbe-555a-4851-aadc-f15697a30f22` |
| `stamp-tool.webp` | The steel hand stamp and red ink | `713ca885-def4-47fc-ab66-98f763f0e0cf` |
| `seal-wax.webp` | An amber wax seal pressed with an H | `72fcf333-3146-44c6-a4e2-fd133fe8b21f` |
| `caliper.webp` | A caliper on a shipping box: measured | `518ef383-fb16-444e-b3a7-7ce7dac52418` |
| `warehouse.webp` | The manifesto's opening, the aisle at night | `b8a20e08-d5f6-4db8-813f-acb617c85b0a` (Soul Cinema) |
| `warehouse-aisle.webp` | The same, symmetric (spare) | `a8ac0b65-fcd7-401d-920b-d68ebcf71b34` |
| `ribbon.webp` | A receipt ribbon in the dark (spare) | `f546607b-5322-4e2c-8a44-e7014e222a86` |
| `film-paid-on-proof.mp4` | The brand film, 22 s, silent, 1280×720, 2.7 MB: receipt → stamp → PROVEN → VOID → warehouse → seal → "Paid on proof." On /manifesto, click to play | shots `f9052bbe-f545-4556-a352-c37fd2bc4849` (the strike, from still `beb5f46c-995f-4779-b859-24318aa700dc`), `8547f933-c2b3-44a5-aa2b-29e44f600490`, `72da9f32-51da-4179-ac74-d753bc0ccd7a`, `91c90609-27a6-454b-ac45-5e30654609db`, `0d83402e-4fea-48af-8012-707c55c52e0b` |
| `film-poster.webp` | The film's poster, the stamp about to strike | from the film |
| `/og.png` | The share card, rendered from `scripts/og.html` | — |

The printer still the film starts from is job `855b9fe1-772c-4b76-89c2-e74923e8ac5e`.

**Masters live outside the repo**, so git stays light: `~/Hubricon/brand-assets/`
holds the film at 1920×1080 (`film/paid-on-proof-1080p.mp4`, 9 MB), a 1080×1080 cut for
square feeds (`film/paid-on-proof-square.mp4`), the hero's source clip, and every still
at full resolution (`stills/`, 2–3K PNG). The film's supers and end card are HTML
rendered in the site's own fonts, not generated text, so they can be re-cut with new
lines in minutes (Anton, white with the key phrase in amber, bottom left).

## The founder

The founder's photograph is off the home page by decision (2026-09-25): Hubricon is
presented as a company with a method, not a person with a pitch. The founder's name
stays where the law and the terms need it (terms, privacy) and in the structured data.
Since 2026-09-30 the face is off camera everywhere (settled in `HUBRICON_SPEC.md`: the
math has no age, the brand carries the authority), so the founder's welcome video is off
/apply too (`archive/apply-2026-09-25.html`). Videos are narrated in the founder's own
recorded voice, never a clone and never a stock or AI voice (his call, 2026-10-06).

## The film's lines

1. Every move gets **a receipt.** (the printer)
2. Called **before** it goes live. (the stamp, about to strike)
3. Measured on **your own** reports. (PROVEN)
4. Short of the Record? **No bill.** (VOID)
5. Managed Profit for Amazon & Shopify brands. (the warehouse)
6. The seal, then the end card: **Paid on proof.** HUBRICON.COM

## Brand plays not yet run

Ideas that fit the system, for when there is budget and a reason. None is live.

- **The stamp in the mail.** A real steel VOID stamp sent to a short list of founders
  with one card: *"For the next invoice that can't prove itself. Ours voids itself."*
  The most Liquid Death thing a B2B service can do without losing its seriousness.
- **The Record, published.** When the first client consents, the case study section
  renders on the home page from `public_case_study()`; that moment is the brand's real
  launch and deserves its own film.
- **The Hubricon Index.** A public, dated index of what Amazon's fees did this quarter,
  built from the fleet detector and the published rate cards (see `MONOPOLY.md`,
  network effects). Owning the reference number is owning the category.
- **"Show me the Record."** The question as a campaign line, once there is a Record to
  show.
