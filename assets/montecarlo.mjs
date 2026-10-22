/* ============================================================================
   Ten thousand years: the Monte Carlo, Hubricon's signature picture.

   What it is: ten thousand equally likely years of one listing's profit.
   Its job: make the uncertainty visible and organised, and never flinch at
   the bad end. The feeling is chaos resolving into clarity.

   1. Graded light, not a flat band. The fan is built from the real simulated
      years: 25 nested bands, each holding 2% of the years on each side, so it
      is darkest where most years land and fades to nothing at the 1-in-100
      edges. The skew shows itself. (The Bank of England's fan chart: colour
      intensity tracks probability.)
   2. The years themselves. The rank-spaced simulated years are drawn as
      hairlines: bright as they sweep out from one point, then settled almost
      invisible. Each line is one equally likely year.
   3. Three answers in plain words. "1 in 10 years ends above", "a typical
      year", "1 in 10 ends below": frequencies, not P10 and P90. The figures
      arrive on the number's wheels and are rounded down to the thousand.
   4. One honest line: the share of the simulated months that lost money,
      stated even when it is none.
   5. Story order: the futures sweep out, settle, a silence, then the three
      lines draw and their figures land. Never a time axis (the founder,
      2026-10-19); never one triumphant number.

   mcLayout(spec) and mcMoment(layout, at) are pure; mcChart(spec, at) draws
   the frame for the films and the site's finished still; playMC patches a
   page's chart frame by frame from the same moment function.

   The data is the montecarlo.json contract (scripts/case-study.mjs): months,
   about fifty years at evenly spaced ranks of the year's total, the
   percentiles across all ten thousand, and share_losing. Nothing here
   simulates; the bands are the kept years' own quantiles, month by month.
   ============================================================================ */

import { css, ms, ease, VIDEO } from "./tokens.mjs";
import { painter, linear, niceTicks, shape, partial, pathD } from "./line.mjs";
import { textWidth } from "./inter.mjs";
import { numberSVG } from "./number.mjs";

// ---------------------------------------------------------------- the light
export const FAN = {
  full: { core: 0.42, restPath: 0.05, drawPath: 0.32, rug: 0.45 },     // the core's opacity where every band overlaps; the years' hairlines at rest and while sweeping
  mood: { core: 0.24, restPath: 0.035, drawPath: 0.2, rug: 0 }, // behind a headline: quieter, and no landing dots
  sub: 4,                                                   // bands between each pair of kept years, so the light has no visible steps
};

// ---------------------------------------------------------------- reading the data

const trim = (x) => String(+x.toFixed(2));
const usd = (v, { compact = false } = {}) => {
  const a = Math.abs(v), s = v < 0 ? "−" : "";
  if (compact && a >= 1e6) return `${s}$${trim(a / 1e6)}M`;
  if (compact && a >= 1e3) return `${s}$${trim(a / 1e3)}k`;
  return `${s}$${Math.round(a).toLocaleString("en-US")}`;
};
/** Rounded down to three significant figures: a figure says no more than the simulation knows, and never more than it found. */
export const floorSig = (v) => {
  if (v === 0) return 0;
  const step = 10 ** (Math.floor(Math.log10(Math.abs(v))) - 2);
  return Math.floor(v / step) * step;
};

/**
 * The kept years' quantiles at each month, as nested bands. Band j runs from the year at rank
 * position j (counting from the lowest) to the one at the same position from the highest; with
 * `sub` > 1, positions between two kept years are read between them, so the shading steps are
 * too fine to see. Every band edge is the kept years' own quantile; nothing is simulated.
 */
export function bands(mc, sub = 1) {
  const n = mc.paths.length, T = mc.months.length;
  const sorted = Array.from({ length: T }, (_, t) => mc.paths.map((p) => p[t]).sort((a, b) => a - b));
  const at = (col, j) => { const i = Math.floor(j), f = j - i; return i + 1 < col.length ? col[i] + (col[i + 1] - col[i]) * f : col[i]; };
  const count = Math.floor(((n - 1) / 2) * sub) + 1;
  return Array.from({ length: count }, (_, k) => {
    const j = k / sub;
    return { k, share: (n - 1 - 2 * j) / (n - 1), lo: sorted.map((col) => at(col, j)), hi: sorted.map((col) => at(col, n - 1 - j)) };
  }).filter((b) => b.share > 0);
}

