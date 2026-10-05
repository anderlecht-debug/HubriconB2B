# Hubricon: brand, funnel and case study

Sep 27, 2026 · @Hagen Simmons

Tonight settled three things: the brand is precision in service of trust, the funnel opens with a leak computable from public data and closes on the call with the leaks that need exports, and the first proof asset is a clearly labelled public-data case study. It is written to be handed to Claude Code whole: the next section says how to treat it, and the landing page is specified section by section as the first build target.

## How to use this doc (for Claude Code)

This doc is the source of truth for the Hubricon rebuild. Where it and the repo disagree, this doc wins. Read it whole before editing code.

- **This doc wins over the repo.** Where the doc and the existing code disagree, the doc is right; the repo is last September's thinking. **Scope and order:** rebuild `index.html` first, then bring `results.html`, `portal.html` and `intake.html` onto the new design system. `teardown.html` is not rebuilt, it is archived (see below). The engine and terms are untouched except where a section names them.
- **Design system:** one shared stylesheet of tokens (colour, type, spacing, radius) from the Visual direction and Landing page sections; every page consumes it. No page keeps a private palette.
- **Archive, don't delete:** move superseded pages and copy to an `/archive` folder. Superseded: `teardown.html` as a page (the per-prospect Teardown is killed), the Anton-and-Fraunces styling, the serif ledger look, any Sample or demo-data badges, and every free-Teardown-first CTA in `index.html` and the cold copy. Preserve the engine, the terms, the attribution logic, and the fee and rank computation inside `teardown.html`, which the case study reuses.
- **Honesty rails:** the results wall reads zero until a real result exists; every case-study figure is labelled an estimate; no testimonial or logo until one is real. Non-negotiable.
- **Open decisions** are the only blanks; leave a marked `TODO` in code rather than guessing.
- **Done, phase 1:** one landing page that states the offer, plays the one video, shows the public-data proof with the Monte Carlo animation, and books a call, responsive, no placeholder copy. Explicitly out of phase 1: `/learn`, the portal scoreboard, `results.html` and `intake.html`, those come after the landing page is live. Build the Monte Carlo against its sample JSON so the page is finishable before the case study brand is chosen.

## Amended by the founder (2026-10-01)

Decided by Hagen Simmons after the first build of the landing page, in his words, and carried through the repo. Where these lines and a line below disagree, these win. The honesty rails above are unchanged.

- **Tabs on every page.** "We are mimicking Apple's .com with the education tab." The landing page and every public page carry one bar: Proof, How it works, The offer, Results, Education, Trust, and the call. This replaces "No navigation bar" and "no navigation on the funnel page". The call stays the only button; `/apply` keeps no bar.
- **The education library on the landing page,** "the way Alex Hormozi has it on acquisition.com". Courses not yet made appear too, "so that we have the empty space where we can just plug in the videos eventually": each is labelled Planned, links nowhere and names no date, and a live course is still one that exists in full. This replaces "Do not add a course preview to the landing page", "linked from the footer only" and "No card for anything not yet built". The one-video rule becomes slots: the case-study film keeps its place in section 4, and every course and lesson has a slot that says what will play there until it does.
- **Trust and testimonials, shoved in their face.** A trust section names where every promise is written down, and a results wall with a frame for each client's words and Record. It reads zero, and says so, until a real client consents; no testimonial is written for anyone.
- **Everything on the page.** "The education tab, the courses, the legal stuff, everything needs to be on that landing page", with the animation: each section and number arrives once, then stays still. The 900-word cap is retired.
- **The email capture where Hormozi has it** (later the same day): "the email capture where Alex Hormozi has it... on the education section it should be built pretty much the same". On acquisition.com the free training opens with a featured card that asks for one thing, "Free. Takes about 30 seconds." So the landing page's Education section opens with the live course as that card, one email field on it. It is the same capture as the course page's (one address registers you for the course, everything inside open), not a second one, and its button is the field's, an outline; the call stays the only solid button.
- **Every lesson open, the email an opt-in** (later still, 2026-10-01): "I want the lessons to be open to everybody as that is the free content that I am giving. Of course, if they want a little bit of extra, they can opt in the email." Every lesson and every spreadsheet opens with no email and no account. The email is the opt-in for the extra: the link and the spreadsheet in your inbox, then a short note only when Amazon changes its fee cards or a new course opens. It sits on the featured card, under each course's start and at the end of its last lesson, marked Optional, with the field's own outline button. This replaces "Email to enter", "One email enters a course", "a single email to enter each course", "the email is the price of admission" and "What they get for the email is the entire course" below, and the line above where the card's email "registers you for the course". The generosity is now total without the email: nothing is held back, and nothing waits for it.
- **Shopify sellers on every page** (2026-10-01): "go deeper on the whole Shopify level because a lot of it's just Amazon. And the copy might just … show Shopify people that they're not welcome here … because nothing shows it." So the fear headline drops the platform ("Your P&L is an average. Your losses are hiding in the steps."), the problem screen says both halves of the line below ("On Amazon, the cliffs are imposed on the seller. On Shopify, the seller built them."), the staircase section draws Shopify's step too (USPS's published pound lines), the FAQ answers a Shopify seller directly, and every course says whom it is for. Nothing claims for Shopify what the product does not do today: claims and Amazon's fee cliffs stay Amazon's.
- **The motion felt, and the site answers back** (2026-10-01): "the animations still need to actually be animated as per the spec says … making the site more interactive with those animations, and answering the questions that need to be answered by a potential customer." So every chart a reader studies can be scrubbed for its values, a visitor who asked for less motion gets a dissolve instead of nothing, and the FAQ answers what a prospect asks before booking: Shopify, their time, access, finding nothing, agency or dashboard, who it is for.
- **A short first page; the proof, a real store's own orders** (2026-10-01, evening): "Right now I'm scrolling way too much … a short first page, not a lot of scrolling. Everything they need to know is on there. And then all the other information about the business on the tabs and the education … utilizing that white space. That results page does the opposite of what we want it to do right now. We can add it later, but right now it only hurts us. Like what the spec says, we need to find a business's data that's open, run it through the engine, and then design it in a way that shows that we give results. Your job is to choose that company, find the data on your own." So the landing page is five bands: the promise, the proof, the offer with its three steps, the free library as a strip of covers, and the call. Every other section has a page under its tab, in the spec's order: **Proof** is /case-study (both studies, the problem and the staircase with them); **How it works** is /how-it-works (the steps, the Profit Record, who runs it, the questions); **The offer** is /offer (the creed, the four layers of the guarantee, where every promise is written down); **Education** is /learn, where the optional email lives; **Trust** opens the pages that say it. The Results tab and the results wall leave the bar and every page until a client's consent fills a frame; the wall's code stays, and /results still goes to /honesty. The proof became a real store's own orders because Amazon now answers automated reads with "Continued access by an unauthorized AI agent violates Amazon's Conditions of Use", so no brand's whole catalogue is read live (the founder chose the open data on 2026-10-01): "Online Retail II", every order a UK online retailer took from December 2009 to December 2011, published by the UCI Machine Learning Repository under CC BY 4.0. The engine, unmodified, calls what comes next from the orders before a cut-off, and the store's own later orders measure each call, misses included: repeat customers at the engine's own calibration cut-off, the regulars it names as slipping away, and peak-season demand a month ahead. It is labelled "Modeled on published data · Not a client · Not a result", it never claims profit (the data has no costs, ads or stock), and it publishes no price finding (a wholesale price falls with order size, so its elasticity would measure the discount, not demand). The one-listing Amazon study stays, second, on /case-study. This replaces "Results" in the first line above; "the home page adds the trust section, the results wall and the education library"; "Everything on the page" and the 900-word cap's retirement (the home page's own words are capped again, by `scripts/build-pages.test.mjs`); the featured card's email "on the landing page"; "One page, no nav" and sections 2, 3, 5, 7, 8 and 9 of "Landing page, section by section" (moved, not cut); and, for the proof's lead, "one listing" in "The public-data case study".
- **The LLC is formed with the first client's payment** (2026-10-02): "it's standard practice for me bootstrapping this business to wait until I get that first payment and then instantly I need to take however much it costs to form that LLC and do it right away with the client's money … the spec says otherwise so just take my word over that for now." So Hubricon trades as a sole proprietor until the first payment lands, and the LLC is filed from that payment, at once. This replaces "the LLC is formed before that first engagement actually starts, never after" in "Money handling, structure and billing" and "The LLC must exist before that first signature" in "The contract". Nothing on the site names an entity it does not have. The attorney's one review of the guarantee and the liability limit is unchanged.

## The spine

Hubricon stands for precision, and what the buyer is actually paying for is trust with someone close to their money. Every decision gets one test: does this make me more trustworthy to a skeptical operator, or less?

## The offer through Hormozi's value equation

Study the people who have done it at scale and reverse-engineer what worked. Hormozi's value equation is the backbone here: value equals the dream outcome times the perceived likelihood of achieving it, divided by the time delay and the effort and sacrifice. Raise the top, shrink the bottom, and you build an offer people feel stupid saying no to. Hubricon is not selling financial math; it is selling a grand slam offer whose product happens to be precision. All four levers are already in the business, and naming them tells us where to push.

