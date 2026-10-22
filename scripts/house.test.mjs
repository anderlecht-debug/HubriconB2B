// The house charts: every other chart on the site, drawn by the line and the bars.
//   node --test scripts/house.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as H from "../assets/house.mjs";
import { lineChart, textWidth } from "../assets/line.mjs";
import { barChart, barCard } from "../assets/bars.mjs";

const j = (p) => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url)));
const cs = j("data/case-study.json"), ss = j("data/store-study.json"), cc = j("data/learn-capital-cash.json");
// the charts are built from the same data the site builds them from today; the store study and the cash path come straight from their files
const all = (o) => ({
  cash: H.cashSpec(cc.cash, o), cone: H.cashSpec(cc.cash, { ...o, band: true }),
  calls: H.callsSpec(ss.customers, o), slip: H.slippingSpec(ss.slipping, o), demand: H.demandSpec(ss.demand, o),
  wf: H.waterfallSpec({ price: 24, ads: 4.026, costs: [["Landed cost", 7.2], ["Payment fee", 0.996], ["Label", 7.5812], ["Packing", 0.9], ["Refunds", 0.48]] }, o),
  order: H.orderSpec({ price: 42, fee: 1.518, packing: 1.4, landed: 11.8, labels: [7.99, 12.87], zones: [1, 8] }, o),
});
const draw = (s, at = Infinity) => (s.kind === "bars" ? barChart(s, at) : lineChart(s, at));
const texts = (svg) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]);

test("no calendar on any chart: no month, date, week number or 'Today' in their words", () => {
  for (const [k, s] of Object.entries(all({ paint: "inline" }))) {
    for (const t of texts(draw(s).svg)) assert.doesNotMatch(t, /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|20\d\d|[Ww]eek \d+|[Dd]ay \d+|Today)\b/, `${k}: "${t}"`);
  }
});

test("each chart's finished frame is its still, and its sound is in order", () => {
  for (const [k, s] of Object.entries(all({ paint: "inline" }))) {
    const r = draw(s);
    assert.equal(draw(s, r.duration + 1).svg, r.svg, `${k}: the end of the draw-in is not the still`);
    assert.ok(r.cues.every((c, i) => i === 0 || c.at >= r.cues[i - 1].at), `${k}: cues out of order`);
  }
});

test("no two words overlap on any chart", () => {
  for (const [k, s] of Object.entries(all({ paint: "inline" }))) {
    const boxes = [...draw(s).svg.matchAll(/<text x="([\d.]+)" y="([\d.]+)" text-anchor="(\w+)"[^>]*font-size:([\d.]+)px;font-weight:(\d+)[^>]*>([^<]+)<\/text>/g)].map((m) => {
      const [x, y, anchor, size, weight, t] = [+m[1], +m[2], m[3], +m[4], +m[5], m[6].replace(/&amp;/g, "&")];
      const w = textWidth(t, size, weight);
      return { t, x: anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x, y: y - size * 0.8, w, h: size };
    });
    for (let i = 0; i < boxes.length; i++) for (let q = i + 1; q < boxes.length; q++) {
      const a = boxes[i], b = boxes[q];
      const ov = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      assert.ok(ov < 6, `${k}: "${a.t}" overlaps "${b.t}"`);
    }
  }
});

test("the waterfall adds up: each total is the one before it less what was taken", () => {
  const s = all({}).wf, rows = s.rows;
  let run = 0;
  for (const r of rows) { if (r.total) assert.ok(Math.abs(r.value - run) < 1e-9 || run === 0, `${r.name} does not follow from the rows above`); run = r.total ? r.value : run + r.value; }
  assert.ok(texts(barChart(s, Infinity).svg).includes("$6.84") && texts(barChart(s, Infinity).svg).includes("$2.82"));
});

test("blue only for the money kept, and only after the silence", () => {
  for (const k of ["order", "wf", "slip"]) {
    const s = all({ paint: "inline" })[k], r = barChart(s);
    const early = barChart(s, r.duration - 500).svg;
    assert.doesNotMatch(early, /#0b5fff/, `${k}: blue before the finding`);
    assert.match(r.svg, /#0b5fff/, `${k}: the finding is not blue`);
  }
  const shares = all({}).slip.rows.map((r) => r.parts.reduce((a, p) => a + p.value, 0));
  assert.ok(shares.every((v) => Math.abs(v - 100) < 1e-9), "a share bar is not whole");
});

test("a bar chart travels as a card, with its label and the mark", () => {
  const c = barCard({ ...all({}).wf, title: "A title", source: "Modeled on published data · Not a client · Not a result" });
  assert.ok(c.includes(">A title<") && c.includes("Not a client · Not a result") && c.includes(">Hubricon</text>"));
});
