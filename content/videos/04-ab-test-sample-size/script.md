TITLE:            Your A/B test told you nothing. Here's the sample size you needed
THUMBNAIL:        {{n_for_se_tenth}} months in amber beside the error ladder: the standard error falling as months of price history are added, with the rungs marked
PILLAR:           4
TIER:             A
AWARENESS STAGE:  unaware
CTA:              Subscribe, and the newsletter. Nothing else.
SPIKY CLAIM:      Nearly every price test an operator has ever called a win was noise, and the ones that were real could not be told apart from the outside.
MISCONCEPTION:    I changed the price, sales went up for a few weeks, so the price change worked.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{n_for_se_tenth}} months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.
2. {{el_ci_width}}. That's how wide the honest answer is on one product's demand curve after {{el_periods}} months of price history. You read your few-week test as worked or didn't. It did neither, and the width is the part nobody showed you.
3. {{anom_detector_flagged}} findings. That's what the detectors alone raised on a {{n_skus}}-product catalog in one sweep. After the noise was measured, {{anom_flagged}} were real. Your price test is one of those detectors, and nobody measured its noise.

SCRIPT
[0:00] HOOK
  VO: {{n_for_se_tenth}} months. That's the price history one product needs before its demand curve is pinned tightly enough to price on. Your few-week price test said the new price worked. It could not have known that, and I can draw what it missed.
  VISUAL: kinetic: the month count lands on the first word, then the phrase "pinned tightly enough"
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the test most of us run. Pick a product. Raise the price a notch. Watch it for a few weeks. Compare units and revenue to the weeks before. If revenue went up and units held, keep the new price. If units fell away, put it back. It's a fair test. It's what every pricing tool suggests, and it feels like evidence because something measurable happened. The problem isn't the idea of testing. The problem is how much a few weeks can tell you, and it's far less than it looks.
  VISUAL: kinetic: the before-and-after comparison in the viewer's own words (a real screenshot of a price-test dashboard replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: Take one product off the demo catalog. {{el_sku}}, from {{demo_brand}}, {{demo_label}}, about {{annual_revenue_m}} a year across {{n_skus}} products. This one has {{el_periods}} months of history where the price moved and the units moved with it. That's far more than a few weeks. Fit the demand curve through it and you get a best guess: an elasticity of {{el_point}}. Units fall faster than price rises, by about that ratio. Now ask the fit how sure it is. The honest range runs from {{el_ci_low}} to {{el_ci_high}}. At one end a price rise is a disaster. At the other it's nearly free. Same product, same data, same fit. The width of that range is {{el_ci_width}}, and it's the thing your test never showed you.
  VISUAL: elasticity: the points appear month by month, the fitted line, then the band opens to the full range
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — WHY THE BAND IS WIDE
  VO: Why so wide, with a year of data? Because demand moves on its own. The same plan, run again with the customers arriving in a different order, finishes {{year_luck_spread}} apart after a year, with no price change at all. Every month on this curve carries that noise. Draw the {{el_periods}} points and the line through them. Each point could sit a good way higher or lower and still be the same product in the same month. So the line can tilt, and every tilt the points allow is a different elasticity. The fit reports that as a standard error, {{el_se}} here, and the range you saw is the line tilting as far as the points let it. The fit won't speak at all until it has {{el_min_periods}} months and the price has moved by at least {{el_min_price_cv}}. On this catalog, {{el_skus_insufficient}} of the {{n_skus}} products failed that bar. Their prices never moved, so there was no curve to draw. Your few-week test is below that bar for every product it touched. Not a wide answer. No answer.
  VISUAL: elasticity: each point jitters within its own noise, the line tilts through the allowed range, the band is annotated with the standard error
  DATA SOURCE: ELASTICITY.FIT on Tarnhollow demo data; the year's spread from cash horizon paths, one-year horizon, Tarnhollow demo data
  CLIP: yes

[2:45] CHAPTER 2 — THE SAMPLE SIZE YOU NEEDED
  VO: Here's the part that should bother you more. Suppose you commit to getting more data. How much more? The error falls as you add months, but it falls slowly, and every step down costs more than the last. On this product, bringing the error to something you'd act on takes {{n_for_se_half}} months. Bringing it down by the same kind of step again takes {{n_for_se_quarter}}. Pinning it tightly enough that the price decision is unambiguous takes {{n_for_se_tenth}} months. Products don't live that long. The sample size you needed was never going to arrive. And it gets worse when you test more than one product. Run the short test across a catalog and you will find winners, because some products will move the right way for a few weeks on noise alone. On this same catalog, a sweep of {{anom_scanned}} series raised {{anom_detector_flagged}} flags from the detectors. Then each detector was run {{null_replicates}} times on data with nothing in it, to learn what its own noise looks like, and the flags were held to a false discovery rate of {{anom_fdr_q}}. {{anom_flagged}} survived. The rest were the noise floor wearing the costume of a finding. Your price test is one detector with no null run behind it, so every winner it hands you is unchecked. The more products you test, the more winners it hands you, and the smaller the share that are real.
  VISUAL: sample_size: the error curve falling with months of history, the three rungs marked and named as they're spoken; then kinetic for the sweep, the detector count shrinking to the survivors
  DATA SOURCE: derived from ELASTICITY.FIT standard error, Tarnhollow demo data; ANOMALY.SCAN null calibration on Tarnhollow demo data
  CLIP: yes

[4:00] WHAT TO DO
  VO: A short list, and it's this week's work. First, stop reading a test as worked or didn't. Write down the range the data allows, and if you can't compute a range, treat the test as a story. Next, make the price move on purpose. Small steps, capped at {{pm_step_cap}}, in both directions, over months, because the fit needs {{el_min_periods}} of them and at least {{el_min_price_cv}} of movement before it can say anything. Then price on the range, not the point. The best move on the demo catalog is {{pm_sku}} to {{pm_new_price}}, a {{pm_step}} step, worth about {{pm_delta}} a month. The honest version is {{pm_delta_p5}} to {{pm_delta_p95}}, with a {{pm_p_loss}} chance it loses. Decide looking at the whole range. Last, keep a control. Leave one product's price where it is and watch how far it moves on its own over the same weeks. That's your noise floor, and a winner that didn't beat it wasn't a winner.
  VISUAL: kinetic: the steps landing one at a time; the price move with its range as a band, not a bar
  TEMPLATE: none for this pillar

[4:45] THE HONEST LIMIT
  VO: What you can do yourself is fit one product's curve in a spreadsheet. Log of units against log of price, the slope is the elasticity, and the spreadsheet gives you the standard error. Do that on your top products and it's worth an afternoon. What you can't do by hand is keep it honest across {{n_skus}} products every month, with errors that don't trust the noise to be tidy, and check each decision against {{null_replicates}} runs of nothing. That part is a model, and a bad model is worse than the few-week test. What you can do today is stop calling a test a win. Ask how wide the answer is.
  VISUAL: kinetic: the closing question
  CTA: If this was useful, subscribe. The newsletter carries one of these a week.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:20, 2:45, 3:15, 3:45, 4:00, 4:30, 4:45, 5:10 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the sample size you needed was {{n_for_se_tenth}} months, and your product won't live that long" · X thread spine: a year of data, an answer from {{el_ci_low}} to {{el_ci_high}} · newsletter section: keep a control product · clips at 0:00, 0:45, 2:45, 4:00
