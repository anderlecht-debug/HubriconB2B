TITLE:            Why {{service_level_default}} service level is wrong for most of your SKUs
THUMBNAIL:        {{service_level_default}} in ink as a single flat line across the newsvendor curve fragment, every product's own level scattered above and below it
PILLAR:           2
TIER:             B
AWARENESS STAGE:  solution-aware
CTA:              The free course at hubricon.com/learn, where the method and the worksheet are written out in full
SPIKY CLAIM:      The default service level is a convention, not a calculation, and it is wrong in both directions at once on the same shelf. Worse, it promises something other than what you think it promises, and it makes a per-product promise about a risk that arrives catalogue-wide.
MISCONCEPTION:    I run a high service level across the catalogue, so I'm covered almost all of the time and the occasional stockout is bad luck rather than a setting.
RUNTIME:          9–10 min

HOOKS (three, pick one)
1. {{service_level_default}}. That's the service level nearly every inventory tool defaults to and nearly every spreadsheet copies. On this demo catalogue the level each product's own margins justify runs from {{nv_fractile_min}} to {{nv_fractile_max}}. The default is right for almost none of them.
2. {{nv_skus_below_95}}. That's how many products on this demo catalogue carry more stock than their own economics justify, because of a figure somebody typed once as a default. The fees on stock held past that point run {{nv_bleed_month}} a month.
3. {{panel_p95_correlated}}. That's how many products here can be out of stock at once at the bad end, against {{panel_p95_independent}} if they failed separately. Your service level is a promise made product by product. The risk doesn't arrive that way.

SCRIPT
[0:00] HOOK
  VO: {{service_level_default}}. That's the service level nearly every inventory tool defaults to, and nearly every spreadsheet copies from the tool. On this demo catalogue the level each product's own margins justify runs from {{nv_fractile_min}} to {{nv_fractile_max}}, and the default is right for almost none of them.
  VISUAL: kinetic: the default lands as a flat line, then each product's own level scatters above and below it
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the model, and it's the one the software hands you. There's a setting called service level. You set it high, because being out of stock is the worst thing that happens to a listing, and high means covered. Maybe you nudged it up once after a bad month. From then on it's the same number across the shelf, it's a high number, and it quietly means you're fine. Nothing about that is lazy. The setting exists, it has a sensible default, and changing it per product sounds like the kind of fiddling that makes a system worse. The trouble is in what the setting actually promises, and in the fact that the default was never a statement about your products at all.
  VISUAL: screenshot: the service level field in an inventory tool, set once and left (a real screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:50] THE CRACK
  VO: Start with what the number promises, because it isn't what it sounds like. A service level set this way is the chance of getting through one replenishment cycle without running out. It is not the share of demand you fill. Those are different measures, and the gap between them is widest exactly where it hurts: when you do run out, you run out at the end of the cycle, in the busiest stretch, having already sold through the easy part. So a high cycle number can sit alongside a meaningful share of demand that went unfilled, and the setting will still read as healthy. Now the second part. That default is a convention from a textbook, not a calculation about your catalogue. On this demo catalogue, {{demo_brand}}, {{demo_label}}, {{inv_skus}} products, the level each product's own margins justify has a middle of {{nv_fractile_median}} and runs from {{nv_fractile_min}} to {{nv_fractile_max}}. A single flat setting lands above some of those and below others, which means the same number is overfeeding one end of your shelf and starving the other, at the same time, for the same reason.
  VISUAL: newsvendor: the justified level for every product plotted against the flat default, the ones above and the ones below lit in turn
  DATA SOURCE: NEWSVENDOR on Tarnhollow demo data
  CLIP: yes

[1:30] CHAPTER 1 — FIND IT
  VO: So where does a product's own number come from? From the only comparison that matters: what being short costs you against what being long costs you. Being short costs the margin you don't earn, plus the rank you lose and the advertising you'll buy to get it back. Being long costs storage for a cycle, the capital tied up, and the markdown risk if it ages. Take the cost of being short, divide it by the cost of being short plus the cost of being long, and that fraction is the share of the time you should be able to cover. That's the whole derivation, and the episode on sizing a purchase order works it through on a named product, free, on the same page as this one. What matters here is what it does to the default. Run it across this catalogue and {{nv_skus_below_95}} products come out below the flat setting — their stockouts are cheap relative to the cost of holding them, so the honest answer is to carry less and take the occasional miss. Others come out above it, and on those the setting has been quietly rationing a product whose stockouts are expensive. Now find your own version. You need, per product: the landed cost, the margin after the platform's fees, the storage cost for a cycle, and an honest figure for what a stockout does to rank and to the ads you'd buy afterwards. That last one is the number everyone leaves blank, and leaving it blank is not neutral. It is the same as entering nothing, which makes every product look like its stockouts are free, which is exactly the assumption that produces a flat setting in the first place.
  VISUAL: newsvendor: the cost of being short and the cost of being long, the ratio between them resolving into a level, then the catalogue's levels landing around the flat default
  DATA SOURCE: NEWSVENDOR on Tarnhollow demo data
  CLIP: yes

