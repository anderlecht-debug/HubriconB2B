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
  const blocks = {
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
    const unused = Object.keys(built.fill).filter((k) => !used.has(k) && !OTHER_PAGES_ONLY.has(k));
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
