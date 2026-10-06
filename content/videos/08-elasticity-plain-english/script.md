TITLE:            Elasticity in plain English, and why "units are holding" is not proof your price is right
THUMBNAIL:        {{el_ci_width}} in ink over the elasticity fragment: the demand line with its band, and the top of the profit hill drawn as a stretch across the price axis, not a point
PILLAR:           3
TIER:             A
AWARENESS STAGE:  problem-aware
CTA:              The free course at hubricon.com/learn, where the method is written out in full
SPIKY CLAIM:      Almost nobody can say where the top of their profit hill is, and the honest measurement of it, run on a year of history, usually refuses to name the top at all — which makes every price set on gut a guess with no error bar on it.
MISCONCEPTION:    If units are holding, the price is right. Elasticity is a warning not to raise prices.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{el_median}}. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
2. {{el_no_top}} of {{el_skus_fit}}. That's how many products on this catalog the model refuses to name a best price for, with a year of price history on each. You'd say your prices are right because units are holding. That isn't the test, and here's the test.
3. {{el_ci_width}}. That's the width of the honest answer on one product's demand slope, and the price you want is set from that slope. You'd say you'd have spotted a pricing mistake yourself. You can't, because nobody has measured it.

SCRIPT
[0:00] HOOK
  VO: {{el_median}}. That's the median elasticity on this catalog: the ratio of how fast units fall to how far the price rises. You'd read it as a warning not to touch the price. It's the number that tells you where the price should sit.
  VISUAL: kinetic: the ratio lands on the first word, then "how fast units fall" over "how far the price rises"
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's how most prices get set. Landed cost, times a markup that gives a gross margin you're comfortable with. A look at the competitors. Then a gut check: would I pay that. If units hold after a change, the price was fine. If units drop, it was too high, put it back. It's a fair method, and it isn't stupid, because units are the thing you can see. The thing you can't see is the line the units sit on, and the price you want is on that line, not on the markup.
  VISUAL: kinetic: the markup method in the viewer's own words (a real pricing spreadsheet screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: Take one product from the demo catalog. {{el_sku}}, from {{demo_brand}}, {{demo_label}}, {{n_skus}} products, about {{annual_revenue_m}} a year. It has {{el_periods}} months of history where the price moved and the units moved with it. Plot them. Price across, units up. The points slope down: dearer, fewer. Fit a line through them and read the slope as a ratio, how fast units fall for how far the price rises. On this product the ratio is {{el_point}}. That's the whole of elasticity. A price rise of a given size costs you units by that multiple of it. It isn't a warning. It's a measurement. And it comes with a range, {{el_ci_low}} to {{el_ci_high}}, because {{el_periods}} months of noisy demand can't pin it tighter than that.
  VISUAL: elasticity: the points appear month by month, the fitted line, then the band opens to the full range
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — THE HILL
  VO: Now why the number tells you where the price should sit. Raise the price and it pulls both ways. Every unit you still sell earns more. You sell fewer units. Profit is what's left when they pull against each other, so as the price climbs, profit climbs, flattens, then falls. It's a hill. Every product has one. The top of the hill is the price you want, and where it sits depends on the slope and the margin, and nothing else. The slope is the elasticity. The margin is what you keep on the next unit, and it isn't the gross margin: the platform's cut and the ad that sold the unit are charged per unit too. On this catalog the platform keeps {{fee_share_latest}} of revenue. The margin after cost, fees and ads is {{contribution_pct_latest}}, against a gross margin of {{gross_pct_latest}}. Set the price off the gross number and you've climbed the wrong hill. Here's the rule in words, before any symbol. The faster the units fall, the closer the price should sit to your true cost. The slower, the further above it. And now the symbol, as a convenience: the fraction of the price you keep above true unit cost should equal the inverse of the elasticity. That's all it is.
  VISUAL: elasticity: the demand line, then the profit hill built underneath it as the price sweeps across, the top marked; a second, lower hill drawn off the gross margin to show the wrong top
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data; MARGIN.DECOMP on Tarnhollow demo data
  CLIP: yes

[2:45] CHAPTER 2 — THE TOP IS A STRETCH
  VO: Here's the part a good operator gets wrong even after the hill. The top isn't a point. The elasticity came with a range, {{el_ci_low}} to {{el_ci_high}}, and the rule for the top divides by how far the slope sits from the place where a price rise exactly pays for the units it costs. Near that place the answer runs off to no limit. So a wide range doesn't hand you a blurry top. It hands you a top that might be one step up the hill, or past the edge of the chart. Run it across the catalog. {{el_skus_fit}} products have a usable fit. {{el_skus_insufficient}} were refused: the fit won't speak until the price has moved by {{el_min_price_cv}} across {{el_min_periods}} months, and nobody ever moved theirs. Of the fitted ones, the range is too wide to name a top for {{el_no_top}}. All of them. So the model does the honest thing. It works the rule at the estimate alone, and calls for a step only if that lands above today's price. On this catalog it calls for no step at all, and weighing the whole history together it puts {{el_p_optimal}} on these prices already being about right. A measurement that will tell you it can't see the top is one you can trust when it tells you to climb.
  VISUAL: elasticity: the band widens and the hill's top smears into a stretch across the price axis; then kinetic: the catalog counts, the word "hold" landing in ink, and the refused products as empty outlines with no band at all
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data; PRICE.OPTIMUM on Tarnhollow demo data ({{pm_count}} recommended steps)
  CLIP: yes

[4:00] WHAT TO DO
  VO: This week. First, pick your top products and pull price and units by month, as far back as you have. Then fit the line: log of units against log of price. The slope is the elasticity, and the spreadsheet gives you the standard error beside it. If the price never moved, you have no line, and the first job is to move it, in small steps, both ways, and wait {{el_min_periods}} months. Then compute your true unit margin, after the platform and the ads, not the gross one, and put the price where the fraction you keep equals the inverse of the slope. If the range is too wide to name a top — and it usually is — work the rule at your estimate alone: above today's price, step up; below it, hold. Last, take the step as a step, not a leap. Cap it at {{pm_step_cap}}, read the result against the range, and go again.
  VISUAL: kinetic: the steps landing one at a time
  TEMPLATE: none yet for this pillar; the CTA points at the course page

[4:45] THE HONEST LIMIT
  VO: What you can do yourself is the line for your top products, and it's worth an afternoon. What you can't do by hand is keep it honest across {{n_skus}} products every month, with errors that don't assume the noise is tidy, and turn each range into a step the right size for what's unknown in it. That part is a model. What you can do today is stop treating units holding as proof. Measure the slope. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the closing line
  CTA: The method, written out in full with the spreadsheet, is free at hubricon.com/learn.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:20, 2:45, 3:15, 3:45, 4:00, 4:30, 4:45, 5:10 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "elasticity isn't a warning, it's a measurement" · X thread spine: the hill, the wrong hill off gross margin, the top as a stretch too wide to mark · newsletter section: move the price on purpose so the fit can speak · clips at 0:00, 0:45, 1:15, 2:45
