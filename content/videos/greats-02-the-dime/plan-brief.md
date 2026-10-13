# Plan brief: greats-02-the-dime

Narration 1724.7 s. Everything you need is here.

## The rules (the shot-plan skill)

# shot-plan

Input: a `slug` whose script is approved. Output: `content/videos/<slug>/shots.json` that
`hubricon-content shots-validate <slug>` passes. You decide what the viewer sees; the tools copy
the times, the words and the figures.

Read once a session: `docs/content/VISUAL_SPEC.md` §3 (the two rooms), §4 (cadence), §5 (screen
time), §6.1–6.2 (what a world shot may show), §7.3 (the schema) and §14 (the styles). The numbers
the validator holds you to are in `content/film/styles.json`.

## Never

- Edit `script.md`, `facts.json` or the timing. The script is the founder's.
- Put a number in the world room. A number, a comparison or a mechanism goes to paper.
- Show a named company, person, place or event with stock or AI (§6.2): archival with that name
  in its provenance, or paper.
- Query a cliché (§6.1): handshakes, suits, laptops or phones with charts, tickers, cash, piggy
  banks, light bulbs, chess, puzzles, rockets, skylines, smiling people at desks, whiteboards,
  sticky notes, glowing particles or networks.

## Steps

1. **Timing.** Use `timing.json`. Before narration exists, run
   `hubricon-content timing <slug> --estimate` (writes `timing.estimate.json` at 150 words a
   minute; it never replaces a real timing). Its `cutpoints` are the only places a cut may fall.
2. **Mode.** `explainer` when the film teaches the method and the engine's models; `history` when
   it tells the story of real companies and people. The mode sets the screen-time ranges (§5).
3. **Walk the beats, sentence by sentence.** For each sentence decide the room by the rule *a
   number, a comparison or a mechanism goes to paper; a thing, a place or a moment goes to the
   world*. Then pick its style with the table below, reaching for a sequence where a run of
   sentences fits one. Group sentences into shots of 7 to 11 s (3 s at least, 14 s at most; a chart
   up to 30 s with something new every 8 s), cutting at sentence ends. The first minute is quicker:
   median 6 s or less, nothing over 8 s.