[3:40] CHAPTER 2 — VERIFY IT
  VO: Here's the part the setting cannot express, whatever you set it to. A service level is a promise made one product at a time. Your actual risk doesn't arrive one product at a time. A soft season is soft across most of the shelf at once; a late container is late for everything inside it; a supplier who slips slips for every product you buy from them. The demand correlation across this catalogue is {{demand_corr}}, which is a long way from products moving independently. So the shelf has to be read together rather than product by product. One product's own chance of being out is {{inv_method}}: the orders arrive as counts, the lead time has a spread of its own, and the odds are swept across every value that spread allows rather than drawn at random. The shelf has to be drawn, though, because what you want is how many are out at once, and that depends on how they move together. Draw it here and the catalogue expects {{panel_expected_stockouts}} products out of stock inside the same lead time, with a bad end of {{panel_p95_correlated}}. Now run the same shelf pretending the products are independent, and that bad end reads {{panel_p95_independent}} instead. The direction of that error is the point. Assuming independence always makes the shelf look safer than it is, and the gap widens as your products move together. Which means a per-product setting, however carefully chosen, is answering a question you didn't ask. You don't care how often one product is out. You care how often enough of them are out at once that the month breaks, and that's a catalogue-level number that no per-product field can hold.
  VISUAL: paths: simultaneous stockouts across the catalogue, correlated against independent, the bad end of each marked
  DATA SOURCE: INVENTORY.PANEL on Tarnhollow demo data
  CLIP: yes

[5:50] WHAT IT'S WORTH
  VO: Put figures on both directions. Overfed first, because it's the invisible one. The fees on stock held past what its own economics justify run {{nv_bleed_month}} a month on this catalogue, and {{nv_skus_below_95}} products are sitting on cover their own margins don't support. That's a recurring cost with no invoice attached, and it's also cash: every unit of it was paid for by a wire that left before the sale arrived. Starved next. {{n_skus_stockout_gt_20}} products here carry a real chance of running out inside their own lead times, and {{stockout_worst_sku}} is close to certain at {{stockout_worst_p}}, on {{stockout_worst_cover}} of cover against a {{stockout_worst_lead}} lead time. A flat high setting did not prevent that, which is the clearest evidence available that the setting is not the safeguard it feels like. And the number of orders the economics actually justify placing right now on this shelf is {{nv_econ_orders}}, out of {{inv_skus}} products — the answer is neither "order everything" nor "order nothing", and a flat rule can't produce a list like that.
  VISUAL: waterfall: the monthly fee bleed on the overfed side; then newsvendor: the starved products lit with their cover against their lead times
  DATA SOURCE: NEWSVENDOR on Tarnhollow demo data; INVENTORY.PANEL on Tarnhollow demo data
  CLIP: yes

[7:50] WHAT TO DO
  VO: This week. First, find the service level setting in whatever tool you use and write down what it's set to, because a surprising number of operators have never looked. Second, write the cost of a stockout for your top products, including the rank and the advertising to recover it. Rough is fine; blank is not. Then take the ratio for each of those products and compare it with the setting. Where the product's own answer is below the setting, you've been paying to hold stock that doesn't earn it, and the fix is to cut cover and accept the occasional miss. Where it's above, raise it, and expect the wire to be bigger. Then the catalogue check: list the products that share a supplier, a container or a season, and ask what happens if that group is late together, because that's your real exposure and no per-product setting will show it to you. Last, write down what you expect the change to do before you make it. Cover days, stockouts, the fee line. Then read it next month against what you wrote, not against how it felt.
  VISUAL: kinetic: the steps landing one at a time; then chapter_card: the single setting crossed out, a column of per-product levels beside it
  TEMPLATE: the service level worksheet in the free course — the cost of short, the cost of long, the ratio, and the group exposure check
  CLIP: no

[9:30] THE HONEST LIMIT
  VO: What you can do yourself is the comparison, on your top products, in an afternoon. Find the setting, cost both sides, take the ratio, and change the ones that are clearly wrong. That alone will beat a flat default, and it costs you nothing but the afternoon. What you can't do by hand is the catalogue-level answer. That needs every product's demand simulated together with its correlations intact, lead times that slip, suppliers that slip as a group, and the whole thing re-run as orders land and seasons turn — a shelf of {{inv_skus}} products drawn together, with each product's own odds computed exactly underneath it, is not a spreadsheet exercise, and the number you most want, how often enough products are out at once to break a month, is precisely the one that needs it. That part is a model. The afternoon is still worth more than the setting you have now. You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the closing line, held
  CTA: The method is written out in full, with the worksheet, free at hubricon.com/learn.

RE-HOOK AUDIT: 0:00, 0:15, 0:50, 1:30, 2:10, 2:50, 3:30, 3:40, 4:20, 5:00, 5:40, 5:50, 6:30, 7:10, 7:50, 8:30, 9:10, 9:30, 10:10 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the default service level is a convention, not a calculation" · X thread spine: what the setting promises, what it does not promise, the spread of justified levels, the shelf failing together · newsletter section: leaving the cost of a stockout blank is not neutral · clips at 0:00, 0:50, 1:30, 3:40, 5:50