/** The years drawn as hairlines: all of them, or evenly spaced by rank when fewer are asked for. */
const pickYears = (mc, count) => {
  const n = mc.paths.length;
  if (!count || count >= n) return mc.paths;
  return Array.from({ length: count }, (_, i) => mc.paths[Math.round((i * (n - 1)) / (count - 1))]);
};

/** The statement under the fan, true for any data: none, or the share. */
export function lossLine(mc, years = 10000) {
  const months = (years * (mc.months.length - 1)).toLocaleString("en-US");
  if (mc.share_losing === 0) return `Not one of ${months} simulated months lost money`;
  const pct = mc.share_losing * 100;
  return `${pct < 1 ? pct.toFixed(1) : Math.round(pct)}% of ${months} simulated months lost money`;
}

// ---------------------------------------------------------------- the clock

export function mcTimeline(spec) {
  const fade = ms("mc-band-ms"), draw = ms("mc-draw-ms"), settle = ms("mc-settle-ms");
  const t = {};
  t.stage = [0, fade];
  t.sweep = [fade * 0.75, fade * 0.75 + draw];               // the futures fan out from one point
  t.settle = [t.sweep[1], t.sweep[1] + settle];              // and fade back to almost nothing
  t.reveal = t.sweep[1] + VIDEO.motion.silenceMs;            // a silence, then the answer
  t.lines = [t.reveal, t.reveal + draw * 0.6];
  t.labels = t.reveal + draw * 0.15;                         // the figures start as the lines get going
  t.loss = [t.labels + ms("count-ms"), t.labels + ms("count-ms") + fade];   // the honest line, once the figures have landed
  t.end = spec.variant === "mood" ? t.settle[1] : Math.max(t.labels + ms("count-ms") + 2 * ms("stagger"), t.loss[1]);
  return t;
}
const prog = (at, [a, b]) => (b <= a ? (at >= a ? 1 : 0) : Math.min(1, Math.max(0, (at - a) / (b - a))));

// ---------------------------------------------------------------- the chart
// Two halves: mcLayout(spec) is everything that never moves (scales, the fan, the years'
// hairlines, the words), built once; mcMoment(layout, at) is what changes with time. mcChart
// joins them into one frame; playMC builds the layout once and patches only the moment.

/**
 * spec: {
 *   mc, variant: "full" | "mood" | "narrow", w, h, font, paint ("css" | "inline"), ground,
 *   years (10,000), paths (how many years to draw as hairlines), title?, titlePx?, subtitle?, source?, id
 * }
 */
