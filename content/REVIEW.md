# Review inbox

Updated 2026-09-19T19:45:24+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

## V01 · day 1 · tier A · pillar 4 — script gate

**Title:** Why most business advice is useless: survivorship bias, with numbers  
**Thumbnail:** $65,320 ⟨year_luck_spread⟩ in amber beside the fan of paths, the top tenth lit  
**Spiky claim:** Most of the gap between the top tenth and the median of similar businesses is dice, and from the outside you cannot tell which.  
**Misconception:** The founders who finished on top did something different. Find out what, and copy it.  
**CTA:** Subscribe, and the newsletter. Nothing else.  
**Estimated runtime:** about 4 min 33 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $65,320 ⟨year_luck_spread⟩. That's the gap between the luckiest tenth and the unluckiest tenth of 2,000 ⟨year_paths⟩ versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.
2. $45,419 ⟨year_top_vs_median⟩ above the median, same prices, same reorders, same ad budget. That's how far luck alone carried the top tenth in a year. Everything they'd tell you about how they did it would be true, and useless.
3. Here are 2,000 ⟨year_paths⟩ companies that ran an identical plan. The top tenth finished with $1,014,998 ⟨year_top_decile⟩. The bottom tenth finished with $924,168 ⟨year_bottom_decile⟩. Only one of those groups gets asked for advice.

### Script

**[0:00] HOOK**  
$65,320 ⟨year_luck_spread⟩. That's the gap between the luckiest tenth and the unluckiest tenth of 2,000 ⟨year_paths⟩ versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.  

**[0:15] LET THEM BE WRONG**  
Here's the model most of us run on. Somebody grew a brand until it was big. They wrote the post, they did the podcast, they listed the moves. Reorder deeper. Hold the price. Cut the bottom of the catalog. The moves worked for them, so the moves must be the reason. It's a fair model. It's how we learn nearly everything. Watch someone succeed, then do what they did. The problem isn't the logic. The problem is who we get to watch.  

**[0:45] THE CRACK**  
So let's find out what the winners did. Not from an interview. From a machine that ran the same plan 2,000 ⟨year_paths⟩ times. One catalog, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year in sales, $262,000 ⟨cash_on_hand⟩ in the bank on day one. Same prices every run. Same reorder points. Same ad spend. The only thing that changes between runs is which customers show up on which day. Here's how the year ends. The median finished at $969,579 ⟨year_terminal_p50⟩. The top tenth finished at $1,014,998 ⟨year_top_decile⟩. The bottom tenth, $924,168 ⟨year_bottom_decile⟩.  

**[1:15] CHAPTER 1 — THE DICE**  
Now go and interview the top tenth. Every one of them can tell you, truthfully, what they did. They reordered on schedule. They held their price through the slow months. They kept the ads running. And every one of those things is also what the bottom tenth did, because it is the same plan. The gap between $1,014,998 ⟨year_top_decile⟩ and $924,168 ⟨year_bottom_decile⟩ is which days the customers came, and nothing else. That gap is $65,320 ⟨year_luck_spread⟩. It's 7% ⟨year_luck_spread_pct⟩ of the median outcome, produced by the order the demand arrived in. If you only ever hear from the top, you will credit all of it to the moves. The moves were shared. The outcome wasn't. And the story the winners tell about the moves will be sincere, detailed, and wrong about what caused what.  

**[2:45] CHAPTER 2 — THE WORST DAY**  
Here's the part that should bother you more. Look at the worst day of the year for the winners. The lowest their cash went was $95,201 ⟨year_top_trough⟩. Now look at the lowest point for every run, winners and losers together: $95,201 ⟨year_all_trough⟩. Same number. The top tenth went through the identical worst day as the bottom tenth, on the same date, for the same reason: the supplier wires leave before the platform pays out. Nobody in the winners' circle will mention that day, because they came out the other side and it stopped mattering. The people it did matter to aren't giving interviews. That is survivorship bias in a sentence. The sample you can hear from was selected by the outcome you are trying to explain. So the advice isn't merely incomplete. It is tilted toward whatever risk the survivors happened to survive.  

**[4:00] WHAT TO DO**  
A short list, and you can do all of it this week. First, before you copy anyone, ask for the denominator. How many people ran this plan, and how many of them are not on the podcast. If nobody can answer, treat the advice as a story, not a method. Next, look for the shared moves. If the winners and the losers did the same thing, that thing is not the explanation, however confidently it's told. Last, run your own plan more than once. Take your last year, change nothing but the order the demand arrived in, and see how wide the spread gets. If it's wide, most of what you'd credit to skill is variance, and the plan should be judged on its worst tenth, not its best.  

