// Bakes figures, numbers and shared text into the pages that carry them.
//
//   node scripts/build-pages.mjs           rewrite every page in PAGES
//   node scripts/build-pages.mjs --check   exit 1 if any page is out of date
//
// Reads ratecard.json (Amazon's published cards), data/montecarlo.json and
// data/case-study.json (written by scripts/case-study.mjs) and scripts/blocks/,
// then, on each page:
//   - replaces whatever sits between <!-- build:NAME --> and <!-- /build:NAME -->
//     with the block of that name: a chart's finished still frame, or shared text
//     such as the attribution rules, which the terms and /honesty must carry word
//     for word;
//   - fills every element marked data-fill="key" with the figure it names, so no
//     number on a page is typed by hand;
//   - writes the FAQPage structured data from the FAQ as the page shows it;
//   - on the home page, counts the words a visitor sees on load (the Hormozi
//     standard: under ~900).
// scripts/build-pages.test.mjs runs the --check path, so a stale page fails CI.
import { readFileSync, writeFileSync } from "node:fs";
import * as fees from "../lib/fees.js";
import { monteCarloSVG, staircaseSVG, agingSVG, usd } from "../assets/charts.mjs";
import { STORAGE } from "./case-study.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const longDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };
const shortDate = (iso) => { const [, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1].slice(0, 3)} ${d}`; };
const n = (v) => Math.round(v).toLocaleString("en-US");
const dollars2 = (v) => `$${v.toFixed(2)}`;
const millions = (v) => `$${(v / 1e6).toFixed(1).replace(/\.0$/, "")}M`;

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
  const learn = learnFigures(rc, cs);
  const blocks = {
    ...learn.blocks,
    attribution: "\n" + read("scripts/blocks/attribution.html").trim() + "\n",
    "mc-mood-wide": monteCarloSVG(mc, { id: "mc-mood-w", w: 560, h: 440, m: { t: 8, r: 8, b: 8, l: 8 }, variant: "mood" }),
    "mc-mood-narrow": monteCarloSVG(mc, { id: "mc-mood-n", w: 360, h: 200, m: { t: 6, r: 6, b: 6, l: 6 }, paths: 20, variant: "mood" }),
    "mc-wide": monteCarloSVG(mc, { id: "mc-w", w: 760, h: 420, m: { t: 24, r: 120, b: 44, l: 64 }, font: 13 }),
    "mc-narrow": monteCarloSVG(mc, { id: "mc-n", w: 360, h: 320, m: { t: 16, r: 74, b: 36, l: 46 }, paths: 20, font: 11 }),
    "stairs-wide": staircaseSVG(stairs, { id: "st-w", w: 760, h: 420, m: { t: 64, r: 24, b: 48, l: 64 }, font: 13, xMax: 20 }),
    "stairs-narrow": staircaseSVG(stairs, { id: "st-n", w: 360, h: 340, m: { t: 56, r: 8, b: 40, l: 46 }, font: 11, xMax: 16 }),
    "aging-wide": agingSVG(aging, { id: "ag-w", w: 760, h: 300, m: { t: 32, r: 24, b: 48, l: 64 }, font: 13 }),
    "aging-narrow": agingSVG(aging, { id: "ag-n", w: 360, h: 260, m: { t: 28, r: 8, b: 40, l: 46 }, font: 11 }),
  };
  return {
    blocks,
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
      units: n(Math.round(cs.listing.est_monthly_units / 100) * 100),
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
      ...learn.fill,
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
  const px = fees.describeItem(rc, { price: 10.49, category: "kitchen & dining", itemWeightOz: 13, dims: "9 x 6 x 2" });
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

  return {
    blocks: {
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
  { file: "portal.html" },
  { file: "learn/fee-staircase.html" },
];

if (import.meta.url === `file://${process.argv[1]}`) {
  const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
  const check = process.argv.includes("--check");
  let stale = 0;
  for (const page of PAGES) {
    const before = read(page.file);
    const after = build(before, built, { requireAllFills: page.requireAllFills, name: page.file });
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