4. **Write each shot** (ids `s001`, `s002`, …) with `start` and `end` (close to a cutpoint; the fill
   step snaps them), `beat`, `room`, `kind`, `style`, `on`, `params`, `intent` (one line: what the
   viewer sees and why it fits these words), and:
   - a world shot or an archival paper shot: `query` (one or two literal queries made of the
     sentence's concrete nouns, e.g. `"container port gantry cranes daylight wide"`), `sources`
     (`pexels`, `pixabay`; archival: `loc`, `smithsonian`, `commons`, `archive`, `nara`;
     a texture: `higgsfield`), `fallback` (archival → stock → texture → `paper:kinetic`);
   - a texture: `"overlay": {"illustration": true}`;
   - a sentence naming a real company, person, place or event: `"specific": "<the name>"`;
   - a chart style: `"chart": {"scene": "<staircase|montecarlo|aging|waterfall|cash_cone|…>"}` and,
     past 14 s, `params.builds` (the seconds where something new lands);
   - `on`: the word, or `{{key}}`, the style's main event lands on (§14.1). Leave it `null` for
     styles without one (`kinetic-thesis`, `chapter`, `footage-establish`, …).
5. **Fill:** `hubricon-content shots-fill <slug>` snaps every cut to the nearest legal one and
   writes `says`, the reveals (paper only) and the labels from the timing and the facts.
6. **Validate:** `hubricon-content shots-validate <slug>`. Fix every problem it names by changing
   the plan (move a cut, change a style, move a figure to paper) and fill again. Stop when it prints
   `clean`.

## What the first Greats film taught (2026-10-06)

- **Picture first.** Aim for at least 45% of the runtime led by a picture (footage, a still, a framed
  photograph, a stack, a split). A sentence with no figure is a chance for the world: never leave
  more than about 45 s of paper in a row when one of its sentences carries no figure.
- **`specific` is for a name the sentence says.** Tag a shot only when the voice names that
  particular company, person, place or event ("Sears", "Batavia, Ohio", "the Joint Committee").
  A generic noun ("a country post office", "an express wagon", "a farmer") is not specific: query
  it from the archival libraries without the tag, or the record filter refuses every good photograph
  that does not repeat the word.
- **Archival queries are file titles.** Write the words a Wikimedia Commons or LOC file title would
  carry ("Rural free delivery wagon", "Sears Roebuck plant Chicago 1906", "farmer plowing horses"),
  not the sentence.

## The picker (VISUAL_SPEC.md §14.2)

| The sentence… | First choice | Second choice | Never |
|---|---|---|---|
| cites a rule, fee, schedule, filing or published line | `doc-highlight` | `table-scan` | a stock shot |
| locates something in a list or schedule | `table-scan` | `doc-highlight` | |
| states one figure or range | `number-land` | `range-band` | footage with a number over it |
| compares two figures | `number-pair` | `counterfactual` | |
| says what one small change would cost or save | `counterfactual` | `number-pair` | |
| explains a mechanism or a relationship | `chart-build` | `formula-build` | |
| defines a quantity by its parts | `formula-build` | `chart-build` | |
| is a forecast, an estimate, uncertainty | `range-band` | `number-land` with "estimate" | a single line |
| gives a share of a countable set | `unit-grid` | `number-pair` | |
| names dated events or an order of events | `timeline` | `doc-clipping` | |
| refers to a dated public event or report | `doc-clipping` | `archive-framed` | |
| names a real historical person, place or company | `still-push` on archival | `archive-framed` | stock, AI |
| lists several real examples | `archive-stack` | `still-pan` | stock, AI |
| contrasts then and now | `split-then-now` | two `archive-framed` | |
| describes a place or opens a chapter | `footage-establish` | `still-pan` | a generic skyline |
| describes a physical process | `footage-process` (three shots: wide, medium, detail) | `footage-insert` | |
| names a small physical object | `footage-insert` | `still-reveal` | |
| moves from a detail to the whole | `still-reveal` | `still-pan` | |
| reasons for 10 s or more with no new noun or number | `footage-observe` | `texture` | a frozen frame |
| is abstract, with no concrete noun | `kinetic-thesis` (the chapter's claim) | `texture` | stock clichés |
| is the chapter's central claim | `kinetic-thesis` | | |
| quotes a dated source verbatim | `quote` | `doc-clipping` | paraphrase in quote marks |
| explains how Hubricon counts a dollar | `receipt` | `doc-highlight` (the terms) | |
| follows a big reveal | `breath` (only where the narration pauses) | | |
| resolves something set up earlier | `callback` (`params.callback`: the earlier shot) | | |

`still-depth` waits for its build after the visual trial; do not plan it yet.

## Sequences (VISUAL_SPEC.md §14.6)

1. **Evidence run** (explainer, ~50 s): `footage-establish` 8 → `footage-process` 12 →
   `doc-highlight` 10 → `chart-build` 14 → `number-land` 6.
2. **History open** (history, ~70 s): `still-push` 10 → `doc-clipping` 8 → `archive-stack` 12 →
   `timeline` 16 → `split-then-now` 10 → `kinetic-thesis` 7.
3. **Counterfactual reveal** (~40 s): `footage-insert` 4 → `table-scan` 10 → `counterfactual` 14 →
   `number-pair` 8 → `breath` 2.
4. **Honest limit** (~35 s): `range-band` 14 → `unit-grid` 10 → `footage-observe` 12.
5. **Chapter turn** (~14 s): `breath` 2 → `chapter` 2.5 → `footage-establish` 8.
6. **Return** (the end, ~25 s): `callback` 12 → `kinetic-thesis` 6 → `end` 6.

## Variety the validator enforces (§14.8)

At least 10 styles in any 20 minutes; no style over 15% of the runtime (`chart-build` 25%,
`texture` 8%); never one style three shots running (a process sequence counts once); one
`kinetic-thesis` per three minutes, one `footage-observe` per 90 s, one `breath` per two minutes;
one `match-bridge` per chapter; no two textures together; at most two inserts together; at most
three shots of one kind in a row; a world run of 90 s and a paper run of 120 s at most; a change of
texture (a chapter card, a document, a number) at least every three minutes.

## The plan fields the v3 stage honours (times are seconds from the shot's first frame)

| Kind | Field | Meaning |
|---|---|---|
| document | `lines`, `line`, `source` | The page's lines (verbatim from a real source, or "Typeset from …" in `source`); `line` is the one the camera reads. |
| document | `visits: [{text, at, mark}]`, `opening: "page"\|"tight"` | Camera waypoints on phrases printed on the page (`mark: true` swipes the highlighter); open on the whole page or tight. |
| table | `rows`, `columns`, `row`, `cell`, `type_values` | A typeset table; `type_values: true` types each cell on its word. |
| number | `value` (`{{key}}`), `sub`, `estimate` | One hero figure and a context line. |
| pair | `left`/`right` `{value, label, at}`, `gap`, `gap_at`, `question` | Two figures to compare; `gap` is the line under them. |
| formula | `terms: [{text, at}]`, `ops`, `caption` | A sum drawn term by term on its words. |
| timeline | `layout: "dates"\|"bars"\|"share"\|"ledger"\|"step"`, `events: [{date, label, at}]`, `heading` | Only `dates` is a line in time; `bars` are quantities to scale; `step` is prices or weights on either side of an edge. |
| chart | `chart: {"scene": …}`, `params.builds` | A case-study chart (`staircase`, `staircases`, `aging`, `waterfall`, `montecarlo`, `catalogue`); `builds` = seconds when something new lands. |
| quote, kinetic | `text` / `lines`, `attribution` | Words land on their onsets. |
| still | `enter: "dive"`, `exit: "surface"`, `focus: [x, y]`, `motion` | A full-frame picture; dive in from a print on the desk, surface back to one. |
| archive | `focus`, `params.trim`, `params.treat: "object"` | A print or a museum object on the desk. |
| number, pair, formula, kinetic, timeline | `params.print: {want, at, caption}` | A companion picture on the desk beside the type: give it whenever the type would stand alone. |
| any | `style: "callback"`, `params.callback: "<shot id>"` | Draw an earlier shot again; it continues that shot's layout. |

## Styles (name: kinds · room · seconds)

- `archive-framed`: archive · paper · [3, 14]
- `archive-stack`: stack · paper · [6, 14]
- `bars-recall`: timeline · paper · [3, 8]
- `breath`: footage, still, texture, chart, number, pair, grid, kinetic, formula, document, table, timeline, receipt, archive, stack, split, quote · either · [1.5, 2]
- `breathe-hold`: still, footage · world · [12, 25]
- `callback`: chart, number, pair, grid, kinetic, formula, document, table, timeline, receipt, archive, stack, split, quote · paper · [4, 30]
- `chapter`: chapter · paper · [2.5, 2.5]
- `chart-build`: chart · paper · [4, 30]
- `counterfactual`: chart · paper · [4, 30]
- `doc-clipping`: document · paper · [4, 14]
- `doc-highlight`: document · paper · [5, 14]
- `end`: end · paper · [4, 10]
- `footage-establish`: footage · world · [6, 10]
- `footage-insert`: footage · world · [3, 5]
- `footage-observe`: footage · world · [10, 14]
- `footage-process`: footage · world · [3, 5]
- `formula-build`: formula · paper · [4, 14]
- `kinetic-thesis`: kinetic · paper · [3, 10]
- `match-bridge`: footage · world · [3, 14]
- `montage-cut`: still, footage · world · [2, 3]
- `number-land`: number · paper · [3, 14]
- `number-pair`: pair · paper · [5, 14]
- `quote`: quote · paper · [3, 14]
- `range-band`: chart · paper · [4, 30]
- `receipt`: receipt · paper · [5, 14]
- `split-then-now`: split · paper · [5, 14]
- `still-pan`: still · world · [7, 14]
- `still-push`: still · world · [3, 14]
- `still-reveal`: still · world · [4, 14]
- `table-scan`: table · paper · [5, 14]
- `texture`: texture · world · [6, 10]
- `timeline`: timeline · paper · [5, 30]
- `unit-grid`: grid · paper · [4, 14]

## The figures the voice says ({{key}} = value: label)

- `{{annual_revenue_m}}` = $3.5M: trailing twelve-month revenue, in millions
- `{{contribution_pre_ads_pct}}` = 38.5%: contribution margin after landed cost and fees, before ads, latest month
- `{{demo_brand}}` = Tarnhollow: the demo brand's name
- `{{demo_label}}` = demo data: the label every demo figure carries
- `{{el_ci_crosses}}` = crosses zero: its interval reaches no effect of price at all
- `{{el_ci_high}}` = 0.35: upper bound of its ninety-five percent interval
- `{{el_ci_low}}` = -5.87: lower bound of its ninety-five percent interval
- `{{el_min_periods}}` = 5: periods the fit needs before it will speak
- `{{el_min_price_cv}}` = 2%: price movement the fit needs before it will speak
- `{{el_no_top}}` = 22: fitted SKUs whose range is too wide for the engine to name a best price
- `{{el_own_weight}}` = 17%: the weight its own points carry against the catalogue's common slope
- `{{el_p_optimal}}` = 97%: the model's probability that the catalogue's prices are already about optimal
- `{{el_periods}}` = 12: periods the example fit used
- `{{el_point}}` = -2.76: its elasticity point estimate
- `{{el_raw}}` = -7.35: the slope through its own points alone, before pooling
- `{{el_sku}}` = TH-OVEMIT-22: the worked elasticity example SKU
- `{{el_skus_fit}}` = 22: SKUs with a usable elasticity fit
- `{{el_skus_insufficient}}` = 2: SKUs the fit refused (too few periods or no price movement)
- `{{gross_pct_latest}}` = 70.7%: gross margin (revenue less landed cost), latest month
- `{{n_skus}}` = 24: SKUs in the demo catalogue
- `{{pm_step_cap}}` = 5%: the hard cap on any single price step
- `{{w_1917}}` = 1917: year
- `{{w_1918}}` = 1918: year
- `{{w_1919}}` = 1919: year
- `{{w_1927}}` = 1927: year
- `{{w_1930_quote}}` = A large quantity order and an improved production system has brought hundreds of higher-priced articles down to ten cents.: Sales Management, 1930
- `{{w_1932}}` = 1932: year
- `{{w_1936}}` = 1936: year
- `{{w_barnard_quote}}` = The five-and-dime industry is defunct and has been defunct for at least 25 years.: Kurt Barnard, retail consultant, July 1997
- `{{w_born}}` = 1852: Woolworth's birth year, near Rodman, New York
- `{{w_building_open}}` = April 24, 1913: the Woolworth Building opens
- `{{w_ceiling_1935}}` = 40 cents: the ceiling soon after the limits went
- `{{w_ceiling_1936}}` = $1: the price of some items by spring 1936
- `{{w_ceiling_span}}` = more than 50 years: from the dime's arrival as the ceiling (1880) to the 20-cent line (1932), in the company's eastern stores
- `{{w_chain_year}}` = 1922: Hayward & White's Chain Stores
- `{{w_charm_quote}}` = As soon as we added 10 cent goods to the line, we took away part of the 5 cent store's charm, the charm of finding only one price on a counter, and only one price in a store.: Woolworth, as the company's 1979 report quotes him ('he later wrote'; original not found)
- `{{w_china}}` = mostly china and glassware: the goods in the 1932 trial of a 20-cent line
- `{{w_clerks}}` = 7: clerks on the Lancaster opening day, in Woolworth's letter to his father ('I had 7 clerks'); the company's centennial report says 'his seven bustling clerks'
- `{{w_combination_quote}}` = For years we have sold so-called combination items for 10 cents each piece.: the 1932 report to stockholders
- `{{w_combination_term}}` = so-called combination items: the 1932 report's words for goods sold in pieces under the limit
- `{{w_cost}}` = $13.5 million: the building's cost
- `{{w_counter_order}}` = $100: the five-cent goods W. H. Moore ordered from Spelman Bros.
- `{{w_counter_quote}}` = I persuaded my employers to create a five cent cash counter with me in charge of it.: Woolworth, 1913
- `{{w_counter_year}}` = 1878: the five-cent counter at Moore & Smith
- `{{w_day1}}` = $127.65: Lancaster's first-day takings
- `{{w_day1_count}}` = 2,553: nickel purchases on Lancaster's first day (multiplies out to $127.65)
- `{{w_died}}` = April 8, 1919: Woolworth's death, at Glen Cove, Long Island
- `{{w_dustpan_cost}}` = $4.75 a gross: toy dustpans on the first store's cost list
- `{{w_dustpan_margin}}` = about 34%: what was left of the price on a toy dustpan (computed from the cost list: about 34%)
- `{{w_exit_date}}` = July 17, 1997: the company announces it is leaving the US Woolworth general merchandise business
- `{{w_exit_jobs}}` = 9,200: jobs, 1997
- `{{w_exit_stores}}` = about 400 stores: US Woolworth stores closed, 1997
- `{{w_first_wage}}` = $3.50 a week: Woolworth's first wage
- `{{w_five_and_ten}}` = five-and-ten: the name the stores took once the dime was added
- `{{w_footlocker}}` = November 1, 2001: the company renamed Foot Locker, Inc.
- `{{w_general_letter}}` = January 14, 1891: Woolworth's General Letter to store managers
- `{{w_gross}}` = 144: items in a gross
- `{{w_gross_value}}` = $7.20: what a gross brings in at five cents each (derived)
- `{{w_height}}` = 792 feet: the Woolworth Building's height
- `{{w_lancaster_date}}` = June 21, 1879: the Lancaster store opens (a Saturday)
- `{{w_letter_quote}}` = We could have sold $200 if the store had been larger.: Woolworth's letter to his father, June 22, 1879 (versions differ slightly)
- `{{w_lights}}` = 80,000: lights switched on at the opening
- `{{w_limits_removed}}` = 1935: all arbitrary price limits removed by the board
- `{{w_lower_costs_quote}}` = because of lower costs, our selling prices on many lines have been reduced: the company's 1932 report to stockholders
- `{{w_merger_stores}}` = 596 stores: stores at the merger
- `{{w_merger_year}}` = 1912: the merger that formed the F. W. Woolworth Co.
- `{{w_net_1917}}` = 9.43%: net earnings as a share of sales, 1917
- `{{w_net_1918}}` = 5.46%: net earnings as a share of sales, 1918
- `{{w_net_1919}}` = 7.89%: net earnings as a share of sales, 1919
- `{{w_new_ceiling}}` = 20-cent: the new ceiling, 1932
- `{{w_new_sign}}` = '5, 10 and 20 cent stores': what the president said the stores might become
- `{{w_office_rent}}` = $25 a month: desk room at 104 Chambers Street
- `{{w_office_year}}` = 1886: the New York buying office opens
- `{{w_owned_by}}` = 1914: by when Woolworth owned the building outright
- `{{w_parson_date}}` = February 1920: Printers' Ink on H. T. Parson
- `{{w_parson_quote}}` = would not under any circumstances even consider breaking away from the ten-cent barrier: Printers' Ink's report of H. T. Parson's declaration (reported speech, not his own words)
- `{{w_people_quote}}` = One of the first things I learned was that I could not expect people to come to me. I had to take my store to the people.: Woolworth, The World's Work, April 1913
- `{{w_pi17_ad}}` = Confining the price of goods to ten cents is fundamentally an advertising idea.: Printers' Ink, May 31, 1917
- `{{w_pi17_date}}` = May 1917: Printers' Ink on Woolworth's orthodoxy
- `{{w_pi17_orthodox}}` = Mr. Woolworth is the only one of the big people in this line who remains strictly orthodox so far as five-and-ten-cent goods are concerned. How long this will continue nobody but Woolworth knows.: G. A. Nichols, Printers' Ink, May 31, 1917
- `{{w_pi17_year}}` = 1917: Printers' Ink on the dime as advertising
- `{{w_promise_date}}` = January 25, 1933: the letter to stockholders in the 1932 report
- `{{w_promise_quote}}` = Fundamentally the Company is in the 5 and 10 cent business and has every intention of continuing that policy. Furthermore, there is no intention of going beyond the 20 cent selling price.: the 1932 report to stockholders, letter dated January 25, 1933
- `{{w_promise_span}}` = 3 years: from the January 1933 promise to the 1935 removal of all limits
- `{{w_quarter_test}}` = 25 cents: the higher price Woolworth tried early and dropped
- `{{w_redfronts}}` = carmine red-fronts: the identical store fronts, in the company's centennial report
- `{{w_rent}}` = $30 a month: the Lancaster store's rent
- `{{w_reserve}}` = a reserve set against inventory: a charge in the 1918 accounts alongside the federal income tax
- `{{w_return_wage}}` = $10 a week: Woolworth's wage on his return
- `{{w_return_year}}` = 1877: Woolworth returns to Moore & Smith after illness
- `{{w_ring_dozen}}` = more than 450 dozen: the ring maker's sales so far that year, before the buyer's offer
- `{{w_ring_order}}` = 5,000 gross: what Woolworth's buyer offered to take over the next year
- `{{w_ring_price}}` = 50 cents: the finger ring's retail price before Woolworth's buyer
- `{{w_ring_result}}` = ten-cent gold-filled rings: what the ring became
- `{{w_ring_units}}` = 720,000 rings: 5,000 gross, in rings
- `{{w_rivals}}` = competitors without a ten-cent limit: one of the reasons given for the 1932 move
- `{{w_sales_1912}}` = $60.6 million: sales in 1912
- `{{w_sales_1919}}` = $119.5 million: sales in 1919
- `{{w_scranton_date}}` = November 6, 1880: the Scranton store opens, run by his brother Sum; the company's centennial report dates the chain's birth to it
- `{{w_shrink_quote}}` = Woolworth clung to the old policy by decreasing the units. The size was made smaller, less candy was sold for ten cents, matches which had been one cent a box were five cents; things were sold separately, one stocking for ten cents, the pail ten cents and the cover ten.: Hayward & White, Chain Stores, 1922
- `{{w_sign_quote}}` = The crowd could not get away from that enticing sign, 'Five Cents.': Woolworth, 1913
- `{{w_skimmer_cost}}` = $2.50 a gross: skimmers and ABC plates on the first store's cost list
- `{{w_skimmer_margin}}` = about 65%: what was left of the price on skimmers (computed from the cost list)
- `{{w_sm_year}}` = 1930: Sales Management's summary of the method
- `{{w_soap_cost}}` = $5.85 a gross: animal soap on the first store's cost list
- `{{w_soap_margin}}` = about 19%: what was left of the price on animal soap (computed from the cost list)
- `{{w_start_year}}` = 1873: Woolworth starts at Augsbury & Moore, Watertown
- `{{w_stock_1879}}` = $410: the Lancaster store's opening stock of 'Yankee Notions', much of it on credit
- `{{w_stock_sold}}` = 31%: share of the opening stock sold on the first day
- `{{w_store_profit_1927}}` = $16,800: profit per store, 1927
- `{{w_store_profit_1932}}` = $8,093: profit per store, 1932
- `{{w_store_sales_1927}}` = $172,500: sales per store, 1927
- `{{w_stores_1900}}` = 59: stores of Woolworth's own in 1900
- `{{w_stores_1900_year}}` = 1900: the year of the count of his own stores
- `{{w_stores_1917}}` = 1,000 stores: stores at the end of 1917
- `{{w_stores_1919}}` = 1,081: stores in 1919
- `{{w_tallest_until}}` = 1930: the year another building passed it
- `{{w_tax_1918}}` = $1.23 million: federal income tax paid in 1918
- `{{w_teatime}}` = $47.65: Lancaster's takings by tea time on the first day
- `{{w_test_date}}` = February 1932: the company's president says the stores may add a 20-cent line
- `{{w_trial_where}}` = in some of their stores, in the West and the South: where the 20-cent line was tried first, 1932
- `{{w_tribune_year}}` = 1901: the New York Tribune on Woolworth's imports
- `{{w_tried_quote}}` = did not yield satisfactory sales and profits: the company's centennial report on Woolworth's early experiment with 25-cent goods
- `{{w_unpaid}}` = 3 months: how long Woolworth worked unpaid at the start
- `{{w_utica_date}}` = February 22, 1879: the Utica store opens (Washington's Birthday)
- `{{w_utica_low}}` = $2.50: Utica's daily takings at their lowest
- `{{w_utica_months}}` = about 3 months: how long the Utica store lasted
- `{{w_utica_profit}}` = $150: the profit Woolworth said he sold out at
- `{{w_utica_sign}}` = Great Five Cent Store: the Utica store's name
- `{{w_utica_stock}}` = about $300: the Utica store's goods on credit from Moore
- `{{w_vats_quote}}` = You can't afford to use brushes. Throw the toys in vats. Dip them. Then you can leave off this little red stripe and this little yellow stripe.: a Woolworth buyer to an American toy maker during the war, as told to Printers' Ink, April 1919
- `{{w_west_limit}}` = 15 cents: the ceiling in some districts west of the Rockies and in Canada
- `{{w_west_points}}` = 5, 10 and 15 cents: the price points in E. P. Charlton's western stores
- `{{w_woolco}}` = Woolco: the crochet cotton an American spinner made, coached by Woolworth's buyers, when the war shut out D.M.C.
- `{{w_ww_year}}` = 1913: the year of Woolworth's World's Work interview

## What you return

The shots below were drafted by code: their cuts are legal and fixed, a figure stays on screen 3 s,
and each says what is spoken under it. Decide each shot. Reply with ONE JSON object and nothing else
(no prose, no code fence):

    {"mode": "history", "shots": {"s001": {"kind": …, "style": …, "on": …, "params": {…}, "query": ["…"], "sources": ["…"],
      "fallback": "…", "specific": "…", "intent": "…"}, "s002": {…}, …}}

- Give only the fields you set; a field you leave keeps the draft's value.
- Keep `intent` to eight words or fewer.
- A paper shot (it holds a figure) stays paper: choose its kind, style and params (values as `{{key}}`, never typed).
  Give it `params.print` with a `want` ({"query": "…", "sources": ["smithsonian", "commons"]}) when a true picture
  fits the sentence.
- A world shot: choose still, footage or archive, with `query`, `sources` and `fallback`, and `specific` when
  the sentence names a real company, person, place or event. A query is two to four words: the name, if any,
  and one or two concrete nouns ("Woolworth store", "dime counter"), never a description: archive titles
  are short, and a long query matches none of them (G02: 422 rejections).
- Follow each beat's VISUAL brief where it names a picture.
- Every shot listed gets an entry. Nothing before or after the object.

Also give each chapter its music's mood, one of calm, tension, lift, resolve, montage, in the same object: "moods": {"the open": "…", "ONE PRICE": "…", "PRICE FIRST": "…", "THE CEILING": "…", "YOUR DIME": "…"}.

## The shots, drafted by code

### Beat 0. VISUAL: still-push on a Shield nickel of the period (Smithsonian National Numismatic Collection, CC0), slow, toward the numeral; archive-framed on an early Woolworth storefront (the Scranton store, about 1880, Wikimedia Commons, public domain), never captioned as Lancaster; unit-grid of {{w_day1_count}} sales filling in ink as the takings rise; number-land on {{w_day1}}; quote card for the letter, attributed "F. W. Woolworth to his father, June 22, 1879".
### Beat 1. VISUAL: archive-framed on the Woolworth Building at night, about 1913 (Library of Congress, no known restrictions), the push toward the lit crown; match-bridge: a single vertical line on a price axis, every item in the store stacked on it, holds still while the era changes and a modern catalogue's own price curves rise around it, labelled Tarnhollow demo data.
### Beat 47
### Beat 3. VISUAL: chapter
### Beat 4. VISUAL: still-push on a portrait of Woolworth (Wikimedia Commons, public domain), toward the eyes; still-pan across a Watertown, New York street photograph of the period (Library of Congress, no known restrictions); footage-insert of a dry goods counter's brass scale and paper twine (stock, close, no labels).
### Beat 5. VISUAL: quote card: Woolworth's sentence, verbatim, attributed "The World's Work, April 1913"; footage-insert of a hand setting small tin goods in a row on a wooden counter (stock, hands only, no labels).
### Beat 6. VISUAL: archive-framed on a Utica street scene of the period (Library of Congress, no known restrictions), never captioned as the store; number-pair: the opening day against {{w_utica_low}}, ink; quote card for "I had to take my store to the people", attributed "The World's Work, April 1913".
### Beat 7. VISUAL: still-push on the Scranton store's sign (Wikimedia Commons, public domain) toward its lettering; quote card for the charm, attributed "F. W. Woolworth, as quoted in the company's centennial report, 1979"; still-push on a Seated Liberty dime of the period (Smithsonian National Numismatic Collection, CC0), the second coin landing beside the first.
### Beat 8. VISUAL: doc-highlight on the centennial report's line about the higher-priced goods (Internet Archive), the phrase "did not yield satisfactory sales and profits" underlined in ink; timeline: one early test, then a long empty stretch of years drawn slowly to the right.
- s046 [265.84–272.98] world still/still-push | So the ceiling wasn't superstition. It was a test, run once, early, and then not run again for a very long time.
- s047 [272.98–278.17] world still/still-push | Keep that in mind. The machine grew from there. Scranton,
### Beat 9. VISUAL: still-pan across the Scranton store photograph (Wikimedia Commons, public domain); archive-stack of early five-and-ten storefronts and a 1908 Charlton store interior postcard (Wikimedia Commons, public domain), landing as the partners are named; timeline of store counts, each landing as spoken.
- s048 [278.17–282.98] paper number/number-land {{w_scranton_date}}@278.24 | November 6, 1880, run by his brother, Sum:
- s049 [282.98–286.81] world still/still-push | the store the company's own history dates the chain from.
- s050 [286.81–292.42] world still/still-push | Then stores run by partners: his cousin Seymour Knox, and Fred Kirby. In
- s051 [292.42–296.97] paper number/number-land {{w_office_year}}@292.42 | 1886, Woolworth rented desk room in New York for
- s052 [296.97–300.53] paper number/number-land {{w_office_rent}}@297.12 | $25 a month and did all the buying himself.
- s053 [300.53–308.66] paper timeline/timeline {{w_stores_1900_year}}@301.20 {{w_stores_1900}}@302.38 {{w_redfronts}}@305.08 | By 1900 he had 59 stores of his own, with the famous carmine red-fronts. One price, one look,
- s054 [308.66–314.84] world still/still-push | one buyer. You could walk into any of them and know what everything cost before you'd seen any of it.
### Beat 47
### Beat 11. VISUAL: chapter
### Beat 12. VISUAL: table-scan typesetting the first store's cost list as the centennial report records it, the cost per gross and the share kept landing row by row, the share kept in blue because it is money; formula-build: a gross, times a nickel, equals {{w_gross_value}}, the ceiling drawn as a hairline across the table.
- s064 [369.81–372.88] world still/still-push | The margin changed on every line.
### Beat 13. VISUAL: chart-build of the three items as bars of the share kept, all under the same price line, the bars in blue; footage-insert of a bar of plain soap and a tin skimmer side by side on paper (stock, no labels).
- s065 [372.88–390.09] world still/breathe-hold FIXED cut and style (BREATHE: one picture held, no camera move): give only query, sources, fallback, specific | Look at what that does to a buyer's mind. The soap barely pays. The skimmer pays handsomely. In a store with one price, the customer doesn't know which is which, and doesn't care. The store has to. So a one-price store isn't simple. It's simple on the outside,
- s066 [390.09–409.73] world still/breathe-hold FIXED cut and style (BREATHE: one picture held, no camera move): give only query, sources, fallback, specific | and on the inside it's a portfolio: every item carrying a different margin under the same tag, and the buyer's whole job is to keep the average above the line. That's the first thing Woolworth understood. Same tag, different margins. Which means, as we'll see, different best prices.
### Beat 14. VISUAL: doc-clipping on the Printers' Ink article of April 1919 (Internet Archive, public domain), the ring passage underlined in ink; number-pair: {{w_ring_dozen}} so far that year against {{w_ring_units}} over the next; footage-insert of a plain gilt ring turning on a jeweller's tray (stock, close, no logos).
- s067 [409.73–414.14] world still/still-push | The next thing changed manufacturing. Because the price was fixed,
### Beat 15. VISUAL: quote card: the buyer's words, verbatim, attributed "as told to Printers' Ink, April 1919"; footage-process (wide, medium, detail) of dip-coating small metal parts in a vat (stock, hands only, no logos), screen direction left to right; quote card for the 1930 summary.
### Beat 16. VISUAL: doc-highlight on the Printers' Ink sentence (Internet Archive), ink underline; still-push on a Woolworth store interior at Christmas, about 1910 (Wikimedia Commons, public domain), toward the ornament counter.
### Beat 17. VISUAL: quote card: the sentence, verbatim, attributed "F. W. Woolworth, General Letter to managers, January 14, 1891"; kinetic-thesis: "Profit is what we are working for, not sales or glory." (the act's one thesis line).
### Beat 18. VISUAL: archive-framed on the building under construction, about 1912 (Wikimedia Commons, public domain), then on the finished tower, 1913 (Library of Congress, no known restrictions), the push rising up the facade; number-land on {{w_height}}; still-depth on the tower at night (Library of Congress), the act's hero photograph.
### Beat 47
### Beat 20. VISUAL: chapter
### Beat 21. VISUAL: doc-clipping on the Printers' Ink paragraph (Internet Archive, public domain), "strictly orthodox" underlined in ink; still-pan across a row of five-and-ten storefronts of the period (Library of Congress, no known restrictions).
### Beat 22. VISUAL: quote card: the passage, verbatim, attributed "Hayward and White, Chain Stores, 1922"; still-push on a Seated Liberty dime (Smithsonian, CC0), the dime seen differently now: the push ends on the coin's edge, not its face; footage-insert of a single stocking laid flat on paper beside an empty space where its pair would be (stock, no labels).
### Beat 23. VISUAL: chart-build of net earnings as a share of sales across the war years, each bar landing as spoken, the fall in blue, the tax and the reserve annotated in ink beside it; breath on the held chart, the bed dropping out a beat before "didn't try the other one".
### Beat 24. VISUAL: archive-framed on a western five, ten and fifteen cent storefront of about 1913 (Boulder, Colorado, public library local history, public domain if so marked; else a Seattle Woolworth's of about 1922, Wikimedia Commons, public domain); table-scan: East and West, each with its ceiling, the difference in ink.
### Beat 25. VISUAL: still-push on the National Magazine portrait of Woolworth, July 1919 (Wikimedia Commons, public domain); doc-clipping on the Printers' Ink report about Parson, underlined in ink, attributed as reported speech.
### Beat 26. VISUAL: chart-build of profit per store at the two dates, the fall landing on {{w_store_profit_1932}}, the profit in blue, the Depression marked in ink across the gap; still-pan across a five-and-ten interior of the early nineteen-thirties (Library of Congress, rights confirmed in sourcing), toward a counter of china.
### Beat 27. VISUAL: doc-clipping on the Southern Textile Bulletin item of March 1932 (Internet Archive, public domain) reporting the trial in some stores, underlined in ink; timeline from the trial to the adoption, each landing as spoken; footage-insert of plain white china cups stacked on a shelf (stock, no marks).
### Beat 28. VISUAL: doc-highlight on the 1932 report to stockholders (Internet Archive), "because of lower costs" underlined in ink; footage-insert of a pail and its lid set apart on a table, then pushed together (stock, no labels).
### Beat 29. VISUAL: quote card: the promise, verbatim, attributed "F. W. Woolworth Co., report to stockholders, January 25, 1933"; doc-highlight on "no intention of going beyond", ink; timeline: the ceiling stepping up, each step landing as spoken.
### Beat 30. VISUAL: still-push on the dime, the third and last time in the archive, the push ending on the date; kinetic-thesis: "A price that never moves can't tell you what a different price would do."; breath, the bed rising under the held line.
### Beat 31. VISUAL: footage-establish on a lower Manhattan street at morning, the Woolworth Building's crown in the frame (stock, no signage legible); quote card for Barnard, attributed "July 1997"; still-push on the tower, 1913 (Library of Congress), the same frame as the cathedral beat.
### Beat 47
### Beat 33. VISUAL: chapter
### Beat 34. VISUAL: formula-build: cost, times markup, a glance at the competitor, a round number, each term landing as spoken, the result stamped as a single price; footage-insert of a price label printing and being pressed onto a shelf edge (stock, no brand), the modern dime.
### Beat 35. VISUAL: chart-build of the demo product's history on log scales, the points landing period by period, drawn from the fit's own points with units divided by days, then the steep line through them, then the line pulled toward the catalogue's as "the rest of the catalogue" is spoken, the slope labelled, Tarnhollow demo data on the figure.
### Beat 36. VISUAL: formula-build: a dollar added to the price, the share-of-price fees taking their cut, the rest landing in the margin in blue; number-pair: {{contribution_pre_ads_pct}} against {{gross_pct_latest}}, labelled Tarnhollow demo data; chart-build returning to the soap-and-skimmer bars.
### Beat 37. VISUAL: chart-build of profit hills for the demo products, each drawn as a band whose top smears across the axis while the price axis marked where each band's top could be, labelled Tarnhollow demo data; then a single vertical line at one price cutting through all of them.
### Beat 38. VISUAL: unit-grid of the demo's {{n_skus}} products, the fitted ones in ink, the refused ones left as hollow outlines, each landing as spoken; still-push on the dime, cut in as a single insert on "Those products are dimes".
### Beat 39. VISUAL: range-band on the demo product's fit, the band opening from the line to the full interval as "range" is spoken, the ends labelled, the zero line marked where the band crosses it, Tarnhollow demo data.
### Beat 40. VISUAL: the {{el_periods}} periods drawn as a short row of ticks, a second row running off the edge of the paper with no figure on it; range-band narrowing as the price's spread widens, not as the months pass, labelled Tarnhollow demo data.
### Beat 41. VISUAL: counterfactual on the demo product's profit band: the top worked out at the estimate alone, one mark on the price axis beside today's price, the current price as the hollow dot and a small step up as the solid dot, the step's size in blue, Tarnhollow demo data.
- s229 [1427.80–1431.92] FIXED: the chapter's takeaway; leave it out
### Beat 42. VISUAL: range-band of every fitted demo product's interval drawn side by side, each with today's price marked inside its band, a single word, "hold", landing in ink; then the {{el_skus_insufficient}} refused products at the end as empty outlines with no band at all, labelled Tarnhollow demo data.
### Beat 43. VISUAL: doc-highlight on the Printers' Ink sentence, the same page as the advertising beat; formula-build: the margin a held price gives up each month, set beside a campaign's monthly spend, as terms only, no figures.
### Beat 44. VISUAL: split-then-now: the {{w_1932}} trial stores on a map of the West and South, then a single demo product's price stepping over time with its predicted and measured units drawn together, labelled Tarnhollow demo data; timeline of steps, each landing as spoken.
### Beat 45. VISUAL: formula-build listing the steps as terms, each landing as spoken, the best-price formula built term by term; receipt: one demo product's line, its price spread, its slope and range, the step and the prediction written before it, labelled Tarnhollow demo data.
### Beat 46. VISUAL: still-push resuming on the cold open's coin in the same framing, then the modern price label on a shelf edge in the same framing; kinetic-thesis: "It never told Woolworth what his customers would have paid.".
- s261 [1642.19–1649.31] paper number/number-land {{w_day1}}@1642.49 {{w_ceiling_span}}@1649.31 | $127.65, in nickels, on a Saturday in Lancaster. A ceiling held for
- s262 [1649.31–1655.30] paper number/number-land {{w_ceiling_span}}@1649.31 | more than 50 years. The tallest building in the world, paid for in nickels and dimes.
- s263 [1655.30–1660.92] world still/still-push | It never told Woolworth what his customers would have paid. Your prices can.
### Beat 47. VISUAL: range-band on the demo catalogue's fits, every product's interval drawn at once, the band holding while the voice names what it takes, labelled Tarnhollow demo data; end card at "hubricon.com/learn".