**[4:45] THE HONEST LIMIT**  
What you can't do by hand is that last step at any real scale. Running a year of a 24 ⟨n_skus⟩-product catalog 2,000 ⟨year_paths⟩ times, with demand that moves together across products the way it really does, is a model, and a bad model is worse than no model. What you can do today is stop asking winners how they won. Ask how many people ran their plan, and where the rest of them are.  
*CTA:* If this was useful, subscribe. The newsletter carries one of these a week.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the spread lands on the first word, then the count of paths |  |
| 0:15 | kinetic: the misconception in the viewer's own words (a real screenshot of a "how I scaled it" post replaces this beat when the founder supplies one) |  |
| 0:45 | paths: every path drawn thin, then the ending spread at the right edge | cash horizon paths, one-year horizon, Tarnhollow demo data |
| 1:15 | paths: the top tenth lit amber, the median line, the spread bracket at the right edge | cash horizon paths, one-year horizon, Tarnhollow demo data |
| 2:45 | cash_cone: the cone with the trough marked and the supplier wires as red ticks | cash horizon on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time |  |
| 4:45 | kinetic: the closing question |  |

### Decide

```
hubricon-content approve 01-survivorship-bias
hubricon-content reject  01-survivorship-bias --note "what to change"
```
Edit `content/videos/01-survivorship-bias/script.md` first if you prefer; it is re-validated on approve.

## V04 · day 4 · tier A · pillar 4 — script gate

**Title:** Your A/B test told you nothing. Here's the sample size you needed  
**Thumbnail:** 546 ⟨n_for_se_tenth⟩ months in amber beside the error ladder: the standard error falling as months of price history are added, with the rungs marked  
**Spiky claim:** Nearly every price test an operator has ever called a win was noise, and the ones that were real could not be told apart from the outside.  
**Misconception:** I changed the price, sales went up for a few weeks, so the price change worked.  
**CTA:** Subscribe, and the newsletter. Nothing else.  
**Estimated runtime:** about 6 min 12 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 546 ⟨n_for_se_tenth⟩ months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.
2. 2.64 ⟨el_ci_width⟩. That's how wide the honest answer is on one product's demand curve after 12 ⟨el_periods⟩ months of price history. You read your few-week test as worked or didn't. It did neither, and the width is the part nobody showed you.
3. 91 ⟨anom_detector_flagged⟩ findings. That's what the detectors alone raised on a 24 ⟨n_skus⟩-product catalog in one sweep. After the noise was measured, 18 ⟨anom_flagged⟩ were real. Your price test is one of those detectors, and nobody measured its noise.

### Script

**[0:00] HOOK**  
546 ⟨n_for_se_tenth⟩ months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.  

**[0:15] LET THEM BE WRONG**  
Here's the test most of us run. Pick a product. Raise the price a notch. Watch it for a few weeks. Compare units and revenue to the weeks before. If revenue went up and units held, keep the new price. If units fell away, put it back. It's a fair test. It's what every pricing tool suggests, and it feels like evidence because something measurable happened. The problem isn't the idea of testing. The problem is how much a few weeks can tell you, and it's far less than it looks.  

**[0:45] THE CRACK**  
Take one product off the demo catalog. TH-OVEMIT-22 ⟨el_sku⟩, from Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, about $3.5M ⟨annual_revenue_m⟩ a year across 24 ⟨n_skus⟩ products. This one has 12 ⟨el_periods⟩ months of history where the price moved and the units moved with it. That's far more than a few weeks. Fit the demand curve through it and you get a best guess: an elasticity of -2.20 ⟨el_point⟩. Units fall faster than price rises, by about that ratio. Now ask the fit how sure it is. The honest range runs from -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩. At one end a price rise is a disaster. At the other it's nearly free. Same product, same data, same fit. The width of that range is 2.64 ⟨el_ci_width⟩, and it's the thing your test never showed you.  

**[1:15] CHAPTER 1 — WHY THE BAND IS WIDE**  
Why so wide, with a year of data? Because demand moves on its own. The same plan, run again with the customers arriving in a different order, finishes $65,320 ⟨year_luck_spread⟩ apart after a year, with no price change at all. Every month on this curve carries that noise. Draw the 12 ⟨el_periods⟩ points and the line through them. Each point could sit a good way higher or lower and still be the same product in the same month. So the line can tilt, and every tilt the points allow is a different elasticity. The fit reports that as a standard error, 0.67 ⟨el_se⟩ here, and the range you saw is the line tilting as far as the points let it. The fit won't speak at all until it has 5 ⟨el_min_periods⟩ months and the price has moved by at least 2% ⟨el_min_price_cv⟩. On this catalog, 2 ⟨el_skus_insufficient⟩ of the 24 ⟨n_skus⟩ products failed that bar. Their prices never moved, so there was no curve to draw. Your few-week test is below that bar for every product it touched. Not a wide answer. No answer.  

**[2:45] CHAPTER 2 — THE SAMPLE SIZE YOU NEEDED**  
Here's the part that should bother you more. Suppose you commit to getting more data. How much more? The error falls as you add months, but it falls slowly, and every step down costs more than the last. On this product, bringing the error to something you'd act on takes 22 ⟨n_for_se_half⟩ months. Bringing it down by the same kind of step again takes 87 ⟨n_for_se_quarter⟩. Pinning it tightly enough that the price decision is unambiguous takes 546 ⟨n_for_se_tenth⟩ months. Products don't live that long. The sample size you needed was never going to arrive. And it gets worse when you test more than one product. Run the short test across a catalog and you will find winners, because some products will move the right way for a few weeks on noise alone. On this same catalog, a sweep of 364 ⟨anom_scanned⟩ series raised 91 ⟨anom_detector_flagged⟩ flags from the detectors. Then each detector was run 4,000 ⟨null_replicates⟩ times on data with nothing in it, to learn what its own noise looks like, and the flags were held to a false discovery rate of 5% ⟨anom_fdr_q⟩. 18 ⟨anom_flagged⟩ survived. The rest were the noise floor wearing the costume of a finding. Your price test is one detector with no null run behind it, so every winner it hands you is unchecked. The more products you test, the more winners it hands you, and the smaller the share that are real.  