export function mcLayout(spec) {
  const mc = spec.mc, variant = spec.variant || "full", mood = variant === "mood", narrow = variant === "narrow";
  const P = painter(spec.paint, spec.ground);
  const f = spec.font || 13, u = f / 13, id = spec.id || "mc";
  const fine = Math.sqrt(u);                                 // hairlines and dots grow slower than type, so a film's stay fine
  const T = mcTimeline({ ...spec, variant });
  const look = mood ? FAN.mood : FAN.full;
  const W = spec.w, H = spec.h, pad = (mood ? 0 : 8) * u;
  const txt = (x, y, s, { size = f, weight = 400, fill = "ink-3", anchor = "start", tab = false } = {}) =>
    `<text x="${r1(x)}" y="${r1(y)}" text-anchor="${anchor}" style="font-size:${r1(size)}px;font-weight:${weight};fill:${P(fill)};${tab ? "font-variant-numeric:tabular-nums;" : ""}">${esc(s)}</text>`;

  // ---- what is said, and how much room it takes
  const end = mc.months.length - 1;
  const pc = mc.percentiles;
  const answers = [
    { q: "p90", cap: narrow ? "1 in 10 above" : "1 in 10 years ends above", v: floorSig(pc.p90[end]), tone: "money", line: "blue" },
    { q: "p50", cap: narrow ? "Typical year" : "A typical year", v: floorSig(pc.p50[end]), tone: "ink", line: "ink" },
    { q: "p10", cap: narrow ? "1 in 10 below" : "1 in 10 years ends below", v: floorSig(pc.p10[end]), tone: "money", line: "blue" },
  ];
  const figPx = f * (narrow ? 1.15 : 1.3), capPx = f * 0.92;
  const figText = (v) => usd(v, { compact: narrow });
  const labelW = mood ? 0 : Math.max(...answers.map((a) => Math.max(textWidth(a.cap, capPx, 400), textWidth(figText(a.v), figPx, 600)))) + 16 * u;

  let top = pad, bottom = H - pad, head = "", loss = "", source = "";
  if (spec.title && !mood) { const ts = spec.titlePx || f * 1.55; head += txt(pad, top + ts * 0.86, spec.title, { size: ts, weight: 600, fill: "ink" }); top += ts * 1.25; }
  if (spec.subtitle && !mood) { head += txt(pad, top + f * 0.9, spec.subtitle); top += f * 1.6; }
  if ((spec.title || spec.subtitle) && !mood) top += f * 0.9;
  if (!mood) {
    const rows = [["loss", lossLine(mc, spec.years)], ["source", spec.source]].filter(([, s]) => s);
    rows.forEach(([k, s], i) => {
      const y = bottom - f * 0.15 - (rows.length - 1 - i) * f * 1.45;
      const t = txt(pad, y, s, { size: f * 0.85, fill: k === "loss" ? "ink-2" : "ink-3" });
      if (k === "loss") loss = t; else source = t;
    });
    if (rows.length) bottom -= f * 1.45 * rows.length + f * 0.6;
  }

  // ---- scales: money up the side, no time along the bottom
  const all = [...mc.paths.flat(), ...pc.p10, ...pc.p90];
  const lo = Math.min(0, ...all), hi = Math.max(...all);
  const ticks = mood ? [] : niceTicks(lo, hi, narrow ? 3 : 4);
  const d0 = Math.min(lo, ticks[0] ?? lo), d1 = Math.max(hi, ticks[ticks.length - 1] ?? hi);
  const tickW = mood ? 0 : Math.max(...ticks.map((v) => textWidth(usd(v, { compact: true }), f, 400, true)));
  const left = mood ? pad : pad + tickW + 12 * u;
  const right = W - pad - labelW;
  const plotTop = top + (mood ? 0 : f * 0.6), plotBottom = bottom - (mood ? 0 : f * 0.4);
  const X = linear(mc.months[0], mc.months[end], left, right);
  const Y = linear(d0, d1, plotBottom, plotTop);
  const xs = mc.months.map(X);
  const curve = (vals) => shape(vals.map((v, i) => [xs[i], Y(v)]), "monotone");

  let gridLines = "", gridText = "";
  for (const v of ticks) {
    const y = Y(v), zero = v === 0;
    gridLines += `<line x1="${r1(left)}" x2="${r1(right)}" y1="${r1(y)}" y2="${r1(y)}" style="stroke:${P(zero ? "rule-2" : "rule")};stroke-width:${r1(parseFloat(css("line-hair")) * fine * (zero ? 1.5 : 1))}px;shape-rendering:crispEdges"/>`;
    gridText += txt(left - 12 * u, y + f * 0.34, usd(v, { compact: true }), { anchor: "end", tab: true });
  }

  // ---- the fan: nested bands, outermost first, each opaque and painted the exact colour the
  // light has at its depth. Stacking hundreds of faint transparent layers instead rounds every
  // colour channel on every layer, and the blue drifts toward violet; this never drifts.
  const B = bands(mc, FAN.sub);
  const depthAlpha = (k) => 1 - Math.pow(1 - look.core, (k + 1) / B.length);
  const tint = mixer(spec.paint, spec.ground);
  let fan = "";
  for (const b of B) {
    const upper = curve(b.hi), lower = curve(b.lo);
    const back = pathD(lower.slice().reverse().map((s) => ({ ...s, p0: s.p1, c1: s.c2, c2: s.c1, p1: s.p0 }))).replace(/^M[^LC]*/, "");
    fan += `<path d="${pathD(upper)} L${r1(xs[end])} ${r1(Y(b.lo[end]))}${back}Z" style="fill:${tint(depthAlpha(b.k))}"/>`;
  }

  // ---- the years, as hairlines; their curves are kept for the tips
  const years = pickYears(mc, spec.paths ?? (narrow ? 20 : mc.paths.length)).map(curve);
  const hair = years.map((segs) => `<path d="${pathD(segs)}" style="fill:none;stroke:${P("blue")};stroke-width:${r1(fine)}px;stroke-linejoin:round"/>`).join("");

  // ---- the three answers: their curves, and their labels' places, stacked so they never touch
  const lines = mood ? [] : answers.map((ans) => ({ ans, segs: curve(pc[ans.q]) }));
  const blockH = capPx * 1.25 + figPx * 1.05;
  const items = mood ? [] : answers.map((ans) => ({ ans, y: Y(pc[ans.q][end]) - blockH / 2 }));
  for (let i = 1; i < items.length; i++) if (items[i].y < items[i - 1].y + blockH + 6 * u) items[i].y = items[i - 1].y + blockH + 6 * u;
  if (items.length) {
    const over = items[items.length - 1].y + blockH - plotBottom;
    if (over > 0) for (const it of items) it.y -= over;
    if (items[0].y < plotTop - f) { const d = plotTop - f - items[0].y; for (const it of items) it.y += d; }
  }

  return { spec, id, variant, mood, f, u, fine, W, H, P, T, look, left, right, plotTop, plotBottom, answers, figPx, capPx, figText,
    head, loss, source, gridLines, gridText, fan, hair, years, lines, items, txt };
}

