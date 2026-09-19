TITLE:            Contribution margin vs gross margin — the one that actually matters
THUMBNAIL:        {{gross_vs_contribution_gap}} in amber over the waterfall fragment, the fee step and the ad step lit
PILLAR:           5
TIER:             B
AWARENESS STAGE:  problem-aware
CTA:              The course page at /learn, where the method is written out in full; no service mention
SPIKY CLAIM:      Gross margin is a number for your supplier's benefit, not yours. The only margin a product has is what's left after the platform and the ads take theirs.
MISCONCEPTION:    Gross margin is my margin. Revenue minus cost of goods is what each product earns, and fees and ads are overhead.
RUNTIME:          9–10 min

HOOKS (three, pick one)
1. {{gross_pct_latest}} gross margin. {{contribution_pct_latest}} after the platform and the ads. You'd say the first number is your margin and the rest is overhead. The gap between them is {{gross_vs_contribution_gap}} of revenue, and it's decided product by product, not in overhead.
2. {{gross_vs_contribution_gap}} of revenue. That's how far this catalog's gross margin sits above the margin it keeps, once the platform and the ads are paid. You'd call that overhead. It isn't, and treating it that way is why the bestseller looks better than it is.
3. {{fees_latest}} in platform fees last month, on {{rev_latest}} of sales. Gross margin never saw it. Contribution margin does, and it's the only margin that tells you which product to reorder.

SCRIPT
[0:00] HOOK
  VO: {{gross_pct_latest}} gross margin. {{contribution_pct_latest}} after the platform and the ads. You'd say the first number is your margin and the rest is overhead. The gap between them is {{gross_vs_contribution_gap}} of revenue, and it's decided product by product, not in overhead.
  VISUAL: kinetic: the gross figure lands, then the contribution figure under it, then the gap between them
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the model. Revenue minus what the goods cost you is the margin. That's the number on the product tab of your own spreadsheet, it's the number the supplier negotiation is about, and it's the number you'd quote if someone asked how good a product is. Fees and ads are real, but they're the cost of doing business, so they live in overhead, below the line, spread across everything. It's a fair model. It's how the accounts are laid out, and for a business with one product it's even correct. The trouble starts the moment there's more than one product, because from then on the fees and the ads are not spread. They're charged.
  VISUAL: kinetic: the gross margin line in the viewer's own words (a real spreadsheet screenshot replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: Here's the demo catalog on screen. {{demo_brand}}, {{demo_label}}, {{n_skus}} products, about {{annual_revenue_m}} a year. Last month, {{rev_latest}} of sales. Landed cost of goods, {{cogs_latest}}. So the gross margin is {{gross_pct_latest}}. Healthy. Now watch the waterfall. Platform fees: {{fees_latest}}, which is {{fee_share_latest}} of revenue. Ads, allocated to the products that spent them: {{ads_latest}}. What's left is {{net_latest}}, and that's {{contribution_pct_latest}} of revenue. The gap between the margin you quote and the margin you keep is {{gross_vs_contribution_gap}} points of revenue. And none of it is overhead. Every dollar of it was charged to a specific product on a specific order, and the platform's own report says which.
  VISUAL: waterfall: revenue, then landed cost, then fees, then ads, then what's left, each step landing as it's spoken
  DATA SOURCE: MARGIN.DECOMP on Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — FIND IT
  VO: Find it in your own reports. Start with the settlement report, the one the platform sends when it pays you. Every fee is on it, by order, by product: the referral fee, fulfilment, storage, refund administration, and the advertising invoice if it's netted from the payout. That is your fee line, and it's per product, not per business. Next, the advertising report, by campaign and by product. Sponsored spend belongs to the product that was advertised. Where a campaign covers several products, allocate its spend by the sales the campaign produced for each of them, not by each product's share of catalog revenue, because revenue share hands the bestseller's ad bill to the products that never needed ads. On this catalog, {{ad_bleed_month}} a month goes to search terms with no attributed sales at all. That's a cost with no sale to carry it, and it lands on whichever product the campaign belongs to. Then the landed cost sheet. Unit cost, inbound freight, packaging, duty. Not the invoice price; the price of the unit sitting in the warehouse. Put those side by side, per product, and the number falls out: price, less landed cost, less the fees on that product, less the ads on that product. Now it has a name. That's contribution margin. It's what the product contributes toward everything that isn't a product: salaries, rent, software, you. Gross margin stops before the platform. Contribution margin stops where your money actually starts.
  VISUAL: kinetic: the report names landing one at a time; then waterfall for a single product, each report feeding its own step
  DATA SOURCE: MARGIN.DECOMP on Tarnhollow demo data; SPEND.RESPONSE on Tarnhollow demo data for the unattributed spend
  CLIP: yes

