/* ============================================================================
   Ten thousand years: the Monte Carlo, Hubricon's signature picture.

   What it is: ten thousand equally likely years of one listing's profit.
   Its job: make the uncertainty visible and organised, and never flinch at
   the bad end. The feeling is chaos resolving into clarity.

   Built to the scoreboard's ladder (HUBRICON_SPEC.md, "the 11-out-of-5"):

   5  It does the job. Graded light from the real simulated years: nested
      bands of the kept years' own quantiles, darkest where most years land,
      fading to nothing at the 1-in-100 edges (the Bank of England's fan
      chart). Three answers in plain words ("1 in 10 years ends above", "a
      typical year", "1 in 10 years ends below"), rounded down. The share of
      losing months stated on the chart, even when it is none. No time axis.
   6  An instrument. Painted in exact solid colours, never stacked
      transparency (which drifts the blue to violet). The years' hairlines
      sweep out bright, then rest only inside the light, so empty space
      carries no stray rays. A wave of light travels with the front. Under
      the camera the money scale rides the view's edge on a margin of paper,
      and the statements under the chart are fixed to the screen.
   7  A heartbeat. Touch the fan and the nearest real year lights up end to
      end; its figure and its rank in a hundred sit in the one corner no year
      crosses, and change the instant the finger does.
   8  It tells you what you did not ask. The story's last beat ties the
      range to the finding: what one weight step costs out of these years.
   9  It is yours. A five-beat story the reader drives by scrolling, and can
      drive back: the years, where most land, the bad end, the good end, the
      range. The camera glides inside the CAMERA tokens' limits.
   10 It anticipates the scary moment. The camera goes to the bad end before
      anyone asks, and states the floor.
   11 It makes you look smart in front of someone else: mcCard, one clean
      card of the chart for a deck, with Hubricon's quiet mark.

   Everything is a pure function: mcLayout(spec) once, then mcMoment for a
   moment in time and mcStoryState for a point in the story. A film renders
   frames from them; a page patches only what moves (playMC, playStory).

   The data is the montecarlo.json contract (scripts/case-study.mjs). Nothing
   here simulates; every band edge is the kept years' own quantile.
   ============================================================================ */

import { css, ms, ease, VIDEO, CAMERA } from "./tokens.mjs";
import { painter, linear, niceTicks, shape, partial, pathD } from "./line.mjs";
import { textWidth } from "./inter.mjs";
import { numberSVG } from "./number.mjs";

// ---------------------------------------------------------------- the light
export const FAN = {
  full: { core: 0.42, restPath: 0.05, lightPath: 0.42, drawPath: 0.32, rug: 0.45, wave: 0.5 },
  mood: { core: 0.24, restPath: 0.03, lightPath: 0.22, drawPath: 0.2, rug: 0, wave: 0.3 },  // behind a headline: quieter, no landing dots
  sub: 4,               // bands between each pair of kept years, so the light has no visible steps
  waveShare: 0.12,      // the wave of light behind the front, as a share of the plot's width
  veil: 0.64,           // how far the story dims what is not its subject
  aside: 0.28,          // an answer that is not the subject of the moment, or while a year is touched
  push: 1.9,            // the story's closest camera: near enough to read the end, far enough to keep the floor
};

// ---------------------------------------------------------------- reading the data

const trim = (x) => String(+x.toFixed(2));
const usd = (v, { compact = false } = {}) => {
  const a = Math.abs(v), s = v < 0 ? "−" : "";
  if (compact && a >= 1e6) return `${s}$${trim(a / 1e6)}M`;
  if (compact && a >= 1e3) return `${s}$${trim(a / 1e3)}k`;
  return `${s}$${Math.round(a).toLocaleString("en-US")}`;
};
/** Rounded down to three significant figures: a figure says no more than the simulation found. */
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

/**
 * The years drawn as hairlines, lowest end first, each with its rank among the kept years (which
 * are spaced evenly by rank through all ten thousand): all of them, or evenly spaced by rank when
 * fewer are asked for.
 */
const pickYears = (mc, count) => {
  const n = mc.paths.length, last = mc.months.length - 1;
  const order = mc.paths.map((p, i) => [p[last], i]).sort((a, b) => a[0] - b[0]).map(([, i]) => i);
  const pos = !count || count >= n ? order.map((_, j) => j) : Array.from({ length: count }, (_, k) => Math.round((k * (n - 1)) / (count - 1)));
  return pos.map((j) => ({ path: mc.paths[order[j]], rank: (j + 0.5) / n }));
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
  t.settle = [t.sweep[1], t.sweep[1] + settle];              // and come to rest inside the light
  t.reveal = t.sweep[1] + VIDEO.motion.silenceMs;            // a silence, then the answer
  t.lines = [t.reveal, t.reveal + draw * 0.6];
  t.labels = t.reveal + draw * 0.15;                         // the figures start as the lines get going
  t.loss = [t.labels + ms("count-ms"), t.labels + ms("count-ms") + fade];   // the honest line, once the figures have landed
  t.end = spec.variant === "mood" ? t.settle[1] : Math.max(t.labels + ms("count-ms") + 2 * ms("stagger"), t.loss[1]);
  return t;
}
const prog = (at, [a, b]) => (b <= a ? (at >= a ? 1 : 0) : Math.min(1, Math.max(0, (at - a) / (b - a))));

// ---------------------------------------------------------------- the layout: everything that never moves

/**
 * spec: {
 *   mc, variant: "full" | "mood" | "narrow", w, h, font, paint ("css" | "inline"), ground,
 *   years (10,000), paths (how many years to draw), title?, titlePx?, subtitle?, source?, id,
 *   forward? (the story's last line: what the finding costs out of these years)
 * }
 */
