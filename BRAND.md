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
Hormozi standard (one action, under ~900 visible words; 822 on 2026-09-30, counted by
`scripts/build-home.mjs`).

## Positioning

For private-label brands doing $1M–$30M a year on Amazon and Shopify (the band since
2026-09-27; it was $3M–$20M), who have no
finance function and five tools that report but never decide, Hubricon is the only
service that makes the money decisions inside the account and is paid only on proof:
each move called in writing before it goes live, measured on the owner's own reports,
and no invoice until the Record covers it.

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
has a private palette (`scripts/build-home.test.mjs` fails the home page if it tries).
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

One sans, two weights: **Inter** 400 and 600, from Google Fonts. Headlines at -0.032em,
balanced. Every number tabular (`font-variant-numeric: tabular-nums`) on figures, money,
charts and every `data-fill` value, but not on prose: Inter's tabular feature also widens
the hyphen, and "founder-operated" would read "founder - operated".

### Space and layout

One spacing scale (4, 8, 12, 16, 24, 32, 48, 64, 96, 128 px), one content width (1120 px),
one radius (10 px). One idea per screen. No navigation on a funnel page: the wordmark,
the content, one button. The button is ink, always reads **Book your call →**, and always
goes to `/apply`.

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

Every chart is baked into the page as its finished still frame (`scripts/build-home.mjs`),
so a visitor without scripts sees the result. Line weights, the band's wash and timings are
tokens (`--line-*`, `--mc-*`).

### Motion

One draw-in, then still. A chart plays once when it scrolls into view: paths sketch in
left to right over about two seconds on an ease-out, fade back to almost nothing, then the
band fills over 0.4 s. It never loops and never asks for attention again. Under
`prefers-reduced-motion`, or when the page's script never arrives, the still frame is all
there is.

### Labels that never come off

Every proof screen carries **Modeled from public data · Not a client · Not a result**.
Every estimate says "estimate" beside it. Ranges, never points, rounded down. An
illustration says it is one.

## Retired 2026-09-30: the night system

From 2026-09-25 to 2026-09-30 the site ran on Night `#050A1F`, Signal amber `#FFC000`,
receipt paper, Anton and IBM Plex Mono, with the stamp, the seal, the receipt and the
low-key still life as its icons. The spec retired it for the funnel ("the Rockefeller
reading a ledger feeling"). The old home page and /apply are in `archive/`; the full
description is in this file's git history (`git show ea46b1b:BRAND.md`). /manifesto,
/method, /portal, /results and /intake still wear it until they are rebuilt on the tokens,
which is why the asset inventory below is kept.

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
/apply too (`archive/apply-2026-09-25.html`). Videos use the founder's voice, recorded
first and later an ElevenLabs clone trained on those recordings, never a stock voice.

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