**[4:00] WHAT TO DO**  
A short list, and it's this week's work. First, stop reading a test as worked or didn't. Write down the range the data allows, and if you can't compute a range, treat the test as a story. Next, make the price move on purpose. Small steps, capped at 5% ⟨pm_step_cap⟩, in both directions, over months, because the fit needs 5 ⟨el_min_periods⟩ of them and at least 2% ⟨el_min_price_cv⟩ of movement before it can say anything. Then price on the range, not the point. The best move on the demo catalog is TH-CASIRO-01 ⟨pm_sku⟩ to $37.84 ⟨pm_new_price⟩, a 5.0% ⟨pm_step⟩ step, worth about $388 ⟨pm_delta⟩ a month. The honest version is $20 ⟨pm_delta_p5⟩ to $909 ⟨pm_delta_p95⟩, with a 4% ⟨pm_p_loss⟩ chance it loses. Decide looking at the whole range. Last, keep a control. Leave one product's price where it is and watch how far it moves on its own over the same weeks. That's your noise floor, and a winner that didn't beat it wasn't a winner.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is fit one product's curve in a spreadsheet. Log of units against log of price, the slope is the elasticity, and the spreadsheet gives you the standard error. Do that on your top products and it's worth an afternoon. What you can't do by hand is keep it honest across 24 ⟨n_skus⟩ products every month, with errors that don't trust the noise to be tidy, and check each decision against 4,000 ⟨null_replicates⟩ runs of nothing. That part is a model, and a bad model is worse than the few-week test. What you can do today is stop calling a test a win. Ask how wide the answer is.  
*CTA:* If this was useful, subscribe. The newsletter carries one of these a week.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the month count lands on the first word, then the phrase "pinned tightly enough" |  |
| 0:15 | kinetic: the before-and-after comparison in the viewer's own words (a real screenshot of a price-test dashboard replaces this beat when the founder supplies one) |  |
| 0:45 | elasticity: the points appear month by month, the fitted line, then the band opens to the full range | ELASTICITY.FIT on Tarnhollow demo data |
| 1:15 | elasticity: each point jitters within its own noise, the line tilts through the allowed range, the band is annotated with the standard error | ELASTICITY.FIT on Tarnhollow demo data; the year's spread from cash horizon paths, one-year horizon, Tarnhollow demo data |
| 2:45 | sample_size: the error curve falling with months of history, the three rungs marked and named as they're spoken; then kinetic for the sweep, the detector count shrinking to the survivors | derived from ELASTICITY.FIT standard error, Tarnhollow demo data; ANOMALY.SCAN null calibration on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time; the price move with its range as a band, not a bar |  |
| 4:45 | kinetic: the closing question |  |

### Decide

```
hubricon-content approve 04-ab-test-sample-size
hubricon-content reject  04-ab-test-sample-size --note "what to change"
```
Edit `content/videos/04-ab-test-sample-size/script.md` first if you prefer; it is re-validated on approve.

## V05 · day 5 · tier B · pillar 2 — script gate

**Title:** Cash conversion cycle: the number that decides whether you survive  
**Thumbnail:** $95,201 ⟨min_p5⟩ in amber over the cash cone fragment, the trough marked on day 13 days ⟨min_p5_day⟩ with the supplier wires as red ticks  
**Spiky claim:** A profitable catalog can run out of cash on a date you can read off a calendar, and most operators watch the P&L instead of the calendar.  
**Misconception:** We're profitable, so cash takes care of itself. If the margin is there, the bank balance follows.  
**CTA:** The free Profit Teardown at /apply  
**Estimated runtime:** about 7 min 28 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $95,201 ⟨min_p5⟩. That's where this catalog's cash bottoms out on day 13 days ⟨min_p5_day⟩, on a business making 32.3% ⟨net_pct_latest⟩ net. You'd say a margin like that can't run out of money. It can, on a date you can read off a calendar.
2. $345,501 ⟨wires_total⟩ leaves this account in supplier wires inside 90 days ⟨horizon_days⟩, against $262,000 ⟨cash_on_hand⟩ in the bank. The margin says fine. The margin doesn't know when the money moves, and the dates are the whole story.
3. 40 days ⟨lead_time_typical⟩ from the wire to the goods landing. 14 days ⟨payout_cycle⟩ from the sale to the payout. Add the time on the shelf and you have the number that decides whether you survive, and almost nobody has written it down.

### Script

**[0:00] HOOK**  
$95,201 ⟨min_p5⟩. That's where this catalog's cash bottoms out on day 13 days ⟨min_p5_day⟩, on a business making 32.3% ⟨net_pct_latest⟩ net. You'd say a margin like that can't run out of money. It can, on a date you can read off a calendar.  

