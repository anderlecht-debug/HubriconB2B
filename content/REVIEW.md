# Review inbox

Updated 2026-10-06T07:20:01+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

## V04 · day 4 · tier A · pillar 4 — script gate

**Title:** Your A/B test told you nothing. Here's the sample size you needed  
**Thumbnail:** 2,335 ⟨n_for_se_tenth⟩ months in amber beside the error ladder: the standard error falling as months of price history are added, with the rungs marked  
**Spiky claim:** Nearly every price test an operator has ever called a win was noise, and the ones that were real could not be told apart from the outside.  
**Misconception:** I changed the price, sales went up for a few weeks, so the price change worked.  
**CTA:** The free course at hubricon.com/learn, where the method is written out in full  
**Estimated runtime:** about 6 min 19 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 2,335 ⟨n_for_se_tenth⟩ months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.
2. 6.22 ⟨el_ci_width⟩. That's how wide the honest answer is on one product's demand curve after 12 ⟨el_periods⟩ months of price history. You read your few-week test as worked or didn't. It did neither, and the width is the part nobody showed you.
3. 106 ⟨anom_detector_flagged⟩ findings. That's what the detectors alone raised on a 24 ⟨n_skus⟩-product catalog in one sweep. After the noise was measured, 19 ⟨anom_flagged⟩ were real. Your price test is one of those detectors, and nobody measured its noise.

### Script

**[0:00] HOOK**  
2,335 ⟨n_for_se_tenth⟩ months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.  

**[0:15] LET THEM BE WRONG**  
Here's the test most of us run. Pick a product. Raise the price a notch. Watch it for a few weeks. Compare units and revenue to the weeks before. If revenue went up and units held, keep the new price. If units fell away, put it back. It's a fair test, and it feels like evidence because something measurable happened. The problem isn't testing. It's how much a few weeks can tell you, and it's far less than it looks.  

**[0:45] THE CRACK**  
Take one product off the demo catalog. TH-OVEMIT-22 ⟨el_sku⟩, from Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, about $3.5M ⟨annual_revenue_m⟩ a year across 24 ⟨n_skus⟩ products. This one has 12 ⟨el_periods⟩ months of history where the price moved and the units moved with it. That's far more than a few weeks. Fit the demand curve through it and you get a best guess: an elasticity of -2.76 ⟨el_point⟩. Units fall faster than price rises, by about that ratio. Now ask the fit how sure it is. The honest range runs from -5.87 ⟨el_ci_low⟩ to 0.35 ⟨el_ci_high⟩. At one end a price rise is a disaster. At the other it's nearly free. Same product, same data, same fit. The width of that range is 6.22 ⟨el_ci_width⟩, and it's the thing your test never showed you.  

**[1:15] CHAPTER 1 — WHY THE BAND IS WIDE**  
Why so wide, with a year of data? Because demand moves on its own. The same plan, run again with the customers arriving in a different order, finishes $43,327 ⟨year_luck_spread⟩ apart after a year, with no price change at all. Every month on this curve carries that noise. Each point could sit a good way higher or lower and still be the same product in the same month. So the line can tilt, and every tilt the points allow is a different elasticity. The fit reports that as a standard error, 1.39 ⟨el_se⟩ here, and the range you saw is the line tilting as far as the points let it. The fit won't speak at all until it has 5 ⟨el_min_periods⟩ months and 2% ⟨el_min_price_cv⟩ of price movement. On this catalog, 2 ⟨el_skus_insufficient⟩ of the 24 ⟨n_skus⟩ products failed that bar. Their prices never moved, so there was no curve to draw. Your few-week test is below that bar for every product it touched. Not a wide answer. No answer.  