- **Dream outcome (raise it):** not "more profit" in the abstract, but the specific dollars leaking out of one SKU while every tool and advisor says the account is fine, e.g. the eleven thousand a year a single weight-band edge quietly costs. Always name the dollars on their own listing, on a named SKU; the more specific and visceral the number, the higher perceived likelihood climbs. Vague is the enemy of belief.
- **Perceived likelihood (the strongest lever, push hardest):** this is where most competitors are weakest and Hubricon is built to win. The "more profit than our bill or you don't pay" guarantee drives belief toward certainty; the public-data case study, the honesty that about half of prospects show nothing, and the attribution engine grading every dollar all exist to make them believe it will actually work. Every proof asset serves this lever.
- **Time delay (shrink it):** the first piece of content they see names a dated leak on their own listing, and the scoreboard shows profit every week. Compress the time to first visible proof at every step.
- **Effort and sacrifice (pin to the floor):** they hand over exports once and Hubricon runs everything. Near-zero effort on their side is a feature to state out loud, not assume.

**The multiplier: honest scarcity and urgency, stated like a firm, not a store.** Hormozi treats scarcity and urgency as multipliers on the whole equation, and Hubricon has both built in, honestly. The rule is to never announce them; state them as facts of how the practice operates, the way a luxury firm does. Scarcity: the work is done personally, so the practice takes a limited number of engagements at once, said plainly, never as a countdown or a "spots left" badge. Urgency: every unsealed leak is losing money right now, every day it stays open, which is a permanent fact of their economics rather than a calendar date — the cost of waiting is real and ongoing, never a countdown Hubricon invents. Where a specific dated fee step happens to be live, it is named as a fact of their economics, never as a deadline to act before. No "act now," no timers, no e-commerce furniture. The restraint is what keeps it reading as a high-ticket B2B practice rather than a store.

The test for any new page, email or feature: which lever does this move, and does it move it up? If it moves none, cut it.

## Proof: the ladder

Proof is the perceived-likelihood lever, the one Hormozi weights highest, and it is the hardest problem from a standing start: zero clients, so no conventional proof exists. The skeptic does not want testimonials, they want to watch Hubricon be right. So the entire proof strategy is demonstrated competence, not claimed results. Everything in the funnel exists to climb this ladder, and the rungs stack: until the top rung exists, every lower rung over-delivers to carry the weight.

1. **The public-data case study (weakest, available now).** Proves Hubricon can find the leak. Built only from a brand's public pages, labelled an estimate on every screen. It is the floor, not the ceiling.
2. **Showing the work in public (the content engine).** A skeptic who watches Hubricon teach a method they can verify starts trusting before a call ever happens. Teaching the exact method, completely, is proof precisely because it is checkable.
3. **Real client scoreboards (strongest, the goal).** The moment a client exists, their real attributed dollars, graded by the engine, become the proof everything else was standing in for. This is where the results wall stops reading zero.

**The honesty move is itself proof.** Saying out loud that about half of public-data models find nothing, and turning that business away, is evidence of confidence in the method. Only someone sure of their work refuses work. Keep it on the page; it does more for perceived likelihood than any testimonial could at this stage.

**Rule:** no rung claims more than it has earned. No testimonial, client logo or dollar result appears until it is real (the repo's existing honesty rail). The ladder is how Hubricon has powerful proof while the top rung is still empty.

- **Feeling in the first three seconds:** excitement and relief. It comes from clarity and exact numbers, never hype or exclamation marks.
- **The enemy, named from the buyer's chair:** the guru who sells a course, the agency that sends a dashboard of nonsense, the gut-feel advice with no math behind it. Hubricon is the calm adult in a room of shouting salesmen.
- **Voice:** cold, matter-of-fact, a little unbothered. A doctor reading a scan, not a closer.
- **Signature line:** "Your mental model is linear. Amazon's cost structure is a staircase."
- **The line that removes the shame:** "A P&L is an average. A cliff is only visible as a counterfactual, and no report anyone sells contains one." That is why five tools, a PPC agency and a bookkeeper all miss it at once.
- **Commitment (the Liquid Death lesson):** pick one identity and never break character. Precision everywhere, including typos, spacing and animation polish.
- **Face:** off camera. The math has no age; the brand carries the authority.
- **Honesty as an asset:** about half of cold prospects produce no findings. Say so out loud. A "nothing here" makes every "here it is" believable.

## Visual direction

The decision tonight is a pivot from the repo's current look: from dark, gold and serif to bright, one-accent fintech. Think a quant fund or Stripe, not a private bank. The serif-and-gold pages (the portal's "Private Desk" style, the results page) are the likeliest source of the "Rockefeller reading a ledger" feeling.

| Element | In the repo today | Decided tonight |
| --- | --- | --- |
| Base | Deep navy `#050A1F` on index and intake; white paper with navy ink on the portal | Bright white base, a lot of air, dark sections only for rhythm |
| Headlines | Anton, condensed uppercase | One clean sans-serif, two weights |
| Numbers and titles | Fraunces and Iowan Old Style serif (portal, results) | The same sans with tabular numerals |
| Accent | Amber `#FFC000` | One sharp, cold electric blue, used only on money and the leak. Cool reads as a precision instrument; warm reads as retail urgency, which the skeptic distrusts. |
| Imagery | Data charts on demo data | Data visuals only; no stock photos, no people shaking hands |
| Signature visual | Monte Carlo chart in the inventory section | Monte Carlo paths drawing in and settling, as an accent below the offer |

Layout rules that carry the luxury feel:

- One idea per screen; nothing fights for attention.
- No navigation on the funnel page; the only thing to click is the call.
- Spacing on one scale everywhere. Uneven padding is the fastest tell of an amateur page.
- The animation sets the mood and never competes with the headline or the button.
- Rebuild the tokens once in a shared stylesheet, then apply them to `index.html` first. The other pages follow after the landing page ships.

## Landing page, section by section

This is the top of the funnel and the most important page. It has one job: a skeptical operator lands, feels excitement and relief in three seconds, and books the call. One page, no nav, one button repeated. Build it top to bottom in this order.

Global rules for the page:

- No navigation bar. The only actions are book-the-call and, optionally, watch-the-video.
- The call to action repeats after each proof block, always the same words and colour.
- One accent colour, used only for the money and the leak. Everything else is ink on white.
- Every number tabular, every claim specific, no adjectives doing a number's job.
- Dark sections separate acts, never decorate.

**1. Hero, above the fold.** The hero opens on the after-state, not the category — the first thing the page says is what becomes true for them, so a qualified operator feels recognition in the first second: *this is what I have been looking for*. Working headline is the outcome and the guarantee in one breath, "More profit than our bill every month, or you don't pay." A/B it against the certainty line "Always know exactly where your money is made and lost — or you don't pay," and against the fear line "Your Amazon P&L is an average; your losses are hiding in the steps." The subhead does the qualifying quietly, so it filters the right operator without ever becoming the pitch: for Amazon and Shopify brands doing $1M to $30M. Do not put the category — the software, the desk, the financial-math label — in the headline or subhead; the box is not the value, and leading with it kills the recognition. One button, book the call, no competing link. The Monte Carlo animation draws in once and settles behind or beside it, muted, text crisp on top. No stock imagery; the data is the image.

**2. The problem, named precisely.** One screen that makes them uncomfortable about their own numbers, in the clinical doctor-reading-a-scan voice: their mental model is linear, Amazon's cost structure is a staircase, a P&L is an average that hides the cliffs.

**3. The signature visual: the staircase.** The drawn fee staircase with a listing one inch past an edge. The moment the brand becomes unmistakably theirs. Caption: modeled from public data.

**4. Proof, the public-data case study.** The three-layer display from the Displaying section, directly under the hero's promise: headline number as a range, the staircase on real steps, the ten-thousand-months animation, the calendar strip. Label on every screen: modeled from public data, not a client, not a result. Repeat the call to action after it.

**5. How it works, in three steps.** Book the call; hand over exports; moves go in and the Record measures them every week. Three, no more. Warm-only leaks are hinted at here, not computed.

**6. The offer and risk reversal.** The one line, big, nearly alone, with the reason beside it. The four guarantee layers live here or one click away, never above.

**7. The scoreboard preview.** One clean mock: one number, one sentence, one bar, what a client sees monthly. No red-and-green dashboard.

**8. Who runs it.** Founder-operated, the math has no age, the export-on-request hedge in writing, and the honesty line: about half of public-data models find nothing, and we say so.

**9. FAQ.** The skeptic's questions, plainly: how attribution works, what counts as profit, why the offer is not too good to be true, what happens if a month underperforms.

**10. Final call to action.** The offer line once more, one button, nothing else. No footer clutter competing with the click.

**Cut from the current index.html:** the free-Teardown-first CTAs, the demo-data badges as hero elements, the dense method exhibits above the offer (method moves below proof), and any surviving dark-navy-and-amber styling.

## The Monte Carlo animation, designed

The signature visual. It is named elsewhere but not designed, so here it is in full. It carries the whole brand feeling in one motion, so it is built deliberately, not dropped in.

**What it must make them feel.** Excitement and relief in one motion. The relief is chaos resolving: ten thousand foggy possible years settle into three clean lines and one honest band, so the operator watches their own unnamed uncertainty get organised in front of them, calm mastery over something that scared them. The excitement is the restraint: it moves once, deliberately, then goes still, which reads as being shown, not sold. The honesty is in the motion itself: it fans out, it does not converge on one triumphant number, and the band openly includes the bad end. One line for the whole thing: someone close to my money made my uncertainty visible, and did not flinch at the downside.

**What it shows.** One listing's profit across ten thousand simulated years. Faint blue paths begin bunched at a single point (today) and fan out to the right, because forecasts widen with time. Then the cloud settles and three crisp lines emerge: P10 at the bottom, median in the middle, P90 at the top, with a soft blue band filling P10 to P90. The band is the point, the honest range, never a promise. P10, median and P90 are labelled; the share of months at a loss is stated beside it.

