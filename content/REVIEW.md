# Review inbox

Updated 2026-10-05T20:15:04+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

## V01 · Why most business advice is useless: survivorship bias, with numbers — final gate

- Master: `content/videos/01-survivorship-bias/media/master.mp4`
- Thumbnail: `content/videos/01-survivorship-bias/thumbnail.png`
- Description: `content/videos/01-survivorship-bias/description.md`
- Shorts: `content/videos/01-survivorship-bias/shorts/`
- Voice: library · publishable once approved: True
- QA: {"pass": true, "duration_s": 275.3, "lufs": -16.5, "max_hold_s": 0.0, "subtitle_coverage": 1.0}

```
hubricon-content approve-final 01-survivorship-bias
hubricon-content reject-final 01-survivorship-bias --note "what to change"
```

## V04 · Your A/B test told you nothing. Here's the sample size you needed — final gate

- Master: `content/videos/04-ab-test-sample-size/media/master.mp4`
- Thumbnail: `content/videos/04-ab-test-sample-size/thumbnail.png`
- Description: `content/videos/04-ab-test-sample-size/description.md`
- Shorts: `content/videos/04-ab-test-sample-size/shorts/`
- Voice: library · publishable once approved: True
- QA: {"pass": true, "duration_s": 361.7, "lufs": -16.5, "max_hold_s": 0.0, "subtitle_coverage": 1.0}

```
hubricon-content approve-final 04-ab-test-sample-size
hubricon-content reject-final 04-ab-test-sample-size --note "what to change"
```

## V09 · day 9 · tier B · pillar 3 — script gate

**Title:** The price increase you're afraid of is probably free  
**Thumbnail:** 4% ⟨pm_p_loss⟩ in ink beside the elasticity fit fragment, the band wide, the point marked  
**Spiky claim:** A price you have never moved is not a safe price, it is an unmeasured one. Waiting for a tighter elasticity pays a known cost to avoid an unknown one, and the band never gets tight enough to justify the wait.  
**Misconception:** If I raise my price the Buy Box goes, conversion drops and the rank slides, and the ads I buy to get it back cost more than the raise made. The price works. Leave it alone.  
**CTA:** The free course at hubricon.com/learn, where the method and the worksheet are written out in full  
**Estimated runtime:** about 10 min 50 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $388 ⟨pm_delta⟩ a month. That's what a 5.0% ⟨pm_step⟩ raise on one product in this demo catalogue is worth, and the same model says it loses money 4% ⟨pm_p_loss⟩ of the time. You'd call that reckless. The arithmetic says the opposite.
2. -2.20 ⟨el_point⟩. That's the measured demand elasticity of one product in this demo catalogue, read off its own price history. You'd call a product that sensitive untouchable. Raise its price and the units do fall. The profit doesn't.
3. -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩. That's the honest range around one product's elasticity, and the width is the point. You'd wait for a tighter number before touching a price. Waiting costs more than moving.

### Script

**[0:00] HOOK**  
$388 ⟨pm_delta⟩ a month. That's what a 5.0% ⟨pm_step⟩ raise on one product in this demo catalogue is worth, and the same model says it loses money 4% ⟨pm_p_loss⟩ of the time. You'd call that reckless. The arithmetic says the opposite, and you can measure it on price changes you've already made.  

**[0:15] LET THEM BE WRONG**  
Here's the model you're working from, and it isn't a stupid one. Price is the lever you can't quietly pull back. Raise it and the Buy Box goes, conversion drops, the rank slides, and the ads you buy to get the rank back cost more than the raise ever made. So the price that's working stays where it is. You've had that thought standing over the price field with the cursor in it, and then you closed the tab and went to do something safer. Everything in that model is true except the size of it. Demand is sensitive. Rank is real. What's missing is a measurement of how sensitive, taken on your own listing instead of assumed, and set against what the raise is actually worth. Without that, a price is a feeling that has sat still long enough to look like a decision.  

**[0:50] THE CRACK**  
This is the demo catalogue on screen. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year, 12 ⟨n_periods⟩ monthly periods of price and units. Take one product, TH-OVEMIT-22 ⟨el_sku⟩. Plot its units against its price for every period it has, and the slope of that line has a name: elasticity. Here it's -2.20 ⟨el_point⟩. Units move more than price moves, in the opposite direction. That is a sensitive product, and your intuition was right about the direction and about the size. Now hold on to it, because the next step doesn't follow from it. Raise the price on a product like that and you do lose units. You also keep more on every unit that still sells, and a chunk of what the platform charges you is fixed per unit, so it doesn't rise when the price does. Whether the raise wins is a race between those, and the race is settled by your margin, not by how frightened you are. On this catalogue the margin that decides it, after the platform and the ads are paid, is 32.3% ⟨contribution_pct_latest⟩.  

**[1:30] CHAPTER 1 — FIND IT**  
Here's the whole method, with nothing held back. Export a pair of columns per product from your own order reports: the price it actually sold at in each period, and the units it sold. Not the list price. The realised price, after promotions, because that's the price the customer saw. Monthly periods are fine, weekly is better if your volume carries it. Then plot units against price with both axes on a log scale. On a log scale, a response that's proportional comes out as a straight line, and the slope of that line is the elasticity: the proportional change in units for a proportional change in price. Fit the line by least squares. That's the estimate. The notation comes after the picture, and the picture is the whole idea. A handful of things make that estimate lie, and all of them are fixable. First, not enough price movement. If the price never moved, the slope is reading noise and will say so confidently. The fit here refuses to speak unless a product has at least 5 ⟨el_min_periods⟩ periods and at least 2% ⟨el_min_price_cv⟩ of movement in its own price. On this catalogue it refused 2 ⟨el_skus_insufficient⟩ of 24 ⟨n_skus⟩ products on that rule and fitted 22 ⟨el_skus_fit⟩. Second, confounding. A price cut that ran alongside a promotion. A stockout that cut units for a reason that had nothing to do with price. A competitor's move. The season. Drop the stockout periods, flag the promotion periods, and if you have the periods to spare, put the season in as a control. Then the error on the slope itself. Ordinary least squares assumes the spread around the line is even, and demand data never is, because the busy months are noisier than the quiet ones. Use a robust standard error. The one used here is the heteroskedasticity-consistent variant, which sounds worse than it is: it's a single option in every stats package, including the free ones. Do that and each product hands you a slope and an error bar. On this catalogue the middle of the fitted products sits at -1.86 ⟨el_median⟩, and 22 ⟨el_elastic_count⟩ of them come out sensitive enough that units move more than price.  

**[3:40] CHAPTER 2 — VERIFY IT**  
Now the part that decides whether you act on any of it. The slope for TH-OVEMIT-22 ⟨el_sku⟩ is -2.20 ⟨el_point⟩, and its robust error is 0.67 ⟨el_se⟩. Put those together and the honest interval runs from -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩: a width of 2.64 ⟨el_ci_width⟩, on 12 ⟨el_periods⟩ periods. The fit's R-squared is 0.53 ⟨el_r2⟩, which is the share of the movement in units that price explains, leaving the rest to the season, the competitor and the weather. Read what that interval contains. At one end, demand barely notices a raise. At the other, it's savage. Both ends are consistent with the data you have. Anyone handing you a single elasticity for your catalogue, with no band on it, either hasn't done this fit or has done it and thrown the error away. The natural reaction is to wait for a tighter number, so price the wait. The error shrinks with the square root of the periods you have, which makes precision expensive fast. To halve this error you'd need 22 ⟨n_for_se_half⟩ periods. To get it to a narrow band, 87 ⟨n_for_se_quarter⟩. To make it precise, 546 ⟨n_for_se_tenth⟩. That's longer than most catalogues have existed, and your demand curve will have moved underneath you long before you get there. So waiting isn't the safe option. It's the option that pays a known cost to avoid an unknown one. What you do instead is take a step small enough that the whole band is survivable. You never needed the exact elasticity. You needed to know that at every value the interval allows, the move you're making is one you can live with.  

**[5:50] WHAT IT'S WORTH**  
So run every value in that band through the profit arithmetic, not the middle one. Simulate the move across the whole interval, hold the fees and the landed cost where they are, and what comes back is a distribution of outcomes instead of a single answer. Here's the best candidate on this catalogue. TH-CASIRO-01 ⟨pm_sku⟩, raised by 5.0% ⟨pm_step⟩, to $37.84 ⟨pm_new_price⟩. The expected change in monthly profit is $388 ⟨pm_delta⟩. The bad end of the band is $20 ⟨pm_delta_p5⟩. The good end is $909 ⟨pm_delta_p95⟩. The chance the move loses money at all is 4% ⟨pm_p_loss⟩. Look at the bad end again. It's a gain. On this product, across the whole range of elasticities its own data allows, the step doesn't lose. That's what probably free means, and it's a statement about one product with one margin, not a slogan about pricing. Across the catalogue there are 22 ⟨pm_count⟩ products carrying a move like this, worth $1,701 ⟨pm_total_delta⟩ a month between them. And the cap matters as much as the figure: no single step bigger than 5% ⟨pm_step_cap⟩, whatever the model wants. A big step walks off the edge of the price range you have data for, and a model asked to extrapolate past its own data will answer you confidently and be wrong.  

**[7:50] WHAT TO DO**  
This week, in order. First, pull price and units by period for your top products and plot them. Inside an hour you'll know which products have enough price movement to say anything and which have sat at the same price so long they can't. Second, fit the slope on the ones that qualify, with a robust error, and write down the interval rather than the point. Write down only the point and you'll start believing it. Then take the product with the thickest margin and the most room above its current price, and raise it by a step inside the cap. Change nothing else that week. No new ad budget, no coupon, no new creative, or you'll have confounded your own measurement in the first week of running it. Hold it long enough to read: a full period at minimum, longer if your volume is thin. Watch units, not revenue, because revenue moves the moment the price does and tells you nothing about demand. Then re-fit with the new period in. The move you made is the cleanest price variation your data has ever had, so it tightens the estimate more than a year of sitting still would. And record what you expected beside what happened, written down before you look. A prediction you write after the fact isn't one.  

**[9:30] THE HONEST LIMIT**  
What you can do yourself is everything up to here, and it's worth doing. One product, one afternoon, a log plot, a robust error, and a step you capped on purpose. That's a better pricing process than most catalogues this size have ever had. Where it breaks is repetition and scale. 24 ⟨n_skus⟩ products, re-fitted every period, each with its own interval, each candidate move checked against the fees on that product and the cash it ties up, with stockout and promotion periods excluded automatically and the season controlled for, and then the whole thing run again next month, because an elasticity measured a year ago describes a market that no longer exists. Done by hand it drifts into a spreadsheet nobody updates, and a stale elasticity is more dangerous than no elasticity, because you'll act on it. And there's a limit no amount of work removes. The band stays wide. 546 ⟨n_for_se_tenth⟩ periods is what precision would cost, and nobody has that. The answer was never a tighter number. It's a process that sizes every step to survive the band it actually has. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method is written out in full, with the worksheet, free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the monthly figure lands, then the chance of losing money under it |  |
| 0:15 | screenshot: the price field on a listing nobody has touched in months, the cursor sitting in it (a real screenshot replaces this beat when the founder supplies one) |  |
| 0:50 | elasticity: the scatter for the worked product building point by point, then the fitted slope landing through it | ELASTICITY.FIT on Tarnhollow demo data |
| 1:30 | elasticity: the log scatter, the fitted slope, then the band around it widening as periods are taken away | ELASTICITY.FIT on Tarnhollow demo data |
| 3:40 | sample_size: the error bar shrinking as periods accumulate, marked where it halves, where it narrows and where it goes precise | ELASTICITY.FIT on Tarnhollow demo data |
| 5:50 | paths: the distribution of the monthly profit change for the worked product, the bad end and the good end marked, the losing tail lit | PRICE.OPTIMUM on Tarnhollow demo data |
| 7:50 | kinetic: the steps landing one at a time, then chapter_card: expected beside actual, written before the result |  |
| 9:30 | kinetic: the closing line, held |  |

### Decide

```
hubricon-content approve 09-price-increase-probably-free
hubricon-content reject  09-price-increase-probably-free --note "what to change"
```
Edit `content/videos/09-price-increase-probably-free/script.md` first if you prefer; it is re-validated on approve.

## V11 · day 11 · tier A · pillar 3 — script gate

**Title:** Discounting: the math of what you gave away  
**Thumbnail:** 32.3% ⟨contribution_pct_latest⟩ in ink over the waterfall's last bar, the discount taken off the whole width of it  
**Spiky claim:** A promotion is not a trade of margin for volume. It is a bet that your product is more price-sensitive than your own price history says it is, and on this catalogue the bet loses at every value of elasticity except the one you have least reason to believe.  
**Misconception:** The discount costs me the discount. Margin is thick, so there's room, and the volume makes it back.  
**CTA:** The free course at hubricon.com/learn, where the method and the worksheet are written out in full  
**Estimated runtime:** about 5 min 41 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 70.7% ⟨gross_pct_latest⟩ gross margin. That's the number in your head when you price a promotion, and it's why the discount feels affordable. The number it actually comes out of is 32.3% ⟨contribution_pct_latest⟩, and the gap between them is the room you thought you had.
2. 32.3% ⟨contribution_pct_latest⟩. That's what's left on a unit here once the platform, the goods and the ads are paid. Take a discount out of that and the units you need to stand still aren't proportional to the discount. They're worse.
3. -1.86 ⟨el_median⟩. That's the middle demand elasticity on this demo catalogue, measured rather than assumed. It says what a discount buys in units. Set it against what the discount costs in margin and most promotions on this shelf never get their money back.

### Script

**[0:00] HOOK**  
70.7% ⟨gross_pct_latest⟩ gross margin. That's the number in your head when you price a promotion, and it's why the discount feels affordable. The number the discount actually comes out of is 32.3% ⟨contribution_pct_latest⟩, and what it does to the units you need is not proportional to the discount.  

**[0:15] LET THEM BE WRONG**  
Here's how the decision gets made, and it's a reasonable way to make it. A promotion is a trade. Give up some margin, get more units, and if the volume comes you're ahead. The margin looks thick, so there's room in it. And underneath that sits a rule of thumb nearly everyone carries: the discount costs you the discount. Take a step off the price and you give up that much of what you were making, then make it back on volume. Hold on to that, because both parts of it are wrong, and they're wrong in the same direction.  

**[0:45] THE CRACK**  
This is the demo catalogue. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. Gross margin is 70.7% ⟨gross_pct_latest⟩. After the platform's fees, the landed cost of the goods and the ads those products spend, what's left is 32.3% ⟨contribution_pct_latest⟩. A gap of 38.4% ⟨gross_vs_contribution_gap⟩. The discount doesn't come out of the first number. It comes out of the second, and it comes out whole — a step off the price is the same step off what you keep, not a slice of it.  

**[1:15] CHAPTER 1 — INTUITION**  
Picture what you keep on a unit as a glass, and the glass is nowhere near full. The discount doesn't take a share of the glass. It takes a fixed depth off the top. So the share of your profit it removes is the discount measured against what was in the glass, which is already far more than the discount measured against the price. That's the first part. Here's the second. To stand still you need enough extra units to refill the profit you poured out, and every new unit now carries less than the old ones did. So the lift you need is what you kept before, divided by what you keep after the discount. That's the whole line. Write it on a sticky note. And look at its shape, because the shape is the point: the lift it demands doesn't rise in step with the discount, it accelerates, and it goes vertical as the discount approaches the margin itself. Now that you've watched it bend, it has a name. Break-even volume lift.  

**[2:45] CHAPTER 2 — THE TURN**  
Here's the part a careful operator still gets wrong. You'd test that lift against what you believe demand will do. Measure it instead. The fit here reads 22 ⟨el_skus_fit⟩ products off their own price histories, and the middle of them sits at -1.86 ⟨el_median⟩. Take the worked product, TH-OVEMIT-22 ⟨el_sku⟩, at -2.20 ⟨el_point⟩, with an honest interval running from -3.52 ⟨el_ci_low⟩ to -0.88 ⟨el_ci_high⟩. Now take a cut the size of the cap this model puts on any price step, 5% ⟨pm_step_cap⟩, and set them side by side: the lift the arithmetic demands, and the lift the measured elasticity actually delivers. On this catalogue the demand falls short at the middle of the band, and short again at the point estimate. Only at the far elastic end of the interval does the cut get its money back, and the far end is the value you have the least evidence for. So a promotion isn't a trade of margin for volume. It's a bet that your product is more price-sensitive than your own data says it is, placed with the margin you already measured.  

**[4:00] WHAT TO DO**  
Before the next promotion, in order. Work out what you actually keep per unit on the product being discounted, after fees, landed cost and the ads that product spends. Not gross. Then take the lift: what you kept, divided by what you'd keep after the discount. Write that down before you run anything. Then look up what the product's own price history says it does when the price moves, and if you've never moved the price, say so out loud, because then the lift is a hope rather than a forecast. And when the promotion ends, measure units against the lift you wrote down. Not revenue against last month. Revenue always rises during a discount. That's the discount, not demand.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is this arithmetic, on the product you were about to discount, in about the time it takes to find the fee line in the settlement report. Do it once and promotions stop being automatic. What you can't do by hand is the other side of the question: whether the cut takes its units from the product sitting next to it, what it does to the rank you'll be bidding to recover afterwards, whether the units you pulled forward were coming anyway, and all of that re-asked across 24 ⟨n_skus⟩ products every month while the fees and the landed costs move underneath. That part is a model. The arithmetic still changes the decision today, which is why it's the part I'd rather you had. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method is written out in full, with the worksheet, free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the gross figure lands, the contribution figure lands under it, the gap between them opens |  |
| 0:15 | screenshot: a promotion being set up in the seller's own console, the discount field filled in (a real screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | waterfall: revenue down to contribution, then the discount taken off the last bar, the bar shrinking by the full width of the step | MARGIN.DECOMP on Tarnhollow demo data |
| 1:15 | formula: the glass draining by a fixed depth, then the line — lift needed = what you kept, divided by what you keep after the discount — then the curve drawn as the discount deepens and runs away |  |
| 2:45 | elasticity: the fitted band for the worked product, with the lift the arithmetic demands drawn across it as a line the band has to clear | ELASTICITY.FIT on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time, then chapter_card: the lift written down before the promotion runs |  |
| 4:45 | kinetic: the closing line, held |  |

### Decide

```
hubricon-content approve 11-discounting-math
hubricon-content reject  11-discounting-math --note "what to change"
```
Edit `content/videos/11-discounting-math/script.md` first if you prefer; it is re-validated on approve.

## V15 · day 15 · tier A · pillar 2 — script gate

**Title:** You don't have a revenue problem. You have a cash trough  
**Thumbnail:** $95,201 ⟨min_median⟩ in ink at the bottom of the cash cone, the ending balance faint above it  
**Spiky claim:** The ending balance is the least useful number on your cash forecast. A business is killed by the lowest point on the path, and growth makes that point deeper while making every number you watch look better.  
**Misconception:** Revenue is up, the month closed profitable and the balance is healthy, so cash is fine. If it gets tight I'll see it coming in the bank account.  
**CTA:** The free course at hubricon.com/learn, where the method and the worksheet are written out in full  
**Estimated runtime:** about 5 min 52 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $337,154 ⟨terminal_p50⟩. That's where the cash on this demo catalogue lands after 90 days ⟨horizon_days⟩, up from $262,000 ⟨cash_on_hand⟩. On the way there it passes through $95,201 ⟨min_median⟩. Nothing on the profit and loss shows you that, and it's the number that ends businesses.
2. 13 days ⟨min_p5_day⟩. That's how far into the horizon this catalogue reaches its lowest cash, at $95,201 ⟨min_median⟩, inside a stretch that closes profitable. The balance you watch is the one at the end. The one that can kill you is the bottom.
3. $345,501 ⟨wires_total⟩ leaves this catalogue in supplier wires over 90 days ⟨horizon_days⟩, across 35 ⟨wire_count⟩ of them, while the platform pays on a 14 days ⟨payout_cycle⟩ lag. That gap has a shape. The shape has a bottom, and you can find it before you reach it.

### Script

**[0:00] HOOK**  
$337,154 ⟨terminal_p50⟩. That's where the cash on this demo catalogue lands after 90 days ⟨horizon_days⟩, up from $262,000 ⟨cash_on_hand⟩. On the way there it passes through $95,201 ⟨min_median⟩. Nothing on the profit and loss shows you that, and the low point is the number that ends businesses.  

**[0:15] LET THEM BE WRONG**  
Here's the model, and almost every operator at this size runs it. Revenue is growing. The month closed profitable. The balance in the account looks like a balance you can work with. So cash is fine, and if it ever gets tight you'll see it coming, because you look at the account most mornings. That model has one assumption buried in it, and the assumption is that cash moves smoothly between the points where you check it. It doesn't. It moves in steps, on dates somebody else chose, and the steps out are earlier than the steps in.  

