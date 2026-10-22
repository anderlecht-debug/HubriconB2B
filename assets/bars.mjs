/* ============================================================================
   The bars: where an amount goes, part by part.

   Two shapes, the same rules as the line (assets/line.mjs):
   "stack"      one bar per row, split left to right into its parts (a price
                into what each party takes and what is kept).
   "waterfall"  one row per step, top to bottom: a total from nothing, each
                cost taken off where it falls, the next total where it lands.

   1. Exact. A part's width is its share of the bar; no rounding on screen.
   2. Labels on the parts. A value sits inside its part when it fits, and
      under it otherwise, placed by the line's solver so nothing collides;
      names sit on the parts, never in a key.
   3. Blue only for the money that is kept (or the leak). Everything else is
      ink and quiet greys, solid, with a paper gap between parts.
   4. Story order: the names, then the bars grow (a stack left to right, a
      waterfall top to bottom, one tick each), a silence, then the finding:
      the kept part turns blue and its note arrives.

   barChart(spec, at) is pure, like lineChart: Infinity is the still frame.
   ============================================================================ */

import { ms, ease, VIDEO } from "./tokens.mjs";
import { painter, place, textWidth, wrap, shareCard } from "./line.mjs";

const r1 = (v) => Math.round(v * 10) / 10;
const prog = (at, a, b) => (b <= a ? (at >= a ? 1 : 0) : Math.min(1, Math.max(0, (at - a) / (b - a))));

/**
 * spec: {
 *   type (or kind): "stack" | "waterfall", w, font, paint, ground, id, title?, subtitle?, source?, label?, format(v),
 *   rows (stack):     [{ name, parts: [{ name, value, money? }] }]
 *   rows (waterfall): [{ name, value, total?, money? }]      a cost is negative; a total is a bar from nothing
 *   note?: { title, body }                                   the finding, beside the first money part
 * }
 * Returns { svg, cues, duration, h }: the height is worked out from the content.
 */