export function mcLayout(spec) {
  const mc = spec.mc, variant = spec.variant || "full", mood = variant === "mood", narrow = variant === "narrow";
  const P = painter(spec.paint, spec.ground);
  const f = spec.font || 13, u = f / 13, id = spec.id || "mc";
  const fine = Math.sqrt(u);                                 // hairlines and dots grow slower than type
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
  const footTop = mood ? H : bottom + f * 0.2;     // the statements under the chart live below this line, on the screen, not in the chart

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
  const reverse = (segs) => pathD(segs.slice().reverse().map((s) => ({ ...s, p0: s.p1, c1: s.c2, c2: s.c1, p1: s.p0 }))).replace(/^M[^LC]*/, "");

  const hairline = parseFloat(css("line-hair")) * fine;
  let gridLines = "";
  const tickRows = [];
  for (const v of ticks) {
    const y = Y(v), zero = v === 0;
    gridLines += `<line x1="${r1(left)}" x2="${r1(right)}" y1="${r1(y)}" y2="${r1(y)}" vector-effect="non-scaling-stroke" style="stroke:${P(zero ? "rule-2" : "rule")};stroke-width:${r1(hairline * (zero ? 1.5 : 1))}px;shape-rendering:crispEdges"/>`;
    tickRows.push({ y, svg: txt(left - 12 * u, y + f * 0.34, usd(v, { compact: true }), { anchor: "end", tab: true }) });
  }

  // ---- the fan: nested bands, outermost first, each opaque and painted the exact colour the
  // light has at its depth (stacked transparency would round each channel per layer and drift
  // the blue toward violet). The same bands, in greys, make the mask that keeps the resting
  // years inside the light.
  const B = bands(mc, FAN.sub);
  const depthAlpha = (k) => 1 - Math.pow(1 - look.core, (k + 1) / B.length);
  const tint = mixer(spec.paint, spec.ground);
  let fan = "", light = "";
  for (const b of B) {
    const d = `${pathD(curve(b.hi))} L${r1(xs[end])} ${r1(Y(b.lo[end]))}${reverse(curve(b.lo))}Z`;
    fan += `<path d="${d}" style="fill:${tint(depthAlpha(b.k))}"/>`;
    const g = Math.round(255 * Math.min(1, Math.pow(depthAlpha(b.k) / look.core, 0.8)));
    light += `<path d="${d}" fill="rgb(${g},${g},${g})"/>`;
  }

  // ---- the years, as hairlines; their curves are kept for the tips and for touch
  const years = pickYears(mc, spec.paths ?? (narrow ? 20 : mc.paths.length)).map((y) => ({ ...y, segs: curve(y.path), end: y.path[end] }));
  const hair = years.map((y) => `<path d="${pathD(y.segs)}" vector-effect="non-scaling-stroke" style="fill:none;stroke:${P("blue")};stroke-width:${r1(fine)}px;stroke-linejoin:round"/>`).join("");

  // ---- the three answers: their curves, and their labels' places, stacked so they never touch
  const lines = mood ? [] : answers.map((ans) => ({ ans, segs: curve(pc[ans.q]) }));
  const blockH = capPx * 1.25 + figPx * 1.05;
  const items = mood ? [] : answers.map((ans) => ({ ans, y: Y(pc[ans.q][end]) - blockH / 2 }));
  for (let i = 1; i < items.length; i++) if (items[i].y < items[i - 1].y + blockH + 6 * u) items[i].y = items[i - 1].y + blockH + 6 * u;
  if (items.length) {
    const over = items[items.length - 1].y + blockH - plotBottom;
    if (over > 0) for (const it of items) it.y -= over;
    if (items[0].y < plotTop - f) { const dd = plotTop - f - items[0].y; for (const it of items) it.y += dd; }
  }

  // ---- what the story dims: everything but its subject
  const box = { x0: left - 4 * u, x1: right + 4 * fine, y0: plotTop - f, y1: plotBottom };
  const mid = B.reduce((best, b) => (Math.abs(b.share - 0.5) < Math.abs(best.share - 0.5) ? b : best), B[0]);
  const rect = `M${r1(box.x0)} ${r1(box.y0)} H${r1(box.x1)} V${r1(box.y1)} H${r1(box.x0)}Z`;
  const pcurve = (q) => curve(pc[q]);
  const veils = {
    core: `${rect} ${pathD(curve(mid.hi))} L${r1(xs[end])} ${r1(Y(mid.lo[end]))}${reverse(curve(mid.lo))}Z`,
    low: `M${r1(box.x0)} ${r1(box.y0)} H${r1(box.x1)} V${r1(Y(pc.p10[end]))}${reverse(pcurve("p10"))} L${r1(box.x0)} ${r1(Y(pc.p10[0]))}Z`,
    high: `M${r1(box.x0)} ${r1(box.y1)} H${r1(box.x1)} V${r1(Y(pc.p90[end]))}${reverse(pcurve("p90"))} L${r1(box.x0)} ${r1(Y(pc.p90[0]))}Z`,
  };

  // ---- where a touched year's readout lives: one fixed place, in the corner the fan leaves empty
  // (every year starts from the same point, so the light opens away from one side), never chasing the finger
  const rise = pc.p50[end] >= pc.p50[0];
  const readout = { x: left + 18 * u, y: rise ? plotTop + 2 * u : plotBottom - capPx * 2.9 - figPx * 1.45 - 2 * u };

  return { spec, id, variant, mood, narrow, f, u, fine, W, H, P, T, look, left, right, plotTop, plotBottom, X, Y, xs, d0, d1,
    answers, figPx, capPx, figText, head, loss, source, footTop, gridLines, tickRows, tickW, fan, light, hair, years, lines, items, blockH, veils, mid, readout, txt };
}