**[2:45] CHAPTER 2 — THE SAMPLE SIZE YOU NEEDED**  
Here's the part that should bother you more. Suppose you commit to more data. How much more? The error falls as you add months, but it falls slowly, and every step down costs more than the last. On this product, bringing the error to something you'd act on takes 93 ⟨n_for_se_half⟩ months. Bringing it down by the same kind of step again takes 374 ⟨n_for_se_quarter⟩. Pinning it tightly enough that the price decision is unambiguous takes 2,335 ⟨n_for_se_tenth⟩ months. Products don't live that long. The sample size you needed was never going to arrive. It gets worse across a catalog. Run the short test on all of them and you'll find winners, because some products move the right way for a few weeks on noise alone. On this same catalog, a sweep of 396 ⟨anom_scanned⟩ series raised 106 ⟨anom_detector_flagged⟩ flags from the detectors. Then each detector was run 4,000 ⟨null_replicates⟩ times on data with nothing in it, and the flags were held to a false discovery rate of 5% ⟨anom_fdr_q⟩. 19 ⟨anom_flagged⟩ survived. The rest were the noise floor wearing the costume of a finding. Your price test is one detector with no null run behind it, so every winner it hands you is unchecked, and the more products you test, the smaller the share that are real.  

**[4:00] WHAT TO DO**  
A short list, and it's this week's work. First, stop reading a test as worked or didn't. Write down the range the data allows, and if you can't compute a range, treat the test as a story. Next, make the price move on purpose. Small steps, capped at 5% ⟨pm_step_cap⟩, both directions, over months: the fit needs 5 ⟨el_min_periods⟩ of them and 2% ⟨el_min_price_cv⟩ of movement before it says anything. Then price on the range, not the point. On this demo catalog the range is too wide to mark a best price for 22 ⟨el_no_top⟩ of the 22 ⟨el_skus_fit⟩ products it could fit. Weigh their histories together and the model puts 97% ⟨el_p_optimal⟩ on these prices already being about right, so it recommends no step at all. A model that can tell you to hold is one you can believe when it tells you to move. And notice what earned it: every product it judged had moved its price. About the 2 ⟨el_skus_insufficient⟩ that never did, it says nothing. Last, keep a control. Leave one product's price where it is and watch how far it moves on its own over the same weeks. That's your noise floor, and a winner that didn't beat it wasn't a winner.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is fit one product's curve in a spreadsheet. Log of units against log of price, the slope is the elasticity, and the spreadsheet gives you the standard error. What you can't do by hand is keep it honest across 24 ⟨n_skus⟩ products every month, with errors that don't trust the noise to be tidy, and check each decision against 4,000 ⟨null_replicates⟩ runs of nothing. That part is a model, and a bad model is worse than the few-week test. What you can do today is stop calling a test a win. Ask how wide the answer is. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method, written out in full with the spreadsheet, is free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the month count lands on the first word, then the phrase "pinned tightly enough" |  |
| 0:15 | kinetic: the before-and-after comparison in the viewer's own words (a real screenshot of a price-test dashboard replaces this beat when the founder supplies one) |  |
| 0:45 | elasticity: the points appear month by month, the fitted line, then the band opens to the full range | ELASTICITY.FIT on Tarnhollow demo data |
| 1:15 | elasticity: each point jitters within its own noise, the line tilts through the allowed range, the band is annotated with the standard error | ELASTICITY.FIT on Tarnhollow demo data; the year's spread from cash horizon paths, one-year horizon, Tarnhollow demo data |
| 2:45 | sample_size: the error curve falling with months of history, the three rungs marked and named as they're spoken; then kinetic for the sweep, the detector count shrinking to the survivors | derived from ELASTICITY.FIT standard error, Tarnhollow demo data; ANOMALY.SCAN null calibration on Tarnhollow demo data |
| 4:00 | elasticity: every fitted product's interval side by side, today's price marked inside each band, the tops smearing across the price axis; then kinetic — the word "hold" landing in ink, and the refused products as empty outlines with no band at all | ELASTICITY.FIT and PRICE.OPTIMUM on Tarnhollow demo data |
| 4:45 | kinetic: the closing question |  |

### Your earlier notes

- The engine was corrected on 2026-10-06 (MATH_SCORECARD iteration 41: the already-optimal prior now costs a unit as the margin and the step do). On the demo it recommends no price step at all and puts {{el_p_optimal}} on the prices already being about right; the pm_* figures this script quotes (step, gain, its range, loss odds) no longer exist. Redraft on what the model says now: the range too wide to mark a top for {{el_no_top}} of {{el_skus_fit}} products, the verdict hold, a verdict it can give only for prices that moved. Never speak a step's gain, loss odds or direction confidence. The founder approved the topic; this is a correction, not a rejection of it.

