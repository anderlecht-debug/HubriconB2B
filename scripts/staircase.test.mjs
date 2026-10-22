// The staircase: the card in force as exact steps, and where any weight stands on it.
//   node --test scripts/staircase.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stairsSpec, weighIn, weighInWords, weighInHTML, stairsCard } from "../assets/staircase.mjs";
import { lineChart, valueAt } from "../assets/line.mjs";
import * as fees from "../lib/fees.js";

const j = (p) => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url)));
const rc = j("ratecard.json"), cs = j("data/case-study.json");
// the card in force on a day in the holiday season, priced the way the site prices it
const card = fees.cardFor(rc, "2026-10-22");
const treads = card.large_standard.map(([edge]) => [edge, fees.fulfilmentFee(rc, "large_standard", edge, 25, cs.priced_on, card)]);
const st = { treads, unit: "oz", xMax: 20, listing: { oz: cs.listing.item_weight_oz, fee: cs.step.peak.fee_now }, edge: { oz: cs.step.edge_oz, fee: cs.step.peak.fee_at_edge },
  step: cs.step.peak.step, range: cs.leak_per_year, title: "A title", source: "Modeled from public data · Not a client · Not a result" };

test("the card in force is the one drawn, and the case's two dots sit on it", () => {
  assert.equal(card.name, "peak", "on 2026-10-22 the holiday card is in force");
  const spec = stairsSpec(st), s = spec.series[0];
  assert.equal(spec.series.length, 1, "last season's card is drawn beside it");
  assert.ok(Math.abs(valueAt(s, st.listing.oz) - st.listing.fee) < 1e-3, "the listing is not on the card");
  assert.ok(Math.abs(valueAt(s, st.edge.oz) - st.edge.fee) < 1e-3, "an edge belongs to the band below it");
  assert.doesNotMatch(lineChart(spec, Infinity).svg, /\b(Jan|Oct|2026|2027|peak|non-peak)\b/, "a date or a season names the card");
});

test("a weight on the card: its fee, the edge below and what being past it costs, the edge above and what crossing it costs", () => {
  const w = weighIn(treads, 8.8);
  assert.ok(Math.abs(w.fee - st.listing.fee) < 1e-3);
  assert.equal(w.below.edge, 8);
  assert.ok(Math.abs(w.below.overBy - 0.8) < 1e-9 && Math.abs(w.below.saves - st.step) < 1e-3);
  assert.equal(w.above.edge, 12);
  assert.equal(weighIn(treads, 8).below.edge, 4, "8.0 oz is still the band below the 8 oz edge");
});

test("the scary moment first: past an edge it says what lighter saves; under one, what creeping over costs", () => {
  assert.match(weighInWords(st, 8.818), /You are 0\.82 oz past the 8 oz edge: 0\.82 oz lighter would save \$0\.28 a unit\./);
  assert.match(weighInWords(st, 11.8), /You are 0\.2 oz under the 12 oz edge: creep over it and each unit costs \$0\.\d\d more\./);
  assert.match(weighInWords(st, 10), /The nearest edge is 2 oz away\./);
  for (const oz of [0.5, 3.9, 8, 8.1, 12, 15.95, 19.9]) assert.match(weighInWords(st, oz), /^At [\d.]+ oz the fee is \$\d\.\d\d a unit\./);
});

test("the control is finished with no script: it already says where the listing stands", () => {
  const html = weighInHTML(st);
  assert.match(html, /<label class="weigh-field"><span>Your shipping weight<\/span>/);
  assert.ok(html.includes('value="8.8"'));
  assert.ok(html.includes("past the 8 oz edge"));
  assert.match(html, /<output class="weigh-says"[^>]*aria-live="polite">/);
});

test("the finding: the riser in blue, the step and its year in words, the card's card for a deck", () => {
  const svg = lineChart(stairsSpec(st, { paint: "inline" }), Infinity).svg;
  assert.ok(svg.includes(">+$0.28 a unit<") && svg.includes(">$6,400–$19,200 a year, estimate<"));
  assert.ok(svg.includes(">This listing, 8.8 oz<") && svg.includes(">8 oz, one step down<"));
  const c = stairsCard(st);
  assert.ok(c.includes(">A title<") && c.includes("Not a client · Not a result") && c.includes(">Hubricon</text>"));
});