**How it moves.** One draw-in, then still, per the brand rule. Paths sketch in over about two seconds on a gentle ease-out so it decelerates as it lands rather than snapping. The individual paths fade back to almost nothing; the band and the three lines stay sharp. It plays once when it scrolls into view, never loops, never asks for attention again. On a phone: the same, with fewer paths so it stays smooth.

**How it is built.** A custom animation on standard, free tools; the math is pre-run so the browser never simulates live.

- Run the real simulation once in the existing engine; export the paths and the P10, median and P90 lines as a small JSON file. The picture is always the real numbers, never faked.
- Draw it with D3 on an HTML canvas or SVG. D3 is the free industry standard for animating data lines and handles the ease-out cleanly; it lets Claude Code build fast with no custom drawing code to maintain. Raw canvas is the lighter alternative if performance ever demands it.
- Trigger it with the browser's built-in Intersection Observer, no library, so it plays once on scroll-in and then rests.
- All of it reads the blue, the line weights and the spacing from the shared token stylesheet, so nothing about the animation is styled in isolation.

### Monte Carlo build contract (for Claude Code)

Everything the builder needs so this can be built now, before the case study brand exists, and have real numbers swapped in later.

**The data contract.** The animation reads one committed JSON file, `montecarlo.json`, and never simulates in the browser. Shape: a `months` array giving the x-axis (integer month indices, 0 through the horizon); a `paths` array of about 50 entries, each an array of profit values one per month; and a `percentiles` object with `p10`, `p50`, `p90`, each an array one value per month; plus `share_losing`, a single number, the fraction of months below zero. All dollar values already computed. Nothing else.

**Build against a sample first.** Commit a `montecarlo.sample.json` of the exact shape, filled with realistic-but-labeled placeholder numbers, so the whole front end is finished and verified before any real listing is chosen. When the case study brand is picked in the build session, the engine exports a real `montecarlo.json` of the identical shape and it drops straight in. The `share_losing` and the y-scale must come from the file, never hard-coded.

**Which engine call.** The real file is produced once by the existing simulation in `engine/`; the build session wires the exact function and listing. Until then the sample stands in. Do not invent a second simulator in JavaScript.

**Motion, in numbers.** About 50 faint paths on desktop, about 20 on mobile (Hormozi clean: few enough to read as many futures, not noise). On scroll-in, one draw-in of roughly 2 seconds, gentle ease-out, left to right. The paths draw in faint, then fade back to very low opacity. The three percentile lines draw with them and stay sharp; the P10 to P90 band fills in softly just after the lines settle, over about 0.4 seconds. Then everything rests, one still frame, no loop, no further motion.

**Trigger and fallbacks.** Intersection Observer fires it once when it scrolls into view, then disconnects. Before it fires, show the finished still frame (lines, band and labels already in place), not a blank box, so anyone who never triggers it still sees the result. If JavaScript is off or the file fails to load, the same static still frame shows. On reduced-motion (`prefers-reduced-motion`), skip the draw-in and show the still frame immediately.

**Styling.** Blue, line weights, band opacity and spacing all read from the shared token stylesheet; nothing styled in isolation. Tabular numerals on every label. The band openly includes the bad end; the lines fan out and never converge on one triumphant number.

**Where it appears.** Muted behind or beside the hero as mood, then again as the working centrepiece of the case-study proof block (layer 2), where the same paths settle into the band on that listing's real numbers. Same asset, two placements, drawn once each.

## Offer, attribution and the scoreboard

The offer is one line: **more profit than our bill every month, or you don't pay.** It is the risk reversal and the offer in one, and it should stand almost alone near the top of the page.

**What it actually is, framed as the after-state, never the category.** Do not lead with what Hubricon is — not a software, not a dashboard, not a desk, not an agency. The category is a box, and the box is not the value. Lead with what becomes true for the client once Hubricon is in: they always know exactly where their money is made and lost, they stop losing it, and it is proven every month or they do not pay. That is not a tool they log into or a service they hire; it is a state of certainty they get to live in. The whole aim of the framing is the wow of recognition — "this is what I have been looking for, I did not know I needed this" — landing across everything at once, without a word of education. Never teach the client why they should want it; show the after-state so plainly they recognize it instantly as the thing they wanted. Everything below — the financial mathematics, the engine, the sealed leaks — is the *how*, the quiet proof for the skeptic who looks, never the pitch. And because certainty is the thing they cannot un-have, the framing and the retention are one idea: once they live in knowing, leaving means choosing to go blind again, and nobody chooses that.

Put the reason next to it, because a too-good offer trips the "what's the catch" reflex. Across the $1M to $30M band, clearing $6,000 a month of measured value is a bar the engine can reach, including at the $1M end, so the bet is priced against a floor Hubricon expects to clear. Explained, the offer reads as confidence; unexplained, it reads as desperation.

**The stack, named once (so the price feels small).** The one line stays the headline, but somewhere on the page the buyer should see everything the engagement includes, stacked, so six thousand reads as small against it. State it plainly, as a firm lists its scope, not as a bulleted "bonuses" pile: continuous SKU-level financial modelling of the whole catalogue; the leak-by-leak work with every dollar graded and attributed; a weekly scoreboard, not a monthly statement; risk and inventory-timing analysis against the fee cliffs; and the guarantee that wraps it, more profit than the bill or no bill. The point is not to inflate; it is to make the full surface of the work visible, because an operator underestimates it when it is compressed to one line.

The current site states this as four stacked layers (free Proving Month, proven or void, service until proven, the open exit). Keep all four, but move them to the FAQ and terms; the page leads with the one line.

