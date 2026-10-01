TITLE:            {{peak_from}}: what Amazon's holiday fees cost one listing, to the cent
THUMBNAIL:        {{cs_delta}} a unit, from {{peak_from}}, in blue on the dashed holiday card
PILLAR:           3
TIER:             A
AWARENESS STAGE:  problem-aware
CTA:              The whole method and the spreadsheet, free at hubricon.com/learn
SPIKY CLAIM:      The holiday card is a price rise Amazon charges you per unit, and your P&L won't show it until it has already been paid.
MISCONCEPTION:    Holiday fees are a seasonal blip: a little higher, volume's up anyway, it washes out.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{peak_from}}. From that morning until {{peak_to}}, every unit you ship through Amazon costs more to fulfil, and your P&L won't say so until it's been paid. Here's what it costs one real listing, to the cent.
2. {{cs_delta}} a unit. That's what Amazon's holiday card adds to one real listing from {{peak_from}}. On its volume, that's {{cs_window_lo}} to {{cs_window_hi}} across the season, and nobody sent it a memo.
3. {{peak_min}} to {{peak_max}} more a unit. That's Amazon's holiday card on standard-size products, row by row, from {{peak_from}}. If you can't say what it costs your best seller, that's not a you problem.

SCRIPT
[0:00] HOOK
  VO: {{peak_from}}. From that morning until {{peak_to}}, every unit you ship through Amazon costs more to fulfil, and your P&L won't say so until it's been paid. Here's what it costs one real listing, to the cent.
  VISUAL: number: {{peak_from}} lands alone, then {{peak_to}} beside it
  CLIP: yes

[0:20] LET THEM BE WRONG
  VO: Here's how most of us treat holiday fees. Amazon raises them a little for the season. Volume's up anyway. It washes out. It's a reasonable view, and it's how the fee usually gets handled, as weather. If you've never priced it, that's not a you problem. Nobody around you is running the math. The trouble is that it isn't the same for every product, and it lands on each unit, not on the average.
  VISUAL: kinetic: the misconception in plain words, then "each unit, not the average"
  CLIP: no

[0:50] WHAT CHANGES
  VO: Here's what changes. First, the fulfilment fee. From {{peak_from}} to {{peak_to}}, Amazon prices every unit off a second card. On the standard-size rows it's {{peak_min}} to {{peak_max}} more a unit, depending on the weight and the price. Second, storage. From October to December, a cubic foot of standard-size stock costs {{stor_peak}} a month, against {{stor_off}} the rest of the year. And under both, the {{surcharge}} fuel and logistics surcharge Amazon added in April stays on every fulfilment fee.
  VISUAL: staircase: the card in force drawn solid, the holiday card dashed above it, the gap between them shaded
  DATA SOURCE: Amazon's published 2026 cards, both of them, with the surcharge
  CLIP: yes

[1:30] CHAPTER 1 — ONE LISTING, PRICED
  VO: Here's what that means on one real listing, modeled from its public page: {{who}}'s best-selling paint scratch remover. Until {{np_through}} it pays {{cs_fee_np}} a unit to fulfil. From {{peak_from}}, {{cs_fee_peak}}. That's {{cs_delta}} a unit. Its public sales rank puts it at roughly {{units}} units a month, and a rank is a rough guide, so we carry a range. Across the season, the holiday card costs this one listing {{cs_window_lo}} to {{cs_window_hi}}. Nothing about the product changed. Nobody decided anything. The date did it.
  VISUAL: number: {{cs_fee_np}} turns into {{cs_fee_peak}}, the difference in blue, then the season's range
  DATA SOURCE: the public-data case study, modeled from public data
  CLIP: yes

[2:10] CHAPTER 2 — THE STEPS GET STEEPER
  VO: Here's the part most people miss. Amazon's card is a staircase, and a unit that sits a fraction of an ounce past an edge pays the whole step. This listing sits {{over}} past the {{edge}} edge. On the card in force until {{np_through}}, that step costs it {{step_np}} a unit. On the holiday card, {{step_peak}}. A step you were already paying for gets more expensive in the months you sell the most.
  VISUAL: staircase: the listing's dot past the edge, the riser in blue on both cards
  DATA SOURCE: the public-data case study, modeled from public data
  CLIP: yes

[2:45] CHAPTER 3 — THE PRICE TRAP
  VO: The reflex is to raise the price to cover it. Be careful where. On Amazon's card a price is a step too. Below {{price_edge}}, a unit pays the cheaper column. Move a price from under {{price_edge}} to over it, and on the card in force the fulfilment fee alone goes up {{ten_min}} to {{ten_max}} a unit, before the holiday card adds its share. A small raise across that line can leave you with less per unit than you had. Check which column the new price lands in before you move it.
  VISUAL: formula: net per unit = the fee jump minus the price you gain, after referral
  DATA SOURCE: Amazon's published 2026 cards
  CLIP: no

[3:20] CHAPTER 4 — THE UNITS THAT SIT
  VO: Then storage. From October to December, a cubic foot costs {{stor_peak}} a month, against {{stor_off}}. The units that cost the most are the ones that don't move. And once a unit has sat {{cliff_day}} days, the aged-inventory surcharge steps from {{aged_before}} to {{aged_after}} a cubic foot, on top of storage. Holiday storage on an old unit is the most expensive combination on Amazon's cards.
  VISUAL: aging: storage plus the surcharge by age, the day-271 riser in blue
  DATA SOURCE: Amazon's published storage schedule, on the case-study unit's size, modeled from public data
  CLIP: yes

[3:55] WHAT TO DO
  VO: Here's the list, and you can do all of it before {{peak_from}}. Price your best sellers on the holiday card, not the one you're used to. Find any that sit a fraction of an ounce past an edge: that step gets steeper now. If you're raising prices for the season, check which column of the card the new price lands in. And pull your inventory age report. For anything close to {{cliff_day}} days, price what it costs to hold through December against what it costs to sell through or remove. The spreadsheet that does every one of these is free, with the course.
  VISUAL: kinetic: the steps landing one at a time, then the template's One listing sheet
  CLIP: no

[4:35] THE HONEST LIMIT
  VO: What a public page can't tell you is how long your units have sat, what your ads cost you per sale, or how many come back. Those live in your own exports, and that's where most of the holiday money goes. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the closing line, then hubricon.com/learn
  CTA: The whole method and the spreadsheet are free at hubricon.com/learn.
  CLIP: no

RE-HOOK AUDIT: 0:00, 0:20, 0:50, 1:30, 1:50, 2:10, 2:45, 3:20, 3:55, 4:15, 4:35
DERIVED ASSETS: LinkedIn post: "the date did it" with the case study's {{cs_fee_np}} and {{cs_fee_peak}} · Shorts at 0:00, 0:50, 1:30, 2:10, each ending on hubricon.com/learn · live only from now to {{peak_to}}: retire the episode when the card does
