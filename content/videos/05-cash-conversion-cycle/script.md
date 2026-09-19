TITLE:            Cash conversion cycle: the number that decides whether you survive
THUMBNAIL:        {{min_p5}} in amber over the cash cone fragment, the trough marked on day {{min_p5_day}} with the supplier wires as red ticks
PILLAR:           2
TIER:             B
AWARENESS STAGE:  solution-aware
CTA:              The free Profit Teardown at /apply
SPIKY CLAIM:      A profitable catalog can run out of cash on a date you can read off a calendar, and most operators watch the P&L instead of the calendar.
MISCONCEPTION:    We're profitable, so cash takes care of itself. If the margin is there, the bank balance follows.
RUNTIME:          9–10 min

HOOKS (three, pick one)
1. {{min_p5}}. That's where this catalog's cash bottoms out on day {{min_p5_day}}, on a business making {{net_pct_latest}} net. You'd say a margin like that can't run out of money. It can, on a date you can read off a calendar.
2. {{wires_total}} leaves this account in supplier wires inside {{horizon_days}}, against {{cash_on_hand}} in the bank. The margin says fine. The margin doesn't know when the money moves, and the dates are the whole story.
3. {{lead_time_typical}} from the wire to the goods landing. {{payout_cycle}} from the sale to the payout. Add the time on the shelf and you have the number that decides whether you survive, and almost nobody has written it down.

SCRIPT
[0:00] HOOK
  VO: {{min_p5}}. That's where this catalog's cash bottoms out on day {{min_p5_day}}, on a business making {{net_pct_latest}} net. You'd say a margin like that can't run out of money. It can, on a date you can read off a calendar.
  VISUAL: kinetic: the trough figure lands on the first word, then the day
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the model. You watch the P&L. Revenue up, margin healthy, net positive, so the business is fine and the bank balance is a lagging copy of the P&L. When cash gets tight it's a surprise, and the explanation is always something else. A big PO. A slow payout. A bad month. It's a fair model, because over a long enough window the P&L and the bank do agree. The trouble is the window. Inside it, the money leaves on one set of dates and comes back on another, and the P&L doesn't carry dates.
  VISUAL: kinetic: the P&L read in the viewer's own words (a real P&L screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: Here's the demo catalog on screen. {{demo_brand}}, {{demo_label}}, {{n_skus}} products, about {{annual_revenue_m}} a year. Last month: {{rev_latest}} of sales, {{net_latest}} of true net profit, {{net_pct_latest}} net margin. On the P&L this business is fine. Now the bank. {{cash_on_hand}} on hand today. Inside the next {{horizon_days}}, the supplier wires already scheduled add up to {{wires_total}}. That's more than the cash in the bank, on a business that is profitable every month. The money comes back. The question is when, and whether the balance runs dry on the way.
  VISUAL: waterfall: revenue down to true net for the latest month; then cash_cone: the cone opens from today's balance with the wires as red ticks
  DATA SOURCE: MARGIN.DECOMP on Tarnhollow demo data; cash horizon on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — FIND IT
  VO: On screen is the cash cone. {{n_paths}} possible versions of the next {{horizon_days}}, drawn from what this catalog's demand actually does, with every supplier wire as a red tick. Read it left to right, and find the clocks. First, the wire schedule. {{wire_count}} wires inside the window. The largest, {{largest_wire}}, for {{largest_wire_sku}}, leaves on day {{largest_wire_day}}. That's today. Next, how long the goods take to arrive. The typical supplier lead time here is {{lead_time_typical}}. For that long the money is gone and there's nothing new to sell. Then the shelf. Once units land they sit until they sell. The tightest product in this catalog, {{stockout_worst_sku}}, has {{stockout_worst_cover}} of cover, and slower products sit longer than that. Last, the payout. The platform holds the sale for a {{payout_cycle}} cycle before it pays you. Now put the clocks in a row. Wire, then lead time, then shelf, then payout. The cash conversion cycle is the length of that row: the days between a dollar leaving for the supplier and the same dollar landing back in the bank. It isn't on the P&L because the P&L has no calendar. It's on this chart, because this chart is nothing but a calendar.
  VISUAL: cash_cone: the wires as ticks; then the lead-time span, the shelf span and the payout lag drawn as brackets under the axis, joined into one bar
  DATA SOURCE: cash horizon on Tarnhollow demo data; MONTE_CARLO.RUN on Tarnhollow demo data for lead time and cover
  CLIP: yes

