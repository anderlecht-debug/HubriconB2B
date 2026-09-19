TITLE:            Elasticity in plain English, and why your price is probably wrong
THUMBNAIL:        {{el_point}} in amber over the elasticity fragment: the demand line with its band, and the top of the profit hill marked as a stretch, not a point
PILLAR:           3
TIER:             A
AWARENESS STAGE:  problem-aware
CTA:              The course page at /learn, where the method is written out in full; no service mention
SPIKY CLAIM:      Almost nobody's price sits on top of the profit hill, because almost nobody has measured the slope, and the ones who moved on gut are as likely to have moved away from the top as toward it.
MISCONCEPTION:    If units are holding, the price is right. Elasticity is a warning not to raise prices.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{el_median}}. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
2. {{pm_count}} of {{n_skus}}. That's how many products on this catalog have a price move worth making, once you know how fast units fall when the price moves. You'd say your prices are right because units are holding. That isn't the test, and here's the test.
3. {{pm_delta}} a month, from moving one product's price by {{pm_step}}. The honest range is {{pm_delta_p5}} to {{pm_delta_p95}}. You'd say you'd have found that yourself if it were there. You can't see it, because the number it depends on has never been measured.

SCRIPT
[0:00] HOOK
  VO: {{el_median}}. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
  VISUAL: kinetic: the ratio lands on the first word, then "how fast units fall" over "how far the price rises"
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's how most prices get set. Landed cost, times a markup that gives a gross margin you're comfortable with. A look at the competitors. Then a gut check: would I pay that. If units hold after a change, the price was fine. If units drop, it was too high, put it back. It's a fair method. It's what everyone does, and it isn't stupid, because units are the thing you can see. The thing you can't see is the line the units sit on, and the price you want is on that line, not on the markup.
  VISUAL: kinetic: the markup method in the viewer's own words (a real pricing spreadsheet screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: Take one product from the demo catalog. {{el_sku}}, from {{demo_brand}}, {{demo_label}}, {{n_skus}} products, about {{annual_revenue_m}} a year. It has {{el_periods}} months of history where the price moved and the units moved with it. Plot them. Price across, units up. The points slope down: dearer, fewer. Fit a line through them and read the slope as a ratio, how fast units fall for how far the price rises. On this product the ratio is {{el_point}}. That's the whole of elasticity. A price rise of a given size costs you units by that multiple of it. It isn't a warning. It's a measurement. And it comes with a range, {{el_ci_low}} to {{el_ci_high}}, because {{el_periods}} months of noisy demand can't pin it tighter than that.
  VISUAL: elasticity: the points appear month by month, the fitted line, then the band opens to the full range
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — THE HILL
  VO: Now why the number tells you where the price should sit. Raise the price and it pulls in both directions. Every unit you still sell earns more. And you sell fewer units. Profit is what's left when those pull against each other, so as the price climbs, profit climbs, then flattens, then falls. It's a hill. Every product has one. The top of the hill is the price you want, and where the top sits depends on the slope and the margin, and nothing else. The slope is the elasticity. The margin is how much of each dollar you keep at the edge, and it is not the gross margin. It's what's left after the platform's cut and the ad it took to sell the unit, because those are charged per unit too. On this catalog the platform keeps {{fee_share_latest}} of revenue. The margin after cost, fees and ads is {{contribution_pct_latest}}, against a gross margin of {{gross_pct_latest}}. Set the price off the gross number and you've climbed the wrong hill. Here's the rule in words, before any symbol. The faster the units fall, the closer the price should sit to your true cost. The slower, the further above it. And now the symbol, as a convenience: the fraction of the price you keep above true unit cost should equal the inverse of the elasticity. That's all it is.
  VISUAL: elasticity: the demand line, then the profit hill built underneath it as the price sweeps across, the top marked; a second, lower hill drawn off the gross margin to show the wrong top
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data; MARGIN.DECOMP on Tarnhollow demo data
  CLIP: yes

[2:45] CHAPTER 2 — THE TOP IS A STRETCH
  VO: Here's the part a good operator gets wrong even after the hill. The top isn't a point. The elasticity came with a range, {{el_ci_low}} to {{el_ci_high}}, so the top is a stretch of hill, and a price move is a bet on where inside that stretch the top really is. So the honest question isn't what's the best price. It's what's the best step, given what we don't know. Run that across the whole catalog. {{el_skus_fit}} products have a usable fit. {{el_skus_insufficient}} were refused, because their price never moved enough to draw a line; the fit won't speak until the price has moved by {{el_min_price_cv}} across {{el_min_periods}} months, and on those products nobody ever moved it. Of the fitted ones, {{pm_count}} have a move worth making. The best is {{pm_sku}}: a {{pm_step}} step to {{pm_new_price}}, expected to add {{pm_delta}} a month. The honest version is somewhere between {{pm_delta_p5}} and {{pm_delta_p95}}, with a {{pm_p_loss}} chance it loses money. Every step is capped at {{pm_step_cap}}, because a small step you can read is worth more than a big step you can't. Across every move the catalog picks up about {{pm_total_delta}} a month in expectation. That's the sense in which your price is probably wrong. Not badly. Wrong by a step, on most products, in a direction you can only learn by measuring the slope.
  VISUAL: elasticity: the band widens and the hill's top becomes a shaded stretch; then kinetic: the catalog counts, the best move drawn as a band from the low case to the high case, not a bar
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data; PRICE.OPTIMUM on Tarnhollow demo data
  CLIP: yes

[4:00] WHAT TO DO
  VO: This week. First, pick your top products and pull price and units by month, as far back as you have. Next, plot them and fit the line: log of units against log of price. The slope is the elasticity, and the spreadsheet gives you the standard error beside it. If the price never moved, you have no line, and the first job is to move it, in small steps, both ways, and wait {{el_min_periods}} months. Then compute your true unit margin, after the platform and the ads, not the gross one, and put the price where the fraction you keep equals the inverse of the slope. Last, take the step as a step, not a leap. Cap it, read the result against the range, and go again.
  VISUAL: kinetic: the steps landing one at a time
  TEMPLATE: none yet for this pillar; the CTA points at the course page

[4:45] THE HONEST LIMIT
  VO: What you can do yourself is the line for your top products, and it's worth an afternoon. What you can't do by hand is keep it honest across {{n_skus}} products every month, with errors that don't assume the noise is tidy, and turn each range into a step that's the right size for what's unknown in it. Done by hand, the ranges get dropped inside a season and you're back to gut. That part is a model. What you can do today is stop treating units holding as proof. Measure the slope.
  VISUAL: kinetic: the closing line
  CTA: The course page at /learn, where the method is written out in full.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:20, 2:45, 3:15, 3:45, 4:00, 4:30, 4:45, 5:10 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "elasticity isn't a warning, it's a measurement" · X thread spine: the hill, the wrong hill off gross margin, the top as a stretch · newsletter section: move the price on purpose so the fit can speak · clips at 0:00, 0:45, 1:15, 2:45