// ---------------------------------------------------------------- a moment

/**
 * What changes with time. `story` (from mcStoryState) overrides when the answers draw and land;
 * `touch` ({ year, start }) lights one real year.
 */
export function mcMoment(L, at, { story = null, touch = null } = {}) {
  const { T, look, u, P, spec, id } = L;
  const ez = ease("ease-out");
  // the camera's push enlarges everything but the hairlines (which keep their width on screen);
  // the dots on them keep their size on screen too
  const zoom = story?.zoom || 1, fine = L.fine / zoom;
  // a touched year takes the stage: the answers step back while it is lit
  const lit = touch ? ez(prog(at, [touch.start, touch.start + 160])) : 0;
  const aside = (q) => (story?.emph?.[q] ?? 1) * (1 - (1 - FAN.aside) * lit);
  const words = (q) => (story?.words?.[q] ?? 1) * (1 - (1 - FAN.aside) * lit);
  const stage = ez(prog(at, T.stage));
  const sweep = ease("ease-sweep")(prog(at, T.sweep));
  const front = L.left + (L.right - L.left) * sweep;
  const settle = ez(prog(at, T.settle));
  // while the years sweep they are bright everywhere; at rest they live only inside the light
  const brightOp = sweep <= 0 ? 0 : look.drawPath * (1 - settle);
  const lightOp = look.lightPath * settle;
  const restOp = look.restPath * settle;
  // the wave: a band of extra light just behind the front, gone once the years have landed
  const waveW = (L.right - L.left) * FAN.waveShare;
  const waveOp = sweep > 0 ? look.wave * (1 - settle) : 0;
  // each year's tip rides the front, and lands: a column of dots where the years end
  const tipsOp = sweep < 1 ? 0.75 : 0.75 + (look.rug - 0.75) * settle;
  let tips = "";
  if (sweep > 0 && tipsOp > 0) for (const y of L.years) {
    const tip = sweep < 1 ? pointAtX(y.segs, front) : y.segs[y.segs.length - 1].p1;
    if (tip) tips += `<circle cx="${r1(tip[0])}" cy="${r1(tip[1])}" r="${r1(1.6 * fine)}" style="fill:${P("blue")}"/>`;
  }
  // the answers: by the clock, or by the story
  let pct = "", labels = "";
  for (const { ans, segs } of L.lines) {
    const drawn = story ? story.lineFrac[ans.q] : ez(prog(at, T.lines));
    if (drawn <= 0) continue;
    const part = partial(segs, drawn);
    if (part.segs.length) pct += `<path d="${pathD(part.segs)}" style="fill:none;stroke:${P(ans.line)};stroke-width:${r1(parseFloat(css("line-pct")) * u * (ans.q === "p50" ? 1.15 : 1))}px;stroke-linecap:round;stroke-linejoin:round;opacity:${r3(aside(ans.q))}"/>`;
  }
  L.items.forEach((it, i) => {
    const start = story ? story.labelStart[it.ans.q] : T.labels + i * ms("stagger");
    if (start == null) return;
    const op = ez(prog(at, [start, start + ms("mc-band-ms")])) * words(it.ans.q);
    if (op < 0.005) return;
    const lx = L.right + 14 * u;
    labels += L.txt(lx, it.y + L.capPx * 0.95, it.ans.cap, { size: L.capPx }).replace('style="', `style="opacity:${r2(op)};`);
    const fig = numberSVG({ text: L.figText(it.ans.v), px: L.figPx, tone: it.ans.tone, paint: spec.paint, ground: spec.ground, start }, at,
      { id: `${id}-n${i}`, place: [lx, it.y + L.capPx * 1.25 - L.figPx * 0.12] }).svg;
    const back = words(it.ans.q);
    labels += back < 0.999 ? `<g style="opacity:${r3(back)}">${fig}</g>` : fig;
  });
  const lossOp = L.mood ? 0 : story ? story.lossOp : ez(prog(at, T.loss));
  // the story's veils
  let veil = "";
  if (story) for (const v of story.veils) if (v.op > 0.001) veil += `<path d="${L.veils[v.kind]}" fill-rule="evenodd" style="fill:${P("paper")};opacity:${r3(v.op * FAN.veil)}"/>`;
  // a touched year
  const touched = touch ? touchSVG(L, touch, at, fine) : "";
  return { stage, front, brightOp, lightOp, restOp, waveW, waveOp, tipsOp, tips, pct, labels, lossOp, veil, touched };
}

/**
 * One real year, lit: its whole line and its end, and its readout in the one fixed place the fan
 * leaves empty. The reader's finger is the animation, so a new year shows at once (no count, no
 * lag); the figures are tabular, so nothing shifts as they change. Only the first touch fades in.
 */
function touchSVG(L, { year, start }, at, fine) {
  const { P, u, spec } = L;
  const y = L.years[year];
  if (!y) return "";
  const endPt = y.segs[y.segs.length - 1].p1;
  const op = ease("ease-out")(prog(at, [start, start + 160]));
  const cp = L.capPx, fp = L.figPx * 1.3, { x, y: top } = L.readout;
  const halo = `paint-order:stroke;stroke:${P("paper")};stroke-width:${r1(4 * u)}px;stroke-linejoin:round;`;
  const line = (yy, s, size, weight, fill) =>
    `<text x="${r1(x)}" y="${r1(yy)}" style="${halo}font-size:${r1(size)}px;font-weight:${weight};fill:${P(fill)};font-variant-numeric:tabular-nums">${esc(s)}</text>`;
  if (op <= 0.0005) return "";
  return `<g style="opacity:${r2(op)}">` +
    `<path d="${pathD(y.segs)}" vector-effect="non-scaling-stroke" style="fill:none;stroke:${P("blue")};stroke-width:${r1(2 * L.fine)}px;stroke-linejoin:round"/>` +
    `<circle cx="${r1(endPt[0])}" cy="${r1(endPt[1])}" r="${r1(4 * fine)}" style="fill:${P("blue")};stroke:${P("paper")};stroke-width:${r1(2 * fine)}px"/>` +
    line(top + cp * 1.0, `1 of ${(spec.years || 10000).toLocaleString("en-US")} years`, cp, 400, "ink-3") +
    line(top + cp * 1.45 + fp * 0.95, usd(floorSig(y.end)), fp, 600, "blue") +
    line(top + cp * 2.5 + fp * 1.45, `Better than ${Math.floor(y.rank * 100)} in 100`, cp, 400, "ink-2") +
    `</g>`;
}