### Decide

```
hubricon-content approve 04-ab-test-sample-size
hubricon-content reject  04-ab-test-sample-size --note "what to change"
```
Edit `content/videos/04-ab-test-sample-size/script.md` first if you prefer; it is re-validated on approve.

## V08 · day 8 · tier A · pillar 3 — script gate

**Title:** Elasticity in plain English, and why "units are holding" is not proof your price is right  
**Thumbnail:** 6.22 ⟨el_ci_width⟩ in ink over the elasticity fragment: the demand line with its band, and the top of the profit hill drawn as a stretch across the price axis, not a point  
**Spiky claim:** Almost nobody can say where the top of their profit hill is, and the honest measurement of it, run on a year of history, usually refuses to name the top at all — which makes every price set on gut a guess with no error bar on it.  
**Misconception:** If units are holding, the price is right. Elasticity is a warning not to raise prices.  
**CTA:** The free course at hubricon.com/learn, where the method is written out in full  
**Estimated runtime:** about 6 min 20 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. -1.82 ⟨el_median⟩. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
2. 22 ⟨el_no_top⟩ of 22 ⟨el_skus_fit⟩. That's how many products on this catalog the model refuses to name a best price for, with a year of price history on each. You'd say your prices are right because units are holding. That isn't the test, and here's the test.
3. 6.22 ⟨el_ci_width⟩. That's the width of the honest answer on one product's demand slope, and the price you want is set from that slope. You'd say you'd have spotted a pricing mistake yourself. You can't, because nobody has measured it.

### Script

**[0:00] HOOK**  
-1.82 ⟨el_median⟩. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.  

**[0:15] LET THEM BE WRONG**  
Here's how most prices get set. Landed cost, times a markup that gives a gross margin you're comfortable with. A look at the competitors. Then a gut check: would I pay that. If units hold after a change, the price was fine. If units drop, it was too high, put it back. It's a fair method, and it isn't stupid, because units are the thing you can see. The thing you can't see is the line the units sit on, and the price you want is on that line, not on the markup.  

**[0:45] THE CRACK**  
Take one product from the demo catalog. TH-OVEMIT-22 ⟨el_sku⟩, from Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. It has 12 ⟨el_periods⟩ months of history where the price moved and the units moved with it. Plot them. Price across, units up. The points slope down: dearer, fewer. Fit a line through them and read the slope as a ratio, how fast units fall for how far the price rises. On this product the ratio is -2.76 ⟨el_point⟩. That's the whole of elasticity. A price rise of a given size costs you units by that multiple of it. It isn't a warning. It's a measurement. And it comes with a range, -5.87 ⟨el_ci_low⟩ to 0.35 ⟨el_ci_high⟩, because 12 ⟨el_periods⟩ months of noisy demand can't pin it tighter than that.  

**[1:15] CHAPTER 1 — THE HILL**  
Now why the number tells you where the price should sit. Raise the price and it pulls both ways. Every unit you still sell earns more. You sell fewer units. Profit is what's left when they pull against each other, so as the price climbs, profit climbs, flattens, then falls. It's a hill. Every product has one. The top of the hill is the price you want, and where it sits depends on the slope and the margin, and nothing else. The slope is the elasticity. The margin is what you keep on the next unit, and it isn't the gross margin: the platform's cut and the ad that sold the unit are charged per unit too. On this catalog the platform keeps 32.1% ⟨fee_share_latest⟩ of revenue. The margin after cost, fees and ads is 32.3% ⟨contribution_pct_latest⟩, against a gross margin of 70.7% ⟨gross_pct_latest⟩. Set the price off the gross number and you've climbed the wrong hill. Here's the rule in words, before any symbol. The faster the units fall, the closer the price should sit to your true cost. The slower, the further above it. And now the symbol, as a convenience: the fraction of the price you keep above true unit cost should equal the inverse of the elasticity. That's all it is.  

