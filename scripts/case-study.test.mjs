// The public-data case study: its files are current, its shape is the animation's
// contract, its numbers are the engine's, and it never names the brand.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import * as fees from "../lib/fees.js";
import { build, STORAGE, PATHS_KEPT, HORIZON } from "./case-study.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const rc = json("ratecard.json");
// The input names the brand, so it is git-ignored (the repo is public). Where it is
// absent the reproduction tests skip; the contract and anonymity tests always run.
const local = existsSync(new URL("scripts/case-study/listing.json", root));
const listing = local ? json("scripts/case-study/listing.json") : null;
const silence = json("scripts/case-study/silence.json");
const { montecarlo, caseStudy } = local ? build(rc, listing, silence) : { montecarlo: null, caseStudy: json("data/case-study.json") };
const needsInput = { skip: !local && "scripts/case-study/listing.json is local only (the repo is public)" };

test("the committed files are what the script writes today", needsInput, () => {
  assert.deepEqual(json("data/montecarlo.json"), montecarlo, "run node scripts/case-study.mjs");
  assert.deepEqual(json("data/case-study.json"), caseStudy, "run node scripts/case-study.mjs");
});

for (const file of ["data/montecarlo.json", "data/montecarlo.sample.json"]) {
  test(`${file} keeps the animation's contract and nothing else`, () => {
    const mc = json(file);
    assert.deepEqual(Object.keys(mc).sort(), ["months", "paths", "percentiles", "share_losing"]);
    assert.deepEqual(Object.keys(mc.percentiles).sort(), ["p10", "p50", "p90"]);
    assert.deepEqual(mc.months, Array.from({ length: HORIZON + 1 }, (_, i) => i));
    assert.equal(mc.paths.length, PATHS_KEPT);
    for (const p of [...mc.paths, ...Object.values(mc.percentiles)]) {
      assert.equal(p.length, mc.months.length);
      assert.equal(p[0], 0, "every year starts today, at zero");
    }
    mc.months.forEach((_, t) => assert.ok(mc.percentiles.p10[t] <= mc.percentiles.p50[t] && mc.percentiles.p50[t] <= mc.percentiles.p90[t]));
    assert.ok(mc.share_losing >= 0 && mc.share_losing <= 1);
  });
}

test("the sample exercises a losing month, so the chart is tested below zero", () => {
  const s = json("data/montecarlo.sample.json");
  assert.ok(s.share_losing > 0);
  assert.ok(s.percentiles.p10.at(-1) < 0);
});

test("the step is the engine's own finding, on both published cards", needsInput, () => {
  const item = fees.describeItem(rc, { price: listing.price, category: listing.category, bsr: listing.bsr, itemWeightOz: listing.item_weight_oz, dims: listing.dims });
  const f = fees.feeBandEdge(rc, fees.cardNamed(rc, "non_peak"), item, caseStudy.priced_on);
  assert.ok(f, "the detector fires on this listing");
  assert.equal(caseStudy.step.edge_oz, f.evidence.edge);
  assert.ok(Math.abs(caseStudy.step.non_peak.step - f.perUnitHigh) < 1e-4);
  const peak = fees.feeBandEdge(rc, fees.cardNamed(rc, "peak"), item, "2026-10-15");
  assert.ok(Math.abs(caseStudy.step.peak.step - peak.perUnitHigh) < 1e-4);
});

test("a range is a range, rounded down, in order", () => {
  const { p10, p50, p90 } = caseStudy.leak_per_year;
  assert.ok(p10 < p50 && p50 < p90);
  for (const v of [p10, p50, p90]) assert.equal(v % 100, 0);
});

test("storage and aged-inventory rates are the engine's fee schedule", () => {
  const py = read("engine/src/hubricon_engine/models/fee_schedule.py");
  assert.match(py, new RegExp(`EFFECTIVE = "${STORAGE.effective}"`));
  assert.match(py, new RegExp(`"standard": \\{"offpeak": ${STORAGE.per_cuft_month.offpeak}, "peak": ${STORAGE.per_cuft_month.peak.toFixed(2)}\\}`));
  const table = py.slice(py.indexOf("AGED_SURCHARGE_PER_CUFT"), py.indexOf("AGED_SURCHARGE_MIN_PER_UNIT"));
  const rows = [...table.matchAll(/\((\d+), (10\*\*6|\d+), ([\d.]+)\)/g)].map(([, a, b, r]) => [+a, b === "10**6" ? null : +b, +r]);
  assert.deepEqual(rows, STORAGE.aged_per_cuft_month);
  assert.match(py, new RegExp(`AGED_SURCHARGE_MIN_PER_UNIT_365_PLUS = ${STORAGE.aged_min_per_unit_366}`));
});

test("nothing published names the brand, the listing or the seller", needsInput, () => {
  const published = read("data/case-study.json") + read("data/montecarlo.json") + read("index.html");
  for (const secret of [listing.brand, listing.asin, listing.seller.split(" ")[0], String(listing.price)]) {
    assert.ok(!published.toLowerCase().includes(secret.toLowerCase()), `"${secret}" appears on a published surface`);
  }
});
