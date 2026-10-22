/* ============================================================================
   The line: how every Hubricon chart draws a series, labels it, points at what
   matters, and moves.

   One pure function, lineChart(spec, at), returns the chart as an SVG string at
   any exact moment `at` (milliseconds into its draw-in; Infinity is the finished
   still frame). The site plays it on scroll and the films render it frame by
   frame, so a viewer and a reader see the same picture at the same moment.

   What it fixes, rule by rule (the "generated" look, taken apart):
   1. Honest curves. A quantity that jumps (a fee card) is drawn as exact steps.
      A quantity that changes continuously between samples is drawn as a monotone
      curve, which passes through every real point and never invents a peak or a
      dip between them. Never cardinal or natural splines: they overshoot.
   2. Four voices, never equal. The finding in blue; the series that matters in
      ink; context quiet in a pale neutral, solid; the grid a hairline. A dashed
      line means one thing only: not real yet (a forecast, an estimate).
   3. Labels on the lines, not in a key. Every series is named at its end.
   4. No text ever crosses a line. Every label is placed by a solver that tries
      positions around its anchor and takes the first clear one, and carries a
      halo in the ground colour.
   5. The finding is annotated: a short headline in its own colour, one plain
      line of explanation, a hairline leader to the exact point.
   6. Axes that whisper: hairline grid, labels in the margin, no axis line on the
      value axis, no tick marks. The unit sits on the last label.
   7. Story order in motion: context first, then the series that matters draws
      in with a tip that carries its real value, then a silence, then the finding.
      Numbers shown while drawing are always real data points, never in-betweens.
   8. No time scales (the founder, 2026-10-19): growth is shown by its numbers,
      never against a calendar. The horizontal axis is a numerical driver
      (weight, price, units) or it carries no labels at all; dates, weeks and
      months never label an axis or name a line.

   Taken to 11 (HUBRICON_SPEC.md, the scoreboard's ladder):
   7  A heartbeat. Touch reads the line where the finger is, only at real
      points (a step reads anywhere on its tread, since a fee card is defined
      for every weight). The reading sits in the clear corner the label solver
      finds, never under the finger.
   8  It tells you what you did not ask: the gap to the other line at that
      point, or, on a staircase, where the next step comes and what it costs.
   9  It is yours: pin a point, move, and the reading says how much changed
      since the pin. Arrow keys walk the real points; Enter pins.
   10 It meets the scary moment first: if the line ever falls, its worst fall
      is marked and named, and whether it came back.
   11 shareCard: one clean 1200 × 630 card of any chart, with its label and
      the mark, for someone else's deck.

   No imports beyond the tokens; plain strings out. Works in a browser, in Node
   and in the video renderer.
   ============================================================================ */

import { css, ms, ease, NIGHT, VIDEO } from "./tokens.mjs";
import { textWidth } from "./inter.mjs";

// ---------------------------------------------------------------- paint
// "css": var(--token), so a night section re-themes the chart with no second style.
// "inline": the token's value, for renderers without the stylesheet (film frames).

const NIGHT_OF = Object.fromEntries(NIGHT);
export function painter(mode = "css", ground = "day") {
  return (name) => (mode === "css" ? `var(--${name})` : css(ground === "night" ? NIGHT_OF[name] || name : name));
}

// ---------------------------------------------------------------- text metrics
// Measured from Inter's own files, in assets/inter.mjs; re-exported for older callers.
export { textWidth } from "./inter.mjs";

// ---------------------------------------------------------------- scales
export function linear(d0, d1, r0, r1) {
  const f = (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
  f.invert = (p) => d0 + ((p - r0) / (r1 - r0 || 1)) * (d1 - d0);
  return f;
}

export function niceTicks(lo, hi, target = 4) {
  const span = hi - lo || 1;
  const mag = 10 ** Math.floor(Math.log10(span / target));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => span / s <= target + 0.5) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

// ---------------------------------------------------------------- geometry
// Every shape is a list of cubic segments {p0, c1, c2, p1, line, v}: a straight run is
// a cubic with its controls on the line. `v` is the real data value the segment
// starts from, which is what a moving tip may show.

const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const straight = (a, b, v) => ({ p0: a, c1: lerp(a, b, 1 / 3), c2: lerp(a, b, 2 / 3), p1: b, line: true, v });

/**
 * pts: [[x, y], …] in screen units; vals: the data value at each point.
 * kind "step": flat to the next x, then up or down to its value (a fee card, a band).
 * kind "monotone": through every point, never past one (Fritsch–Carlson, as d3's curveMonotoneX).
 * kind "linear": straight runs, for the rare series that really is straight between samples.
 */
export function shape(pts, kind = "monotone", vals = pts.map((p) => p[1])) {
  const n = pts.length, out = [];
  if (n < 2) return out;
  if (kind === "linear") {
    for (let i = 0; i < n - 1; i++) out.push(straight(pts[i], pts[i + 1], vals[i]));
    return out;
  }
  if (kind === "step") {
    for (let i = 0; i < n - 1; i++) {
      const a = pts[i], b = pts[i + 1], corner = [b[0], a[1]];
      if (corner[0] !== a[0]) out.push(straight(a, corner, vals[i]));
      if (b[1] !== a[1]) out.push({ ...straight(corner, b, vals[i]), riser: true });
    }
    return out;
  }
  // monotone
  const sign = (x) => (x < 0 ? -1 : 1);
  const t = new Array(n).fill(0);
  const h = (i) => pts[i + 1][0] - pts[i][0];
  const s = (i) => (pts[i + 1][1] - pts[i][1]) / (h(i) || 1e-9);
  for (let i = 1; i < n - 1; i++) {
    const s0 = s(i - 1), s1 = s(i), h0 = h(i - 1), h1 = h(i);
    const p = (s0 * h1 + s1 * h0) / (h0 + h1);
    t[i] = (sign(s0) + sign(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)) || 0;
  }
  t[0] = n > 2 ? (3 * s(0) - t[1]) / 2 : s(0);
  t[n - 1] = n > 2 ? (3 * s(n - 2) - t[n - 2]) / 2 : s(0);
  // keep the end tangents from overshooting too
  if (Math.sign(t[0]) !== Math.sign(s(0))) t[0] = 0;
  if (Math.sign(t[n - 1]) !== Math.sign(s(n - 2))) t[n - 1] = 0;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], dx = (x1 - x0) / 3;
    out.push({ p0: pts[i], c1: [x0 + dx, y0 + dx * t[i]], c2: [x1 - dx, y1 - dx * t[i + 1]], p1: pts[i + 1], line: false, v: vals[i] });
  }
  return out;
}