**[0:15] LET THEM BE WRONG**  
Here's the model. You watch the P&L. Revenue up, margin healthy, net positive, so the business is fine and the bank balance is a lagging copy of the P&L. When cash gets tight it's a surprise, and the explanation is always something else. A big PO. A slow payout. A bad month. It's a fair model, because over a long enough window the P&L and the bank do agree. The trouble is the window. Inside it, the money leaves on one set of dates and comes back on another, and the P&L doesn't carry dates.  

**[0:45] THE CRACK**  
Here's the demo catalog on screen. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. Last month: $318,632 ⟨rev_latest⟩ of sales, $102,864 ⟨net_latest⟩ of true net profit, 32.3% ⟨net_pct_latest⟩ net margin. On the P&L this business is fine. Now the bank. $262,000 ⟨cash_on_hand⟩ on hand today. Inside the next 90 days ⟨horizon_days⟩, the supplier wires already scheduled add up to $345,501 ⟨wires_total⟩. That's more than the cash in the bank, on a business that is profitable every month. The money comes back. The question is when, and whether the balance runs dry on the way.  

**[1:15] CHAPTER 1 — FIND IT**  
On screen is the cash cone. 10,000 ⟨n_paths⟩ possible versions of the next 90 days ⟨horizon_days⟩, drawn from what this catalog's demand actually does, with every supplier wire as a red tick. Read it left to right, and find the clocks. First, the wire schedule. 35 ⟨wire_count⟩ wires inside the window. The largest, $23,482 ⟨largest_wire⟩, for TH-ENADUT-03 ⟨largest_wire_sku⟩, leaves on day 0 days ⟨largest_wire_day⟩. That's today. Next, how long the goods take to arrive. The typical supplier lead time here is 40 days ⟨lead_time_typical⟩. For that long the money is gone and there's nothing new to sell. Then the shelf. Once units land they sit until they sell. The tightest product in this catalog, TH-STAMIX-12 ⟨stockout_worst_sku⟩, has 22 days ⟨stockout_worst_cover⟩ of cover, and slower products sit longer than that. Last, the payout. The platform holds the sale for a 14 days ⟨payout_cycle⟩ cycle before it pays you. Now put the clocks in a row. Wire, then lead time, then shelf, then payout. The cash conversion cycle is the length of that row: the days between a dollar leaving for the supplier and the same dollar landing back in the bank. It isn't on the P&L because the P&L has no calendar. It's on this chart, because this chart is nothing but a calendar.  

**[3:30] CHAPTER 2 — VERIFY IT**  
Now verify it against the cone. The median path's low point is $95,201 ⟨min_median⟩. The bad paths' low point, the worst day of the unlucky tail, is $95,201 ⟨trough_p5⟩, and it arrives on day 13 days ⟨min_p5_day⟩. Look where that day sits. It's after the wires have left and before the goods have landed, let alone sold and paid out. That's the cycle showing up as a date. In this run the share of paths that ever runs dry is 0.0% ⟨p_ruin⟩. That's with $262,000 ⟨cash_on_hand⟩ in the bank on day 0 days ⟨largest_wire_day⟩. Bring the starting balance down toward $95,201 ⟨trough_p5⟩ and the same schedule, same margin, same products, starts touching the floor. The margin never changed. Only the balance did, and the dates did the rest. And here's what the cone knows that a spreadsheet doesn't. Products don't sell independently. Across this catalog, demand moves together with a correlation of 0.48 ⟨demand_corr⟩, so a slow week is slow for most of the products at once, and the trough is deeper than it would be if each product rolled its own dice. Seen from the other end, after 90 days ⟨horizon_days⟩ the top of the cone is $352,682 ⟨terminal_p90⟩ and the bottom is $322,319 ⟨terminal_p10⟩. Same plan, same margin. Over a full year that gap opens to $65,320 ⟨year_luck_spread⟩ on dice alone.  

**[5:30] WHAT IT'S WORTH**  
So what's the number worth? Every day you shorten the cycle is a day less of cash sitting in the gap, and here's what's sitting in the gap on this catalog right now. On the shelf clock, stock ordered past its economic quantity costs $3,874 ⟨nv_bleed_month⟩ a month in fees to hold, and there are 13 ⟨nv_econ_orders⟩ orders the newsvendor would trim. That's cash parked on a shelf. On the wire clock, the largest wire is $23,482 ⟨largest_wire⟩ and it goes out on day 0 days ⟨largest_wire_day⟩, so it sets the depth of the trough more than any other line on the calendar. On the payout clock, 14 days ⟨payout_cycle⟩ is fixed by the platform. You can't shorten it. You can stop treating it as instant. And the price of getting this wrong isn't a fee. It's the reorder you can't place because the cash is in transit, and the rank you buy back with ads afterwards. The risk model puts the expected shortfall below plan in a bad period at $38,007 ⟨risk_cvar_95⟩, and the worst run of periods at $61,358 ⟨risk_worst_5⟩ of net against an expected $99,365 ⟨risk_expected_net⟩. The cycle is where that shortfall lands.  

