# Review inbox

Updated 2026-10-02T19:09:24+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

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
