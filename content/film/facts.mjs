// Facts for the films that run on the public-data case study and Amazon's published
// cards, in the pipeline's facts.json shape ({key: {value, label, source}}), so the
// number guard holds them like every other script: no figure is spoken unless it is
// one of these.
//
//   node content/film/facts.mjs <slug>      writes content/videos/<slug>/facts.json
//
// Every value is the site's own: scripts/build-pages.mjs `figures()` (what the home
// page and /learn print) and lib/fees.js on ratecard.json. A film can never say a
// number the page does not.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import * as fees from "../../lib/fees.js";
import { figures } from "../../scripts/build-pages.mjs";

const root = new URL("../../", import.meta.url);
const json = (p) => JSON.parse(readFileSync(new URL(p, root), "utf8"));
const rc = json("ratecard.json");
const cs = json("data/case-study.json");
const mc = json("data/montecarlo.json");
const built = figures(rc, mc, cs);
const F = built.fill;

const CASE = "public-data case study (data/case-study.json), modeled from public data, not a client, not a result";
const CARD = `Amazon's published 2026 US FBA cards (ratecard.json, loaded ${rc.generated})`;
const cents = (v) => `$${v.toFixed(2)}`;
const usd = (v) => `$${Math.floor(v).toLocaleString("en-US")}`;
const fact = (value, label, source) => ({ value: String(value), label, source });

/** The case study as the home page tells it. */
function caseStudyFacts() {
  return {
    who: fact(F.who_lower, "the case-study brand, anonymised", CASE),
    category: fact(F.category, "its category", CASE),
    weight: fact(`${F.weight} ounces`, "the listing's published item weight", CASE),
    edge: fact(`${F.edge} ounces`, "the weight-band edge it sits past", CARD),
    step_np: fact(F.step_np, "the step, per unit, on the card in force until October 14", CARD),
    step_peak: fact(F.step_peak, "the step, per unit, on the holiday card", CARD),
    units: fact(F.units, "estimated units a month, from the public sales rank", CASE),
    leak_p10: fact(F.leak_p10, "the step a year, P10", CASE),
    leak_p90: fact(F.leak_p90, "the step a year, P90", CASE),
    years: fact(F.years, "simulated years", CASE),
    months_total: fact(F.months_total, "simulated months", CASE),
    months_losing: fact(F.months_losing, "simulated months at a loss before ads, storage and returns", CASE),
    aged_before: fact(F.aged_rate_before, "aged-inventory surcharge a cubic foot, days 241 to 270", "Amazon's storage schedule in force from January 15, 2026"),
    aged_after: fact(F.aged_rate_after, "aged-inventory surcharge a cubic foot, days 271 to 300", "Amazon's storage schedule in force from January 15, 2026"),
    cliff_day: fact("271", "the day the surcharge steps", "Amazon's storage schedule in force from January 15, 2026"),
    brands_modeled: fact(F.brands_modeled, "Amazon brands modeled from public pages", "data/case-study.json selection"),
    brands_silent: fact(F.brands_silent, "of them, brands that showed nothing worth fixing", "data/case-study.json selection"),
    surcharge: fact(F.surcharge, "the fuel and logistics surcharge on every fulfilment fee", CARD),
    peak_from: fact("October 15", "the holiday card's first day", CARD),
    peak_to: fact("January 14", "the holiday card's last day", CARD),
    np_through: fact("October 14", "the last day of the card in force before the holiday card", CARD),
    over: fact(`${(Math.floor(cs.step.over_by_oz * 10) / 10).toFixed(1)} of an ounce`, "how far past the edge the listing's published weight sits", CASE),
    price_edge: fact(`$${rc.fba.price_band_edges[0]}`, "the price edge between the card's first two columns", CARD),
  };
}

/** The holiday card, priced: what October 15 does to one unit and one listing. */
function octoberFacts() {
  const np = fees.cardNamed(rc, "non_peak"), pk = fees.cardNamed(rc, "peak");
  const day = cs.priced_on;
  const steps = [];
  for (const tier of ["small_standard", "large_standard"]) {
    for (const [edge] of np[tier]) {
      for (const p of [9.99, 25, 99]) steps.push(fees.fulfilmentFee(rc, tier, edge, p, day, pk) - fees.fulfilmentFee(rc, tier, edge, p, day, np));
    }
  }
  // The case-study unit, on both cards.
  const s = cs.step;
  const delta = s.peak.fee_now - s.non_peak.fee_now;
  const units = cs.listing.est_monthly_units;
  // Three months on the holiday card, at the rank curve's bracket (lib/fees.js unitEconomics).
  const lo = delta * units * fees.UNITS_LOW * 3, hi = delta * units * fees.UNITS_HIGH * 3;
  return {
    peak_min: fact(cents(Math.min(...steps)), "the smallest holiday increase on any standard-size row", CARD),
    peak_max: fact(cents(Math.max(...steps)), "the largest holiday increase on any standard-size row", CARD),
    stor_off: fact(F.learn_stor_off, "monthly storage a cubic foot, January to September", "Amazon's storage schedule in force from January 15, 2026"),
    stor_peak: fact(F.learn_stor_peak, "monthly storage a cubic foot, October to December", "Amazon's storage schedule in force from January 15, 2026"),
    cs_fee_np: fact(cents(s.non_peak.fee_now), "the case-study unit's fee until October 14", CARD),
    cs_fee_peak: fact(cents(s.peak.fee_now), "the case-study unit's fee from October 15", CARD),
    cs_delta: fact(cents(delta), "the case-study unit's holiday increase", CARD),
    cs_window_lo: fact(usd(Math.floor(lo / 100) * 100), "the holiday increase over the three months, low end", CASE),
    cs_window_hi: fact(usd(Math.floor(hi / 100) * 100), "the holiday increase over the three months, high end", CASE),
    ten_min: fact(F.learn_ten_min, "the $10 price step, smallest row", CARD),
    ten_max: fact(F.learn_ten_max, "the $10 price step, largest row", CARD),
  };
}

const SETS = {
  "case-study-film": () => ({ ...caseStudyFacts() }),
  "october-15": () => ({ ...caseStudyFacts(), ...octoberFacts() }),
};

if (import.meta.url === `file://${process.argv[1]}`) {
  const slug = process.argv[2];
  if (!SETS[slug]) { console.error(`no facts set for ${slug}: ${Object.keys(SETS).join(", ")}`); process.exit(2); }
  const out = SETS[slug]();
  const dir = new URL(`content/videos/${slug}/`, root);
  mkdirSync(dir, { recursive: true });
  writeFileSync(new URL("facts.json", dir), JSON.stringify(out, null, 2) + "\n");
  console.log(`content/videos/${slug}/facts.json: ${Object.keys(out).length} facts`);
  for (const [k, v] of Object.entries(out)) console.log(`  ${k.padEnd(16)} ${v.value}`);
}

export { SETS };