/** The nearest real year to a point on the chart, in the chart's own units. */
export function mcNearestYear(L, x, y) {
  const cx = Math.min(L.right, Math.max(L.left + 1, x));
  let best = -1, dist = Infinity;
  L.years.forEach((yr, i) => { const p = pointAtX(yr.segs, cx); if (p && Math.abs(p[1] - y) < dist) { dist = Math.abs(p[1] - y); best = i; } });
  return best;
}

// ---------------------------------------------------------------- one frame

export function mcChart(spec, at = Infinity, opts = {}) {
  const L = mcLayout(spec);
  return { svg: compose(L, mcMoment(L, at, opts), opts.story?.camera), cues: mcCues(L), end: L.T.end };
}

function compose(L, m, view = null) {
  const { id, W, H, P, spec } = L;
  const v = view || [0, 0, W, H];
  return `<svg class="chart mc-chart mc-chart--${L.variant}" viewBox="${v.map(r1).join(" ")}" role="img" aria-label="${esc(describe(spec.mc, L.answers, spec))}" style="font-family:${spec.paint === "inline" ? "Inter Display, Inter, sans-serif" : "var(--font)"}">` +
    `<defs><clipPath id="${id}-sweep"><rect id="${id}-front" x="0" y="0" width="${r1(Math.max(0, m.front))}" height="${H}"/></clipPath>` +
    `<mask id="${id}-light" maskUnits="userSpaceOnUse" x="0" y="0" width="${W}" height="${H}">${L.light}</mask>` +
    `<linearGradient id="${id}-gut-g" x1="0" y1="0" x2="1" y2="0">${gutterStops(L, P)}</linearGradient>` +
    `<linearGradient id="${id}-band-g" x1="0" y1="0" x2="0" y2="1">${[0, 0.25, 0.5, 0.75].map((k) => [k * (24 * L.u) / (H - L.footTop + 24 * L.u), 1 - Math.pow(1 - k, 2)]).concat([[(24 * L.u) / (H - L.footTop + 24 * L.u), 1], [1, 1]]).map(([o, a]) => `<stop offset="${r3(o)}" style="stop-color:${P("paper")};stop-opacity:${r3(a * 0.96)}"/>`).join("")}</linearGradient>` +
    `<linearGradient id="${id}-wave-g" x1="0" y1="0" x2="1" y2="0"><stop offset="0" style="stop-color:${P("blue")};stop-opacity:0"/><stop offset="1" style="stop-color:${P("blue")};stop-opacity:1"/></linearGradient></defs>` +
    (spec.paint === "inline" ? `<rect x="${r1(v[0])}" y="${r1(v[1])}" width="${r1(v[2])}" height="${r1(v[3])}" style="fill:${P("paper")}"/>` : "") +
    L.head +
    `<g clip-path="url(#${id}-sweep)"><g class="mc-fan">${L.fan}</g></g>` +
    `<rect id="${id}-wave" x="${r1(m.front - m.waveW)}" y="0" width="${r1(m.waveW)}" height="${H}" fill="url(#${id}-wave-g)" mask="url(#${id}-light)" style="opacity:${r3(m.waveOp)}${off(m.waveOp)}"/>` +
    // the grid is printed over the light, like ink on a page: multiplied by day, screened by night
    `<g id="${id}-grid" style="opacity:${r2(m.stage)}${off(m.stage)}"><g class="mc-grid" style="mix-blend-mode:${spec.ground === "night" ? "screen" : "multiply"}">${L.gridLines}</g></g>` +
    `<g clip-path="url(#${id}-sweep)">` +
      `<g id="${id}-bright" class="mc-years" style="opacity:${r3(m.brightOp)}${off(m.brightOp)}">${L.hair}</g>` +
      `<g id="${id}-rest" style="opacity:${r3(m.restOp)}${off(m.restOp)}">${L.hair}</g>` +
      `<g id="${id}-inlight" mask="url(#${id}-light)" style="opacity:${r3(m.lightOp)}${off(m.lightOp)}">${L.hair}</g>` +
    `</g>` +
    `<g id="${id}-tips" class="mc-tips" style="opacity:${r2(m.tipsOp)}${off(m.tipsOp)}">${m.tips}</g>` +
    `<g id="${id}-veil">${m.veil}</g>` +
    `<g id="${id}-pct">${m.pct}</g><g id="${id}-labels">${m.labels}</g>` +
    `<g id="${id}-touch">${m.touched}</g>` +

    // the money scale rides the left edge of whatever the camera shows, so a push-in never loses it
    // over the light, it reads off a margin of paper the data fades into, as the edge of a page would
    `<g id="${id}-ticks" transform="translate(${r1(tickShift(L, v))} 0)" style="opacity:${r2(m.stage)}${off(m.stage)}">` +
      `<rect id="${id}-gutter" x="${r1(L.left - 12 * L.u - L.tickW - 16 * L.u)}" y="${-H}" width="${r1(L.tickW + 64 * L.u)}" height="${H * 3}" fill="url(#${id}-gut-g)" style="opacity:${r2(gutterOp(L, tickShift(L, v)))}${off(gutterOp(L, tickShift(L, v)))}"/>` +
      L.tickRows.map((t, i) => { const op = tickOp(L, v, t.y); return t.svg.replace("<text ", `<text id="${id}-tk${i}" `).replace('style="', `style="opacity:${r2(op)}${off(op)};`); }).join("") + `</g>` +
    // the statements under the chart (the losing months, the label that never comes off) are fixed to the
    // screen: whatever the camera does, they stay where they were, on a margin of paper the chart goes under
    `<g id="${id}-screen" transform="${screenT(L, v)}">` +
      `<rect id="${id}-band" x="0" y="${r1(L.footTop - 24 * L.u)}" width="${W}" height="${r1(H - L.footTop + 24 * L.u)}" fill="url(#${id}-band-g)" style="opacity:${r2(bandOp(L, v))}${off(bandOp(L, v))}"/>` +
      `<g id="${id}-loss" style="opacity:${r2(m.lossOp)}${off(m.lossOp)}">${L.loss}</g>${L.source}` +
    `</g>` +
    `</svg>`;
}