/** What changes with time: the front, the opacities, the tips, the three lines and their figures. */
export function mcMoment(L, at) {
  const { T, look, u, f, P, spec, id } = L;
  const ez = ease("ease-out");
  const stage = ez(prog(at, T.stage));
  const sweep = ease("ease-sweep")(prog(at, T.sweep));
  const front = L.left + (L.right - L.left) * sweep;
  const settle = ez(prog(at, T.settle));
  const drawn = ez(prog(at, T.lines));
  const yearsOp = sweep < 1 ? look.drawPath : look.drawPath + (look.restPath - look.drawPath) * settle;
  // each year's tip rides the front, and lands: a column of dots where the years end
  const tipsOp = sweep < 1 ? 0.75 : 0.75 + (look.rug - 0.75) * settle;
  let tips = "";
  if (sweep > 0 && tipsOp > 0) for (const segs of L.years) {
    const tip = sweep < 1 ? pointAtX(segs, front) : segs[segs.length - 1].p1;
    if (tip) tips += `<circle cx="${r1(tip[0])}" cy="${r1(tip[1])}" r="${r1(1.6 * L.fine)}" style="fill:${P("blue")}"/>`;
  }
  let pct = "";
  if (drawn > 0) for (const { ans, segs } of L.lines) {
    const part = partial(segs, drawn);
    if (part.segs.length) pct += `<path d="${pathD(part.segs)}" style="fill:none;stroke:${P(ans.line)};stroke-width:${r1(parseFloat(css("line-pct")) * u * (ans.q === "p50" ? 1.15 : 1))}px;stroke-linecap:round;stroke-linejoin:round"/>`;
  }
  let labels = "";
  L.items.forEach((it, i) => {
    const lx = L.right + 14 * u, start = T.labels + i * ms("stagger");
    const op = ez(prog(at, [start, start + ms("mc-band-ms")]));
    if (op <= 0) return;
    labels += L.txt(lx, it.y + L.capPx * 0.95, it.ans.cap, { size: L.capPx }).replace('style="', `style="opacity:${r2(op)};`);
    labels += numberSVG({ text: L.figText(it.ans.v), px: L.figPx, tone: it.ans.tone, paint: spec.paint, ground: spec.ground, start }, at,
      { id: `${id}-n${i}`, place: [lx, it.y + L.capPx * 1.25 - L.figPx * 0.12] }).svg;
  });
  const lossOp = L.mood ? 0 : ez(prog(at, T.loss));
  return { stage, front, yearsOp, tipsOp, tips, pct, labels, lossOp };
}

/** One frame: the still for the site when `at` is Infinity, any moment of the draw-in otherwise. */
export function mcChart(spec, at = Infinity) {
  const L = mcLayout(spec);
  return { svg: compose(L, mcMoment(L, at)), cues: mcCues(L), end: L.T.end };
}

function compose(L, m) {
  const { id, W, H, P, spec } = L;
  return `<svg class="chart mc-chart mc-chart--${L.variant}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(describe(spec.mc, L.answers, spec))}" style="font-family:${spec.paint === "inline" ? "Inter Display, Inter, sans-serif" : "var(--font)"}">` +
    `<defs><clipPath id="${id}-sweep"><rect id="${id}-front" x="0" y="0" width="${r1(Math.max(0, m.front))}" height="${H}"/></clipPath></defs>` +
    (spec.paint === "inline" ? `<rect width="${W}" height="${H}" style="fill:${P("paper")}"/>` : "") +
    L.head +
    `<g clip-path="url(#${id}-sweep)"><g class="mc-fan">${L.fan}</g></g>` +
    // the grid is printed over the light, like ink on a page: multiplied by day, screened by night
    `<g id="${id}-grid" style="opacity:${r2(m.stage)}"><g class="mc-grid" style="mix-blend-mode:${spec.ground === "night" ? "screen" : "multiply"}">${L.gridLines}</g>${L.gridText}</g>` +
    `<g clip-path="url(#${id}-sweep)"><g id="${id}-years" class="mc-years" style="opacity:${r3(m.yearsOp)}">${L.hair}</g></g>` +
    `<g id="${id}-tips" class="mc-tips" style="opacity:${r2(m.tipsOp)}">${m.tips}</g>` +
    `<g id="${id}-pct">${m.pct}</g><g id="${id}-labels">${m.labels}</g>` +
    `<g id="${id}-loss" style="opacity:${r2(m.lossOp)}">${L.loss}</g>${L.source}` +
    `</svg>`;
}

