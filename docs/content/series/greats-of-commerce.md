# The Greats of Commerce

*Hubricon's first documentary series. The series bible, the cinematography and writing doctrine,
season one's slate, and the pilot scripts. Written 2026-10-05 at the founder's request ("a document in
the project with extensive scripts … I want to begin with that series"). The scripts are drafts for
Hagen's review: nothing renders before he approves each one (`hubricon-content approve <slug>`).*

*Order of authority: `HUBRICON.md`'s honesty rules, then `HUBRICON_SPEC.md`, then
`docs/content/VISUAL_SPEC.md`, then this file, then the scripting doctrine. Every figure a viewer
hears or reads is a `{{key}}` from the episode's facts, each with its source (§3).*

---

## 1. What the series is

**The promise, in one line:** *The greats of commerce solved the problems your business has now, a
century early. Each film tells how one of them did it, finds the same mechanism inside a modern
store's numbers, and teaches the math completely.*

**Format.** Tier D: 30 to 40 minutes, VISUAL_SPEC.md's `history` mode (archival 20–35% of the
runtime, engine charts 15–25%). The scripts are Hagen's: drafted for his review, and nothing renders
before he approves each one. Narrated by Hagen in his own recorded voice (his call,
2026-10-06), off camera.

**Who it is for.** The founder doing one to forty million a year on Amazon, Shopify or both, forty
tabs open, wondering whether he can afford the next purchase order. And, because history travels, the
operator outside that niche: the DTC founder, the wholesaler, the student of business. The spec's
split holds: half of every film is universal (the story, the mechanism), half is specific (the
mechanism in today's fee cards and cash flows). Universal grows the audience; specific converts it.

**Why history.** A film about "your fulfilment fees" reaches people who already know they have a fee
problem. A film about how Sears won America reaches everyone who builds anything, and then shows
them, at minute twenty, that they have the same problem Sears had. The series turns unaware viewers
into problem-aware ones without ever pitching, which is the job of the top of the funnel.

**What every episode leaves the viewer with.** (1) A true story told better than they have heard it.
(2) One mechanism, understood well enough to see it in their own numbers. (3) A method they can run
this week, taught without a withheld step. (4) A clear sense of how deep the rest of the method goes,
and that a person who studied it runs it for a living. Never a pitch; one calm line at the end.

---

## 2. The episode architecture: how a film earns the itch

Five acts, about 35 minutes. The timings are targets; the re-hook rule is not (a new question, a new
number, a new picture or a turn at least every 40 seconds, the RE-HOOK AUDIT lists them all).

| Act | Time | Job | The viewer feels |
|---|---|---|---|
| **Cold open** | 0:00–1:30 | One moment from the past, one number, one question the film will answer. No channel intro, no "today we'll". | "I need to know how this ends." |
| **I · The world before** | 1:30–7:00 | The problem the great faced, the stakes, and what everyone in that era believed (the misconception, period edition). | "That's a hard problem. I'd have believed that too." |
| **II · The invention** | 7:00–15:00 | The mechanism, shown working: the decision, the risk, the evidence. | "That's clever, and I can see exactly why it worked." |
| **III · The turn** | 15:00–21:00 | The hidden cost, the near-ruin, the counterintuitive part: what the mechanism demanded that nobody saw. | "Wait. That's happening to me." |
| **IV · The mirror** | 21:00–30:00 | The same mechanism in a modern store's numbers (the demo catalogue, labelled), taught completely, chart by chart. | "I can find this in my own business tonight." |
| **V · The method and the honest limit** | 30:00–35:00 | What to do this week; where doing it by hand breaks; the depth it takes; the soft close. | "I could do this. I'd rather the person who studied it did." |

**The itch, built honestly.** The pull toward hiring Hubricon is never stated; it is constructed by
five devices, all true:

1. **The self-recognition beat** (Act I → III). The viewer watches a smart person in 1913 make the
   intuitive mistake, then hears the same mistake described in his own words. He recognises himself
   without being accused. The doctrine's "let them be wrong", told as history.
2. **The open loop from the cold open**, closed only in Act IV. The question asked in the first
   ninety seconds is answered in today's numbers, not in 1913's.
3. **The number he does not know about his own business.** Act IV puts a modelled figure on screen
   (demo data) that the viewer realises he could not produce for his own store tonight.
4. **The depth, shown and not claimed.** Act IV and V show the actual models working: the cash cone
   of ten thousand paths, the elasticity curve with its confidence band, the fee staircase for every
   SKU. Then one true sentence about where that comes from: *"This is applied mathematics: the same
   tools actuaries use to price risk. It's what I studied, and it's what Hubricon is built to run, every week, for every SKU."*
   Never a claim of years, clients or results that does not exist (HUBRICON.md).
5. **The honest limit.** What the viewer can do by hand (the top five SKUs, this week, worth doing),
   where it breaks (every SKU, every two weeks, with enough data to know the answer is not noise),
   and the spec's soft close, word for word: *"You can build this yourself. If you're doing real
   volume and want it run with rigor, this is what I do, and I only get paid when it works."* Then
   the free course at /learn. Every pillar closes on it (HUBRICON_SPEC.md, Content engine: name the leak,
   teach the leak, offer to handle the leak); pillars 3–5 name no product (no Managed Profit, no
   /apply, no Capital Position), which the validator enforces.

**Act IV is the conversion engine; Acts I–III are the reason anyone is still watching at minute
twenty-one.** Both must be excellent; neither may be padding.

---

## 3. Writing history honestly

The series' credibility is the brand's credibility. One wrong date in a film about precision undoes
the film.

- **Every fact has a source.** Each episode carries a facts table: key, value, label, source URL.
  Every figure, year included, enters the script only as `{{key}}` (the number guard refuses digits,
  currency signs and number words in narration). A fact without a source does not enter the script.
- **Myths are named and corrected, never repeated.** Business history is full of good lines that
  never happened. When the episode's research finds one, the script says so: correcting a myth is a
  credibility asset and often the best re-hook in the film.
- **Quotes are verbatim, attributed and dated,** shown with the `quote` style and the source in the
  attribution. Nothing is paraphrased inside quotation marks. No invented dialogue, no "he must have
  thought".
- **Reconstruction is labelled.** If a shot shows a period-like scene that is not the event itself
  (stock footage of a train, a texture), it never carries a caption implying it is the event (§6.2:
  specific things need specific evidence). Named things are shown only by archival material that
  names them, or on paper.
- **Money across a century** is stated in period dollars. A modern equivalent appears only when a
  cited source gives it (the BLS CPI calculator, a dated history), and says it is an equivalent.
- **The modern half is labelled.** The demo catalogue says "Tarnhollow demo data" on every figure;
  Amazon's fees are typeset from `ratecard.json` with the date they were recorded; no figure implies a
  client. Never Amazon's interface, never its logo.
- **Portraits of the historical subject are allowed, credited** (the founder's call, 2026-10-04).
  Living people are not shown.

---

## 4. Cinematography: how a film made from archives and charts becomes cinema

"Cinematic" is not a filter. It is intent in every frame, rhythm across the whole, and a world the
viewer believes. The pipeline already holds the instruments (VISUAL_SPEC.md §14's thirty styles, the
grade, the sound); this section is how the series plays them.

### 4.1 One object carries each film

Every episode has a **visual thesis**: a single object that the story turns on and the camera keeps
returning to. Sears: the parcel on a scale. Woolworth: the dime. Piggly Wiggly: the turnstile. The
object appears in the cold open (a slow push toward it), at the turn (seen differently), and in the
final callback (the modern equivalent, in the same framing). Three appearances make a motif; a motif
makes a film feel authored.

### 4.2 Two eras, one bridge

- **The past** is black and white, archival, still: photographs pushed slowly toward their subject,
  catalogue pages read like evidence (`archive-framed`, `doc-clipping`, `still-push`, `still-pan`), the
  depth push (W4) reserved for each act's hero photograph.
- **The present** is graded footage, bright and cool: warehouses, ports, conveyors, hands at work
  (`footage-establish`, `footage-process`, `footage-insert`).
- **Paper is the bridge between them.** The same chart is drawn over both eras: the 1913 parcel rate
  card becomes today's fee card in one `match-bridge` (the staircase shape holds still on screen while
  the era changes behind it). A cut across a century on a shape that does not move is the series'
  signature transition. One per episode, never forced.

### 4.3 The camera has intent

- Every move goes toward the subject: the slow push ends on the face, the scale, the number. A move
  that drifts toward empty sky is a failed shot.
- **Pans mean scale** (the catalogue's pages, a warehouse aisle, a row of stores). **Pull-backs mean
  one becomes many** (one price tag, then the shelf of ten thousand). **Holds mean listen.**
- Within a world sequence: wide, then medium, then detail. Goods move left to right across cuts.

### 4.4 Rhythm across forty minutes

- **Cold open:** dense. Shots of three to six seconds, a number every fifteen, the question landing on
  a hard cut to black-on-paper.
- **Act I:** settle. Longer archival holds while the narration builds the world (the founder's "ten
  seconds and that's okay"): something always moves, nothing is frozen.
- **Act II:** build. The process sequence, the document highlighted at its line, the first chart.
- **Act III:** tighten. Shorter shots, the turn spoken over a single held image, then a **breath**:
  two seconds of no voice, the bed rising. This is the film's emotional peak.
- **Act IV:** the classroom. Chart builds up to thirty seconds with something new every eight; the
  counterfactual; the range band. Calm, exact, generous.
- **Act V:** the return, then the close. The callback to the object and the thesis line come first; the honest limit and the spec's soft close are the film's last words, over the end card (HUBRICON_SPEC.md: every piece ends on the soft close).

### 4.5 Sound is half the picture

- **Era ambience under the archive:** a rail yard, a sorting room, a cash register, a crowded store.
  Generated once per subject and cached (`audio.py`, −40 dB), never under paper.
- **The bed family:** a different cue per act from one family (sparse piano, low strings, no melody),
  crossfading under the chapter cards. A licensed family replaces the generated bed when the founder
  supplies it.
- **Silence before the turn.** The bed drops out a beat before Act III's key sentence. Nothing in a
  documentary is louder than a pause.
- **Ticks under data:** every figure that lands on paper gets the soft tick, so the numbers have a
  physical feel.

### 4.6 Typography as cinema

Chapter cards are act titles: one hairline, two to four words, the act's question rather than its
topic ("What a pound cost", not "Chapter 2: Parcel Post"). The thesis line (`kinetic-thesis`) appears
once per act at most, in the narration's exact words.

### 4.7 What cinematic is not

No film burns, light leaks, sepia, colourised photographs, whip pans, zoom punches, drone skylines,
stock clichés or generated video (VISUAL_SPEC.md §14.7). Those are what cheap documentary channels use
in place of intent.

### 4.8 Production upgrades that would lift the whole series (proposed, not yet built)

1. **A 4K master** (2160p): YouTube encodes 4K uploads at a higher-quality codec even for 1080p
   viewers; the footage is mostly 4K already; the stage renders at twice the scale. Two to three times
   the render time.
2. **The depth push (W4)** for each act's hero photograph: the strongest single signal of a crafted
   archival film.
3. **A licensed bed family**, five or six cues, one per act.
4. **The map** (VISUAL_SPEC §8.1, deferred): routes drawn in ink, the leg that costs money in blue.
   Parcel post zones, Woolworth's spread, the supply chain from factory to shelf all want it.
5. **A subject screen in sourcing**: a local vision model ranks candidates by the sentence's nouns and
   flags sensitive subjects and logos before the pick (the visual trial's sourcing passed material the
   pick had to refuse by eye).

---

## 5. Season one: the slate

Twelve films. Each takes one great, one mechanism and one modern leak. The first three are written in
full below; the rest are treatments, to be researched and written in the same way.

| # | Title | The great | The mechanism | The modern leak | Pillar |
|---|---|---|---|---|---|
| 1 | **What One More Ounce Cost** | Sears, Roebuck; Rosenwald; the 1913 Parcel Post | A delivery price that climbs in steps by weight and distance | Fulfilment fees charged in weight steps: the staircase | 1 · the money you can't see |
| 2 | **The Dime** | F. W. Woolworth | A fixed price point decided first, products made to fit it, and the ceiling that inflation broke | Price points and thresholds; pricing by elasticity, not habit | 3 · pricing |
| 3 | **The Corner** | Clarence Saunders, Piggly Wiggly | A profitable business undone by cash with a date on it | The cash conversion cycle; the trough on day N | 2 · capital and cash |
| 4 | **Money Back** | Aaron Montgomery Ward | Trust at a distance: the guarantee that made buying from strangers safe | Returns, reimbursements and the claims nobody files | 1 · the money you can't see |
| 5 | **Which Half** | John Wanamaker | The price tag, the department store and the advertising dollar nobody could measure | Ad spend measured honestly: isolated, attributable, unknown | 5 · operator's math |
| 6 | **The Price That Fell** | Henry Ford's Model T | Cutting price as volume rose, and when that stops working | Elasticity: when a price cut pays and when it only feels like it does | 3 · pricing |
| 7 | **The Supermarket in Toyota City** | Taiichi Ohno and the American supermarket | Replenish what sold, not what was forecast (kanban) | Reorder points, service levels and the newsvendor | 2 · capital and cash |
| 8 | **The Satellite** | Sam Walton | Distribution centres, cross-docking and data as inventory | Inventory turns, aging stock and the long-term storage cliff | 2 · capital and cash |
| 9 | **Paid Before It's Built** | Build-to-order computing | A cash cycle that runs negative | Cash conversion as a strategy, not an accident | 2 · capital and cash |
| 10 | **The Markup Cap** | Costco's membership model | A capped markup and a fee that carries the margin | Contribution margin by SKU: the bestseller that loses money | 5 · operator's math |
| 11 | **The Razor Myth** | King C. Gillette | The razor-and-blades story, and what actually happened | Loss leaders that never lead anywhere | 3 · pricing |
| 12 | **The Chain** | The Great Atlantic & Pacific Tea Company | Thin margins at enormous volume, and the backlash | Unit economics at scale: what volume hides | 5 · operator's math |

*Episode 9 tells a modern company's story through public filings and press, with no living person on
screen. Episode 11 is built around a myth corrected (the research begins with the economic history of
Gillette's pricing before and after the 1921 patent expiry).*

---

## 6. The pilot scripts

The full scripts live in [greats-of-commerce-scripts.md](greats-of-commerce-scripts.md): every hook,
every line of narration with its figures filled in, the picture brief under each beat, and the facts
table with each source. `hubricon-content series-doc` renders that file from the units, which are the
truth (`content/videos/greats-*/script.md` and `history.json`); edit a unit, never the rendering.
Each pilot validates clean against the tier-D guard: no typed number, no banned phrase, a `{{key}}` in
every hook's first sentence, a re-hook at least every 40 seconds, one close, and a data source on
every chart.

### Pilot 1 · What one more ounce cost (pillar 1, about 32 minutes)

`greats-01-sears-parcel-post` · 4,692 spoken words · 49 beats · 147 sourced history facts, plus the case study's and the demo engine's figures.

| Act | Time | What happens |
|---|---|---|
| Cold open | 0:00–1:13 | Baby James Beagle mailed for 15 cents, against regulations, a figure that is exactly the 1913 card's local rate for an 11-pound parcel. The question: what does one more ounce cost? The viewer is asked to guess (most guess a sliver), and the guess is paid off at the fraction. |
| I · What a pound cost | 1:17–6:10 | Mail at $320 a ton against freight at $1.90; Rural Free Delivery brings the mailbox but not the parcel; the express lobby; Wilson at Gloucester; the catalogue telling farmers to split a freight minimum; Sears, Roebuck, Rosenwald. |
| II · The machine before the card | 6:15–10:15 | The West Side plant and Doering's fifteen-minute schedule, which took years to bed in; the sewing machines shipped five times; the guarantee that refunded transport. |
| III · The staircase / who paid for the ounce | 10:19–19:52 | The midnight cups; the Act's "fraction of a pound"; the flood of parcels; the catalogue's own postage cut from 24 cents to 10; the turn (customers paid the postage, so they could see the card); the farmer's pencil worked through; Bavaria, Kansas; the card that could redraw itself; the myth of "five times the orders" corrected against the audited accounts. |
| IV · The card you pay now | 19:56–27:46 | The USPS ground card's one-pound riser; the FBA weight steps; the case study's listing a fraction of an ounce over a line ($6,400 to $19,200 a year, an estimate); where the card went (the moment of decision); the other staircases (price bands, dimensional weight, the day-271 storage cliff); how to find your steps; where the staircases meet. |
| V · The method and the honest limit | 27:46–30:00 | This week's worksheet; where by-hand breaks; the soft close; the Fee Staircase course; the return to the 15-cent parcel. |

Object: the parcel on a scale. Bridge: the 1913 rate table holds still while today's card replaces it.
Myths corrected on screen: Sears invented the money-back guarantee; parcel post built the Sears
machine; "five times as many orders"; the staged babies-in-mailbags photographs.

### Pilot 2 · The dime (pillar 3, about 29 minutes; title: "Woolworth's Kept Its Dime Ceiling for More Than 50 Years. Here's What It Never Told Them")

`greats-02-the-dime` · 4,233 spoken words · 44 beats · 118 sourced history facts, plus the demo
engine's elasticity and price-move figures.

| Act | Time | What happens |
|---|---|---|
| Cold open | 0:00–1:24 | Lancaster, June 21, 1879: a circus parade, seven clerks, $127.65 in 2,553 nickel sales. The question: what could one price never tell him? |
| I · One price | 1:27–5:35 | The clerk; Moore's five-cent table (he ran it, he didn't invent it); Utica's failure and "take my store to the people"; the charm of one price; the 25-cent test he ran once and dropped; the chain. |
| II · Price first | 5:38–11:17 | The arithmetic of a nickel: a gross at $7.20, and the margin that changes under every line; the one-price store as a portfolio; cash and the auditors; the ring redesigned to sell at a dime; "throw the toys in vats"; the price as the advertising; "Profit is what we are working for, not sales or glory"; the Cathedral of Commerce. |
| III · The ceiling | 11:20–18:37 | Holding a dime through the war by shrinking the unit (one stocking for ten cents); net earnings from 9.43% to 5.46% of sales, with the tax and the reserve stated; the West's 15-cent ceiling (a different price in a different place is not a price test); profit per store halved; the 1932 test in some stores, in deflation, not inflation; the promise of January 1933, broken within three years. |
| IV · Your dime | 18:26–26:20 | The price you set once and left; elasticity shown on log scales, then named, with the worked product's own slope (−7.35) pulled toward the catalogue's (−2.76); why a raise that loses units can pay (how many you can afford to lose is the margin, how many you will lose is the slope), and what minus one means; the hill, whose top the model will not mark for any demo product; the products the fit refused; the honest range, which crosses zero; why movement, not months, narrows it; how to step when you can't see the top (work it out at the estimate and both ends of the range; agree, step; disagree, step small); when the answer is hold: on the demo the model puts 97% on the prices already being about right and recommends no step, a verdict it can give only for products whose prices moved, never for the dimes; when the price is the brand; testing in time. (The engine's earlier confident up-steps came from a cost-basis mismatch in its already-optimal prior, fixed on main as MATH_SCORECARD iteration 41; the film speaks the fixed engine.) |
| V · The method and the honest limit | 26:20–29:20 | This week's steps, the course's whole method (units a day, the 2% rule, the log fit and its range, the minus-one rule, the best-price formula, a predicted step, watch and reverse); the return to Lancaster ("Your prices can."); where by hand breaks; the soft close; the Price Curve course. |

Object: the dime, pushed toward three times (its face, its edge at the turn, its date at the lesson),
then a modern shelf label in the same framing. Bridge: every item in the store on a single vertical
price line, while a modern catalogue's own price curves rise around it. Myths corrected on screen:
Woolworth invented the nickel counter; nothing ever cost more than a dime; inflation broke the dime.

### Pilot 3 · The corner (pillar 2, about 28 minutes)

`greats-03-the-corner` · 4,027 spoken words · 42 beats · 101 sourced history facts, plus the demo
engine's cash-horizon and risk figures.

| Act | Time | What happens |
|---|---|---|
| Cold open | 0:00–1:40 | 11 a.m., March 20, 1923: Saunders fires Livermore by telegram, calls 42,000 shares, the stock runs from $75.50 to $124. That August: "I am unable to get cash on this stock." The question: how does a man who owns nearly all of a profitable company lose it? |
| I · The turnstile | 1:43–4:59 | The grocer who knew the supply side; counter service; the 1916 opening (staff "politely refused to select merchandise"); the turnstile and the patent's "required to review the entire assortment"; not the first self-service store, the one that spread. |
| II · The machine | 5:03–7:15 | The business, name and patent sold for $550,000 and stock; licensing for a royalty; the stores company listed in 1922 to retire its bank loans; profit up from $208,662 to $653,058; a grocery as a cash machine. |
| III · The corner and the date | 7:19–18:31 | Short selling explained; the raid; $10 million raised, secured on the stock; the Corporation's cash ($967,016 to $22,724) turned into stock; the instalment plan and its due dates; corner day; the delisting, with both sides of the deadline dispute; the settlement at $100; the trap that closes on both sides; the calendar (September 1, $2.5 million); the stores shrinking; resignation, Detroit, bankruptcy; the Pink Palace (his creditors took it); Time's "cemetery at one end and a river at the other". |
| IV · Your calendar | 18:40–25:13 | Profit is about a month, cash is about a day; the demo catalogue, profitable and holding more than eight months of fixed costs: is it safe? (the viewer commits); the trough of $85,242, 13 days out, set by ten wires that leave today; the clocks of the cash cycle, with the course's 21 days from a sale to the bank; the same low point on every one of 10,000 paths, because it falls before the next payout; Saunders' September in a modern catalogue (one payment a little over the trough, due that day, breaks every path; the same payment on the last day comes out of a balance above $323,149 on all but the worst twentieth); why months-of-expenses rules miss it; the levers, each a date. |
| V · The method and the honest limit | 25:13–28:00 | This week's day-by-day calendar and "what single payment would break me?"; where by-hand breaks; the soft close; the Capital & Cash course; "Find your date." |

Object: the turnstile, pushed toward in the cold open, seen as a trap at the turn, and returned to
at the end beside a modern calendar page in the same framing. Bridge: a single cash line across a
calendar holds still while 1923's due dates become a modern catalogue's supplier wires. Myths
corrected on screen: Saunders invented the supermarket; Livermore was a short seller; Saunders gave
the Pink Palace to Memphis. The corner took a week; losing the company took five months.