/** How far the money scale slides right to stay inside the camera's view. */
function tickShift(L, view) {
  return Math.max(0, view[0] + L.tickW + 8 * L.u - (L.left - 12 * L.u));
}
/** The margin's paper: solid under the figures, then an eased fade, so the light has no edge where it goes under. */
function gutterStops(L, P) {
  const total = L.tickW + 64 * L.u, solid = (L.tickW + 20 * L.u) / total;
  return [[0, 1], [solid, 0.94], ...[0.25, 0.5, 0.75, 1].map((k) => [solid + (1 - solid) * k, 0.94 * Math.pow(1 - k, 2)])]
    .map(([o, a]) => `<stop offset="${r3(o)}" style="stop-color:${P("paper")};stop-opacity:${r3(a)}"/>`).join("");
}
/**
 * A money label's strength under the camera: whole while its line is on screen and clear of the
 * margins, fading as it nears an edge, so a label is never cut in half or left ghosted under paper.
 */
function tickOp(L, v, y) {
  const z = L.W / v[2], sy = (y - v[1]) * z, ramp = 10 * L.u;
  const top = 2 * L.u + L.f * 0.7 * z;
  const floor = L.H + (L.footTop - 24 * L.u - L.H) * bandOp(L, v) - L.f * 0.5 * z;
  return Math.min(1, Math.max(0, (sy - top) / ramp + 1), Math.max(0, (floor - sy) / ramp + 1));
}

/** The screen's own place inside the camera's view: the inverse of the camera. */
const screenT = (L, v) => (v[2] === L.W && !v[0] && !v[1] ? "" : `translate(${r1(v[0])} ${r1(v[1])}) scale(${(v[2] / L.W).toFixed(5)})`);
/** The paper under the statements: none at rest (it would cover the chart's floor), full once the camera has pushed in. */
const bandOp = (L, v) => Math.max(0, Math.min(1, (L.W / v[2] - 1) / 0.12));
/** The paper margin under a sliding scale: none at rest (it would hide where the years start), full once the scale is over the light. */
const gutterOp = (L, shift) => Math.min(1, shift / (24 * L.u));

/** The sound: the reveal as the three lines start, and each figure's ticks. */
export function mcCues(L) {
  if (L.mood) return [];
  const cues = [{ name: "reveal", at: Math.round(L.T.reveal) }];
  L.answers.forEach((ans, i) => {
    for (const c of numberSVG({ text: L.figText(ans.v), px: L.figPx, start: L.T.labels + i * ms("stagger") }, 0).cues) if (c.name === "tick") cues.push(c);
  });
  return cues.sort((p, q) => p.at - q.at);
}

// ---------------------------------------------------------------- the story

/**
 * Where the camera looks to show a region: the region with a margin, widened to the frame's shape
 * toward the left (the answers sit on the right), never closer than FAN.push or the CAMERA tokens
 * allow, and never past the chart's own edges. Returns a viewBox.
 */
function frameOf(L, x0, x1, y0, y1) {
  const { W, H } = L, ar = W / H, pad = 12 * L.u;
  const gutter = L.tickW + 30 * L.u, foot = H - L.footTop + 24 * L.u;   // the margins, in screen units
  let view = [0, 0, W, H];
  for (let pass = 0; pass < 4; pass++) {           // the margins shrink in the chart's units as the camera pushes in
    const k = view[2] / W;
    let a = x0 - pad - gutter * k, b = Math.min(W, x1 + pad), c = y0 - pad, d = y1 + pad + foot * k;
    let w = b - a, h = d - c;
    if (w / h < ar) { w = h * ar; a = b - w; } else { const nh = w / ar; c -= (nh - h) / 2; h = nh; }
    const minW = W / Math.min(CAMERA.zoom.max, FAN.push);
    if (w < minW) { const cy = c + h / 2; w = minW; h = w / ar; a = b - w; c = cy - h / 2; }
    view = w >= W ? [0, 0, W, H] : [Math.min(Math.max(0, a), W - w), Math.min(Math.max(0, c), H - h), w, h];
  }
  // where the camera comes to rest, no money label is left half-faded at the top edge: it is lifted fully into view
  for (const t of L.tickRows) {
    const op = tickOp(L, view, t.y);
    if (op > 0.02 && op < 0.98 && (t.y - view[1]) * (W / view[2]) < H / 2) view[1] = Math.max(0, view[1] - ((1 - op) * 10 * L.u) / (W / view[2]) - 0.5);
  }
  return view;
}