[3:30] CHAPTER 2 — VERIFY IT
  VO: Now verify it on the product you're proudest of. The bestseller here is {{bestseller_sku}}. {{bestseller_revenue}} of revenue last month, {{top_sku_share}} of the catalog. On gross margin it looks like the whole business. On contribution it earns {{bestseller_net}}, a margin of {{bestseller_net_pct}}, and by contribution it ranks {{bestseller_rank_by_net}} in the catalog. So on this catalog the bestseller survives the test. That's not the usual outcome, and the point is you cannot know until you've run it. The product at the bottom by contribution is {{worst_net_sku}}, at {{worst_net_pct}}. The count of products losing money after ads this month, on this catalog, is {{n_skus_negative_net}}. Had it been anything else, gross margin would have hidden it, because a product can carry a fine gross margin and a negative contribution at the same time. All it takes is a fee tier or an ad campaign that eats the difference, and neither of those shows up in revenue minus cost of goods. The spread across the catalog runs from {{worst_net_pct}} to {{best_net_pct}}. Same catalog, same supplier, same gross margin logic, and the products sit that far apart once the platform and the ads are charged to the product that incurred them. That ranking, by contribution, is the only ranking that should decide a reorder, a price move or an ad budget.
  VISUAL: waterfall: the bestseller alone, revenue to contribution; then kinetic: the catalog ranked by contribution with the top and bottom named
  DATA SOURCE: MARGIN.DECOMP on Tarnhollow demo data
  CLIP: yes

[5:30] WHAT IT'S WORTH
  VO: What's the difference worth? Every decision that used the wrong margin. Reorders first. A product with a high gross margin and a thin contribution gets restocked deep, and the cash sits on a shelf. The newsvendor on this catalog finds {{nv_bleed_month}} a month of fees on stock ordered past its economic quantity. Ads next. The break-even return on ad spend is set by contribution, never by gross. On this catalog it's {{ad_breakeven_roas}}. The worst campaign, {{ad_worst_campaign}}, returns {{ad_worst_marginal_roas}} on its last dollar, which is below break-even at contribution and looks perfectly healthy if you judge it at gross. Pricing. A price rise on a product with a fee tier in the way can lift gross margin and cut contribution in the same move, and only the contribution waterfall shows it. And concentration. There are {{n_skus}} products on the shelf, but by where the money comes from the catalog behaves like {{effective_skus}}, so the risk of the business sits in fewer products than the shelf suggests. In short: the margin you quote and the margin you keep are {{gross_vs_contribution_gap}} of revenue apart on this catalog, and every reorder, bid and price set on the wrong one was set on a number that's wrong by that much.
  VISUAL: kinetic: reorders, ads, pricing, concentration as chapter cards; waterfall fragment for the ad break-even
  DATA SOURCE: NEWSVENDOR on Tarnhollow demo data; SPEND.RESPONSE on Tarnhollow demo data; risk on Tarnhollow demo data
  CLIP: yes

[7:30] WHAT TO DO
  VO: This week. First, build the waterfall for your top products. Price, landed cost from the cost sheet, fees from the settlement report, ads from the campaign report allocated by attributed sales. One row per product, and the last column is contribution. Next, rank by that column. Not by revenue, not by gross. Read the bottom of the list before the top, because the bottom is where the decisions are. Then set your break-even return on ad spend from contribution and hold every campaign to it, starting with the one that returns least on its last dollar. Last, take gross margin off the dashboard. Keep it for the supplier conversation, where it belongs, and put contribution where you look every morning. When a product looks better on gross than on contribution, that gap is the platform and the ads, and it's per product, so it's yours to fix per product.
  VISUAL: kinetic: the steps landing one at a time; the ranked table with the bottom rows lit
  TEMPLATE: none yet for this pillar; the CTA points at the course page

[9:00] THE HONEST LIMIT
  VO: What you can do yourself is the waterfall for your top products, this week, from reports you already export. It's an afternoon, and it changes what you reorder. What you can't do by hand is the allocation at scale. {{n_skus}} products, every fee line on every order, ads allocated by attributed sales across campaigns that overlap, every month, with the fee tiers rechecked whenever a weight or a price moves. Done by hand it drifts back to revenue share inside a few months, and revenue share is gross margin wearing a different name. That part is a model. What you can do today is stop quoting gross margin as if it were yours. Rank by contribution, and read the bottom of the list.
  VISUAL: kinetic: the closing line
  CTA: The course page at /learn, where the method is written out in full.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:25, 3:00, 3:30, 4:05, 4:40, 5:15, 5:30, 6:05, 6:40, 7:15, 7:30, 8:05, 8:40, 9:00, 9:35 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "gross margin is a number for your supplier" · X thread spine: {{gross_pct_latest}} quoted, {{contribution_pct_latest}} kept, {{gross_vs_contribution_gap}} of revenue between them · newsletter section: allocate ads by attributed sales, never by revenue share · clips at 0:00, 0:45, 1:15, 3:30, 5:30