export function barChart(spec, at = Infinity) {
  const P = painter(spec.paint, spec.ground), f = spec.font || 13, u = f / 13, W = spec.w, pad = 8 * u, id = spec.id || "bars";
  const ez = ease("ease-out"), fmt = spec.format || ((v) => `${v}`);
  const halo = `paint-order:stroke;stroke:${P("paper")};stroke-width:${r1(0.34 * f)}px;stroke-linejoin:round`;
  const txt = (x, y, s, { size = f, weight = 400, fill = "ink-3", anchor = "start", op = 1, haloed = false, tab = false } = {}) =>
    `<text x="${r1(x)}" y="${r1(y)}" text-anchor="${anchor}" style="font-size:${r1(size)}px;font-weight:${weight};fill:${P(fill)};${tab ? "font-variant-numeric:tabular-nums;" : ""}${op < 1 ? `opacity:${r1(op * 100) / 100};` : ""}${haloed ? halo : ""}">${esc(s)}</text>`;

  // ---- the clock: names, then each row or part in turn, a silence, the finding
  const shape = spec.type || spec.kind;
  const n = shape === "waterfall" ? spec.rows.length : spec.rows.reduce((a, r) => a + r.parts.length, 0);
  const draw = ms("mc-draw-ms"), each = draw / Math.max(1, n), fade = ms("mc-band-ms");
  const T = { stage: [0, fade], grow: [fade * 0.6, fade * 0.6 + draw] };
  T.reveal = T.grow[1] + VIDEO.motion.silenceMs;
  T.finding = [T.reveal, T.reveal + fade];
  T.end = T.finding[1];
  const stageOp = ez(prog(at, ...T.stage)), fop = ez(prog(at, ...T.finding));
  const cues = [];

  // ---- head and foot, wrapped to the width
  let y = pad, head = "", body = "";
  if (spec.title) { const ts = f * 1.55; for (const l of wrap(spec.title, ts, 600, W - 2 * pad)) { head += txt(pad, y + ts * 0.86, l, { size: ts, weight: 600, fill: "ink" }); y += ts * 1.18; } }
  if (spec.subtitle) { for (const l of wrap(spec.subtitle, f, 400, W - 2 * pad)) { head += txt(pad, y + f * 0.9, l); y += f * 1.35; } }
  if (spec.title || spec.subtitle) y += f * 1.2;
  const taken = [];
  const bh = f * 2.3, gap = 2 * u;

  if (shape === "stack") {
    const max = Math.max(...spec.rows.map((r) => r.parts.reduce((a, p) => a + p.value, 0)));
    const X0 = pad, span = W - 2 * pad;
    let k = 0;
    spec.rows.forEach((row, ri) => {
      body += txt(X0, y + f * 0.95, row.name, { weight: 600, fill: "ink", op: stageOp });
      y += f * 1.5;
      // names over the first row's parts, so each part is named once, on the part: on one line when
      // they fit side by side, otherwise alternating over two, each line with its own room
      if (ri === 0) {
        const items = [];
        let x = X0;
        for (const part of row.parts) { const wpx = (part.value / max) * span; items.push({ part, cx: x + wpx / 2, w: textWidth(part.name, f * 0.92, part.money ? 600 : 400) }); x += wpx; }
        const clamp = (it) => Math.min(X0 + span - it.w, Math.max(X0, it.cx - it.w / 2));
        // each name takes the lowest line where it clears the name before it on that line
        const lines = [];
        for (const it of items) {
          const x0 = clamp(it), line = lines.find((l) => l.end + 8 * u <= x0) || (lines.push({ end: -Infinity, list: [] }), lines[lines.length - 1]);
          line.list.push(it); line.end = x0 + it.w;
        }
        lines.reverse();
        for (const { list } of lines) {
          for (const it of list) body += txt(clamp(it), y + f * 0.9, it.part.name, { size: f * 0.92, weight: it.part.money ? 600 : 400, fill: it.part.money ? (fop > 0.5 ? "blue" : "ink-3") : "ink-3", op: stageOp });
          y += f * 1.25;
        }
        y += f * 0.3;
      }
      let x = X0;
      const top = y, below = [];
      row.parts.forEach((part, pi) => {
        const wpx = (part.value / max) * span;
        const t0 = T.grow[0] + k * each, g = ez(prog(at, t0, t0 + each * 1.6));
        k++;
        cues.push({ name: "tick", at: Math.round(t0) });
        const fill = part.money ? (fop > 0 ? mixHex(P, fop) : "rule-2") : pi % 2 ? "paper-2" : "rule-2";
        const ww = Math.max(0, wpx - gap) * g;
        if (ww > 0.2) body += `<rect x="${r1(x)}" y="${r1(top)}" width="${r1(ww)}" height="${r1(bh)}" style="fill:${fill.startsWith("#") || fill.startsWith("color-mix") ? fill : P(fill)}"/>`;
        const s = fmt(part.value), tw = textWidth(s, f, 600, true);
        if (tw + 10 * u <= wpx - gap) { if (g >= 1) body += txt(x + (wpx - gap) / 2, top + bh / 2 + f * 0.34, s, { weight: 600, fill: part.money && fop > 0.5 ? "paper" : "ink", anchor: "middle", tab: true, op: g }); }
        else below.push({ s, cx: x + wpx / 2, g, money: part.money });
        x += wpx;
      });
      taken.push({ x: X0, y: top, w: span, h: bh, k: 3 });
      y = top + bh;
      // values too wide for their part sit under it, the solver keeping them apart
      for (const b of below) {
        const w = textWidth(b.s, f, 600, true);
        const c = place([{ x: b.cx - w / 2, y: y + 4 * u, w, h: f * 1.2 }, { x: b.cx - w, y: y + 4 * u, w, h: f * 1.2 }, { x: b.cx, y: y + 4 * u, w, h: f * 1.2 }, { x: b.cx - w / 2, y: y + f * 1.4, w, h: f * 1.2 }],
          taken, { x: X0, y, w: span, h: f * 3 }, [b.cx, y], 0, 0, 4 * u);
        taken.push({ ...c, k: 3 });
        if (b.g >= 1) body += txt(c.x + w / 2, c.y + f * 0.9, b.s, { weight: 600, fill: b.money && fop > 0.5 ? "blue" : "ink-2", anchor: "middle", tab: true });
      }
      y += (below.length ? f * 1.6 : 0) + f * 1.3;
    });
  } else {
    // ---- the waterfall: names in a column (or above each bar on a phone), a bar per step, hairlines carrying the running total down
    const labelW = W < 520 ? 0 : Math.max(...spec.rows.map((r) => textWidth(r.name, f, r.total ? 600 : 400))) + 16 * u;
    let run = 0, lo = 0, hi = 0;
    for (const r of spec.rows) { run = r.total ? r.value : run + r.value; lo = Math.min(lo, run); hi = Math.max(hi, run, r.total ? r.value : 0); }
    const valW = Math.max(...spec.rows.map((r) => textWidth(fmt(r.value), f, 600, true))) + 10 * u;
    const X0 = pad + labelW, span = W - pad - X0 - valW;
    const X = (v) => X0 + ((v - lo) / (hi - lo || 1)) * span;
    run = 0;
    let prevEdge = null, prevBottom = null;
    spec.rows.forEach((r, i) => {
      const from = r.total ? 0 : run, to = r.total ? r.value : run + r.value;
      run = to;
      let above = "";
      if (!labelW) { above = txt(pad, y + f * 0.95, r.name, { weight: r.total ? 600 : 400, fill: r.total ? "ink" : "ink-2", op: stageOp, haloed: true }); y += f * 1.4; }
      const t0 = T.grow[0] + i * each, g = ez(prog(at, t0, t0 + each * 1.6));
      cues.push({ name: "tick", at: Math.round(t0) });
      const a = X(Math.min(from, to)), b = X(Math.max(from, to)), grown = a + (b - a) * g;
      const start = r.value < 0 && !r.total ? b - (b - a) * g : a;
      const fill = r.money ? (fop > 0 ? mixHex(P, fop) : "ink-4") : r.total ? "ink-4" : "rule-2";
      const top = y, h = bh * 0.82;
      if (labelW) body += txt(pad, top + h / 2 + f * 0.34, r.name, { weight: r.total ? 600 : 400, fill: r.total ? "ink" : "ink-2", op: stageOp });
      if (prevEdge != null && g > 0) body += `<line x1="${r1(prevEdge)}" x2="${r1(prevEdge)}" y1="${r1(prevBottom)}" y2="${r1(top)}" style="stroke:${P("ink-4")};stroke-width:${r1(u)}px;opacity:${r1(g * 100) / 100}"/>`;
      body += above;
      if (g > 0) body += `<rect x="${r1(r.value < 0 && !r.total ? start : a)}" y="${r1(top)}" width="${r1(Math.max(0, (r.value < 0 && !r.total ? b - start : grown - a)))}" height="${r1(h)}" style="fill:${fill.startsWith("#") || fill.startsWith("color-mix") ? fill : P(fill)}"/>`;
      const s = fmt(r.value);
      if (g >= 1) body += txt(b + 8 * u, top + h / 2 + f * 0.34, s, { weight: 600, fill: r.money && fop > 0.5 ? "blue" : r.total ? "ink" : "ink-2", tab: true });
      prevEdge = X(to);
      prevBottom = top + h;
      y = top + h + f * 0.55;
    });
    y += f * 0.6;
  }

  // ---- the finding's note, after the silence
  if (spec.note && fop > 0) {
    body += txt(pad, y + f * 1.05, spec.note.title, { size: f * 1.08, weight: 600, fill: "blue", op: fop });
    if (spec.note.body) body += txt(pad, y + f * 2.4, spec.note.body, { fill: "ink-3", op: fop });
  }
  if (spec.note) y += f * (spec.note.body ? 3.2 : 1.8);
  cues.push({ name: "reveal", at: Math.round(T.reveal) });
  let foot = "";
  if (spec.source) { y += f * 0.6; for (const l of wrap(spec.source, f * 0.85, 400, W - 2 * pad, " · ")) { foot += txt(pad, y + f * 0.85, l, { size: f * 0.85 }); y += f * 1.2; } }
  const H = Math.ceil(y + pad);
  const svg = `<svg class="chart bar-chart" viewBox="0 0 ${W} ${H}" role="img"${spec.label ? ` aria-label="${esc(spec.label)}"` : ""} style="font-family:${spec.paint === "inline" ? "Inter Display, Inter, sans-serif" : "var(--font)"}">` +
    (spec.paint === "inline" ? `<rect width="${W}" height="${H}" style="fill:${P("paper")}"/>` : "") + head + body + foot + `</svg>`;
  return { svg, cues: dedupe(cues), duration: T.end, h: H };
}