const cubicAt = (s, u) => {
  const m = 1 - u, a = m * m * m, b = 3 * m * m * u, c = 3 * m * u * u, d = u * u * u;
  return [a * s.p0[0] + b * s.c1[0] + c * s.c2[0] + d * s.p1[0], a * s.p0[1] + b * s.c1[1] + c * s.c2[1] + d * s.p1[1]];
};
const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
const SAMPLES = 32;
function arc(s) {
  if (s.line) return { len: dist(s.p0, s.p1), cum: null };
  const cum = [0];
  let prev = s.p0;
  for (let i = 1; i <= SAMPLES; i++) { const p = cubicAt(s, i / SAMPLES); cum.push(cum[i - 1] + dist(prev, p)); prev = p; }
  return { len: cum[SAMPLES], cum };
}
/** Split a cubic at parameter u (de Casteljau) and keep the first part. */
function head(s, u) {
  if (s.line) return { ...s, p1: lerp(s.p0, s.p1, u), c1: lerp(s.p0, s.p1, u / 3), c2: lerp(s.p0, s.p1, (2 * u) / 3) };
  const a = lerp(s.p0, s.c1, u), b = lerp(s.c1, s.c2, u), c = lerp(s.c2, s.p1, u);
  const d = lerp(a, b, u), e = lerp(b, c, u), f = lerp(d, e, u);
  return { ...s, c1: a, c2: d, p1: f };
}

/** The first `frac` (0..1) of a shape's length, its tip point and the segment the tip is on. */
export function partial(segs, frac) {
  if (!segs.length) return { segs: [], tip: null, seg: null };
  const arcs = segs.map(arc), total = arcs.reduce((a, b) => a + b.len, 0);
  if (frac >= 1) return { segs, tip: segs[segs.length - 1].p1, seg: segs[segs.length - 1], done: true, total };
  let left = Math.max(0, frac) * total;
  const out = [];
  for (let i = 0; i < segs.length; i++) {
    const { len, cum } = arcs[i];
    if (left >= len) { out.push(segs[i]); left -= len; continue; }
    let u;
    if (!cum) u = len ? left / len : 0;
    else { let k = 1; while (k < SAMPLES && cum[k] < left) k++; u = (k - 1 + (left - cum[k - 1]) / (cum[k] - cum[k - 1] || 1)) / SAMPLES; }
    const cut = head(segs[i], u);
    out.push(cut);
    return { segs: out, tip: cut.p1, seg: segs[i], total };
  }
  return { segs, tip: segs[segs.length - 1].p1, seg: segs[segs.length - 1], done: true, total };
}

const r1 = (v) => Math.round(v * 10) / 10;
/** SVG path data for a list of segments. */
export function pathD(segs) {
  if (!segs.length) return "";
  let d = `M${r1(segs[0].p0[0])} ${r1(segs[0].p0[1])}`;
  for (const s of segs) d += s.line ? ` L${r1(s.p1[0])} ${r1(s.p1[1])}` : ` C${r1(s.c1[0])} ${r1(s.c1[1])} ${r1(s.c2[0])} ${r1(s.c2[1])} ${r1(s.p1[0])} ${r1(s.p1[1])}`;
  return d;
}

/** Points along a shape every `step` px, for the label solver to avoid. */
function samplePoints(segs, step) {
  const out = [];
  for (const s of segs) {
    const n = Math.max(2, Math.ceil(arc(s).len / step));
    for (let i = 0; i <= n; i++) out.push(s.line ? lerp(s.p0, s.p1, i / n) : cubicAt(s, i / n));
  }
  return out;
}

// ---------------------------------------------------------------- placement
const overlap = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));

/** How far a box is from a point (0 when the point is inside it). */
const reach = (c, [x, y]) => Math.hypot(Math.max(c.x - x, 0, x - (c.x + c.w)), Math.max(c.y - y, 0, y - (c.y + c.h)));

/**
 * The best box for a label: inside `bounds`, clear of everything in `taken`, and as
 * close to its anchor as that allows. Earlier candidates are preferred when equal.
 * With `open`, the whole plot is searched too, so a note crowded out of its
 * neighbourhood moves to clear space and takes a leader back to its point.
 */
export function place(candidates, taken, bounds, anchor = null, open = 0, leaderStep = 0, margin = 0) {
  const all = [...candidates];
  if (open && anchor && candidates.length) {
    const { w, h } = candidates[0];
    for (let y = bounds.y; y + h <= bounds.y + bounds.h; y += open) {
      for (let x = bounds.x; x + w <= bounds.x + bounds.w; x += open) all.push({ x, y, w, h, far: true });
    }
  }
  let best = null, bestCost = Infinity;
  all.forEach((c, i) => {
    const out = (Math.max(0, bounds.x - c.x) + Math.max(0, c.x + c.w - (bounds.x + bounds.w)) + Math.max(0, bounds.y - c.y) + Math.max(0, c.y + c.h - (bounds.y + bounds.h))) * 1000;
    const grown = margin ? { x: c.x - margin, y: c.y - margin * 0.5, w: c.w + margin * 2, h: c.h + margin } : c;
    const hit = taken.reduce((a, t) => a + overlap(grown, t) * ((t.k ?? 1) >= 3 ? 1 : t.k ?? 1) * ((t.k ?? 1) >= 3 || overlap(c, t) > 0 ? 1 : 0), 0);
    const near = anchor ? reach(c, anchor) : 0;
    // a leader that would cross a label or a line costs as much as a label sitting on one
    let cross = 0;
    if (leaderStep && anchor && near > leaderStep * 3) {
      const nx = Math.max(c.x, Math.min(c.x + c.w, anchor[0])), ny = Math.max(c.y, Math.min(c.y + c.h, anchor[1]));
      const len = Math.hypot(anchor[0] - nx, anchor[1] - ny);
      for (let k = leaderStep; k < len - leaderStep * 2; k += leaderStep) {
        const px = nx + ((anchor[0] - nx) / len) * k, py = ny + ((anchor[1] - ny) / len) * k;
        if (taken.some((t) => (t.k ?? 1) >= 1 && px >= t.x && px <= t.x + t.w && py >= t.y && py <= t.y + t.h)) cross++;
      }
    }
    const cost = out + hit * 10 + cross * 400 + near * 0.6 + (c.far ? 40 : i);
    if (cost < bestCost) { bestCost = cost; best = c; }
  });
  return best;
}

// ---------------------------------------------------------------- the timeline
// Story order, from the tokens. `at` in ms; each part reports its progress 0..1.

