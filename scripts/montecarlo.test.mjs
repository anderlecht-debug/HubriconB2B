// Ten thousand years: graded light from the real years, plain answers, honest order.
//   node --test scripts/montecarlo.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { bands, lossLine, floorSig, mixer, mcLayout, mcMoment, mcChart, mcTimeline, playMC, FAN } from "../assets/montecarlo.mjs";
import { css, VIDEO } from "../assets/tokens.mjs";
import { textWidth } from "../assets/inter.mjs";

const read = (p) => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url)));
const mc = read("data/montecarlo.json"), sample = read("data/montecarlo.sample.json");
const base = { mc, w: 760, h: 440, font: 13, paint: "inline", source: "Modeled from public data · Not a client · Not a result" };

test("the fan is the kept years' own quantiles: nested bands that hold every year", () => {
  for (const data of [mc, sample]) {
    const B = bands(data, FAN.sub);
    assert.ok(B.length >= 4 * Math.floor(data.paths.length / 2) - 4, "too few bands for smooth light");
    const T = data.months.length;
    for (let t = 0; t < T; t++) {
      const col = data.paths.map((p) => p[t]);
      assert.ok(Math.abs(B[0].lo[t] - Math.min(...col)) < 1e-6 && Math.abs(B[0].hi[t] - Math.max(...col)) < 1e-6, "the outermost band is not the lowest and highest year");
      for (let k = 1; k < B.length; k++) {
        assert.ok(B[k].lo[t] >= B[k - 1].lo[t] - 1e-6 && B[k].hi[t] <= B[k - 1].hi[t] + 1e-6, `band ${k} is not inside band ${k - 1} at month ${t}`);
        assert.ok(B[k].lo[t] <= B[k].hi[t] + 1e-6);
      }
    }
    for (let k = 1; k < B.length; k++) assert.ok(B[k].share < B[k - 1].share);
  }
});

test("the light is painted in exact colours, never stacked transparency, so the blue never drifts", () => {
  const svg = mcChart(base, Infinity).svg;
  const fan = svg.slice(svg.indexOf('class="mc-fan"'), svg.indexOf("</g>", svg.indexOf('class="mc-fan"')));
  assert.doesNotMatch(fan, /fill-opacity|opacity:/, "the fan must not rely on transparency");
  const mix = mixer("inline");
  assert.equal(mix(0), css("paper"));
  assert.equal(mix(1), css("blue"));
  const core = mix(FAN.full.core);
  assert.ok(fan.includes(`fill:${core}`), "the innermost band is not the core colour");
  // the hue holds: red falls faster than green, exactly as the blue over white does
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(core.slice(i, i + 2), 16));
  assert.ok(255 - r > 255 - g && b === 255, `the core ${core} is not the brand's blue at strength`);
  assert.match(mcChart({ ...base, paint: "css" }, Infinity).svg, /color-mix\(in srgb, var\(--blue\) [\d.]+%, var\(--paper\)\)/);
});

test("three answers in plain words, rounded down, never above what the ten thousand years found", () => {
  const L = mcLayout(base), end = mc.months.length - 1;
  assert.deepEqual(L.answers.map((a) => a.cap), ["1 in 10 years ends above", "A typical year", "1 in 10 years ends below"]);
  for (const a of L.answers) {
    const truth = mc.percentiles[a.q][end];
    assert.ok(a.v <= truth && a.v > truth * 0.99, `${a.q}: ${a.v} against ${truth}`);
  }
  assert.equal(floorSig(402259), 402000);
  assert.equal(floorSig(3742), 3740);
  assert.equal(floorSig(-1012), -1020, "a loss rounds down too: more negative, never less");
  const svg = mcChart(base, Infinity).svg;
  for (const s of ["$687,000", "$402,000", "$230,000"]) assert.ok(svg.replace(/<\/text><text[^>]*>/g, "").includes(s.replace(/[$,]/g, (c) => c)) || svg.includes(`aria-label="${s}"`), `${s} missing`);
  assert.doesNotMatch(svg, /P10|P90|Median|percentile/i, "jargon on the chart");
});

test("no time scale anywhere: money up the side, nothing along the bottom", () => {
  for (const variant of ["full", "narrow", "mood"]) {
    // the axis and the lines' names only; the sentence under the chart counts months as a frequency, not a scale
    const svg = mcChart({ ...base, variant, mc: sample }, Infinity).svg.replace(/aria-label="[^"]*"/g, "").replace(/<g id="[^"]*-loss"[\s\S]*?<\/g>/, "");
    assert.doesNotMatch(svg, />[^<]*\b(month|months|week|weeks|today|Jan|Oct|2026)\b[^<]*</i, `${variant}: a time label`);
  }
});