[3:30] CHAPTER 2 — VERIFY IT
  VO: Now verify it against the cone. The median path's low point is {{min_median}}. The bad paths' low point, the worst day of the unlucky tail, is {{trough_p5}}, and it arrives on day {{min_p5_day}}. Look where that day sits. It's after the wires have left and before the goods have landed, let alone sold and paid out. That's the cycle showing up as a date. In this run the share of paths that ever runs dry is {{p_ruin}}. That's with {{cash_on_hand}} in the bank on day {{largest_wire_day}}. Bring the starting balance down toward {{trough_p5}} and the same schedule, same margin, same products, starts touching the floor. The margin never changed. Only the balance did, and the dates did the rest. And here's what the cone knows that a spreadsheet doesn't. Products don't sell independently. Across this catalog, demand moves together with a correlation of {{demand_corr}}, so a slow week is slow for most of the products at once, and the trough is deeper than it would be if each product rolled its own dice. Seen from the other end, after {{horizon_days}} the top of the cone is {{terminal_p90}} and the bottom is {{terminal_p10}}. Same plan, same margin. Over a full year that gap opens to {{year_luck_spread}} on dice alone.
  VISUAL: cash_cone: the trough marked at day {{min_p5_day}}, the floor line, the fan widening to the right with the ends labelled
  DATA SOURCE: cash horizon on Tarnhollow demo data; cash horizon paths, one-year horizon, Tarnhollow demo data
  CLIP: yes

[5:30] WHAT IT'S WORTH
  VO: So what's the number worth? Every day you shorten the cycle is a day less of cash sitting in the gap, and here's what's sitting in the gap on this catalog right now. On the shelf clock, stock ordered past its economic quantity costs {{nv_bleed_month}} a month in fees to hold, and there are {{nv_econ_orders}} orders the newsvendor would trim. That's cash parked on a shelf. On the wire clock, the largest wire is {{largest_wire}} and it goes out on day {{largest_wire_day}}, so it sets the depth of the trough more than any other line on the calendar. On the payout clock, {{payout_cycle}} is fixed by the platform. You can't shorten it. You can stop treating it as instant. And the price of getting this wrong isn't a fee. It's the reorder you can't place because the cash is in transit, and the rank you buy back with ads afterwards. The risk model puts the expected shortfall below plan in a bad period at {{risk_cvar_95}}, and the worst run of periods at {{risk_worst_5}} of net against an expected {{risk_expected_net}}. The cycle is where that shortfall lands.
  VISUAL: newsvendor: the overstocked orders as bars above the economic quantity; then kinetic for the clocks and the shortfall
  DATA SOURCE: NEWSVENDOR on Tarnhollow demo data; risk on Tarnhollow demo data
  CLIP: yes

[7:30] WHAT TO DO
  VO: This week. First, write the cycle down. Wire date, landing date, first sale, first payout, for your top products, from your own POs and settlement reports. It's a spreadsheet with dates in it, and most operators have never made one. Next, draw the wires. Every scheduled supplier payment inside the next {{horizon_days}}, on a calendar, against the cash you hold and the payouts you expect. Where the line dips lowest is your own day {{min_p5_day}}. Then move the clocks. Split the largest wire into a deposit and a balance where the supplier allows it. That flattens the trough without touching the margin. Trim the orders the newsvendor flags as overstocked, because that cash comes back onto the calendar. Ask for terms before you ask for growth. Last, hold cash for the trough, not for the month. Fixed costs here are {{monthly_fixed_costs}} a month, and the trough arrives on day {{min_p5_day}}. The right reserve is the trough plus a buffer for the cone's bad tail, not a round number of months.
  VISUAL: kinetic: the steps landing one at a time; cash_cone with the largest wire split and the trough lifting
  DATA SOURCE: cash horizon on Tarnhollow demo data
  TEMPLATE: none for this unit

[9:00] THE HONEST LIMIT
  VO: What you can do yourself is the calendar for your top products, and it's worth doing this week. What you can't do by hand is the cone. {{n_paths}} versions of the next {{horizon_days}} across {{skus_in_cone}} products with demand that moves together, redrawn every time a wire moves or a payout slips. That's a model, and this is one of the places a bad model is dangerous, because a cone drawn too narrow tells you you're safe. The free Profit Teardown runs this cone on your own exports and hands you the date and the trough. What you can do today is stop reading the margin as a cash forecast. Find your day {{min_p5_day}}.
  VISUAL: kinetic: the closing line
  CTA: The free Profit Teardown at /apply. Your own cash cone, from your own exports, inside a day.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:25, 3:00, 3:30, 4:05, 4:40, 5:15, 5:30, 6:05, 6:40, 7:15, 7:30, 8:05, 8:40, 9:00, 9:35 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the P&L has no calendar" · X thread spine: {{wires_total}} of wires against {{cash_on_hand}} in the bank, and the trough on day {{min_p5_day}} · newsletter section: write the cycle down, four dates per product · clips at 0:00, 0:45, 1:15, 3:30, 5:30