**[7:30] WHAT TO DO**  
This week. First, write the cycle down. Wire date, landing date, first sale, first payout, for your top products, from your own POs and settlement reports. It's a spreadsheet with dates in it, and most operators have never made one. Next, draw the wires. Every scheduled supplier payment inside the next 90 days ⟨horizon_days⟩, on a calendar, against the cash you hold and the payouts you expect. Where the line dips lowest is your own day 13 days ⟨min_p5_day⟩. Then move the clocks. Split the largest wire into a deposit and a balance where the supplier allows it. That flattens the trough without touching the margin. Trim the orders the newsvendor flags as overstocked, because that cash comes back onto the calendar. Ask for terms before you ask for growth. Last, hold cash for the trough, not for the month. Fixed costs here are $31,500 ⟨monthly_fixed_costs⟩ a month, and the trough arrives on day 13 days ⟨min_p5_day⟩. The right reserve is the trough plus a buffer for the cone's bad tail, not a round number of months.  

**[9:00] THE HONEST LIMIT**  
What you can do yourself is the calendar for your top products, and it's worth doing this week. What you can't do by hand is the cone. 10,000 ⟨n_paths⟩ versions of the next 90 days ⟨horizon_days⟩ across 24 ⟨skus_in_cone⟩ products with demand that moves together, redrawn every time a wire moves or a payout slips. That's a model, and this is one of the places a bad model is dangerous, because a cone drawn too narrow tells you you're safe. The free Profit Teardown runs this cone on your own exports and hands you the date and the trough. What you can do today is stop reading the margin as a cash forecast. Find your day 13 days ⟨min_p5_day⟩.  
*CTA:* The free Profit Teardown at /apply. Your own cash cone, from your own exports, inside a day.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the trough figure lands on the first word, then the day |  |
| 0:15 | kinetic: the P&L read in the viewer's own words (a real P&L screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | waterfall: revenue down to true net for the latest month; then cash_cone: the cone opens from today's balance with the wires as red ticks | MARGIN.DECOMP on Tarnhollow demo data; cash horizon on Tarnhollow demo data |
| 1:15 | cash_cone: the wires as ticks; then the lead-time span, the shelf span and the payout lag drawn as brackets under the axis, joined into one bar | cash horizon on Tarnhollow demo data; MONTE_CARLO.RUN on Tarnhollow demo data for lead time and cover |
| 3:30 | cash_cone: the trough marked at day {{min_p5_day}}, the floor line, the fan widening to the right with the ends labelled | cash horizon on Tarnhollow demo data; cash horizon paths, one-year horizon, Tarnhollow demo data |
| 5:30 | newsvendor: the overstocked orders as bars above the economic quantity; then kinetic for the clocks and the shortfall | NEWSVENDOR on Tarnhollow demo data; risk on Tarnhollow demo data |
| 7:30 | kinetic: the steps landing one at a time; cash_cone with the largest wire split and the trough lifting | cash horizon on Tarnhollow demo data |
| 9:00 | kinetic: the closing line |  |

### Decide

```
hubricon-content approve 05-cash-conversion-cycle
hubricon-content reject  05-cash-conversion-cycle --note "what to change"
```
Edit `content/videos/05-cash-conversion-cycle/script.md` first if you prefer; it is re-validated on approve.

## V07 · day 7 · tier B · pillar 5 — script gate

**Title:** Contribution margin vs gross margin — the one that actually matters  
**Thumbnail:** 38.4% ⟨gross_vs_contribution_gap⟩ in amber over the waterfall fragment, the fee step and the ad step lit  
**Spiky claim:** Gross margin is a number for your supplier's benefit, not yours. The only margin a product has is what's left after the platform and the ads take theirs.  
**Misconception:** Gross margin is my margin. Revenue minus cost of goods is what each product earns, and fees and ads are overhead.  
**CTA:** The course page at /learn, where the method is written out in full; no service mention  
**Estimated runtime:** about 7 min 58 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 70.7% ⟨gross_pct_latest⟩ gross margin. 32.3% ⟨contribution_pct_latest⟩ after the platform and the ads. You'd say the first number is your margin and the rest is overhead. The gap between them is 38.4% ⟨gross_vs_contribution_gap⟩ of revenue, and it's decided product by product, not in overhead.
2. 38.4% ⟨gross_vs_contribution_gap⟩ of revenue. That's how far this catalog's gross margin sits above the margin it keeps, once the platform and the ads are paid. You'd call that overhead. It isn't, and treating it that way is why the bestseller looks better than it is.
3. $102,395 ⟨fees_latest⟩ in platform fees last month, on $318,632 ⟨rev_latest⟩ of sales. Gross margin never saw it. Contribution margin does, and it's the only margin that tells you which product to reorder.

### Script

**[0:00] HOOK**  
70.7% ⟨gross_pct_latest⟩ gross margin. 32.3% ⟨contribution_pct_latest⟩ after the platform and the ads. You'd say the first number is your margin and the rest is overhead. The gap between them is 38.4% ⟨gross_vs_contribution_gap⟩ of revenue, and it's decided product by product, not in overhead.  

