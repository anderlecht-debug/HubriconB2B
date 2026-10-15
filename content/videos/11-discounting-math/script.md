TITLE:            Discounting: the math of what you gave away
THUMBNAIL:        {{contribution_pct_latest}} in ink over the waterfall's last bar, the discount taken off the whole width of it
PILLAR:           3
TIER:             A
AWARENESS STAGE:  problem-aware
CTA:              The free course at hubricon.com/learn, where the method and the worksheet are written out in full
SPIKY CLAIM:      A promotion is not a trade of margin for volume. It is a bet that your product is more price-sensitive than your own price history says it is, and on this catalogue the bet loses at every value of elasticity except the one you have least reason to believe.
MISCONCEPTION:    The discount costs me the discount. Margin is thick, so there's room, and the volume makes it back.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{gross_pct_latest}} gross margin. That's the number in your head when you price a promotion, and it's why the discount feels affordable. The number it actually comes out of is {{contribution_pct_latest}}, and the gap between them is the room you thought you had.
2. {{contribution_pct_latest}}. That's what's left on a unit here once the platform, the goods and the ads are paid. Take a discount out of that and the units you need to stand still aren't proportional to the discount. They're worse.
3. {{el_median}}. That's the middle demand elasticity on this demo catalogue, measured rather than assumed. It says what a discount buys in units. Set it against what the discount costs in margin and most promotions on this shelf never get their money back.

SCRIPT
[0:00] HOOK
  VO: {{gross_pct_latest}} gross margin. That's the number in your head when you price a promotion, and it's why the discount feels affordable. The number the discount actually comes out of is {{contribution_pct_latest}}, and what it does to the units you need is not proportional to the discount.
  VISUAL: kinetic: the gross figure lands, the contribution figure lands under it, the gap between them opens
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's how the decision gets made, and it's a reasonable way to make it. A promotion is a trade. Give up some margin, get more units, and if the volume comes you're ahead. The margin looks thick, so there's room in it. And underneath that sits a rule of thumb nearly everyone carries: the discount costs you the discount. Take a step off the price and you give up that much of what you were making, then make it back on volume. Hold on to that, because both parts of it are wrong, and they're wrong in the same direction.
  VISUAL: screenshot: a promotion being set up in the seller's own console, the discount field filled in (a real screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: This is the demo catalogue. {{demo_brand}}, {{demo_label}}, {{n_skus}} products, about {{annual_revenue_m}} a year. Gross margin is {{gross_pct_latest}}. After the platform's fees, the landed cost of the goods and the ads those products spend, what's left is {{contribution_pct_latest}}. A gap of {{gross_vs_contribution_gap}}. The discount doesn't come out of the first number. It comes out of the second, and it comes out whole — a step off the price is the same step off what you keep, not a slice of it.
  VISUAL: waterfall: revenue down to contribution, then the discount taken off the last bar, the bar shrinking by the full width of the step
  DATA SOURCE: MARGIN.DECOMP on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — INTUITION
  VO: Picture what you keep on a unit as a glass, and the glass is nowhere near full. The discount doesn't take a share of the glass. It takes a fixed depth off the top. So the share of your profit it removes is the discount measured against what was in the glass, which is already far more than the discount measured against the price. That's the first part. Here's the second. To stand still you need enough extra units to refill the profit you poured out, and every new unit now carries less than the old ones did. So the lift you need is what you kept before, divided by what you keep after the discount. That's the whole line. Write it on a sticky note. And look at its shape, because the shape is the point: the lift it demands doesn't rise in step with the discount, it accelerates, and it goes vertical as the discount approaches the margin itself. Now that you've watched it bend, it has a name. Break-even volume lift.
  VISUAL: formula: the glass draining by a fixed depth, then the line — lift needed = what you kept, divided by what you keep after the discount — then the curve drawn as the discount deepens and runs away
  CLIP: yes

[2:45] CHAPTER 2 — THE TURN
  VO: Here's the part a careful operator still gets wrong. You'd test that lift against what you believe demand will do. Measure it instead. The fit here reads {{el_skus_fit}} products off their own price histories, and the middle of them sits at {{el_median}}. Take the worked product, {{el_sku}}, at {{el_point}}, with an honest interval running from {{el_ci_low}} to {{el_ci_high}}. Now take a cut the size of the cap this model puts on any price step, {{pm_step_cap}}, and set them side by side: the lift the arithmetic demands, and the lift the measured elasticity actually delivers. On this catalogue the demand falls short at the middle of the band, and short again at the point estimate. Only at the far elastic end of the interval does the cut get its money back, and the far end is the value you have the least evidence for. So a promotion isn't a trade of margin for volume. It's a bet that your product is more price-sensitive than your own data says it is, placed with the margin you already measured.
  VISUAL: elasticity: the fitted band for the worked product, with the lift the arithmetic demands drawn across it as a line the band has to clear
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data
  CLIP: yes

[4:00] WHAT TO DO
  VO: Before the next promotion, in order. Work out what you actually keep per unit on the product being discounted, after fees, landed cost and the ads that product spends. Not gross. Then take the lift: what you kept, divided by what you'd keep after the discount. Write that down before you run anything. Then look up what the product's own price history says it does when the price moves, and if you've never moved the price, say so out loud, because then the lift is a hope rather than a forecast. And when the promotion ends, measure units against the lift you wrote down. Not revenue against last month. Revenue always rises during a discount. That's the discount, not demand.
  VISUAL: kinetic: the steps landing one at a time, then chapter_card: the lift written down before the promotion runs
  TEMPLATE: the discount worksheet in the free course — what you keep per unit, the break-even lift, and the product's measured elasticity beside it
  CLIP: no

[4:45] THE HONEST LIMIT
  VO: What you can do yourself is this arithmetic, on the product you were about to discount, in about the time it takes to find the fee line in the settlement report. Do it once and promotions stop being automatic. What you can't do by hand is the other side of the question: whether the cut takes its units from the product sitting next to it, what it does to the rank you'll be bidding to recover afterwards, whether the units you pulled forward were coming anyway, and all of that re-asked across {{n_skus}} products every month while the fees and the landed costs move underneath. That part is a model. The arithmetic still changes the decision today, which is why it's the part I'd rather you had. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the closing line, held
  CTA: The method is written out in full, with the worksheet, free at hubricon.com/learn.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:55, 2:35, 2:45, 3:25, 4:00, 4:40, 4:45, 5:25, 6:00 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the discount does not cost you the discount" · X thread spine: what you keep, the lift that refills it, the elasticity that has to deliver it · newsletter section: measure units against the lift you wrote down, never revenue against last month · clips at 0:00, 0:45, 1:15, 2:45
