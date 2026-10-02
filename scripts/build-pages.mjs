// Bakes figures, numbers and shared text into the pages that carry them.
//
//   node scripts/build-pages.mjs           rewrite every page in PAGES
//   node scripts/build-pages.mjs --check   exit 1 if any page is out of date
//
// Reads ratecard.json (Amazon's published cards), data/montecarlo.json and
// data/case-study.json (written by scripts/case-study.mjs), scripts/blocks/, and the
// data behind the shared pieces (scripts/site-blocks.mjs: data/library.json,
// data/testimonials.json, data/scoreboard-illustration.json), then, on each page:
//   - replaces whatever sits between <!-- build:NAME --> and <!-- /build:NAME -->
//     with the block of that name: a chart's finished still frame, shared text
//     such as the attribution rules, which the terms and /honesty must carry word
//     for word, or a shared piece: the nav, the footer, the library, a video slot,
//     the results wall, the scoreboard;
//   - fills every element marked data-fill="key" with the figure it names, so no
//     number on a page is typed by hand;
//   - writes the FAQPage structured data from the FAQ as the page shows it;
//   - on the home page, counts the words a visitor sees on load (printed, no longer
//     capped: the founder retired the 900-word cap on 2026-10-01).
// scripts/build-pages.test.mjs runs the --check path, so a stale page fails CI.
import { readFileSync, writeFileSync } from "node:fs";
import * as fees from "../lib/fees.js";
import { monteCarloSVG, staircaseSVG, agingSVG, agingStripSVG, fitSVG, profitSVG, cashSVG, lateSVG, parcelSVG, orderSVG, waterfallSVG, responseSVG, paybackSVG, usd } from "../assets/charts.mjs";
import * as priceCurve from "../assets/price-curve.mjs";
import { STORAGE } from "./case-study.mjs";
import { siteBlocks } from "./site-blocks.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const longDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };
const shortDate = (iso) => { const [, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1].slice(0, 3)} ${d}`; };
const n = (v) => Math.round(v).toLocaleString("en-US");
const dollars2 = (v) => `$${v.toFixed(2)}`;
const millions = (v) => `$${(v / 1e6).toFixed(1).replace(/\.0$/, "")}M`;

// An invented parcel for the home page's Shopify staircase: a few tenths of an ounce past a pound.
const PARCEL_OZ = 16.4;

export function figures(rc, mc, cs) {
  const priced = cs.priced_on;
  const ls = (card, oz) => fees.fulfilmentFee(rc, "large_standard", oz, 25, priced, card);
  const nonPeak = fees.cardNamed(rc, "non_peak"), peak = fees.cardNamed(rc, "peak");
  const treads = (card) => card.large_standard.map(([edge]) => [edge, ls(card, edge)]);
  const stairs = {
    treads: treads(nonPeak), alt: treads(peak),
    label: `${shortDate(cs.cards.non_peak.effective)} – ${shortDate(cs.cards.non_peak.through)}`,
    altLabel: `${shortDate(cs.cards.peak.effective)} – ${shortDate(cs.cards.peak.through)}`,
    listing: { oz: cs.listing.item_weight_oz, fee: cs.step.non_peak.fee_now },
    edge: { oz: cs.step.edge_oz, fee: cs.step.non_peak.fee_at_edge },
    step: cs.step.non_peak.step,
  };
  // The staircase is drawn from the card itself; the case study's two dots must sit on it.
  const onTread = (oz) => stairs.treads.find(([edge]) => oz <= edge)[1];
  if (Math.abs(onTread(stairs.listing.oz) - stairs.listing.fee) > 1e-3 || Math.abs(onTread(stairs.edge.oz) - stairs.edge.fee) > 1e-3) {
    throw new Error("the case study's fees are not on the published card; re-run scripts/case-study.mjs");
  }

  const aging = {
    cliff: 271,
    ticks: [0, 181, 271, 366],
    bands: [{ from: 0, to: 180, value: cs.aging.under_181_per_1000_units_month },
      ...cs.aging.bands.map((b) => ({ from: b.from, to: b.to, value: b.per_1000_units_month }))],
  };

  const end = mc.months.length - 1;
  // The parcel staircase: the rate card's USPS rows and the step at the pound line, by zone
  const parcel = { rows: rc.carrier.ground_commercial, parcel_oz: PARCEL_OZ, step: fees.carrierSteps(rc)[16] };
  if (!parcel.step) throw new Error("the rate card has no USPS step at one pound");
  const learn = learnFigures(rc, cs);
  const pc = priceCurveFigures(json("data/learn-price-curve.json"));
  const cc = capitalCashFigures(json("data/learn-capital-cash.json"));
  const sm = shopifyMarginFigures(json("data/learn-shopify-margin.json"), rc);
  const om = operatorsMathFigures(json("data/learn-operators-math.json"), rc);
  const blocks = {
    ...learn.blocks,
    ...pc.blocks,
    ...cc.blocks,
    ...sm.blocks,
    ...om.blocks,
    ...siteBlocks(),
    attribution: "\n" + read("scripts/blocks/attribution.html").trim() + "\n",
    // /case-study: the home page's sections as they stand (the build loop refreshes it after index.html)
    "case-study-page": caseStudySections(read("index.html")),
    "mc-mood-wide": monteCarloSVG(mc, { id: "mc-mood-w", w: 560, h: 440, m: { t: 8, r: 8, b: 8, l: 8 }, variant: "mood" }),
    // The hero's: wide, wordless, behind the headline (HUBRICON_SPEC.md: "muted behind or beside it").
    "mc-mood-hero": monteCarloSVG(mc, { id: "mc-mood-h", w: 1000, h: 560, m: { t: 12, r: 12, b: 12, l: 12 }, variant: "mood" }),
    "mc-mood-narrow": monteCarloSVG(mc, { id: "mc-mood-n", w: 360, h: 200, m: { t: 6, r: 6, b: 6, l: 6 }, paths: 20, variant: "mood" }),
    "mc-wide": monteCarloSVG(mc, { id: "mc-w", w: 760, h: 420, m: { t: 24, r: 120, b: 44, l: 64 }, font: 13 }),
    "mc-narrow": monteCarloSVG(mc, { id: "mc-n", w: 360, h: 340, m: { t: 16, r: 82, b: 38, l: 50 }, paths: 20, font: 12 }),
    "stairs-wide": staircaseSVG(stairs, { id: "st-w", w: 760, h: 420, m: { t: 64, r: 24, b: 48, l: 64 }, font: 13, xMax: 20 }),
    "stairs-narrow": staircaseSVG(stairs, { id: "st-n", w: 360, h: 420, m: { t: 60, r: 26, b: 42, l: 50 }, font: 12, xMax: 16 }),
    // Shopify's staircase: USPS Ground Advantage's published rows, one invented parcel just past a pound
    "parcel-wide": parcelSVG(parcel, { id: "pa-w", w: 760, h: 380, m: { t: 64, r: 24, b: 48, l: 64 }, font: 13 }),
    "parcel-narrow": parcelSVG(parcel, { id: "pa-n", w: 360, h: 380, m: { t: 60, r: 16, b: 42, l: 50 }, font: 12 }),
    "aging-wide": agingSVG(aging, { id: "ag-w", w: 760, h: 300, m: { t: 32, r: 24, b: 48, l: 64 }, font: 13 }),
    "aging-narrow": agingSVG(aging, { id: "ag-n", w: 360, h: 260, m: { t: 28, r: 8, b: 40, l: 46 }, font: 12 }),
    "strip-wide": agingStripSVG(aging, { id: "sp-w", w: 1040, h: 200, m: { t: 44, r: 8, b: 66, l: 8 }, font: 15 }),
    "strip-narrow": agingStripSVG(aging, { id: "sp-n", w: 360, h: 190, m: { t: 40, r: 6, b: 60, l: 6 }, font: 12, ticks: [0, 271] }),
  };
  return {
    blocks,
    // The charts' own inputs, so a film can draw the same charts at its own size
    // (content/film/scenes.mjs) instead of scaling the page's.
    charts: { stairs, aging, mc },
    fill: {
      years: n(cs.simulation.years),
      months_total: n(cs.simulation.months),
      months_losing: n(mc.share_losing * cs.simulation.months),
      who: cs.who,
      who_lower: cs.who.charAt(0).toLowerCase() + cs.who.slice(1),
      category: cs.category,
      leak_p10: usd(cs.leak_per_year.p10),
      leak_p90: usd(cs.leak_per_year.p90),
      weight: cs.listing.item_weight_oz.toFixed(1),
      edge: String(cs.step.edge_oz),
      step_np: dollars2(cs.step.non_peak.step),
      step_peak: dollars2(cs.step.peak.step),
      // an estimate, so rounded down (HUBRICON_SPEC.md: "ranges, never points; rounded down")
      units: n(Math.floor(cs.listing.est_monthly_units / 100) * 100),
      mc_p10: usd(mc.percentiles.p10[end], { step: 1000 }),
      mc_p50: usd(mc.percentiles.p50[end], { step: 1000 }),
      mc_p90: usd(mc.percentiles.p90[end], { step: 1000 }),
      aged_rate_before: dollars2(cs.aging.bands.find((b) => b.to === 270).surcharge_per_cuft),
      aged_rate_after: dollars2(cs.aging.bands.find((b) => b.from === 271).surcharge_per_cuft),
      brands_modeled: n(cs.selection.brands_modeled),
      brands_silent: n(cs.selection.brands_silent),
      silence_share: `${Math.round((cs.selection.brands_silent / cs.selection.brands_modeled) * 100)}%`,
      silence_on: longDate(cs.selection.measured_on),
      captured_on: longDate(cs.captured_on),
      priced_on: longDate(cs.priced_on),
      rank_band: cs.listing.rank_band,
      surcharge: `${+(cs.cards.fuel_surcharge * 100).toFixed(1)}%`,
      referral: `${Math.round(cs.cards.referral_rate * 100)}%`,
      landed: `${Math.round(cs.profit_basis.landed_cost_share * 100)}%`,
      sales_lo: millions(cs.listing.est_annual_sales[0]),
      sales_hi: millions(cs.listing.est_annual_sales[1]),
      card_np: `${shortDate(cs.cards.non_peak.effective)} to ${shortDate(cs.cards.non_peak.through)}, ${cs.cards.non_peak.through.slice(0, 4)}`,
      card_peak: `${shortDate(cs.cards.peak.effective)} to ${shortDate(cs.cards.peak.through)}`,
      card_np_full: `${longDate(cs.cards.non_peak.effective).replace(/, \d{4}$/, "")} to ${longDate(cs.cards.non_peak.through).replace(/, \d{4}$/, "")}`,
      card_peak_full: `${longDate(cs.cards.peak.effective).replace(/, \d{4}$/, "")} to ${longDate(cs.cards.peak.through).replace(/, \d{4}$/, "")}`,
      storage_effective: longDate(cs.aging.storage_effective),
      parcel_oz: String(PARCEL_OZ),
      parcel_step_lo: `$${parcel.step[0].toFixed(2)}`,
      parcel_step_hi: `$${parcel.step[1].toFixed(2)}`,
      usps_effective: longDate(rc.carrier.effective),
      // Shopify Payments, Basic plan: The Price Curve's "On Shopify the split is the same"
      learn_shop_rate: `${+(rc.shopify.payments[rc.shopify.default_plan].rate * 100).toFixed(2)}%`,
      learn_shop_fixed: `$${rc.shopify.payments[rc.shopify.default_plan].fixed.toFixed(2)}`,
      ...learn.fill,
      ...pc.fill,
      ...cc.fill,
      ...sm.fill,
      ...om.fill,
    },
  };
}

/**
 * The Fee Staircase course's figures (/learn/fee-staircase). The cards as tables,
 * and the worked examples, each priced here by lib/fees.js on the published card so
 * the lesson's arithmetic and the engine's are the same arithmetic. The examples
 * are invented listings and the lessons say so; the case study's figures come from
 * the fill keys above.
 */
function learnFigures(rc, cs) {
  const day = cs.priced_on;                                    // non-peak, after the fuel surcharge began
  const nonPeak = fees.cardNamed(rc, "non_peak"), peak = fees.cardNamed(rc, "peak");
  const BAND_PRICE = [9.99, 25, 99];                            // one price inside each column
  const fee = (card, tier, oz, price) => fees.fulfilmentFee(rc, tier, oz, price, day, card);
  const cents = (v) => `$${v.toFixed(2)}`;
  const shortCard = (c) => `${shortDate(c.effective)} to ${shortDate(c.through)}`;

  const table = (tier, caption, label) => {
    const rows = (tier === "small_standard" ? nonPeak.small_standard : nonPeak.large_standard).map(([edge]) => edge);
    const head = `<thead><tr><th scope="col" rowspan="2">Up to</th><th scope="colgroup" colspan="3">${shortCard(nonPeak)}</th><th scope="colgroup" colspan="3">${shortCard(peak)}</th></tr>` +
      `<tr>${["Under $10", "$10 to $50", "Over $50"].map((b) => `<th scope="col">${b}</th>`).join("").repeat(2)}</tr></thead>`;
    const oz = (e) => (e % 16 === 0 && e >= 16 ? `${e / 16} lb` : `${e} oz`);
    const body = rows.map((edge) => `<tr><th scope="row">${oz(edge)}</th>${[nonPeak, peak].flatMap((card) => BAND_PRICE.map((p) => `<td>${cents(fee(card, tier, edge, p))}</td>`)).join("")}</tr>`).join("");
    let tail = "";
    if (tier === "large_standard") {
      const base = [nonPeak, peak].flatMap((card) => BAND_PRICE.map((p) => `<td>${cents(fee(card, tier, 48.01, p) - card.over_3lb_per_4oz * (1 + rc.fba.fuel_surcharge))}</td>`)).join("");
      tail = `<tr class="over"><th scope="row">Over 3 lb, base</th>${base}</tr>`;
    }
    return `\n<div class="card-table" role="region" aria-label="${label}" tabindex="0"><table>\n<caption>${caption}</caption>\n${head}\n<tbody>${body}${tail}</tbody>\n</table></div>\n`;
  };

  // The price edges, across every standard-size row of the card in force.
  const jumps = (from, to) => {
    const out = [];
    for (const tier of ["small_standard", "large_standard"]) {
      for (const [edge] of nonPeak[tier]) out.push(fee(nonPeak, tier, edge, BAND_PRICE[to]) - fee(nonPeak, tier, edge, BAND_PRICE[from]));
    }
    return [Math.min(...out), Math.max(...out)];
  };
  const peakSteps = [];
  for (const tier of ["small_standard", "large_standard"]) {
    for (const [edge] of nonPeak[tier]) peakSteps.push(fee(peak, tier, edge, 25) - fee(nonPeak, tier, edge, 25));
  }
  const ten = jumps(0, 1);

  // Worked example: the price edge. An invented 13 oz kitchen item at $10.49.
  const PX = { price: 10.49, category: "kitchen & dining", itemWeightOz: 13, dims: [9, 6, 2] };
  const px = fees.describeItem(rc, PX);
  const pxFind = fees.priceBandEdge(rc, nonPeak, px, day);
  const pxHi = fee(nonPeak, px.tier, px.billableWeightOz, px.price), pxLo = fee(nonPeak, px.tier, px.billableWeightOz, pxFind.evidence.targetPrice);
  // The size tier: an invented 6 oz item, 15 × 12 × 0.9 in, at $12.99.
  const tr = fees.describeItem(rc, { price: 12.99, category: "kitchen & dining", itemWeightOz: 6, dims: "15 x 12 x 0.9" });
  const trFind = fees.sizeTierEdge(rc, nonPeak, tr, day);
  // The box: an invented 4 lb item in an 18 × 14 × 7 in box, at $39.99.
  const bx = fees.describeItem(rc, { price: 39.99, category: "home & kitchen", itemWeightOz: 64, dims: "18 x 14 x 7" });
  const bxFind = fees.dimWeightOverage(rc, nonPeak, bx, day);
  if (!pxFind || !trFind || !bxFind) throw new Error("a /learn worked example no longer finds its edge on the card; rewrite the example");
  const tens = (v) => n(Math.round(v / 10) * 10);
  const u = (rank, cat) => fees.estimateUnits(rc, rank, cat);
  const band = (from) => cs.aging.bands.find((b) => b.from === from);
  const aged = (from) => dollars2(band(from).surcharge_per_cuft);

  // The course's own "Fill in the example" (assets/learn-fee-staircase.js): lesson 4's invented listing.
  const fsExample = { name: "An invented kitchen item (lesson 4's example)", price: PX.price, category: PX.category, weight: PX.itemWeightOz,
    l: PX.dims[0], w: PX.dims[1], h: PX.dims[2], rank: "", cost: "" };
  return {
    blocks: {
      "fs-example-json": `\n<script type="application/json" id="fs-example">${JSON.stringify(fsExample)}</script>\n`,
      "learn-card-small": table("small_standard", "Small standard: fulfilment fee per unit, with the fuel and logistics surcharge", "Small standard fee card"),
      "learn-card-large": table("large_standard", "Large standard: fulfilment fee per unit, with the fuel and logistics surcharge", "Large standard fee card"),
    },
    fill: {
      learn_rc_date: longDate(rc.generated),
      learn_over3: cents(nonPeak.over_3lb_per_4oz),
      learn_ten_min: cents(ten[0]),
      learn_ten_max: cents(ten[1]),
      learn_peak_min: cents(Math.min(...peakSteps)),
      learn_peak_max: cents(Math.max(...peakSteps)),
      learn_px_fee_hi: cents(pxHi),
      learn_px_fee_lo: cents(pxLo),
      // Three places, so the lesson's subtraction adds up on the page.
      learn_px_jump: `$${pxFind.evidence.feeJumpLow.toFixed(3)}`,
      learn_px_given: `$${((px.price - pxFind.evidence.targetPrice) * (1 - pxFind.evidence.referralRate)).toFixed(3)}`,
      learn_px_net: `$${pxFind.perUnitLow.toFixed(3)}`,
      learn_px_be: cents(pxFind.evidence.breakEvenPrice),
      learn_tier_small: cents(trFind.evidence.smallFee),
      learn_tier_large: cents(trFind.evidence.largeFee),
      learn_tier_gap: cents(trFind.perUnitLow),
      learn_box_dim_lb: (bx.dimWeightOz / 16).toFixed(1),
      learn_box_fee_dim: cents(fee(nonPeak, bx.tier, bx.dimWeightOz, bx.price)),
      learn_box_fee_item: cents(fee(nonPeak, bx.tier, bx.itemWeightOz, bx.price)),
      learn_box_gap: cents(bxFind.perUnitLow),
      learn_uc_a: String(rc.units_curve.a),
      learn_uc_b: String(rc.units_curve.b),
      learn_uc_knee: n(rc.units_curve.head_knee),
      learn_u_5000: tens(u(5000, "kitchen & dining")),
      learn_u_5000_lo: tens(u(5000, "kitchen & dining") * fees.UNITS_LOW),
      learn_u_5000_hi: tens(u(5000, "kitchen & dining") * fees.UNITS_HIGH),
      learn_u_30000: tens(u(30000, "home & kitchen")),
      learn_u_800: tens(u(800, "beauty & personal care")),
      learn_stor_off: dollars2(STORAGE.per_cuft_month.offpeak),
      learn_stor_peak: dollars2(STORAGE.per_cuft_month.peak),
      learn_aged_181: aged(181),
      learn_aged_211: aged(211),
      learn_aged_301: aged(301),
      learn_aged_331: aged(331),
      learn_aged_366: aged(366),
      learn_aged_min: dollars2(STORAGE.aged_min_per_unit_366),
      learn_cliff_x: (band(271).surcharge_per_cuft / band(241).surcharge_per_cuft).toFixed(1),
      learn_cs_cuft: cs.aging.cubic_feet_per_unit.toFixed(3),
      learn_cs_270: dollars2(band(241).per_1000_units_month),
      learn_cs_271: dollars2(band(271).per_1000_units_month),
    },
  };
}

/**
 * The Price Curve's figures (/learn/price-curve). Every number is the engine's, computed by
 * scripts/learn/price_curve.py into data/learn-price-curve.json from an invented listing: its
 * history and costs are invented, its fees are Amazon's. Nothing here does arithmetic beyond
 * formatting and the charts' own drawing, except the "Check yourself" answers, which come from
 * assets/price-curve.mjs: the course's own port, held to the engine by its golden cases.
 */
function priceCurveFigures(pc) {
  const sign = (v) => (v < 0 ? "−" : "+");
  const neg = (v, d = 2) => (v < 0 ? `−${Math.abs(v).toFixed(d)}` : v.toFixed(d));
  const money = (v) => `$${v.toFixed(2)}`;
  const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  const signed$ = (v) => `${sign(v)}$${Math.abs(Math.round(v)).toLocaleString("en-US")}`;
  const pct = (v, d = 1) => `${(Math.abs(v) * 100).toFixed(d)}%`;
  const e = pc.economics, b = pc.best, f = pc.fit, d = pc.discount, r = pc.runs;
  const five = pc.table.find((t) => Math.abs(t.change - 0.05) < 1e-9);
  const tenOff = pc.table.find((t) => Math.abs(t.change + 0.10) < 1e-9);
  const fill = {
    learn_pc_what: pc.what,
    learn_pc_n: String(f.n), learn_pc_dof: String(f.dof), learn_pc_t: f.t.toFixed(2), learn_pc_cv: pct(f.price_cv),
    learn_pc_eps: neg(f.elasticity), learn_pc_eps_abs: Math.abs(f.elasticity).toFixed(2),
    learn_pc_p_min: money(Math.min(...pc.history.map((h) => h.price))), learn_pc_p_max: money(Math.max(...pc.history.map((h) => h.price))),
    learn_pc_se: f.std_err.toFixed(2), learn_pc_se_classical: f.std_err_classical.toFixed(2),
    learn_pc_lo: neg(f.ci[0]), learn_pc_hi: neg(f.ci[1]), learn_pc_r2: f.r_squared.toFixed(2),
    learn_pc_min_periods: String(pc.rules.min_periods), learn_pc_min_cv: pct(pc.rules.min_price_cv, 0),
    learn_pc_cap: pct(pc.rules.step_cap, 0), learn_pc_pole_log_sd: pct(pc.rules.pole_optimum_log_sd, 0),
    learn_pc_price: money(e.price), learn_pc_units: e.units_month.toLocaleString("en-US"), learn_pc_cost: money(e.landed_cost),
    learn_pc_referral: pct(e.referral, 0), learn_pc_fba: money(e.fba_fee), learn_pc_fixed: money(e.fixed + e.landed_cost),
    learn_pc_margin: money(e.margin), learn_pc_profit: dollars(e.profit_month), learn_pc_weight: `${pc.weight_oz}`,
    learn_pc_base: money(b.base), learn_pc_factor: b.factor.toFixed(2), learn_pc_best: money(b.price),
    learn_pc_best_up: pct(b.price / e.price - 1), learn_pc_step: money(b.step_price),
    learn_pc_step_delta: signed$(b.step_delta), learn_pc_best_delta: signed$(b.best_delta),
    learn_pc_be5: pct(five.breakeven), learn_pc_im5: pct(five.implied), learn_pc_d5: signed$(five.delta),
    learn_pc_be_m10: pct(tenOff.breakeven), learn_pc_im_m10: pct(tenOff.implied), learn_pc_d_m10: signed$(tenOff.delta),
    learn_pc_disc: pct(d.rate, 0), learn_pc_disc_price: money(d.price), learn_pc_disc_margin: money(d.margin),
    learn_pc_disc_needed: pct(d.needed, 0), learn_pc_disc_implied: pct(d.implied, 0), learn_pc_disc_delta: signed$(d.delta),
    learn_pc_runs: String(r.runs), learn_pc_true: neg(r.true_elasticity, 1), learn_pc_se10: r.se_p10.toFixed(2),
    learn_pc_se50: r.se_p50.toFixed(2), learn_pc_se90: r.se_p90.toFixed(2), learn_pc_guard_share: pct(r.guard_share, 0),
    learn_pc_up_share: pct(r.up_share, 0),
    learn_pc_np_eps: neg(pc.near_pole.elasticity), learn_pc_np_se: pc.near_pole.std_err.toFixed(2),
    learn_pc_np_lo: neg(pc.near_pole.ci[0]), learn_pc_np_hi: neg(pc.near_pole.ci[1]), learn_pc_np_factor: pc.near_pole.pole_factor.toFixed(1),
    learn_pc_in_eps: neg(pc.inelastic.elasticity, 1),
    // "Check yourself": one invented SKU for every exercise, answers from the course's own arithmetic.
    ...(() => {
      const X = { p: 20, cost: 5, fixed: 4, f: 0.15 };
      const best = priceCurve.bestPrice(-2, X.cost, X.f, X.fixed);
      return {
        learn_pc_q_p: dollars(X.p), learn_pc_q_cost: dollars(X.cost), learn_pc_q_fixed: dollars(X.fixed), learn_pc_q_f: pct(X.f, 0),
        learn_pc_q_costs: dollars(X.cost + X.fixed), learn_pc_q_gross: money((X.cost + X.fixed) / (1 - X.f)),
        learn_pc_q_raise_price: dollars(X.p * 1.05), learn_pc_q_coupon_price: dollars(X.p * 0.75),
        learn_pc_q_inelastic: pct(1 - 1.05 ** -0.7),
        learn_pc_q_margin: money(X.p * (1 - X.f) - X.cost - X.fixed),
        learn_pc_q_best: money(best),
        learn_pc_q_raise: pct(-priceCurve.breakEven(X.p, X.p * 1.05, X.cost, X.f, X.fixed)),
        learn_pc_q_raise_margin: money(X.p * 1.05 * (1 - X.f) - X.cost - X.fixed),
        learn_pc_q_coupon_margin: money(X.p * 0.75 * (1 - X.f) - X.cost - X.fixed),
        learn_pc_q_coupon: pct(priceCurve.breakEven(X.p, X.p * 0.75, X.cost, X.f, X.fixed), 0),
        learn_pc_q_step: money(priceCurve.stepPrice(X.p, X.p * 1.12, "up")),
        learn_pc_t3: priceCurve.tCritical(3).toFixed(2),
      };
    })(),
    learn_pc_lo_best: money((e.landed_cost + e.fixed) / (1 - e.referral) * f.ci[0] / (1 + f.ci[0])),
    learn_pc_hi_best: money((e.landed_cost + e.fixed) / (1 - e.referral) * f.ci[1] / (1 + f.ci[1])),
  };
  const fitData = { points: pc.history.map((h) => ({ price: h.price, perDay: h.units / h.days })), intercept: f.intercept,
    elasticity: f.elasticity, lo: f.ci[0], hi: f.ci[1] };
  const curve = { p0: e.price, q0: e.units_month, cost: e.landed_cost, fee: e.referral, fixed: e.fixed, eps: f.elasticity,
    lo: f.ci[0], hi: f.ci[1], best: b.price, step: b.step_price, range: [e.price * 0.76, e.price * 1.4] };
  const rows = pc.history.map((h) => `<tr><th scope="row">${h.label}</th><td class="num">${h.days}</td><td class="num">${h.units.toLocaleString("en-US")}</td><td class="num">${money(h.price)}</td><td class="num">${(h.units / h.days).toFixed(1)}</td></tr>`).join("");
  const be = pc.table.map((t) => `<tr><th scope="row">${sign(t.change)}${pct(t.change, 0)}</th><td class="num">${money(t.price)}</td><td class="num">${money(t.margin)}</td><td class="num">${t.breakeven === null ? "—" : `${sign(t.breakeven)}${pct(t.breakeven)}`}</td><td class="num">${sign(t.implied)}${pct(t.implied)}</td><td class="num">${signed$(t.delta)}</td></tr>`).join("");
  return {
    fill,
    blocks: {
      // The example, for the course's own "Fill in the example": the same figures the page prints.
      "pc-example-json": `\n<script type="application/json" id="pc-example">${JSON.stringify({ history: pc.history.map(({ days, units, price }) => ({ days, units, price })), economics: e, discount: d.rate })}</script>\n`,
      "pc-history": `\n<table class="data"><thead><tr><th scope="col">Period</th><th scope="col">Days</th><th scope="col">Units</th><th scope="col">Average price</th><th scope="col">Units a day</th></tr></thead><tbody>${rows}</tbody></table>\n`,
      "pc-breakeven": `\n<div class="table-scroll" role="region" aria-label="Break-even units at each price change" tabindex="0"><table class="data"><thead><tr><th scope="col">Change</th><th scope="col">Price</th><th scope="col">Per unit</th><th scope="col">Break-even units</th><th scope="col">Elasticity says</th><th scope="col">Profit a month</th></tr></thead><tbody>${be}</tbody></table></div>\n`,
      "pc-fit-wide": fitSVG(fitData, { id: "pcf-w", w: 680, h: 360, m: { t: 40, r: 16, b: 46, l: 56 }, font: 13 }),
      "pc-fit-narrow": fitSVG(fitData, { id: "pcf-n", w: 360, h: 300, m: { t: 36, r: 10, b: 42, l: 44 }, font: 12 }),
      "pc-profit-wide": profitSVG(curve, { id: "pcp-w", w: 680, h: 380, m: { t: 40, r: 132, b: 46, l: 64 }, font: 13 }),
      "pc-profit-narrow": profitSVG(curve, { id: "pcp-n", w: 360, h: 320, m: { t: 36, r: 12, b: 42, l: 50 }, font: 12, narrow: true }),
    },
  };
}

/**
 * The Shopify Margin's figures (/learn/shopify-margin). Every number is the engine's cards (cold/priors.py:
 * USPS Ground Advantage and Shopify Payments), computed by scripts/learn/shopify_margin.py into
 * data/learn-shopify-margin.json for an invented product. The rate card here is the same card,
 * exported; the parcel chart reads it, and must agree with the example's labels.
 */
function shopifyMarginFigures(sm, rc) {
  const money = (v) => `$${v.toFixed(2)}`;
  const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
  const x = sm.example, o = sm.order, p = sm.pound, f = sm.free, a = sm.anchor, ads = sm.ads;
  const plan = sm.cards.payments[x.plan];
  const lo = Math.min(...o.label_now), hi = Math.max(...o.label_now);
  if (JSON.stringify(rc.carrier.ground_commercial["32"]) !== JSON.stringify(sm.cards.usps["32"])) {
    throw new Error("shopify-margin: the rate card's USPS rows differ from the ones the course was computed on; rerun scripts/learn/shopify_margin.py");
  }
  const fill = {
    learn_sm_price: money(x.price), learn_sm_compare: money(x.compare_at), learn_sm_oz: String(x.packed_oz), learn_sm_landed: money(x.landed_cost),
    learn_sm_packing: money(x.packing), learn_sm_fee: money(o.fee), learn_sm_rate: `${+(plan[0] * 100).toFixed(2)}%`, learn_sm_fixed: money(plan[1]),
    learn_sm_gateway: pct(sm.cards.gateway_surcharge[x.plan]), learn_sm_label_lo: money(lo), learn_sm_label_hi: money(hi),
    learn_sm_kept_lo: money(o.contribution_lo), learn_sm_kept_hi: money(o.contribution_hi), learn_sm_usps_effective: longDate(rc.carrier.effective),
    learn_sm_over_by: String(p.over_by), learn_sm_step_lo: money(p.step[0]), learn_sm_step_hi: money(p.step[1]), learn_sm_orders: x.orders.toLocaleString("en-US"),
    learn_sm_month_lo: dollars(p.month_lo), learn_sm_month_hi: dollars(p.month_hi), learn_sm_line: dollars(x.free_line), learn_sm_share_over: pct(x.share_over),
    learn_sm_orders_over: f.orders_over.toLocaleString("en-US"), learn_sm_free_lo: dollars(f.subsidy_lo), learn_sm_free_hi: dollars(f.subsidy_hi),
    learn_sm_anchor: money(a.per_unit), learn_sm_anchor_share: pct(a.share), learn_sm_cat_share: pct(a.catalogue_share), learn_sm_step5: money(a.step5),
    learn_sm_roas_lo: ads.roas_lo.toFixed(2), learn_sm_roas_hi: ads.roas_hi.toFixed(2), learn_sm_roas_under_lo: ads.roas_under_lo.toFixed(2), learn_sm_roas_under_hi: ads.roas_under_hi.toFixed(2),
  };
  const order = { price: x.price, fee: o.fee, packing: x.packing, landed: x.landed_cost, labels: [o.label_now[0], o.label_now[7]], zones: [1, 8] };
  const parcel = { rows: rc.carrier.ground_commercial, parcel_oz: x.packed_oz, step: p.step };
  return {
    fill,
    blocks: {
      "sm-order-wide": orderSVG(order, { id: "smo-w", w: 680, h: 250, m: { t: 44, r: 8, b: 56, l: 8 }, font: 13 }),
      "sm-order-narrow": orderSVG(order, { id: "smo-n", w: 360, h: 250, m: { t: 40, r: 4, b: 60, l: 4 }, font: 12 }),
      "sm-parcel-wide": parcelSVG(parcel, { id: "smp-w", w: 680, h: 360, m: { t: 64, r: 24, b: 48, l: 64 }, font: 13 }),
      "sm-parcel-narrow": parcelSVG(parcel, { id: "smp-n", w: 360, h: 360, m: { t: 60, r: 16, b: 42, l: 50 }, font: 12 }),
    },
  };
}

/**
 * The Operator's Math's figures (/learn/operators-math). Every number is the engine's, computed by
 * scripts/learn/operators_math.py into data/learn-operators-math.json from an invented coffee roaster
 * (its customers and its ad curve simulated from stated parameters): the label and payment cards from
 * cold/priors.py, the ad curve from models/ad_efficiency.py, repeat orders and payback from models/clv.py.
 * Nothing here does arithmetic beyond formatting and the order's own subtraction for the waterfall.
 */
function operatorsMathFigures(om, rc) {
  const money = (v) => `$${v.toFixed(2)}`;
  const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
  const x = om.example, u = om.unit, a = om.ads, c = om.customers, p = om.payback, mo = om.month;
  const row = rc.carrier.ground_commercial["0"];
  if (Math.abs(row.reduce((t, v) => t + v, 0) / row.length - u.label) > 1e-3 || Math.min(...row) !== u.label_lo || Math.max(...row) !== u.label_hi) {
    throw new Error("operators-math: the rate card's under-a-pound USPS row differs from the one the course was computed on; rerun scripts/learn/operators_math.py");
  }
  const monthName = new Date(`${mo.month}-01T12:00:00Z`).toLocaleString("en-US", { month: "long", timeZone: "UTC" });
  const fill = {
    learn_om_price: money(x.price), learn_om_landed: money(x.landed_cost), learn_om_gross: money(u.gross), learn_om_gross_rate: pct(u.gross_rate),
    learn_om_fee: money(u.fee), learn_om_label: money(u.label), learn_om_label_lo: money(u.label_lo), learn_om_label_hi: money(u.label_hi),
    learn_om_packing: money(x.packing), learn_om_refund_share: pct(x.refund_share), learn_om_refunds: money(u.refunds),
    learn_om_before: money(u.before_ads), learn_om_rate: pct(u.rate, 1), learn_om_ad_per_order: money(u.ad_per_order),
    learn_om_after: money(u.after_ads), learn_om_after_rate: pct(u.after_rate, 1),
    learn_om_month: monthName, learn_om_month_spend: dollars(mo.spend), learn_om_month_orders: mo.orders.toLocaleString("en-US"), learn_om_month_new: String(mo.new),
    learn_om_be_roas: a.be_roas.toFixed(2), learn_om_be_acos: pct(a.be_acos, 1), learn_om_target: a.target.toFixed(1),
    learn_om_cost_at_target: money(a.cost_at_target), learn_om_lost_at_target: money(-a.kept_at_target),
    learn_om_days: String(a.days), learn_om_spend: dollars(a.spend), learn_om_average: a.average.toFixed(2), learn_om_marginal: a.marginal.toFixed(2),
    learn_om_marginal_p5: a.marginal_p5.toFixed(2), learn_om_marginal_p95: a.marginal_p95.toFixed(2),
    learn_om_breakeven: dollars(a.breakeven), learn_om_breakeven_p5: dollars(a.breakeven_p5), learn_om_breakeven_p95: dollars(a.breakeven_p95),
    learn_om_lost_month: dollars(a.lost_month), learn_om_life_be_roas: a.life_be_roas.toFixed(2), learn_om_life_breakeven: dollars(a.life_breakeven),
    learn_om_max_seen: dollars(a.max_seen),
    learn_om_cac: money(c.cac), learn_om_customers: c.n.toLocaleString("en-US"), learn_om_repeats_new: c.repeats_52w_new.toFixed(2),
    learn_om_repeats_truth: om.truth.repeats_52w_new.toFixed(2), learn_om_first: money(c.first), learn_om_repeat: money(c.repeat),
    learn_om_rev_ltv: money(c.rev_ltv), learn_om_rev_ltv_cac: c.rev_ltv_cac.toFixed(1), learn_om_margin_ltv: money(c.margin_ltv),
    learn_om_margin_ltv_cac: c.margin_ltv_cac.toFixed(2), learn_om_margin_ltv_cac_lo: c.margin_ltv_cac_band[0].toFixed(2), learn_om_margin_ltv_cac_hi: c.margin_ltv_cac_band[1].toFixed(2),
    learn_om_discount: pct(c.discount), learn_om_calibration: c.calibration.toFixed(2), learn_om_multiplier: c.multiplier.toFixed(2),
    learn_om_first_margin: money(p.weekly[0]), learn_om_weeks: String(p.weeks), learn_om_weeks_lo: String(p.band[0]), learn_om_weeks_hi: String(p.band[1]),
    learn_om_cash_out: dollars(mo.cash_out),
  };
  const wf = { price: x.price, ads: u.ad_per_order,
    costs: [["Landed cost", x.landed_cost], ["Payment fee", u.fee], ["Label", u.label], ["Packing", x.packing], ["Refunds", u.refunds]] };
  const val = (r, v) => (r.kind === "share" ? pct(v, v < 0.5 ? 1 : 0) : r.kind === "ratio" ? v.toFixed(v >= 3 ? 1 : 2) : v.toFixed(2));
  const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const ranked = `
        <div class="table-scroll" role="region" aria-label="The numbers that mislead, ranked" tabindex="0"><table class="data ranked">
          <thead><tr><th scope="col">#</th><th scope="col">The number</th><th scope="col">It says</th><th scope="col">True</th><th scope="col">How far off</th></tr></thead>
          <tbody>