**[0:15] LET THEM BE WRONG**  
Here's the model. Revenue minus what the goods cost you is the margin. That's the number on the product tab of your own spreadsheet, it's the number the supplier negotiation is about, and it's the number you'd quote if someone asked how good a product is. Fees and ads are real, but they're the cost of doing business, so they live in overhead, below the line, spread across everything. It's a fair model. It's how the accounts are laid out, and for a business with one product it's even correct. The trouble starts the moment there's more than one product, because from then on the fees and the ads are not spread. They're charged.  

**[0:45] THE CRACK**  
Here's the demo catalog on screen. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. Last month, $318,632 ⟨rev_latest⟩ of sales. Landed cost of goods, $93,443 ⟨cogs_latest⟩. So the gross margin is 70.7% ⟨gross_pct_latest⟩. Healthy. Now watch the waterfall. Platform fees: $102,395 ⟨fees_latest⟩, which is 32.1% ⟨fee_share_latest⟩ of revenue. Ads, allocated to the products that spent them: $19,930 ⟨ads_latest⟩. What's left is $102,864 ⟨net_latest⟩, and that's 32.3% ⟨contribution_pct_latest⟩ of revenue. The gap between the margin you quote and the margin you keep is 38.4% ⟨gross_vs_contribution_gap⟩ points of revenue. And none of it is overhead. Every dollar of it was charged to a specific product on a specific order, and the platform's own report says which.  

**[1:15] CHAPTER 1 — FIND IT**  
Find it in your own reports. Start with the settlement report, the one the platform sends when it pays you. Every fee is on it, by order, by product: the referral fee, fulfilment, storage, refund administration, and the advertising invoice if it's netted from the payout. That is your fee line, and it's per product, not per business. Next, the advertising report, by campaign and by product. Sponsored spend belongs to the product that was advertised. Where a campaign covers several products, allocate its spend by the sales the campaign produced for each of them, not by each product's share of catalog revenue, because revenue share hands the bestseller's ad bill to the products that never needed ads. On this catalog, $4,101 ⟨ad_bleed_month⟩ a month goes to search terms with no attributed sales at all. That's a cost with no sale to carry it, and it lands on whichever product the campaign belongs to. Then the landed cost sheet. Unit cost, inbound freight, packaging, duty. Not the invoice price; the price of the unit sitting in the warehouse. Put those side by side, per product, and the number falls out: price, less landed cost, less the fees on that product, less the ads on that product. Now it has a name. That's contribution margin. It's what the product contributes toward everything that isn't a product: salaries, rent, software, you. Gross margin stops before the platform. Contribution margin stops where your money actually starts.  

**[3:30] CHAPTER 2 — VERIFY IT**  
Now verify it on the product you're proudest of. The bestseller here is TH-CHEKNI-08 ⟨bestseller_sku⟩. $33,634 ⟨bestseller_revenue⟩ of revenue last month, 11% ⟨top_sku_share⟩ of the catalog. On gross margin it looks like the whole business. On contribution it earns $14,339 ⟨bestseller_net⟩, a margin of 42.6% ⟨bestseller_net_pct⟩, and by contribution it ranks 1 ⟨bestseller_rank_by_net⟩ in the catalog. So on this catalog the bestseller survives the test. That's not the usual outcome, and the point is you cannot know until you've run it. The product at the bottom by contribution is TH-TRICOR-23 ⟨worst_net_sku⟩, at 23.4% ⟨worst_net_pct⟩. The count of products losing money after ads this month, on this catalog, is 0 ⟨n_skus_negative_net⟩. Had it been anything else, gross margin would have hidden it, because a product can carry a fine gross margin and a negative contribution at the same time. All it takes is a fee tier or an ad campaign that eats the difference, and neither of those shows up in revenue minus cost of goods. The spread across the catalog runs from 23.4% ⟨worst_net_pct⟩ to 42.6% ⟨best_net_pct⟩. Same catalog, same supplier, same gross margin logic, and the products sit that far apart once the platform and the ads are charged to the product that incurred them. That ranking, by contribution, is the only ranking that should decide a reorder, a price move or an ad budget.  

**[5:30] WHAT IT'S WORTH**  
What's the difference worth? Every decision that used the wrong margin. Reorders first. A product with a high gross margin and a thin contribution gets restocked deep, and the cash sits on a shelf. The newsvendor on this catalog finds $3,874 ⟨nv_bleed_month⟩ a month of fees on stock ordered past its economic quantity. Ads next. The break-even return on ad spend is set by contribution, never by gross. On this catalog it's 2.61 ⟨ad_breakeven_roas⟩. The worst campaign, Catalog - Auto ⟨ad_worst_campaign⟩, returns 0.97 ⟨ad_worst_marginal_roas⟩ on its last dollar, which is below break-even at contribution and looks perfectly healthy if you judge it at gross. Pricing. A price rise on a product with a fee tier in the way can lift gross margin and cut contribution in the same move, and only the contribution waterfall shows it. And concentration. There are 24 ⟨n_skus⟩ products on the shelf, but by where the money comes from the catalog behaves like 19.3 ⟨effective_skus⟩, so the risk of the business sits in fewer products than the shelf suggests. In short: the margin you quote and the margin you keep are 38.4% ⟨gross_vs_contribution_gap⟩ of revenue apart on this catalog, and every reorder, bid and price set on the wrong one was set on a number that's wrong by that much.  