export function timeline(spec) {
  const draw = ms("mc-draw-ms"), fade = ms("mc-band-ms"), beat = ms("stagger");
  const hasContext = spec.series.some((s) => s.role === "context" || s.role === "ghost");
  const t = {};
  t.stage = [0, fade];
  t.context = hasContext ? [fade * 0.5, fade * 0.5 + draw * 0.5] : [0, 0];
  t.focus = [hasContext ? t.context[1] : fade, 0];      // the grid is in place before the line starts
  t.focus[1] = t.focus[0] + draw;
  t.names = [t.focus[1], t.focus[1] + fade];
  t.reveal = t.focus[1] + VIDEO.motion.silenceMs;            // the silence, then the finding
  t.finding = [t.reveal, t.reveal + fade];
  t.notes = [t.finding[1], t.finding[1] + fade];
  t.end = t.notes[1] + beat * Math.max(0, (spec.notes || []).length - 1);
  return t;
}
const progress = (at, [a, b]) => (b <= a ? (at >= a ? 1 : 0) : Math.min(1, Math.max(0, (at - a) / (b - a))));

// ---------------------------------------------------------------- the chart

/**
 * spec: {
 *   w, h, font (13 on the site, 40 in a film), paint ("css" | "inline"), ground ("day" | "night"),
 *   title?, titlePx?, subtitle?, source?,           the takeaway, the units, the source and labels
 *   x: { domain: [a, b], ticks?: [...], format(v, last) },   no ticks: no labels on the horizontal axis
 *   y: { domain?: [a, b], ticks?: [...], format(v) },
 *   series: [{ id, points: [[x, y], …], kind, role: "focus" | "context" | "ghost" | "leak", name, tip(v)? }],
 *   risers: [{ x, y0, y1 }],                        the finding as a vertical step, in blue
 *   dots: [{ x, y, hollow, label, emphasis }],
 *   bands: [{ x0, x1, label }],
 *   notes: [{ x, y, title, body }],                 the annotation: headline, one line, a leader to (x, y)
 *   id?,                                            prefix for the parts a page patches (default "ln")
 *   x.read?(v), y.read?(v), x.snap?,                how touch says a place and a value; a step's reading resolution
 *   series[].short?, compare?(focus, other), fall?  the reading's short names; the gap line; false: no worst fall
 * }
 * opts.touch: { x, pin? } in data units, already snapped (lineSnap): the reading drawn into this frame.
 * Returns { svg, cues, duration, geom }. cues: [{ name, at }] for the film's sound; geom is what
 * touch needs (lineSnap, lineTouch, playLine).
 */
export function lineChart(spec, at = Infinity, opts = {}) {
  // a chart too crowded to hold its reading in a clear corner gets a band for it above the plot
  const first = drawLine(spec, at, opts, 0);
  return first.geom.clear ? first : drawLine(spec, at, opts, first.geom.readout.h + (spec.font || 13) * 0.5);
}