/**
 * Five beats, each a sentence and a place on the chart. The words are worked out from the data,
 * so they are true for any listing: which end spreads wider, whether any month lost money. The
 * camera frames each beat's subject with its answer, and the bad end with the floor under it.
 */
export function mcStory(L) {
  const { spec, answers, W, H, Y, items, blockH } = L;
  const [hi, mid, lo] = answers;
  const mc = spec.mc, pc = mc.percentiles, end = mc.months.length - 1;
  const ends = mc.paths.map((p) => p[end]);
  const upWider = pc.p90[end] - pc.p50[end] > pc.p50[end] - pc.p10[end];
  const floor = mc.share_losing === 0 ? `Even then, ${lossLine(mc, spec.years).replace(/^Not/, "not")}.` : `${lossLine(mc, spec.years)}.`;
  const item = (q) => items.find((it) => it.ans.q === q);
  const x0 = L.left + (L.right - L.left) * 0.5;
  const full = [0, 0, W, H];
  const core = frameOf(L, x0, W, Math.min(Y(L.mid.hi[end]), item("p50").y), Math.max(Y(L.mid.lo[end]), item("p50").y + blockH));
  const low = frameOf(L, x0, W, Math.min(Y(pc.p10[end]), item("p10").y), Y(Math.min(0, ...ends)));
  const high = frameOf(L, x0, W, Y(Math.max(...ends)), Math.max(Y(pc.p90[end]), item("p90").y + blockH));
  return [
    { key: "years", title: `${(spec.years || 10000).toLocaleString("en-US")} possible years.`, body: "One listing's profit for a year, simulated ten thousand times. Each line is one of them.", view: full, veil: null },
    { key: "core", title: "Most of them land here.", body: `The light is brightest where most years land. A typical year makes ${usd(mid.v)}.`, view: core, veil: "core", answer: "p50" },
    { key: "low", title: "One year in ten does worse.", body: `It ends below ${usd(lo.v)}. ${floor}`, view: low, veil: "low", answer: "p10" },
    { key: "high", title: "One year in ten does better.", body: `It ends above ${usd(hi.v)}. The ${upWider ? "upside spreads wider than the downside" : "downside spreads wider than the upside"}.`, view: high, veil: "high", answer: "p90" },
    { key: "range", title: "The range we plan for.", body: spec.forward || "Touch any line to see that year.", view: full, veil: null },
  ];
}

/**
 * Where the story is at progress s (0 to 5, one per beat). Each beat opens with a glide of the
 * camera, the veil and the answers' emphasis, all on the camera's own easing, then holds; each
 * answer's line draws with the scroll as its beat opens. Reversible: the same s always gives the
 * same picture.
 */
const LAND = 0.28;   // into its beat, an answer's figure starts to land: as the camera arrives, not while it travels

export function mcStoryState(L, s, beats = mcStory(L)) {
  const n = beats.length, c = Math.min(n - 1e-9, Math.max(0, s));
  const i = Math.floor(c), l = c - i;
  const glide = i === 0 ? 1 : ease(CAMERA.ease)(Math.min(1, l / 0.4));
  const prev = beats[Math.max(0, i - 1)], cur = beats[i];
  const mixv = (a, b) => a.map((v, k) => v + (b[k] - v) * glide);
  const camera = mixv(prev.view, cur.view);
  const veils = [];
  if (i > 0 && prev.veil && prev.veil !== cur.veil) veils.push({ kind: prev.veil, op: 1 - glide });
  if (cur.veil) veils.push({ kind: cur.veil, op: i > 0 && prev.veil === cur.veil ? 1 : glide });
  const qs = ["p90", "p50", "p10"];
  const emphOf = (b, off) => qs.map((q) => (b.answer && b.answer !== q ? off : 1));
  const emph = Object.fromEntries(mixv(emphOf(prev, FAN.aside), emphOf(cur, FAN.aside)).map((v, k) => [qs[k], v]));
  const words = Object.fromEntries(mixv(emphOf(prev, 0), emphOf(cur, 0)).map((v, k) => [qs[k], v]));
  const first = (q) => { const k = beats.findIndex((b) => b.answer === q); return k < 0 ? n - 1 : k; };
  const lineFrac = {}, labelOn = {};
  for (const q of qs) {
    lineFrac[q] = ease("ease-out")(Math.min(1, Math.max(0, (c - first(q)) / 0.45)));
    labelOn[q] = c >= first(q) + LAND;
  }
  const k = beats.findIndex((b) => b.key === "low");
  const lossOn = c >= (k < 0 ? n - 1 : k) + 0.3;
  return { beat: i, local: l, camera, zoom: L.W / camera[2], veils, emph, words, lineFrac, labelOn, lossOn, title: cur.title, body: cur.body, glide };
}

/**
 * The story as a film: each beat a fixed length of time, the first one the draw-in itself.
 * Returns the story progress and the clock for a moment of the film.
 */
export function mcStoryClock(L, beats = mcStory(L), { beatMs = 3400 } = {}) {
  const first = L.T.sweep[1] + ms("mc-settle-ms") * 0.6;
  const total = first + (beats.length - 1) * beatMs + VIDEO.motion.holdMs;
  const at = (t) => (t < first ? { s: t / first, at: t } : { s: Math.min(beats.length - 1e-9, 1 + (t - first) / beatMs), at: t });
  return { first, beatMs, total, at };
}

/**
 * The story film's sound: a turn as each beat's camera move begins, the reveal as each answer's
 * figure starts to land, and that figure's ticks.
 */