**[7:30] WHAT TO DO**  
This week. First, build the waterfall for your top products. Price, landed cost from the cost sheet, fees from the settlement report, ads from the campaign report allocated by attributed sales. One row per product, and the last column is contribution. Next, rank by that column. Not by revenue, not by gross. Read the bottom of the list before the top, because the bottom is where the decisions are. Then set your break-even return on ad spend from contribution and hold every campaign to it, starting with the one that returns least on its last dollar. Last, take gross margin off the dashboard. Keep it for the supplier conversation, where it belongs, and put contribution where you look every morning. When a product looks better on gross than on contribution, that gap is the platform and the ads, and it's per product, so it's yours to fix per product.  

**[9:00] THE HONEST LIMIT**  
What you can do yourself is the waterfall for your top products, this week, from reports you already export. It's an afternoon, and it changes what you reorder. What you can't do by hand is the allocation at scale. 24 ⟨n_skus⟩ products, every fee line on every order, ads allocated by attributed sales across campaigns that overlap, every month, with the fee tiers rechecked whenever a weight or a price moves. Done by hand it drifts back to revenue share inside a few months, and revenue share is gross margin wearing a different name. That part is a model. What you can do today is stop quoting gross margin as if it were yours. Rank by contribution, and read the bottom of the list.  
*CTA:* The course page at /learn, where the method is written out in full.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the gross figure lands, then the contribution figure under it, then the gap between them |  |
| 0:15 | kinetic: the gross margin line in the viewer's own words (a real spreadsheet screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | waterfall: revenue, then landed cost, then fees, then ads, then what's left, each step landing as it's spoken | MARGIN.DECOMP on Tarnhollow demo data |
| 1:15 | kinetic: the report names landing one at a time; then waterfall for a single product, each report feeding its own step | MARGIN.DECOMP on Tarnhollow demo data; SPEND.RESPONSE on Tarnhollow demo data for the unattributed spend |
| 3:30 | waterfall: the bestseller alone, revenue to contribution; then kinetic: the catalog ranked by contribution with the top and bottom named | MARGIN.DECOMP on Tarnhollow demo data |
| 5:30 | kinetic: reorders, ads, pricing, concentration as chapter cards; waterfall fragment for the ad break-even | NEWSVENDOR on Tarnhollow demo data; SPEND.RESPONSE on Tarnhollow demo data; risk on Tarnhollow demo data |
| 7:30 | kinetic: the steps landing one at a time; the ranked table with the bottom rows lit |  |
| 9:00 | kinetic: the closing line |  |

### Decide

```
hubricon-content approve 07-contribution-vs-gross-margin
hubricon-content reject  07-contribution-vs-gross-margin --note "what to change"
```
Edit `content/videos/07-contribution-vs-gross-margin/script.md` first if you prefer; it is re-validated on approve.

## V08 · day 8 · tier A · pillar 3 — script gate

**Title:** Elasticity in plain English, and why your price is probably wrong  
**Thumbnail:** -2.20 ⟨el_point⟩ in amber over the elasticity fragment: the demand line with its band, and the top of the profit hill marked as a stretch, not a point  
**Spiky claim:** Almost nobody's price sits on top of the profit hill, because almost nobody has measured the slope, and the ones who moved on gut are as likely to have moved away from the top as toward it.  
**Misconception:** If units are holding, the price is right. Elasticity is a warning not to raise prices.  
**CTA:** The course page at /learn, where the method is written out in full; no service mention  
**Estimated runtime:** about 6 min 13 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. -1.86 ⟨el_median⟩. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
2. 22 ⟨pm_count⟩ of 24 ⟨n_skus⟩. That's how many products on this catalog have a price move worth making, once you know how fast units fall when the price moves. You'd say your prices are right because units are holding. That isn't the test, and here's the test.
3. $388 ⟨pm_delta⟩ a month, from moving one product's price by 5.0% ⟨pm_step⟩. The honest range is $20 ⟨pm_delta_p5⟩ to $909 ⟨pm_delta_p95⟩. You'd say you'd have found that yourself if it were there. You can't see it, because the number it depends on has never been measured.

### Script

**[0:00] HOOK**  
-1.86 ⟨el_median⟩. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.  

**[0:15] LET THEM BE WRONG**  
Here's how most prices get set. Landed cost, times a markup that gives a gross margin you're comfortable with. A look at the competitors. Then a gut check: would I pay that. If units hold after a change, the price was fine. If units drop, it was too high, put it back. It's a fair method. It's what everyone does, and it isn't stupid, because units are the thing you can see. The thing you can't see is the line the units sit on, and the price you want is on that line, not on the markup.  

**[0:45] THE CRACK**  
Take one product from the demo catalog. TH-OVEMIT-22 ⟨el_sku⟩, from Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. It has 12 ⟨el_periods⟩ months of history where the price moved and the units moved with it. Plot them. Price across, units up. The points slope down: dearer, fewer. Fit a line through them and read the slope as a ratio, how fast units fall for how far the price rises. On this product the ratio is -2.20 ⟨el_point⟩. That's the whole of elasticity. A price rise of a given size costs you units by that multiple of it. It isn't a warning. It's a measurement. And it comes with a range, -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩, because 12 ⟨el_periods⟩ months of noisy demand can't pin it tighter than that.  

