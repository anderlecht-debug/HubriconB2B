// The line: honest geometry, a frame for any exact moment, labels that never collide.
//   node --test scripts/line.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { shape, partial, pathD, lineChart, textWidth, place, timeline, painter, valueAt, lineSnap, lineTouch, worstFall, lineCard, playLine, wrap } from "../assets/line.mjs";
import { ms, VIDEO } from "../assets/tokens.mjs";

const cubicAt = (s, u) => { const m = 1 - u; return [0, 1].map((k) => m * m * m * s.p0[k] + 3 * m * m * u * s.c1[k] + 3 * m * u * u * s.c2[k] + u * u * u * s.p1[k]); };

test("a monotone curve passes through every real point and invents nothing between them", () => {
  const pts = [[0, 10], [1, 12], [2, 30], [3, 31], [4, 31], [5, 18], [6, 2], [7, 2.5], [8, 40]];
  const segs = shape(pts, "monotone");
  assert.equal(segs.length, pts.length - 1);
  segs.forEach((s, i) => {
    assert.deepEqual(s.p0, pts[i]); assert.deepEqual(s.p1, pts[i + 1]);
    const lo = Math.min(pts[i][1], pts[i + 1][1]) - 1e-9, hi = Math.max(pts[i][1], pts[i + 1][1]) + 1e-9;
    for (let k = 0; k <= 40; k++) { const y = cubicAt(s, k / 40)[1]; assert.ok(y >= lo && y <= hi, `segment ${i} overshoots to ${y}`); }
  });
});

test("a step shape is only flats and risers, and every riser is marked", () => {
  const segs = shape([[0, 1], [4, 2], [8, 3], [10, 3]], "step");
  for (const s of segs) assert.ok(s.p0[0] === s.p1[0] || s.p0[1] === s.p1[1], "a diagonal in a step shape");
  assert.equal(segs.filter((s) => s.riser).length, 2);
  assert.ok(segs.every((s) => (s.riser ? s.p0[0] === s.p1[0] : s.p0[1] === s.p1[1])));
});

test("a partial line grows with time, ends exactly at the full line, and its tip carries a real value", () => {
  const pts = [[0, 0], [10, 50], [20, 40], [30, 90]];
  const segs = shape(pts, "monotone");
  let last = -1;
  for (let k = 0; k <= 20; k++) {
    const p = partial(segs, k / 20);
    assert.ok(p.tip[0] >= last - 1e-9, "the tip went backwards"); last = p.tip[0];
    if (p.seg) assert.ok(pts.some(([, y]) => y === p.seg.v), "the tip's value is not a data point");
  }
  assert.equal(pathD(partial(segs, 1).segs), pathD(segs));
  assert.deepEqual(partial(segs, 0).tip, [0, 0]);
});

// A dense synthetic chart: two step cards close together, a riser, two dots and a note.
const spec = (paint = "inline") => ({
  w: 760, h: 440, font: 13, paint,
  title: "A title that states the finding", subtitle: "Units, in plain words", source: "Source · Not a client · Not a result",
  x: { domain: [0, 20], ticks: [0, 4, 8, 12, 16, 20], format: (v, last) => (last ? `${v} oz` : `${v}`) },
  y: { format: (v) => `$${v.toFixed(2)}` },
  series: [
    { id: "a", points: [[0, 3.86], [4, 4.09], [8, 4.35], [12, 4.76], [16, 5.21], [20, 5.21]], kind: "step", role: "context", name: "Other card" },
    { id: "b", points: [[0, 4.11], [4, 4.36], [8, 4.64], [12, 5.06], [16, 5.53], [20, 5.53]], kind: "step", role: "focus", name: "Card in force", tip: (v) => `$${v.toFixed(2)}` },
  ],
  risers: [{ x: 8, y0: 4.36, y1: 4.64 }],
  dots: [{ x: 8, y: 4.36, hollow: true, label: "8.0 oz, one step down" }, { x: 8.8, y: 4.64, label: "This listing, 8.8 oz", emphasis: true }],
  notes: [{ x: 8, y: 4.5, title: "+$0.28 a unit", body: "$6,400–$19,200 a year, estimate" }],
});

test("the finished frame is the still frame: the end of the draw-in and Infinity are the same picture", () => {
  const T = timeline(spec());
  assert.equal(lineChart(spec(), T.end + 1).svg, lineChart(spec(), Infinity).svg);
});

