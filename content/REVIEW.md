# Review inbox

Updated 2026-09-19T00:12:45+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

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