export function mcStoryCues(L, beats = mcStory(L), { beatMs = 3400 } = {}) {
  const clock = mcStoryClock(L, beats, { beatMs }), cues = [];
  beats.forEach((b, i) => {
    if (i === 0) return;
    const at = clock.first + (i - 1) * clock.beatMs;
    cues.push({ name: "turn", at: Math.round(at) });
    const k = L.answers.findIndex((a) => a.q === b.answer);
    if (k < 0) return;
    const start = at + LAND * clock.beatMs;
    cues.push({ name: "reveal", at: Math.round(start) });
    for (const c of numberSVG({ text: L.figText(L.answers[k].v), px: L.figPx, start }, 0).cues) if (c.name === "tick") cues.push(c);
  });
  return cues.sort((p, q) => p.at - q.at);
}

/** One frame of the story, for a film: progress s, the chart's clock, and when each figure began to land. */
export function mcStoryFrame(spec, t, { beatMs = 3400, touch = null } = {}) {
  const L = mcLayout(spec), beats = mcStory(L), clock = mcStoryClock(L, beats, { beatMs });
  const { s, at } = clock.at(t);
  const st = mcStoryState(L, s, beats);
  // a figure starts to land the moment its beat's label turns on
  const labelStart = {};
  for (const q of ["p90", "p50", "p10"]) {
    const k = beats.findIndex((b) => b.answer === q), on = (k < 0 ? beats.length - 1 : k) + LAND;
    labelStart[q] = st.labelOn[q] ? clock.first + (on - 1) * clock.beatMs : null;
  }
  const story = { lineFrac: st.lineFrac, labelStart, lossOp: st.lossOn ? 1 : 0, veils: st.veils, emph: st.emph, words: st.words, zoom: st.zoom };
  const m = mcMoment(L, at, { story, touch });
  return { svg: compose(L, m, st.camera), state: st, beats, clock, L };
}

// ---------------------------------------------------------------- the card to share

const MARK = '<path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z"/>';

/**
 * One clean card of the chart, for a deck or an email: the title, the finished chart with its
 * three answers, the label that never comes off, and Hubricon's quiet mark. 1200 × 630.
 */
export function mcCard(spec) {
  const W = 1200, H = 630, pad = 56, P = painter(spec.paint || "inline", spec.ground);
  const chart = mcChart({ ...spec, variant: "full", w: W - pad * 2, h: 440, font: 17, title: null, subtitle: null, source: null, id: (spec.id || "mc") + "-card" }, Infinity).svg
    .replace("<svg ", `<svg x="${pad}" y="128" width="${W - pad * 2}" height="440" `);
  const t = (x, y, s, size, weight, fill, anchor = "start") => `<text x="${x}" y="${y}" text-anchor="${anchor}" style="font-size:${size}px;font-weight:${weight};fill:${P(fill)}">${esc(s)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="font-family:${spec.paint === "css" ? "var(--font)" : "Inter Display, Inter, sans-serif"}">` +
    `<rect width="${W}" height="${H}" style="fill:${P("paper")}"/>` +
    t(pad, 84, spec.cardTitle || "Ten thousand simulated years of one listing's profit", 40, 600, "ink") +
    chart +
    t(pad, H - 34, spec.source || "Modeled from public data · Not a client · Not a result", 16, 400, "ink-3") +
    `<g transform="translate(${W - pad - 132} ${H - 58}) scale(0.5)" style="fill:${P("ink")}"><circle cx="32" cy="32" r="27" fill="none" style="stroke:${P("ink")}" stroke-width="5"/>${MARK}</g>` +
    t(W - pad, H - 34, "Hubricon", 20, 600, "ink", "end") +
    `</svg>`;
}

// ---------------------------------------------------------------- in a page

/** The parts of a mounted chart that move, by id. */
function parts(host, id, L) {
  const $ = (k) => host.querySelector(`#${id}-${k}`);
  const tk = L.tickRows.map((_, i) => $(`tk${i}`));
  return { svg: host.querySelector("svg"), front: $("front"), wave: $("wave"), grid: $("grid"), bright: $("bright"), rest: $("rest"), inlight: $("inlight"),
    tips: $("tips"), veil: $("veil"), pct: $("pct"), labels: $("labels"), touch: $("touch"), loss: $("loss"), ticks: $("ticks"), gutter: $("gutter"), screen: $("screen"), band: $("band"), tk };
}
function patch(L, el, m, view) {
  el.front.setAttribute("width", r1(Math.max(0, m.front)));
  el.wave.setAttribute("x", r1(m.front - m.waveW));
  show(el.wave, m.waveOp);
  show(el.grid, m.stage);
  show(el.bright, m.brightOp);
  show(el.rest, m.restOp);
  show(el.inlight, m.lightOp);
  show(el.tips, m.tipsOp);
  html(el.tips, m.tips);
  html(el.veil, m.veil);
  html(el.pct, m.pct);
  html(el.labels, m.labels);
  html(el.touch, m.touched);
  show(el.loss, m.lossOp);
  show(el.ticks, m.stage);
  if (view) {
    const sh = tickShift(L, view);
    el.svg.setAttribute("viewBox", view.map(r1).join(" "));
    el.ticks.setAttribute("transform", `translate(${r1(sh)} 0)`);
    show(el.gutter, gutterOp(L, sh));
    el.screen.setAttribute("transform", screenT(L, view));
    L.tickRows.forEach((t, i) => show(el.tk[i], tickOp(L, view, t.y)));
    show(el.band, bandOp(L, view));
  }
}

/** A part's drawing, replaced only when it changed: most frames of a held beat change nothing, and the page should do nothing. */
function html(node, s) {
  if (node._drawn !== s) { node.innerHTML = s; node._drawn = s; }
}

/** A layer at a strength; one at none is taken out of the drawing altogether, so nothing composites an empty mask. */
function show(node, op) {
  node.style.opacity = r3(op);
  node.style.display = op > 0.0005 ? "" : "none";
}

