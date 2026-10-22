// Ten thousand years: graded light from the real years, plain answers, honest order, a story the
// reader drives, a year they can touch, a card they can take.
//   node --test scripts/montecarlo.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { bands, lossLine, floorSig, mixer, mcLayout, mcMoment, mcChart, mcTimeline, playMC, FAN,
  mcStory, mcStoryState, mcStoryFrame, mcStoryCues, mcNearestYear, mcCard, playStory } from "../assets/montecarlo.mjs";
import { css, VIDEO, CAMERA } from "../assets/tokens.mjs";
import { textWidth } from "../assets/inter.mjs";

const read = (p) => JSON.parse(readFileSync(new URL(`../${p}`, import.meta.url)));
const mc = read("data/montecarlo.json"), sample = read("data/montecarlo.sample.json");
const LABEL = "Modeled from public data · Not a client · Not a result";
const base = { mc, w: 760, h: 440, font: 13, paint: "inline", source: LABEL };

// a stand-in page: innerHTML once, then every moving part by id
function standIn() {
  const parts = {};
  const node = () => ({ attrs: {}, style: {}, innerHTML: "", setAttribute(a, v) { this.attrs[a] = v; }, addEventListener() {} });
  const host = { set innerHTML(h) { this.html = h; }, querySelector(sel) { return sel === "svg" ? (parts.svg ??= node()) : (parts[sel.slice(1)] ??= node()); } };
  return { host, parts };
}

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
  const { host, parts } = standIn();
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

test("at rest the years live only inside the light; while they sweep, they are bright and a wave rides the front", () => {
  const L = mcLayout(base), T = L.T;
  const rest = mcMoment(L, Infinity), mid = mcMoment(L, (T.sweep[0] + T.sweep[1]) / 2);
  assert.equal(rest.brightOp, 0, "bright hairlines left on at rest");
  assert.ok(rest.lightOp > 0 && rest.restOp < rest.lightOp / 4, "the resting years are not held by the light");
  assert.ok(mid.brightOp > 0 && mid.waveOp > 0 && rest.waveOp === 0);
  const svg = mcChart(base, Infinity).svg;
  assert.match(svg, /<g id="mc-inlight" mask="url\(#mc-light\)"/, "the resting years are not masked by the light");
  assert.equal((svg.match(/<mask id="mc-light"[^>]*>(.*?)<\/mask>/)[1].match(/<path/g) || []).length, bands(mc, FAN.sub).length, "the mask is not the fan's own bands");
  // the mask is the light in greys, brightest at the core
  const greys = [...svg.match(/<mask id="mc-light"[^>]*>(.*?)<\/mask>/)[1].matchAll(/rgb\((\d+),/g)].map((m) => +m[1]);
  assert.ok(greys.every((g, i) => i === 0 || g >= greys[i - 1]) && greys.at(-1) === 255);
});

test("nothing at no strength is drawn: an empty layer is out of the drawing, never invisible", () => {
  const L = mcLayout(base);
  const frames = [0, L.T.sweep[0], 900, L.T.reveal, Infinity].map((t) => mcChart(base, t).svg);
  for (const t of [600, 3200, 6000, 9000, 12500, 16000]) frames.push(mcStoryFrame({ ...base, id: "s" }, t).svg);
  for (const svg of frames) assert.doesNotMatch(svg, /(?:"|;)opacity:0(\.0+)?(["]|;(?!display:none))/, "a layer at no strength left in the drawing");
});

test("the story's words are worked out from the data, true for any listing", () => {
  for (const [data, losing] of [[mc, false], [sample, true]]) {
    const L = mcLayout({ ...base, mc: data, years: 10000, forward: "What the finding costs." });
    const beats = mcStory(L);
    assert.deepEqual(beats.map((b) => b.key), ["years", "core", "low", "high", "range"]);
    assert.deepEqual(beats.map((b) => b.title), ["10,000 possible years.", "Most of them land here.", "One year in ten does worse.", "One year in ten does better.", "The range we plan for."]);
    for (const b of beats) assert.ok(b.title.split(" ").length <= VIDEO.wordsOnScreen, `${b.title}: too many words for the screen`);
    assert.ok(beats[2].body.includes(lossLine(data, 10000).replace(/^Not/, losing ? "Not" : "not")), "the bad end does not state the losing months");
    const end = data.months.length - 1, pc = data.percentiles, up = pc.p90[end] - pc.p50[end] > pc.p50[end] - pc.p10[end];
    assert.ok(beats[3].body.includes(up ? "upside spreads wider" : "downside spreads wider"));
    assert.equal(beats[4].body, "What the finding costs.");
    for (const b of beats) assert.doesNotMatch(b.title + b.body, /\b(month|week|Jan|Oct|2026|P10|P90|median|percentile)\b/i);
  }
});