/** The sound: the reveal as the three lines start, and each figure's ticks. */
export function mcCues(L) {
  if (L.mood) return [];
  const cues = [{ name: "reveal", at: Math.round(L.T.reveal) }];
  L.answers.forEach((ans, i) => {
    for (const c of numberSVG({ text: L.figText(ans.v), px: L.figPx, start: L.T.labels + i * ms("stagger") }, 0).cues) if (c.name === "tick") cues.push(c);
  });
  return cues.sort((p, q) => p.at - q.at);
}

/**
 * Play a chart in a page: draw the still's structure once, then patch only what moves, frame
 * by frame, from the same moment function a film uses. Returns a function that stops it and
 * leaves the finished still.
 */
export function playMC(host, spec, { now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame } = {}) {
  const L = mcLayout(spec), id = L.id;
  host.innerHTML = compose(L, mcMoment(L, 0));
  const $ = (k) => host.querySelector(`#${id}-${k}`);
  const el = { front: $("front"), grid: $("grid"), years: $("years"), tips: $("tips"), pct: $("pct"), labels: $("labels"), loss: $("loss") };
  const t0 = now();
  let rid = 0;
  const paint = (at) => {
    const m = mcMoment(L, at);
    el.front.setAttribute("width", r1(Math.max(0, m.front)));
    el.grid.style.opacity = r2(m.stage);
    el.years.style.opacity = r3(m.yearsOp);
    el.tips.style.opacity = r2(m.tipsOp);
    el.tips.innerHTML = m.tips;
    el.pct.innerHTML = m.pct;
    el.labels.innerHTML = m.labels;
    el.loss.style.opacity = r2(m.lossOp);
  };
  const stop = () => { caf(rid); paint(Infinity); };
  const frame = () => { const at = now() - t0; paint(at); if (at < L.T.end) rid = raf(frame); else stop(); };
  rid = raf(frame);
  return stop;
}

const r1 = (v) => Math.round(v * 10) / 10;
const r2 = (v) => Math.round(v * 100) / 100;
const r3 = (v) => Math.round(v * 1000) / 1000;

/**
 * The blue laid over the ground at a given strength, as one solid colour. On the site it stays
 * a mix of the stylesheet's own variables, so a night section re-tints it; in a film it is the
 * tokens' values, mixed here.
 */
export function mixer(paint = "css", ground = "day") {
  if (paint === "css") return (alpha) => `color-mix(in srgb, var(--blue) ${(Math.round(alpha * 1000) / 10).toFixed(1)}%, var(--paper))`;
  const night = ground === "night";
  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const b = rgb(css(night ? "night-blue" : "blue")), p = rgb(css(night ? "night" : "paper"));
  return (alpha) => "#" + b.map((c, i) => Math.round(p[i] + (c - p[i]) * alpha).toString(16).padStart(2, "0")).join("");
}

/** Where a hairline is when the front reaches x: its point at that x, found on its own curve. */
function pointAtX(segs, x) {
  const s = segs.find((g) => x >= g.p0[0] && x <= g.p1[0]);
  if (!s) return null;
  const at = (u) => { const m = 1 - u; return [0, 1].map((k) => m * m * m * s.p0[k] + 3 * m * m * u * s.c1[k] + 3 * m * u * u * s.c2[k] + u * u * u * s.p1[k]); };
  let lo = 0, hi = 1;
  for (let i = 0; i < 30; i++) { const mid = (lo + hi) / 2; if (at(mid)[0] < x) lo = mid; else hi = mid; }
  return at((lo + hi) / 2);
}

function describe(mc, answers, spec) {
  const [hi, mid, lo] = answers;
  return `${(spec.years || 10000).toLocaleString("en-US")} simulated years of one listing's profit. ` +
    `One year in ten ends above ${usd(hi.v)}, a typical year at ${usd(mid.v)}, and one in ten below ${usd(lo.v)}. ${lossLine(mc, spec.years)}.`;
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