**Attribution is already built.** `measurement.py` grades every dollar as *direct* (the platform's own record), *isolated* (the exact line the move named), *attributable* (against a stated counterfactual, at the least favourable end of its range) or *none*. It caps isolated and attributable claims at the promise, skips anything under a materiality floor, requires the effect to persist, and credits each dollar once. Two things from tonight are still missing:

1. The attribution definition in plain English, signed before kickoff. The worst time to define "profit" is when an invoice is due.
2. The monthly scoreboard, replacing anything that looks like a statement.

**The scoreboard, in three layers:**

1. One number and one sentence: what the system made you this month, your bill, and what you are up net. A single bar shows the baseline against now.
2. The levers underneath: each move, its dollars, and its "how we know" label.
3. The method, collapsed, for the rare reader who wants it.

Most founders read only layer 1, and it should feel like winning. The portal's big-number "position hero" is the starting point; it needs the new type and colour, and the serif removed.

## The scoreboard, deep

The most important deliverable: it is what makes a client keep paying. One psychological job, every time they open it: feel that the $6,000 was obviously worth it, in under five seconds, doing no math themselves.

**The running cumulative total is the retention anchor.** The largest, first thing on the page is not the month, it is everything Hubricon has made them since day one, a number that only ever grows. A fixed-leak business has a churn trap: once a leak is sealed the client forgets it was ever bleeding and wonders why they still pay. The cumulative total beats that: it is the standing monument to total damage prevented, and it makes cancelling feel like turning off the thing holding the money in.

**Design language tied to the pain, not to growth.** Their pain is not "I want a number to go up." It is "money is leaking somewhere I cannot see and nobody is watching it." So the scoreboard reads as a monitor, not a growth dashboard, the calm readout of an instrument confirming someone is on watch and everything is under control. Less quarterly-earnings chart, more instrument panel.

- **Each leak is named and shown as sealed.** Not just a dollar figure: a thing that was bleeding, now held shut. "Weight-band edge on SKU X, sealed, holding $Y a month." The emotional frame is damage that is no longer happening because someone is watching, not growth being added.
- **The cumulative total is the sum of everything stopped from leaking.** Every sealed leak feeds it; it is the running proof of the watch.
- **The bar every time:** what we made you this month, minus the bill, equals what you are up. Always in the black, no math required.

**The three layers, restated with this frame:**

1. The cumulative total (biggest), then the month's number, the bill, and net, with the baseline-vs-now bar. Reads in three seconds and feels like winning.
2. The sealed leaks: each named, its monthly dollars, its "how we know" attribution label, and its status as held shut and still watched.
3. The method, collapsed, for the rare reader.

**Rules:** tabular numerals, one accent (the electric blue) only on the money; no red-and-green dashboard; the cumulative total never resets and never goes down; the portal's big-number position hero is the starting point, restyled to the new tokens with the serif removed.

## Customer experience, moment by moment

The wow at this price is not hospitality; it is unnerving competence and calm. The buyer is a skeptical operator who has been burned by agencies that sold hard and delivered a dashboard, so a welcome kit, a concierge and branded everything read as exactly the fluff that hides a thin service. The feeling to engineer is: this system is more organized about my money than I am. Warmth that has not been earned reads as a salesman; precision reads as safety. So the experience is almost subtractive, a few touchpoints, each one exact.

**The scalability rule that governs all of it:** the thing that is close to the client's money is the system, not the founder. The founder built the machine and signs off on it; he is not the operator. This is deliberate, because the opposite, a personal hand-written note per client, is a prison that breaks the moment volume arrives. A system that watches the account around the clock is something a skeptic trusts more than a busy human who might miss something, so the scalable version is also the more convincing one. Every moment below is designed to run at high client count with the founder reviewing exceptions, never producing from scratch.

1. **The application (before the call).** The four-question intake goes out on booking and should feel like a private practice taking a new patient, not a lead form: short, exact, quietly selective. The signal is that not everyone gets worked with. This runs itself; it never needs the founder.
2. **The call (the wow, already designed).** Exports are opened live and the warm-only cliffs computed in front of them, their own named dollars on the screen before they have paid a cent. Nobody at this price does this. It does more than any welcome kit could. The only moment that is genuinely founder-time; protect it and keep it rare by letting content and the case study pre-qualify hard.
3. **Kickoff (speed and precision).** On yes, the attribution definition in plain English is signed before anything starts, so "profit" is never argued later. Then one clean handoff of exports, and the client never lifts a finger again. Engineer the feeling: they did almost nothing and someone serious took the wheel. Templatized and repeatable, not bespoke per client.
4. **The ongoing rhythm (where most services quietly die).** The client forgets they are paying. The scoreboard is the standing answer, and the human layer is a short, calm weekly note in the brand voice, a doctor's follow-up, not a status update: here is what I found, here is what I sealed, here is what I am watching. Critically, this note is drafted by the system from the real graded numbers and approved by the founder, never written from scratch. That is the only way the rhythm survives volume.
5. **The save (retention).** The real risk is not a bad month; it is the client forgetting the damage being prevented. The cumulative total on the scoreboard fights that, and the discipline is never to let a sealed leak become invisible: keep showing the money that would be bleeding if no one were watching.

The through-line: competence and calm, never hospitality, and every moment built so the system carries it and the founder only supervises.

## The funnel: what opens, what closes

The leaks split in two, and the split designs the funnel. What can be computed from a public listing gets the call booked; what needs the brand's own exports is what makes them say yes on the call.

| Leak | Platform | From public data? | Role | Why |
| --- | --- | --- | --- | --- |
| Oct 15 peak fulfillment step, priced on their exact listing | Amazon | Yes | Content opener, while live | Dated, specific to them, urgent, ends Jan 14. Nobody else is sending it. |
| Price-band, weight-band, dim-weight and size-tier edges | Amazon | Yes | Evergreen opener and teaching topic | The staircase in its purest form. The $10 edge does not exist for a brand priced at $25–$40. |
| Compare-at "permanent discount" | Shopify | Yes | Content opener | Half the catalog below its own compare-at so long no customer has seen the real price. Two published numbers, unarguable, fixed with a click. |
| The 16 oz USPS boundary | Shopify | If weight is published (check) | Opener, larger than anything on Amazon | A few tenths of an ounce moves a parcel into the next rate step. |
| 271-day aged-inventory cliff | Amazon | No, needs the inventory-age export | Call closer, biggest jolt | 3.6× step on a specific morning, colliding with peak storage right now. |
| Low-inventory-level fee | Amazon | No | Call closer | Needs their inventory data. |
| ACOS break-even target | Amazon | No, needs spend response and margin | Call closer and teaching topic | They are not overspending against their target; their target is wrong. |
| Refunds with no return | Amazon | No | Do not lead with it | Biggest emotional number, zero novelty: every reimbursement service pitches it. It also selects the wrong buyer. |

**Rule to keep:** jolt is relative to their inbox, not their knowledge. Novelty in their world beats magnitude in yours.

On Amazon, the cliffs are imposed on the seller. On Shopify, the seller built them. The copy for each platform should say so.

The path, in order:

1. A piece of content names one public-data leak on their world. (Cold messages are paused; see the channel decision.)
2. They book the call.
3. They hand over exports.
4. The warm-only leaks land on the call.
5. Managed Profit.

**The call mechanism (how a booked call becomes a yes).** The path names what opens and what closes, but not the close itself, so name it: the content earns the call; on the call the exports are opened live and the warm-only cliffs (aged inventory, low-inventory fee, the wrong ACOS target) are computed in front of them, turning an abstract promise into their own named dollars on the screen. The close is not a pitch, it is the reveal: they watch their uncertainty become a specific number, and the guarantee removes the last risk of saying yes. The call sells by demonstration, in the same voice as the rest of the brand, a scan being read, not a deal being pushed.

## The dated Amazon lead, checked

This was the strongest cold lead; with cold outreach paused it is now one of the strongest early content topics, live only while the step is: October 15 to January 14. The fee facts behind it hold up against the published 2026 schedules.

| Fee | The step | When | Source |
| --- | --- | --- | --- |
| Holiday peak fulfillment | Average +$0.32 a unit; +$0.19 on small standard (the example case goes $2.49 to $2.68) up to +$2.81 on extra-large | Oct 15, 2026 to Jan 14, 2027 | [Eightx](https://eightx.co/blog/amazon-holiday-fulfillment-fees-peak-surcharge) |
| Fuel and logistics surcharge | 3.5% on top of every fulfillment fee, peak included | Since Apr 17, 2026, no end date | [Eightx](https://eightx.co/blog/amazon-holiday-fulfillment-fees-peak-surcharge) |
| Monthly storage, standard size | $0.78 to $2.40 per cubic foot, about 3.1× | Oct to Dec | [E-Globe](https://eglobe.business.blog/2026/08/18/day-271-when-storage-goes-from-1-50-to-5-45/) |
| Aged-inventory surcharge | $1.50 to $5.45 per cubic foot at day 271, a 3.6× step | Snapshot on the 15th of each month, on top of storage | [E-Globe](https://eglobe.business.blog/2026/08/18/day-271-when-storage-goes-from-1-50-to-5-45/) |

The mechanism is structural, not seasonal: any unit that sits long enough crosses the 271-day aged-inventory line and its storage cost jumps from roughly $1.50 to $5.45 a cubic foot — a permanent cliff in Amazon's own published schedule that a seller's linear mental model never prices. Slow-moving stock hits it every day of the year, which is exactly why it makes a case study that never expires.

**Still to re-derive from the engine's rate card before any page or email** (these came through voice transcription; re-derived 2026-09-30, see OPERATIONS.md):

- Crossing $10: fulfillment per unit 82¢ to $1.01; crossing $50 costs 26¢.
- The $9.95 to $10.49 example: a 46¢ raise net of referral, set against the step handed to Amazon.
- "19¢ to 54¢ across 63 cells" for the peak step: the published range across all tiers runs $0.19 to $2.81, so confirm which tiers the 54¢ ceiling covers.
- USPS: 15.9 oz against just over 16 oz, 96¢ to $4.47 a parcel across zones 1 to 8.

## The public-data case study

Until a client's Profit Record produces a real number, the one proof asset is a case study built only from a brand's public pages, labelled on every screen: **modeled from public data, not a client, not a result.** That label keeps faith with the repo's own rule that the results wall reads $0 until a real result exists.

**Which brand.** None has been modeled yet; it is chosen in the build session per the case study build spec below. It should:

- be a recognizable private-label brand in the $3M to $30M estimated band,
- have a standard-size listing sitting just past a weight or price edge,
- have slow-moving stock exposed to the aged-inventory storage cliff on that exact listing,
- have enough rank and price history for the volume estimate to hold.

On the landing page, anonymize to category and band ("a home and kitchen brand, estimated $X to $Y") so it can never read as a hit piece or an implied client. In the content series, naming is fine with a right of reply offered and every figure labelled an estimate, which `GROWTH.md` already requires.

**What goes in.** Everything is public. The fee and rank computation inside `teardown.html` already does most of it: the page itself is archived, but lift that computation into a build script or the engine and reuse it here rather than rewriting it.

| Input | From | How it is used |
| --- | --- | --- |
| Price and its history | Listing page | Places the listing on a price-band step |
| Weight and dimensions | Listing page | Size tier, weight band, ounces past the edge |
| Best Sellers Rank | Listing page | Monthly units from the engine's rank-to-units curve, drawn lognormally |
| Landed cost | Assumed | Drifts ±10%, stated on the page |
| Referral, fulfillment and peak fees | Amazon's published schedules | Rate card dated on the page |
| The simulation | Engine | 10,000 months: P10, median, P90, share of months at a loss |

**The story in five beats.** The same five beats run the page, the long-form video and the clips cut from it.

1. **The staircase.** The seller's mental model is linear; Amazon's cost structure is steps.
2. **Where this listing stands.** How far past the edge it sits, in ounces or dollars.
3. **The counterfactual.** What one inch the other way would cost, per unit and per year.
4. **Ten thousand months.** The honest range, not a point, and how often a month loses money.
5. **The cliff and the gap.** The aged-inventory cliff this listing's slow stock is drifting toward — where storage jumps from roughly $1.50 to $5.45 a cubic foot the day a unit crosses 271 days — and what public data cannot see (exact days-on-hand, ads, returns). That gap is what the call is for.

**Where it lives.** One asset, four uses:

- the landing page's proof block, directly under the offer and video, carrying the Monte Carlo accent;
- its own page, linked from the content;
- the first long-form video, run as hook, teach, soft close;
- clips cut from that video, one leak each.

## Displaying the case study

Display it the way the scoreboard works: one number a founder gets in three seconds, three visuals they get in thirty, and the method folded away for the one reader who wants it. The staircase below is the signature picture; it shows the counterfactual that no P&L contains.

&#91;embedded content: the fee staircase · concept, not to scale\]

The solid dot is the listing; the hollow dot is the same listing one inch the other way. The gap between them is the whole finding, so it is the only thing in the accent colour.

**Layer 1, three seconds.**

- The headline as a range: "$\[P10\] to $\[P90\] a year, paid on one step of Amazon's fee staircase."
- One sentence naming the step.
- The label: modeled from public data, not a client, not a result.

**Layer 2, thirty seconds.** Three visuals, in this order:

1. The staircase, drawn with this listing's real steps and a dated rate card.
2. Ten thousand months: Monte Carlo paths draw in once and settle into a band, with P10, median and P90 marked and the share of losing months stated. This is the signature animation doing real work, not decoration.
3. The aging strip: each unit's clock toward the 271-day cliff, the storage-cost band it sits in now, the band it falls into on the next tier, and a "today" marker showing how close the stock already is.

**Layer 3, folded.** The assumptions list in the same form the archived `teardown.html` prints it, the rate-card date, the method in two sentences, and what a public page cannot see.

**Display rules:**

- Ranges, never points; rounded down; "estimate" beside every number.
- One accent colour, used only for the leak; everything else neutral.
- Tabular numerals. No red-and-green money dashboard.
- One draw-in animation, then still. Every chart readable at phone width.
- Say the selection out loud: "We picked this listing because it had a finding. About half the brands we model from public data show nothing worth fixing, and we tell them so."
- One button: book the call.

## Case study build spec (for Claude Code)

The case study does not exist yet, so it cannot be audited, only built. This section is the mechanical recipe: pick the real listing, run the real data, and only then write the numbers. Do not invent figures; an unverified number on a named brand is the hit-piece risk the honesty rails exist to prevent.

**Target profile (pick one real listing that fits all of these):**

- A recognizable private-label brand in the $3M to $30M estimated band, not a giant like Anker or a household name, and not an Amazon in-house label.
- A standard-size hero SKU sitting just past a weight or price edge. The cleanest is a roughly one-pound flagship near the 16 oz boundary (coffee, supplements, protein or creatine tubs are ideal: recognizable, standard-size, and often right at an edge).
- Genuinely exposed to the aged-inventory storage cliff on that exact listing: slow-enough stock that real units cross the 271-day line and jump storage tiers, a leak that is true every day of the year, not seasonal.
- Enough rank and price history for the volume estimate to hold.

**Build steps, in order:**

1. Pull the live public data for the chosen listing: current price and price history, exact weight and dimensions, and Best Sellers Rank. Confirm with your own eyes that it sits past an edge; if it does not, pick another. `teardown.html` already computes most of this.
2. Convert BSR to monthly units with the engine's rank-to-units curve (`engine/src/hubricon_engine/harvest/amazon.py`), drawn lognormally, not as a point.
3. Assume landed cost and drift it plus or minus ten percent; state the assumption on the page.
4. Apply the published, dated 2026 fee schedules (referral, fulfillment, peak, storage, aged-inventory) from the Sources section.
5. Run the simulation, ten thousand months, for P10, median, P90 and the share of months at a loss.
6. Build the counterfactual: the same listing one inch the other way (one ounce under the boundary, or one cent under the price edge), and the per-unit and per-year gap between them. The gap is the whole finding.

**Then write it in the five beats and the three display layers already specified** (the staircase, the ten-thousand-months animation, the calendar strip). Every figure labelled an estimate; every screen labelled modeled from public data, not a client, not a result.

**Naming decision, deferred to the build:** name the brand only after the real data confirms the finding, with a right of reply offered per `GROWTH.md`. On the landing page, anonymize to category and band; naming is for the content series only. Until then this doc's brand blank stays blank on purpose.

## The honesty page (/honesty), built quiet

A permanent, self-auditing page that gives honesty-as-proof a home. It is deliberately quiet: linked only from the footer, never promoted in the funnel body. It is the reward for digging. A skeptical operator goes looking for the catch and finds Hubricon has already listed every catch itself, which is the moment they trust it. Promoting it would make it read as a marketing asset and kill the effect.

**It matures, so it is never empty and never dishonest.** Today, with no clients, the page is radically honest about exactly that. As real client numbers arrive it grows into the results wall. Same URL, same voice, it just matures.

**What it holds now (pre-client):**

- A plain statement: no client results yet. Say it first, before anything else.
- The method in plain English: how the simulation works, what a range means, why figures are estimates.
- Attribution in plain English: how every dollar is graded direct, isolated, attributable or none, capped at the promise, credited once. The signable version that also goes in `terms.html`.
- The public-data case study, clearly labelled modeled from public data, not a client, not a result.
- The misses, stated openly: about half of public-data models find nothing worth fixing, and we say so.
- What we will show the moment it is real: the exact scoreboard fields a future client's numbers will fill.

**What it becomes (post-client):** the live results wall. It reads zero until a real result exists (the existing honesty rail), then fills with real attributed dollars, graded by the engine, each figure labelled. The pre-client copy about method and misses stays; the results simply appear above it.

**Tone:** the same cold, self-auditing register as the rest of the brand. No defensiveness, no spin, no "but." A firm reading its own scan aloud. Every limitation stated as a fact, not an apology. This page never sells; it only tells the truth, which is what makes it sell.

## Content engine

Every piece runs the same skeleton, so volume never depends on inspiration: **name the leak, teach the leak, offer to handle the leak.** Each leak in the funnel table is a video, and the engine has dozens of them.

**The content split: roughly half universal, half platform-specific.** The single most important content decision, and the reason the audience grows past the FBA niche. Universal topics, the math every operator needs, pricing and elasticity, decisions under uncertainty, cash conversion, contribution margin, grow the audience: a $30M DTC founder, a SaaS operator and an agency owner all watch them. Platform-specific topics, Amazon fee leakage and the cliffs, convert that audience into booked calls. **Universal grows, specific converts, and you need both.** Nobody owns the math the way Hormozi owns offers; that open category is the real reach play, and it is genuinely the founder's training. Aim for about a 50/50 mix; the ratio matters more than any single topic.

1. **Hook (the doorway).** Open in their frustration, then remove the shame: "If you're doing eight figures and you can't tell me where this is costing you, that's not a you problem. Nobody around you is running the math."
2. **Teach (the room).** Give the real insight away. Teaching the method does not cannibalize the service; it makes the size of the gap legible, and most buyers still want the person who understands it to run it.
3. **Soft close.** One calm line: "You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works."

How it gets made:

- **You own the script.** The insight is the moat and is never outsourced. Talking ideas out loud on a walk and turning them into scripts works.
- **Voice:** yours or a high-quality AI voice (open decision). Staying off camera is settled.
- **Visuals:** a Vox-style template of clean type, charts and motion, reused every episode. The staircase and the Monte Carlo band are house visuals.
- **A pre-publish checklist,** run every time: audio levels, spelling on every text frame, brand colours, spacing, every number labelled.
- **Tools:** pick them in the build session with a fresh search; this space changes monthly.

Where it goes: one long-form YouTube video, cut into clips for Shorts, Reels, TikTok and LinkedIn. Instagram and LinkedIn are where more real buyers are; TikTok widens the top of the funnel. Every piece points to `/learn`, the free courses modelled on Acquisition.com, where a single email registers them for a course, everything inside free and open. That course registration is how the list is built, and the free content and courses are the entire lead magnet.

## Education: landing page vs the hub (the split)

Two different jobs, kept separate. The landing page teaches once, as proof; the full library lives elsewhere and is chosen, not pushed.

**On the landing page: exactly one video.** It sits in the proof block, section 4, directly under the offer. It is the case study told as the five-beat story (the staircase, where this listing sits, the counterfactual, ten thousand months, the cliff). It does double duty, proof and teaching in one asset, and it is the only teaching on the page. Everything else on the landing page stays lean and points at the call. Do not add a second video or a course preview to the landing page; its job is to book the call, not to educate fully.

**The video ends pointing two ways.** Primary: book the call. Secondary, quiet, for the curious-but-not-ready: a soft path toward `/learn`. So the one video feeds both the funnel and the library, and an operator who is not ready to book does not just bounce.

**On `/learn`: the full library, held back.** The complete teaching, the courses, the method end to end, linked quietly (footer, and the soft secondary path above), never in the landing page's main scroll. This is the destination a visitor chooses to go deeper into. It follows the hub build already specified: one complete course first, three-column layout, a single email to enter each course, everything inside free and open.

**Sequence note:** plan and place this video now; learn to actually produce it (the AI video toolchain) in the later build session with a fresh search, as agreed. Placement and script come before tools.

## Education hub (/learn), modeled on acquisition.com

Hormozi gives away real, complete training on acquisition.com, gated by an email, and it does his selling for him. Hubricon copies the structure and the discipline, not the look. The look stays Hubricon's own: white, one accent, precise. The governing rule is teach everything the reader can actually do themselves and let it pay them real money, then teach the shape of what they cannot, in enough detail that they size it. Giving away the best thinking is the flex; scarcity-minded amateurs hoard.

**Why it exists (three jobs at once):**

1. Proof of competence before payment. With no client results yet, teaching the method publicly is the strongest authority available.
2. Capture and route, without a paywall. One email enters a course (that builds the list), and the teaching inside is entirely open; the four-question application lives only at book-the-call, where the revenue answer sorts the lead into Managed Profit or the downsell. Nothing inside a course is held back.
3. Manufacturing the gap. A founder who fully understands elasticity, 20,000-path Monte Carlo and heteroskedasticity-consistent errors still cannot execute them alone. Teaching the method in full makes the size of what they're missing legible; it does not cannibalize the service.

**Structure, borrowed from acquisition.com:**

- `/learn` hub: a card grid, one card per course, a badge on each. No card for anything not yet built. The library is the lead magnet; the whole thing is genuinely free.
- **Email to enter, the Acquisition.com model.** This is the email capture, and the only one. A single email registers you for a course, the way Acquisition.com's free courses work: the email is the price of admission, not a wall in front of the good part. Once in, every lesson and every template is completely open, free, and never paywalled. No second ask, no payment, no upsell inside the content.
- `/learn/<course>`: three columns, a sticky lesson nav on the left, the lesson in the centre with the template download free directly under it, and the right column holding a soft, standing invitation to book the call, present but never desperate.
- **The generosity stays total.** What they get for the email is the entire course, not a teaser. That is the whole point: if this much is free for just an email, the paid thing must be extraordinary. The email ask never looks like the course sellers who are the named enemy, because nothing is held back behind it.
- **Deliberately overwhelming volume.** Not one tight course but a firehose of it. The sheer amount of free, checkable, high-quality material is the lead magnet and the proof at once.
- **The other capture is book-the-call.** Chosen when the material has already convinced them. The four-question application sorts the lead into Managed Profit or the downsell, and it sits at the call, not in front of the teaching.

**Build order: one course, not four.** Ship one complete course before any second. One finished artifact reads as more authoritative than four with "coming soon" badges, and four half-built courses is how a solo operator loses a quarter. The first course is the one that produces the most shareable, self-contained win from public data, taught end to end.

**Rules that keep it on-brand:**

- Teach completely. No withheld steps, no "the rest is in the paid version." The service is execution; every gap left in the teaching weakens the authority.
- Templates over videos. If a lesson can ship as a document plus a spreadsheet, ship it and add video later.
- No hype furniture. No countdowns, no "limited spots," no fake enrollment counts. Same luxury pass as the landing page.
- `/learn` is linked from the footer only, never inside the Managed Profit body copy.
- The downsell stays genuinely premium: same quality, smaller scope, never a cash-grab that cheapens the brand.

## Channel decision: content first, one channel, cold outreach paused

The strategic decision that governs the launch: with one operator, one channel done to a ten beats five channels done to a four. The channel is content.

- **Cold outreach is paused, on purpose.** A cold message from an unknown with no proof does not convert a skeptical eight-figure operator; it is the treadmill, not the asset. Revisit only once real proof exists.
- **Content is the one channel.** It compounds: every video keeps working while you sleep, builds the audience, and manufactures proof at the same time. Cold outreach is a treadmill; content is an asset.
- **It doubles as proof.** Content is rung two of the proof ladder, showing the work in public. The same effort that builds the audience builds the trust. That is the leverage.
- **All time into one thing.** Build the audience first. Do not split focus across channels until the one channel is genuinely working and there is more than one operator to run them.

This reframes the launch below: phase 2 is no longer cold-hook-before-October-15; it is content, published consistently, as the single top of funnel.

## Internal operations: the CRM that scales delivery

Hubricon is built to take on a lot of clients, so delivery has to scale without the founder's hours becoming the ceiling. Everything about the business must be scalable; this section is where that principle becomes infrastructure. The answer is an internal operations layer where the system does the producing and the founder only reviews: draft, review, approve, send.

**What it is.** An internal console on top of the existing engine, not client-facing. Client records (the CRM), the attribution engine feeding auto-drafted client updates, an approval queue, and lifecycle triggers that fire the right touchpoint at the right time. The client sees only the scoreboard; the console is the founder's cockpit behind it.

**The core loop: draft, review, approve, send.** The engine already grades every dollar. It generates each weekly note in the brand voice from the real numbers, flags the ones that need the founder's eyes (an unusual result, an at-risk client, a month that underperformed), and queues them for a one-click approve. The founder reviews exceptions, not every line. This is the single mechanism that lets the personal-feeling rhythm run at high volume.

**Lifecycle triggers, so the rhythm runs itself:**

- **Kickoff:** on a signed client, auto-generate the attribution agreement and the exports checklist.
- **Weekly:** draft the scoreboard note from the graded numbers; hold for approval.
- **At-risk:** when a client's cumulative value flattens or a month underperforms, flag it to the top of the queue before the client feels it.
- **Save:** surface any sealed leak that has gone quiet on the scoreboard, so it never becomes invisible.

**Sequencing (important, do not build this early).** This is a phase-three or phase-four build, after there are real clients. Do not build the CRM before the pipeline exists; automating an empty pipeline is wasted work. With the first handful of clients the founder writes the notes by hand, on purpose, to learn exactly what the system should later say. Then encode that pattern into the draft templates. Hand-write first, extract the pattern, then build the machine that drafts it.

**Build notes for later:** it reuses the engine's attribution output directly (no second source of truth for dollars); the approval queue and client records can sit on the existing stack; the client never sees the console, only the scoreboard the notes reference.

## Launch sequence

Four phases, each unlocked by a gate. Content is the single channel from phase 2 on (see the channel decision above); the October 15 step is an early content topic, not a deadline the launch has to beat.

&#91;embedded content: launch sequence · 4 phases, 3 gates\]

Per the channel decision above, phase 2 is content, not a cold hook: publish consistently on the one channel and build the audience, which doubles as proof. The October 15 leak is no longer a launch clock; it is simply one strong early content topic while it is live. The diagram's phase-2 gate becomes replies, saved-content and booked calls from published content, not from cold sends. Ship each piece at five out of five and let real operators hand you the six.

Phases 3 and 4 are where the internal operations layer gets built (see that section): first clients are served with hand-written notes to learn the pattern, then the draft-review-approve CRM is built so delivery scales to real client volume without the founder's hours becoming the ceiling. Do not build it before clients exist.

## Money handling, structure and billing

The founder is a mathematics student, not a business operator, so this section records the operational money spine plainly. It is foundational and settled, not open for debate.

- **Entity.** Sole proprietor to land the first client, to avoid the cost before the business is proven. But the LLC is formed before that first engagement actually starts, never after: it is a liability shield, not a badge, and serving even one eight-figure brand (with a profit guarantee, handling their financial data) as a sole proprietor exposes personal assets. Land the client as a sole proprietor; file the LLC before touching their data.
- **Taxes, from dollar one.** About 30% of every payment is moved to a separate account the day it arrives and never treated as income. Quarterly estimated payments to the IRS, since there is no employer withholding. This is settled discipline, set up the moment the first payment lands.
- **Billing: monthly, in arrears, and the order is the guarantee.** Stripe is already connected. Each month the scoreboard shows the profit first, then the invoice bills against it, never the reverse. That sequence is the guarantee made real: the client sees the justified number before they ever pay it, so there is never a moment where they have paid and are waiting to find out if it was worth it. The proof always comes first. This billing order is part of the brand's credibility and must never flip.
- **Tools deferred on purpose.** QuickBooks is connected but not built into the software, and Plaid is not in use. Both wait until real proof exists (approval is also easier then). Early on the only requirement is a clean invoice-and-get-paid path, which Stripe already covers. Do not build QuickBooks or Plaid integration into the product yet.

## The contract

A contract for a trust brand is not a wall of scary clauses. It is a clear, fair agreement that makes the client feel safe rather than trapped. The fairness is the relationship-builder: a contract that only protects Hubricon reads as distrust, while one that visibly protects the client too is part of how Hubricon becomes the operator a client treats like their best friend. Every clause below is written in plain English on purpose, so the meaning is the same whether a founder or a client reads it.

**This is a skeleton, not a filed document.** It is complete enough that an attorney's review is a cheap, fast pass rather than a from-scratch job. Before the first client signs, the two high-risk clauses — the guarantee and the liability limit — get one review by a licensed Texas attorney. Not because the drafting here is weak, but because a performance guarantee that promises money back is the one document that can reach the founder's personal assets, and it is worth a human with a license standing behind it once. The LLC must exist before that first signature.

**1. Scope — what Managed Profit is.** State plainly what the service includes: continuous financial-mathematics and risk analysis of the client's Amazon and Shopify economics, the leaks found and sealed, the scoreboard, and the weekly note. State just as plainly what it excludes — Hubricon advises and models, it does not run the client's ad accounts, touch their bank, make pricing changes on their behalf, or guarantee any specific business outcome. Naming the excludes is what prevents scope creep, the thing that eats a solo operator alive. The best-friend energy lives in how the work is delivered, never in an unbounded scope.

**2. The guarantee — defined precisely.** The promise is: more profit than the bill every month, or the client is not charged that month. In contract language that means each month is measured, the attribution runs, and if the attributed profit does not clear the fee, that month is simply free — no charge, no credit, no carried balance. "Not charged" is deliberate and beats a credit: a credit quietly keeps the client on the hook, a free month is clean and can be said in one breath to a skeptic. The clause must define an unbilled month tightly enough that it cannot be gamed: the month is measured, attribution runs once, and the result stands. This is the clause that most protects the client and most exposes the founder, so its wording is the single most important sentence in the document.

**3. Attribution — signed before kickoff.** The plain-English definition of how every dollar is graded — direct, isolated, attributable, or none — why each dollar is credited only once, and the materiality floor beneath which nothing counts. This is what makes the guarantee measurable instead of arguable. It is signed as part of kickoff, before any work begins, so the rules of the scoreboard are agreed before there is ever a number on it.

**4. Data handling.** What Hubricon can access, how it is protected, and a flat promise never to share or sell it. For a trust brand this is part of the product, not boilerplate. The client's financial exports are theirs; Hubricon holds them only to do the work and returns or deletes them on request.

**5. Cancellation — the no-trap clause.** Month-to-month, cancel anytime, no lock-in. This is counterintuitive for churn but exactly right: the freedom to leave is why they stay, and it is the opposite of the agencies the client distrusts. Retention comes from value, never from a contract term.

**6. Liability limit — the clause that prevents ruin.** Hubricon provides analysis; the client makes the decisions. Hubricon is not liable for business outcomes beyond the fee actually paid. This is the clause that keeps a bad month or a client's own choice from becoming a lawsuit against a solo founder. Along with the guarantee wording, it is the second clause that gets an attorney's eyes.

**7. Intellectual property and confidentiality.** The client owns their data and the specific analysis of their business. Hubricon keeps its methods, engine, and templates. Confidentiality runs both directions: Hubricon never discloses the client's numbers, and the client keeps Hubricon's methods private.

**The two that protect the founder from ruin are the guarantee wording (2) and the liability limit (6). The two that build the friendship are honest scope (1) and fair cancellation (5).** Build the full skeleton here, get 2 and 6 reviewed once before the first signature, and the contract does both jobs at once.

## The mechanics: when the guarantee triggers, and disputes

The contract defines the guarantee and the attribution grading; this section is the procedure that runs them, so nothing about the scariest moments is improvised. A trust brand cannot decide how a free month works in the middle of its first free month, or how a disagreement resolves in the middle of its first disagreement. Both are written down now, while it is calm.

**The unbilled-month workflow, step by step.** Each month closes on a fixed date. The attribution engine runs once on the closed month and grades every dollar direct, isolated, attributable or none, capped at the fee and floored at materiality. That produces one number: attributed profit for the month. The scoreboard shows it first — always before any invoice — so the client sees the justified figure, not a bill. Then one of two things happens, mechanically, with no judgment call left to make. If attributed profit clears the $6,000 fee, Stripe bills the fee against it. If it does not clear the fee, the month is unbilled: no invoice is generated, no charge, no credit, no balance carried into next month. The founder does not decide this and the client does not have to ask for it — a month that does not clear simply never bills. That automatic quality is the whole point: the guarantee is not a refund you request, it is a charge that never happens.

**Say it out loud on the call, before they sign.** The moment a prospect understands that an under-performing month costs them nothing and requires no argument to make free, the fear leaves the deal. Walk them through exactly this sequence on the first call — measured, graded, shown, then billed only if it cleared — so the mechanic itself is part of the sell. Nobody who has felt a vendor stall on a refund expects this, and that is precisely why stating it plainly converts.

**Attribution disputes resolve by inspection, not negotiation.** The disagreement a skeptical operator will raise is that Hubricon is crediting itself for a dollar the client would have earned anyway. The answer is built before the dispute: every graded dollar carries its audit trail from the risk gate — which rule, which data, which threshold, what confidence — so a contested figure is not argued, it is opened. The founder and the client look at the same record. Because attribution is signed at kickoff before any number exists, the rules were agreed while neither side knew who they would favor, which is what makes the later inspection binding rather than a fight.

**Three grading choices settle most disputes in the client's favor, on purpose.** Each dollar is credited only once, so nothing is double-counted. The materiality floor means small, noisy movements are never claimed. And where a dollar's cause is genuinely ambiguous between Hubricon's work and something the client did, it grades as none, not attributable — the tie goes to the client. Leaning conservative is not a concession, it is the moat: a guarantee that under-claims is one a client never has to defend against, and it keeps the whole brand on the honest side of every close call.

**The standing escalation, kept simple.** If the audit trail does not resolve it, the disputed dollars are dropped from the claim for that month — removed, not split. A dropped dollar can lower the month below the fee, which only ever helps the client. This gives the founder one clean rule for every unresolved dispute instead of a negotiation, and it means a disagreement can never end with the client paying for something they still doubt. The dispute path, like the guarantee, always resolves toward the client, which is the only way a trust brand can afford to run it.

## Data handling and trust

Trust splits in two. There is trust as a feeling, built by brand and honesty, which the rest of this doc covers. And there is trust as an operational promise: the concrete, unglamorous things Hubricon does with a client's financial data so that trust is earned rather than claimed. For a brand whose enemy is the vague agency, the gap between saying "we are trustworthy" and showing exactly how the numbers are handled is the whole moat. This surfaces on the site, not as quiet internal hygiene — it is a question every prospect will have, answered before they ever have to ask it. Everything earns its place, and this earns its place by removing the fear that would otherwise sit unspoken through the whole first call.

**What is actually being trusted.** A client hands over their Amazon and Shopify exports — real revenue, margins, costs, weak spots. For an eight-figure brand this is among the most sensitive information they own; leaked, it could help a competitor or expose them. The standard is not "don't be careless," it is "treat this like it is radioactive." That framing alone puts Hubricon ahead of agencies that treat client data like loose paperwork.

**Least access.** Ask only for the data the work actually needs — the specific exports the engine reads, never a blanket login to the whole account. A narrow, precise ask is both safer and more trust-building: it signals the precise operator, while "give me access to everything" signals the opposite. The data ask is itself a brand moment.

**Storage and protection.** Exports live in one controlled place — the Supabase backend — not scattered across a laptop, email attachments, and stray folders. Encrypted at rest, access limited to the founder, with a clear retention rule: hold the data only as long as the work needs it, delete or return it when the engagement ends or the client asks. A client can ask "what do you have of mine, and where" and get a straight answer.

**The flat promises.** Never shared, never sold, never used for anything but the client's own work. Obvious to say, rare to state — and stating it plainly, in the contract and out loud, is part of the product.

**The breach honesty rule.** Decided now, while it is calm, so panic never makes the decision. If data were ever exposed or compromised, the client is told immediately and plainly: what happened and what is being done. The honesty that says "half of cold prospects produce no findings" cannot have a hidden exception for its scariest moment. The rule is written down before it is ever needed.

**The client stays in control.** The data is theirs, not Hubricon's. They can ask what is held, ask for deletion, and take it back when they leave. Hubricon is a custodian, not an owner — the opposite of the sticky, hostage-taking way agencies hoard data to raise switching costs. Freedom over their own data is the same promise as the no-trap cancellation clause: freedom to leave, extended to their numbers.

**Where it lives.** Its own quiet page — "How we handle your data" — linked in the footer, in the same cold, matter-of-fact voice as the honesty page: not a legal wall, six short human answers to the six points above. One line belongs in the landing-page FAQ, since every prospect wonders it. The page is where the fear goes to be fully answered before the call, earning its own real estate the way the biggest operators give every real question its own tab.

## Client boundaries: the engineered approval gate

A solo operator usually protects quality with willpower — a capacity ceiling, a response rhythm, a line against scope creep held by hand. Hubricon inverts that. The thing close to the client's money is the system, so the boundary that protects quality is not the founder's discipline, it is an engineered risk gate modeled on how automated trading desks run real money: risk management built into the machine so tightly that it can act on its own, inside limits a human set in advance. The founder's human role is top-of-funnel — content, calls, and hiring salespeople the moment pre-qualified calls flood in. Sales is deliberately never automated. Approval is, but only the way a quant fund automates execution: behind hard rails, with a human on the exceptions. Borrowed directly from how the greats build it, four rails.

**Hard limits — the circuit breakers.** Like a trading system's position caps and loss limits, the engine has bounds it physically cannot cross no matter what a model suggests: no claimed dollar exceeds the guarantee cap, nothing below the materiality floor counts, no single figure moves beyond a set bound without tripping a halt. The risk gate is mandatory, not advisory — every number that touches a client's money or the scoreboard routes through it before it can be sent, and the analysis layer can request to send but can never bypass, disable, or silently override the gate. The kill switch is a separate mechanism from the engine it guards, so a fault in the engine cannot disable its own brake.

**Anomaly detection and confidence scoring — knowing when it is confused.** The system distinguishes the normal from the weird. A figure far outside anything seen before, malformed data, or an attribution the model lands with low confidence is flagged and held, not sent. The fail-safe default is the quant discipline that keeps funds alive: when a calculation is uncertain, pause rather than proceed blindly — the cost of holding a number for review is trivial next to the cost of sending one that is wrong. Everything squarely inside the known-safe zone auto-approves; the edge cases quarantine for a human. This is how ninety-plus percent flows automatically while only the genuinely risky slice reaches the founder's desk.

**The audit trail — nothing invisible.** Every automated decision logs why it was made: which rule, which data, which threshold, what confidence. A quant fund can reconstruct any trade; Hubricon can reconstruct any approved number. This is what makes auto-approval safe to defend — if a client ever questions a figure, a complete record shows exactly how the machine reached it. Trust survives scrutiny because the work is inspectable, which is the whole brand in one sentence.

**Graduated autonomy — earning the gate wider.** Autonomy is not switched to full trust on day one. The system earns it the way a desk earns trust in a strategy: at first a human reviews a large share, and every time the machine's judgment matches the human's, that is a data point. As the match rate proves out on a category of decision, that category is allowed to auto-approve. The boundary between automatic and human is not fixed — it moves as the system proves itself against real outcomes. The autonomy is watched being safe, then the gate is widened, never the reverse.

**The order that cannot flip.** Build the rails before widening the gate, never after. Quant funds that lasted built risk management first and returns second; the ones that blew up did it backwards. The same asymmetry governs here: the founders who survive automate aggressively everywhere the rails already hold, and keep a human on the money-touching exceptions until the track record earns the machine that decision too. The real ceiling is not how many clients can be served, it is how many the system can still stand behind — and because the rails do the standing, that number is large, and it rises as the engine proves itself. The signal to hire is the exception queue backing up faster than it clears, felt with real clients in the system, not a number guessed today.

## Becoming the foundation

The strongest businesses are not a service a client buys, they are the infrastructure the client runs on — rip it out and something breaks. This is the Becker move, and it is the real answer to churn: not a contract that traps, but an indispensability that makes leaving feel like going blind. Hubricon is closer to this than most services, because of what it already becomes for a client. The scoreboard is how they *see* their own profitability. The engine is their early-warning system for cost cliffs. Their financial clarity literally lives in the system. That is not a vendor relationship, it is the floor they stand on.

**Lean into it deliberately.** Become the layer they check every week, the source of truth for the one question that governs everything — are we actually making money — and the thing they would feel blind without. When leaving means going back to not being able to see, no contract term is needed to keep them. That is the anti-churn: indispensability, not lock-in, and it is the exact opposite of the sticky, hostage-taking agencies the brand is defined against. The freedom to leave stays total, and they stay anyway, because what they would lose is their own sight.

**The honest boundary on "it always finds something."** Where there is math there are answers, so the engine never comes back empty on *insight* — it always produces clarity, a sharper picture of a client's economics than they had. That is real and worth claiming. What is not automatic is finding enough recoverable profit to clear the bill every single month forever. Some months the math will say the account is already tight and nothing large moved — and that is not failure, it is the guarantee doing its job: the client simply is not charged that month. Claiming the engine always finds insight is true; being honest that not every month clears the bill is what keeps the promise credible. Both are true, and together they are stronger than either alone. The foundation is built on clarity that never stops, priced by a guarantee that makes the lean months safe.

## Scoreboard design brief: the 11-out-of-5

The whole business should be a clean 5 out of 5. This one surface should be an 11. The scoreboard is the foundation made visible — the thing a client opens every week to feel that their money is in the right place — so it is the single most-seen surface Hubricon owns, and it is small and bounded enough that over-investing here pays off without moving the timeline. It must never look like AI slop or a generic SaaS dashboard handed to a code tool with "make this." It is a designed instrument. The emotion in the first two seconds is Hormozi's wow: a financial operator looks at it and immediately trusts it. The through-line of every rung below is that each adds *perceived intelligence and care*, never clutter — restraint holds the whole way up, and an 11 that got loud would collapse back to a 3.

**5 of 5 — it does the job, cleanly.** The running cumulative profit number, each leak named and shown as sealed, the three layers, tabular numerals, cold electric blue on bright white, nothing templated. It loads, it is accurate, it is readable. Most would call this done.

**6 of 5 — it feels like an instrument, not a dashboard.** Deliberate hierarchy: the eye hits the cumulative number first, then the leaks, then the detail, in that order every time. Bloomberg-terminal restraint. It says a financial professional built this, not a SaaS template.

**7 of 5 — it has a heartbeat.** The number is not static. When it updates it ticks — a subtle count-up, a quiet data-tick if they are in it live. It feels alive, like money is actively being watched.

**8 of 5 — it tells them something they did not ask.** One honest forward line: at this rate, sealed leaks will have returned this much by year end. Not a projection to be trusted — a plain extrapolation of what is already banked. It turns a record of the past into a reason to stay for the future.

**9 of 5 — it is theirs, not Hubricon's.** Their logo, their brand color used once as a secondary accent, their SKUs named the way they name them. It stops being a tool they log into and becomes their financial cockpit that Hubricon happens to power. Foundation-level intimacy.

**10 of 5 — it anticipates the scary moment.** The at-risk signal from the lifecycle system surfaces here, gently, before they would notice it themselves — a SKU drifting toward the aged-inventory cliff, flagged early. Catching the thing that would have cost them, before it does, is the moment they tell someone about Hubricon.

**11 of 5 — it makes them look smart in front of someone else.** A one-click export of the scoreboard as a single clean page they can drop into a board deck or send an investor, with Hubricon's quiet mark on it. Now the scoreboard walks into rooms the founder is not in, makes the *client* look like a sharp operator, and carries the Hubricon name doing it. The foundation becomes their reputation, not just their tool — and it costs almost nothing to build.

**Build note.** This is a design standard, not a feature list to rush. Ship 5 through 7 with the first real client; 8 through 11 earn their place as the relationship and the data deepen. Every rung obeys the visual direction already set — tabular numerals, blue only on money and the leak, bright white base, data visuals only. The scoreboard is where restraint and wow prove they are the same thing.

## Money, later

Delivery already scales solo, so distribution is the only ceiling, and most reinvestment goes there. At 10 clients that is $60,000 a month at near-total margin; the order of operations:

1. **Pay yourself and set aside taxes first.** A precision brand with sloppy personal books is a bad look, even if only you know.
2. **Hold a real reserve.** Performance billing makes revenue lumpy: a void month or two churned clients hits hard. The reserve is you hedging your own book the way you hedge theirs.
3. **Buy back production time.** An editor or motion designer turns your scripts into volume without you touching the timeline. You stay the brain and buy the hands.
4. **Amplify only proven winners.** Paid spend goes behind content that already converted organically, never ahead of it.
5. **Diversify last.** The business compounds faster than the market while it can absorb cash; index funds come once it throws off more than it can use.

Measure the return on each reinvested dollar the same way you measure a client's.

## Open decisions for tomorrow

Ticked items are settled; the unticked ones are the only blanks left for the build.

- [x] **The Teardown is killed (decided).** The per-prospect Profit Teardown is gone: a logistical nightmare, largely automated-AI busywork, and not what converts. Archive `teardown.html` and strip every free-Teardown CTA from `index.html` and the cold copy. The only button is book the call. The public-data case study (not a per-prospect teardown) carries the proof; exports are read on or after the call. This supersedes the repo everywhere the two disagree.
- [x] **Accent colour:** locked. A sharp, cold electric blue, one accent everywhere, used only on money and the leak.
- [x] **ICP band: $1M to $30M (decided).** One clean band on the site. The wider bottom costs nothing on the page, and a $1M brand is worth serving as long as the leaks genuinely clear the bill for them, which they do. Note the honesty check: at $1M revenue the flat $6,000 is a bigger share of margin than at $30M, so the promise must actually hold at the bottom of the band. Update the site copy from $1M–$20M to $1M–$30M; the Reorder Desk downsell still exists for anyone below or not yet ready.
- [x] **Case study brand:** *(done: a car-care brand's best-selling scratch remover, one of 1,856 harvested brands, live on the home page and /case-study since 2026-09-30; live page re-read and checked by eye 2026-10-01: price, fulfilment, weight and size unchanged, 0.818 oz past the 8 oz large-standard edge, FBA stock exposed to the 271-day bands; the name stays in the git-ignored `scripts/case-study/listing.json`)* Claude Code resolves this directly — pick the real listing from live public data per the case study build spec above (fits all four target-profile criteria, confirmed by eye to sit past an edge and exposed to the 271-day cliff), run it through the engine, and only then write the numbers. Not a pending human decision; it is a build task with everything it needs in the repo. Anonymize to category and band on the landing page, naming reserved for the content series with right of reply.
- [x] **Voice for the videos:** decided (mine). Both, in sequence: record in my own voice now so content ships with a real human voice, and in parallel build an ElevenLabs clone of that same voice. Once the clone is good enough to be indistinguishable, production goes fully automated voice-wise — my voice at scale, without me recording and editing every episode. The clone trains on my own real recordings, so the automated version still sounds like me, never a generic AI voice. Sequence: human voice first, clone trained alongside, switch over only when quality clears the bar. Staying off camera is already settled; wire the toolchain in the later production build with a fresh search.
- [x] **Re-derive the voice-note figures (Claude Code task):** *(done 2026-09-30, from `ratecard.json`: OPERATIONS.md, "The founder's dictated fee figures, re-derived")* recompute every figure I dictated by voice — the $10 and $50 price-band crossings, the $9.95-to-$10.49 example, the per-cell ranges, the USPS weight-zone jumps — directly from the engine's rate card and the dated 2026 schedules in Sources, since voice transcription may have garbled them. The repo and engine are the source of truth; replace any dictated number that does not match. Nothing here needs me.
- [x] **Attribution in plain English** *(done: terms §3, "How your Profit Record counts a dollar", word for word on /honesty; the terms carry the founder's approval)* in `terms.html`, drafted by Claude Code directly from measurement.py — the direct, isolated, attributable, none grading, the once-only credit, the materiality floor, capped at the promise — in plain language a client signs at kickoff. Code writes the full draft from the engine; I only review and sign. This is the same definition the honesty page and the dispute-mechanics section reference, so keep all three in sync.

## Sources

**Fee schedules (opened September 27, 2026):**

- [Eightx: Amazon's 2026 holiday fees, the real stack behind $0.32](https://eightx.co/blog/amazon-holiday-fulfillment-fees-peak-surcharge), citing Amazon's Seller Central help page for the peak window, the per-tier examples and the 3.5% surcharge.
- [E-Globe Business: Day 271, when storage goes from $1.50 to $5.45](https://eglobe.business.blog/2026/08/18/day-271-when-storage-goes-from-1-50-to-5-45/), for the aged-inventory bands, the 15th-of-month snapshot and Q4 storage rates.

**Repo (HubriconB2B, main):** `index.html`, `teardown.html`, `results.html`, `portal.html`, `intake.html`, `engine/src/hubricon_engine/measurement.py`, `GROWTH.md`, `HUBRICON.md`.

**Earlier chats:** [the Reorder Desk ladder and /learn plan](https://claude.ai/chat/02ca1a0c-b945-4526-9a1f-f389a39a83aa), and [the weekly public teardown pick](https://claude.ai/chat/9dfc7917-6e73-423f-864e-74f49f9d39f8).