test("the losing months are stated, whatever they are", () => {
  assert.equal(lossLine(mc, 10000), "Not one of 120,000 simulated months lost money");
  assert.equal(lossLine(sample, 10000), "43% of 120,000 simulated months lost money");
  assert.equal(lossLine({ ...sample, share_losing: 0.004 }, 10000), "0.4% of 120,000 simulated months lost money");
  assert.ok(mcChart({ ...base, mc: sample }, Infinity).svg.includes("43% of 120,000 simulated months lost money"));
});

test("story order: the futures sweep, settle, a silence, then the answer", () => {
  const T = mcTimeline({ variant: "full" });
  assert.equal(T.reveal, T.sweep[1] + VIDEO.motion.silenceMs);
  assert.ok(T.lines[0] >= T.reveal && T.labels >= T.reveal);
  const L = mcLayout(base);
  const before = mcMoment(L, T.reveal - 1);
  assert.equal(before.pct, "", "a line of the answer before the silence ends");
  assert.equal(before.labels, "", "a figure before the silence ends");
  const mid = mcMoment(L, (T.sweep[0] + T.sweep[1]) / 2);
  assert.ok(mid.front > L.left && mid.front < L.right, "the front is not mid-chart mid-sweep");
  assert.equal((mid.tips.match(/<circle/g) || []).length, mc.paths.length, "every year's tip rides the front");
  assert.equal(mcChart(base, T.end + 1).svg, mcChart(base, Infinity).svg, "the end of the draw-in is not the still frame");
  const cues = mcChart(base, Infinity).cues;
  assert.equal(cues[0].name, "reveal");
  assert.equal(cues[0].at, Math.round(T.reveal));
  assert.ok(cues.filter((c) => c.name === "tick").length >= 6);
});

test("on the site a chart takes its colours from the stylesheet; in a film, from the tokens", () => {
  const site = mcChart({ ...base, paint: "css" }, Infinity).svg, film = mcChart(base, Infinity).svg;
  assert.doesNotMatch(site.replace(/aria-label="[^"]*"/, ""), /#[0-9a-f]{6}/i, "a literal colour on the site would ignore night sections");
  assert.doesNotMatch(film, /var\(|color-mix/, "a film frame has no stylesheet");
  assert.match(mcChart({ ...base, ground: "night" }, Infinity).svg, /mix-blend-mode:screen/);
});

test("the quiet version behind a headline says nothing and asks for nothing", () => {
  const r = mcChart({ mc, variant: "mood", w: 1000, h: 560, paint: "css" }, Infinity);
  assert.doesNotMatch(r.svg, /<text/);
  assert.deepEqual(r.cues, []);
  assert.ok(r.end < mcTimeline({ variant: "full" }).end);
});

test("on a phone the answers fit: compact figures inside the chart's width", () => {
  const L = mcLayout({ ...base, variant: "narrow", w: 360, h: 400 });
  for (const it of L.items) {
    const w = Math.max(textWidth(it.ans.cap, L.capPx), textWidth(L.figText(it.ans.v), L.figPx, 600));
    assert.ok(L.right + 14 * L.u + w <= 360 + 0.5, `${it.ans.cap} runs off a 360px screen`);
  }
  assert.deepEqual(L.answers.map((a) => L.figText(a.v)), ["$687k", "$402k", "$230k"]);
  assert.equal(L.years.length, 20);
});

test("in a page, the chart plays by patching only what moves, and ends on the still frame", () => {
  const spec = { ...base, paint: "css", id: "t" }, L = mcLayout(spec);
  // a stand-in host: innerHTML, and the seven moving parts by id
  const parts = {};
  const host = { set innerHTML(h) { this.html = h; }, querySelector(sel) { const k = sel.slice(1); return (parts[k] ??= { attrs: {}, style: {}, innerHTML: "", setAttribute(a, v) { this.attrs[a] = v; } }); } };
  let clock = 0; const queue = [];
  playMC(host, spec, { now: () => clock, raf: (fn) => queue.push(fn), caf: () => {} });
  assert.ok(host.html.startsWith("<svg"), "the structure is drawn once");
  let frames = 0;
  while (queue.length) { clock += 16; queue.shift()(); frames++; }
  assert.ok(frames > 200, "it did not play through");
  const still = mcMoment(L, Infinity);
  assert.equal(parts["t-front"].attrs.width, Math.round(still.front * 10) / 10);
  assert.equal(parts["t-pct"].innerHTML, still.pct);
  assert.equal(parts["t-labels"].innerHTML, still.labels);
  assert.equal(parts["t-tips"].innerHTML, still.tips);
});

test("a figure inside the chart is a plain group, so no page CSS can resize it", () => {
  const svg = mcChart(base, Infinity).svg;
  assert.equal((svg.match(/<svg/g) || []).length, 1, "a nested <svg> inside the chart");
  assert.equal((svg.match(/class="num-g"/g) || []).length, 3);
});