${om.ranked.map((r, i) => `            <tr><td class="num">${i + 1}</td><th scope="row">${esc(r.number)}<span class="sub">True: ${esc(r.truth)}</span></th><td class="num">${val(r, r.says)}</td><td class="num">${val(r, r.true)}</td><td class="num"><b>${r.factor.toFixed(1)}×</b><span class="sub">${r.flatters ? "flatters" : "too strict"}</span></td></tr>`).join("\n")}
          </tbody>
        </table></div>
        `;
  return {
    fill,
    blocks: {
      "om-waterfall-wide": waterfallSVG(wf, { id: "omw-w", w: 680, h: 330, m: { t: 8, r: 8, b: 8, l: 0 }, font: 13, labelW: 150 }),
      "om-waterfall-narrow": waterfallSVG(wf, { id: "omw-n", w: 360, h: 330, m: { t: 8, r: 4, b: 8, l: 0 }, font: 12, labelW: 118 }),
      "om-response-wide": responseSVG(a, { id: "omr-w", w: 680, h: 380, m: { t: 44, r: 16, b: 62, l: 64 }, font: 13 }),
      "om-response-narrow": responseSVG(a, { id: "omr-n", w: 360, h: 360, m: { t: 40, r: 10, b: 58, l: 50 }, font: 12, narrow: true }),
      "om-payback-wide": paybackSVG({ weekly: p.weekly, cac: c.cac, weeks: p.weeks }, { id: "omp-w", w: 680, h: 340, m: { t: 44, r: 16, b: 44, l: 56 }, font: 13 }),
      "om-payback-narrow": paybackSVG({ weekly: p.weekly, cac: c.cac, weeks: p.weeks }, { id: "omp-n", w: 360, h: 320, m: { t: 40, r: 10, b: 40, l: 44 }, font: 12 }),
      "om-ranked": ranked,
    },
  };
}

/**
 * Capital & Cash's figures (/learn/capital-and-cash). Every number is the engine's, computed by
 * scripts/learn/capital_cash.py into data/learn-capital-cash.json from an invented garlic press
 * (The Price Curve's) and an invented spatula set. Nothing here does arithmetic beyond formatting,
 * the sums the lesson shows the reader doing, and the charts' own drawing.
 */
function capitalCashFigures(cc) {
  const money = (v) => `$${v.toFixed(2)}`;
  const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  const n0 = (v) => Math.round(v).toLocaleString("en-US");
  const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
  const g = cc.garlic, r = cc.reorder, cy = cc.cycle, c = cc.cash, l = cc.late, sv = cc.service, h = cc.hold;
  const sg = sv.garlic, ss = sv.spatula;
  const fill = {
    learn_cc_price: money(g.price), learn_cc_landed: money(g.landed_cost), learn_cc_margin: money(g.margin), learn_cc_lead: String(g.lead_days),
    learn_cc_rate: r.rate.toFixed(1), learn_cc_rate_sd: r.rate_sd.toFixed(1), learn_cc_units_month: n0(r.units_month), learn_cc_on_hand: n0(g.on_hand),
    learn_cc_sell_days: n0(cy.sell_days), learn_cc_payout_cycle: String(cy.payout_cycle), learn_cc_half_sell: (cy.sell_days / 2).toFixed(1).replace(/\.0$/, ""),
    learn_cc_reserve: String(cy.reserve_days), learn_cc_transit: String(cy.transit_days), learn_cc_paid_days: n0(cy.paid_days),
    learn_cc_ccc: cy.ccc.toFixed(1).replace(/\.0$/, ""),
    // the cash a cycle holds: units a day × landed cost × the days a dollar is gone (the lesson's own sum)
    learn_cc_tied: dollars(r.rate * g.landed_cost * cy.ccc),
    learn_cc_lead_cv: pct(r.lead_cv), learn_cc_lead_mean: n0(r.lead_demand_mean), learn_cc_rop: n0(r.reorder_point), learn_cc_rop_cf: n0(r.closed_form_rop),
    learn_cc_safety: n0(r.safety_stock), learn_cc_cover_extra: String(r.cover_extra_days), learn_cc_qty: n0(r.reorder_qty),
    learn_cc_wire: dollars(r.wire), learn_cc_wire_day: String(c.wire_day), learn_cc_cycle_days: String(r.cycle_days), learn_cc_rate2: r.rate.toFixed(2),
    learn_cc_days_above: ((g.on_hand - r.reorder_point) / r.rate).toFixed(1),
    learn_cc_start: dollars(c.start), learn_cc_fixed: dollars(c.fixed_month), learn_cc_ads: dollars(c.ad_month), learn_cc_horizon: String(c.horizon_days),
    learn_cc_paths: n0(c.paths), learn_cc_trough_day: String(c.trough_day), learn_cc_trough_med: dollars(c.trough_median),
    learn_cc_trough_p5: dollars(c.trough_p5), learn_cc_trough_es: dollars(c.trough_es), learn_cc_need_es: dollars(c.need_es),
    learn_cc_start_less: dollars(c.start - 500), learn_cc_start_less2: dollars(c.start - 1000),
    learn_cc_ruin_less: pct(c.ruin_at["-500"]), learn_cc_ruin_less2: pct(c.ruin_at["-1000"]),
    learn_cc_p_on: pct(l.on_time.p_out), learn_cc_p_late: pct(l.two_weeks.p_out), learn_cc_short_on: n0(l.on_time.units_short),
    learn_cc_short_late: n0(l.two_weeks.units_short), learn_cc_late_pos: n0(l.two_weeks.position), learn_cc_late_days: String(l.days),
    learn_cc_lost_on: dollars(l.lost_on_time), learn_cc_lost_late: dollars(l.lost_late),
    learn_cc_lost_extra: dollars(l.lost_late - l.lost_on_time), learn_cc_carry_saved: dollars(l.carry_saved),
    learn_cc_lilf: money(sg.c_u_parts.low_inventory_fee), learn_cc_lilf_lo: money(sv.lilf_lo), learn_cc_lilf_hi: money(sv.lilf_hi), learn_cc_capital: pct(sv.capital_rate), learn_cc_obsolescence: pct(sv.obsolescence_rate),
    learn_cc_g_q: pct(sg.q, 1), learn_cc_g_cu: money(sg.c_u), learn_cc_g_co: money(sg.c_o), learn_cc_g_up_q: n0(sg.up_to_q), learn_cc_g_up_95: n0(sg.up_to_95),
    learn_cc_s_q: pct(ss.q, 1), learn_cc_s_up_q: n0(ss.up_to_q), learn_cc_s_up_95: n0(ss.up_to_95), learn_cc_s_extra: n0(ss.up_to_95 - ss.up_to_q),
    learn_cc_recovery: pct(h.recovery), learn_cc_h_pos: n0(h.position), learn_cc_h_age: String(h.age_days), learn_cc_h_rate: String(h.rate),
    learn_cc_h_horizon: String(h.hold_horizon), learn_cc_h_cover: n0(h.rate * h.hold_horizon), learn_cc_h_excess: n0(h.excess),
    learn_cc_h_hold: dollars(h.hold_npv), learn_cc_h_liq: dollars(h.liquidate), learn_cc_h_months: String(h.months), learn_cc_h_unit: money(h.per_unit_hold),
  };
  if (Math.floor((g.on_hand - r.reorder_point) / r.rate) + 1 !== c.wire_day) {
    // lesson 3 shows the days of sales above the reorder point and says the wire goes the day after
    throw new Error(`capital-and-cash: lesson 3's arithmetic (${((g.on_hand - r.reorder_point) / r.rate).toFixed(1)} days) does not give the engine's wire day ${c.wire_day}`);
  }
  if (r.reorder_point - Math.round(r.lead_demand_mean) !== r.safety_stock) {
    // the lesson shows the safety stock as the reorder point less the average lead-time demand, as the engine does
    throw new Error(`capital-and-cash: reorder point − average lead-time demand (${r.reorder_point - Math.round(r.lead_demand_mean)}) is not the engine's safety stock (${r.safety_stock})`);
  }
  if (!(l.lost_late - l.lost_on_time > l.carry_saved)) {
    // lesson 7 says late costs more than it saves; on this example it must
    throw new Error(`capital-and-cash: two weeks late now costs ${l.lost_late - l.lost_on_time} and saves ${l.carry_saved}; rewrite lesson 7`);
  }
  const row = (name, x) => `<tr><th scope="row">${name}</th><td class="num">${money(x.margin)}</td><td class="num">${money(x.c_u)}</td><td class="num">${money(x.c_o)}</td><td class="num">${pct(x.q, 1)}</td></tr>`;
  const service = `\n<div class="table-scroll" role="region" aria-label="The service level each SKU earns" tabindex="0"><table class="data"><thead><tr><th scope="col">SKU</th><th scope="col">Margin a unit</th><th scope="col">One short costs</th><th scope="col">One left over costs</th><th scope="col">Service level</th></tr></thead><tbody>${row("Garlic press", { ...sg, margin: g.margin })}${row("Spatula set", ss)}</tbody></table></div>\n`;
  const pathData = { ...c };
  return {
    fill,
    blocks: {
      "cc-path-wide": cashSVG(pathData, { id: "ccp-w", w: 680, h: 360, m: { t: 24, r: 24, b: 46, l: 64 }, font: 13 }),
      "cc-path-narrow": cashSVG(pathData, { id: "ccp-n", w: 360, h: 320, m: { t: 20, r: 12, b: 42, l: 50 }, font: 12, narrow: true }),
      "cc-cone-wide": cashSVG(pathData, { id: "ccc-w", w: 680, h: 360, m: { t: 24, r: 24, b: 46, l: 64 }, font: 13, band: true }),
      "cc-cone-narrow": cashSVG(pathData, { id: "ccc-n", w: 360, h: 320, m: { t: 20, r: 12, b: 42, l: 50 }, font: 12, band: true, narrow: true }),
      "cc-late": lateSVG(l, { id: "ccl", w: 680, h: 340, m: { t: 40, r: 24, b: 46, l: 52 }, font: 13 }),
      "cc-service": service,
    },
  };
}