**[0:45] THE CRACK**  
This is the demo catalogue. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products. It starts with $262,000 ⟨cash_on_hand⟩ and carries $31,500 ⟨monthly_fixed_costs⟩ of fixed costs a month. Over 90 days ⟨horizon_days⟩ it ends at $337,154 ⟨terminal_p50⟩, so it grew, and every monthly statement in that window is healthy. Now the part the statements can't show. The lowest the balance gets on the way is $95,201 ⟨min_median⟩, and it gets there on 13 days ⟨min_p5_day⟩. That bottom is not a bad month. It sits inside the good ones.  

**[1:15] CHAPTER 1 — INTUITION**  
Why there's a bottom at all. You pay for goods when the supplier says so, and you get paid when the platform says so, and those are different calendars. Here the platform settles on a 14 days ⟨payout_cycle⟩ lag. So every unit you sell is money you've already spent and haven't yet received. Now add the lumps. Over this horizon there are 35 ⟨wire_count⟩ supplier wires, $345,501 ⟨wires_total⟩ in total, and they don't arrive evenly — the largest is $23,482 ⟨largest_wire⟩, for TH-ENADUT-03 ⟨largest_wire_sku⟩, leaving on 0 days ⟨largest_wire_day⟩. Stack those against a settlement that's always running behind, and the balance doesn't glide. It falls in steps, refills slowly, and finds a bottom somewhere nobody chose. Growth makes it deeper, not shallower, because growth means ordering more inventory earlier, which pulls the wires forward and pushes the receipts back. That's the thing you're looking for, and now it has a name. The cash trough.  

**[2:45] CHAPTER 2 — THE TURN**  
Here's where a careful operator still gets it wrong. He builds the forecast as one line. One line gives you one trough, and that trough is a guess wearing a decimal point. Demand isn't a line; it's a range, and the products move together, which makes the range wider than it looks. The correlation across these products is 0.48 ⟨demand_corr⟩, so a soft month is soft nearly everywhere at once. So run it many times instead. 10,000 ⟨n_paths⟩ paths, each with its own demand draw, the same wire calendar underneath. Then read the bottom of each path, not the end of it. On this catalogue the trough at the bad end is $95,201 ⟨trough_p5⟩, and the average of the worst paths is $95,201 ⟨trough_es⟩. Look at how close those sit to the middle one, $95,201 ⟨trough_median⟩. That tells you something specific: this trough isn't being driven by demand at all. It's the wire calendar, and a wire calendar is something you can negotiate. The share of paths that ran out of money is 0.0% ⟨p_ruin⟩, with a simulation error of 0.00% ⟨p_ruin_se⟩. Which doesn't mean it can't happen. It means no path in 10,000 ⟨n_paths⟩ did, and the honest reading of that is a bound, not a promise.  

**[4:00] WHAT TO DO**  
Build it this week, in a spreadsheet. First, a dated list of money out: every supplier wire with the date it actually leaves, plus rent, payroll and the rest of the fixed costs. Second, money in, lagged by your platform's settlement cycle, not booked on the day of the sale. Then vary the demand. Even a crude version works: run the sales line at your good case, your normal case and a bad one, and keep the wire dates fixed, because the wires don't care what demand did. Then read the minimum of each line, not the ending balance. The lowest of those minimums is your planning number. Set your floor above it, and when it's too close, move a wire before you move a price. A supplier who takes payment a fortnight later changes the bottom of the curve more than a promotion ever will.  

**[4:45] THE HONEST LIMIT**  
What you can do yourself is the dated calendar and a handful of demand cases, and it's the highest-value afternoon on this list, because it's the one that tells you whether you can take the next purchase order at all. What you can't do by hand is the width of it. Demand that moves together across 24 ⟨n_skus⟩ products, supplier lead times that slip by a week and move a wire with them, the correlation between a soft month and a late container, and the whole thing re-run every week as orders land. A handful of cases gives you a shape. It doesn't give you the bad end, and the bad end is the one you're planning against. That part is a model. The calendar is still worth building tomorrow, because most of the fix is in the dates. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method is written out in full, with the worksheet, free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the ending balance lands, then the low point lands beneath it, the distance between them held |  |
| 0:15 | screenshot: the bank balance on a phone, checked in the morning (a real screenshot replaces this beat when the founder supplies one) |  |
| 0:45 | cash_cone: the balance over the horizon, the ending point marked, then the low point marked far beneath it | cash horizon on Tarnhollow demo data |
| 1:15 | cash_cone: the wires drawn as steps down, the settlements as slower steps up, the trough forming between them | cash horizon on Tarnhollow demo data |
| 2:45 | paths: the simulated balances drawn faintly, the band around them, the trough percentiles lit at the bottom | cash horizon paths on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time, then chapter_card: the minimum of each line circled, the ending balances crossed out |  |
| 4:45 | kinetic: the closing line, held |  |

### Decide

```
hubricon-content approve 15-cash-trough
hubricon-content reject  15-cash-trough --note "what to change"
```
Edit `content/videos/15-cash-trough/script.md` first if you prefer; it is re-validated on approve.

## V16 · day 16 · tier B · pillar 2 — script gate

**Title:** The $23,482 ⟨largest_wire⟩ wire you're guessing on  
**Thumbnail:** 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩ in ink across the newsvendor curve fragment, the flat default marked as a single line through it  
**Spiky claim:** A flat service level is a decision about your money that you never made. Every product has its own right answer, it is set by that product's own costs, and on this catalogue the answers run far enough apart that the flat number is wrong for almost all of them.  
**Misconception:** I order to a cover number and keep a safety margin on top. More cover is safer, and the number I use works well enough across the catalogue.  
**CTA:** The free course at hubricon.com/learn, where the method and the worksheet are written out in full  
**Estimated runtime:** about 10 min 08 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $23,482 ⟨largest_wire⟩. That's the biggest single supplier wire leaving this demo catalogue, and the quantity inside it was set by a cover rule. You'd call that prudent. The product's own economics disagree, and they can be read off a settlement report.
2. 98% ⟨stockout_worst_p⟩. That's the chance one product here runs out before its next delivery lands: 22 days ⟨stockout_worst_cover⟩ of cover against a 50 days ⟨stockout_worst_lead⟩ lead time. The cover rule that produced it looked reasonable on the day it was applied.
3. 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩. That's the range of service levels this catalogue's own margins justify, product by product. Most operators run a single flat number across everything, and 8 ⟨nv_skus_below_95⟩ products here are overstocked because of it.

### Script

**[0:00] HOOK**  
$23,482 ⟨largest_wire⟩. That's the biggest single supplier wire leaving this demo catalogue, and the quantity inside it was set by a cover rule and a feeling. You'd call that prudent rather than reckless. The product's own economics disagree, and you can read them off reports you already have.  

**[0:15] LET THEM BE WRONG**  
Here's how the purchase order actually gets decided, and it's not a careless process. You look at what the product sold last month, you pick a cover number — a month, a season, whatever the lead time and the cash allow — you add a margin on top for safety, and you round it to a carton quantity. It's the same rule across the catalogue because a rule you apply differently everywhere isn't a rule, it's a mood. And the margin on top feels conservative: more cover is safer, and the worst thing that happens is money sits on a shelf a little longer. That model has one thing missing, and it isn't the forecast. It's that the cost of being short and the cost of being long are different on every product, and a single rule applied across all of them quietly assumes they're the same.  

**[0:50] THE CRACK**  
This is the demo catalogue. Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨inv_skus⟩ products. Take the product most likely to run out: TH-STAMIX-12 ⟨stockout_worst_sku⟩. It has 22 days ⟨stockout_worst_cover⟩ of cover on hand and a supplier lead time of 50 days ⟨stockout_worst_lead⟩. So the chance it runs out before the next delivery lands is 98% ⟨stockout_worst_p⟩. Not a risk — close to a certainty, and it's been sitting on the shelf in plain sight. Across the catalogue, 6 ⟨n_skus_stockout_gt_20⟩ products carry a meaningful chance of going out inside their own lead times. Now the other direction. The same rule orders too much elsewhere: the inventory fees on stock held past what its own economics justify run $3,874 ⟨nv_bleed_month⟩ a month. One rule, producing a near-certain stockout at one end of the shelf and a standing fee at the other, at the same time.  

**[1:30] CHAPTER 1 — FIND IT**  
Here's the method, whole. The quantity on a purchase order is a bet, and the useful question is about the last unit in it. Order that unit and one thing happens: either you sell it, or you hold it. So work out both costs for that product. What does being short by one unit cost you? The margin you don't earn on the sale, plus whatever the stockout does to your rank and to the ad spend you'll need afterwards to recover it. On the worked product here, TH-CHEKNI-08 ⟨nv_sku⟩, the unit margin is $28.45 ⟨nv_unit_margin⟩ on a landed cost of $16.60 ⟨nv_unit_cost⟩, and the cost of being one unit short comes out at $29.34 ⟨nv_cu⟩. Now the other side. What does holding one unit too many cost you over a cycle? Storage, the capital tied up, the risk it ages into a higher fee band or gets marked down. On the same product that's $0.74 ⟨nv_co⟩. Look at the size of those against each other, because that's the whole decision. Being short costs many times what being long costs, so you should be willing to carry quite a lot of extra stock to avoid it. How much is set by the ratio: the cost of being short, divided by the cost of being short plus the cost of being long. That fraction is the chance you want to be able to cover. On TH-CHEKNI-08 ⟨nv_sku⟩ it comes out at 98% ⟨nv_fractile⟩. Now it has a name, and you derived it before you heard it: the critical fractile. Then turn it into units. Take your demand over the lead time, take its spread, and set the reorder point at the level that covers demand that share of the time. On TH-STAMIX-12 ⟨stockout_worst_sku⟩ at the flat default, that point is 884 ⟨stockout_worst_rop⟩ units, and the cover it has now is nowhere near it. That's the whole calculation: a pair of costs, one ratio, one reorder point per product.  

**[3:40] CHAPTER 2 — VERIFY IT**  
Now run it across the shelf and look at the spread. On this catalogue the margin-justified service level runs from 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩, with the middle at 97% ⟨nv_fractile_median⟩. Compare that with the flat default most tools and most spreadsheets assume, 95% ⟨service_level_default⟩. The products above it are being starved. The products below it are being overfed: 8 ⟨nv_skus_below_95⟩ of them here have economics that justify less cover than the flat rule gives them, and the difference is money sitting in a warehouse paying rent. Take TH-STAMIX-12 ⟨nv_low_sku⟩, the product with the lowest justified level, 92% ⟨nv_low_fractile⟩. Being short costs $14.58 ⟨nv_low_cu⟩ a unit there, and being long costs $1.22 ⟨nv_low_co⟩. Those are closer together than on the first product, so the bet changes, and the right answer is to carry less. Same catalogue, same supplier, same rule applied to both, and the rule is wrong in opposite directions on the same shelf. One more check, and this is the one people skip. Products don't fail independently. A soft season is soft across most of the shelf at once, and a late container is late for everything on it. Simulate them together and this catalogue expects 5.6 ⟨panel_expected_stockouts⟩ products out of stock inside the same lead time, and at the bad end, 9 ⟨panel_p95_correlated⟩. Treat them as independent and that bad end reads 8 ⟨panel_p95_independent⟩. The gap is small here and it is always in the same direction: assuming independence makes the shelf look safer than it is, and the error grows with how much your products move together.  

**[5:50] WHAT IT'S WORTH**  
Put a figure on it. On the overfed side, the fees on stock held past what its own economics justify are $3,874 ⟨nv_bleed_month⟩ a month on this catalogue, and the number of products whose cover should be cut rather than raised is 8 ⟨nv_skus_below_95⟩. That's recurring, and nobody sends you an invoice for it that says what it is. On the starved side, 6 ⟨n_skus_stockout_gt_20⟩ products are carrying a real chance of running out inside their lead times, with TH-STAMIX-12 ⟨stockout_worst_sku⟩ close to certain. A stockout doesn't cost you the sale, it costs you the sale plus the rank plus the advertising to buy the rank back, which is why the cost of being short came out so much larger than the cost of being long. And the wire itself. Across the horizon this catalogue sends 35 ⟨wire_count⟩ supplier wires totalling $345,501 ⟨wires_total⟩, the largest being $23,482 ⟨largest_wire⟩ for TH-ENADUT-03 ⟨largest_wire_sku⟩. Every one of those is a dated outflow, and ordering deeper than the economics justify doesn't only cost the fees, it moves the bottom of your cash curve. The engine's own count of orders worth placing on this catalogue right now is 13 ⟨nv_econ_orders⟩, against a shelf of 24 ⟨inv_skus⟩.  

**[7:50] WHAT TO DO**  
This week, on your top products, in order. First, write down the landed cost and the unit margin for each one. You need both, and the margin has to be after the platform's fees, not gross. Second, write the cost of being short beside it: the margin forgone, plus your own estimate of the rank and the advertising it takes to recover. Put a real figure there even if it's rough, because leaving it out is the same as calling it nothing. Then the cost of being long: storage for a cycle, the capital at your cost of money, and a markdown allowance for anything seasonal. Then take the ratio and get each product's own service level. You'll find it isn't flat, and the ones that surprise you are the ones worth a second look. Then convert it: demand over the lead time, its spread, and the reorder point that covers it that often. Order to that, not to a cover rule. Last, before you send the wire, put it on the dated cash calendar and check what it does to the low point, because a correctly sized order on a date that breaks your trough is still the wrong order. If they disagree, move the date before you cut the quantity, and talk to the supplier about terms before you do either.  

**[9:30] THE HONEST LIMIT**  
What you can do yourself is the arithmetic on your top products, in an afternoon, and it will change the next purchase order you send. A pair of costs, a ratio, a reorder point. That's a better inventory policy than a flat cover rule and most catalogues this size have never had one. Where it breaks is everything that moves. Lead times that slip, which change the reorder point on every product they touch. Demand that moves across the shelf together rather than product by product, which is what made the simultaneous stockout count worse than the independent one. Fees that change band when a weight or a dimension changes. And the whole thing needing to be re-run every time an order lands, across 24 ⟨inv_skus⟩ products rather than the handful you did by hand, with 20,000 ⟨inv_sims⟩ draws behind each one so the bad end is a measurement rather than a guess. Done by hand it becomes a spreadsheet that was right once. That part is a model. The afternoon still changes the next wire, and the next wire is the biggest discretionary decision you'll make this month. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method is written out in full, with the worksheet, free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the wire figure lands, then the cover rule beneath it, then the product's own answer replacing the rule |  |
| 0:15 | screenshot: the purchase order being built in a spreadsheet, the cover column filled with the same number down every row (a real screenshot replaces this beat when the founder supplies one) |  |
| 0:50 | newsvendor: the catalogue's products plotted by cover against lead time, the near-certain stockout lit at one end, the overstocked tail at the other | INVENTORY.PANEL and NEWSVENDOR on Tarnhollow demo data |
| 1:30 | newsvendor: the cost of being short and the cost of being long as two bars, then the ratio between them becoming the fractile, then the demand distribution with the reorder point drawn on it | NEWSVENDOR on Tarnhollow demo data |
| 3:40 | newsvendor: every product's justified level plotted against the flat default, the starved and the overfed lit in turn; then paths: simultaneous stockouts, correlated against independent | NEWSVENDOR on Tarnhollow demo data; INVENTORY.PANEL on Tarnhollow demo data |
| 5:50 | waterfall: the monthly fee bleed, then cash_cone: the wires as dated steps with the largest marked | NEWSVENDOR on Tarnhollow demo data; cash horizon on Tarnhollow demo data |
| 7:50 | kinetic: the steps landing one at a time; then chapter_card: the service level per product replacing the single flat number |  |
| 9:30 | kinetic: the closing line, held |  |

### Decide

```
hubricon-content approve 16-the-wire-you-guess-on
hubricon-content reject  16-the-wire-you-guess-on --note "what to change"
```
Edit `content/videos/16-the-wire-you-guess-on/script.md` first if you prefer; it is re-validated on approve.

## V17 · day 17 · tier B · pillar 2 — script gate

**Title:** Why 95% ⟨service_level_default⟩ service level is wrong for most of your SKUs  
**Thumbnail:** 95% ⟨service_level_default⟩ in ink as a single flat line across the newsvendor curve fragment, every product's own level scattered above and below it  
**Spiky claim:** The default service level is a convention, not a calculation, and it is wrong in both directions at once on the same shelf. Worse, it promises something other than what you think it promises, and it makes a per-product promise about a risk that arrives catalogue-wide.  
**Misconception:** I run a high service level across the catalogue, so I'm covered almost all of the time and the occasional stockout is bad luck rather than a setting.  
**CTA:** The free course at hubricon.com/learn, where the method and the worksheet are written out in full  
**Estimated runtime:** about 9 min 14 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 95% ⟨service_level_default⟩. That's the service level nearly every inventory tool defaults to and nearly every spreadsheet copies. On this demo catalogue the level each product's own margins justify runs from 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩. The default is right for almost none of them.
2. 8 ⟨nv_skus_below_95⟩. That's how many products on this demo catalogue carry more stock than their own economics justify, because of a figure somebody typed once as a default. The fees on stock held past that point run $3,874 ⟨nv_bleed_month⟩ a month.
3. 9 ⟨panel_p95_correlated⟩. That's how many products here can be out of stock at once at the bad end, against 8 ⟨panel_p95_independent⟩ if they failed separately. Your service level is a promise made product by product. The risk doesn't arrive that way.

### Script

**[0:00] HOOK**  
95% ⟨service_level_default⟩. That's the service level nearly every inventory tool defaults to, and nearly every spreadsheet copies from the tool. On this demo catalogue the level each product's own margins justify runs from 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩, and the default is right for almost none of them.  

**[0:15] LET THEM BE WRONG**  
Here's the model, and it's the one the software hands you. There's a setting called service level. You set it high, because being out of stock is the worst thing that happens to a listing, and high means covered. Maybe you nudged it up once after a bad month. From then on it's the same number across the shelf, it's a high number, and it quietly means you're fine. Nothing about that is lazy. The setting exists, it has a sensible default, and changing it per product sounds like the kind of fiddling that makes a system worse. The trouble is in what the setting actually promises, and in the fact that the default was never a statement about your products at all.  

**[0:50] THE CRACK**  
Start with what the number promises, because it isn't what it sounds like. A service level set this way is the chance of getting through one replenishment cycle without running out. It is not the share of demand you fill. Those are different measures, and the gap between them is widest exactly where it hurts: when you do run out, you run out at the end of the cycle, in the busiest stretch, having already sold through the easy part. So a high cycle number can sit alongside a meaningful share of demand that went unfilled, and the setting will still read as healthy. Now the second part. That default is a convention from a textbook, not a calculation about your catalogue. On this demo catalogue, Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨inv_skus⟩ products, the level each product's own margins justify has a middle of 97% ⟨nv_fractile_median⟩ and runs from 92% ⟨nv_fractile_min⟩ to 98% ⟨nv_fractile_max⟩. A single flat setting lands above some of those and below others, which means the same number is overfeeding one end of your shelf and starving the other, at the same time, for the same reason.  

**[1:30] CHAPTER 1 — FIND IT**  
So where does a product's own number come from? From the only comparison that matters: what being short costs you against what being long costs you. Being short costs the margin you don't earn, plus the rank you lose and the advertising you'll buy to get it back. Being long costs storage for a cycle, the capital tied up, and the markdown risk if it ages. Take the cost of being short, divide it by the cost of being short plus the cost of being long, and that fraction is the share of the time you should be able to cover. That's the whole derivation, and the episode on sizing a purchase order works it through on a named product, free, on the same page as this one. What matters here is what it does to the default. Run it across this catalogue and 8 ⟨nv_skus_below_95⟩ products come out below the flat setting — their stockouts are cheap relative to the cost of holding them, so the honest answer is to carry less and take the occasional miss. Others come out above it, and on those the setting has been quietly rationing a product whose stockouts are expensive. Now find your own version. You need, per product: the landed cost, the margin after the platform's fees, the storage cost for a cycle, and an honest figure for what a stockout does to rank and to the ads you'd buy afterwards. That last one is the number everyone leaves blank, and leaving it blank is not neutral. It is the same as entering nothing, which makes every product look like its stockouts are free, which is exactly the assumption that produces a flat setting in the first place.  