/** The card for a deck. */
export const barCard = (spec) => shareCard({ title: spec.cardTitle || spec.title, source: spec.source, paint: "inline", ground: spec.ground,
  chart: (w, h) => barChart({ ...spec, w, font: 17, paint: "inline", title: null, subtitle: null, source: null, id: (spec.id || "bars") + "-card" }, Infinity).svg.replace(/viewBox="0 0 (\d+) (\d+)"/, (m, a, b) => `viewBox="0 0 ${a} ${Math.max(+b, h)}"`) });

/** Play bars in a page: re-drawn each frame for the short draw-in, then left as the still. */
export function playBars(host, spec, { now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame } = {}) {
  const t0 = now(); let rid = 0;
  const frame = () => { rid = 0; const at = now() - t0, r = barChart(spec, at); host.innerHTML = r.svg; if (at < r.duration) rid = raf(frame); };
  rid = raf(frame);
  return () => { caf(rid); host.innerHTML = barChart(spec, Infinity).svg; };
}

// the kept part's colour on its way from grey to blue: one solid colour, never stacked transparency
function mixHex(P, t) {
  const a = P("rule-2"), b = P("blue");
  if (a.startsWith("var(")) return `color-mix(in srgb, ${b} ${Math.round(t * 100)}%, ${a})`;
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [rgb(a), rgb(b)];
  return "#" + x.map((c, i) => Math.round(c + (y[i] - c) * t).toString(16).padStart(2, "0")).join("");
}
function dedupe(cues) { const seen = new Set(); return cues.sort((a, b) => a.at - b.at).filter((c) => { const k = c.name + c.at; if (seen.has(k)) return false; seen.add(k); return true; }); }
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