**[1:15] CHAPTER 1 — THE HILL**  
Now why the number tells you where the price should sit. Raise the price and it pulls in both directions. Every unit you still sell earns more. And you sell fewer units. Profit is what's left when those pull against each other, so as the price climbs, profit climbs, then flattens, then falls. It's a hill. Every product has one. The top of the hill is the price you want, and where the top sits depends on the slope and the margin, and nothing else. The slope is the elasticity. The margin is how much of each dollar you keep at the edge, and it is not the gross margin. It's what's left after the platform's cut and the ad it took to sell the unit, because those are charged per unit too. On this catalog the platform keeps 32.1% ⟨fee_share_latest⟩ of revenue. The margin after cost, fees and ads is 32.3% ⟨contribution_pct_latest⟩, against a gross margin of 70.7% ⟨gross_pct_latest⟩. Set the price off the gross number and you've climbed the wrong hill. Here's the rule in words, before any symbol. The faster the units fall, the closer the price should sit to your true cost. The slower, the further above it. And now the symbol, as a convenience: the fraction of the price you keep above true unit cost should equal the inverse of the elasticity. That's all it is.  

**[2:45] CHAPTER 2 — THE TOP IS A STRETCH**  
Here's the part a good operator gets wrong even after the hill. The top isn't a point. The elasticity came with a range, -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩, so the top is a stretch of hill, and a price move is a bet on where inside that stretch the top really is. So the honest question isn't what's the best price. It's what's the best step, given what we don't know. Run that across the whole catalog. 22 ⟨el_skus_fit⟩ products have a usable fit. 2 ⟨el_skus_insufficient⟩ were refused, because their price never moved enough to draw a line; the fit won't speak until the price has moved by 2% ⟨el_min_price_cv⟩ across 5 ⟨el_min_periods⟩ months, and on those products nobody ever moved it. Of the fitted ones, 22 ⟨pm_count⟩ have a move worth making. The best is TH-CASIRO-01 ⟨pm_sku⟩: a 5.0% ⟨pm_step⟩ step to $37.84 ⟨pm_new_price⟩, expected to add $388 ⟨pm_delta⟩ a month. The honest version is somewhere between $20 ⟨pm_delta_p5⟩ and $909 ⟨pm_delta_p95⟩, with a 4% ⟨pm_p_loss⟩ chance it loses money. Every step is capped at 5% ⟨pm_step_cap⟩, because a small step you can read is worth more than a big step you can't. Across every move the catalog picks up about $1,701 ⟨pm_total_delta⟩ a month in expectation. That's the sense in which your price is probably wrong. Not badly. Wrong by a step, on most products, in a direction you can only learn by measuring the slope.  

**[4:00] WHAT TO DO**  
This week. First, pick your top products and pull price and units by month, as far back as you have. Next, plot them and fit the line: log of units against log of price. The slope is the elasticity, and the spreadsheet gives you the standard error beside it. If the price never moved, you have no line, and the first job is to move it, in small steps, both ways, and wait 5 ⟨el_min_periods⟩ months. Then compute your true unit margin, after the platform and the ads, not the gross one, and put the price where the fraction you keep equals the inverse of the slope. Last, take the step as a step, not a leap. Cap it, read the result against the range, and go again.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is the line for your top products, and it's worth an afternoon. What you can't do by hand is keep it honest across 24 ⟨n_skus⟩ products every month, with errors that don't assume the noise is tidy, and turn each range into a step that's the right size for what's unknown in it. Done by hand, the ranges get dropped inside a season and you're back to gut. That part is a model. What you can do today is stop treating units holding as proof. Measure the slope.  
*CTA:* The course page at /learn, where the method is written out in full.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the ratio lands on the first word, then "how fast units fall" over "how far the price rises" |  |
| 0:15 | kinetic: the markup method in the viewer's own words (a real pricing spreadsheet screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | elasticity: the points appear month by month, the fitted line, then the band opens to the full range | ELASTICITY.FIT on Tarnhollow demo data |
| 1:15 | elasticity: the demand line, then the profit hill built underneath it as the price sweeps across, the top marked; a second, lower hill drawn off the gross margin to show the wrong top | ELASTICITY.FIT on Tarnhollow demo data; MARGIN.DECOMP on Tarnhollow demo data |
| 2:45 | elasticity: the band widens and the hill's top becomes a shaded stretch; then kinetic: the catalog counts, the best move drawn as a band from the low case to the high case, not a bar | ELASTICITY.FIT on Tarnhollow demo data; PRICE.OPTIMUM on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time |  |
| 4:45 | kinetic: the closing line |  |

### Decide

```
hubricon-content approve 08-elasticity-plain-english
hubricon-content reject  08-elasticity-plain-english --note "what to change"
```
Edit `content/videos/08-elasticity-plain-english/script.md` first if you prefer; it is re-validated on approve.