const decode = (s) => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
const text = (html) => decode(html.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();

function faqJsonLd(html) {
  const faq = html.match(/<section[^>]*id="faq"[\s\S]*?<\/section>/);
  if (!faq) throw new Error("no FAQ section");
  const items = [...faq[0].matchAll(/<details[^>]*data-q="[^"]+"[^>]*>\s*<summary>([\s\S]*?)<\/summary>([\s\S]*?)<\/details>/g)]
    .map(([, q, a]) => ({ "@type": "Question", name: text(q), acceptedAnswer: { "@type": "Answer", text: text(a) } }));
  return `<script type="application/ld+json">\n${JSON.stringify({ "@context": "https://schema.org", "@type": "FAQPage", mainEntity: items }, null, 2)}\n</script>`;
}

/** The words a visitor sees on load: no head, scripts, styles, hidden sections, closed folds or chart titles. */
export function visibleWords(html) {
  let b = html.slice(html.indexOf("<body"));
  b = b.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ");
  b = b.replace(/<(section|div)\b[^>]*\bhidden\b[^>]*>[\s\S]*?<\/\1>/g, " ");
  b = b.replace(/(<details[^>]*>\s*<summary>[\s\S]*?<\/summary>)[\s\S]*?<\/details>/g, "$1");
  b = b.replace(/<(title|desc)\b[^>]*>[\s\S]*?<\/\1>/g, " ");
  b = b.replace(/<div class="chart-narrow">[\s\S]*?<\/div>/g, " ");   // one variant is ever shown
  return text(b).split(" ").filter((w) => /[\p{L}\p{N}$]/u.test(w)).length;
}

/** One page, rebuilt. `requireAllFills` is for the home page, which shows every figure. */
export function build(html, built, { requireAllFills = false, name = "page" } = {}) {
  let out = html.replace(/(<!-- build:([a-z0-9-]+) -->)[\s\S]*?(<!-- \/build:\2 -->)/g, (whole, a, block, z) => {
    if (block === "faq-jsonld") return whole;
    if (!(block in built.blocks)) throw new Error(`${name}: build:${block} has no block`);
    return `${a}${built.blocks[block]}${z}`;
  });
  const used = new Set();
  out = out.replace(/(<([a-z0-9]+)\b[^>]*\bdata-fill="([a-z0-9_]+)"[^>]*>)([^<]*)(<\/\2>)/g, (_, open, _tag, key, _old, close) => {
    if (!(key in built.fill)) throw new Error(`${name}: data-fill="${key}" has no figure`);
    used.add(key);
    return `${open}${built.fill[key]}${close}`;
  });
  if (requireAllFills) {
    const unused = Object.keys(built.fill).filter((k) => !used.has(k) && !OTHER_PAGES_ONLY.has(k) && !k.startsWith("learn_"));
    if (unused.length) throw new Error(`${name}: figures computed but never shown: ${unused.join(", ")}`);
  }
  out = out.replace(/(<!-- build:faq-jsonld -->)[\s\S]*?(<!-- \/build:faq-jsonld -->)/, (_, a, z) => `${a}\n${faqJsonLd(out)}\n${z}`);
  return out;
}

// Figures only /honesty prints.
const OTHER_PAGES_ONLY = new Set(["who_lower", "silence_share", "silence_on"]);

export const PAGES = [
  { file: "index.html", requireAllFills: true },
  { file: "honesty.html" },
  { file: "terms.html" },
  { file: "privacy.html" },
  { file: "your-data.html" },
  { file: "verify.html" },
  { file: "case-study.html" },
  { file: "manifesto.html" },
  { file: "portal.html" },
  { file: "learn/index.html" },
  { file: "learn/fee-staircase.html" },
  { file: "learn/price-curve.html" },
  { file: "learn/capital-and-cash.html" },
  { file: "learn/shopify-margin.html" },
  { file: "learn/operators-math.html" },
  { file: "learn/fee-staircase-card.html" },
  { file: "learn/price-curve-card.html" },
  { file: "learn/capital-and-cash-card.html" },
  { file: "learn/shopify-margin-card.html" },
  { file: "learn/operators-math-card.html" },
];

/** The home page's staircase and case study, whole, for /case-study. */
export function caseStudySections(home) {
  const take = (id) => {
    const m = home.match(new RegExp(`<section class="section" id="${id}">[\\s\\S]*?\\n</section>`));
    if (!m) throw new Error(`index.html has no #${id} section for /case-study`);
    return m[0];
  };
  return `\n${take("staircase")}\n\n${take("case-study")}\n`;
}

/** The sitemap: every public page the build knows, by its clean URL. The client's own pages and the noindex ones stay out. */
export function sitemap(pages = PAGES) {
  const url = (f) => `https://www.hubricon.com/${f.replace(/(^|\/)index\.html$/, "").replace(/\.html$/, "").replace(/\/$/, "")}`;
  const urls = pages.map((p) => p.file).filter((f) => f !== "portal.html" && !/<meta name="robots" content="noindex">/.test(read(f)))
    .map((f) => `  <url><loc>${url(f)}</loc></url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join("\n")}\n</urlset>\n`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
  const check = process.argv.includes("--check");
  writeFileSync(new URL("sitemap.xml", root), sitemap());
  let stale = 0;
  for (const page of PAGES) {
    const before = read(page.file);
    const after = build(before, built, { requireAllFills: page.requireAllFills, name: page.file });
    // /case-study carries the home page's own staircase and case-study sections, as just built
    if (page.file === "index.html") built.blocks["case-study-page"] = caseStudySections(after);
    const words = page.file === "index.html" ? ` · ${visibleWords(after)} visible words` : "";
    if (check) {
      if (before !== after) { stale++; console.error(`${page.file} is out of date: run node scripts/build-pages.mjs`); }
      else console.log(`${page.file} is current${words}`);
    } else {
      writeFileSync(new URL(page.file, root), after);
      console.log(`${page.file} ${before === after ? "unchanged" : "rebuilt"}${words}`);
    }
  }
  if (stale) process.exit(1);
}