function drawLine(spec, at, { touch = null } = {}, band = 0) {
  const P = painter(spec.paint, spec.ground);
  const f = spec.font || 13, u = f / 13;                    // every weight and gap scales with the type
  const lw = (name) => parseFloat(css(name)) * u;
  const T = timeline(spec);
  const ez = ease("ease-out");
  const halo = (w = 0.34 * f) => `paint-order:stroke;stroke:${P("paper")};stroke-width:${r1(w)}px;stroke-linejoin:round`;
  const txt = (x, y, s, { size = f, weight = 400, fill = "ink-3", anchor = "start", tab = false, op = 1, haloed = false, base = "alphabetic" } = {}) =>
    `<text x="${r1(x)}" y="${r1(y)}" text-anchor="${anchor}" dominant-baseline="${base}" style="font-size:${r1(size)}px;font-weight:${weight};fill:${P(fill)};${tab ? "font-variant-numeric:tabular-nums;" : ""}${op < 1 ? `opacity:${r1(op * 100) / 100};` : ""}${haloed ? halo() : ""}">${esc(s)}</text>`;

  // ---- layout, derived from the content, not fixed margins
  const W = spec.w, H = spec.h, pad = 8 * u;
  let top = pad, bottom = H - pad;
  let head = "";
  // words above and below the chart wrap to its width: on a phone the title and the label are never cut
  const width = W - 2 * pad;
  if (spec.title) {
    const ts = spec.titlePx || f * 1.55;
    for (const line of wrap(spec.title, ts, 600, width)) { head += txt(pad, top + ts * 0.86, line, { size: ts, weight: 600, fill: "ink" }); top += ts * 1.18; }
    top += ts * 0.07;
  }
  if (spec.subtitle) { for (const line of wrap(spec.subtitle, f, 400, width)) { head += txt(pad, top + f * 0.9, line, { fill: "ink-3" }); top += f * 1.35; } top += f * 0.25; }
  if (spec.title || spec.subtitle) top += f * 1.1;
  let foot = "";
  if (spec.source) {
    const lines = wrap(spec.source, f * 0.85, 400, width, " · ");
    lines.forEach((line, i) => { foot += txt(pad, bottom - f * 0.15 - (lines.length - 1 - i) * f * 1.2, line, { size: f * 0.85, fill: "ink-3" }); });
    bottom -= f * 1.7 + (lines.length - 1) * f * 1.2;
  }

  const yVals = spec.series.flatMap((s) => s.points.map((p) => p[1])).concat((spec.risers || []).flatMap((r) => [r.y0, r.y1]));
  const yDom = spec.y.domain || [Math.min(...yVals), Math.max(...yVals)];
  const yTicks = spec.y.ticks || niceTicks(yDom[0], yDom[1], 4);
  // a line never lies on the axis: the scale reaches down to the gridline below the lowest value
  if (!spec.y.ticks && !spec.y.domain && yTicks.length > 1 && yDom[0] < yTicks[0] - 1e-9) yTicks.unshift(Math.round((yTicks[0] - (yTicks[1] - yTicks[0])) * 1e6) / 1e6);
  const y0 = Math.min(yDom[0], yTicks[0]), y1 = Math.max(yDom[1], yTicks[yTicks.length - 1]);
  const yLabW = Math.max(...yTicks.map((v) => textWidth(spec.y.format(v), f, 400, true)));
  const left = pad + yLabW + 12 * u;
  const named = spec.series.filter((s) => s.name);
  const nameW = Math.max(0, ...named.map((s) => textWidth(s.name, f, s.role === "focus" ? 600 : 400)));
  const inlineNames = nameW + 14 * u > W * 0.25;            // a narrow chart keeps its width for the data
  const right = W - pad - (nameW && !inlineNames ? nameW + 14 * u : 0);
  const hasX = (spec.x.ticks || []).length > 0;
  const plotBottom = bottom - (hasX ? f * 2.1 : f * 0.6);
  const plotTop = top + f * 0.6 + band;
  const X = linear(spec.x.domain[0], spec.x.domain[1], left, right);
  const Y = linear(y0, y1, plotBottom, plotTop);
  const bounds = { x: left, y: plotTop - f, w: W - pad - left, h: plotBottom - plotTop + f };

  const stageOp = ez(progress(at, T.stage));
  let back = "", grid = "", lines = "", leaders = "", marks = "", names = "", notes = "", tipLayer = "";
  const taken = [];                                           // boxes the label solver must avoid

  // ---- bands, behind everything
  for (const b of spec.bands || []) {
    const bx0 = X(b.x0), bx1 = X(b.x1), op = ez(progress(at, T.finding));
    back += `<rect x="${r1(bx0)}" y="${r1(plotTop)}" width="${r1(bx1 - bx0)}" height="${r1(plotBottom - plotTop)}" style="fill:${P("blue-wash")};opacity:${r1(op * 100) / 100}"/>`;
    if (b.label) {
      const lw_ = textWidth(b.label, f * 0.92, 600);
      const lx = (bx0 + bx1) / 2;
      names += txt(lx, plotTop + f * 0.9, b.label, { size: f * 0.92, weight: 600, fill: "blue", anchor: "middle", op, haloed: true });
      taken.push({ x: lx - lw_ / 2, y: plotTop, w: lw_, h: f * 1.2, k: 3 });
    }
  }

  // ---- the grid and axes: hairlines, labels in the margin, no ticks
  for (const v of yTicks) {
    const y = Y(v), zero = v === 0;
    grid += `<line x1="${r1(left)}" x2="${r1(right)}" y1="${r1(y)}" y2="${r1(y)}" style="stroke:${P(zero ? "rule-2" : "rule")};stroke-width:${r1(lw("line-hair") * (zero ? 1.5 : 1))}px;shape-rendering:crispEdges;opacity:${stageOp}"/>`;
    grid += txt(left - 12 * u, y + f * 0.34, spec.y.format(v), { anchor: "end", tab: true, op: stageOp });
  }
  grid += `<line x1="${r1(left)}" x2="${r1(right)}" y1="${r1(plotBottom)}" y2="${r1(plotBottom)}" style="stroke:${P("rule-2")};stroke-width:${r1(lw("line-hair"))}px;shape-rendering:crispEdges;opacity:${stageOp}"/>`;
  const xt = spec.x.ticks || [];
  const xl = xt.map((v, i) => {
    const last = i === xt.length - 1, s = spec.x.format(v, last), w = textWidth(s, f, 400, true);
    const anchor = i === 0 && X(v) - left < f ? "start" : last && right - X(v) < f * 2 ? "end" : "middle";
    const x0 = anchor === "start" ? X(v) : anchor === "end" ? X(v) - w : X(v) - w / 2;
    return { v, s, anchor, x0, x1: x0 + w, keep: true };
  });
  const room = f * 0.8;
  for (let i = xl.length - 2; i >= 0; i--) {                  // walk back from the unit-bearing last label
    const next = xl.slice(i + 1).find((l) => l.keep);
    if (next && xl[i].x1 + room > next.x0) xl[i].keep = false;
  }
  for (const l of xl) if (l.keep) grid += txt(l.anchor === "start" ? l.x0 : l.anchor === "end" ? l.x1 : (l.x0 + l.x1) / 2, plotBottom + f * 1.55, l.s, { anchor: l.anchor, tab: true, op: stageOp });

  // ---- the series, in story order
  const roleStyle = {
    ghost: { stroke: "ink-4", width: lw("line-hair") * 1.5, dash: `${r1(5 * u)} ${r1(4 * u)}`, op: 1 },
    context: { stroke: "ink-4", width: lw("line-hair") * 1.5, op: 1 },
    focus: { stroke: "ink", width: lw("line-pct") * 1.15, op: 1 },
    leak: { stroke: "blue", width: lw("line-leak"), op: 1 },
  };
  const cues = [];
  const ends = [];
  for (const s of spec.series) {
    const st = roleStyle[s.role] || roleStyle.focus;
    const screen = s.points.map(([x, y]) => [X(x), Y(y)]);
    const segs = shape(screen, s.kind || "monotone", s.points.map((p) => p[1]));
    const window = s.role === "focus" || s.role === "leak" ? T.focus : T.context;
    const p = progress(at, window), frac = s.role === "focus" ? ez(p) : ez(p);
    const part = partial(segs, frac);
    const cap = s.kind === "step" ? "butt" : "round", join = s.kind === "step" ? "miter" : "round";
    if (part.segs.length) {
      lines += `<path d="${pathD(part.segs)}" style="fill:none;stroke:${P(st.stroke)};stroke-width:${r1(st.width)}px;stroke-linecap:${cap};stroke-linejoin:${join};${st.dash ? `stroke-dasharray:${st.dash};` : ""}"/>`;
    }
    for (const pt of samplePoints(segs, 6 * u)) taken.push({ x: pt[0] - 3 * u, y: pt[1] - 3 * u, w: 6 * u, h: 6 * u });
    // the tip while drawing: a dot, and the real value it has passed
    if (s.role === "focus" && p > 0 && p < 1 && part.tip) {
      const [tx, ty] = part.tip;
      tipLayer += `<circle cx="${r1(tx)}" cy="${r1(ty)}" r="${r1(3.2 * u)}" style="fill:${P("ink")}"/>`;
      if (s.tip) tipLayer += txt(tx + 7 * u, ty - 9 * u, s.tip(part.seg.v), { weight: 600, fill: "ink", tab: true, haloed: true });
    }
    // a tick for each step the tip climbs, so the sound lands on it
    if (s.role === "focus" && s.kind === "step") {
      const arcs = segs.map(arc), total = arcs.reduce((a, b) => a + b.len, 0);
      let acc = 0;
      segs.forEach((g, i) => {
        if (g.riser) {
          const fr = (acc + arcs[i].len) / total;
          // invert the ease-out to find when the tip reaches the top of this riser
          let lo = 0, hi = 1;
          for (let k = 0; k < 30; k++) { const mid = (lo + hi) / 2; if (ez(mid) < fr) lo = mid; else hi = mid; }
          cues.push({ name: "tick", at: Math.round(window[0] + lo * (window[1] - window[0])) });
        }
        acc += arcs[i].len;
      });
    }
    if (s.name) ends.push({ s, x: screen[screen.length - 1][0], y: screen[screen.length - 1][1] });
  }

  // ---- names at the ends of the lines, spread so they never touch
  const nameOp0 = ez(progress(at, T.names));
  if (inlineNames) {
    // the line that ends highest is named above itself, the one that ends lowest below,
    // so a name is never on the far side of another line
    const byEnd = [...ends].sort((p, q) => p.y - q.y);
    for (const e of [...ends].sort((p, q) => (p.s.role === "focus" ? -1 : 1))) {
      const focus = e.s.role === "focus", wgt = focus ? 600 : 400, w = textWidth(e.s.name, f, wgt), h = f * 1.2, g = 6 * u;
      const below = byEnd.length > 1 && byEnd.indexOf(e) === byEnd.length - 1;
      // flush right at the end of the line, sliding left along it until clear
      const cands = [];
      for (let k = 0; k <= 8; k++) cands.push({ x: e.x - w - k * f * 1.2, y: below ? e.y + g : e.y - g - h, w, h });
      const c = place(cands, taken, { x: left, y: plotTop - f, w: W - pad - left, h: plotBottom - plotTop + f }, null, 0, 0, 5 * u);
      taken.push({ ...c, k: 3 });
      const op = focus ? nameOp0 : ez(progress(at, [T.context[1], T.context[1] + ms("mc-band-ms")]));
      names += txt(c.x + w, c.y + f * 0.92, e.s.name, { weight: wgt, fill: focus ? "ink" : "ink-3", anchor: "end", op, haloed: true });
    }
    ends.length = 0;
  }
  const gap = f * 1.35;
  const sorted = [...ends].sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i++) if (sorted[i].y - sorted[i - 1].y < gap) sorted[i].y = sorted[i - 1].y + gap;
  const nameOp = ez(progress(at, T.names));
  for (const e of sorted) {
    const focus = e.s.role === "focus";
    const op = focus ? nameOp : ez(progress(at, [T.context[1], T.context[1] + ms("mc-band-ms")]));
    names += txt(e.x + 10 * u, e.y + f * 0.34, e.s.name, { weight: focus ? 600 : 400, fill: focus ? "ink" : "ink-3", op });
    taken.push({ x: e.x + 10 * u, y: e.y - f * 0.7, w: textWidth(e.s.name, f, focus ? 600 : 400), h: f * 1.3, k: 3 });
  }

  // ---- the finding: risers in blue, drawn after the silence
  const fp = progress(at, T.finding), fop = ez(fp);
  if ((spec.risers || []).length || (spec.notes || []).length) cues.push({ name: "reveal", at: Math.round(T.reveal) });
  for (const r of spec.risers || []) {
    const x = X(r.x), ya = Y(r.y0), yb = ya + (Y(r.y1) - ya) * ez(fp);
    if (fp > 0) marks += `<line x1="${r1(x)}" x2="${r1(x)}" y1="${r1(ya)}" y2="${r1(yb)}" style="stroke:${P("blue")};stroke-width:${r1(lw("line-leak") * 1.35)}px;stroke-linecap:butt"/>`;
    taken.push({ x: x - 4 * u, y: Math.min(Y(r.y0), Y(r.y1)), w: 8 * u, h: Math.abs(Y(r.y1) - Y(r.y0)) });
  }
  // ---- dots, and their labels placed by the solver
  const dr = 4.6 * u;
  for (const d of spec.dots || []) {
    const x = X(d.x), y = Y(d.y);
    if (fp > 0) {
      marks += d.hollow
        ? `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(dr)}" style="fill:${P("paper")};stroke:${P("ink")};stroke-width:${r1(lw("line-step"))}px;opacity:${r1(fop * 100) / 100}"/>`
        : `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(dr)}" style="fill:${P("ink")};opacity:${r1(fop * 100) / 100}"/>`;
    }
    taken.push({ x: x - dr, y: y - dr, w: dr * 2, h: dr * 2, k: 3 });
  }
  // ---- notes first: the finding gets the best place; the dot labels work around it
  (spec.notes || []).forEach((n, i) => {
    const start = T.notes[0] + ms("stagger") * i;
    const op = ez(progress(at, [start, start + ms("mc-band-ms")]));
    const ax = X(n.x), ay = Y(n.y);
    const tw = Math.max(textWidth(n.title, f * 1.08, 600), n.body ? textWidth(n.body, f, 400) : 0);
    const th = f * 1.08 * 1.25 + (n.body ? f * 1.4 : 0);
    const g = 12 * u;                                            // close enough to need no leader
    const c = place([
      { x: ax - g - tw, y: ay - th / 2, w: tw, h: th },          // left of the point
      { x: ax + g, y: ay - th / 2, w: tw, h: th },               // right
      { x: ax - g - tw, y: ay - g - th, w: tw, h: th },          // above left
      { x: ax + g, y: ay - g - th, w: tw, h: th },               // above right
      { x: ax - g - tw, y: ay + g, w: tw, h: th },               // below left
      { x: ax + g, y: ay + g, w: tw, h: th },                    // below right
    ], taken, bounds, [ax, ay], f * 1.1, 6 * u, 6 * u);
    taken.push({ ...c, k: 3 });
    // set flush to the side that faces the point
    const away = reach(c, [ax, ay]);
    if (op <= 0 && away <= 18 * u) return;
    const faceRight = c.x + c.w <= ax + 1;
    const anchor = faceRight ? "end" : "start";
    const tx = faceRight ? c.x + tw : c.x;
    if (op > 0) notes += txt(tx, c.y + f * 1.08 * 0.92, n.title, { size: f * 1.08, weight: 600, fill: n.tone || "blue", anchor, op, haloed: true });
    if (op > 0 && n.body) notes += txt(tx, c.y + f * 1.08 * 1.25 + f * 1.02, n.body, { fill: "ink-3", anchor, op, haloed: true });
    // the leader, only when the note had to move away: from its nearest edge to the point, stopping short
    if (away > 18 * u) {
      const nx = Math.max(c.x, Math.min(c.x + c.w, ax)), ny = Math.max(c.y, Math.min(c.y + c.h, ay));
      const len = Math.hypot(ax - nx, ay - ny), dx = (ax - nx) / len, dy = (ay - ny) / len;
      const sx = nx + dx * 6 * u, sy = ny + dy * 6 * u, ex = ax - dx * 7 * u, ey = ay - dy * 7 * u;
      for (let k = 0; k <= len; k += 6 * u) taken.push({ x: nx + dx * k - 2 * u, y: ny + dy * k - 2 * u, w: 4 * u, h: 4 * u, k: 0.15 });
      if (op <= 0) return;
      leaders += `<line x1="${r1(sx)}" y1="${r1(sy)}" x2="${r1(ex)}" y2="${r1(ey)}" style="stroke:${P("ink-3")};stroke-width:${r1(lw("line-hair"))}px;opacity:${r1(op * 100) / 100}"/>`;
      leaders += `<circle cx="${r1(ax)}" cy="${r1(ay)}" r="${r1(2.2 * u)}" style="fill:${P("ink-3")};opacity:${r1(op * 100) / 100}"/>`;
    }
  });

  // ---- the worst fall, named before anyone asks (rung 10): from the line's running peak to the lowest point after it
  const focusS = spec.series.find((q) => q.role === "focus") || spec.series[0];
  const fall = spec.fall === false ? null : worstFall(focusS.points, (y1 - y0) * 0.02);
  if (fall) {
    const op = ez(progress(at, T.notes));
    const [px, pv] = focusS.points[fall.i], [qx, qv] = focusS.points[fall.j];
    const xa = X(px), xb = X(qx), ya = Y(pv), yb = Y(qv), cap = 4 * u;
    const title = `Worst fall ${signed(readOf(spec, focusS), qv - pv)}`, body = fall.back ? "then it came back" : "not back yet";
    const tw = Math.max(textWidth(title, f, 600), textWidth(body, f, 400)), th = f * 2.5, g = 10 * u;
    // the bracket is in the way of its own label
    for (let x = xa; x <= xb; x += 6 * u) taken.push({ x: x - 2 * u, y: ya - 2 * u, w: 4 * u, h: 4 * u, k: 3 });
    for (let y = ya; y <= yb; y += 6 * u) taken.push({ x: xb - 2 * u, y: y - 2 * u, w: 4 * u, h: 4 * u, k: 3 });
    const c = place([
      { x: xb + g, y: (ya + yb) / 2 - th / 2, w: tw, h: th }, { x: (xa + xb) / 2 - tw / 2, y: ya - g * 0.6 - th, w: tw, h: th },
      { x: xb - tw, y: ya - g * 0.6 - th, w: tw, h: th }, { x: xb - g - tw, y: (ya + yb) / 2 - th / 2, w: tw, h: th },
      { x: xb + g, y: yb + g, w: tw, h: th }, { x: xb - g - tw, y: yb + g, w: tw, h: th },
    ], taken, bounds, [xb, (ya + yb) / 2], f * 1.1, 6 * u, 5 * u);
    taken.push({ ...c, k: 3 });
    if (op > 0) {
      const o = `opacity:${r1(op * 100) / 100}`, hair = `stroke:${P("ink-3")};stroke-width:${r1(lw("line-hair"))}px`;
      marks += `<line x1="${r1(xa)}" x2="${r1(xb)}" y1="${r1(ya)}" y2="${r1(ya)}" style="${hair};${o}"/>` +
        `<line x1="${r1(xb)}" x2="${r1(xb)}" y1="${r1(ya)}" y2="${r1(yb)}" style="${hair};${o}"/>` +
        `<line x1="${r1(xb - cap)}" x2="${r1(xb + cap)}" y1="${r1(yb)}" y2="${r1(yb)}" style="${hair};${o}"/>`;
      notes += txt(c.x, c.y + f * 0.92, title, { weight: 600, fill: "ink", op, haloed: true }) +
        txt(c.x, c.y + f * 2.2, body, { fill: "ink-3", op, haloed: true });
    }
  }

  for (const d of spec.dots || []) {
    if (!d.label) continue;
    const x = X(d.x), y = Y(d.y), wgt = d.emphasis ? 600 : 400;
    const w = textWidth(d.label, f, wgt), h = f * 1.2, g = 9 * u;
    const c = place([
      { x: x + g, y: y + g * 0.6, w, h }, { x: x + g, y: y - g * 0.6 - h, w, h },
      { x: x - g - w, y: y + g * 0.6, w, h }, { x: x - g - w, y: y - g * 0.6 - h, w, h },
      { x: x - w / 2, y: y + g * 1.2, w, h }, { x: x - w / 2, y: y - g * 1.2 - h, w, h },
    ], taken, bounds, null, 0, 0, 5 * u);
    taken.push({ ...c, k: 3 });
    marks += txt(c.x, c.y + f * 0.92, d.label, { weight: wgt, fill: d.emphasis ? "ink" : "ink-3", op: fop, haloed: true });
  }

  // ---- where a reading sits (rung 7): the clearest corner of the plot, found once, sized for the widest reading
  const id = spec.id || "ln";
  const geom = { spec, id, f, u, P, X, Y, left, right, plotTop, plotBottom, focus: focusS, lw, txt };
  const xs = touchXs(spec, focusS);
  const rowsAll = xs.map((x) => readingRows(geom, x, xs[0]));
  const rw = Math.max(...rowsAll.flat().map((r) => textWidth(r.s, r.size, r.weight, true))), rh = Math.max(...rowsAll.map((rows) => rows.reduce((a, r) => a + r.size * 1.38, 0)));
  const inset = 10 * u;
  const corner = place([
    { x: left + inset, y: plotTop, w: rw, h: rh }, { x: right - inset - rw, y: plotTop, w: rw, h: rh },
    { x: left + inset, y: plotBottom - rh - inset, w: rw, h: rh }, { x: right - inset - rw, y: plotBottom - rh - inset, w: rw, h: rh },
  ], taken, { x: left, y: plotTop - f, w: right - left, h: plotBottom - plotTop + f }, null, 0, 0, 4 * u);
  geom.readout = band ? { x: left + inset, y: plotTop - band, w: rw, h: rh } : corner;
  geom.clear = band > 0 || !taken.some((t) => (t.k ?? 1) >= 1 && overlap({ x: corner.x - 2 * u, y: corner.y - 2 * u, w: corner.w + 4 * u, h: corner.h + 4 * u }, t) > 0);
  geom.xs = xs;
  const t = touch ? lineTouch(geom, touch) : { back: "", front: "" };

  const svg = `<svg class="chart line-chart" viewBox="0 0 ${W} ${H}" role="img"${spec.label ? ` aria-label="${esc(spec.label)}"` : ""} style="font-family:${spec.paint === "inline" ? "Inter Display, Inter, sans-serif" : "var(--font)"}">` +
    (spec.paint === "inline" ? `<rect width="${W}" height="${H}" style="fill:${P("paper")}"/>` : "") +
    head + back + grid + `<g id="${id}-touch-back">${t.back}</g>` + lines + leaders + marks + names + notes + tipLayer + foot + `<g id="${id}-touch">${t.front}</g>` + `</svg>`;
  cues.sort((a, b) => a.at - b.at);
  const seen = new Set();
  return { svg, cues: cues.filter((c) => { const k = c.name + c.at; if (seen.has(k)) return false; seen.add(k); return true; }), duration: T.end, geom };
}

