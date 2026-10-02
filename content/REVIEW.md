# Review inbox

Updated 2026-10-02T16:20:03+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

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