test("the camera: never nearer than the tokens allow, its frame the chart's shape, the subject and its answer in view", () => {
  const L = mcLayout(base), beats = mcStory(L), end = mc.months.length - 1;
  const maxZ = Math.min(CAMERA.zoom.max, FAN.push);
  beats.forEach((b, i) => {
    const [x, y, w, h] = b.view, z = L.W / w;
    assert.ok(z <= maxZ + 1e-9, `${b.key}: zoom ${z}`);
    assert.ok(Math.abs(w / h - L.W / L.H) < 1e-6, `${b.key}: the frame is not the chart's shape`);
    assert.ok(x >= -1e-6 && y >= -1e-6 && x + w <= L.W + 1e-6 && y + h <= L.H + 1e-6, `${b.key}: past the chart's edge`);
    if (i) assert.ok(Math.abs(Math.log(z / (L.W / beats[i - 1].view[2]))) <= Math.log(CAMERA.zoom.maxPerMove) + 1e-9, `${b.key}: too far in one move`);
    if (!b.answer) return;
    // its answer's words, whole, above the paper the statements sit on
    const it = L.items.find((t) => t.ans.q === b.answer), screenY = (v) => (v - y) * z;
    assert.ok(screenY(it.y) >= 0 && screenY(it.y + L.blockH) <= L.footTop - 24 * L.u, `${b.key}: its answer is cut or under the margin`);
    assert.ok((L.right + 14 * L.u - x) * z >= 0, `${b.key}: its answer is off the side`);
  });
  // the bad end is shown with the floor under it
  const low = beats.find((b) => b.key === "low").view, zl = L.W / low[2];
  assert.ok((L.Y(0) - low[1]) * zl <= L.footTop - 24 * L.u, "the floor is not in view at the bad end");
});

