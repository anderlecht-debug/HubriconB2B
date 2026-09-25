# The Hubricon brand

*The brand system, for whoever touches a page, an email, a deck or an asset next.
Read `HUBRICON.md` first: the honesty rules and the vocabulary there bind everything
here. Written 2026-09-25, when the founder's photo came off the home page and the
brand replaced it. The strategy it serves is in `MONOPOLY.md`.*

---

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

The offer headline stays the offer: *More profit than our bill, every month. Or you
don't pay.* The brand line sits above it as a stamp; it never replaces it. The home
page is still judged by the Hormozi standard (one action, under ~900 visible words,
820 on 2026-09-25).

## Positioning

For private-label brands doing $3M–$20M a year on Amazon and Shopify, who have no
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

- Short declaratives. Numbers before adjectives. A figure always says what it is
  (our price, a vendor's price list, arithmetic from a named source, demo data).
- Contempt for vagueness, never for people.
- No hype words: revolutionary, unlock, leverage, game-changer, AI-powered, supercharge.
- One dry line per page, at most. The stamp is funnier than any joke.
- Future things in the future tense, labelled. Nothing is described as live until it
  is live in production (the manifesto's section V carries a "not live yet" tag and a
  footer line for exactly this reason).
- HUBRICON.md's retired words stay retired: desk, ledger, quantitative, retainer,
  engagement, directive, and the rest of that list.

## The visual system

### Colour

| Token | Value | Role |
|---|---|---|
| `--bg` Night | `#050A1F` (hsl 225 72% 7%) | Every page's ground |
| `--band` / `--raise` | hsl 224 62% 10% / 224 58% 13% | Alternating bands, cards |
| `--amber` Signal | `#FFC000` | The only accent: CTAs, the called number, PROVEN, the mark |
| `--paper` Receipt | `#F2EDE3` | Receipts only |
| `--paper-ink` | `#16181F` | Text on paper |
| `--void` Stamp red | `#CF3B2D` (on paper), `#FF6B5A` (on night) | VOID, a loss, a "No" |
| `--ok-ink` / `--ok` | hsl 152 62% 28% / 152 55% 52% | A measured gain, on paper / on night |

Amber is the only solid fill that isn't paper. Red appears as ink: a stamp, a negative
figure, a ✕. The one exception is older than this system and kept: the 90-second
demo's red button on /results, which appears only once that video exists (HUBRICON.md,
"How customers arrive").

### Type

- **Anton** — the stamp voice. Headlines, numbers, the wordmark. Always uppercase.
- **IBM Plex Mono** 400/500/700 — the receipt voice. Everything else. Loaded from
  Google Fonts on the home page, /apply and /manifesto (the other pages still use the
  system monospace stack; move them over when they are next edited).

### The mark

An amber ring with a geometric H: the seal, and the zero you pay until it's proven.
The wordmark keeps the amber O. In code:

```html
<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>
```

The favicon is the same mark on a Night rounded square (every page's `<link rel="icon">`).

### The seal

The mark inside a ring of text, *PAID ON PROOF · PROVEN OR VOID · CALLED BEFORE ·
MEASURED AFTER ·*, turning once a minute (still under `prefers-reduced-motion`). Used
at the hero's corner and above every closing call to action. Inline the SVG; styles
cannot reach inside a `<use>` clone, which is why the text once rendered black.

### The stamp

Anton in a double border, rotated a few degrees, with a speckle mask so it reads as
ink (`.stamp` plus `.amber`, `.void` or `.ok`). Words it may say: PAID ON PROOF,
PROVEN, VOID, VOID UNLESS PROVEN, 24 HRS. Nothing else; a stamp that says anything is
a sticker.

### The receipt

Paper, Plex Mono, dashed rules, dotted leaders, a zig-zag torn edge (a conic-gradient
mask), a stamp in its own foot row so it never covers a figure. Every receipt that
shows numbers is labelled **Sample** and **Demo data**. It is the product made
visible: every move gets one.

### Imagery

Low-key still life. Midnight-navy shadows, one warm amber key light, paper and steel,
shallow depth of field, film grain. No people, no hands, no logos, no screens, no
legible text unless the word is the point (PROVEN, VOID). The client's world
(inventory, boxes, the warehouse) at night; the instruments of proof (the receipt,
the stamp, the seal, the caliper) up close. Every photograph is an illustration and
the page says so.

Prompt recipe (Higgsfield, `gpt_image_2_5`, quality high, 2k): *"[subject]. Low-key
studio lighting: one warm amber key light (#FFB300) from the right, deep midnight
navy-black (#050A1F) shadows. Shallow depth of field, 85mm, subtle 35mm film grain.
Restrained, premium, like a product film for a precision defense-technology company.
[Composition: subject right, dark negative space left, if it will carry type.] No
people, no logos, no legible text."* Films: animate the approved still with
`kling3_0`, mode pro, sound off, 8 s, start image = the still's job id; then loop it
by cross-fading the last 1.5 s into the first (the command is in the commit that added
`brand/hero-printer.mp4`).

### Motion

One film (the hero) and one slow rotation (the seal). The film plays only on screen,
never under reduced motion or Save-Data, and its poster is its own first frame, so a
visitor who never gets the film sees the same picture, still.

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
stays where the law and the terms need it (terms, privacy) and in the structured data. The /apply
video is still the founder's own welcome when a visitor presses play; its poster is
now the brand still. When the founder page arrives it lives at its own address and the
home page links to it, once.

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