// ---------------------------------------------------------------- touch (rungs 7–9)

/** How a series' value is said: its own reading, the axis's reading, its tip, or the axis's label. */
const readOf = (spec, s) => s.read || spec.y.read || s.tip || spec.series.find((q) => q.tip)?.tip || spec.y.format;
/** A change, said with its sign: +$0.28, −1,230. */
const signed = (fmt, d) => (d < 0 ? "−" : "+") + fmt(Math.abs(d)).replace(/^[-−]/, "");
const shortOf = (s) => s.short ?? s.name ?? "";

/** A series' real value at x: on a step, the tread x stands on (an edge belongs to the tread before it); otherwise only at its own points. */
export function valueAt(s, x) {
  const pts = s.points;
  if (s.kind === "step") {
    if (x < pts[0][0] || x > pts[pts.length - 1][0]) return null;
    let i = 0;
    while (i + 1 < pts.length && pts[i + 1][0] < x) i++;
    return pts[i][1];
  }
  const hit = pts.find(([px]) => Math.abs(px - x) < 1e-9);
  return hit ? hit[1] : null;
}

/** The places touch may read: every real point; on a step, every snap along its treads. */
function touchXs(spec, focus) {
  const [a, b] = spec.x.domain;
  if (focus.kind === "step") {
    const step = spec.x.snap || (b - a) / 200, out = [];
    for (let x = a; x <= b + 1e-9; x += step) out.push(Math.round(x * 1e6) / 1e6);
    return out;
  }
  return focus.points.map(([x]) => x);
}