/** Where a pointer is, in the chart's own units. */
function toChart(svg, e) {
  const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return [p.x, p.y];
}

/**
 * Play a chart in a page: draw the still's structure once, play the draw-in, then let the reader
 * touch any year. It draws only while something moves, and sleeps otherwise. Returns a function
 * that stops it and leaves the finished still.
 */
export function playMC(host, spec, { now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame, touchable = true } = {}) {
  const L = mcLayout(spec);
  host.innerHTML = compose(L, mcMoment(L, 0));
  const el = parts(host, L.id, L);
  const t0 = now();
  let rid = 0, touch = null, busy = L.T.end, live = true;
  const frame = () => {
    rid = 0;
    const at = now() - t0;
    patch(L, el, mcMoment(L, at, { touch }));
    if (live && at < busy) rid = raf(frame);
  };
  const wake = (ms) => { if (!live) return; busy = Math.max(busy, now() - t0 + ms); if (!rid) rid = raf(frame); };
  rid = raf(frame);
  if (touchable && !L.mood && typeof window !== "undefined") {
    const move = (e) => {
      const [x, y] = toChart(el.svg, e);
      const k = x >= L.left && x <= L.right && y >= L.plotTop - L.f && y <= L.plotBottom ? mcNearestYear(L, x, y) : -1;
      const next = k < 0 ? null : touch && touch.year === k ? touch : { year: k, start: now() - t0 };
      if (next !== touch) { touch = next; wake(200); }
    };
    el.svg.addEventListener("pointermove", move);
    el.svg.addEventListener("pointerdown", move);
    el.svg.addEventListener("pointerleave", () => { if (touch) { touch = null; wake(0); } });
  }
  return () => { live = false; caf(rid); rid = 0; touch = null; patch(L, el, mcMoment(L, Infinity)); };
}

/**
 * Play the story in a page. `progress()` returns where the reader is, 0 to 5 (from their scroll).
 * The first beat plays by the clock as the chart arrives, so it is never blank for want of a
 * scroll. What is shown follows the reader closely but never cuts: a jump in the scroll (a link,
 * a fling) is a quick glide on screen, at most CATCH beats a second. It draws only while something
 * moves, and sleeps until the next scroll. `onBeat(beat, state)` lets the page change its words.
 * Returns a stop function.
 */
const CATCH = { tauMs: 140, beatsPerSecond: 2.5 };
export function playStory(host, spec, { progress, onBeat = () => {}, now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame,
  subscribe = (fn) => { addEventListener("scroll", fn, { passive: true }); addEventListener("resize", fn); return () => { removeEventListener("scroll", fn); removeEventListener("resize", fn); }; } } = {}) {
  const L = mcLayout(spec), beats = mcStory(L);
  host.innerHTML = compose(L, mcMoment(L, 0), beats[0].view);
  const el = parts(host, L.id, L);
  const t0 = now();
  const starts = { p90: null, p50: null, p10: null };
  let rid = 0, lastBeat = -1, touch = null, shown = 0, lastAt = 0, busy = L.T.settle[1] + 50, live = true;
  const frame = () => {
    rid = 0;
    const at = now() - t0, dt = Math.max(0, at - lastAt);
    lastAt = at;
    // the draw-in finishes on the clock before the story may move past its first beat
    const target = at < L.T.settle[1] ? Math.min(progress(), 0.999) : progress();
    const gap = target - shown;
    shown = Math.abs(gap) < 0.0005 ? target : shown + Math.sign(gap) * Math.min(Math.abs(gap) * (1 - Math.exp(-dt / CATCH.tauMs)), (CATCH.beatsPerSecond * dt) / 1000);
    const st = mcStoryState(L, shown, beats);
    for (const q of Object.keys(starts)) {
      if (st.labelOn[q] && starts[q] == null) { starts[q] = at; busy = Math.max(busy, at + ms("count-ms") + ms("mc-band-ms")); }
      if (!st.labelOn[q]) starts[q] = null;
    }
    if (st.beat !== lastBeat) { lastBeat = st.beat; onBeat(beats[st.beat], st); if (st.beat !== beats.length - 1) touch = null; }
    patch(L, el, mcMoment(L, at, { story: { lineFrac: st.lineFrac, labelStart: { ...starts }, lossOp: st.lossOn ? 1 : 0, veils: st.veils, emph: st.emph, words: st.words, zoom: st.zoom }, touch }), st.camera);
    if (live && (at < busy || shown !== target)) rid = raf(frame);
  };
  const wake = (ms = 0) => { if (!live) return; busy = Math.max(busy, now() - t0 + ms); if (!rid) rid = raf(frame); };
  rid = raf(frame);
  const unsubscribe = subscribe(() => wake(0));
  if (typeof window !== "undefined") {
    const move = (e) => {
      if (lastBeat !== beats.length - 1) return;            // touch belongs to the last beat, once the whole range is shown
      const [x, y] = toChart(el.svg, e);
      const k = x >= L.left && x <= L.right ? mcNearestYear(L, x, y) : -1;
      const next = k < 0 ? null : touch && touch.year === k ? touch : { year: k, start: now() - t0 };
      if (next !== touch) { touch = next; wake(200); }
    };
    el.svg.addEventListener("pointermove", move);
    el.svg.addEventListener("pointerdown", move);
    el.svg.addEventListener("pointerleave", () => { if (touch) { touch = null; wake(0); } });
  }
  return () => { live = false; caf(rid); rid = 0; unsubscribe?.(); };
}

// ---------------------------------------------------------------- helpers

const r1 = (v) => Math.round(v * 10) / 10;
const off = (op) => (op > 0.0005 ? "" : ";display:none");
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