test("story order: nothing of the finding before the silence ends, and the reveal cue lands on it", () => {
  const s = spec(), T = timeline(s);
  assert.ok(T.context[1] <= T.focus[0], "the context must be on screen before the series that matters");
  assert.equal(T.reveal, T.focus[1] + VIDEO.motion.silenceMs);
  const before = lineChart(s, T.reveal - 1).svg;
  assert.doesNotMatch(before, /a unit<\/text>/, "the note shows before the silence");
  assert.doesNotMatch(before, /stroke:#0b5fff/, "the blue riser shows before the silence");
  const r = lineChart(s, Infinity);
  assert.deepEqual(r.cues.filter((c) => c.name === "reveal").map((c) => c.at), [T.reveal]);
  assert.equal(r.cues.filter((c) => c.name === "tick").length, 4, "one tick per step the focus line climbs");
  assert.ok(r.cues.filter((c) => c.name === "tick").every((c) => c.at > T.focus[0] && c.at <= T.focus[1]));
  assert.equal(T.focus[1] - T.focus[0], ms("mc-draw-ms"));
});

test("while drawing, the tip shows only values the data really has", () => {
  const s = spec(), T = timeline(s), real = new Set(s.series[1].points.map(([, y]) => `$${y.toFixed(2)}`));
  for (let at = T.focus[0] + 20; at < T.focus[1]; at += 97) {
    const m = lineChart(s, at).svg.match(/font-weight:600;fill:#0a0e17;font-variant-numeric:tabular-nums;[^"]*">([^<]+)<\/text><\/svg>/) ||
      lineChart(s, at).svg.match(/>(\$\d+\.\d\d)<\/text>(?:<text[^>]*>[^<]*<\/text>)*<\/svg>/);
    if (m) assert.ok(real.has(m[1]), `the tip showed ${m[1]}`);
  }
});

test("no two labels overlap in the finished frame", () => {
  const svg = lineChart(spec(), Infinity).svg;
  const boxes = [...svg.matchAll(/<text x="([\d.]+)" y="([\d.]+)" text-anchor="(\w+)"[^>]*font-size:([\d.]+)px;font-weight:(\d+)[^>]*>([^<]+)<\/text>/g)].map((m) => {
    const [x, y, anchor, size, weight, s] = [+m[1], +m[2], m[3], +m[4], +m[5], m[6].replace(/&amp;/g, "&")];
    const w = textWidth(s, size, weight);
    const left = anchor === "end" ? x - w : anchor === "middle" ? x - w / 2 : x;
    return { s, x: left, y: y - size * 0.8, w, h: size };
  });
  assert.ok(boxes.length >= 15);
  for (let i = 0; i < boxes.length; i++) for (let k = i + 1; k < boxes.length; k++) {
    const a = boxes[i], b = boxes[k];
    const ov = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
    assert.ok(ov < 4, `"${a.s}" overlaps "${b.s}"`);
  }
});

test("on the site a chart takes its colours from the stylesheet; in a film, from the tokens' values", () => {
  const site = lineChart(spec("css"), Infinity).svg, film = lineChart(spec("inline"), Infinity).svg;
  assert.doesNotMatch(site, /#[0-9a-f]{6}/i, "a literal colour on the site would ignore night sections");
  assert.match(site, /var\(--ink\)/);
  assert.doesNotMatch(film, /var\(/, "a film frame has no stylesheet to resolve var()");
  assert.equal(painter("inline", "night")("paper"), "#070a11");
});

test("the blue is only on the finding", () => {
  const svg = lineChart(spec("css"), Infinity).svg;
  const blue = [...svg.matchAll(/<[^>]*var\(--blue\)[^>]*>(?:([^<]*)<\/text>)?/g)].map((m) => m[0]);
  assert.ok(blue.length >= 2);
  for (const el of blue) assert.ok(/<line x1="([\d.]+)" x2="\1"/.test(el) || /a unit/.test(el), `blue on something that is not the finding: ${el.slice(0, 80)}`);
});

test("text is measured, and the solver prefers clear space near its point", () => {
  assert.ok(textWidth("Hubricon", 13, 600) > textWidth("Hubricon", 13, 400));
  assert.equal(textWidth("8,888", 13, 400, true), textWidth("1,111", 13, 400, true), "tabular digits must be equal width");
  const bounds = { x: 0, y: 0, w: 100, h: 100 };
  const taken = [{ x: 0, y: 0, w: 50, h: 50 }];
  const c = place([{ x: 10, y: 10, w: 10, h: 10 }, { x: 60, y: 10, w: 10, h: 10 }], taken, bounds, [55, 15]);
  assert.equal(c.x, 60);
});

test("growth with no time scale: a chart without x ticks draws no labels under its axis", () => {
  const s = { ...spec(), x: { domain: [0, 20] }, series: [spec().series[1]], risers: [], dots: [], notes: [] };
  const svg = lineChart(s, Infinity).svg;
  const axisY = +svg.match(/<line x1="[\d.]+" x2="[\d.]+" y1="([\d.]+)" y2="\1" style="stroke:#cdd2da/)[1];
  // the value axis's labels sit in the left margin, set flush right; anything else under the axis is an x label
  const below = [...svg.matchAll(/<text x="[\d.]+" y="([\d.]+)" text-anchor="(\w+)"[^>]*>([^<]+)<\/text>/g)]
    .filter((m) => m[2] !== "end" && +m[1] > axisY + 2 && +m[1] < s.h - 24).map((m) => [m[1], m[2], m[3]]);
  assert.deepEqual(below.map((m) => m[2]), [], "labels under the axis");
  assert.ok(lineChart(spec(), Infinity).svg.includes(">20 oz<"), "a numerical driver still gets its axis");
});

// ---- taken to 11: the reading, the pin, the worst fall, the card

const readable = () => ({ ...spec(), id: "r", x: { ...spec().x, read: (v) => `${v.toFixed(1)} oz`, snap: 0.1 }, y: { ...spec().y, read: (v) => `$${v.toFixed(2)} a unit` } });
const two = () => ({
  w: 760, h: 440, font: 13, paint: "inline", id: "c", x: { domain: [0, 10] }, y: { format: (v) => `${v / 1000}k`, read: (v) => Math.round(v).toLocaleString("en-US") },
  series: [
    { id: "called", points: [[0, 0], [2, 1000], [4, 2100], [6, 3000], [8, 4100], [10, 5000]], kind: "monotone", role: "ghost", name: "Called 5,000", short: "Called" },
    { id: "measured", points: [[0, 0], [2, 900], [4, 2000], [6, 3300], [8, 4000], [10, 5125]], kind: "monotone", role: "focus", name: "Measured 5,125", short: "Measured", tip: (v) => Math.round(v).toLocaleString("en-US") },
  ],
  compare: (m, c) => `${Math.abs((m / c - 1) * 100).toFixed(1)}% ${m >= c ? "above" : "below"} the call`,
});

test("a step reads anywhere on its tread, an edge belonging to the tread before it; a curve only at its real points", () => {
  const st = spec().series[1];
  assert.equal(valueAt(st, 8), 4.36, "8.0 oz is still the lower tread");
  assert.equal(valueAt(st, 8.1), 4.64);
  assert.equal(valueAt(st, 0), 4.11);
  assert.equal(valueAt(two().series[1], 6), 3300);
  assert.equal(valueAt(two().series[1], 5), null, "a curve read between its real points would invent a value");
  const g = lineChart(two(), Infinity).geom;
  for (const px of [g.left + 3, (g.left + g.right) / 2 + 7, g.right - 1]) assert.ok(two().series[1].points.some(([x]) => x === lineSnap(g, px)), "touch landed between real points");
  const gs = lineChart(readable(), Infinity).geom;
  assert.equal(lineSnap(gs, gs.X(8.83)), 8.8, "a step reads at its snap");
});

test("the reading: each line's real value, the gap to the other, the change since a pin, in a corner nothing else uses", () => {
  const r = lineChart(two(), Infinity, { touch: { x: 6, pin: 2 } });
  const svg = r.svg;
  assert.ok(svg.includes(">Measured 3,300<") && svg.includes(">Called 3,000<"));
  assert.ok(svg.includes(">10.0% above the call<"), "the gap to the other line");
  assert.ok(svg.includes(">Since the pin +2,400<"), "the change since the pin");
  const one = { ...readable(), series: [{ ...readable().series[1], short: "" }] };
  const st = lineChart(one, Infinity, { touch: { x: 8.8 } }).svg;
  assert.ok(st.includes(">8.8 oz<") && st.includes(">$4.64 a unit<"));
  assert.ok(st.includes(">Next step +$0.42 a unit past 12.0 oz<"), "the staircase does not say where its next step is");
  // the reading's place is chosen once, clear of every line and label, and does not move with the finger
  const g = r.geom, box = g.readout;
  for (const x of [0, 4, 10]) assert.deepEqual(lineChart(two(), Infinity, { touch: { x } }).geom.readout, box);
  for (const q of two().series) for (const [x, y] of q.points) {
    const sx = g.X(x), sy = g.Y(y);
    assert.ok(!(sx > box.x - 2 && sx < box.x + box.w + 2 && sy > box.y - 2 && sy < box.y + box.h + 2), "a line runs through the reading");
  }
});

test("no time scale sneaks in through the reading: a chart with no axis words says no place", () => {
  const svg = lineChart(two(), Infinity, { touch: { x: 4 } }).svg;
  assert.doesNotMatch(svg, />[^<]*\b(week|weeks|month|months|day|days)\b[^<]*</i);
  assert.equal(lineTouch(lineChart(two(), Infinity).geom, { x: 4 }).front.match(/<text/g).length, 3, "only the two values and the gap");
});

test("the worst fall is named when the line falls, with whether it came back, and never invented", () => {
  assert.equal(worstFall([[0, 1], [1, 2], [2, 3]]), null);
  const f = worstFall([[0, 0], [1, 13], [2, 9], [3, 8], [4, 14]]);
  assert.deepEqual([f.i, f.j, f.fall, f.back], [1, 3, 5, true]);
  assert.equal(worstFall([[0, 5], [1, 2], [2, 4]]).back, false);
  const falling = { ...two(), series: [{ ...two().series[1], points: [[0, 0], [2, 9000], [4, 6000], [6, 5000], [8, 9500], [10, 12000]], name: "Profit" }] };
  const svg = lineChart(falling, Infinity).svg;
  assert.ok(svg.includes(">Worst fall −4,000<") && svg.includes(">then it came back<"));
  assert.doesNotMatch(lineChart(two(), Infinity).svg, /Worst fall/, "a line that never falls is not given a fall");
  assert.doesNotMatch(lineChart(falling, timeline(falling).reveal - 1).svg, /Worst fall/, "the fall is named before the silence ends");
});

test("the card: one clean page with the label and the mark from BRAND.md", () => {
  const svg = lineCard({ ...two(), title: "A title", source: "Modeled on published data · Not a client · Not a result" });
  assert.match(svg, /^<svg viewBox="0 0 1200 630"/);
  assert.ok(svg.includes(">A title<") && svg.includes("Not a client · Not a result") && svg.includes(">Hubricon</text>"));
  assert.ok(svg.includes('<path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z"/>'));
  assert.doesNotMatch(svg, /var\(/);
});

test("in a page the line draws in, then rests: it sleeps until a finger moves", () => {
  const html = {}, host = { set innerHTML(h) { html.h = h; }, get innerHTML() { return html.h; }, querySelector(sel) { return (html[sel] ??= { innerHTML: "" }); } };
  let clock = 0; const queue = [];
  playLine(host, two(), { now: () => clock, raf: (fn) => queue.push(fn), caf: () => {} });
  let frames = 0;
  while (queue.length && frames < 1000) { clock += 16; queue.shift()(); frames++; }
  assert.equal(queue.length, 0, "it kept drawing after the draw-in");
  assert.equal(html.h, lineChart(two(), Infinity).svg, "it did not end on the still");
});

test("on a phone the title and the label wrap to the chart's width; no part of the label is split", () => {
  const long = "Online Retail II, UCI Machine Learning Repository, CC BY 4.0 · Modeled on published data · Not a client · Not a result";
  const lines = wrap(long, 11, 400, 330, " · ");
  assert.ok(lines.length >= 2);
  assert.ok(lines.every((l) => textWidth(l, 11, 400) <= 330));
  assert.ok(lines.some((l) => l.includes("Not a client")) && lines.join(" ").includes("Not a result"));
  const svg = lineChart({ ...two(), w: 360, h: 420, title: "Called 7,671 repeat orders. The store measured 7,865", source: long }, Infinity).svg;
  for (const m of svg.matchAll(/<text x="([\d.]+)" y="[\d.]+" text-anchor="start"[^>]*font-size:([\d.]+)px;font-weight:(\d+)[^>]*>([^<]+)<\/text>/g))
    assert.ok(+m[1] + textWidth(m[4].replace(/&amp;/g, "&"), +m[2], +m[3]) <= 360 + 0.5, `"${m[4]}" runs off a 360px chart`);
});