/** The place nearest a pointer, in data units: a real point, or a snap on a step's tread. */
export function lineSnap(geom, px) {
  const x = geom.X.invert(Math.min(geom.right, Math.max(geom.left, px)));
  return geom.xs.reduce((best, v) => (Math.abs(v - x) < Math.abs(best - x) ? v : best), geom.xs[0]);
}

/** The reading at x, row by row: where (when the axis can say it), each line's value, what you did not ask, and the change since a pin. */
function readingRows({ spec, f, focus }, x, pin) {
  const rows = [];
  if (spec.x.read) rows.push({ s: spec.x.read(x), size: f * 0.92, weight: 400, fill: "ink-3" });
  const tone = (q) => (q.role === "leak" ? "blue" : q.role === "focus" ? "ink" : "ink-3");
  const vals = [];
  for (const q of [focus, ...spec.series.filter((q) => q !== focus)]) {
    const v = valueAt(q, x);
    if (v == null) continue;
    vals.push([q, v]);
    const name = shortOf(q);
    rows.push({ s: (name ? name + " " : "") + readOf(spec, q)(v), size: q === focus ? f * 1.15 : f, weight: q === focus ? 600 : 400, fill: tone(q) });
  }
  const extra = whatYouDidNotAsk(spec, focus, x, vals);
  if (extra) rows.push({ s: extra, size: f * 0.92, weight: 400, fill: "ink-2" });
  if (pin != null && valueAt(focus, pin) != null && valueAt(focus, x) != null)
    rows.push({ s: `Since the pin ${signed(readOf(spec, focus), valueAt(focus, x) - valueAt(focus, pin))}`, size: f * 0.92, weight: 600, fill: "ink-2" });
  return rows;
}