**[3:40] CHAPTER 2 — VERIFY IT**  
Here's the part the setting cannot express, whatever you set it to. A service level is a promise made one product at a time. Your actual risk doesn't arrive one product at a time. A soft season is soft across most of the shelf at once; a late container is late for everything inside it; a supplier who slips slips for every product you buy from them. The demand correlation across this catalogue is 0.48 ⟨demand_corr⟩, which is a long way from products moving independently. So simulate the shelf together rather than product by product. Do that here, with 20,000 ⟨inv_sims⟩ draws per product, and the catalogue expects 5.6 ⟨panel_expected_stockouts⟩ products out of stock inside the same lead time, with a bad end of 9 ⟨panel_p95_correlated⟩. Now run the same shelf pretending the products are independent, and that bad end reads 8 ⟨panel_p95_independent⟩ instead. The direction of that error is the point. Assuming independence always makes the shelf look safer than it is, and the gap widens as your products move together. Which means a per-product setting, however carefully chosen, is answering a question you didn't ask. You don't care how often one product is out. You care how often enough of them are out at once that the month breaks, and that's a catalogue-level number that no per-product field can hold.  

**[5:50] WHAT IT'S WORTH**  
Put figures on both directions. Overfed first, because it's the invisible one. The fees on stock held past what its own economics justify run $3,874 ⟨nv_bleed_month⟩ a month on this catalogue, and 8 ⟨nv_skus_below_95⟩ products are sitting on cover their own margins don't support. That's a recurring cost with no invoice attached, and it's also cash: every unit of it was paid for by a wire that left before the sale arrived. Starved next. 6 ⟨n_skus_stockout_gt_20⟩ products here carry a real chance of running out inside their own lead times, and TH-STAMIX-12 ⟨stockout_worst_sku⟩ is close to certain at 98% ⟨stockout_worst_p⟩, on 22 days ⟨stockout_worst_cover⟩ of cover against a 50 days ⟨stockout_worst_lead⟩ lead time. A flat high setting did not prevent that, which is the clearest evidence available that the setting is not the safeguard it feels like. And the number of orders the economics actually justify placing right now on this shelf is 13 ⟨nv_econ_orders⟩, out of 24 ⟨inv_skus⟩ products — the answer is neither "order everything" nor "order nothing", and a flat rule can't produce a list like that.  

**[7:50] WHAT TO DO**  
This week. First, find the service level setting in whatever tool you use and write down what it's set to, because a surprising number of operators have never looked. Second, write the cost of a stockout for your top products, including the rank and the advertising to recover it. Rough is fine; blank is not. Then take the ratio for each of those products and compare it with the setting. Where the product's own answer is below the setting, you've been paying to hold stock that doesn't earn it, and the fix is to cut cover and accept the occasional miss. Where it's above, raise it, and expect the wire to be bigger. Then the catalogue check: list the products that share a supplier, a container or a season, and ask what happens if that group is late together, because that's your real exposure and no per-product setting will show it to you. Last, write down what you expect the change to do before you make it. Cover days, stockouts, the fee line. Then read it next month against what you wrote, not against how it felt.  

**[9:30] THE HONEST LIMIT**  
What you can do yourself is the comparison, on your top products, in an afternoon. Find the setting, cost both sides, take the ratio, and change the ones that are clearly wrong. That alone will beat a flat default, and it costs you nothing but the afternoon. What you can't do by hand is the catalogue-level answer. That needs every product's demand simulated together with its correlations intact, lead times that slip, suppliers that slip as a group, and the whole thing re-run as orders land and seasons turn — 20,000 ⟨inv_sims⟩ draws per product across 24 ⟨inv_skus⟩ products is not a spreadsheet exercise, and the number you most want, how often enough products are out at once to break a month, is precisely the one that needs it. That part is a model. The afternoon is still worth more than the setting you have now. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The method is written out in full, with the worksheet, free at hubricon.com/learn.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the default lands as a flat line, then each product's own level scatters above and below it |  |
| 0:15 | screenshot: the service level field in an inventory tool, set once and left (a real screenshot replaces this beat when the founder supplies one) |  |
| 0:50 | newsvendor: the justified level for every product plotted against the flat default, the ones above and the ones below lit in turn | NEWSVENDOR on Tarnhollow demo data |
| 1:30 | newsvendor: the cost of being short and the cost of being long, the ratio between them resolving into a level, then the catalogue's levels landing around the flat default | NEWSVENDOR on Tarnhollow demo data |
| 3:40 | paths: simultaneous stockouts across the catalogue, correlated against independent, the bad end of each marked | INVENTORY.PANEL on Tarnhollow demo data |
| 5:50 | waterfall: the monthly fee bleed on the overfed side; then newsvendor: the starved products lit with their cover against their lead times | NEWSVENDOR on Tarnhollow demo data; INVENTORY.PANEL on Tarnhollow demo data |
| 7:50 | kinetic: the steps landing one at a time; then chapter_card: the single setting crossed out, a column of per-product levels beside it |  |
| 9:30 | kinetic: the closing line, held |  |

### Decide

```
hubricon-content approve 17-service-level-is-wrong
hubricon-content reject  17-service-level-is-wrong --note "what to change"
```
Edit `content/videos/17-service-level-is-wrong/script.md` first if you prefer; it is re-validated on approve.

## G01 · series · tier D · pillar 1 — script gate

**Title:** What One More Ounce Cost in 1913 ⟨s_pp_year⟩, and the Fee Staircase You Still Pay  
**Thumbnail:** 15 cents ⟨s_11_local⟩ set over the parcel post rate card's first step, beside a fragment of today's fee staircase with one riser in blue  
**Spiky claim:** The parcel post years taught a nation of catalogue customers what an ounce cost. The card is still there; what's gone is the moment you see it.  
**Misconception:** Shipping and fulfilment fees are a fixed cost of selling online. A few cents a unit isn't worth anyone's attention.  
**CTA:** The free Fee Staircase course at hubricon.com/learn, then the one soft close.  
**Estimated runtime:** about 31 min 43 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. 15 cents ⟨s_beagle_postage⟩. That's what it cost to mail a baby in early 1913 ⟨s_beagle_when⟩, on a card that charged by the pound and by the mile. That card fed the machine that built Sears. Its descendants are charging you now.
2. In its first year, more than 600 million ⟨s_parcels_year⟩ parcels went through the mail, and Congress found the mail-order houses sent more of them than everyone else combined. The arithmetic on that card never went away. You pay it on every unit.
3. $0.26 a unit ⟨cs_step⟩, by our estimate. That's what being a fraction of an ounce over one line costs a listing we modelled from public data. In 1913 ⟨s_pp_year⟩, farmers paid the same kind of step. The difference is they could see it.

### Script

**[0:00] COLD OPEN**  
15 cents ⟨s_beagle_postage⟩. That's what it cost, in early 1913 ⟨s_beagle_when⟩, to mail a baby. His name was James Beagle, and he was mailed to his grandmother, a few miles away near Batavia, Ohio. A rural carrier named Vernon Lytle carried him, insured for $50 ⟨s_beagle_insured⟩. It was against postal regulations even then. It happened anyway, because the country had a new way to send a parcel, and the price of a parcel came off a card. A card that charged by the pound, and by the mile.  

**[0:34] THE QUESTION**  
That card fed a machine in Chicago that was assembling 45,000 ⟨s_orders_day⟩ orders a day. A historian of the rural mail wrote in 1964 ⟨s_fuller_year⟩ that the decline of the old general store began the day parcel post went into effect. And the card has descendants. If you sell online, you pay one of them right now, on every unit. So here's the question Sears' customers answered with a pencil: what does one more ounce cost? Make a guess before we go on. Most of us would say one more ounce costs one more ounce's worth: a sliver, too small to bother with. Hold on to that guess.  

**[1:17] CHAPTER — WHAT A POUND COST**  
What a pound cost.  

**[1:21] THE WORLD BEFORE**  
Before 1913 ⟨s_pp_year⟩, the United States mail would carry a package of up to 4 pounds ⟨s_old_limit⟩. It charged 16 cents a pound ⟨s_old_per_lb⟩. That works out at $320 a ton ⟨s_mail_ton⟩. Rail freight moved the same ton for $1.90 a ton ⟨s_freight_ton⟩. The private express companies charged about $28 a ton ⟨s_express_ton⟩. So a farm family in Kansas that wanted a stove, a plough blade, a bolt of cloth, had bad choices, all of them. Pay the mail's price, if the parcel came in under 4 pounds ⟨s_old_limit⟩. Pay the express company's price. Or wait for freight, which ran to a railroad depot, not to a farm.  

**[2:02] THE MAILBOX AT THE END OF THE LANE**  
One piece had to come first, and the post office built it. For most of the century, a farm family collected its mail in town, when somebody had a reason to go. On October 1, 1896 ⟨s_rfd_start⟩, the post office tried something new around Charles Town, Halltown and Uvilla, West Virginia: carriers who took the mail out to the farms themselves. Rural Free Delivery. It became permanent on July 1, 1902 ⟨s_rfd_permanent⟩. The country went from under 500 ⟨s_rfd_carriers_1899⟩ rural carriers to over 32,000 ⟨s_rfd_carriers_1905⟩ in a handful of years. So by the time anyone argued about parcels, the farm had something it had never had: a mailbox at the end of the lane, and a carrier who came to it on a route. What it didn't have was a way to send anything heavy down that lane.  

**[2:56] THE EXPRESS COMPANIES**  
Why didn't the post office carry heavier parcels? Ask the man who ran it. John Wanamaker, the Philadelphia merchant, was Postmaster General from 1889 to 1893 ⟨s_wanamaker_term⟩. As The Cosmopolitan reported it in 1904 ⟨s_wanamaker_year⟩, he said there were insuperable obstacles to the post office carrying parcels. First, the Adams Express Company. Then the American Express Company. Then Wells Fargo. Then the Southern Express Company. He was joking, and he wasn't. The express companies were a powerful lobby, and they liked the parcel business exactly as it was.  

**[3:31] WILSON**  
On August 15, 1912 ⟨s_wilson_date⟩, under a hot afternoon sun in Gloucester, New Jersey, the Democratic candidate for president, Woodrow Wilson, stood in front of about 5,000 ⟨s_wilson_crowd⟩ farmers and said it out loud. America had no parcels post, he told them, because there are certain express companies which object. On August 24, 1912 ⟨s_pp_signed⟩, nine days ⟨s_law_days⟩ after that speech, President Taft signed the parcel post into law. It would start on January 1, 1913 ⟨s_pp_start⟩.  

**[4:01] HOW MAIL ORDER SHIPPED BEFORE**  
Now, mail order existed long before the parcel post. In 1911 ⟨s_ward_year⟩, Montgomery Ward, the oldest of the big catalogue houses, said it shipped 82% ⟨s_ward_freight⟩ of its orders by rail freight, and only 8% ⟨s_ward_mail⟩ by mail. Freight had its own staircase. The Sears catalogue explained it to customers in capital letters: railroad companies usually charge no more for carrying 100 pounds ⟨s_rail_hi⟩ than they do for 20 pounds ⟨s_rail_lo⟩. So, it told them, if you only have a small order, get a friend to buy at the same time. Ship together. Split the minimum.  

**[4:38] THE CUSTOMER WHO DID THE ARITHMETIC**  
Think about who that customer was. A farmer, reading a catalogue by lamplight, working out whether a pair of boots and a lamp chimney would cost less if the neighbour ordered a saw. That's a person doing logistics arithmetic, on paper, to save cents. Hold on to that person. We'll need them later, because I think they understood something a lot of businesses selling online have lost.  

**[5:05] RICHARD SEARS**  
The company that would ship the most of it started with a box of watches nobody wanted. In 1886 ⟨s_watch_year⟩, a railroad station agent in North Redwood, Minnesota, named Richard Sears was offered a shipment of watches a local jeweller had refused. He sold them to other station agents along the line, and ordered more. He was 22 ⟨s_sears_age⟩. The next year, 1887 ⟨s_chicago_year⟩, he moved the business to Chicago and hired a watchmaker who answered a newspaper advertisement, Alvah Roebuck. By 1893 ⟨s_name_year⟩ the company carried both their names.  

**[5:40] ROSENWALD AND THE CATALOGUE**  
Richard Sears was a born copywriter. Make a watch sell a watch, he said. Roebuck, worn out, sold his stake. In 1895 ⟨s_rosenwald_year⟩, a Chicago clothing man named Julius Rosenwald and his brother-in-law bought in, paying $75,000 for half the company ⟨s_rosenwald_stake⟩. Sears wrote the catalogue. Rosenwald ran the business. By the turn of the century, with more than $10 million ⟨s_sales_1900⟩ a year in sales, Sears had passed Montgomery Ward. The catalogue was a thick book, mailed to farms, selling everything from a stove to a buggy, and every item in it had to get from a building in Chicago to a door that might be across the continent.  

**[6:24] CHAPTER — THE MACHINE BEFORE THE CARD**  
The machine before the card.  

**[6:28] THE PLANT**  
On January 22, 1906 ⟨s_plant_open⟩, Sears moved into a new plant on Chicago's West Side, years before anyone mailed a parcel at a parcel rate. The merchandise building alone covered 3 million square feet ⟨s_plant_sqft⟩. Railroad tracks ran into it. It had its own post office branch inside. And it ran on a schedule, designed by the operations superintendent, Otto Doering. Every order that came in was assigned a shipping room and a fifteen-minute ⟨s_slot⟩ window. Every department that held an item on that order had to deliver it to that room, in that window. If a department was late, the item shipped separately, and the department was billed for the extra cost.  

**[7:13] INSIDE THE SCHEDULE**  
The company's own guidebook from 1914 ⟨s_guide_year⟩ walks a visitor through it. Mail arrives by the sack. Clerks open it and sort it. In the Entry Department, 500 ⟨s_typists⟩ women type the orders on billing machines. Each order is split into tickets, one for every department it touches. Goods come down spiral chutes from the floors above, and in the shipping room, an army of 1,200 ⟨s_shipping_staff⟩ billers, checkers, weighers and packers assemble the orders, divided into freight, express and parcel post. The goods, the guidebook says, chase one another down the chutes as if they enjoyed the sport. And its phrase for the whole thing: the schedule must be rigidly maintained.  

**[7:57] THE YEARS IT TOOK**  
And it didn't work on the first day. Company forms show the schedule in wide use about two years after the move ⟨s_schedule_wide⟩. Julius Rosenwald's son Lessing joined the shipping department in 1912 ⟨s_lessing_year⟩, and he remembered the system as only then becoming fully effective. It took six years ⟨s_schedule_years⟩ from opening day. The idea fits in a sentence: a room, and a window on the clock. Making it hold is another thing. A system like that isn't installed. It's grown.  

**[8:29] THE SEWING MACHINES**  
Getting it wrong was expensive. In the 1890s ⟨s_sewing_decade⟩, before the schedule, one customer wrote in: For heaven's sake, quit sending me sewing machines. Every time I go to the station I find another one there. You have shipped me five already. ⟨s_sewing_quote⟩ Orders went out over and over again, and Sears paid the freight on every one that came back. A low price shipped over and over was the most expensive thing Sears could sell.  

**[8:59] THE DAILY LOAD**  
By the time the parcel post arrived, the plant was assembling 45,000 ⟨s_orders_day⟩ complete orders a day, and loading sixty to seventy-five freight cars ⟨s_cars_day⟩. And notice the word in the guidebook: weighers. Every parcel was weighed, because weight decided the price of moving it. Before the parcel post, that price was mostly a freight bill the customer paid at the depot. After the parcel post, it was a stamp on the box.  

**[9:28] THE GUARANTEE**  
There was one more piece of the machine, and it's the one that made strangers buy from a catalogue. Sears printed a guarantee. In the guidebook's version: if for any reason whatever you are dissatisfied with any article purchased from us, we expect you to return it to us at our expense, and we will return your money, including any transportation charges you paid. Notice the last part. The guarantee named shipping by name. That tells you which cost its customers worried about. A small correction to the story you may have heard: Sears didn't invent the money-back guarantee. Montgomery Ward adopted it in 1875 ⟨s_ward_guarantee_year⟩. Sears made it part of the machine.  

**[10:13] CHAPTER — THE STAIRCASE**  
The staircase.  

**[10:17] MIDNIGHT**  
At 12:01 a.m. ⟨s_cup_time⟩ on January 1, 1913 ⟨s_pp_start⟩, the Postmaster General, Frank Hitchcock, put one of the new service's first parcels into the mail: a silver trophy cup, addressed to the postmaster of New York, Edward Morgan. A second cup went the other way, from New York to Washington. Both are in the Smithsonian's postal collection, and the museum's own records give each of them a claim to being first. It was publicity, and it worked. But a cup isn't the interesting thing that started that night. The interesting thing was printed on a card.  

**[10:55] THE CARD**  
Here it is. A parcel could weigh up to 11 pounds ⟨s_limit_1913⟩ and measure up to 72 inches ⟨s_size_1913⟩, length and girth combined. The country was cut into 8 zones and a local rate ⟨s_zone_count⟩, measured outward from wherever you mailed it. And the price had a shape: a rate for the first pound, and a rate for each additional pound. In zone 1 ⟨s_z1⟩, out to about 50 miles ⟨s_z1_miles⟩, the first pound cost 5 cents ⟨s_z1_first⟩, and each pound after it 3 cents ⟨s_z1_add⟩. In zone 8 ⟨s_z8⟩, the farthest, the first pound cost 12 cents ⟨s_z8_first⟩, and every pound after it another 12 cents ⟨s_z8_add⟩.  

**[11:35] THE FRACTION**  
Now read the line again, because this is the whole film. The Act charged for the first pound, quote, or fraction of a pound, and for each additional pound, or fraction of a pound. A fraction counted as a whole. A parcel of a pound and an ounce paid the same as a parcel a whisker under the next pound. So, your guess. If you guessed a sliver, you guessed a slope. The card was a staircase. Flat treads, sudden risers. And the risers don't care how far over the line you are. One ounce over costs exactly as much as the whole next pound. Below the first step there was a smaller staircase: parcels of 4 ounces ⟨s_small_limit⟩ or less paid 1 cent an ounce ⟨s_small_rate⟩. Steps inside steps.  

**[12:27] WHAT ELEVEN POUNDS COST**  
Here's what that meant at the weight limit. A parcel at the 11-pound ⟨s_limit_1913_adj⟩ limit cost 15 cents ⟨s_11_local⟩ at the local rate. That's the exact postage on James Beagle. To zone 1 ⟨s_z1⟩ the same parcel cost 35 cents ⟨s_11_z1⟩. To zone 8 ⟨s_z8⟩, $1.32 ⟨s_11_z8⟩. Distance multiplied the steps. And every customer in America could see this card. It was printed. It was posted. The postmaster would tell you your zone.  

**[12:54] THE FLOOD**  
Then the parcels came. In its opening days, more than 4 million ⟨s_parcels_5days⟩. In the first year, more than 600 million ⟨s_parcels_year⟩. In a count Congress ran over six weeks ⟨s_count_weeks⟩ in 1914 ⟨s_count_year⟩, post offices dispatched 77,539,521 ⟨s_count_all⟩ parcels, and 19,818,210 ⟨s_count_chicago⟩ of them left from Chicago. The average postage on a parcel was 4.9 cents ⟨s_avg_postage⟩. A Joint Committee of Congress reported on December 1, 1914 ⟨s_jc_date⟩ that the parcel post business from the mail-order houses exceeded the business from all other sources combined.  

**[13:26] THE CATALOGUE RODE THE CARD**  
There's a quieter number in the Joint Committee's report, and it may matter more than the parcels. The catalogue itself was mail. A postmaster in Iowa told the committee that a 3-pound ⟨s_cat_weight⟩ Sears catalogue had cost 24 cents ⟨s_cat_before⟩ to mail before catalogues were let into the parcel post. After, it cost 10 cents ⟨s_cat_after⟩ to reach his office. And the committee found that one firm alone had saved approximately $1,000,000 ⟨s_one_firm_saving⟩ a year in postage from that change. The card didn't only cut the cost of delivering an order. It cut the cost of asking for one. Every book that landed on a farm table was a store opened in somebody's kitchen, and the card had made opening it far cheaper.  

**[14:14] THE STORE IN TOWN**  
Think about what that did to the general store in a farm town. It had a counter, a shelf, a credit book, and it had never competed with a catalogue on the price of moving a parcel, because before 1913 ⟨s_pp_year⟩ the catalogue couldn't move a parcel to the farm cheaply. Now it could. The customer did the arithmetic: the catalogue's price, plus the postage off the card, against the storekeeper's price. That's the sentence our historian wrote. The decline of the old general store began the day parcel post went into effect.  

**[14:52] CHAPTER — WHO PAID FOR THE OUNCE**  
Who paid for the ounce.  

**[14:56] THE TURN**  
Here is the detail that changes the story. Sears did not pay that postage. The customer did. Open a Sears catalogue of 1917 ⟨s_1917_year⟩, this one for electrical goods, and you find, printed in the book itself, a full table: Rates for Parcel Post Shipments, measuring from Chicago. Zones across the top. Weights down the side. And next to every item in the catalogue, its shipping weight. The instructions told you to work out the postage yourself and include it in your money order.  