**[2:45] CHAPTER 2 — THE TOP IS A STRETCH**  
Here's the part a good operator gets wrong even after the hill. The top isn't a point. The elasticity came with a range, -5.87 ⟨el_ci_low⟩ to 0.35 ⟨el_ci_high⟩, and the rule for the top divides by how far the slope sits from the place where a price rise exactly pays for the units it costs. Near that place the answer runs off to no limit. So a wide range doesn't hand you a blurry top. It hands you a top that might be one step up the hill, or past the edge of the chart. Run it across the catalog. 22 ⟨el_skus_fit⟩ products have a usable fit. 2 ⟨el_skus_insufficient⟩ were refused: the fit won't speak until the price has moved by 2% ⟨el_min_price_cv⟩ across 5 ⟨el_min_periods⟩ months, and nobody ever moved theirs. Of the fitted ones, the range is too wide to name a top for 22 ⟨el_no_top⟩. All of them. So the model does the honest thing. It works the rule at the estimate alone, and calls for a step only if that lands above today's price. On this catalog it calls for no step at all, and weighing the whole history together it puts 97% ⟨el_p_optimal⟩ on these prices already being about right. A measurement that will tell you it can't see the top is one you can trust when it tells you to climb.  

**[4:00] WHAT TO DO**  
This week. First, pick your top products and pull price and units by month, as far back as you have. Then fit the line: log of units against log of price. The slope is the elasticity, and the spreadsheet gives you the standard error beside it. If the price never moved, you have no line, and the first job is to move it, in small steps, both ways, and wait 5 ⟨el_min_periods⟩ months. Then compute your true unit margin, after the platform and the ads, not the gross one, and put the price where the fraction you keep equals the inverse of the slope. If the range is too wide to name a top — and it usually is — work the rule at your estimate alone: above today's price, step up; below it, hold. Last, take the step as a step, not a leap. Cap it at 5% ⟨pm_step_cap⟩, read the result against the range, and go again.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is the line for your top products, and it's worth an afternoon. What you can't do by hand is keep it honest across 24 ⟨n_skus⟩ products every month, with errors that don't assume the noise is tidy, and turn each range into a step the right size for what's unknown in it. That part is a model. What you can do today is stop treating units holding as proof. Measure the slope. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method, written out in full with the spreadsheet, is free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the ratio lands on the first word, then "how fast units fall" over "how far the price rises" |  |
| 0:15 | kinetic: the markup method in the viewer's own words (a real pricing spreadsheet screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | elasticity: the points appear month by month, the fitted line, then the band opens to the full range | ELASTICITY.FIT on Tarnhollow demo data |
| 1:15 | elasticity: the demand line, then the profit hill built underneath it as the price sweeps across, the top marked; a second, lower hill drawn off the gross margin to show the wrong top | ELASTICITY.FIT on Tarnhollow demo data; MARGIN.DECOMP on Tarnhollow demo data |
| 2:45 | elasticity: the band widens and the hill's top smears into a stretch across the price axis; then kinetic: the catalog counts, the word "hold" landing in ink, and the refused products as empty outlines with no band at all | ELASTICITY.FIT on Tarnhollow demo data; PRICE.OPTIMUM on Tarnhollow demo data ({{pm_count}} recommended steps) |
| 4:00 | kinetic: the steps landing one at a time |  |
| 4:45 | kinetic: the closing line |  |

### Your earlier notes

- The engine was corrected on 2026-10-06 (MATH_SCORECARD iteration 41: the already-optimal prior now costs a unit as the margin and the step do). On the demo it recommends no price step at all and puts {{el_p_optimal}} on the prices already being about right; the pm_* figures this script quotes (step, gain, its range, loss odds) no longer exist. Redraft on what the model says now: the range too wide to mark a top for {{el_no_top}} of {{el_skus_fit}} products, the verdict hold, a verdict it can give only for prices that moved. Never speak a step's gain, loss odds or direction confidence. The founder approved the topic; this is a correction, not a rejection of it.

### Decide

```
hubricon-content approve 08-elasticity-plain-english
hubricon-content reject  08-elasticity-plain-english --note "what to change"
```
Edit `content/videos/08-elasticity-plain-english/script.md` first if you prefer; it is re-validated on approve.