/** Rung 8: the gap to the other line here, or on a staircase, the next step and its cost. */
function whatYouDidNotAsk(spec, focus, x, vals) {
  const other = vals.find(([q]) => q !== focus);
  const vf = valueAt(focus, x);
  if (other && vf != null && other[1] !== 0) {
    if (spec.compare) return spec.compare(vf, other[1]);
    const pct = ((vf - other[1]) / Math.abs(other[1])) * 100;
    return `${Math.abs(pct).toFixed(1)}% ${pct >= 0 ? "above" : "below"} ${shortOf(other[0]).toLowerCase() || "the other line"}`;
  }
  if (focus.kind === "step" && spec.x.read && vf != null) {
    const pts = focus.points;
    for (let k = 1; k < pts.length; k++) {
      if (pts[k][0] >= x && pts[k][1] !== vf && k + 0 < pts.length) {
        const edge = pts[k][0];
        if (edge >= spec.x.domain[1]) break;
        return `Next step ${signed(readOf(spec, focus), pts[k][1] - vf)} past ${spec.x.read(edge)}`;
      }
    }
  }
  return null;
}

/**
 * The reading drawn: behind the lines, the span from a pin and a hairline at the place; in front,
 * a ring on each line where it is read, and the rows in the clear corner. The finger is the
 * animation, so it changes the instant the finger does.
 */
export function lineTouch(geom, { x, pin = null }) {
  const { P, X, Y, f, u, plotTop, plotBottom, spec, focus, readout, lw } = geom;
  const halo = `paint-order:stroke;stroke:${P("paper")};stroke-width:${r1(0.34 * f)}px;stroke-linejoin:round`;
  let back = "", front = "";
  if (pin != null) {
    const a = X(Math.min(pin, x)), b = X(Math.max(pin, x));
    back += `<rect x="${r1(a)}" y="${r1(plotTop)}" width="${r1(Math.max(0, b - a))}" height="${r1(plotBottom - plotTop)}" style="fill:${P("paper-2")}"/>`;
    back += `<line x1="${r1(X(pin))}" x2="${r1(X(pin))}" y1="${r1(plotTop)}" y2="${r1(plotBottom)}" style="stroke:${P("ink-3")};stroke-width:${r1(lw("line-hair"))}px"/>`;
  }
  const cx = X(x);
  // the place's hairline goes behind the lines and their words, so it never strikes through a label
  back += `<line x1="${r1(cx)}" x2="${r1(cx)}" y1="${r1(plotTop)}" y2="${r1(plotBottom)}" style="stroke:${P("ink-3")};stroke-width:${r1(lw("line-hair"))}px"/>`;
  for (const q of [...spec.series.filter((q) => q !== focus), focus]) {
    const v = valueAt(q, x);
    if (v == null) continue;
    const stroke = q.role === "leak" ? "blue" : q.role === "focus" ? "ink" : "ink-3";
    front += `<circle cx="${r1(cx)}" cy="${r1(Y(v))}" r="${r1((q === focus ? 4.4 : 3.4) * u)}" style="fill:${P("paper")};stroke:${P(stroke)};stroke-width:${r1(1.6 * u)}px"/>`;
  }
  if (pin != null && valueAt(focus, pin) != null) front += `<circle cx="${r1(X(pin))}" cy="${r1(Y(valueAt(focus, pin)))}" r="${r1(3.4 * u)}" style="fill:${P("ink-3")}"/>`;
  let y = readout.y;
  for (const r of readingRows(geom, x, pin)) {
    y += r.size * 1.12;
    front += `<text x="${r1(readout.x)}" y="${r1(y)}" style="font-size:${r1(r.size)}px;font-weight:${r.weight};fill:${P(r.fill)};font-variant-numeric:tabular-nums;${halo}">${esc(r.s)}</text>`;
    y += r.size * 0.26;
  }
  return { back, front };
}