**[15:30] THE STAIRCASE WAS VISIBLE**  
So the staircase was visible. The catalogue asked every customer to look up their zone, read the item's weight, and find the postage on the table. For the unsure, it said this: If in doubt as to what amount is required for any order you are perfectly safe in adding even more than you think necessary, for we will ship by the most economical method and will return you any amount that is left over. ⟨s_doubt_quote⟩ And it warned them about the box: Occasionally, according to the nature of the merchandise, we are obliged to give the actual weight. In such cases a few ounces extra in weight must be allowed for wrapping and packing, according to the nature of the goods. ⟨s_wrap_quote⟩ In effect, a nation of farmers was optimising shipping weight against a rate card. With a pencil.  

**[16:26] THE FARMER'S PENCIL**  
Let's do one with the pencil. A parcel going to zone 8 ⟨s_z8⟩ weighs a pound and an ounce. The first pound costs 12 cents ⟨s_z8_first⟩. The extra ounce counts as a whole pound, so it costs another 12 cents ⟨s_z8_add⟩. That's 24 cents ⟨s_z8_17oz⟩ in all. Take the ounce out and it's 12 cents ⟨s_z8_first⟩. That one ounce cost as much as the whole first pound. Now flip it. Leave the ounce in, and you've already paid for the second pound. You can add almost a full pound of something else to the order for no more postage at all. A farmer who saw that could order the lamp chimney now instead of next month. One who didn't would pay for another first pound a month later.  

**[17:15] THE EDGES**  
And the card had edges, and the edges decided who won. On August 15, 1913 ⟨s_merge_date⟩, the post office changed the card. Zones 1 and 2 ⟨s_z12⟩ were merged at 5 cents, plus 1 cent a pound ⟨s_merge_rate⟩, because, the official in charge explained, 30% ⟨s_merge_share⟩ of all shipments went to those zones. On January 1, 1914 ⟨s_limit_1914_date⟩, the weight limit nearby rose to 50 pounds ⟨s_limit_1914⟩. And then a congressional committee found the town of Bavaria, Kansas. A 50-pound ⟨s_bavaria_weight⟩ parcel to Bavaria cost 54 cents ⟨s_bavaria_cost⟩ from a mail-order house in Kansas City, 193 miles ⟨s_kc_miles⟩ away by rail. From a merchant in Salina, 7 miles ⟨s_salina_miles⟩ away, it cost the same. The committee's word for it was inequitable. And notice who could fix it. Congress had done something unusual in the Act: it let the Postmaster General change the rates, the zones and the weights himself, with the consent of the Interstate Commerce Commission. The card could be redrawn without a new law. It was, again and again.  

**[18:20] THE LESSON OF THE EDGE**  
A rate card isn't neutral. Wherever it draws a line, somebody sits a hair over it and somebody sits a hair under it, and they pay different prices for nearly the same thing. A merchant who knew where the lines were could arrange his business around them, and Congress found the mail-order houses did. Under the zones, its report said, a mail-order house could set up a branch agency in the territory it wanted to reach. Within 150 miles ⟨s_radius⟩ of it, the house paid exactly the same rate as the local merchant. That's Bavaria. And for the catalogues: From points in the fourth or fifth zones, these catalogues are shipped by freight to some point within the State and distributed from that point by mail. ⟨s_freight_catalogue_quote⟩ By 1918 ⟨s_pi_year⟩, Sears had 72 ⟨s_warehouses⟩ warehouses for its catalogues alone. Position against the card is money.  

**[19:17] THE MYTH**  
One more correction, because you'll read it everywhere. The story goes that the parcel post made Sears fill five times as many orders ⟨s_myth_orders⟩ in its first year. Sears' own annual reports don't support it. Net sales were $77.1 million ⟨s_sales_1912⟩ in the year before parcel post, and $91.4 million ⟨s_sales_1913⟩ in its first year. Up 18.5% ⟨s_growth_1913⟩. The accounts count dollars, not orders. But that many more orders on that much more money would mean the average order collapsed in a single year, and we found nothing in the record that shows it. By 1917 ⟨s_1917_year⟩ sales reached $165.8 million ⟨s_sales_1917⟩. By the end of the decade, $234 million ⟨s_sales_1919⟩. The parcel post was a ramp, not a rocket, and the company that climbed it was the one that had built the machine first.  

**[20:09] HOW IT ENDED**  
The catalogue lived a long time. On February 2, 1925 ⟨s_store_1925⟩, Sears opened its first retail store, inside the Chicago plant. When the stores came, the executive who pushed them, Robert Wood, explained why Sears would compete with its own catalogue: Better to lose that business to one's self than to someone else ⟨s_wood_quote⟩. By 1931 ⟨s_store_year⟩, stores brought in 53.4% ⟨s_store_share⟩ of its sales. And in 1993 ⟨s_end_year⟩, a newspaper wrote the obituary of the 97-year-old ⟨s_end_age⟩ general merchandise catalogue. It wasn't killed by postage. Cars, cities and chain stores had moved where people shopped, and by the end it was losing money. But the card it rode is still with us.  

**[20:53] CHAPTER — THE CARD YOU PAY NOW**  
The card you pay now.  

**[20:57] THE DESCENDANT**  
Here is today's version of the 1913 ⟨s_pp_year⟩ card. The postal service's ground parcel rate, effective July 12, 2026 ⟨usps_effective⟩. It has 8 zones ⟨usps_zones⟩. Prices go up by the pound. In zone 1 ⟨usps_z1⟩, a parcel under a pound costs $6.93 ⟨usps_z1_1lb⟩. Go an ounce over a pound and it bills as 2 pounds ⟨usps_two_lb⟩: $7.99 ⟨usps_z1_2lb⟩. In zone 8 ⟨usps_z8⟩, under a pound: $8.40 ⟨usps_z8_1lb⟩. An ounce over a pound: $12.87 ⟨usps_z8_2lb⟩. Crossing that line costs $4.47 ⟨usps_z8_step⟩ a parcel. If you sell on Shopify and ship your own orders, this is the card under your margin. The same skeleton Congress wrote over a century ago. Zones across the top. Pounds down the side. Every fraction rounded up.  

**[21:41] THE FULFILMENT FEE**  
If you sell on Amazon and use its fulfilment, you pay a different card, built the same way. The fulfilment fee for a standard-size item climbs in steps of weight. For a large standard item priced from $10 to $50 ⟨rc_band⟩, the non-peak card that took effect January 15, 2026 ⟨rc_card_from⟩ charges $4.20 ⟨rc_ls12⟩ from 8 ounces ⟨rc_8oz⟩ up to 12 ounces ⟨rc_12oz⟩. Over 12 ounces ⟨rc_12oz⟩, $4.60 ⟨rc_ls16⟩. One step: $0.40 ⟨rc_ls_step⟩, on every unit, before the fuel and logistics surcharge of 3.5% ⟨rc_fuel⟩ that's added to every fulfilment fee. And from October 15 ⟨rc_peak_from⟩, a peak card raises the steps for the holidays. Your customer never sees this card. You pay it. And unlike the farmer, I'd bet most sellers have never laid their products against it.  

**[22:30] THE CASE**  
Here's what that looks like on one real listing, which we modelled from public data. It belongs to a car-care brand ⟨cs_who⟩: a paint scratch remover ⟨cs_product⟩. Its public page lists an item weight of 8.8 ounces ⟨cs_weight⟩. Packed, it can only weigh more, so that's the least it's over by. The step below sits at 8 ounces ⟨cs_edge⟩. So on every unit it ships, it pays the next step: $0.26 a unit ⟨cs_step⟩ on the non-peak card, $0.28 ⟨cs_step_peak⟩ on the peak card, surcharge included. It sells an estimated 3,500 units a month ⟨cs_units⟩, from its public sales rank. Before I tell you what that comes to in a year, put your own number on it. Now, its units aren't one number, so we didn't use one. We ran 10,000 ⟨cs_years⟩ simulated years of its sales and costs. In eight in ten ⟨cs_band_share⟩ of them, that one riser comes to between $6,400 ⟨cs_leak_p10⟩ and $19,200 ⟨cs_leak_p90⟩ a year. An estimate. Not a client. Not a result. And not on the brand's P&L as a line of its own, because a P&L has no line for it.  

**[23:41] THE INVISIBLE LINE ITEM**  
That's the turn our farmer would understand immediately, and a P&L never shows. The P&L shows fulfilment fees as one number. It doesn't show which of them are a step you could have stepped under. In the demo catalogue we use for teaching, Tarnhollow ⟨demo_brand⟩, Amazon's fees, referral, fulfilment, storage and the rest together, took 32.1% ⟨fee_share_latest⟩ of revenue last month, $102,395 ⟨fees_latest⟩ in all. That's demo data ⟨demo_label⟩, made to behave like a real catalogue. The total is on the P&L. The steps inside it are not.  

**[24:17] WHERE THE CARD WENT**  
So why could a farmer with a pencil see the staircase, when a business with accounting software can't? It isn't that the card is hidden. The cards in this film are published, every one of them. What changed is the moment. In the parcel post years, the customer paid the postage, before the parcel moved, with the card open on the table and the item's weight printed beside its price. Today the seller pays, after the sale, as a deduction in a settlement report or a line on a monthly bill, folded in with everything else. The card is still there. Nobody hands it to you at the moment you could act on it. And a cost you never see at the moment of decision is a cost you never decide.  

**[25:10] THE OTHER STAIRCASES**  
And weight is only the first staircase. The fulfilment fee also changes with the price you charge: the card has edges at $10 ⟨rc_edge_lo⟩ and $50 ⟨rc_edge_hi⟩, and a price that crosses one moves the whole product onto a different card. For a box over a cubic foot, the card weighs the box itself: length times width times height, in inches, divided by 139 ⟨rc_dim_divisor⟩, gives a weight in pounds, and the card charges whichever is greater. In 1913 ⟨s_pp_year⟩, size was a limit. Today it's a price. Storage has a cliff of its own. On that same case-study listing, the surcharge for stock that has sat between 241 and 270 days ⟨cs_aged_band⟩ is $1.50 ⟨cs_aged_before⟩ a cubic foot a month. From day 271 ⟨cs_aged_day⟩, it's $5.45 ⟨cs_aged_after⟩. For every 1,000 units ⟨cs_aged_units⟩, at the January-to-September storage rate, storage and surcharge together go, by our estimate, from $72.70 ⟨cs_aged_1000_before⟩ a month to $198.67 ⟨cs_aged_1000_after⟩. Nothing about the product changes on that day. Only its age. Our farmer would have recognised every one of these. Same shape. Drawn in dollars, in inches and in days instead of pounds.  

**[26:21] HOW TO FIND YOUR STEPS**  
So let's do what the farmer did, with your catalogue. Take your top sellers by units. For each one, find its billable weight: the item, plus the box, plus the packing, or the box's dimensional weight if that's greater. Not the weight on the spec sheet. Sears told its customers the same thing in 1917 ⟨s_1917_year⟩: a few ounces extra for wrapping and packing. On Amazon, the fee preview report lists the weight and the sides it measured for every product; your carrier's invoice shows the weight it billed. Then find each product's line on the card. Write down the next edge below it, and how far over that edge it sits. That distance is the whole game. A product an ounce over a line is a candidate. A product sitting in the middle of a tread is not.  

**[27:17] THE COUNTERFACTUAL**  
For each candidate, write the counterfactual. What would this unit cost to ship, one step down? The difference, times the units it sells, is the riser's yearly cost. Use the peak card's step from October 15 ⟨rc_peak_from⟩, and the normal card's the rest of the year. And your units aren't one number either: do the multiplication for a slow year and a strong year, and that's your range. Then ask the practical question. Can the packaging lose that ounce? A lighter box, a thinner insert, a different mailer. Here's a rule: if the packaging change costs less a unit than the step, and doesn't add damage, fight the step. If the change has a one-time cost, a new carton run or a redesign, divide it by the step times the units a month: that's how many months it takes to pay back. Plan on the slow year. If it doesn't pay, leave it, and count the step in the product's margin.  

**[28:21] THE ZONES**  
If you ship your own orders, do the same with zones. Where do your parcels actually go? A store whose customers sit mostly in the far zones pays a different card than one whose customers are close. Sears' customers knew their zone because the postmaster told them. You can know yours from your own shipping reports. The carrier's card is public. Your mix of zones is in your own data.  

**[28:50] WHEN THE CARD CHANGES**  
And do it again every time the card changes. The 1913 ⟨s_pp_year⟩ card changed on August 15, 1913 ⟨s_merge_date⟩, and again on January 1, 1914 ⟨s_limit_1914_date⟩. Today's cards change on a calendar: the fulfilment fee has a non-peak card and a peak card, and the postal rates move when a notice says they move. A product that sat safely under a line last year can sit over it this year without anything about the product changing. The line moved.  

**[29:21] WHERE THE STAIRCASES MEET**  
Here's the part that takes longer than an afternoon. The staircases touch each other. Shave the ounce with a thinner mailer, and the product arrives damaged more often, and every return pays the card again. Buy a bigger box to protect it, and you may cross into the size price. Cut the price to sell more, and you can step across a price edge onto another card. Order deeper to get a better unit cost, and the slowest units walk toward day 271 ⟨cs_aged_day⟩. Hold less to stay young, and you run out in the season that matters. Every one of those moves is arithmetic on its own. Together they push on each other, and they all depend on a number nobody knows yet: how many units you'll actually sell. That's the difference between a staircase and a system.  

**[30:17] WHAT YOU CAN DO THIS WEEK**  
So here's this week. List your top products by units. Find each one's billable weight. Find its line on the card you actually pay. Mark the ones within 2 ounces ⟨cs_near_edge⟩ above the edge below. For each, write the counterfactual, at the peak and normal cards, for a slow year and a strong one. Try the packaging on the top few, and fight each step or count it, by the rule. Then set a reminder for the next card change. That's a few hours. If one of your bestsellers sits an ounce over a line, it may be the cheapest money you find this month.  

**[30:59] THE RETURN**  
15 cents ⟨s_beagle_postage⟩. A boy in Ohio, a carrier, a card. The card asked every farmer who ordered to do the arithmetic. The card never went away. It's yours to read now.  

