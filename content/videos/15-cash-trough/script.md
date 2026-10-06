TITLE:            You don't have a revenue problem. You have a cash trough
THUMBNAIL:        {{min_median}} in ink at the bottom of the cash cone, the ending balance faint above it
PILLAR:           2
TIER:             A
AWARENESS STAGE:  solution-aware
CTA:              The free course at hubricon.com/learn, where the method and the worksheet are written out in full
SPIKY CLAIM:      The ending balance is the least useful number on your cash forecast. A business is killed by the lowest point on the path, and growth makes that point deeper while making every number you watch look better.
MISCONCEPTION:    Revenue is up, the month closed profitable and the balance is healthy, so cash is fine. If it gets tight I'll see it coming in the bank account.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{end_p50}}. That's where the cash on this demo catalogue lands after {{horizon_days}}, up from {{cash_on_hand}}. On the way there it passes through {{min_median}}. Nothing on the profit and loss shows you that, and it's the number that ends businesses.
2. {{min_p5_day}}. That's how far into the horizon this catalogue reaches its lowest cash, at {{min_median}}, inside a stretch that closes profitable. The balance you watch is the one at the end. The one that can kill you is the bottom.
3. {{wires_total}} leaves this catalogue in supplier wires over {{horizon_days}}, across {{wire_count}} of them, while the platform pays on a {{payout_cycle}} lag. That gap has a shape. The shape has a bottom, and you can find it before you reach it.

SCRIPT
[0:00] HOOK
  VO: {{end_p50}}. That's where the cash on this demo catalogue lands after {{horizon_days}}, up from {{cash_on_hand}}. On the way there it passes through {{min_median}}. Nothing on the profit and loss shows you that, and the low point is the number that ends businesses.
  VISUAL: kinetic: the ending balance lands, then the low point lands beneath it, the distance between them held
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the model, and almost every operator at this size runs it. Revenue is growing. The month closed profitable. The balance in the account looks like a balance you can work with. So cash is fine, and if it ever gets tight you'll see it coming, because you look at the account most mornings. That model has one assumption buried in it, and the assumption is that cash moves smoothly between the points where you check it. It doesn't. It moves in steps, on dates somebody else chose, and the steps out are earlier than the steps in.
  VISUAL: screenshot: the bank balance on a phone, checked in the morning (a real screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: This is the demo catalogue. {{demo_brand}}, {{demo_label}}, {{n_skus}} products. It starts with {{cash_on_hand}} and carries {{monthly_fixed_costs}} of fixed costs a month. Over {{horizon_days}} it ends at {{end_p50}}, so it grew, and every monthly statement in that window is healthy. Now the part the statements can't show. The lowest the balance gets on the way is {{min_median}}, and it gets there on {{min_p5_day}}. That bottom is not a bad month. It sits inside the good ones.
  VISUAL: cash_cone: the balance over the horizon, the ending point marked, then the low point marked far beneath it
  DATA SOURCE: cash horizon on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — INTUITION
  VO: Why there's a bottom at all. You pay for goods when the supplier says so, and you get paid when the platform says so, and those are different calendars. Here the platform settles on a {{payout_cycle}} lag. So every unit you sell is money you've already spent and haven't yet received. Now add the lumps. Over this horizon there are {{wire_count}} supplier wires, {{wires_total}} in total, and they don't arrive evenly — the largest is {{largest_wire}}, for {{largest_wire_sku}}, leaving on {{largest_wire_day}}. Stack those against a settlement that's always running behind, and the balance doesn't glide. It falls in steps, refills slowly, and finds a bottom somewhere nobody chose. Growth makes it deeper, not shallower, because growth means ordering more inventory earlier, which pulls the wires forward and pushes the receipts back. That's the thing you're looking for, and now it has a name. The cash trough.
  VISUAL: cash_cone: the wires drawn as steps down, the settlements as slower steps up, the trough forming between them
  DATA SOURCE: cash horizon on Tarnhollow demo data
  CLIP: yes

[2:45] CHAPTER 2 — THE TURN
  VO: Here's where a careful operator still gets it wrong. He builds the forecast as one line. One line gives you one trough, and that trough is a guess wearing a decimal point. Demand isn't a line; it's a range, and the products move together, which makes the range wider than it looks. The correlation across these products is {{demand_corr}}, so a soft month is soft nearly everywhere at once. So run it many times instead. {{n_paths}} paths, each with its own demand draw, the same wire calendar underneath. Then read the bottom of each path, not the end of it. On this catalogue the trough at the bad end is {{trough_p5}}, and the average of the worst paths is {{trough_es}}. Look at how close those sit to the middle one, {{trough_median}}. That tells you something specific: this trough isn't being driven by demand at all. It's the wire calendar, and a wire calendar is something you can negotiate. The share of paths that ran out of money is {{p_ruin}}, with a simulation error of {{p_ruin_se}}. Which doesn't mean it can't happen. It means no path in {{n_paths}} did, and the honest reading of that is a bound, not a promise.
  VISUAL: paths: the simulated balances drawn faintly, the band around them, the trough percentiles lit at the bottom
  DATA SOURCE: cash horizon paths on Tarnhollow demo data
  CLIP: yes

[4:00] WHAT TO DO
  VO: Build it this week, in a spreadsheet. First, a dated list of money out: every supplier wire with the date it actually leaves, plus rent, payroll and the rest of the fixed costs. Second, money in, lagged by your platform's settlement cycle, not booked on the day of the sale. Then vary the demand. Even a crude version works: run the sales line at your good case, your normal case and a bad one, and keep the wire dates fixed, because the wires don't care what demand did. Then read the minimum of each line, not the ending balance. The lowest of those minimums is your planning number. Set your floor above it, and when it's too close, move a wire before you move a price. A supplier who takes payment a fortnight later changes the bottom of the curve more than a promotion ever will.
  VISUAL: kinetic: the steps landing one at a time, then chapter_card: the minimum of each line circled, the ending balances crossed out
  TEMPLATE: the cash trough worksheet in the free course — the dated outflows, the lagged receipts, and the minimum read off each line
  CLIP: no

[4:45] THE HONEST LIMIT
  VO: What you can do yourself is the dated calendar and a handful of demand cases, and it's the highest-value afternoon on this list, because it's the one that tells you whether you can take the next purchase order at all. What you can't do by hand is the width of it. Demand that moves together across {{n_skus}} products, supplier lead times that slip by a week and move a wire with them, the correlation between a soft month and a late container, and the whole thing re-run every week as orders land. A handful of cases gives you a shape. It doesn't give you the bad end, and the bad end is the one you're planning against. That part is a model. The calendar is still worth building tomorrow, because most of the fix is in the dates. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the closing line, held
  CTA: The method is written out in full, with the worksheet, free at hubricon.com/learn.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:55, 2:35, 2:45, 3:25, 4:00, 4:40, 4:45, 5:25, 6:00 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the ending balance is the least useful number on your cash forecast" · X thread spine: the settlement lag, the wire calendar, the trough, the bad end of it · newsletter section: move a wire before you move a price · clips at 0:00, 0:45, 1:15, 2:45
