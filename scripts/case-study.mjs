// The public-data case study: one real listing, priced off Amazon's published
// cards, simulated ten thousand times. Writes the two files the home page reads:
//
//   data/montecarlo.json   the animation's contract: months, paths, percentiles,
//                          share_losing. Nothing else.
//   data/case-study.json   every other figure the page prints, each with its basis.
//
//   node scripts/case-study.mjs            (then: node scripts/build-home.mjs)
//
// Nothing here is a second simulator. Fees, size tier, the rank→units curve and
// the volume and cost uncertainty are lib/fees.js — the archived Teardown's own
// arithmetic, pinned to the Python engine by lib/fees.test.mjs — run month by
// month across the calendar so the 15 October card lands where it falls. Storage
// and the aged-inventory surcharge are engine/src/hubricon_engine/models/
// fee_schedule.py, copied below and pinned by scripts/case-study.test.mjs.
//
// The input (scripts/case-study/listing.json) names the brand and is never
// deployed. The outputs carry the category and band only.
import { readFileSync, writeFileSync } from "node:fs";
import * as fees from "../lib/fees.js";

const root = new URL("../", import.meta.url);
const read = (p) => JSON.parse(readFileSync(new URL(p, root)));

export const N_YEARS = 10000;
export const SEED = 20260930;
export const PATHS_KEPT = 50;
export const START = "2026-10-01";            // month 0 is today; month 1 is October
export const HORIZON = 12;
// Public pages publish no cost. Assumed, stated on the page, drifting ±10% a month
// for freight and FX exactly as fees.simulateMonthly drifts it.
export const LANDED_COST_SHARE = 0.25;
// fees.simulateMonthly's volume doubt: the rank curve is wrong by a factor of two
// either way, so 5% and 95% land at half and double the estimate.
export const SIGMA = Math.log(2) / 1.645;
const Z10 = -1.2816, Z90 = 1.2816;

// engine/src/hubricon_engine/models/fee_schedule.py, EFFECTIVE 2026-01-15.
export const STORAGE = {
  effective: "2026-01-15",
  per_cuft_month: { offpeak: 0.78, peak: 2.4 },              // standard size
  aged_per_cuft_month: [[181, 210, 0.5], [211, 240, 1.0], [241, 270, 1.5], [271, 300, 5.45], [301, 330, 5.7], [331, 365, 5.9], [366, null, 6.9]],
  aged_min_per_unit_366: 0.15,
};

// Invented, for data/montecarlo.sample.json only.
const SAMPLE_LISTING = {
  captured_on: "2026-09-30", category: "Home & Kitchen", bsr: 2400, price: 14.99, item_weight_oz: 12.6,
  dims: "9 x 6 x 3 inches", public: { brand_descriptor: "Sample", product: "an invented listing", category: "Home & Kitchen" },
};

const iso = (d) => d.toISOString().slice(0, 10);
const addMonths = (day, n) => { const d = new Date(day + "T00:00:00Z"); d.setUTCMonth(d.getUTCMonth() + n); return iso(d); };
const daysBetween = (a, b) => Math.round((new Date(b + "T00:00:00Z") - new Date(a + "T00:00:00Z")) / 864e5);
const quantile = (sorted, p) => sorted[Math.min(sorted.length - 1, Math.max(0, Math.floor(p * sorted.length)))];
const floorTo = (v, step) => Math.floor(v / step) * step;

/** The share of a calendar month that falls on the holiday peak card. */
function peakShare(rc, monthStart) {
  const next = addMonths(monthStart, 1);
  const peak = rc.fba.cards.peak;
  const lo = monthStart > peak.effective ? monthStart : peak.effective;
  const hiExclusive = next < addDay(peak.through) ? next : addDay(peak.through);
  const inPeak = Math.max(0, daysBetween(lo, hiExclusive));
  return inPeak / daysBetween(monthStart, next);
}
function addDay(day) { const d = new Date(day + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + 1); return iso(d); }

