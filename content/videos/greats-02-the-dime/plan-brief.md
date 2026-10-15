# Plan brief: greats-02-the-dime

Narration 1724.7 s. Write `videos/greats-02-the-dime/shots.json` as `{"slug": …, "mode": "history"|"explainer", "fps": 30, "shots": [...]}`, then run `content/.venv/bin/hubricon-content shots-fill greats-02-the-dime` and `… shots-validate greats-02-the-dime` and fix until it prints clean. Screen-mix shares are advisory. Do not read any other file: everything is here.

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
and each says what is spoken under it. Decide each shot. Write ONE file,
`content/videos/greats-02-the-dime/decisions.json`, in a single write:

    {"mode": "history", "shots": {"s001": {"kind": …, "style": …, "on": …, "params": {…}, "query": ["…"], "sources": ["…"],
      "fallback": "…", "specific": "…", "intent": "…"}, "s002": {…}, …}}

- Give only the fields you set; a field you leave keeps the draft's value.
- Keep `intent` to eight words or fewer.
- A paper shot (it holds a figure) stays paper: choose its kind, style and params (values as `{{key}}`, never typed).
  Give it `params.print` with a `want` ({"query": "…", "sources": ["smithsonian", "commons"]}) when a true picture
  fits the sentence.
- A world shot: choose still, footage or archive, with `query` (the sentence's concrete nouns), `sources` and
  `fallback`, and `specific` when the sentence names a real company, person, place or event.
- Follow each beat's VISUAL brief where it names a picture.
- Do not run commands and do not read other files. Reply with the number of shots decided.

## The shots, drafted by code

### Beat 0. VISUAL: still-push on a Shield nickel of the period (Smithsonian National Numismatic Collection, CC0), slow, toward the numeral; archive-framed on an early Woolworth storefront (the Scranton store, about 1880, Wikimedia Commons, public domain), never captioned as Lancaster; unit-grid of {{w_day1_count}} sales filling in ink as the takings rise; number-land on {{w_day1}}; quote card for the letter, attributed "F. W. Woolworth to his father, June 22, 1879".
- s001 [0.00–4.11] paper number/number-land {{w_lancaster_date}}@0.90 | Saturday, June 21, 1879.
- s002 [4.11–9.09] world still/still-push | The circus has come to Lancaster, Pennsylvania, with its parade down the city streets,
- s003 [9.09–14.38] world still/still-push | and a young man whose first store has already closed is opening another he can barely afford.
- s004 [14.38–27.24] paper timeline/timeline {{w_rent}}@15.70 {{w_stock_1879}}@18.24 {{w_clerks}}@21.58 | The rent is $30 a month. The stock, $410 of it, is much of it on credit. He has 7 clerks, and he hasn't advertised. He spends the morning worrying whether anyone will come.
- s005 [27.24–31.81] world still/still-push | Every item in the store costs the same: a nickel. By tea time
- s006 [31.81–35.76] paper number/number-land {{w_teatime}}@32.30 | they've taken $47.65. By closing,
- s007 [35.76–43.17] paper pair/number-pair {{w_day1}}@35.96 {{w_day1_count}}@39.26 | $127.65. That's 2,553 separate sales, at one price,
- s008 [43.17–48.27] paper number/number-land {{w_stock_sold}}@43.56 | and 31% of everything in the store gone in a day. The next morning
- s009 [48.27–53.92] paper number/number-land {{w_letter_quote}}@49.82 | he wrote to his father: We could have sold $200 if the store had been larger.
### Beat 1. VISUAL: archive-framed on the Woolworth Building at night, about 1913 (Library of Congress, no known restrictions), the push toward the lit crown; match-bridge: a single vertical line on a price axis, every item in the store stacked on it, holds still while the era changes and a modern catalogue's own price curves rise around it, labelled Tarnhollow demo data.
- s010 [53.92–60.52] world still/still-push | His name was Frank Woolworth. If you sell anything, you already know the moral you'd draw from a day like that.
- s011 [60.52–71.44] paper number/number-land {{w_ceiling_span}}@67.82 | Find a price that works, and don't touch it. Woolworth's company kept a ceiling over its prices, in most of its stores, for more than 50 years: first a nickel, then a dime.
- s012 [71.44–78.00] world still/still-push | And it built the tallest building in the world. Hold on to that moral. This film tests it.
### Beat 47
- s013 [78.00–80.50] paper chapter/chapter | 
### Beat 3. VISUAL: chapter
- s014 [80.50–87.46] world still/still-push | One price. Go back a few years. Woolworth was born on a farm near Rodman,
### Beat 4. VISUAL: still-push on a portrait of Woolworth (Wikimedia Commons, public domain), toward the eyes; still-pan across a Watertown, New York street photograph of the period (Library of Congress, no known restrictions); footage-insert of a dry goods counter's brass scale and paper twine (stock, close, no labels).
- s015 [87.46–98.36] paper pair/number-pair {{w_born}}@89.38 {{w_start_year}}@93.66 | in upstate New York, in 1852. In 1873 he got himself a place in a dry goods store in Watertown,
- s016 [98.36–108.51] paper pair/number-pair {{w_unpaid}}@101.66 {{w_first_wage}}@102.84 | Augsbury and Moore. The pay was nothing at all for 3 months, then $3.50 a week. Ill health sent him back to the farm for a while.
- s017 [108.51–118.57] paper pair/number-pair {{w_return_year}}@112.70 {{w_return_wage}}@115.12 | He came back to the same firm, by then Moore and Smith, in 1877, at $10 a week. A farm boy, a clerk,
- s018 [118.57–127.07] paper number/number-land {{w_counter_year}}@122.19 | and nobody's idea of a merchant prince. In 1878, a travelling salesman told his employer,
### Beat 5. VISUAL: quote card: Woolworth's sentence, verbatim, attributed "The World's Work, April 1913"; footage-insert of a hand setting small tin goods in a row on a wooden counter (stock, hands only, no labels).
- s019 [127.07–133.36] world still/still-push | William Moore, about something he'd seen in Michigan: a counter where everything cost a nickel.
- s020 [133.36–138.91] paper number/number-land {{w_counter_order}}@134.37 | Moore ordered $100 of goods for one from a wholesaler, Spelman Brothers.
- s021 [138.91–144.70] world still/still-push | Woolworth set out the table. In his own telling, years later, he gave himself more of the credit:
- s022 [144.70–149.89] paper number/number-land {{w_counter_quote}}@144.95 | I persuaded my employers to create a five cent cash counter with me in charge of it.
- s023 [149.89–156.87] world still/still-push | A correction you'll need, because the story is usually told the other way: Woolworth didn't invent the nickel counter.
- s024 [156.87–163.54] world still/still-push | He ran one, watched what it did, and asked the bigger question. Not what a nickel table could sell.
- s025 [163.54–168.96] world still/still-push | What a whole store could, if every price in it was a nickel. So he tried it.
### Beat 6. VISUAL: archive-framed on a Utica street scene of the period (Library of Congress, no known restrictions), never captioned as the store; number-pair: the opening day against {{w_utica_low}}, ink; quote card for "I had to take my store to the people", attributed "The World's Work, April 1913".
- s026 [168.96–174.82] paper number/number-land {{w_utica_date}}@169.40 | On February 22, 1879, Washington's Birthday,
- s027 [174.82–182.41] paper pair/number-pair {{w_utica_sign}}@175.76 {{w_utica_stock}}@179.00 | he opened the Great Five Cent Store in Utica, New York, with about $300 of goods on credit from Moore.
- s028 [182.41–192.98] paper pair/number-pair {{w_utica_low}}@184.90 {{w_utica_months}}@187.46 | The daily takings fell as low as $2.50. Within about 3 months he'd sold out and closed, at a profit, by his own account, of
- s029 [192.98–202.25] paper pair/number-pair {{w_utica_profit}}@193.24 {{w_people_quote}}@197.02 | $150. Decades later he said what he took from it: One of the first things I learned was that I could not expect people to come to me.
- s030 [202.25–207.43] world still/still-push | I had to take my store to the people. He took the lesson to Lancaster.
### Beat 7. VISUAL: still-push on the Scranton store's sign (Wikimedia Commons, public domain) toward its lettering; quote card for the charm, attributed "F. W. Woolworth, as quoted in the company's centennial report, 1979"; still-push on a Seated Liberty dime of the period (Smithsonian National Numismatic Collection, CC0), the second coin landing beside the first.
- s031 [207.43–214.35] world still/still-push | Now go back to that Saturday in Lancaster, because now you can see what he'd built. Not a shop with low prices.
- s032 [214.35–219.93] world still/still-push | A shop with one price. A customer didn't have to ask, haggle, compare or calculate.
- s033 [219.93–231.59] paper timeline/timeline {{w_ww_year}}@223.27 {{w_sign_quote}}@224.97 {{w_five_and_ten}}@228.05 | The sign did the selling. As Woolworth put it in 1913: The crowd could not get away from that enticing sign, 'Five Cents.' By the next summer he'd added a second price,
- s034 [231.59–237.03] world still/still-push | a dime, and the store became a five-and-ten. He later wrote that it cost him something:
- s035 [237.03–243.85] paper number/number-land {{w_charm_quote}}@237.25 | As soon as we added 10 cent goods to the line, we took away part of the 5 cent store's charm,
- s036 [243.85–250.34] world still/still-push | the charm of finding only one price on a counter, and only one price in a store.
### Beat 8. VISUAL: doc-highlight on the centennial report's line about the higher-priced goods (Internet Archive), the phrase "did not yield satisfactory sales and profits" underlined in ink; timeline: one early test, then a long empty stretch of years drawn slowly to the right.
- s037 [250.34–256.17] world still/still-push | And here's a detail the company's own history keeps, which matters for this film. Early on,
- s038 [256.17–265.84] paper pair/number-pair {{w_quarter_test}}@259.00 {{w_tried_quote}}@261.74 | Woolworth tried a line of goods at a higher price, 25 cents. In the company's words, it did not yield satisfactory sales and profits. He dropped it.
- s039 [265.84–272.98] world still/still-push | So the ceiling wasn't superstition. It was a test, run once, early, and then not run again for a very long time.
- s040 [272.98–278.17] world still/still-push | Keep that in mind. The machine grew from there. Scranton,
### Beat 9. VISUAL: still-pan across the Scranton store photograph (Wikimedia Commons, public domain); archive-stack of early five-and-ten storefronts and a 1908 Charlton store interior postcard (Wikimedia Commons, public domain), landing as the partners are named; timeline of store counts, each landing as spoken.
- s041 [278.17–282.98] paper number/number-land {{w_scranton_date}}@278.24 | November 6, 1880, run by his brother, Sum:
- s042 [282.98–289.13] world still/still-push | the store the company's own history dates the chain from. Then stores run by partners:
- s043 [289.13–296.97] paper number/number-land {{w_office_year}}@292.42 | his cousin Seymour Knox, and Fred Kirby. In 1886, Woolworth rented desk room in New York for
- s044 [296.97–300.53] paper number/number-land {{w_office_rent}}@297.12 | $25 a month and did all the buying himself.
- s045 [300.53–308.66] paper timeline/timeline {{w_stores_1900_year}}@301.20 {{w_stores_1900}}@302.38 {{w_redfronts}}@305.08 | By 1900 he had 59 stores of his own, with the famous carmine red-fronts. One price, one look,
- s046 [308.66–314.84] world still/still-push | one buyer. You could walk into any of them and know what everything cost before you'd seen any of it.
### Beat 47
- s047 [314.84–317.34] paper chapter/chapter | 
### Beat 11. VISUAL: chapter
- s048 [317.34–323.89] world still/still-push | Price first. Now the mechanism, because it's the opposite of how most businesses set a price.
### Beat 12. VISUAL: table-scan typesetting the first store's cost list as the centennial report records it, the cost per gross and the share kept landing row by row, the share kept in blue because it is money; formula-build: a gross, times a nickel, equals {{w_gross_value}}, the ceiling drawn as a hairline across the table.
- s049 [323.89–329.79] world still/still-push | Most start with a cost and add a margin. Woolworth started with the price and worked backwards.
- s050 [329.79–336.49] paper number/number-land {{w_gross}}@333.24 | His first cost list priced its goods by the gross, 144 items. At a nickel each,
- s051 [336.49–343.92] paper number/number-land {{w_gross_value}}@337.72 | a gross brought in $7.20. That figure was fixed. It sat over everything like a ceiling.
- s052 [343.92–349.06] world still/still-push | So every line on his first cost list was really the same question: what does a gross cost?
- s053 [349.06–356.78] paper pair/number-pair {{w_dustpan_cost}}@350.90 {{w_dustpan_margin}}@353.26 | Toy dustpans: $4.75 a gross, which kept about 34% of the price. Animal soap:
- s054 [356.78–363.15] paper pair/number-pair {{w_soap_cost}}@357.04 {{w_soap_margin}}@359.40 | $5.85 a gross, keeping about 19%. Skimmers and alphabet plates:
- s055 [363.15–369.81] paper pair/number-pair {{w_skimmer_cost}}@363.42 {{w_skimmer_margin}}@366.08 | $2.50 a gross, keeping about 65%. The price never changed.
- s056 [369.81–375.54] world still/still-push | The margin changed on every line. Look at what that does to a buyer's mind.
### Beat 13. VISUAL: chart-build of the three items as bars of the share kept, all under the same price line, the bars in blue; footage-insert of a bar of plain soap and a tin skimmer side by side on paper (stock, no labels).
- s057 [375.54–381.23] world still/still-push | The soap barely pays. The skimmer pays handsomely. In a store with one price,
- s058 [381.23–388.32] world still/still-push | the customer doesn't know which is which, and doesn't care. The store has to. So a one-price store isn't simple.
- s059 [388.32–392.75] world still/still-push | It's simple on the outside, and on the inside it's a portfolio:
- s060 [392.75–400.62] world still/still-push | every item carrying a different margin under the same tag, and the buyer's whole job is to keep the average above the line.
- s061 [400.62–407.75] world still/still-push | That's the first thing Woolworth understood. Same tag, different margins. Which means, as we'll see,
- s062 [407.75–414.14] world still/still-push | different best prices. The next thing changed manufacturing. Because the price was fixed,
### Beat 14. VISUAL: doc-clipping on the Printers' Ink article of April 1919 (Internet Archive, public domain), the ring passage underlined in ink; number-pair: {{w_ring_dozen}} so far that year against {{w_ring_units}} over the next; footage-insert of a plain gilt ring turning on a jeweller's tray (stock, close, no logos).
- s063 [414.14–421.95] world still/still-push | the only way to sell something new was to make it cost less, and Woolworth's buyers went to manufacturers and showed them how.
- s064 [421.95–427.08] world still/still-push | Here's one, as Woolworth himself told it to the trade paper Printers' Ink.
- s065 [427.08–435.43] paper pair/number-pair {{w_ring_price}}@429.83 {{w_ring_dozen}}@432.19 | A finger ring sold at retail for around 50 cents. Its maker had sold more than 450 dozen so far that year.
- s066 [435.43–445.99] paper pair/number-pair {{w_ring_order}}@437.61 {{w_ring_units}}@440.67 | A Woolworth buyer offered to take 5,000 gross over the next year. That's 720,000 rings. And he came with suggestions for making it cheaper.
- s067 [445.99–451.29] paper number/number-land {{w_ring_result}}@447.31 | The result: ten-cent gold-filled rings. The price came first.
- s068 [451.29–456.51] world still/still-push | The product was redesigned to meet it. Here's another. During the war,
### Beat 15. VISUAL: quote card: the buyer's words, verbatim, attributed "as told to Printers' Ink, April 1919"; footage-process (wide, medium, detail) of dip-coating small metal parts in a vat (stock, hands only, no logos), screen direction left to right; quote card for the 1930 summary.
- s069 [456.51–464.32] world still/still-push | a German iron toy that sold for a dime was cut off. An American maker was asked to make it, and said he couldn't do it at the price.
- s070 [464.32–471.80] paper number/number-land {{w_vats_quote}}@468.01 | The Woolworth buyer looked at how it was made and said this: You can't afford to use brushes. Throw the toys in vats.
- s071 [471.80–478.13] world still/still-push | Dip them. Then you can leave off this little red stripe and this little yellow stripe. The price stayed.
- s072 [478.13–486.54] world still/still-push | The product changed to fit it. When the war shut out a European crochet cotton, the buyers coached an American spinner to make one like it,
- s073 [486.54–502.98] paper timeline/timeline {{w_woolco}}@487.23 {{w_sm_year}}@492.81 {{w_1930_quote}}@494.59 | sold as Woolco, still at a dime a ball. A trade magazine summed up the method in 1930: A large quantity order and an improved production system has brought hundreds of higher-priced articles down to ten cents.
### Beat 16. VISUAL: doc-highlight on the Printers' Ink sentence (Internet Archive), ink underline; still-push on a Woolworth store interior at Christmas, about 1910 (Wikimedia Commons, public domain), toward the ornament counter.
- s074 [502.98–507.53] world still/still-push | And one more thing: the price did the marketing. Printers' Ink
- s075 [507.53–517.07] paper pair/number-pair {{w_pi17_year}}@509.18 {{w_pi17_ad}}@511.34 | put it in a single sentence in 1917: Confining the price of goods to ten cents is fundamentally an advertising idea.
- s076 [517.07–524.53] world still/still-push | A single price is a promise a customer can remember from the sidewalk. And because the buying was so concentrated,
- s077 [524.53–534.52] paper number/number-land {{w_tribune_year}}@526.64 | it was enormous. In 1901, the New York Tribune reported that Woolworth imported a larger tonnage of toys and Christmas tree ornaments
- s078 [534.52–540.95] world still/still-push | than all other United States buyers put together. Underneath all of it was one rule,
### Beat 17. VISUAL: quote card: the sentence, verbatim, attributed "F. W. Woolworth, General Letter to managers, January 14, 1891"; kinetic-thesis: "Profit is what we are working for, not sales or glory." (the act's one thesis line).
- s079 [540.95–544.56] world still/still-push | and it's the line from this story worth keeping where you can see it.
- s080 [544.56–550.34] paper number/number-land {{w_general_letter}}@546.77 | In a letter to his store managers dated January 14, 1891,
- s081 [550.34–557.79] world still/still-push | Woolworth wrote: Profit is what we are working for, not sales or glory. Hold on to that sentence.
- s082 [557.79–564.56] world still/still-push | The rest of this film is about what happens when a price stops serving the profit and starts serving the sign.
### Beat 18. VISUAL: archive-framed on the building under construction, about 1912 (Wikimedia Commons, public domain), then on the finished tower, 1913 (Library of Congress, no known restrictions), the push rising up the facade; number-land on {{w_height}}; still-depth on the tower at night (Library of Congress), the act's hero photograph.
- s083 [564.56–569.56] paper number/number-land {{w_merger_year}}@564.98 | In 1912, Woolworth merged his company with his partners' chains:
- s084 [569.56–585.34] paper timeline/timeline {{w_merger_stores}}@569.88 {{w_sales_1912}}@573.34 {{w_building_open}}@576.06 {{w_lights}}@582.02 | 596 stores. That year the company sold $60.6 million. And on April 24, 1913, President Wilson pressed a button in the White House and 80,000 lights came on in a tower on Broadway:
- s085 [585.34–599.76] paper timeline/timeline {{w_height}}@585.70 {{w_tallest_until}}@590.20 {{w_cost}}@592.32 {{w_owned_by}}@596.72 | 792 feet tall, the tallest building in the world until 1930. It cost $13.5 million. It was built without a mortgage, and by 1914 Woolworth owned it outright.
- s086 [599.76–607.42] world still/still-push | A minister who saw it called it the Cathedral of Commerce. Woolworth said he built it to advertise his stores all over the world.
- s087 [607.42–614.07] world still/still-push | It was paid for, nickel by nickel and dime by dime, by a price that hadn't moved. So far,
- s088 [614.07–618.40] world still/still-push | the moral writes itself: find the price, hold the price.
### Beat 47
- s089 [618.40–620.90] paper chapter/chapter | 
### Beat 20. VISUAL: chapter
- s090 [620.90–624.57] world still/still-push | The ceiling. Then the costs moved.
### Beat 21. VISUAL: doc-clipping on the Printers' Ink paragraph (Internet Archive, public domain), "strictly orthodox" underlined in ink; still-pan across a row of five-and-ten storefronts of the period (Library of Congress, no known restrictions).
- s091 [624.57–633.39] paper number/number-land {{w_five_and_ten}}@628.39 | The war in Europe drove up the price of almost everything a five-and-ten sold, and the big rivals began to sell above the old limit.
- s092 [633.39–647.92] paper pair/number-pair {{w_pi17_date}}@635.35 {{w_pi17_orthodox}}@638.45 | Woolworth didn't. In May 1917, Printers' Ink wrote: Mr. Woolworth is the only one of the big people in this line who remains strictly orthodox so far as five-and-ten-cent goods are concerned.
- s093 [647.92–653.89] world still/still-push | How long this will continue nobody but Woolworth knows. By the end of that year,
- s094 [653.89–660.89] paper number/number-land {{w_stores_1917}}@654.91 | the company had 1,000 stores. So how do you hold a price when everything under it costs more?
### Beat 22. VISUAL: quote card: the passage, verbatim, attributed "Hayward and White, Chain Stores, 1922"; still-push on a Seated Liberty dime (Smithsonian, CC0), the dime seen differently now: the push ends on the coin's edge, not its face; footage-insert of a single stocking laid flat on paper beside an empty space where its pair would be (stock, no labels).
- s095 [660.89–666.31] paper number/number-land {{w_chain_year}}@662.96 | A book on chain stores from 1922 described exactly how:
- s096 [666.31–672.20] paper number/number-land {{w_shrink_quote}}@666.68 | Woolworth clung to the old policy by decreasing the units. The size was made smaller,
- s097 [672.20–679.13] world still/still-push | less candy was sold for ten cents, matches which had been one cent a box were five cents; things were sold separately,
- s098 [679.13–686.34] world still/still-push | one stocking for ten cents, the pail ten cents and the cover ten. Look at the stocking. A pair became one.
- s099 [686.34–693.71] world still/still-push | The price on the tag never moved. What the customer got for it did. Your customers have a name for that today,
- s100 [693.71–697.81] world still/still-push | and it isn't a kind one. And the margin moved too.
### Beat 23. VISUAL: chart-build of net earnings as a share of sales across the war years, each bar landing as spoken, the fall in blue, the tax and the reserve annotated in ink beside it; breath on the held chart, the bed dropping out a beat before "didn't try the other one".
- s101 [697.81–709.06] paper timeline/timeline {{w_net_1917}}@698.98 {{w_1917}}@701.36 {{w_1918}}@703.56 {{w_net_1918}}@705.28 | Net earnings were 9.43% of sales in 1917. In 1918, 5.46%. To be fair to the record,
- s102 [709.06–719.85] paper pair/number-pair {{w_tax_1918}}@712.40 {{w_reserve}}@715.14 | that year also carried a federal income tax bill of $1.23 million and a reserve set against inventory, so not all of the drop was the dime.
- s103 [719.85–727.03] world still/still-push | But the dime was the one thing the company had chosen not to let move, so every other cost had to land somewhere else:
- s104 [727.03–732.46] world still/still-push | in the size of the product, in the supplier's margin, or in the company's own.
- s105 [732.46–739.50] paper pair/number-pair {{w_1919}}@733.00 {{w_net_1919}}@735.96 | By 1919, net earnings were back to 7.89%. The ceiling had held.
- s106 [739.50–746.21] world still/still-push | Whether holding it was the most profitable choice is a question the company never had to answer, because in the East
- s107 [746.21–751.39] world still/still-push | it didn't try the other one. And here's the correction most retellings miss.
### Beat 24. VISUAL: archive-framed on a western five, ten and fifteen cent storefront of about 1913 (Boulder, Colorado, public library local history, public domain if so marked; else a Seattle Woolworth's of about 1922, Wikimedia Commons, public domain); table-scan: East and West, each with its ceiling, the difference in ink.
- s108 [751.39–757.86] world still/still-push | Nothing over a dime was never quite the whole truth. In some districts west of the Rockies, and in Canada,
- s109 [757.86–764.98] paper number/number-land {{w_west_limit}}@759.95 | the stores already had a ceiling of 15 cents. Charlton's western stores, part of the merged company,
- s110 [764.98–773.38] paper number/number-land {{w_west_points}}@765.67 | sold at 5, 10 and 15 cents. So the company was running different ceilings in different parts of the same chain, for years.
- s111 [773.38–779.19] world still/still-push | That's the closest thing in this story to a price experiment. But it wasn't designed as one,
- s112 [779.19–787.15] world still/still-push | and prices compared across places can't tell you much about price, because the places differ in many ways besides the price.
- s113 [787.15–796.68] paper number/number-land {{w_died}}@791.99 | Hold on to that. It matters later. Woolworth died on April 8, 1919, at his house on Long Island.
### Beat 25. VISUAL: still-push on the National Magazine portrait of Woolworth, July 1919 (Wikimedia Commons, public domain); doc-clipping on the Printers' Ink report about Parson, underlined in ink, attributed as reported speech.
- s114 [796.68–805.24] paper pair/number-pair {{w_stores_1919}}@799.11 {{w_sales_1919}}@801.97 | By the end of that year the company had 1,081 stores, and it sold $119.5 million.
- s115 [805.24–810.18] world still/still-push | And the ceiling had become something more than a policy. It was an identity.
- s116 [810.18–817.20] paper number/number-land {{w_parson_date}}@810.78 | In February 1920, Printers' Ink reported that the company's president, Hubert Parson,
- s117 [817.20–825.26] paper number/number-land {{w_parson_quote}}@819.16 | had declared that the company would not under any circumstances even consider breaking away from the ten-cent barrier.
### Beat 26. VISUAL: chart-build of profit per store at the two dates, the fall landing on {{w_store_profit_1932}}, the profit in blue, the Depression marked in ink across the gap; still-pan across a five-and-ten interior of the early nineteen-thirties (Library of Congress, rights confirmed in sourcing), toward a counter of china.
- s118 [825.26–841.19] paper timeline/timeline {{w_1927}}@828.28 {{w_store_sales_1927}}@830.96 {{w_store_profit_1927}}@834.78 {{w_1932}}@837.88 | For a while, the identity paid. In 1927, each store sold $172,500 and made $16,800. By 1932, deep in the Depression,
- s119 [841.19–846.07] paper number/number-land {{w_store_profit_1932}}@841.92 | each made $8,093. Much of that was the Depression.
- s120 [846.07–851.75] world still/still-push | But a store held under a dime couldn't follow its customers to anything that cost more.
- s121 [851.75–859.11] world still/still-push | The price that had once made every store a magnet had become a thing every store had to work around.
### Beat 27. VISUAL: doc-clipping on the Southern Textile Bulletin item of March 1932 (Internet Archive, public domain) reporting the trial in some stores, underlined in ink; timeline from the trial to the adoption, each landing as spoken; footage-insert of plain white china cups stacked on a shelf (stock, no marks).
- s122 [859.11–871.00] paper pair/number-pair {{w_test_date}}@862.79 {{w_new_sign}}@866.47 | And then the company did the right thing, the right way round. In February 1932, its president said the stores might become '5, 10 and 20 cent stores'. They didn't switch the whole chain.
- s123 [871.00–879.02] paper timeline/timeline {{w_new_ceiling}}@871.79 {{w_china}}@872.85 {{w_trial_where}}@874.47 | They tried a 20-cent line, mostly china and glassware, in some of their stores, in the West and the South, first. Then they adopted it.
- s124 [879.02–885.62] world still/still-push | A test, then a rollout. Remember that phrase. It's the most useful one in this whole story.
### Beat 28. VISUAL: doc-highlight on the 1932 report to stockholders (Internet Archive), "because of lower costs" underlined in ink; footage-insert of a pail and its lid set apart on a table, then pushed together (stock, no labels).
- s125 [885.62–892.88] world still/still-push | Now look at why, because it's the opposite of the story people tell. The story is that rising prices forced the dime up.
- s126 [892.88–906.84] paper pair/number-pair {{w_1932}}@897.04 {{w_lower_costs_quote}}@902.00 | In the year it finally moved, prices were falling. The year was 1932, deep in the Depression. The company's own report said that because of lower costs, our selling prices on many lines have been reduced.
- s127 [906.84–911.39] world still/still-push | They raised the ceiling while costs were going down. Their reasons:
- s128 [911.39–915.08] world still/still-push | to supply a larger share of what their customers wanted.
- s129 [915.08–922.11] paper number/number-land {{w_combination_term}}@916.70 | To end what the report called so-called combination items, where a thing was sold in pieces to fit under the limit.
- s130 [922.11–928.67] paper number/number-land {{w_combination_quote}}@923.72 | Their own words: For years we have sold so-called combination items for 10 cents each piece.
- s131 [928.67–936.06] paper number/number-land {{w_rivals}}@929.16 | And competitors without a ten-cent limit were selling what Woolworth couldn't. The ceiling wasn't protecting anything anymore.
- s132 [936.06–942.37] world still/still-push | It was stopping the company from selling things its customers wanted to buy. And then,
### Beat 29. VISUAL: quote card: the promise, verbatim, attributed "F. W. Woolworth Co., report to stockholders, January 25, 1933"; doc-highlight on "no intention of going beyond", ink; timeline: the ceiling stepping up, each step landing as spoken.
- s133 [942.37–946.04] world still/still-push | having moved the price once, the company made a promise.
- s134 [946.04–952.95] paper number/number-land {{w_promise_date}}@948.41 | In a letter to its stockholders dated January 25, 1933, it wrote:
- s135 [952.95–960.53] paper number/number-land {{w_promise_quote}}@953.33 | Fundamentally the Company is in the 5 and 10 cent business and has every intention of continuing that policy.
- s136 [960.53–965.40] world still/still-push | Furthermore, there is no intention of going beyond the 20 cent selling price.
- s137 [965.40–970.73] paper number/number-land {{w_limits_removed}}@965.89 | In 1935, the board removed all arbitrary price limits.
- s138 [970.73–982.40] paper timeline/timeline {{w_ceiling_1935}}@972.37 {{w_1936}}@974.57 {{w_ceiling_1936}}@976.83 {{w_promise_span}}@979.21 | Soon there were goods at 40 cents. By the spring of 1936, some cost $1. The promise didn't last 3 years. So test the moral.
### Beat 30. VISUAL: still-push on the dime, the third and last time in the archive, the push ending on the date; kinetic-thesis: "A price that never moves can't tell you what a different price would do."; breath, the bed rising under the held line.
- s139 [982.40–988.87] world still/still-push | Find a price that works and hold it. The dime was brilliant: an advertisement, a discipline on cost,
- s140 [988.87–993.26] world still/still-push | a promise a customer could remember. But the moral is missing a piece.
- s141 [993.26–997.45] world still/still-push | A price that never moves can't tell you what a different price would do.
- s142 [997.45–1002.01] world still/still-push | Woolworth knew, to the fraction of a cent, what a gross of soap cost him.
- s143 [1002.01–1007.64] world still/still-push | What he couldn't know, from inside a ceiling, was what his customers would have paid above it. For decades
- s144 [1007.64–1017.15] world still/still-push | the company learned a great deal about the cost side of its price, and far less about the demand side, because the demand side only speaks when the price moves.
- s145 [1017.15–1023.54] world still/still-push | When it finally listened, it did it by testing. And then it promised the new ceiling would hold.
- s146 [1023.54–1030.32] world still/still-push | A price that's tested once and then held for decades isn't a measurement anymore. It's a memory.
### Beat 31. VISUAL: footage-establish on a lower Manhattan street at morning, the Woolworth Building's crown in the frame (stock, no signage legible); quote card for Barnard, attributed "July 1997"; still-push on the tower, 1913 (Library of Congress), the same frame as the cathedral beat.
- s147 [1030.32–1033.92] paper number/number-land {{w_five_and_ten}}@1030.76 | The five-and-ten lasted a long time after that.
- s148 [1033.92–1041.72] paper number/number-land {{w_exit_date}}@1034.44 | On July 17, 1997, the company announced it was leaving the American Woolworth store business:
- s149 [1041.72–1049.84] paper pair/number-pair {{w_exit_stores}}@1042.06 {{w_exit_jobs}}@1044.28 | about 400 stores, 9,200 jobs. A retail consultant told reporters that day:
- s150 [1049.84–1055.72] paper number/number-land {{w_barnard_quote}}@1050.08 | The five-and-dime industry is defunct and has been defunct for at least 25 years.
- s151 [1055.72–1061.35] paper number/number-land {{w_footlocker}}@1056.24 | On November 1, 2001, the company renamed itself Foot Locker.
- s152 [1061.35–1066.88] world still/still-push | The building on Broadway is still standing. The price that built it is gone.
### Beat 47
- s153 [1066.88–1069.38] paper chapter/chapter | 
### Beat 33. VISUAL: chapter
- s154 [1069.38–1075.15] world still/still-push | Your dime. Now your business. You have a dime. Probably several.
### Beat 34. VISUAL: formula-build: cost, times markup, a glance at the competitor, a round number, each term landing as spoken, the result stamped as a single price; footage-insert of a price label printing and being pressed onto a shelf edge (stock, no brand), the modern dime.
- s155 [1075.15–1081.66] world still/still-push | A price you set once, for a reason that made sense at the time: a round number, a competitor's price,
- s156 [1081.66–1088.66] world still/still-push | your cost times a markup, whatever the last product sold for. And it's been working, so you've left it alone.
- s157 [1088.66–1094.11] paper number/number-land {{w_ceiling_span}}@1090.89 | That's what Woolworth's company did for more than 50 years: it worked, so it stayed.
- s158 [1094.11–1102.63] world still/still-push | And it carries the same blind spot. As long as that price doesn't move, your sales history can't tell you what a different one would do.
- s159 [1102.63–1108.09] world still/still-push | Not a little. Nothing. Here's what a price that has moved can tell you.
### Beat 35. VISUAL: chart-build of the demo product's history on log scales, the points landing period by period, drawn from the fit's own points with units divided by days, then the steep line through them, then the line pulled toward the catalogue's as "the rest of the catalogue" is spoken, the slope labelled, Tarnhollow demo data on the figure.
- s160 [1108.09–1111.61] world still/still-push | Take one product from the demo catalogue we use for teaching:
- s161 [1111.61–1124.42] paper timeline/timeline {{el_sku}}@1111.88 {{demo_brand}}@1113.54 {{demo_label}}@1114.26 {{n_skus}}@1115.40 {{annual_revenue_m}}@1117.06 {{el_periods}}@1120.82 | TH-OVEMIT-22, from Tarnhollow, demo data, 24 products, about $3.5M a year. Its price moved across 12 periods of history, and its units moved with it.
- s162 [1124.42–1131.54] world still/still-push | Plot them on a scale where every step is the same percentage, price across and units a day up, and fit a line.
- s163 [1131.54–1138.72] paper number/number-land {{el_raw}}@1134.44 | Through this product's own points alone, the line reads -7.35: steep, from very little movement.
- s164 [1138.72–1156.02] paper pair/number-pair {{el_own_weight}}@1142.74 {{el_point}}@1148.02 | So the model doesn't trust it alone. It gives the product's own points 17% of the weight, lets the rest of the catalogue carry the rest, and lands at -2.76. A rise of a given size in the price costs this product about that multiple of it in units.
- s165 [1156.02–1162.35] world still/still-push | That number has a name: price elasticity. Here's why it matters more than it looks.
### Beat 36. VISUAL: formula-build: a dollar added to the price, the share-of-price fees taking their cut, the rest landing in the margin in blue; number-pair: {{contribution_pre_ads_pct}} against {{gross_pct_latest}}, labelled Tarnhollow demo data; chart-build returning to the soap-and-skimmer bars.
- s166 [1162.35–1169.39] world still/still-push | When you raise a price, the extra lands in your margin almost whole. Your landed cost doesn't change.
- s167 [1169.39–1175.67] world still/still-push | Most of your fees don't change. Only the ones charged as a share of the price take a cut of it.
- s168 [1175.67–1181.63] world still/still-push | So a raise that loses units can still make more money, as long as it doesn't lose too many.
- s169 [1181.63–1187.81] world still/still-push | How many you can afford to lose depends only on how much of each sale you keep after landed cost and fees.
- s170 [1187.81–1192.01] world still/still-push | How many you will lose is the slope. On this demo catalogue,
- s171 [1192.01–1202.66] paper pair/number-pair {{contribution_pre_ads_pct}}@1192.58 {{gross_pct_latest}}@1197.34 | that's 38.5%. The gross margin, before fees, is 70.7%. Price off the wrong one and you'll aim at the wrong target.
- s172 [1202.66–1207.46] world still/still-push | And the slope decides the shape of what comes next. Steeper than minus one,
- s173 [1207.46–1213.68] world still/still-push | a raise loses a bigger share of units than it adds to the price, so profit rises, peaks and falls:
- s174 [1213.68–1222.84] world still/still-push | there's a top. Shallower than minus one, a raise loses a smaller share of units than it adds, so profit keeps climbing: no top at all.
- s175 [1222.84–1230.15] world still/still-push | Remember Woolworth's soap and his skimmers: same price, very different margins, very different answers.
### Beat 37. VISUAL: chart-build of profit hills for the demo products, each drawn as a band whose top smears across the axis while the price axis marked where each band's top could be, labelled Tarnhollow demo data; then a single vertical line at one price cutting through all of them.
- s176 [1230.15–1235.99] world still/still-push | Now picture profit as the price sweeps upward. Every unit you still sell earns more.
- s177 [1235.99–1243.06] world still/still-push | You sell fewer units. They pull against each other, so for most products profit climbs, flattens, then falls.
- s178 [1243.06–1250.42] world still/still-push | It's a hill. Its top sits where the slope and the margin put it, but only as sharply as the slope is known.
- s179 [1250.42–1258.63] paper pair/number-pair {{el_no_top}}@1251.89 {{el_skus_fit}}@1252.71 | In this demo, for 22 of the 22 products it measured, the range on the slope is too wide for the model to mark the top.
- s180 [1258.63–1262.27] world still/still-push | The honest thing it can say is how far it can't see.
- s181 [1262.27–1269.49] world still/still-push | Woolworth's ceiling set every product in his stores at the same point on the price axis, whatever its hill looked like.
- s182 [1269.49–1274.21] world still/still-push | From one price that never moved, there was no way to see any of it.
### Beat 38. VISUAL: unit-grid of the demo's {{n_skus}} products, the fitted ones in ink, the refused ones left as hollow outlines, each landing as spoken; still-push on the dime, cut in as a single insert on "Those products are dimes".
- s183 [1274.21–1278.08] world still/still-push | Here is Woolworth's dime inside a modern catalogue.
- s184 [1278.08–1287.04] paper timeline/timeline {{n_skus}}@1279.54 {{el_skus_fit}}@1281.91 {{el_skus_insufficient}}@1283.73 | Across the demo's 24 products, the fit worked on 22. It refused 2. Not because those products are special.
- s185 [1287.04–1291.86] world still/still-push | Because their price never moved enough to draw a line. The rule is plain:
- s186 [1291.86–1300.41] paper pair/number-pair {{el_min_price_cv}}@1295.89 {{el_min_periods}}@1297.41 | the spread of a product's prices, measured against their average, has to reach 2%, across at least 5 periods, or the fit says nothing at all.
- s187 [1300.41–1307.26] world still/still-push | That isn't caution for its own sake. With no movement, there's nothing to measure. Those products are dimes.
- s188 [1307.26–1313.55] world still/still-push | They might be priced perfectly. Nobody can know, including the person who set the price.
### Beat 39. VISUAL: range-band on the demo product's fit, the band opening from the line to the full interval as "range" is spoken, the ends labelled, the zero line marked where the band crosses it, Tarnhollow demo data.
- s189 [1313.55–1318.18] world still/still-push | And even the products that can be measured come with a range, not a point.
- s190 [1318.18–1322.49] paper number/number-land {{el_point}}@1318.68 | That -2.76 has an honest interval around it,
- s191 [1322.49–1331.62] paper timeline/timeline {{el_ci_low}}@1322.81 {{el_ci_high}}@1324.61 {{el_ci_crosses}}@1326.83 | from -5.87 to 0.35. It crosses zero. At one end, this product is very sensitive to price.
- s192 [1331.62–1338.76] world still/still-push | At the other, the estimate can't rule out that price doesn't matter at all. The range comes from the standard error,
- s193 [1338.76–1343.24] world still/still-push | which is how far another run of periods like these could move the slope,
- s194 [1343.24–1347.61] world still/still-push | times a multiplier that grows as the periods get fewer.
- s195 [1347.61–1353.86] world still/still-push | A tool that hands you a single number without the range is telling you something it doesn't know.
### Beat 40. VISUAL: the {{el_periods}} periods drawn as a short row of ticks, a second row running off the edge of the paper with no figure on it; range-band narrowing as the price's spread widens, not as the months pass, labelled Tarnhollow demo data.
- s196 [1353.86–1359.74] world still/still-push | So why not wait for a better number? Because waiting with the price held still adds nothing at all.
- s197 [1359.74–1364.69] world still/still-push | That's the dime. And even with the price moving, certainty is slow.
- s198 [1364.69–1373.02] world still/still-push | To shrink the error on this one estimate to a tight band from its own history would take far more periods than any business will ever have.
- s199 [1373.02–1379.61] world still/still-push | And the fastest way to narrow it isn't more months. It's more movement: the wider your price has ranged,
- s200 [1379.61–1387.53] world still/still-push | the tighter the slope. A dime that never moves never narrows at all. So the honest move isn't to wait for certainty.
- s201 [1387.53–1395.21] world still/still-push | It's to decide under uncertainty, in steps small enough that a wrong one is cheap, and to measure every step.
### Beat 41. VISUAL: counterfactual on the demo product's profit band: the top worked out at the estimate alone, one mark on the price axis beside today's price, the current price as the hollow dot and a small step up as the solid dot, the step's size in blue, Tarnhollow demo data.
- s202 [1395.21–1400.44] world still/still-push | So how do you step when you can't see the top? Work the formula at the estimate alone.
- s203 [1400.44–1405.28] world still/still-push | If that puts the best price above today's, step up: near minus one
- s204 [1405.28–1412.72] world still/still-push | the top runs off to the right, and the estimate agrees. If it puts it below today's while the range still reaches minus one,
- s205 [1412.72–1419.22] world still/still-push | hold: the estimate says down, and the range can't rule out far up. And never by much:
- s206 [1419.22–1427.80] paper number/number-land {{pm_step_cap}}@1422.13 | the demo's model caps any single move at 5%, so that a wrong step costs little and a right one shows up in the data.
- s207 [1427.80–1435.35] world still/still-push | A small step you can measure beats a confident number you can't. And sometimes the right step is none at all.
### Beat 42. VISUAL: range-band of every fitted demo product's interval drawn side by side, each with today's price marked inside its band, a single word, "hold", landing in ink; then the {{el_skus_insufficient}} refused products at the end as empty outlines with no band at all, labelled Tarnhollow demo data.
- s208 [1435.35–1441.80] world still/still-push | Because here's what the model says about this whole catalogue. Weighing every product's history together,
- s209 [1441.80–1448.98] paper number/number-land {{el_p_optimal}}@1442.41 | it puts 97% on these prices already being about right, and it recommends no price step at all.
- s210 [1448.98–1456.32] world still/still-push | That's an answer, and a useful one. A model that can say hold is a model you can believe when it says move.
- s211 [1456.32–1461.95] world still/still-push | But notice what made the answer possible: every product it judged had moved its price.
- s212 [1461.95–1467.80] paper number/number-land {{el_skus_insufficient}}@1462.71 | About the 2 dimes, it can't say anything at all. That's the real cost of a dime.
- s213 [1467.80–1473.61] world still/still-push | Not a number on a report. A number nobody can know until the price moves.
### Beat 43. VISUAL: doc-highlight on the Printers' Ink sentence, the same page as the advertising beat; formula-build: the margin a held price gives up each month, set beside a campaign's monthly spend, as terms only, no figures.
- s214 [1473.61–1480.97] world still/still-push | And sometimes the price is the brand, the way the dime was. A product sold as a gift under a round number.
- s215 [1480.97–1485.30] world still/still-push | A line that's always the cheapest, or always the premium one.
- s216 [1485.30–1491.59] world still/still-push | That's a real asset, and Printers' Ink was right about it: a price can be an advertising idea.
- s217 [1491.59–1498.24] world still/still-push | But treat it like one. An advertising idea has a cost, and you'd measure any other advertising.
- s218 [1498.24–1507.85] world still/still-push | Know what holding the line costs you in margin each month, the same way you'd know what a campaign costs, and decide on purpose whether it's worth it.
- s219 [1507.85–1513.26] world still/still-push | Woolworth's successors held theirs until it stopped them selling what their customers wanted.
- s220 [1513.26–1520.78] paper number/number-land {{w_1932}}@1517.02 | You can know long before that. Now go back to 1932, because the company finally did it right:
### Beat 44. VISUAL: split-then-now: the {{w_1932}} trial stores on a map of the West and South, then a single demo product's price stepping over time with its predicted and measured units drawn together, labelled Tarnhollow demo data; timeline of steps, each landing as spoken.
- s221 [1520.78–1525.00] world still/still-push | a test, then a rollout. But remember the West.
- s222 [1525.00–1529.25] world still/still-push | Comparing places tells you about the places as much as the prices,
- s223 [1529.25–1535.72] world still/still-push | unless the places are picked at random and some are left alone. Most online sellers can't do that:
- s224 [1535.72–1540.12] world still/still-push | one listing, one price. So the test open to you is in time.
- s225 [1540.12–1545.83] world still/still-push | A small step, measured against what you wrote down before you took it. Then the next step.
- s226 [1545.83–1551.88] world still/still-push | Not a test and a promise. A test, then another test. So here's this week.
### Beat 45. VISUAL: formula-build listing the steps as terms, each landing as spoken, the best-price formula built term by term; receipt: one demo product's line, its price spread, its slope and range, the step and the prediction written before it, labelled Tarnhollow demo data.
- s227 [1551.88–1561.45] world still/still-push | Pick your top products by revenue. For each one, pull its price and units by period, as far back as you have, and divide each period's units by its days.
- s228 [1561.45–1566.02] world still/still-push | Leave out stockouts, big deals and launches. Check the rule:
- s229 [1566.02–1573.01] paper pair/number-pair {{el_min_price_cv}}@1567.89 {{el_min_periods}}@1570.01 | has the spread of its prices reached 2% of their average, over at least 5 periods? If not, you have a dime.
- s230 [1573.01–1580.09] world still/still-push | Write it down. For the ones that have moved, fit the line: the log of units a day against the log of price.
- s231 [1580.09–1588.93] world still/still-push | Read the slope and its range: its standard error, times the multiplier for your number of periods, which the course's spreadsheet gives you.
- s232 [1588.93–1595.48] world still/still-push | If the slope is shallower than minus one, the direction is up. If the range is clear of minus one,
- s233 [1595.48–1603.71] world still/still-push | the top is your costs that don't move with price, divided by what the share-of-price fees leave you, times the slope over one plus the slope:
- s234 [1603.71–1609.82] world still/still-push | step toward it. If the range reaches minus one, work that formula at the estimate alone:
- s235 [1609.82–1614.42] world still/still-push | above today's price, step up; below it, hold. Either way,
- s236 [1614.42–1619.78] paper number/number-land {{pm_step_cap}}@1615.35 | by no more than 5%. Before you take the step, write down the units you expect:
- s237 [1619.78–1626.46] world still/still-push | today's, times one plus the step, raised to the slope. While it's live, watch your conversion, and on Amazon
- s238 [1626.46–1633.50] world still/still-push | your Buy Box share; if either drops, reverse the step. When the period ends, add it to the history and fit again.
- s239 [1633.50–1638.39] world still/still-push | And if no price on the curve makes your margin, the cost is the thing to move,
- s240 [1638.39–1642.19] world still/still-push | the way Woolworth's buyers moved the ring and the toy.
### Beat 46. VISUAL: still-push resuming on the cold open's coin in the same framing, then the modern price label on a shelf edge in the same framing; kinetic-thesis: "It never told Woolworth what his customers would have paid.".
- s241 [1642.19–1647.92] paper number/number-land {{w_day1}}@1642.49 | $127.65, in nickels, on a Saturday in Lancaster.
- s242 [1647.92–1655.30] paper number/number-land {{w_ceiling_span}}@1649.31 | A ceiling held for more than 50 years. The tallest building in the world, paid for in nickels and dimes.
- s243 [1655.30–1660.92] world still/still-push | It never told Woolworth what his customers would have paid. Your prices can.
### Beat 47. VISUAL: range-band on the demo catalogue's fits, every product's interval drawn at once, the band holding while the voice names what it takes, labelled Tarnhollow demo data; end card at "hubricon.com/learn".
- s244 [1660.92–1668.62] world still/still-push | You can do this week's steps by hand for a few products, and it's worth doing. Where it breaks is everything that makes demand messy.
- s245 [1668.62–1676.46] world still/still-push | Seasons. Your own ads switching on and off. Prices you changed because demand moved, which tilt the line.
- s246 [1676.46–1684.23] world still/still-push | A competitor's sale the same week. Products that take sales from each other, so a raise on one sells more of another.
- s247 [1684.23–1690.83] world still/still-push | Products with too little history, which have to borrow strength from the rest of the catalogue, the way this one did.
- s248 [1690.83–1696.84] world still/still-push | And a range on every estimate that has to become the right size of step for what's still unknown.
- s249 [1696.84–1702.88] world still/still-push | This is applied mathematics: the same tools actuaries use to price risk.
- s250 [1702.88–1708.36] world still/still-push | It's what I studied, and it's what Hubricon is built to run, every week, for every product.
- s251 [1708.36–1714.92] world still/still-push | The whole method, with the spreadsheet, is free at hubricon.com/learn, in the Price Curve course.
- s252 [1714.92–1724.69] world still/still-push | You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