**[31:12] THE HONEST LIMIT**  
You can do this week's list by hand for your top products, and it's worth doing. Where it breaks is everything after. Every product, against every card you pay, the fulfilment card, the peak card, the carrier's zones, the storage fees that have their own steps, re-checked every time a card changes, with the units each product will actually sell over the next season rather than last month's. And deciding, for each one, whether the step is worth fighting or worth pricing in, when the moves push on each other. The lookup is a spreadsheet. The forecast and the trade-offs aren't. They're a model: probability, forecasting, the same tools actuaries use to price risk. It's what I studied, and it's what Hubricon is built to run, every week, for every product. The whole method is free at hubricon.com/learn, in the Fee Staircase course. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The free Fee Staircase course at hubricon.com/learn. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | still-push on a public-domain parcel post carrier photograph (Smithsonian National Postal Museum, CC0) toward the parcel; number-land on {{s_beagle_postage}}; still-push on the card's printed table, the push stopping before the first row can be read. Never the staged babies-in-mailbags photographs: they are posed and predate parcel post. |  |
| 0:34 | footage-establish on a present-day parcel sorting hall (stock, no logos); quote card for Wayne Fuller's line with its source; still-push on a parcel on a scale, the needle not yet settled (stock, no logos). |  |
| 1:17 | chapter |  |
| 1:21 | archive-framed on a rural free delivery wagon (Smithsonian National Postal Museum, CC0); table-scan typesetting the three prices per ton from the Postal Regulatory Commission's history, the mail row marked; still-pan across a farm landscape photograph (Library of Congress, no known restrictions). |  |
| 2:02 | archive-framed on a Rural Free Delivery wagon (Smithsonian National Postal Museum, CC0); timeline from the experiment to the permanent service, each date landing as spoken; still-push on a rural carrier at a roadside mailbox (Smithsonian, CC0) toward the box; footage-insert of a farm lane's mailbox in morning light (stock, no markings). |  |
| 2:56 | quote card: Wanamaker's remark as The Cosmopolitan printed it, attributed "as reported"; archive-stack of express company wagons and offices (Library of Congress, no known restrictions), each landing as the narration names it. |  |
| 3:31 | quote card: Wilson's sentence, verbatim, with "St. Louis Post-Dispatch, August 16, 1912" in the attribution; timeline from the speech to the signing to the launch, each date landing as it is spoken. |  |
| 4:01 | doc-clipping on the catalogue's freight advice as quoted in the Congressional Record, the capitalised line underlined in ink; footage-insert of a freight car door rolling shut (stock, no markings). |  |
| 4:38 | still-push on a public-domain photograph of a farm family reading by lamplight, or of a general store's mail-order counter (Library of Congress); breath under the last sentence. |  |
| 5:05 | archive-framed on the R. W. Sears Watch Company advertisement of 1888 (Wikimedia Commons, public domain); still-pan across a Minnesota railroad depot photograph (Library of Congress); footage-insert of a pocket watch movement (stock, close). |  |
| 5:40 | still-push on the Library of Congress portrait sheet of Sears, Nusbaum and Rosenwald (no known restrictions), toward Rosenwald; archive-stack of catalogue covers from the turn of the century (public domain), landing as "stove" and "buggy" are spoken; doc-highlight on a catalogue page's shipping weight line. |  |
| 6:24 | chapter |  |
| 6:28 | still-pan across the Historic American Buildings Survey photograph of the Sears mail-order plant (Library of Congress, no restrictions); archive-framed on the plant's train shed stereoview (New York Public Library, public domain); timeline drawing the order's path, room by room, in the shot's own time. |  |
| 7:13 | archive-stack of the guidebook's photographs (Internet Archive, public domain): the mail room, the billing machines, the chutes, a row of packers, each landing with its noun; doc-highlight on "the schedule must be rigidly maintained". |  |
| 7:57 | archive-stack of the plant's pneumatic tube station (Wikimedia Commons, public domain) and the guidebook's billing room; timeline from the move to {{s_lessing_year}}, the years drawn out slowly, the span landing as spoken. |  |
| 8:29 | quote card: the letter verbatim, attributed "a customer's letter, quoted in Emmet and Jeuck, Catalogues and Counters"; footage-insert of an old treadle sewing machine's wheel turning (stock, close, no maker's mark). |  |
| 8:59 | number-pair: orders a day against freight cars a day, ink; footage-process (wide, medium, detail) of a modern parcel line: the conveyor, a parcel on a scale, a label printing (stock, no logos), screen direction left to right; footage-insert on the scale's needle settling. |  |
| 9:28 | quote card: the guarantee, verbatim, with "A Visit to Sears, Roebuck and Co., 1914" in the attribution; doc-highlight on "including any transportation charges you paid", ink underline; archive-framed on a Montgomery Ward catalogue page (public domain). |  |
| 10:13 | chapter |  |
| 10:17 | archive-framed on the Hitchcock inaugural trophy cup (Smithsonian National Postal Museum, CC0), the push slow; archive-framed on the second cup (same source); still-push on a parcel post wagon of 1913 (same source). |  |
| 10:55 | archive-framed on the official 1913 Parcel Post zone map signed by Postmaster General Hitchcock (Smithsonian National Postal Museum, CC0); table-scan typesetting the Act's rate table, zone 1 and zone 8 rows marked as spoken, the money cells in blue. | published: the Parcel Post Act, 37 Stat. 557 (govinfo.gov) |
| 11:35 | doc-highlight on "or fraction of a pound", the underline in blue because it is money; counterfactual on the house staircase chart, redrawn with the 1913 zone 8 rates: a solid dot for the parcel as it is, a hair over a pound, and a hollow dot for the same parcel one step down, the riser in blue; the narration names which dot is which the first time they appear. | published: the Parcel Post Act, 37 Stat. 557 |
| 12:27 | chart-build of the three prices for the same parcel as a stepped bar by zone, the local rate landing on "James Beagle" with a callback to the cold open's parcel; still-push on a parcel post wagon (Smithsonian, CC0). | published: computed from the Parcel Post Act's rates |
| 12:54 | number-land on {{s_parcels_year}}; unit-grid of the {{s_count_weeks}} count with Chicago's share filled in ink; archive-framed on a parcel post section of a city post office (Library of Congress); quote card with the Joint Committee's sentence and its date. |  |
| 13:26 | doc-clipping on the postmaster's testimony and the committee's finding in the Joint Committee report (Internet Archive, public domain), the prices and the saving underlined, the money in blue; still-push on a turn-of-the-century catalogue cover (public domain) toward its title; number-pair: {{s_cat_before}} against {{s_cat_after}}. | published: the Joint Committee of Congress report, 1914 |
| 14:14 | still-push on a general store interior photograph (Library of Congress, no known restrictions), toward the counter; split-then-now: the general store then, a modern parcel locker bank now (stock, no logos); quote card for Fuller, "RFD: The Changing Face of Rural America". |  |
| 14:52 | chapter |  |
| 14:56 | doc-highlight on the 1917 catalogue's rate table page (Internet Archive, public domain), the heading and "measuring from Chicago" marked in ink; doc-highlight on an item's printed shipping weight; still-push on the catalogue page's footer line, "We Positively Guarantee the Safe Delivery of Everything Shipped by Us." |  |
| 15:30 | formula-build: the first pound at its rate, plus each further pound, rounded up, at the additional rate, each term landing as spoken; doc-highlight on "a few ounces extra in weight must be allowed for wrapping and packing", ink; kinetic-thesis: "In effect, a nation of farmers was optimising shipping weight against a rate card." (the act's one thesis line). |  |
| 16:26 | formula-build: first pound, plus the ounce rounded up to a pound, each term landing as spoken, the total in blue; counterfactual on the house staircase redrawn with the 1913 zone 8 rates, the solid dot a hair over the riser, then a second dot sliding along the same tread toward the next riser as "almost a full pound" is spoken; still-push on a catalogue page of lamp chimneys (Internet Archive, public domain). | published: computed from the Parcel Post Act's rates |
| 17:15 | timeline of the card's revisions, each date landing as spoken; table-scan of the merged zones row; still-pan across a Kansas prairie town photograph (Library of Congress); number-pair: {{s_kc_miles}} against {{s_salina_miles}}, both paying {{s_bavaria_cost}}, the distances in ink, the price in blue. | published: the Joint Committee of Congress report, 1914 |
| 18:20 | quote card: the committee's branch-agency sentence verbatim ({{s_branch_quote}}); doc-clipping on it in the report (Internet Archive, public domain), "150 miles" and "the same rate" underlined in ink; still-pan across a map of Kansas with a branch agency's radius drawn in ink and Bavaria inside it; counterfactual on the house staircase redrawn with the 1913 rates, two parcels either side of one riser. | published: the Joint Committee of Congress report, 1914, and the Parcel Post Act's rates |
| 19:17 | doc-highlight on the net sales line of Sears' annual report (Internet Archive, public domain); chart-build of net sales by year, each bar landing as its figure is spoken, the myth's claim struck through in ink beside it. | published: Sears, Roebuck and Co. annual reports (Internet Archive) |
| 20:09 | archive-framed on a Sears retail store photograph of the 1920s (Library of Congress, if no known restrictions, else public-domain Commons); quote card for Wood's line, verbatim, attributed "Robert E. Wood, quoted in Emmet and Jeuck, Catalogues and Counters"; timeline from the first store to the end of the catalogue; breath on a held catalogue page, the bed rising. |  |
| 20:53 | chapter |  |
| 20:57 | match-bridge: the 1913 rate table holds still on screen while the era changes, then table-scan of today's ground rates as recorded in ratecard.json, the zone 8 row and the one-pound line marked, the money cells in blue; counterfactual on the house staircase at the one-pound riser, the dots labelled "an invented parcel". | published: USPS Ground Advantage Commercial prices, Notice 123, as recorded in ratecard.json |
| 21:41 | doc-highlight on a typeset extract of Amazon's published fee card as recorded in ratecard.json, dated, never imitating Amazon's interface; table-scan of the large standard rows with the eight, twelve and sixteen ounce lines marked, the step in blue; footage-insert of a parcel on a warehouse scale (stock, no logos). | published: Amazon's US FBA fee card, 2026, as recorded in ratecard.json |
| 22:30 | counterfactual on the house staircase chart from the case study, the solid dot at {{cs_weight}}, the hollow dot at {{cs_edge}}, the riser and its label in blue; breath on "put your own number on it"; range-band on the house Monte Carlo, the band landing on "between", the label "Modeled from public data · Not a client · Not a result" on both. | modeled from public data: Hubricon's public-data case study (data/case-study.json) |
| 23:41 | chart-build of the demo catalogue's monthly waterfall, revenue down to net, the fees bar landing on "fees", labelled Tarnhollow demo data; doc-highlight on a typeset P&L line "Fulfilment fees" with no detail beneath it, ink underline. | demo: Tarnhollow demo data, the engine's latest month |
| 24:17 | split-then-now: the 1917 catalogue's rate table open beside an item's shipping weight, then a typeset settlement report with fees as one deduction (house design, never imitating any platform's interface); footage-observe on a desk with a closed laptop in soft daylight (stock, high-key, no screen visible). |  |
| 25:10 | table-scan of the price bands with the two edges marked, the edges in blue; formula-build: length, times width, times height, over the divisor, set against the scale's weight, the greater one landing on "whichever is greater"; chart-build on the house aging chart, the cliff landing on {{cs_aged_day}}, the jump and its label in blue, the proof label on; number-pair: {{cs_aged_1000_before}} against {{cs_aged_1000_after}}, labelled "estimate · Modeled from public data · Not a client · Not a result". | modeled from public data: Hubricon's public-data case study (data/case-study.json, aging bands); published: Amazon's US FBA fee card, 2026, as recorded in ratecard.json |
| 26:21 | formula-build: item, plus box, plus packing, against the dimensional weight, the greater rounded up to the card's step, each term landing as spoken; doc-highlight returning to the 1917 catalogue's "a few ounces extra" line; table-scan of a typeset worksheet with columns for product, billable weight, edge below, distance over (empty, no figures); footage-insert of a hand placing a carton on a postal scale (stock, no face). |  |
| 27:17 | counterfactual on the house staircase, the hollow dot one step down landing on "one step down", labelled "Modeled from public data · Not a client · Not a result"; formula-build: the step, times the units, at the peak and normal cards, for a slow year and a strong year, each term landing as spoken (terms only, no figures); footage-process (wide, medium, detail) of repacking: a box cut down, an insert replaced, the parcel weighed again (stock, hands only). | modeled from public data: the house staircase chart |
| 28:21 | table-scan of today's ground rates by zone with the one-pound line marked; still-push on the 1913 zone map, back to the opening of the staircase chapter. | published: USPS Ground Advantage Commercial prices, as recorded in ratecard.json |
| 28:50 | timeline of card changes, 1913's revisions above, today's effective dates below, each landing as spoken; counterfactual: an invented parcel's dot, with the riser moving under it, labelled "illustration"; footage-observe on a quiet packing table under daylight (stock), the voice carrying the point. | published: the 1913 card's revisions and today's fee card dates, as recorded in ratecard.json |
| 29:21 | chart-build of the house staircase, the aging chart and the price bands set side by side on one paper, a single demo product's dot moving on all three at once as each move is spoken, each crossing marked in blue, labelled Tarnhollow demo data; range-band on the house Monte Carlo as "a number nobody knows yet" is spoken, labelled "Modeled from public data · Not a client · Not a result". | demo: Tarnhollow demo data; modeled from public data: the house Monte Carlo |
| 30:17 | formula-build listing the steps as terms, each landing as spoken; receipt: one demo row showing a step found, the counterfactual, and the decision, labelled Tarnhollow demo data. | demo: Tarnhollow demo data |
| 30:59 | still-push resuming on the cold open's parcel post photograph, the same framing; kinetic-thesis: "The card never went away.". | published: the Parcel Post Act's rates |
| 31:12 | range-band on the house Monte Carlo, the band holding while the voice names what it takes, labelled "Modeled from public data · Not a client · Not a result"; chart-build of the staircase with every demo product placed on it at once, the over-the-line ones in blue, labelled Tarnhollow demo data; end card at "hubricon.com/learn". | demo: Tarnhollow demo data; modeled from public data: the house Monte Carlo |

### Decide

```
hubricon-content approve greats-01-sears-parcel-post
hubricon-content reject  greats-01-sears-parcel-post --note "what to change"
```
Edit `content/videos/greats-01-sears-parcel-post/script.md` first if you prefer; it is re-validated on approve.

## G02 · series · tier D · pillar 3 — script gate

**Title:** Woolworth's Kept Its Dime Ceiling for more than 50 years ⟨w_ceiling_span⟩. Here's What It Never Told Them  
**Thumbnail:** A dime, close and sharp, on paper; beside it a hairline price curve with a single point and its hollow band  
**Spiky claim:** A price you've never moved isn't a safe price. It's an unmeasured one, and the most famous price in American retail stayed unmeasured for decades.  
**Misconception:** A price that's working should be left alone. Moving it is a gamble, and holding it is the safe choice.  
**CTA:** The free Price Curve course at hubricon.com/learn, then the one soft close.  
**Estimated runtime:** about 29 min 04 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $127.65 ⟨w_day1⟩ in nickels, every sale the same price. That's what Frank Woolworth's store took on its first day. His company kept a ceiling over its prices for more than 50 years ⟨w_ceiling_span⟩. It built the tallest building in the world. It also hid a number.
2. 10 cents ⟨w_dime⟩. A toy maker said he couldn't make it pay at that price. Woolworth's buyer said: throw the toys in vats. Dip them. The product changed. The price never did. What would it have told him if it had?
3. January 25, 1933 ⟨w_promise_date⟩. Woolworth's board tells its stockholders it has no intention of going past its new ceiling. Within 3 years ⟨w_promise_span⟩ the ceiling is gone. A held price feels safe. Is it?

### Script

**[0:00] COLD OPEN**  
Saturday, June 21, 1879 ⟨w_lancaster_date⟩. The circus has come to Lancaster, Pennsylvania, with its parade down the city streets, and a young man whose first store has already closed is opening another he can barely afford. The rent is $30 a month ⟨w_rent⟩. The stock, $410 ⟨w_stock_1879⟩ of it, is much of it on credit. He has 7 ⟨w_clerks⟩ clerks, and he hasn't advertised. He spends the morning worrying whether anyone will come. Every item in the store costs the same: a nickel. By tea time they've taken $47.65 ⟨w_teatime⟩. By closing, $127.65 ⟨w_day1⟩. That's 2,553 ⟨w_day1_count⟩ separate sales, at one price, and 31% ⟨w_stock_sold⟩ of everything in the store gone in a day. The next morning he wrote to his father: We could have sold $200 if the store had been larger. ⟨w_letter_quote⟩  

**[0:50] THE QUESTION**  
His name was Frank Woolworth. If you sell anything, you already know the moral you'd draw from a day like that. Find a price that works, and don't touch it. Woolworth's company kept a ceiling over its prices, in most of its stores, for more than 50 years ⟨w_ceiling_span⟩: first a nickel, then a dime. And it built the tallest building in the world. Hold on to that moral. This film tests it.  

**[1:20] CHAPTER — ONE PRICE**  
One price.  

**[1:23] THE CLERK**  
Go back a few years. Woolworth was born on a farm near Rodman, in upstate New York, in 1852 ⟨w_born⟩. In 1873 ⟨w_start_year⟩ he got himself a place in a dry goods store in Watertown, Augsbury and Moore. The pay was nothing at all for 3 months ⟨w_unpaid⟩, then $3.50 a week ⟨w_first_wage⟩. Ill health sent him back to the farm for a while. He came back to the same firm, by then Moore and Smith, in 1877 ⟨w_return_year⟩, at $10 a week ⟨w_return_wage⟩. A farm boy, a clerk, and nobody's idea of a merchant prince.  

**[1:59] THE FIVE-CENT TABLE**  
In 1878 ⟨w_counter_year⟩, a travelling salesman told his employer, William Moore, about something he'd seen in Michigan: a counter where everything cost a nickel. Moore ordered $100 ⟨w_counter_order⟩ of goods for one from a wholesaler, Spelman Brothers. Woolworth set out the table. In his own telling, years later, he gave himself more of the credit: I persuaded my employers to create a five cent cash counter with me in charge of it. ⟨w_counter_quote⟩ A correction you'll need, because the story is usually told the other way: Woolworth didn't invent the nickel counter. He ran one, watched what it did, and asked the bigger question. Not what a nickel table could sell. What a whole store could, if every price in it was a nickel.  

**[2:48] UTICA**  
So he tried it. On February 22, 1879 ⟨w_utica_date⟩, Washington's Birthday, he opened the Great Five Cent Store ⟨w_utica_sign⟩ in Utica, New York, with about $300 ⟨w_utica_stock⟩ of goods on credit from Moore. The daily takings fell as low as $2.50 ⟨w_utica_low⟩. Within about 3 months ⟨w_utica_months⟩ he'd sold out and closed, at a profit, by his own account, of $150 ⟨w_utica_profit⟩. Decades later he said what he took from it: One of the first things I learned was that I could not expect people to come to me. I had to take my store to the people. ⟨w_people_quote⟩ He took the lesson to Lancaster.  

**[3:28] THE CHARM OF ONE PRICE**  
Now go back to that Saturday in Lancaster, because now you can see what he'd built. Not a shop with low prices. A shop with one price. A customer didn't have to ask, haggle, compare or calculate. The sign did the selling. As Woolworth put it in 1913 ⟨w_ww_year⟩: The crowd could not get away from that enticing sign, 'Five Cents.' ⟨w_sign_quote⟩ By the next summer he'd added a second price, a dime, and the store became a five-and-ten ⟨w_five_and_ten⟩. He later wrote that it cost him something: As soon as we added 10 cent goods to the line, we took away part of the 5 cent store's charm, the charm of finding only one price on a counter, and only one price in a store. ⟨w_charm_quote⟩  

**[4:18] THE PRICE HE TRIED AND DROPPED**  
And here's a detail the company's own history keeps, which matters for this film. Early on, Woolworth tried a line of goods at a higher price, 25 cents ⟨w_quarter_test⟩. In the company's words, it did not yield satisfactory sales and profits ⟨w_tried_quote⟩. He dropped it. So the ceiling wasn't superstition. It was a test, run once, early, and then not run again for a very long time. Keep that in mind.  

**[4:46] THE CHAIN**  
The machine grew from there. Scranton, November 6, 1880 ⟨w_scranton_date⟩, run by his brother, Sum: the store the company's own history dates the chain from. Then stores run by partners: his cousin Seymour Knox, and Fred Kirby. In 1886 ⟨w_office_year⟩, Woolworth rented desk room in New York for $25 a month ⟨w_office_rent⟩ and did all the buying himself. By 1900 ⟨w_stores_1900_year⟩ he had 59 ⟨w_stores_1900⟩ stores of his own, with the famous carmine red-fronts ⟨w_redfronts⟩. One price, one look, one buyer. You could walk into any of them and know what everything cost before you'd seen any of it.  

**[5:24] CHAPTER — PRICE FIRST**  
Price first.  

**[5:27] THE ARITHMETIC OF A NICKEL**  
Now the mechanism, because it's the opposite of how most businesses set a price. Most start with a cost and add a margin. Woolworth started with the price and worked backwards. His first cost list priced its goods by the gross, 144 ⟨w_gross⟩ items. At a nickel each, a gross brought in $7.20 ⟨w_gross_value⟩. That figure was fixed. It sat over everything like a ceiling. So every line on his first cost list was really the same question: what does a gross cost? Toy dustpans: $4.75 a gross ⟨w_dustpan_cost⟩, which kept about 34% ⟨w_dustpan_margin⟩ of the price. Animal soap: $5.85 a gross ⟨w_soap_cost⟩, keeping about 19% ⟨w_soap_margin⟩. Skimmers and alphabet plates: $2.50 a gross ⟨w_skimmer_cost⟩, keeping about 65% ⟨w_skimmer_margin⟩. The price never changed. The margin changed on every line.  

**[6:16] THE SOAP AND THE SKIMMER**  
Look at what that does to a buyer's mind. The soap barely pays. The skimmer pays handsomely. In a store with one price, the customer doesn't know which is which, and doesn't care. The store has to. So a one-price store isn't simple. It's simple on the outside, and on the inside it's a portfolio: every item carrying a different margin under the same tag, and the buyer's whole job is to keep the average above the line. That's the first thing Woolworth understood. Same tag, different margins. Which means, as we'll see, different best prices.  

**[6:55] THE RING**  
The next thing changed manufacturing. Because the price was fixed, the only way to sell something new was to make it cost less, and Woolworth's buyers went to manufacturers and showed them how. Here's one, as Woolworth himself told it to the trade paper Printers' Ink. A finger ring sold at retail for around 50 cents ⟨w_ring_price⟩. Its maker had sold more than 450 dozen ⟨w_ring_dozen⟩ so far that year. A Woolworth buyer offered to take 5,000 gross ⟨w_ring_order⟩ over the next year. That's 720,000 rings ⟨w_ring_units⟩. And he came with suggestions for making it cheaper. The result: ten-cent gold-filled rings ⟨w_ring_result⟩. The price came first. The product was redesigned to meet it.  

**[7:39] THE VATS**  
Here's another. During the war, a German iron toy that sold for a dime was cut off. An American maker was asked to make it, and said he couldn't do it at the price. The Woolworth buyer looked at how it was made and said this: You can't afford to use brushes. Throw the toys in vats. Dip them. Then you can leave off this little red stripe and this little yellow stripe. ⟨w_vats_quote⟩ The price stayed. The product changed to fit it. When the war shut out a European crochet cotton, the buyers coached an American spinner to make one like it, sold as Woolco ⟨w_woolco⟩, still at a dime a ball. A trade magazine summed up the method in 1930 ⟨w_sm_year⟩: A large quantity order and an improved production system has brought hundreds of higher-priced articles down to ten cents. ⟨w_1930_quote⟩  

**[8:35] THE PRICE WAS THE ADVERTISING**  
And one more thing: the price did the marketing. Printers' Ink put it in a single sentence in 1917 ⟨w_pi17_year⟩: Confining the price of goods to ten cents is fundamentally an advertising idea. ⟨w_pi17_ad⟩ A single price is a promise a customer can remember from the sidewalk. And because the buying was so concentrated, it was enormous. In 1901 ⟨w_tribune_year⟩, the New York Tribune reported that Woolworth imported a larger tonnage of toys and Christmas tree ornaments than all other United States buyers put together.  

**[9:09] PROFIT, NOT GLORY**  
Underneath all of it was one rule, and it's the line from this story worth keeping where you can see it. In a letter to his store managers dated January 14, 1891 ⟨w_general_letter⟩, Woolworth wrote: Profit is what we are working for, not sales or glory. Hold on to that sentence. The rest of this film is about what happens when a price stops serving the profit and starts serving the sign.  

**[9:38] THE CATHEDRAL**  
In 1912 ⟨w_merger_year⟩, Woolworth merged his company with his partners' chains: 596 stores ⟨w_merger_stores⟩. That year the company sold $60.6 million ⟨w_sales_1912⟩. And on April 24, 1913 ⟨w_building_open⟩, President Wilson pressed a button in the White House and 80,000 ⟨w_lights⟩ lights came on in a tower on Broadway: 792 feet ⟨w_height⟩ tall, the tallest building in the world until 1930 ⟨w_tallest_until⟩. It cost $13.5 million ⟨w_cost⟩. It was built without a mortgage, and by 1914 ⟨w_owned_by⟩ Woolworth owned it outright. A minister who saw it called it the Cathedral of Commerce. Woolworth said he built it to advertise his stores all over the world. It was paid for, nickel by nickel and dime by dime, by a price that hadn't moved. So far, the moral writes itself: find the price, hold the price.  

**[10:28] CHAPTER — THE CEILING**  
The ceiling.  

**[10:31] ORTHODOX**  
Then the costs moved. The war in Europe drove up the price of almost everything a five-and-ten ⟨w_five_and_ten⟩ sold, and the big rivals began to sell above the old limit. Woolworth didn't. In May 1917 ⟨w_pi17_date⟩, Printers' Ink wrote: Mr. Woolworth is the only one of the big people in this line who remains strictly orthodox so far as five-and-ten-cent goods are concerned. How long this will continue nobody but Woolworth knows. ⟨w_pi17_orthodox⟩ By the end of that year, the company had 1,000 stores ⟨w_stores_1917⟩.  

**[11:04] HOW TO HOLD A PRICE**  
So how do you hold a price when everything under it costs more? A book on chain stores from 1922 ⟨w_chain_year⟩ described exactly how: Woolworth clung to the old policy by decreasing the units. The size was made smaller, less candy was sold for ten cents, matches which had been one cent a box were five cents; things were sold separately, one stocking for ten cents, the pail ten cents and the cover ten. ⟨w_shrink_quote⟩ Look at the stocking. A pair became one. The price on the tag never moved. What the customer got for it did. Your customers have a name for that today, and it isn't a kind one.  

**[11:48] WHAT IT COST**  
And the margin moved too. Net earnings were 9.43% ⟨w_net_1917⟩ of sales in 1917 ⟨w_1917⟩. In 1918 ⟨w_1918⟩, 5.46% ⟨w_net_1918⟩. To be fair to the record, that year also carried a federal income tax bill of $1.23 million ⟨w_tax_1918⟩ and a reserve set against inventory ⟨w_reserve⟩, so not all of the drop was the dime. But the dime was the one thing the company had chosen not to let move, so every other cost had to land somewhere else: in the size of the product, in the supplier's margin, or in the company's own. By 1919 ⟨w_1919⟩, net earnings were back to 7.89% ⟨w_net_1919⟩. The ceiling had held. Whether holding it was the most profitable choice is a question the company never had to answer, because in the East it didn't try the other one.  

**[12:40] THE WEST**  
And here's the correction most retellings miss. Nothing over a dime was never quite the whole truth. In some districts west of the Rockies, and in Canada, the stores already had a ceiling of 15 cents ⟨w_west_limit⟩. Charlton's western stores, part of the merged company, sold at 5, 10 and 15 cents ⟨w_west_points⟩. So the company was running different ceilings in different parts of the same chain, for years. That's the closest thing in this story to a price experiment. But it wasn't designed as one, and prices compared across places can't tell you much about price, because the places differ in many ways besides the price. Hold on to that. It matters later.  

**[13:25] THE FOUNDER'S DEATH**  
Woolworth died on April 8, 1919 ⟨w_died⟩, at his house on Long Island. By the end of that year the company had 1,081 ⟨w_stores_1919⟩ stores, and it sold $119.5 million ⟨w_sales_1919⟩. And the ceiling had become something more than a policy. It was an identity. In February 1920 ⟨w_parson_date⟩, Printers' Ink reported that the company's president, Hubert Parson, had declared that the company would not under any circumstances even consider breaking away from the ten-cent barrier ⟨w_parson_quote⟩.  

**[13:55] THE STORES GREW OLD**  
For a while, the identity paid. In 1927 ⟨w_1927⟩, each store sold $172,500 ⟨w_store_sales_1927⟩ and made $16,800 ⟨w_store_profit_1927⟩. By 1932 ⟨w_1932⟩, deep in the Depression, each made $8,093 ⟨w_store_profit_1932⟩. Much of that was the Depression. But a store held under a dime couldn't follow its customers to anything that cost more. The price that had once made every store a magnet had become a thing every store had to work around.  

**[14:22] THE TEST**  
And then the company did the right thing, the right way round. In February 1932 ⟨w_test_date⟩, its president said the stores might become '5, 10 and 20 cent stores' ⟨w_new_sign⟩. They didn't switch the whole chain. They tried a 20-cent ⟨w_new_ceiling⟩ line, mostly china and glassware ⟨w_china⟩, in some of their stores, in the West and the South ⟨w_trial_where⟩, first. Then they adopted it. A test, then a rollout. Remember that phrase. It's the most useful one in this whole story.  

**[14:53] WHY THEY MOVED**  
Now look at why, because it's the opposite of the story people tell. The story is that rising prices forced the dime up. In the year it finally moved, prices were falling. The year was 1932 ⟨w_1932⟩, deep in the Depression. The company's own report said that because of lower costs, our selling prices on many lines have been reduced ⟨w_lower_costs_quote⟩. They raised the ceiling while costs were going down. Their reasons: to supply a larger share of what their customers wanted. To end what the report called so-called combination items ⟨w_combination_term⟩, where a thing was sold in pieces to fit under the limit. Their own words: For years we have sold so-called combination items for 10 cents each piece. ⟨w_combination_quote⟩ And competitors without a ten-cent limit ⟨w_rivals⟩ were selling what Woolworth couldn't. The ceiling wasn't protecting anything anymore. It was stopping the company from selling things its customers wanted to buy.  

**[15:52] THE PROMISE**  
And then, having moved the price once, the company made a promise. In a letter to its stockholders dated January 25, 1933 ⟨w_promise_date⟩, it wrote: Fundamentally the Company is in the 5 and 10 cent business and has every intention of continuing that policy. Furthermore, there is no intention of going beyond the 20 cent selling price. ⟨w_promise_quote⟩ In 1935 ⟨w_limits_removed⟩, the board removed all arbitrary price limits. Soon there were goods at 40 cents ⟨w_ceiling_1935⟩. By the spring of 1936 ⟨w_1936⟩, some cost $1 ⟨w_ceiling_1936⟩. The promise didn't last 3 years ⟨w_promise_span⟩.  

**[16:27] WHAT THE DIME TAUGHT**  
So test the moral. Find a price that works and hold it. The dime was brilliant: an advertisement, a discipline on cost, a promise a customer could remember. But the moral is missing a piece. A price that never moves can't tell you what a different price would do. Woolworth knew, to the fraction of a cent, what a gross of soap cost him. What he couldn't know, from inside a ceiling, was what his customers would have paid above it. For decades the company learned a great deal about the cost side of its price, and far less about the demand side, because the demand side only speaks when the price moves. When it finally listened, it did it by testing. And then it promised the new ceiling would hold. A price that's tested once and then held for decades isn't a measurement anymore. It's a memory.  

**[17:27] THE END OF THE STORES**  
The five-and-ten ⟨w_five_and_ten⟩ lasted a long time after that. On July 17, 1997 ⟨w_exit_date⟩, the company announced it was leaving the American Woolworth store business: about 400 stores ⟨w_exit_stores⟩, 9,200 ⟨w_exit_jobs⟩ jobs. A retail consultant told reporters that day: The five-and-dime industry is defunct and has been defunct for at least 25 years. ⟨w_barnard_quote⟩ On November 1, 2001 ⟨w_footlocker⟩, the company renamed itself Foot Locker. The building on Broadway is still standing. The price that built it is gone.  

**[17:57] CHAPTER — YOUR DIME**  
Your dime.  

**[18:00] THE DIME IN YOUR CATALOGUE**  
Now your business. You have a dime. Probably several. A price you set once, for a reason that made sense at the time: a round number, a competitor's price, your cost times a markup, whatever the last product sold for. And it's been working, so you've left it alone. That's what Woolworth's company did for more than 50 years ⟨w_ceiling_span⟩: it worked, so it stayed. And it carries the same blind spot. As long as that price doesn't move, your sales history can't tell you what a different one would do. Not a little. Nothing.  

**[18:38] THE NUMBER YOU'RE MISSING**  
Here's what a price that has moved can tell you. Take one product from the demo catalogue we use for teaching: TH-OVEMIT-22 ⟨el_sku⟩, from Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year. Its price moved across 12 ⟨el_periods⟩ periods of history, and its units moved with it. Plot them on a scale where every step is the same percentage, price across and units a day up, and fit a line. Through this product's own points alone, the line reads -7.35 ⟨el_raw⟩: steep, from very little movement. So the model doesn't trust it alone. It gives the product's own points 17% ⟨el_own_weight⟩ of the weight, lets the rest of the catalogue carry the rest, and lands at -2.74 ⟨el_point⟩. A rise of a given size in the price costs this product about that multiple of it in units. That number has a name: price elasticity.  

**[19:35] WHY A RAISE THAT LOSES UNITS CAN PAY**  
Here's why it matters more than it looks. When you raise a price, the extra lands in your margin almost whole. Your landed cost doesn't change. Most of your fees don't change. Only the ones charged as a share of the price take a cut of it. So a raise that loses units can still make more money, as long as it doesn't lose too many. How many you can afford to lose depends only on how much of each sale you keep after landed cost and fees. How many you will lose is the slope. On this demo catalogue, that's 38.5% ⟨contribution_pre_ads_pct⟩. The gross margin, before fees, is 70.7% ⟨gross_pct_latest⟩. Price off the wrong one and you'll aim at the wrong target. And the slope decides the shape of what comes next. Steeper than minus one, a raise loses a bigger share of units than it adds to the price, so profit rises, peaks and falls: there's a top. Shallower than minus one, a raise loses a smaller share of units than it adds, so profit keeps climbing: no top at all. Remember Woolworth's soap and his skimmers: same price, very different margins, very different answers.  

**[20:53] THE HILL**  
Now picture profit as the price sweeps upward. Every unit you still sell earns more. You sell fewer units. They pull against each other, so for most products profit climbs, flattens, then falls. It's a hill. Its top sits where the slope and the margin put it, but only as sharply as the slope is known. In this demo, for every one of the 22 ⟨pm_no_top⟩ products the model would move, the range on the slope is too wide to mark the top. The honest thing it can say is how far it can't see. Woolworth's ceiling set every product in his stores at the same point on the price axis, whatever its hill looked like. From one price that never moved, there was no way to see any of it.  

**[21:46] THE PRODUCTS THAT REFUSED**  
Here is Woolworth's dime inside a modern catalogue. Across the demo's 24 ⟨n_skus⟩ products, the fit worked on 22 ⟨el_skus_fit⟩. It refused 2 ⟨el_skus_insufficient⟩. Not because those products are special. Because their price never moved enough to draw a line. The rule is plain: the spread of a product's prices, measured against their average, has to reach 2% ⟨el_min_price_cv⟩, across at least 5 ⟨el_min_periods⟩ periods, or the fit says nothing at all. That isn't caution for its own sake. With no movement, there's nothing to measure. Those products are dimes. They might be priced perfectly. Nobody can know, including the person who set the price.  

**[22:26] THE HONEST RANGE**  
And even the products that can be measured come with a range, not a point. That -2.74 ⟨el_point⟩ has an honest interval around it, from -5.85 ⟨el_ci_low⟩ to 0.37 ⟨el_ci_high⟩. It crosses zero ⟨el_ci_crosses⟩. At one end, this product is very sensitive to price. At the other, the estimate can't rule out that price doesn't matter at all. The range comes from the standard error, which is how far another run of periods like these could move the slope, times a multiplier that grows as the periods get fewer. A tool that hands you a single number without the range is telling you something it doesn't know.  

**[23:08] WAITING DOESN'T HELP**  
So why not wait for a better number? Because waiting with the price held still adds nothing at all. That's the dime. And even with the price moving, certainty is slow. To shrink the error on this one estimate to a tight band from its own history would take far more periods than any business will ever have. And the fastest way to narrow it isn't more months. It's more movement: the wider your price has ranged, the tighter the slope. A dime that never moves never narrows at all. So the honest move isn't to wait for certainty. It's to decide under uncertainty, in steps small enough that a wrong one is cheap, and to measure every step.  

**[23:56] THE STEP**  
So how do you step when you can't see the top? Work it out at the estimate, and again at both ends of its range. Where they all agree on a direction, step that way. Where they disagree, step small and measure. And never by much: the demo's model caps any single move at 5% ⟨pm_step_cap⟩, so that a wrong step costs little and a right one shows up in the data. It won't name a destination for any of these products. That's an honest answer. A small step you can measure beats a confident number you can't.  

**[24:36] WHAT A HELD PRICE COSTS**  
So what does a held price cost? On the products that have moved, the model can at least draw a range. On the 2 ⟨el_skus_insufficient⟩ dimes, it can't say anything at all. That's the real cost of a dime. Not a number on a report. A number nobody can know until the price moves.  

**[24:58] WHEN THE PRICE IS THE BRAND**  
And sometimes the price is the brand, the way the dime was. A product sold as a gift under a round number. A line that's always the cheapest, or always the premium one. That's a real asset, and Printers' Ink was right about it: a price can be an advertising idea. But treat it like one. An advertising idea has a cost, and you'd measure any other advertising. Know what holding the line costs you in margin each month, the same way you'd know what a campaign costs, and decide on purpose whether it's worth it. Woolworth's successors held theirs until it stopped them selling what their customers wanted. You can know long before that.  

**[25:44] A TEST, THEN ANOTHER TEST**  
Now go back to 1932 ⟨w_1932⟩, because the company finally did it right: a test, then a rollout. But remember the West. Comparing places tells you about the places as much as the prices, unless the places are picked at random and some are left alone. Most online sellers can't do that: one listing, one price. So the test open to you is in time. A small step, measured against what you wrote down before you took it. Then the next step. Not a test and a promise. A test, then another test.  

**[26:22] WHAT YOU CAN DO THIS WEEK**  
So here's this week. Pick your top products by revenue. For each one, pull its price and units by period, as far back as you have, and divide each period's units by its days. Leave out stockouts, big deals and launches. Check the rule: has the spread of its prices reached 2% ⟨el_min_price_cv⟩ of their average, over at least 5 ⟨el_min_periods⟩ periods? If not, you have a dime. Write it down. For the ones that have moved, fit the line: the log of units a day against the log of price. Read the slope and its range: its standard error, times the multiplier for your number of periods, which the course's spreadsheet gives you. If the estimate itself sits near minus one, the direction is up. If it's clear of minus one, the top is your costs that don't move with price, divided by what the share-of-price fees leave you, times the slope over one plus the slope. Work that out at the estimate and at both ends of the range. Where they agree, step that way; where they disagree, step small. Either way, by no more than 5% ⟨pm_step_cap⟩. Before you take the step, write down the units you expect: today's, times one plus the step, raised to the slope. While it's live, watch your conversion, and on Amazon your Buy Box share; if either drops, reverse the step. When the period ends, add it to the history and fit again. And if no price on the curve makes your margin, the cost is the thing to move, the way Woolworth's buyers moved the ring and the toy.  

**[28:09] THE RETURN**  
$127.65 ⟨w_day1⟩, in nickels, on a Saturday in Lancaster. A ceiling held for more than 50 years ⟨w_ceiling_span⟩. The tallest building in the world, paid for in nickels and dimes. It never told Woolworth what his customers would have paid. Your prices can.  

**[28:26] THE HONEST LIMIT**  
You can do this week's steps by hand for a few products, and it's worth doing. Where it breaks is everything that makes demand messy. Seasons. Your own ads switching on and off. Prices you changed because demand moved, which tilt the line. A competitor's sale the same week. Products that take sales from each other, so a raise on one sells more of another. Products with too little history, which have to borrow strength from the rest of the catalogue, the way this one did. And a range on every estimate that has to become the right size of step for what's still unknown. This is applied mathematics: the same tools actuaries use to price risk. It's what I studied, and it's what Hubricon is built to run, every week, for every product. The whole method, with the spreadsheet, is free at hubricon.com/learn, in the Price Curve course. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The free Price Curve course at hubricon.com/learn. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | still-push on a Shield nickel of the period (Smithsonian National Numismatic Collection, CC0), slow, toward the numeral; archive-framed on an early Woolworth storefront (the Scranton store, about 1880, Wikimedia Commons, public domain), never captioned as Lancaster; unit-grid of {{w_day1_count}} sales filling in ink as the takings rise; number-land on {{w_day1}}; quote card for the letter, attributed "F. W. Woolworth to his father, June 22, 1879". |  |
| 0:50 | archive-framed on the Woolworth Building at night, about 1913 (Library of Congress, no known restrictions), the push toward the lit crown; match-bridge: a single vertical line on a price axis, every item in the store stacked on it, holds still while the era changes and a modern catalogue's own price curves rise around it, labelled Tarnhollow demo data. | demo: Tarnhollow demo data |
| 1:20 | chapter |  |
| 1:23 | still-push on a portrait of Woolworth (Wikimedia Commons, public domain), toward the eyes; still-pan across a Watertown, New York street photograph of the period (Library of Congress, no known restrictions); footage-insert of a dry goods counter's brass scale and paper twine (stock, close, no labels). |  |
| 1:59 | quote card: Woolworth's sentence, verbatim, attributed "The World's Work, April 1913"; footage-insert of a hand setting small tin goods in a row on a wooden counter (stock, hands only, no labels). |  |
| 2:48 | archive-framed on a Utica street scene of the period (Library of Congress, no known restrictions), never captioned as the store; number-pair: the opening day against {{w_utica_low}}, ink; quote card for "I had to take my store to the people", attributed "The World's Work, April 1913". |  |
| 3:28 | still-push on the Scranton store's sign (Wikimedia Commons, public domain) toward its lettering; quote card for the charm, attributed "F. W. Woolworth, as quoted in the company's centennial report, 1979"; still-push on a Seated Liberty dime of the period (Smithsonian National Numismatic Collection, CC0), the second coin landing beside the first. |  |
| 4:18 | doc-highlight on the centennial report's line about the higher-priced goods (Internet Archive), the phrase "did not yield satisfactory sales and profits" underlined in ink; timeline: one early test, then a long empty stretch of years drawn slowly to the right. |  |
| 4:46 | still-pan across the Scranton store photograph (Wikimedia Commons, public domain); archive-stack of early five-and-ten storefronts and a 1908 Charlton store interior postcard (Wikimedia Commons, public domain), landing as the partners are named; timeline of store counts, each landing as spoken. |  |
| 5:24 | chapter |  |
| 5:27 | table-scan typesetting the first store's cost list as the centennial report records it, the cost per gross and the share kept landing row by row, the share kept in blue because it is money; formula-build: a gross, times a nickel, equals {{w_gross_value}}, the ceiling drawn as a hairline across the table. | published: the first store's cost list, as recorded in the company's centennial report (1979) |
| 6:16 | chart-build of the three items as bars of the share kept, all under the same price line, the bars in blue; footage-insert of a bar of plain soap and a tin skimmer side by side on paper (stock, no labels). | published: computed from the first store's cost list, as recorded in the company's centennial report |
| 6:55 | doc-clipping on the Printers' Ink article of April 1919 (Internet Archive, public domain), the ring passage underlined in ink; number-pair: {{w_ring_dozen}} so far that year against {{w_ring_units}} over the next; footage-insert of a plain gilt ring turning on a jeweller's tray (stock, close, no logos). |  |
| 7:39 | quote card: the buyer's words, verbatim, attributed "as told to Printers' Ink, April 1919"; footage-process (wide, medium, detail) of dip-coating small metal parts in a vat (stock, hands only, no logos), screen direction left to right; quote card for the 1930 summary. |  |
| 8:35 | doc-highlight on the Printers' Ink sentence (Internet Archive), ink underline; still-push on a Woolworth store interior at Christmas, about 1910 (Wikimedia Commons, public domain), toward the ornament counter. |  |
| 9:09 | quote card: the sentence, verbatim, attributed "F. W. Woolworth, General Letter to managers, January 14, 1891"; kinetic-thesis: "Profit is what we are working for, not sales or glory." (the act's one thesis line). |  |
| 9:38 | archive-framed on the building under construction, about 1912 (Wikimedia Commons, public domain), then on the finished tower, 1913 (Library of Congress, no known restrictions), the push rising up the facade; number-land on {{w_height}}; still-depth on the tower at night (Library of Congress), the act's hero photograph. |  |
| 10:28 | chapter |  |
| 10:31 | doc-clipping on the Printers' Ink paragraph (Internet Archive, public domain), "strictly orthodox" underlined in ink; still-pan across a row of five-and-ten storefronts of the period (Library of Congress, no known restrictions). |  |
| 11:04 | quote card: the passage, verbatim, attributed "Hayward and White, Chain Stores, 1922"; still-push on a Seated Liberty dime (Smithsonian, CC0), the dime seen differently now: the push ends on the coin's edge, not its face; footage-insert of a single stocking laid flat on paper beside an empty space where its pair would be (stock, no labels). |  |
| 11:48 | chart-build of net earnings as a share of sales across the war years, each bar landing as spoken, the fall in blue, the tax and the reserve annotated in ink beside it; breath on the held chart, the bed dropping out a beat before "didn't try the other one". | published: F. W. Woolworth Co. annual reports (Internet Archive) |
| 12:40 | archive-framed on a western five, ten and fifteen cent storefront of about 1913 (Boulder, Colorado, public library local history, public domain if so marked; else a Seattle Woolworth's of about 1922, Wikimedia Commons, public domain); table-scan: East and West, each with its ceiling, the difference in ink. |  |
| 13:25 | still-push on the National Magazine portrait of Woolworth, July 1919 (Wikimedia Commons, public domain); doc-clipping on the Printers' Ink report about Parson, underlined in ink, attributed as reported speech. |  |
| 13:55 | chart-build of profit per store at the two dates, the fall landing on {{w_store_profit_1932}}, the profit in blue, the Depression marked in ink across the gap; still-pan across a five-and-ten interior of the early nineteen-thirties (Library of Congress, rights confirmed in sourcing), toward a counter of china. | published: The Magazine of Wall Street, November 1936; Time, 1936 |
| 14:22 | doc-clipping on the Southern Textile Bulletin item of March 1932 (Internet Archive, public domain) reporting the trial in some stores, underlined in ink; timeline from the trial to the adoption, each landing as spoken; footage-insert of plain white china cups stacked on a shelf (stock, no marks). |  |
| 14:53 | doc-highlight on the 1932 report to stockholders (Internet Archive), "because of lower costs" underlined in ink; footage-insert of a pail and its lid set apart on a table, then pushed together (stock, no labels). |  |
| 15:52 | quote card: the promise, verbatim, attributed "F. W. Woolworth Co., report to stockholders, January 25, 1933"; doc-highlight on "no intention of going beyond", ink; timeline: the ceiling stepping up, each step landing as spoken. |  |
| 16:27 | still-push on the dime, the third and last time in the archive, the push ending on the date; kinetic-thesis: "A price that never moves can't tell you what a different price would do."; breath, the bed rising under the held line. |  |
| 17:27 | footage-establish on a lower Manhattan street at morning, the Woolworth Building's crown in the frame (stock, no signage legible); quote card for Barnard, attributed "July 1997"; still-push on the tower, 1913 (Library of Congress), the same frame as the cathedral beat. |  |
| 17:57 | chapter |  |
| 18:00 | formula-build: cost, times markup, a glance at the competitor, a round number, each term landing as spoken, the result stamped as a single price; footage-insert of a price label printing and being pressed onto a shelf edge (stock, no brand), the modern dime. |  |
| 18:38 | chart-build of the demo product's history on log scales, the points landing period by period, drawn from the fit's own points with units divided by days, then the steep line through them, then the line pulled toward the catalogue's as "the rest of the catalogue" is spoken, the slope labelled, Tarnhollow demo data on the figure. | demo: Tarnhollow demo data, ELASTICITY.FIT |
| 19:35 | formula-build: a dollar added to the price, the share-of-price fees taking their cut, the rest landing in the margin in blue; number-pair: {{contribution_pre_ads_pct}} against {{gross_pct_latest}}, labelled Tarnhollow demo data; chart-build returning to the soap-and-skimmer bars. | demo: Tarnhollow demo data, MARGIN.DECOMP |
| 20:53 | chart-build of profit hills for the demo products, each drawn as a band whose top smears across the axis while the price axis marked where each band's top could be, labelled Tarnhollow demo data; then a single vertical line at one price cutting through all of them. | demo: Tarnhollow demo data, ELASTICITY.FIT and PRICE.OPTIMUM |
| 21:46 | unit-grid of the demo's {{n_skus}} products, the fitted ones in ink, the refused ones left as hollow outlines, each landing as spoken; still-push on the dime, cut in as a single insert on "Those products are dimes". |  |
| 22:26 | range-band on the demo product's fit, the band opening from the line to the full interval as "range" is spoken, the ends labelled, the zero line marked where the band crosses it, Tarnhollow demo data. | demo: Tarnhollow demo data, ELASTICITY.FIT |
| 23:08 | number-pair: {{el_periods}} periods held against {{n_for_se_tenth}}, the long one running off the edge of the paper; range-band narrowing as the price's spread widens, not as the months pass, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, ELASTICITY.FIT |
| 23:56 | counterfactual on the demo product's profit band: the top worked out at the estimate and at both ends of the range, three marks on the price axis, the current price as the hollow dot and a small step as the solid dot, the step's size in blue, Tarnhollow demo data. | demo: Tarnhollow demo data, PRICE.OPTIMUM |
| 24:36 | range-band of every fitted demo product's interval drawn side by side, then the {{el_skus_insufficient}} refused products at the end as empty outlines with no band at all, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, PRICE.OPTIMUM |
| 24:58 | doc-highlight on the Printers' Ink sentence, the same page as the advertising beat; formula-build: the margin a held price gives up each month, set beside a campaign's monthly spend, as terms only, no figures. |  |
| 25:44 | split-then-now: the {{w_1932}} trial stores on a map of the West and South, then a single demo product's price stepping over time with its predicted and measured units drawn together, labelled Tarnhollow demo data; timeline of steps, each landing as spoken. | demo: Tarnhollow demo data |
| 26:22 | formula-build listing the steps as terms, each landing as spoken, the best-price formula built term by term; receipt: one demo product's line, its price spread, its slope and range, the step and the prediction written before it, labelled Tarnhollow demo data. | demo: Tarnhollow demo data |
| 28:09 | still-push resuming on the cold open's coin in the same framing, then the modern price label on a shelf edge in the same framing; kinetic-thesis: "It never told Woolworth what his customers would have paid.". | published: the Lancaster takings, as recorded by the Woolworths Museum and the company's centennial report |
| 28:26 | range-band on the demo catalogue's fits, every product's interval drawn at once, the band holding while the voice names what it takes, labelled Tarnhollow demo data; end card at "hubricon.com/learn". | demo: Tarnhollow demo data, ELASTICITY.FIT |

### Decide

```
hubricon-content approve greats-02-the-dime
hubricon-content reject  greats-02-the-dime --note "what to change"
```
Edit `content/videos/greats-02-the-dime/script.md` first if you prefer; it is re-validated on approve.

## G03 · series · tier D · pillar 2 — script gate

**Title:** The Grocer Who Cornered Wall Street, and the Date That Took His Company  
**Thumbnail:** The early Memphis turnstile photograph, the push ending on the turnstile's arm; September 1, 1923 ⟨p_pool_date⟩ set beside it in blue  
**Spiky claim:** A business doesn't fail on the day it stops making money. It fails on the first day it can't pay a bill that has a date on it, and that day can arrive in its most profitable year.  
**Misconception:** If the business is profitable and worth more than it owes, the cash will take care of itself.  
**CTA:** The free Capital & Cash course at hubricon.com/learn, then the one soft close.  
**Estimated runtime:** about 27 min 32 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. September 1, 1923 ⟨p_pool_date⟩. That was the deadline for the $2,500,000 ⟨p_pool_due⟩ Clarence Saunders owed. He said he owned nearly every Class A share of a profitable grocery chain. He couldn't turn enough of it into cash in time, and he lost the company.
2. $124 ⟨p_peak⟩ a share, up from $75.50 ⟨p_open⟩ at the open. That spring a grocer from Memphis cornered Wall Street. By August he had resigned from his own company, and his stores were still selling groceries.
3. $653,058 ⟨p_net_1922⟩. That's what the Piggly Wiggly stores made the year before their founder lost them. What he couldn't meet was a payment with a date on it, and your business keeps the same kind of calendar.

### Script

**[0:00] COLD OPEN**  
At about 11 a.m. ⟨p_corner_time⟩ on Tuesday, March 20, 1923 ⟨p_corner_date⟩, a man in Memphis sent a telegram to New York and fired his Wall Street operator, Jesse Livermore. Then he called for delivery of 42,000 shares ⟨p_called⟩ of a grocery company's stock. The man was Clarence Saunders, who had built Piggly Wiggly. On the floor of the New York Stock Exchange, the stock opened at $75.50 ⟨p_open⟩. Before the close it touched $124 ⟨p_peak⟩. A newspaper wrote: Fully one-third of the brokers on the floor were crowded about the Piggly Wiggly post. ⟨p_floor_quote⟩ Saunders said he had bought 198,872 ⟨p_claimed⟩ of the 200,000 ⟨p_total_shares⟩ Class A shares. He had cornered Wall Street. By August he had resigned from his own company, and his stores were still selling groceries.  

**[0:49] THE QUESTION**  
So how does a man who says he owns nearly all of a profitable company lose it in a matter of months? Not to a competitor. Not to a bad idea: walking the aisles and serving yourself is how almost everyone shops now. The stores kept selling groceries the whole time. So what took it? There's a version of the answer in your business, and this film is going to find it.  

**[1:18] CHAPTER — THE TURNSTILE**  
The turnstile.  

**[1:21] THE GROCER**  
Saunders was born in 1881 ⟨p_born⟩, in Amherst County, Virginia, to a poor family that farmed tobacco. In 1896 ⟨p_palmyra_year⟩ he went to work in a general store in Palmyra, Tennessee. From there he went into the wholesale grocery trade, and in time to Memphis, where he worked for wholesalers. So he knew groceries from the supply side: what the stores bought, and what they paid for it.  

**[1:48] HOW A GROCERY WORKED**  
Here's how most grocery stores of the time worked. The goods sat behind a counter. You told a clerk what you wanted. The clerk walked to the shelf, fetched it, wrapped it, and came back. Every item in every order passed through somebody's hands, and the store paid for those hands on every sale, busy day or quiet one. It worked. It was slow, and every sale paid for a clerk's time.  

**[2:18] THE IDEA**  
The idea, by the account in the National Register, came to him in 1915 ⟨p_idea_year⟩. Let the customer walk among the goods and take them herself. In September 1916 ⟨p_open_month⟩ he opened the first Piggly Wiggly, at 79 Jefferson ⟨p_address⟩, in Memphis. As a historian of the company tells it in the Tennessee Historical Quarterly ⟨p_opening_account⟩, he staged the opening like a fair: a brass band, flowers and balloons for the children, and a stunt with gold coins for the women. And the staff, that same account says, politely refused to select merchandise for visitors. The customers would serve themselves. By the end of that year there were 9 ⟨p_stores_1916⟩ Piggly Wiggly stores in Memphis.  

**[3:02] THE TURNSTILE**  
Look at how the store was built, because the design did more than one job. The company's own description, filed with the New York Stock Exchange, says each store had a turnstile that customers passed through on entering. Then they moved through a system of aisles, one after another, and paid at a cashier's counter on the way out. A standard store needed three or four ⟨p_staff⟩ employees. And the filing says this: Over 100 customers can conveniently make their purchases at one time. ⟨p_capacity_quote⟩ So the first job was cost: fewer hands per sale. The second job is in the patent. The point of the layout, it says, is that the customer will be enabled to serve himself and, in so doing, will be required to review the entire assortment of goods carried in stock. Every shopper walked past every shelf. The design that cut the cost of a sale also put every product in front of every buyer.  

**[4:06] NOT THE FIRST**  
The patent, number 1,242,872 ⟨p_patent_no⟩, was granted on October 9, 1917 ⟨p_patent_date⟩. And here's the correction you'll want, because the story usually says he invented the supermarket. A federal court in 1924 ⟨p_court_year⟩, in a case Saunders' own old company brought against him, found that self-serving stores have long been in existence. Lisa Tolbert's history of self-service, Beyond Piggly Wiggly ⟨p_tolbert⟩, calls Piggly Wiggly the most influential of them, and neither the first nor the only. That's a fair verdict. It wasn't the first. It was the one that spread.  

**[4:41] CHAPTER — THE MACHINE**  
The machine.  

**[4:44] SELLING THE IDEA**  
How it spread is a lesson in its own right. On September 9, 1918 ⟨p_sale_date⟩, Saunders sold the business, the Piggly Wiggly name and the patent to a new company, Piggly Wiggly Corporation, for $550,000 ⟨p_sale_cash⟩ in cash and 15,000 shares ⟨p_sale_shares⟩. That company licensed the system to independent grocers all over the country, for a fee and a royalty of a fraction of 1% ⟨p_royalty⟩ of their gross sales. Another company, Piggly Wiggly Stores, Incorporated, formed in 1919 ⟨p_stores_inc_year⟩, ran stores of its own. So the business was split: one company owned the idea and rented it out, and another ran the stores. Hold on to that, because both of them come into the corner.  

**[5:29] THE BUSINESS WAS WORKING**  
And the stores company was working. On March 31, 1922 ⟨p_mar31_1922⟩, by its own filing, it ran 347 ⟨p_stores_1922⟩ stores with about 2,500 ⟨p_staff_1922⟩ employees. On May 3, 1922 ⟨p_listing_date⟩ it applied to list its Class A stock on the New York Stock Exchange: 200,000 ⟨p_total_shares⟩ shares, including 50,000 ⟨p_new_shares⟩ new ones offered to its stockholders at $43 ⟨p_new_price⟩. They were oversubscribed. And the money went, in the filing's words, for the retirement of all existing bank loans. The numbers were improving, too. Sales were $30.2 million ⟨p_sales_1921⟩ in 1921 ⟨p_1921⟩, with $208,662 ⟨p_net_1921⟩ of profit. In 1922 ⟨p_1922⟩, $31.5 million ⟨p_sales_1922⟩, and $653,058 ⟨p_net_1922⟩ of profit. The company paid $550,000 ⟨p_div_1922⟩ in dividends. By Saunders' count the following March, there were 1,241 ⟨p_ad_stores⟩ Piggly Wiggly stores, of every owner, in 41 states and Canada ⟨p_ad_states⟩, and his company owned 659 ⟨p_owned⟩ of them.  

**[6:21] A CASH BUSINESS**  
Notice what kind of business that is. A grocery's customer pays at the counter on the way out, so the money is in the till the day the goods leave the shelf. Groceries don't sit on the shelf for long. A store like that is about as close to a cash machine as retail gets. It had raised money to pay off its bank loans. It was profitable and growing. If you were going to pick a business that couldn't run out of cash, you might well have picked this one.  

**[6:58] CHAPTER — THE CORNER**  
The corner.  

**[7:01] THE RAID**  
In November 1922 ⟨p_raid_month⟩, some independent Piggly Wiggly licensees in the East failed. They had nothing to do with Saunders' own stores company, but the stock fell anyway, to around $39 ⟨p_low_1922⟩, from above $50 ⟨p_before_raid⟩ before the failures. And professional traders began to sell it short. Here's what that means, because the rest of the story depends on it. A short seller borrows shares he doesn't own and sells them, planning to buy them back later, cheaper, and return them. If the price falls, he profits. If the price rises, he loses. And if he can't find anyone to sell him the shares back at all, he's cornered: he has promised to deliver something that only one person has.  

**[7:48] SAUNDERS BUYS**  
Saunders decided to buy. In a single day that month, a St. Louis paper reported later, he raised a little more than $1,000,000 ⟨p_stl_raised⟩ from 40 St. Louisans ⟨p_stl_people⟩ who were to share in any profits. In December 1922 ⟨p_livermore_date⟩ he hired Jesse Livermore to buy, sell and lend the stock for his account. A correction here, too, because you'll read it the other way: Livermore wasn't one of the short sellers. He was Saunders' own operator, and he said publicly that he'd never traded the stock for himself.  

**[8:23] WHERE THE MONEY CAME FROM**  
And the buying took money. A manager of one of the Missouri Piggly Wiggly companies put it plainly: Mr. Saunders in all raised about $10,000,000 ⟨p_raised⟩ for his fight. It came from a pool of investors in the South and St. Louis, promised a share of the profits, and from banks, and the loans were secured on the stock itself. And there was company money in it. Look at Piggly Wiggly Corporation's balance sheet. Its cash at the end of the year: $967,016 ⟨p_corp_cash_before⟩. By the end of June: $22,724 ⟨p_corp_cash_after⟩. Over the same months, its holdings of the stores company's stock went from $1,223,372 ⟨p_corp_stock_before⟩ to $2,446,147 ⟨p_corp_stock_after⟩. The company's cash had become the company's stock.  

**[9:09] THE INSTALMENT PLAN**  
Then he took the fight to the public. He offered shares at $55 ⟨p_offer_price⟩: $25 ⟨p_down⟩ down, and three notes of $10 ⟨p_notes⟩, which the buyers would pay on June 1, September 1 and December 1, 1923 ⟨p_note_dates⟩. He bought whole newspaper pages to sell it. One began: Shall the Gambler Rule? On a high horse he rides. Bluff is his Coat of Mail, and thus shielded is a yellow heart. Another headline read A Million People Buy From Piggly Wiggly Every Day ⟨p_partners_quote⟩. The Exchange objected to what it called two markets at widely different prices ⟨p_two_markets⟩. Meanwhile the stock climbed: $55.25 ⟨p_jan_low⟩ at its January low, about $69 ⟨p_mar1⟩ on the first of March, and as high as $79.50 ⟨p_mar12⟩ by the middle of the month.  

**[9:57] CORNER DAY**  
Now the day itself, slowly. On Monday the stock closed at $72 ⟨p_mar19⟩. On Tuesday morning Saunders fired Livermore and called for his shares. The short sellers now had to deliver stock they didn't have, and almost nobody but Saunders had any to sell. The price opened at $75.50 ⟨p_open⟩ and ran to $124 ⟨p_peak⟩. By the close it was back at $82 ⟨p_close⟩. That evening, the Exchange's committee suspended dealings in the stock. Its resolution added a sentence: this action was taken after conference with the counsel of Piggly Wiggly Stores, and meets with his approval.  

**[10:35] THE PRICE OF A SHARE YOU MUST HAVE**  
The next day, Saunders named his price. $150 ⟨p_demand⟩ a share by the following afternoon, he said, or $250 ⟨p_demand_later⟩ after that. He told the Associated Press: A razor to my throat, figuratively speaking, is why I suddenly without warning kicked the pegs from under Wall street. ⟨p_razor_quote⟩ On Thursday, March 22 ⟨p_delisted⟩, the Exchange struck the stock from its list. It gave its reason: such a concentration of holdings as to make impossible a free market for the stock. And it moved the delivery deadline to 2:15 in the afternoon on Monday, March 26 ⟨p_deadline⟩, to give sellers whose stock was coming from distant points time to get it. Here the record splits. The Exchange said Saunders' own attorney had asked for that Monday. Saunders said he never agreed to any postponement. You can read both statements. Nobody has settled it.  

**[11:31] THE SETTLEMENT**  
The extra days were enough. On Friday Saunders offered to supply the shares himself, at $100 ⟨p_settle⟩ each, until that afternoon, and most of the short sellers took it. By Saturday noon only about 4,000 shares ⟨p_left_sat⟩ were still owed. On Monday every delivery was made. The Exchange published its review: Mr. Saunders has received all of the stock at the prices he contracted for it, and is in exactly the same position in all respects as though the stock had been delivered to him on March 21. ⟨p_nyse_review⟩ Saunders had his own summary: Wall Street got licked and then called for 'mamma,' the New York Stock Exchange, to help, and, of course, 'mamma' heard the cry of her petted child. ⟨p_mamma_quote⟩ And one more number, from the Exchange's own count: only 11,200 shares ⟨p_clearing⟩ had been deliverable through its clearing house that Wednesday. The squeeze was real. It was smaller than the headlines.  

**[12:31] THE TURN**  
Now look at what he was holding. By his own count, nearly every Class A share. The stock had no exchange to trade on, because the Exchange had removed it. His loans were secured on that stock, and his lenders wanted cash. On paper he was rich: that summer he put his assets at $11 million ⟨p_assets_claimed⟩, against debts the newspapers estimated at about $5,000,000 ⟨p_total_owed⟩. In cash, he had whatever he could sell the stock for, and he had become the only big holder there was. A corner is a trap that closes on both sides. The short sellers couldn't buy. Saunders couldn't sell.  

**[13:13] CHAPTER — THE DATE**  
The date.  

**[13:16] THE CALENDAR**  
So here is the calendar he lived on that year. On one side, money that might come in: the public still owed on its notes, due June 1, September 1 and December 1, 1923 ⟨p_note_dates⟩, but only if the buyers kept paying for a stock that no longer traded. On the other side, money he had to pay. The pool that had financed the corner required $2,500,000 ⟨p_pool_due⟩ before September 1, 1923 ⟨p_pool_date⟩. The Associated Press, that August: The $2,500,000, which the pool required that he pay before Sept. 1 was understood to total approximately half of his obligations. ⟨p_half_quote⟩ And Piggly Wiggly Corporation, the company that owned the idea, had $965,000 ⟨p_corp_notes⟩ of notes due on December 1, 1923 ⟨p_corp_notes_due⟩, against cash, at the end of June, of $22,724 ⟨p_corp_cash_after⟩. None of these dates cared what the stock was worth. Each of them wanted cash.  

**[14:12] THE STORES, MEANWHILE**  
And the stores company was no longer the cash machine it had been. Its own balance sheet at the end of June shows it. Cash: from $841,064 ⟨p_si_cash_before⟩ at the start of the year to $391,267 ⟨p_si_cash_after⟩. Merchandise on hand: from $3.44 million ⟨p_si_merch_before⟩ to $2.17 million ⟨p_si_merch_after⟩. Its surplus of $407,007 ⟨p_si_surplus_before⟩ had turned into a deficit of $477,975 ⟨p_si_deficit_after⟩. Saunders said the stores lost approximately $100,000 ⟨p_july_loss⟩ from operations in July. The record doesn't say why in so many words. It does say that the company in the middle of the fight was shrinking while its founder's debts came due.  

**[14:51] AUGUST**  
On August 12, 1923 ⟨p_aug⟩, Saunders resigned as president of Piggly Wiggly Stores. He explained himself to the Associated Press. He had offered, he said, to settle with all pool interests by full payment in stock at the cost price to the pool, as I am unable to get cash on this stock. They turned it down. He offered the lenders the asset. The lenders wanted the cash. And he said what he expected: that he would lose every nickel he had, even his home, as he had saved nothing outside in anybody else's name. J. C. Bradford, of Nashville, became president. On August 17, 1923 ⟨p_corp_resign⟩, Saunders resigned from Piggly Wiggly Corporation too.  

**[15:36] DETROIT**  
There was a last attempt. At a receivership hearing on September 21, 1923 ⟨p_ford_date⟩, Saunders testified that the governor of Tennessee, Austin Peay, and Colonel Luke Lea had gone to Detroit to ask Henry Ford for help, and had failed to get an interview. A receiver was named for the stock he had pledged. On February 23, 1924 ⟨p_bankrupt⟩, he filed for bankruptcy. He had said, that August: I have lost my business and my money, but I have gained knowledge and on that knowledge I will attempt to build up another fortune.  

**[16:13] THE PINK PALACE**  
There was a house, too. In 1922 ⟨p_palace_begun⟩ he had begun a mansion in Memphis, faced in pink Georgia marble. He told the architect to spare no expense. His plans for its interior were never completed, and he never lived in it. It passed to his creditors that summer. A development company bought it, and in August 1926 ⟨p_palace_donated⟩ gave it to the city. In 1930 ⟨p_palace_museum⟩ it opened as a museum. One more correction, because the story is often told the generous way: Saunders didn't give his house to Memphis. His creditors took it, and somebody else gave it.  

**[16:52] AFTER**  
The court kept him from using the Piggly Wiggly methods, but not his own name. So by 1929 ⟨p_cs_year⟩ he was back, with 400 ⟨p_cs_stores⟩ Clarence Saunders stores in 225 towns and cities in 18 states ⟨p_cs_towns⟩, the chain he called Sole Owner of My Name. It failed in the Depression. Time magazine summed up his career with a line worth remembering: Mr. Saunders discovered that Wall Street has a cemetery at one end and a river at the other. He died in Memphis in 1953 ⟨p_died⟩. The idea did better than the man. Piggly Wiggly had 1,331 ⟨p_pw_1924⟩ stores in the spring after his bankruptcy, and by one count about 2,660 ⟨p_pw_1932⟩ at its peak.  

**[17:37] WHAT THE CORNER TAUGHT**  
So what did the corner teach? Not that ambition is dangerous. The lesson is narrower and more useful than that. Money asks a business more than one question, and the answers differ. The first is: am I worth more than I owe? Saunders could say yes. The second is: will the cash be there on the day each payment is due? Before September 1, 1923 ⟨p_pool_date⟩, the answer was no. He measured his position by what his stock was worth. His lenders measured it by what it would pay on a date. The second measure is the one that ends businesses, and it's the one a profit and loss statement never shows.  

**[18:22] CHAPTER — YOUR CALENDAR**  
Your calendar.  

**[18:25] YOUR CORNER**  
Now your business. You probably haven't cornered anything. But if you sell physical products, you own an asset you can't spend until it sells: inventory. And you owe money on dates other people set. A supplier's wire. Payroll. Rent. A tax payment. A card bill. A loan. Let's see what a calendar like that does to a healthy business.  

**[18:50] IS IT SAFE?**  
Let's do it on a real-shaped example. The demo catalogue we use for teaching: Tarnhollow ⟨demo_brand⟩, demo data ⟨demo_label⟩, 24 ⟨n_skus⟩ products. Last month it made $102,864 ⟨net_latest⟩ of net profit on $318,632 ⟨rev_latest⟩ of revenue. It starts today with $262,000 ⟨cash_on_hand⟩ in the bank, which is more than 8 months ⟨cash_months⟩ of its fixed costs, and it carries $31,500 ⟨monthly_fixed_costs⟩ a month of them. So, before we draw anything: how big a single bill could this business pay in the next 90 days ⟨horizon_days⟩ without bouncing it? Most operators would look at the $262,000 ⟨cash_on_hand⟩ and name something close to it. Hold your number.  

**[19:28] THE TROUGH**  
We ran its next 90 days ⟨horizon_days⟩ as 10,000 ⟨n_paths⟩ different futures, each with its own demand. In the middle of them, it ends the horizon at $336,443 ⟨end_p50⟩, higher than it starts. But on the way, the balance falls to $85,242 ⟨min_median⟩, 13 days ⟨min_p5_day⟩ into the horizon. Here's why. As the horizon opens, 10 ⟨day0_wire_count⟩ supplier wires leave, $130,622 ⟨day0_wires_total⟩ in all, before a single sale from this month can pay. Goods take about 40 days ⟨lead_time_typical⟩ to arrive and be sellable. And the platform pays out every 14 days ⟨payout_cycle⟩, on sales it has already held for a while. Cash goes out for stock before the stock sells, and comes back in after it sells. In between, there's a bottom. Nobody chose that bottom. It fell out of when the wires were set to leave.  

**[20:20] THE CLOCKS**  
Count it the way the course does, clock by clock. A dollar that leaves for your supplier is gone for the time it takes the goods to arrive and be sellable, plus the time the average unit then waits on the shelf, plus the time from a sale until the money is in your bank. Subtract whatever credit your supplier gives you. That's how long each dollar is away. On this catalogue the goods take about 40 days ⟨lead_time_typical⟩ to land, and the supplier is paid in full when the order is placed. The shelf time depends on how much each order covers, so it differs product by product. A sale here reaches the bank about 21 days ⟨sale_to_cash_days⟩ after it's made: 10 days ⟨sale_payable_days⟩ until the platform can pay it, then the wait for the next settlement, and 4 days ⟨bank_transit_days⟩ at the bank. Every day you add to that count is a day of sales you have to fund before you see a cent of them.  

**[21:27] THE SAME ON EVERY PATH**  
And here's the part that should make you sit up. Across those 10,000 ⟨n_paths⟩ futures, each with its own demand, the low point is the same on every one ⟨trough_every_path⟩ of them: $85,242 ⟨min_median⟩, 13 days ⟨min_p5_day⟩ into the horizon. It falls the day before the next payout lands, which the model sets a full cycle away, the cautious case, because a seller's settlement date isn't on file. So nothing a customer does in those days can move it. The wires have already left. The trough was decided when the orders were placed.  

**[22:03] SAUNDERS' SEPTEMBER**  
Now give this healthy catalogue a Saunders problem. A payment a little more than $85,242 ⟨min_median⟩, due on that day. A loan instalment, a tax bill, a deposit on a new order. On every one of those 10,000 ⟨n_paths⟩ futures, the balance goes negative. Not on the bad ones. On all of them. Move the same payment to the horizon's last day, and on all but the worst twentieth of those futures it comes out of a balance above $323,149 ⟨end_p5⟩. Same business. Same profit. Same amount. A different date. That's the whole lesson of September 1, 1923 ⟨p_pool_date⟩, in a modern catalogue. So, your number. A single bill of more than $85,242 ⟨min_median⟩, landing on that day, would have bounced. Not $262,000 ⟨cash_on_hand⟩. It was safe, by far less than it looked. Your profit is a statement about a month. Your cash is a statement about a day. They're different numbers, and the cash is the one with a date on it.  

**[23:06] VALUE IS NOT CASH**  
And notice the other side of Saunders' trap: an asset worth a lot that couldn't be turned into cash by the date. Inventory is that asset, in miniature. On your books, stock is worth what you paid for it. On a date, it's worth what it will sell for by then, after the platform's cut and the payout's wait. Over these 90 days ⟨horizon_days⟩, this catalogue turns $349,342 ⟨wires_total⟩ of cash into stock. Every dollar of it is worth something. None of it pays a bill until it sells and the payout lands.  

**[23:43] WHY RULES OF THUMB MISS IT**  
You've heard the usual rule: hold a few months of expenses in the bank. This catalogue holds more than 8 months ⟨cash_months⟩ of its fixed costs, far more than the rule asks. And still, between today and the trough, its cash falls $176,758 ⟨cash_drop⟩. That's more than 5 months ⟨cash_drop_months⟩ of fixed costs, gone in under a fortnight, in a month when nothing at all goes wrong. Start this same business with less than $176,758 ⟨cash_drop⟩ in the bank, and that same calendar takes it into the red on every path. The rule is measuring the wrong thing. The drop isn't driven by rent and payroll. It's driven by the wires, and by when they leave relative to when the money comes back.  

**[24:31] WHAT MOVES THE BOTTOM**  
So what moves the trough? Every lever is a date. When a wire leaves: a deposit now and the balance on shipment, instead of everything up front. How big each order is: smaller, more frequent orders make the bottom shallower, and cost more per unit and per shipment. How long a supplier lets you pay: every day of credit is a day the money stays in your account. When you reorder: a reorder that goes out late saves cash today and buys a stockout later. And the payout schedule you're on. Each of those moves the bottom up or down, and each of them has a price. Choosing among them is the real work of running cash.  

**[25:19] WHAT YOU CAN DO THIS WEEK**  
So here's this week. List every payment that leaves your account in the next 90 days ⟨horizon_days⟩, on the day it actually leaves: supplier wires, payroll, rent, tax, card bills, loan payments. List every payment that comes in, on the day it actually lands. For a platform payout, that's not the day of the sale. Date it from the day the platform can pay the sale, then the next settlement, then the bank. Draw your balance, day by day. Find the lowest point, and its date. Then ask Saunders' question: what single payment, due on that day, would break me? If the answer is a number you could plausibly owe, move something now. Split a wire. Ask a supplier for a different date. And hold enough that your lowest day still clears a floor you choose. Keep your buffer above the trough, not above the average.  

**[26:17] THE RETURN**  
A turnstile in Memphis. A corner in New York. And a payment with a date on it. Saunders said he'd lost his business and his money, but gained knowledge. You can have the knowledge without paying his price. Find your date.  

**[26:34] THE HONEST LIMIT**  
You can draw this week's calendar by hand for one path, and it's worth doing. Where it breaks is that one path isn't the future. On this catalogue the bottom came before any sale could pay. On yours, a wire that leaves after a payout puts demand into the bottom, and then it's a range. Demand varies, and products tend to have their bad months together. Lead times slip. Every reorder decision changes a wire, and every wire changes the trough. A real catalogue has dozens of products, each on its own calendar, and the question isn't what happens on the expected path. It's how deep the bottom goes on the bad ones. And how likely you are to hit it. Answering that honestly means simulating thousands of futures. Then reading the bottom of each one, averaging the worst twentieth of those bottoms, and holding enough that the average still clears your floor. This is applied mathematics: the same tools actuaries use to price risk. It's what I studied, and it's what Hubricon is built to run, every week, for every product. The whole method, with the spreadsheet, is free at hubricon.com/learn, in the Capital and Cash course. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  
*CTA:* The free Capital & Cash course at hubricon.com/learn. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | still-push on the 1918 Memphis photograph of a Piggly Wiggly interior with two turnstiles (Library of Congress, no known restrictions), slow, toward the turnstile's arm; doc-clipping on the Chronicle's report of the day's prices (Internet Archive, public domain), {{p_open}} and {{p_peak}} underlined in ink; number-land on {{p_peak}}; still-push on the Bain portrait of Saunders (Library of Congress, no known restrictions). |  |
| 0:49 | still-pan across the 1917 photograph of the store's shelves (Library of Congress, no known restrictions); match-bridge: a single line of cash falling and refilling across a calendar holds still while the era changes, the 1923 dates becoming a modern catalogue's supplier wires, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 1:18 | chapter |  |
| 1:21 | still-pan across a Memphis street of the period (Library of Congress, no known restrictions), toward a wholesaler's loading door; footage-insert of sacks and crates on a wooden loading floor (stock, no labels). |  |
| 1:48 | archive-framed on a counter-service grocery interior of the period (Library of Congress, no known restrictions), the clerk behind the counter; footage-insert of a hand wrapping a parcel in brown paper and string (stock, hands only). |  |
| 2:18 | archive-framed on the 1917 entrance photograph, the turnstile with its small wicker baskets (Library of Congress, no known restrictions), the push toward the baskets; footage-insert of a wicker basket being lifted from a stack (stock, hands only, no labels); number-land on {{p_stores_1916}}. |  |
| 3:02 | doc-highlight on the patent's sheet of drawings, the aisles traced in ink in the order a customer walks them (US patent, public domain); doc-highlight on "required to review the entire assortment of goods carried in stock", ink; still-push on the 1918 check-out counter photograph (Library of Congress, no known restrictions) toward the cash registers. |  |
| 4:06 | doc-highlight on the patent's first page (Google Patents scan, public domain), the number and the date in ink; doc-clipping on the court's sentence, underlined in ink, attributed "Piggly Wiggly Corp. v. Saunders, 1924"; quote card for Tolbert's phrase, attributed "Lisa Tolbert, Beyond Piggly Wiggly, 2023". |  |
| 4:41 | chapter |  |
| 4:44 | formula-build: the business, the name and the patent on one side, {{p_sale_cash}} and {{p_sale_shares}} on the other, the cash in blue; table-scan of the two companies, side by side, what each owned and what each did, landing as spoken. |  |
| 5:29 | doc-highlight on the listing statement's line about the bank loans (Internet Archive, public domain), ink; chart-build of sales and net profit for the two years, the profit landing in blue as spoken; unit-grid of {{p_ad_stores}} stores with the company's own {{p_owned}} filled in ink. | published: the Commercial & Financial Chronicle, June 17, 1922 and February 24, 1923 |
| 6:21 | still-push on the 1918 check-out counter photograph, toward a cash register's drawer; footage-insert of coins dropping into an old till drawer (stock, close, no marks). |  |
| 6:58 | chapter |  |
| 7:01 | doc-clipping on a newspaper report of the eastern receivership (Library of Congress, Chronicling America, public domain), underlined in ink; formula-build: borrow the shares, sell them, buy them back, return them, each step landing as spoken, the profit or loss in blue; number-pair: {{p_before_raid}} against {{p_low_1922}}. |  |
| 7:48 | doc-clipping on the St. Louis Post-Dispatch front page of March 22, 1923 (Internet Archive, public domain), the fundraising sentence underlined in ink; quote card for Livermore's statement, verbatim, attributed "Jesse L. Livermore, March 20, 1923". |  |
| 8:23 | quote card: the manager's sentence, verbatim, attributed "George H. Wearen, St. Louis Post-Dispatch, March 22, 1923"; doc-highlight on the Corporation's balance sheet in the Chronicle (Internet Archive, public domain), the cash lines and the stock lines underlined; number-pair: {{p_corp_cash_before}} against {{p_corp_cash_after}}, the cash in blue. | published: the Commercial & Financial Chronicle, September 1, 1923 |
| 9:09 | doc-highlight on the "Shall the Gambler Rule?" advertisement (St. Louis Post-Dispatch, March 8, 1923, Internet Archive, public domain), cropped to the headline and the quoted lines only; table-scan: the price, the down payment and the buyers' notes with their dates, drawn as money coming in, in ink; timeline of the share price through the winter, each figure landing as spoken. |  |
| 9:57 | chart-build of the day's prices, open, high and close, each landing as spoken, the spike in blue; doc-highlight on the Exchange's resolution as the Chronicle printed it (Internet Archive, public domain), "meets with his approval" underlined in ink. | published: the Commercial & Financial Chronicle, March 24, 1923 |
| 10:35 | quote card: the razor sentence, verbatim, attributed "Clarence Saunders to the Associated Press, March 1923"; doc-highlight on the Exchange's delisting resolution (Internet Archive, public domain), "impossible a free market" underlined; table-scan: the Exchange's account and Saunders' account side by side, neither marked as right. |  |
| 11:31 | timeline from Tuesday to Monday, each day's event landing as spoken; quote card for the Exchange's review, verbatim, attributed "New York Stock Exchange, March 26, 1923"; quote card for Saunders' reply, verbatim, attributed "Associated Press, March 23, 1923"; number-land on {{p_clearing}}. |  |
| 12:31 | unit-grid of the {{p_total_shares}} shares, nearly all filled in ink as his, a thin unfilled sliver left; breath, the bed dropping out a beat before "Saunders couldn't sell."; kinetic-thesis: "A corner is a trap that closes on both sides." |  |
| 13:13 | chapter |  |
| 13:16 | timeline of the year as a calendar, the buyers' notes landing as money in (ink) and each obligation landing as money out on its day (blue), as spoken; doc-clipping on the Associated Press report (St. Louis Post-Dispatch, August 13, 1923, Internet Archive, public domain), "before Sept. 1" underlined in ink. | published: the St. Louis Post-Dispatch, August 13, 1923; the Commercial & Financial Chronicle, September 1, 1923 |
| 14:12 | chart-build of the stores company's cash, merchandise and surplus at the two dates, each pair landing as spoken, the deficit in blue; doc-highlight on the balance sheet in the Chronicle (Internet Archive, public domain). | published: the Commercial & Financial Chronicle, September 1, 1923 |
| 14:51 | quote card: "I am unable to get cash on this stock", verbatim, attributed "Clarence Saunders, Associated Press, August 12, 1923"; doc-highlight on the statement as the Post-Dispatch printed it (Internet Archive, public domain), the sentence underlined in ink; still-push on the Saunders portrait, the second time, closer. |  |
| 15:36 | footage-establish on a rail line under a wide morning sky (stock, no markings), never captioned as the journey; doc-clipping on the hearing report (Library of Congress, Chronicling America, public domain), attributed as testimony; quote card for "I have gained knowledge", verbatim, attributed "Associated Press, August 1923". |  |
| 16:13 | still-push on the Pink Palace (Wikimedia Commons, CC BY-SA 3.0, credited on screen and in the description), slow, toward the upper windows; if the licence is refused in sourcing, kinetic-thesis falls back to the words "His plans for its interior were never completed, and he never lived in it."; timeline from the house begun to the museum opened. |  |
| 16:52 | quote card for Time's line, verbatim, attributed "Time, February 25, 1929"; unit-grid of Piggly Wiggly's store count growing past his ruin, each count landing as spoken, the 1932 count marked "one count; secondary". |  |
| 17:37 | number-pair: {{p_assets_claimed}} against {{p_total_owed}}, then the pair struck through and replaced by a single date, {{p_pool_date}}, in blue; kinetic-thesis: "Worth is a number. Cash is a date."; breath, the bed rising under the held line. |  |
| 18:22 | chapter |  |
| 18:25 | footage-process (wide, medium, detail) of cartons arriving on pallets in a bright warehouse, a pallet set down, a carton's label (stock, no logos), screen direction left to right; formula-build: the dated payments, each landing on its own day of a calendar as spoken, in blue. |  |
| 18:50 | chart-build of the demo's monthly profit, landing on {{net_latest}}, labelled Tarnhollow demo data; number-land on {{cash_on_hand}}, with {{cash_months}} beside it in ink; the calendar ahead left blank. | demo: Tarnhollow demo data, MARGIN.DECOMP and the cash horizon |
| 19:28 | chart-build of the demo cash path, day by day, the day's wires drawn as steps down in blue, the payouts as steps up, the trough landing with {{min_median}} labelled, Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 20:20 | formula-build: the time until it lands, plus the time on the shelf, plus the time until you're paid, minus the supplier's credit, each clock landing as spoken, the sale-to-cash clock built from its three parts, labelled Tarnhollow demo data; footage-insert of a container being lifted from a ship at a bright port (stock, no logos). | demo: Tarnhollow demo data, the cash horizon |
| 21:27 | range-band of the {{n_paths}} cash paths, the fan wide at the end and pinched to a single point at the trough, the pinch in blue, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 22:03 | counterfactual on the demo cash path: the payment dropped onto the trough's day, the line crossing zero in blue, then the same payment lifted and set down on the horizon's last day, the line staying well above zero, labelled Tarnhollow demo data; timeline returning to the 1923 calendar on the date. | demo: Tarnhollow demo data, the cash horizon |
| 23:06 | formula-build: a dollar wired, the lead time, the selling time, the payout's wait, the dollar back, each clock landing as spoken; number-land on {{wires_total}}, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 23:43 | number-pair: {{monthly_fixed_costs}} a month against the {{cash_drop}} fall, the fall in blue; chart-build of the demo cash path started lower, the same shape crossing zero on the trough's day, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 24:31 | chart-build of an illustrative cash path with each lever applied in turn, the trough rising or falling as each is spoken, drawn without figures and labelled "Illustration"; footage-insert of a hand turning a desk calendar's page (stock, hands only). | demo: Tarnhollow demo data, the cash horizon (shape only) |
| 25:19 | formula-build listing the steps as terms, each landing as spoken; receipt: one demo row of the calendar, a wire, a payout and the day's balance, the trough day marked in blue, labelled Tarnhollow demo data. | demo: Tarnhollow demo data, the cash horizon |
| 26:17 | still-push resuming on the cold open's turnstile photograph in the same framing; then a modern calendar page with one date circled in blue in the same framing; kinetic-thesis: "Find your date.". | published: the Library of Congress photograph and the Associated Press report of August 1923 |
| 26:34 | range-band of the demo's {{n_paths}} cash paths, the whole fan drawn while the voice names what it takes, the trough marked, labelled Tarnhollow demo data; end card at "hubricon.com/learn". | demo: Tarnhollow demo data, the cash horizon |

### Decide

```
hubricon-content approve greats-03-the-corner
hubricon-content reject  greats-03-the-corner --note "what to change"
```
Edit `content/videos/greats-03-the-corner/script.md` first if you prefer; it is re-validated on approve.