export function build(rc, listing, silence, { landedCostShare = LANDED_COST_SHARE } = {}) {
  const item = fees.describeItem(rc, { price: listing.price, category: listing.category, bsr: listing.bsr, itemWeightOz: listing.item_weight_oz, dims: listing.dims });
  const nonPeak = fees.cardNamed(rc, "non_peak");
  const peak = fees.cardNamed(rc, "peak");
  const priced = "2026-09-30";

  // The finding, exactly as the engine's detector states it. No finding, no case study.
  const finding = fees.feeBandEdge(rc, nonPeak, item, priced);
  if (!finding) throw new Error("the engine finds no weight-band edge on this listing; pick another");
  const edge = finding.evidence.edge;
  const fee = (card, oz, day) => fees.fulfilmentFee(rc, item.tier, oz, item.price, day, card);
  const onCard = (card, day) => {
    const now = fee(card, item.billableWeightOz, day), atEdge = fee(card, edge, day);
    return { fee_now: now, fee_at_edge: atEdge, step: Math.round((now - atEdge) * 1e4) / 1e4 };
  };
  const steps = { non_peak: onCard(nonPeak, priced), peak: onCard(peak, peak.effective) };

  const referral = Math.round(fees.referralFee(rc, item.price, item.category) * 100) / 100;
  const cogs = Math.round(item.price * landedCostShare * 100) / 100;

  // Twelve calendar months, each priced on the card(s) in force that month.
  const months = Array.from({ length: HORIZON }, (_, i) => {
    const start = addMonths(START, i);
    const share = peakShare(rc, start);
    return {
      start,
      peak_share: Math.round(share * 1e4) / 1e4,
      fee: steps.non_peak.fee_now * (1 - share) + steps.peak.fee_now * share,
      step: steps.non_peak.step * (1 - share) + steps.peak.step * share,
    };
  });

  // Ten thousand years. One volume level per year (the rank curve's doubt is a
  // level, not a wobble); the landed cost drifts each month.
  const rand = fees.mulberry32(SEED);
  const mu = Math.log(item.estMonthlyUnits);
  const cumulative = [];
  const leaks = new Float64Array(N_YEARS);
  let monthsLosing = 0;
  for (let k = 0; k < N_YEARS; k++) {
    const units = Math.exp(mu + SIGMA * fees.gaussian(rand));
    const path = new Float64Array(HORIZON + 1);
    let leak = 0;
    for (let t = 0; t < HORIZON; t++) {
      const c = cogs * (0.9 + 0.2 * rand());
      const profit = units * (item.price - referral - months[t].fee - c);
      if (profit < 0) monthsLosing++;
      path[t + 1] = path[t] + profit;
      leak += units * months[t].step;
    }
    cumulative.push(path);
    leaks[k] = leak;
  }

  const pct = (p) => Array.from({ length: HORIZON + 1 }, (_, t) => {
    const col = cumulative.map((path) => path[t]).sort((a, b) => a - b);
    return Math.round(quantile(col, p));
  });
  // The paths drawn are the ones at evenly spaced ranks of the year's total, so
  // the picture is the distribution, not a chosen few.
  const byFinal = cumulative.map((path, k) => [path[HORIZON], k]).sort((a, b) => a[0] - b[0]);
  const paths = Array.from({ length: PATHS_KEPT }, (_, i) => {
    const k = byFinal[Math.floor(((i + 0.5) / PATHS_KEPT) * N_YEARS)][1];
    return Array.from(cumulative[k], (v) => Math.round(v));
  });
  const montecarlo = {
    months: Array.from({ length: HORIZON + 1 }, (_, t) => t),
    paths,
    percentiles: { p10: pct(0.1), p50: pct(0.5), p90: pct(0.9) },
    share_losing: Math.round((monthsLosing / (N_YEARS * HORIZON)) * 1e4) / 1e4,
  };

  const leakSorted = Array.from(leaks).sort((a, b) => a - b);
  const units = item.estMonthlyUnits;
  const volume = item.dims[0] * item.dims[1] * item.dims[2] / 1728;
  const per1000 = (rate) => Math.round(rate * volume * 1000 * 100) / 100;
  const aged = STORAGE.aged_per_cuft_month.map(([from, to, rate]) => ({
    from, to, surcharge_per_cuft: rate,
    per_1000_units_month: Math.round((per1000(STORAGE.per_cuft_month.offpeak) + Math.max(per1000(rate), to == null ? STORAGE.aged_min_per_unit_366 * 1000 : 0)) * 100) / 100,
  }));

  const caseStudy = {
    label: "Modeled from public data. Not a client. Not a result.",
    captured_on: listing.captured_on,
    priced_on: priced,
    who: listing.public.brand_descriptor,
    what: listing.public.product,
    category: listing.public.category,
    listing: {
      price_band: fees.priceBand(rc, item.price) === 1 ? "$10 to $50" : null,
      item_weight_oz: item.itemWeightOz,
      tier: item.tier,
      rank_band: item.rank <= 100 ? `top 100 in ${listing.category}` : `#${item.rank.toLocaleString("en-US")} in ${listing.category}`,
      est_monthly_units: Math.round(units),
      // This one listing's sales, at the volume curve's own P10 and P90.
      est_annual_sales: [Z10, Z90].map((z) => floorTo(units * Math.exp(SIGMA * z) * item.price * 12, 100000)),
    },
    step: {
      edge_oz: edge,
      over_by_oz: finding.evidence.overByOz,
      non_peak: steps.non_peak,
      peak: steps.peak,
    },
    leak_per_year: {
      p10: floorTo(quantile(leakSorted, 0.1), 100),
      p50: floorTo(quantile(leakSorted, 0.5), 100),
      p90: floorTo(quantile(leakSorted, 0.9), 100),
    },
    profit_basis: {
      referral, landed_cost: cogs, landed_cost_share: landedCostShare,
      excludes: ["advertising", "storage", "returns"],
    },
    aging: {
      cubic_feet_per_unit: Math.round(volume * 1e4) / 1e4,
      storage_effective: STORAGE.effective,
      under_181_per_1000_units_month: per1000(STORAGE.per_cuft_month.offpeak),
      bands: aged,
    },
    simulation: {
      years: N_YEARS, months: N_YEARS * HORIZON, seed: SEED, start: START,
      volume_sigma: Math.round(SIGMA * 1e4) / 1e4,
      landed_cost_drift: "±10% a month",
      calendar: months.map(({ start, peak_share }) => ({ start, peak_share })),
    },
    cards: {
      non_peak: { source: rc.fba.cards.non_peak.source, effective: rc.fba.cards.non_peak.effective, through: rc.fba.cards.non_peak.through },
      peak: { source: rc.fba.cards.peak.source, effective: rc.fba.cards.peak.effective, through: rc.fba.cards.peak.through },
      fuel_surcharge: rc.fba.fuel_surcharge,
      fuel_surcharge_from: rc.fba.fuel_surcharge_from,
      referral_rate: fees.referralRate(rc, item.category),
    },
    selection: {
      brands_modeled: silence.brands_modeled,
      brands_silent: silence.brands_silent,
      measured_on: silence.measured_on,
      captured_between: silence.captured_between,
    },
  };
  return { montecarlo, caseStudy };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { montecarlo, caseStudy } = build(read("ratecard.json"), read("scripts/case-study/listing.json"), read("scripts/case-study/silence.json"));
  writeFileSync(new URL("data/montecarlo.json", root), JSON.stringify(montecarlo) + "\n");
  writeFileSync(new URL("data/case-study.json", root), JSON.stringify(caseStudy, null, 2) + "\n");
  const { leak_per_year: l, step } = caseStudy;
  console.log(`step ${step.edge_oz} oz: $${step.non_peak.step}/unit (peak $${step.peak.step}); leak/yr P10 $${l.p10} · P50 $${l.p50} · P90 $${l.p90}; months losing ${montecarlo.share_losing}`);
  // The sample: the same contract on an invented listing whose thin margin loses
  // some months, so the renderer is exercised below zero. Labelled by its name only.
  const sample = build(read("ratecard.json"), SAMPLE_LISTING, read("scripts/case-study/silence.json"), { landedCostShare: 0.52 });
  writeFileSync(new URL("data/montecarlo.sample.json", root), JSON.stringify(sample.montecarlo) + "\n");
  console.log(`sample: months losing ${sample.montecarlo.share_losing}`);
  console.log(`year-end cumulative P10 $${montecarlo.percentiles.p10.at(-1)} · P50 $${montecarlo.percentiles.p50.at(-1)} · P90 $${montecarlo.percentiles.p90.at(-1)}`);
}