/** Rung 10: the largest fall from a running peak to a later low, if it is worth naming, and whether the line came back. */
export function worstFall(points, min = 0) {
  let peak = 0, best = null;
  for (let j = 1; j < points.length; j++) {
    if (points[j][1] > points[peak][1]) peak = j;
    const d = points[peak][1] - points[j][1];
    if (d > min && d > (best?.fall ?? 0)) best = { i: peak, j, fall: d };
  }
  if (best) best.back = points.slice(best.j + 1).some(([, v]) => v >= points[best.i][1]);
  return best;
}

// ---------------------------------------------------------------- the card (rung 11)

const MARK = '<path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z"/>';

/**
 * One clean card of a finished chart, for a deck, an email or a board pack: the title, the chart,
 * the label that never comes off, and Hubricon's quiet mark (BRAND.md). 1200 × 630, its own colours.
 * `chart(w, h)` returns the chart's SVG at that size.
 */
export function shareCard({ title, source, chart, paint = "inline", ground = "day" }) {
  const W = 1200, H = 630, pad = 56, P = painter(paint, ground);
  const body = chart(W - pad * 2, 440).replace("<svg ", `<svg x="${pad}" y="128" width="${W - pad * 2}" height="440" `);
  const t = (x, y, s, size, weight, fill, anchor = "start") => `<text x="${x}" y="${y}" text-anchor="${anchor}" style="font-size:${size}px;font-weight:${weight};fill:${P(fill)}">${esc(s)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="font-family:${paint === "css" ? "var(--font)" : "Inter Display, Inter, sans-serif"}">` +
    `<rect width="${W}" height="${H}" style="fill:${P("paper")}"/>` +
    t(pad, 84, title, 40, 600, "ink") + body +
    t(pad, H - 34, source, 16, 400, "ink-3") +
    `<g transform="translate(${W - pad - 132} ${H - 58}) scale(0.5)" style="fill:${P("ink")}"><circle cx="32" cy="32" r="27" fill="none" style="stroke:${P("ink")}" stroke-width="5"/>${MARK}</g>` +
    t(W - pad, H - 34, "Hubricon", 20, 600, "ink", "end") +
    `</svg>`;
}

/** A line chart's card: the chart finished, without its own title (the card carries it). */
export function lineCard(spec) {
  return shareCard({ title: spec.cardTitle || spec.title, source: spec.source, paint: "inline", ground: spec.ground,
    chart: (w, h) => lineChart({ ...spec, w, h, font: 17, paint: "inline", title: null, subtitle: null, source: null, id: (spec.id || "ln") + "-card" }, Infinity).svg });
}

// ---------------------------------------------------------------- in a page

/** Where a pointer is, in the chart's own units. */
function toChart(svg, e) {
  const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return [p.x, p.y];
}

/**
 * Play a line chart in a page: the draw-in, then the reading. Hover or touch reads the line; a
 * click or a second tap on the same place pins it; arrow keys walk the real points, Enter pins,
 * Escape clears. It draws only while something moves. Returns a function that stops it and
 * leaves the finished still.
 */
export function playLine(host, spec, { now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame, touchable = true } = {}) {
  const id = spec.id || "ln";
  let r = lineChart(spec, 0);
  host.innerHTML = r.svg;
  const t0 = now();
  let rid = 0, live = true, ready = false, touch = null, geom = null;
  const show = () => {
    const t = touch ? lineTouch(geom, touch) : { back: "", front: "" };
    host.querySelector(`#${id}-touch-back`).innerHTML = t.back;
    host.querySelector(`#${id}-touch`).innerHTML = t.front;
  };
  const frame = () => {
    rid = 0;
    const at = now() - t0;
    if (at >= r.duration) { r = lineChart(spec, Infinity); host.innerHTML = r.svg; geom = r.geom; ready = true; arm(); if (touch) { touch = { ...touch, x: nearestX(geom, touch.x) }; show(); } return; }
    host.innerHTML = lineChart(spec, at).svg;
    if (live) rid = raf(frame);
  };
  rid = raf(frame);
  function arm() {
    if (!touchable || typeof window === "undefined") return;
    const svg = host.querySelector("svg");
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-description", "Move across the chart to read it. Click to pin a point; arrow keys step through the real points.");
    const move = (e) => { const x = lineSnap(geom, toChart(svg, e)[0]); if (!touch || touch.x !== x) { touch = { x, pin: touch?.pin ?? null }; show(); } };
    svg.addEventListener("pointermove", move);
    svg.addEventListener("pointerdown", (e) => {
      const x = lineSnap(geom, toChart(svg, e)[0]);
      if (touch && touch.x === x) touch = { x, pin: touch.pin === x ? null : x };   // a second tap on the same place pins it, or lets it go
      else touch = { x, pin: touch?.pin ?? null };
      show();
    });
    svg.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse" && touch && touch.pin == null) { touch = null; show(); } });
    svg.addEventListener("keydown", (e) => {
      const xs = geom.xs;
      const i = touch ? xs.indexOf(touch.x) : -1;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const k = Math.min(xs.length - 1, Math.max(0, i < 0 ? 0 : i + (e.key === "ArrowRight" ? 1 : -1)));
        touch = { x: xs[k], pin: touch?.pin ?? null }; show(); e.preventDefault();
      } else if ((e.key === "Enter" || e.key === " ") && touch) { touch = { x: touch.x, pin: touch.pin === touch.x ? null : touch.x }; show(); e.preventDefault(); }
      else if (e.key === "Escape") { touch = null; show(); }
    });
  }
  const stop = () => { live = false; caf(rid); rid = 0; if (!ready) { r = lineChart(spec, Infinity); host.innerHTML = r.svg; geom = r.geom; ready = true; arm(); if (touch) show(); } };
  /** Read the line at x from outside (a control on the page): shown once the draw-in has landed. */
  stop.read = (x) => { touch = { x: geom ? nearestX(geom, x) : x, pin: null }; if (ready) show(); };
  return stop;
}

/** The readable place nearest a value, in data units. */
const nearestX = (geom, x) => geom.xs.reduce((best, v) => (Math.abs(v - x) < Math.abs(best - x) ? v : best), geom.xs[0]);

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
 * Words broken into lines that fit `maxW`, measured with Inter's own widths. A label's parts
 * ("Not a client · Not a result") break at their separators first, so no part is split.
 */
export function wrap(s, size, weight, maxW, sep = " ") {
  const parts = String(s).split(sep), lines = [];
  let cur = "";
  for (const part of parts) {
    const next = cur ? cur + sep + part : part;
    if (!cur || textWidth(next, size, weight) <= maxW) { cur = next; continue; }
    lines.push(cur + (sep === " " ? "" : sep.trimEnd()));
    cur = part;
  }
  if (cur) lines.push(cur);
  // a part longer than the line on its own is broken at its spaces
  return sep === " " ? lines : lines.flatMap((l) => (textWidth(l, size, weight) > maxW ? wrap(l, size, weight, maxW, " ") : [l]));
}