test("where the camera rests, every money label is whole or gone, and the scale rides the view's edge", () => {
  const { clock, beats } = mcStoryFrame({ ...base, id: "s" }, 0);
  beats.forEach((b, i) => {
    const t = i === 0 ? clock.first - 1 : clock.first + (i - 1) * clock.beatMs + clock.beatMs * 0.95;
    const { svg, state } = mcStoryFrame({ ...base, id: "s" }, t);
    const ops = [...svg.matchAll(/<text id="s-tk\d+"[^>]*style="opacity:([\d.]+)/g)].map((m) => +m[1]);
    assert.ok(ops.length >= 3, `${b.key}: the money scale is missing`);
    for (const op of ops) assert.ok(op <= 0.02 || op >= 0.98, `${b.key}: a money label left half-faded (${op})`);
    assert.ok(ops.filter((op) => op >= 0.98).length >= 2, `${b.key}: fewer than two money labels to read the scale by`);
    // the scale's figures sit inside the view, at its left edge
    const shift = +svg.match(/<g id="s-ticks" transform="translate\(([\d.]+) 0\)/)[1];
    if (state.camera[0] > 0) assert.ok(shift > 0, `${b.key}: the scale was left behind off-screen`);
  });
});

test("the label never leaves the screen: the statements are fixed to it, above every margin", () => {
  for (const t of [600, 4000, 6000, 8200, 11800, 15600, 17900]) {
    const { svg, state } = mcStoryFrame({ ...base, id: "s" }, t);
    const [x, y, w] = state.camera;
    const m = svg.match(/<g id="s-screen" transform="([^"]*)">/);
    assert.ok(m, "no screen layer");
    if (w < base.w) assert.equal(m[1], `translate(${Math.round(x * 10) / 10} ${Math.round(y * 10) / 10}) scale(${(w / base.w).toFixed(5)})`);
    const screen = svg.slice(svg.indexOf('<g id="s-screen"'));
    assert.ok(screen.includes(LABEL), "the label is not on the screen layer");
    assert.ok(svg.indexOf('<g id="s-screen"') > svg.indexOf('<g id="s-ticks"'), "a margin is drawn over the label");
  }
});

test("the answers draw with the reader's scroll, and land as the camera arrives", () => {
  const L = mcLayout(base);
  const at = (s) => mcStoryState(L, s);
  assert.equal(at(1.99).lineFrac.p10, 0);
  assert.equal(at(2.45).lineFrac.p10, 1);
  assert.equal(at(2.1).labelOn.p10, false);
  assert.equal(at(2.3).labelOn.p10, true);
  assert.equal(at(2.3).glide > 0.75, true, "the figure lands before the camera is nearly there");
  // reversible: the same place in the story is the same picture, whichever way the reader came
  assert.deepEqual(at(3.2), at(3.2));
  assert.deepEqual(mcStoryFrame({ ...base, id: "s" }, 9100).svg, mcStoryFrame({ ...base, id: "s" }, 9100).svg);
  // the subject's words stay; the others' leave, their lines stay quiet as a reference
  const low = at(2.9);
  assert.equal(low.words.p50, 0);
  assert.equal(low.emph.p50, FAN.aside);
  assert.equal(low.words.p10, 1);
});

test("touch lights one real year: its own figure and rank, in a corner no year crosses", () => {
  const L = mcLayout(base), n = mc.paths.length, end = mc.months.length - 1;
  const sorted = mc.paths.map((p) => p[end]).sort((a, b) => a - b);
  for (const j of [0, 7, 24, 49]) {
    const yr = L.years[j];
    assert.equal(yr.end, sorted[j], "the years are not in rank order");
    const k = mcNearestYear(L, L.right - 2, L.Y(yr.end));
    assert.equal(k, j, "the touch did not find the year under the finger");
    const m = mcMoment(L, 5000, { touch: { year: k, start: 4000 } });
    assert.ok(m.touched.includes(`Better than ${Math.floor(((j + 0.5) / n) * 100)} in 100`));
    assert.ok(m.touched.includes("$" + floorSig(yr.end).toLocaleString("en-US")));
    assert.ok(m.touched.includes("1 of 10,000 years"));
  }
  // the readout's corner: every year passes below it
  const box = { x0: L.readout.x, x1: L.readout.x + 220 * L.u, y1: L.readout.y + L.capPx * 2.9 + L.figPx * 1.45 };
  for (const yr of L.years) for (let x = box.x0; x <= Math.min(box.x1, L.right); x += 4) {
    const s = yr.segs.find((g) => x >= g.p0[0] && x <= g.p1[0]);
    if (s) assert.ok(Math.min(s.p0[1], s.p1[1]) > box.y1, "a year runs through the readout");
  }
});

test("the card: one clean page of the chart, the label on it, Hubricon's own mark", () => {
  const svg = mcCard({ ...base, id: "c" });
  assert.match(svg, /^<svg viewBox="0 0 1200 630" width="1200" height="630"/);
  assert.ok(svg.includes(LABEL));
  assert.ok(svg.includes(">Hubricon</text>"));
  assert.ok(svg.includes('<path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z"/>'), "not the mark in BRAND.md");
  for (const s of ["$687,000", "$402,000", "$230,000"]) assert.ok(svg.includes(`aria-label="${s}"`), `${s} missing from the card`);
  assert.doesNotMatch(svg, /var\(|color-mix/, "a card leaves the site: it carries its own colours");
});

test("the story plays from the reader's scroll, patching only what moves, and sleeps when nothing does", () => {
  const spec = { ...base, paint: "css", id: "p" }, L = mcLayout(spec);
  const { host, parts } = standIn();
  let clock = 0, s = 0, wake = null; const queue = [], seen = [], views = [];
  playStory(host, spec, { progress: () => s, onBeat: (b) => seen.push(b.key), now: () => clock, raf: (fn) => queue.push(fn), caf: () => {},
    subscribe: (fn) => { wake = fn; return () => {}; } });
  assert.ok(host.html.startsWith("<svg"));
  const run = (ms) => { for (let t = 0; t < ms; t += 16) { clock += 16; const f = queue.shift(); if (f) { f(); if (parts.svg.attrs.viewBox) views.push(parts.svg.attrs.viewBox.split(" ").map(Number)); } } };
  run(L.T.settle[1] + 100);
  assert.equal(queue.length, 0, "it keeps drawing when nothing moves");
  assert.deepEqual(seen, ["years"]);
  s = 3.5; wake(); run(200);                           // a fling: the story follows quickly, never cuts
  run(3000);
  assert.equal(seen.at(-1), "high");
  for (let i = 1; i < views.length; i++) {
    const jump = Math.max(...views[i].map((v, k) => Math.abs(v - views[i - 1][k])));
    assert.ok(jump < spec.w * 0.12, `the camera cut ${jump.toFixed(0)} units in one frame`);
  }
  s = 4.99; wake(); run(3000);
  assert.equal(seen.at(-1), "range");
  assert.equal(parts.svg.attrs.viewBox, `0 0 ${spec.w} ${spec.h}`);
  assert.equal((parts["p-labels"].innerHTML.match(/class="num-g"/g) || []).length, 3, "the range does not show all three answers");
  assert.equal(queue.length, 0, "it keeps drawing after the range has landed");
  s = 2.9; wake(); run(3000);                          // and back
  assert.equal(seen.at(-1), "low");
  assert.notEqual(parts.svg.attrs.viewBox, `0 0 ${spec.w} ${spec.h}`);
});

test("a touched chart wakes for the touch and sleeps again", () => {
  const spec = { ...base, paint: "css", id: "q" }, L = mcLayout(spec);
  const { host } = standIn();
  let clock = 0; const queue = [];
  playMC(host, spec, { now: () => clock, raf: (fn) => queue.push(fn), caf: () => {} });
  for (let i = 0; i < 400 && queue.length; i++) { clock += 16; queue.shift()(); }
  assert.ok(clock >= L.T.end && queue.length === 0, "the draw-in did not finish and sleep");
});

test("the story film's sound: a turn for each move, a reveal as each figure lands, then its ticks", () => {
  const L = mcLayout(base), cues = mcStoryCues(L);
  assert.deepEqual([...new Set(cues.map((c) => c.name))].sort(), ["reveal", "tick", "turn"]);
  assert.equal(cues.filter((c) => c.name === "turn").length, 4);
  assert.equal(cues.filter((c) => c.name === "reveal").length, 3);
  assert.ok(cues.every((c, i) => i === 0 || c.at >= cues[i - 1].at), "cues out of order");
  const ticks = cues.filter((c) => c.name === "tick");
  assert.ok(ticks.every((c, i) => i === 0 || c.at - ticks[i - 1].at >= 1000 / 20 - 1), "more than twenty ticks a second");
});
