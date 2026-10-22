// The aging cliff: the aged-stock charge by days in storage, and what the coming days bring.
//   node --test scripts/aging.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { agingSchedule, ageWords, agingSpec } from "../assets/aging.mjs";
import { lineChart, valueAt } from "../assets/line.mjs";

const cs = JSON.parse(readFileSync(new URL("../data/case-study.json", import.meta.url)));
const st = agingSchedule(cs.aging);

test("the schedule is the surcharge alone, band by band, with day 270 still below the cliff", () => {
  const s = agingSpec(st).series[0], k = cs.aging.cubic_feet_per_unit * 1000;
  for (const b of cs.aging.bands) assert.ok(Math.abs(valueAt(s, b.from) - b.surcharge_per_cuft * k) < 1e-6, `day ${b.from}`);
  assert.equal(valueAt(s, 180), 0);
  assert.ok(Math.abs(valueAt(s, 270) - 1.5 * k) < 1e-6, "day 270 is still the band below the cliff");
});

test("the cliff is found in the schedule, not typed: the largest multiple, at day 271", () => {
  assert.equal(st.cliff.day, 271);
  assert.ok(Math.abs(st.cliff.times - 5.45 / 1.5) < 1e-9);
  assert.equal(st.title, "Day 271: the aged-stock charge jumps 3.6×");
  const svg = lineChart(agingSpec(st, { paint: "inline" }), Infinity).svg;
  assert.ok(svg.includes(">3.6× at day 271<") && svg.includes(">$48 to $174 per 1,000 units a month<"));
  assert.doesNotMatch(svg, />[^<]*\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|month 1|week)\b[^<]*</, "a calendar on the axis");
});

test("age only grows, so the sentence looks ahead, and names the cliff before it comes", () => {
  assert.equal(ageWords(st, 90), "At 90 days it pays no aged-stock charge yet. The next band starts in 91 days. In 181 days it crosses day 271, and the charge becomes $174.");
  assert.equal(ageWords(st, 200), "At 200 days it pays $16 per 1,000 units a month. The next band starts in 11 days. In 71 days it crosses day 271, and the charge becomes $174: 10.9× what it pays now.");
  assert.equal(ageWords(st, 270), "At 270 days it pays $48 per 1,000 units a month. In 1 day it crosses day 271, and the charge becomes $174: 3.6× what it pays now.");
  assert.equal(ageWords(st, 290), "At 290 days it pays $174 per 1,000 units a month. It has crossed day 271. The next band starts in 11 days, at $182.");
  assert.match(ageWords(st, 380), /It is in the last band\.$/);
});

test("the money scale never reads minus zero", () => {
  assert.doesNotMatch(lineChart(agingSpec(st, { paint: "inline" }), Infinity).svg, />\$-0</);
});
