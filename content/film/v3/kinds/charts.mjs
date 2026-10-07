// v3 charts: data drawn as light on the dark desk (docs/content/FILM_LOOK_V3.md, "Data is light";
// round 2: scratchpad ROUND2.md, the shared base in base.css / clock.js / shots.mjs; round 3:
// DESIGN_R3.md, every drawn figure accounted for and every chart owning its frame).
//
// chart(job, built) draws one chart shot as hand-set SVG and HTML: the fee staircase, the Monte
// Carlo, the aging cliff and the engine's waterfall, the riser that moves (an illustration), plus a
// quiet typographic fallback for any other scene. The figures are the site's own (built =
// scripts/build-pages.mjs figures(): built.charts.stairs / .aging / .mc), the waterfall is the film's
// own run.json (job.chart_data), the spoken values are the job's reveals. Nothing here types a
// figure: every number is formatted from that data with the site's own helpers, and none counts up
// (S3): a figure lands, whole and exact, on its spoken word.
//
// What may be drawn (round 3). A figure (an amount, a count, a share, a weight, a date) is drawn only
// when the voice speaks it in this shot (job.reveals: it lands on its word) or has already said it
// (job.known: it may stand from frame 0). saidAt() is that test, and every figure on a chart passes
// it; one that fails is not drawn at all (the waterfall's other bars carry no value, the Monte
// Carlo's ends are named in words). A chart's scale, the ticks on its axes, is a ruler and not a
// figure. A heading or caption that holds a figure this shot speaks sets that figure on its word.
//
// Time comes from the words (S5): job.words gives each spoken word's onset in seconds from the shot's
// first frame. A figure lands on the onset of the word that speaks it, never before; the other builds
// land on the editor's `params.builds` or on the words that name them, and fall back to times spread
// between those. Frame 1 is never empty (R1): what a return already showed stands at the cut, and a
// first appearance opens with its axes drawn and its first strokes on.
//
// The camera is base.css's one rig; each chart's own move rides on an inner layer. camera() frames
// it: wide, a push about a point, or tight on a detail with the rest of the chart off the frame. When
// the move takes the chart's axes past title-safe, its scale (rules, ticks, axis names: class
// ch-scale-<id>) dims away and returns as the camera pulls back, the way a graphic's context falls
// away when the shot dives into its point.
import { esc } from "../shots.mjs";
import { usd, niceTicks } from "../../../../assets/charts.mjs";

// ---------------------------------------------------------------- small tools

const r1 = (v) => Math.round(v * 10) / 10;
const s3 = (v) => Math.round(v * 1000) / 1000;
const lin = (d0, d1, a, b) => (v) => a + ((v - d0) / (d1 - d0 || 1)) * (b - a);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const MINUS = "−";
const cents = (v) => `$${v.toFixed(2)}`;
const money0 = (v) => `$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
const early = (t) => (t <= 0.4 ? -0.4 : t);                 // R1: an entrance due by 0.4 s is mid-way at the cut
const at = (t, d) => `--at:${s3(t)}${d != null ? `;--d:${s3(d)}` : ""}`;
/** A build at or before this many seconds is "at the cut": on a return, it already stands. */
const AT_CUT = 0.45;
/** An entrance time that has finished before frame 0 (every entrance here lasts under 3 s). */
const DONE = -3;
// Title-safe for what the plot layer may push into, inside base.css's camera (a push of at most 6%
// about the left grid at 45% height, no drift): x 1680 ends at 1771 and y 114 at 90.
const SAFE = { l: 160, r: 1680, t: 114, b: 930 };
/** The heading block's foot: a heading line, and a caption line under it when there is one. */
const headFoot = (p) => (p?.caption ? 252 : p?.heading ? 186 : 104);
/** The plot's baseline: its tick labels clear shots.mjs's label slot (taller when a source line sits in it). */
const floorOf = (job) => (job.source_label ? 676 : 766);

// ---------------------------------------------------------------- words

const norm = (s) => String(s ?? "").toLowerCase().replace(/[“”"‘’'(),.:;!?]/g, "");
const wordsOf = (job) => (Array.isArray(job.words) ? job.words : []).filter((w) => Number.isFinite(+w.t));

/** The onset of the first word matching `re`, between `after` and `before` (seconds), else null. */
function cue(job, re, after = -1, before = Infinity) {
  const w = wordsOf(job).find((x) => +x.t >= after && +x.t <= before && re.test(norm(x.w)));
  return w ? +w.t : null;
}

/** When a reveal's figure is spoken: the onset of the word that carries its first figure. */
function spoken(job, r) {
  if (!r) return null;
  const m = String(r.value ?? "").match(/[$−-]?\d[\d,.]*%?/);
  if (!m) return +r.t;
  const tok = norm(m[0]).replace(/[−-]/g, "");
  const w = wordsOf(job).find((x) => +x.t >= +r.t - 0.6 && norm(x.w).replace(/[−-]/g, "").includes(tok));
  return w ? +w.t : +r.t;
}

/** A computed beat snapped onto the next word onset (within 0.7 s), so it lands with the voice. */
function snap(job, t) {
  const w = wordsOf(job).find((x) => +x.t >= t - 0.05 && +x.t <= t + 0.7);
  return w ? +w.t : t;
}

/** The numbers in a text, bare ("−$102,395" → ["102395"]). */
const numbers = (s) => (String(s ?? "").match(/\d[\d,]*(?:\.\d+)?/g) || []).map((x) => x.replace(/,/g, ""));

/**
 * Whether, and from when, a figure may be drawn: the onset of its word when this shot speaks it,
 * DONE when the voice said it before this shot (job.known: it stands at the cut), else null (it is
 * never drawn). A figure is matched on its numbers ("−$102,395" is the fact "$102,395"; "+$0.26" is
 * "$0.26 a unit"), a figure in words on its words ("eight in ten").
 */
function saidAt(job, text) {
  const want = numbers(text), words = norm(text).trim();
  if (!want.length && !words) return null;
  const same = (v) => {
    const got = numbers(v);
    return want.length ? got.length > 0 && want.every((x) => got.includes(x)) : norm(v).trim() === words;
  };
  const r = (job.reveals || []).find((x) => Number.isFinite(+x.t) && same(x.value));
  if (r) return spoken(job, r);
  return Object.values(job.known || {}).some(same) ? DONE : null;
}

/**
 * The shot's clock: length, `on`, reveals by key (with the onset their figure is spoken), and the
 * editor's `params.builds` (PLAN_PARAMS.md: seconds from the shot's first frame at which something
 * new lands). Builds written in film seconds (the retired form) are not read. Priority, for every
 * beat: the word that speaks a figure, then the editor's build, then a word that names the beat,
 * then a time spread between them. `n` is how many builds the plan gave (a scene reads its beats by
 * their count); `ret` is true when every build is at the cut (a return: the chart stands).
 */
function clockOf(job) {
  const S = Number(job.seconds) || 8;
  const reveals = Array.isArray(job.reveals) ? job.reveals : [];
  const rv = (k) => {
    const r = reveals.find((x) => x.key === k && Number.isFinite(+x.t) && +x.t >= 0 && +x.t <= S);
    return r ? { ...r, at: spoken(job, r) } : null;
  };
  const on = Number.isFinite(job.on) && job.on >= 0 && job.on <= S ? job.on : null;
  const raw = job.params?.builds;
  const B = Array.isArray(raw) && raw.length && raw.every((b) => Number.isFinite(+b) && +b >= 0 && +b <= S + 0.05)
    ? raw.map(Number).sort((p, q) => p - q) : null;
  /** The editor's i-th build, if the plan wrote one. */
  const build = (i) => (B && i < B.length ? B[i] : null);
  return { S, on, rv, build, n: B ? B.length : 0, ret: !!B && B.every((b) => b <= AT_CUT) };
}

/** Times spread evenly over [a, b] (n of them; one lands at a). */
const spread = (n, a, b) => Array.from({ length: n }, (_, i) => (n === 1 ? a : a + ((b - a) * i) / (n - 1)));

// ---------------------------------------------------------------- the camera

/**
 * The plot layer's own move, on top of the camera: keyframes of translate and scale about a focus
 * point, kept inside SAFE for the content's bounds. Between keys it eases; the rig under it never
 * stops, so the frame never comes to rest. (The aging chart's camera; the others use camera().)
 */
function pushCSS(uid, S, keys, box, { top = SAFE.t, left = SAFE.l } = {}) {
  const sMax = Math.max(1, Math.min((SAFE.r - left) / Math.max(1, box.r - box.l), (SAFE.b - top) / Math.max(1, box.b - box.t)));
  const fit = ({ s = 1, fx = 960, fy = 540, dx = 0, dy = 0 }) => {
    s = Math.min(s, sMax);
    let tx = fx * (1 - s) + dx, ty = fy * (1 - s) + dy;
    const xlo = left - box.l * s, xhi = SAFE.r - box.r * s, ylo = top - box.t * s, yhi = SAFE.b - box.b * s;
    tx = xlo <= xhi ? clamp(tx, xlo, xhi) : clamp(0, xhi, xlo);
    ty = ylo <= yhi ? clamp(ty, ylo, yhi) : clamp(0, yhi, ylo);
    return `translate(${r1(tx)}px,${r1(ty)}px) scale(${s.toFixed(4)})`;
  };
  const ks = [...keys].filter((k) => k.t >= 0 && k.t <= S).sort((p, q) => p.t - q.t);
  if (!ks.length || ks[0].t > 0) ks.unshift({ ...(ks[0] || {}), t: 0 });
  if (ks[ks.length - 1].t < S) ks.push({ ...ks[ks.length - 1], t: S });
  const body = ks.map((k) => `${r1((k.t / S) * 100)}%{transform:${fit(k)};animation-timing-function:cubic-bezier(.45,0,.25,1)}`).join("");
  return `@keyframes chp-${uid}{${body}}`;
}

/** A camera key: the content point f sits on the screen at (sx, sy), at scale s (a push about f when sx, sy are f). */
const pin = (f, s, sx = f.x, sy = f.y) => ({ s, fx: f.x, fy: f.y, sx, sy });

/**
 * The plot layer's camera: keys {t, s, fx, fy, sx, sy} (pin()), or {t, s: 1} for the chart as laid
 * out. Eases between keys. `groups` are the chart's dimmable parts, each {cls, box}: wherever a key
 * puts a group's box past title-safe, that group (its scale's rules and ticks, its card names) dims
 * out early in the move toward that key and back in late in the move away, so no label is ever read
 * cut by the frame.
 */
function camera(uid, S, keys, groups) {
  const ks = keys.map((k) => ({ ...k, t: clamp(k.t, 0, S) })).sort((p, q) => p.t - q.t);
  if (!ks.length || ks[0].t > 0) ks.unshift({ ...(ks[0] || { s: 1 }), t: 0 });
  if (ks[ks.length - 1].t < S) ks.push({ ...ks[ks.length - 1], t: S });
  const tf = (k) => {
    const s = k.s ?? 1, fx = k.fx ?? 0, fy = k.fy ?? 0;
    return { s, tx: (k.sx ?? fx) - fx * s, ty: (k.sy ?? fy) - fy * s };
  };
  const pc = (t) => r1((clamp(t, 0, S) / S) * 100);
  const body = ks.map((k) => {
    const { s, tx, ty } = tf(k);
    return `${pc(k.t)}%{transform:translate(${r1(tx)}px,${r1(ty)}px) scale(${s.toFixed(4)});animation-timing-function:cubic-bezier(.45,0,.25,1)}`;
  }).join("");
  let css = `@keyframes chp-${uid}{${body}}`;
  groups.forEach(({ cls, box }, g) => {
    const fits = (k) => {
      const { s, tx, ty } = tf(k);
      return box.l * s + tx >= SAFE.l - 1 && box.r * s + tx <= SAFE.r + 1 && box.t * s + ty >= SAFE.t - 1 && box.b * s + ty <= SAFE.b + 1;
    };
    const op = ks.map(fits);
    if (op.every(Boolean)) return;
    const stops = [[0, op[0] ? 1 : 0]];
    for (let i = 1; i < ks.length; i++) {
      const a = ks[i - 1].t, b = ks[i].t, d = b - a;
      if (op[i - 1] && !op[i]) stops.push([a, 1], [a + Math.min(0.5, 0.2 * d), 0]);
      if (!op[i - 1] && op[i]) stops.push([b - Math.min(0.4, 0.15 * d), 0], [b, 1]);
    }
    stops.push([S, op[op.length - 1] ? 1 : 0]);
    css += `@keyframes chq${g}-${uid}{${stops.map(([t, o]) => `${pc(t)}%{opacity:${o}}`).join("")}}` +
      `.${cls}{animation:chq${g}-${uid} ${s3(S)}s linear 0s both}`;
  });
  return css;
}

// ---------------------------------------------------------------- the frame

/** The frame every chart shares: the camera, the plot layer that moves, the still layers over it. */
function stage({ uid, S, css = "", under = "", svg, html = "", over = "", head = "" }) {
  return `<style>${css}</style>` +
    `<div class="cam ch"><div class="rig"><div class="ch-cam">` +
    `<div class="ch-push" style="animation:chp-${uid} ${s3(S)}s linear 0s both">${under}` +
    `<svg class="ch-svg" viewBox="0 0 1920 1080" width="1920" height="1080" aria-hidden="true">${svg}</svg>${html}</div>` +
    `${over}${head}</div></div></div>`;
}

/**
 * A heading's or caption's text as HTML. A figure in it that this shot speaks (a {{key}} the plan
 * filled with a value revealed in this shot) is set as its own span that lands on its word, so
 * "From day 271" never reads "271" before "271" is said; a figure the voice said before stands.
 */
function says(job, text) {
  const s = String(text ?? "");
  const known = new Set(Object.values(job.known || {}).map(String));
  const hits = [];
  const mine = (job.reveals || []).filter((r) => r.value && Number.isFinite(+r.t) && !known.has(String(r.value)))
    .sort((p, q) => String(q.value).length - String(p.value).length);
  for (const r of mine) {
    const v = String(r.value);
    for (let i = s.indexOf(v); i >= 0; i = s.indexOf(v, i + v.length)) {
      if (!hits.some(([a, b]) => i < b && i + v.length > a)) hits.push([i, i + v.length, spoken(job, r)]);
    }
  }
  hits.sort((p, q) => p[0] - q[0]);
  let out = "", k = 0;
  for (const [a, b, t] of hits) {
    out += esc(s.slice(k, a)) + `<span class="ch-hfig ch-land" style="${at(t)}">${esc(s.slice(a, b))}</span>`;
    k = b;
  }
  return out + esc(s.slice(k));
}

/** Heading and caption: Fraunces at its own size (the --heading-font token), Inter for the caption. */
function heading(job, { kicker, title, caption, captionAt = -0.4 }) {
  if (!kicker && !title && !caption) return "";
  return `<header class="ch-head">` +
    (kicker ? `<p class="ch-kicker ch-in" style="${at(-0.4)}">${says(job, kicker)}</p>` : "") +
    (title ? `<h2 class="ch-title ch-in" style="${at(-0.4)}">${says(job, title)}</h2>` : "") +
    (caption ? `<p class="ch-cap ch-in" style="${at(early(captionAt))}">${says(job, caption)}</p>` : "") +
    `</header>`;
}

/** A label at frame coordinates; anchor a: "l" | "r" | "c", v: "t" | "m" | "b". Records its box for the grid's mask. */
function labeller() {
  const boxes = [];
  const est = (text, px, caps) => String(text).length * px * (caps ? 0.8 : 0.58);
  const label = (x, y, inner, { cls = "", t = 0, a = "l", v = "m", w = 0, h = 0 } = {}) => {
    if (w && h) {
      const x0 = a === "r" ? x - w : a === "c" ? x - w / 2 : x, y0 = v === "b" ? y - h : v === "m" ? y - h / 2 : y;
      boxes.push([x0 - 14, y0 - 10, w + 28, h + 20]);
    }
    const tx = a === "r" ? "-100%" : a === "c" ? "-50%" : "0", ty = v === "b" ? "-100%" : v === "m" ? "-50%" : "0";
    return `<div class="ch-lab ${cls}" style="left:${r1(x)}px;top:${r1(y)}px;translate:${tx} ${ty};${at(t)}">${inner}</div>`;
  };
  /** Rules drawn after the labels, cut wherever a label sits over them (a cut, not a mask: R4). */
  const rules = [];
  const rule = (x0, x1, y, cls = "ch-grid", vertical = false) => rules.push({ x0, x1, y, cls, vertical });
  const grid = () => rules.map(({ x0, x1, y, cls, vertical }) => {
    const cuts = boxes.filter(([bx, by, bw, bh]) => vertical ? y >= bx && y <= bx + bw : y >= by && y <= by + bh)
      .map(([bx, by, bw, bh]) => (vertical ? [by, by + bh] : [bx, bx + bw])).sort((p, q) => p[0] - q[0]);
    const segs = [];
    let a = Math.min(x0, x1);
    const b = Math.max(x0, x1);
    for (const [c0, c1] of cuts) { if (c1 <= a || c0 >= b) continue; if (c0 > a) segs.push([a, c0]); a = Math.max(a, c1); }
    if (a < b) segs.push([a, b]);
    const d = segs.map(([p, q]) => (vertical ? `M${r1(y)},${r1(p)} V${r1(q)}` : `M${r1(p)},${r1(y)} H${r1(q)}`)).join(" ");
    return d ? `<path class="${cls} ch-fade" style="${at(-0.8, 0.6)}" d="${d}"/>` : "";
  }).join("");
  /** Keep a region clear of the grid (a ledger or label that sits outside the labeller). */
  const keep = (x, y, w, h) => boxes.push([x, y, w, h]);
  return { label, est, rule, grid, keep, boxes };
}

/** A figure that lands (S3): blur, scale and tracking settle on its word; money then blooms. */
const fig = (text, t, { cls = "", money = false } = {}) =>
  `<span class="ch-fig ch-land${money ? " money" : ""}${cls ? ` ${cls}` : ""}" style="${at(t)}">${esc(text)}</span>`;
/** A unit beside its figure: 0.3 of its size (never under 28 px), italic, ivory 70%, never blue. */
const unit = (text, px, t) => `<span class="ch-unit-t ch-in" style="font-size:${Math.max(28, Math.round(px * 0.3))}px;${at(t)}">${esc(text)}</span>`;

/** Light falling on the desk around a figure as it lands; and the plot's light spilling below its baseline. */
const bloom = (x, y, r, t, d = 1.4, cls = "") =>
  `<div class="ch-bloom ${cls}" style="left:${r1(x - r)}px;top:${r1(y - r)}px;width:${2 * r}px;height:${2 * r}px;${at(t, d)}"></div>`;
const spill = (x0, x1, y) => `<div class="ch-spill" style="left:${r1(x0)}px;top:${r1(y - 70)}px;width:${r1(x1 - x0)}px;height:200px;${at(-0.8, 1.2)}"></div>`;
const flare = (x, y, t) => `<div class="ch-flare" style="left:${r1(x)}px;top:${r1(y)}px;${at(t)}"></div>`;

/** A stroke of light: a wide faint halo under a crisp core, drawn on together (no filter: R4). */
const light = (d, t, dur, { cls = "ch-line", halo = "ch-halo", extra = "" } = {}) =>
  `<path class="${halo} ch-draw${extra}" pathLength="1" style="${at(t, dur)}" d="${d}"/><path class="${cls} ch-draw${extra}" pathLength="1" style="${at(t, dur)}" d="${d}"/>`;

// ---------------------------------------------------------------- the fee staircase

/**
 * The fulfilment fee staircase (built.charts.stairs), across the frame: weight from 0 to 16 oz over
 * x 236–1516, the fee scale at its right. The card in force draws on tread by tread, each riser
 * snapping up; the peak card wipes on as a dashed ghost. The listing's dot lands at its weight and the
 * hollow dot one step down; the riser between them is the leak, the frame's one blue, with its per-unit
 * figure in the ledger in the empty upper left (the staircase rises away from it), on its word.
 *
 * The staircase returns in several shots, and each return takes its own camera: the first appearance
 * opens wide with its first treads drawn and dives into the riser as the figure lands ("establish");
 * a quick return opens tight on the riser, already standing, and pulls back ("pull"; far back, the
 * chart small under its heading, when nothing new lands in it); a long build opens close on the edge,
 * opens out as its points land and dives into the riser at the end ("build"); a chart-build racks
 * focus to the listing ("rack").
 *
 * params.builds, in order, by count:
 *  - counterfactual, up to 5: the treads drawn, the listing, one step down, the riser, the peak card;
 *  - counterfactual, 6: the treads drawn, the line (the edge's riser lights), the listing, a product
 *    mid-tread (an ivory marker, no figure: "a product sitting in the middle of a tread is not"), the
 *    peak card, one step down with the riser;
 *  - chart-build, 4: the treads begin, the treads drawn, the peak card, the listing with one step
 *    down and the riser;
 *  - chart-build, 5: the treads drawn, the peak card, the listing, one step down, the riser.
 * A build at the cut (≤ 0.45 s) stands at frame 0.
 */
function staircase(job, built, C, uid) {
  const st = built.charts.stairs;
  const { S, on, rv, build, n, ret } = C;
  const L = labeller();
  const cf = job.style !== "chart-build";
  const xMax = 16;
  const tr = st.treads.filter(([e]) => e <= xMax), al = st.alt.filter(([e]) => e <= xMax);
  const fees = [...tr, ...al].map(([, f]) => f);
  const lo = Math.min(...fees), hi = Math.max(...fees);
  const yt = niceTicks(lo - 0.15, hi + 0.1, 4);
  const d0 = Math.min(yt[0], lo - 0.15), d1 = Math.max(yt[yt.length - 1], hi + 0.1);
  const P = { l: 236, r: 1516, t: 330, b: floorOf(job) };
  const X = lin(0, xMax, P.l, P.r), Y = lin(d0, d1, P.b, P.t);
  const feeAt = (rows, oz) => (rows.find(([e]) => oz <= e) || rows[rows.length - 1])[1];
  const ex = X(st.edge.oz), yLo = Y(st.edge.fee), yHi = Y(st.listing.fee), lx = X(st.listing.oz);
  const peakLo = feeAt(al, st.edge.oz), peakHi = feeAt(al, st.listing.oz);
  const stepTxt = `+${cents(st.step)}`, peakTxt = `+${cents(peakHi - peakLo)}`;

  // ---- time, from the words and the plan's builds
  const R = rv("cs_step"), E = rv("cs_edge"), PK = rv("cs_step_peak"), U = rv("cs_units");
  const order = cf ? (n >= 6 ? ["tread", "line", "list", "mark", "peak", "edge"] : ["tread", "list", "edge", "riser", "peak"])
    : n === 4 ? ["start", "tread", "peak", "list"] : ["tread", "peak", "list", "edge", "riser"];
  const bt = (k) => { const i = order.indexOf(k); return i < 0 ? null : build(i); };
  const cut = (t) => (t != null && t <= AT_CUT ? DONE : t);    // a build at the cut already stands
  const quick = ret || (on ?? 9) < 3;                           // a return, or a beat inside its first 3 s
  const variant = R || E ? "establish" : !cf ? "rack" : quick ? "pull" : "build";
  let listT = null, edgeT, riserT, lineT = null, markT = null;
  if (cf) {
    edgeT = E?.at ?? cut(bt("edge")) ?? (on ?? S * 0.45);
    riserT = R?.at ?? cut(bt("riser")) ?? (order.includes("riser") ? snap(job, edgeT + 0.35) : edgeT);
    lineT = cut(bt("line"));
    markT = cut(bt("mark"));
  } else {
    listT = cut(bt("list")) ?? on ?? S * 0.45;
    const chain = !order.includes("edge");                       // the 4-build form: dot, step down and riser as one beat
    edgeT = cut(bt("edge")) ?? (listT === DONE ? DONE : chain ? listT + 0.15 : snap(job, listT + 0.3));
    riserT = cut(bt("riser")) ?? (edgeT === DONE ? DONE : chain ? listT + 0.3 : snap(job, edgeT + 0.3));
  }
  // the pen: on a return the treads already stand; a first appearance opens with its first treads on
  const standing = variant === "pull" || cut(bt("tread")) === DONE;
  let drawA, drawB;
  if (standing) { drawA = DONE - 1.6; drawB = DONE; }
  else {
    drawA = Math.min(bt("start") ?? -0.9, -0.6);
    const next = Math.min(...[edgeT, riserT, listT, lineT, markT].filter((t) => t != null && t > drawA + 1));
    drawB = clamp(bt("tread") ?? cue(job, /^tread|^staircase/, 0.8, next - 0.2) ?? next - 0.3, drawA + 1.6, drawA + 3.2);
  }
  const anchor = !standing && E && E.at > drawA + 0.6 ? E.at : null;     // the pen reaches the edge as "8" is spoken
  if (anchor) drawB = Math.max(drawB, anchor + 0.9);
  if (cf) listT = cut(bt("list")) ?? (edgeT < riserT - 1.5 ? snap(job, (edgeT + riserT) / 2) : null) ?? (cue(job, /candidate|listing|product/, drawB, edgeT - 0.3) ??
    clamp(snap(job, (drawB + edgeT) / 2), drawB + 0.15, Math.max(drawB + 0.15, edgeT - 0.4)));
  const ghostT = PK?.at ?? cut(bt("peak")) ?? cue(job, /^staircases$|^peak$/, 0.5) ??
    (standing ? DONE : cf ? (riserT + 2.4 <= S - 1.6 ? snap(job, riserT + 2.4) : drawB + 0.6) : snap(job, (drawB + listT) / 2));
  const npT = standing ? DONE : cue(job, /^non-peak$/, 0) ?? Math.max(early(drawB - 0.4), 0.2);
  const pkT = ghostT === DONE ? DONE : cue(job, /^peak$/, ghostT - 0.1) ?? ghostT + 1.0;
  const labT = cf || listT === DONE || riserT + 2.2 > S - 0.8 ? null : snap(job, riserT + 2.2);

  // ---- the scale: rules, ticks and the axis name (dimmed when the camera moves in past them)
  let scale = "", svg = "", under = "", html = "", over = "", near = "";
  yt.forEach((v) => {
    L.rule(P.l, P.r, Y(v));
    scale += `<text class="ch-tick ch-in" x="${P.r + 26}" y="${r1(Y(v))}" dominant-baseline="central" style="${at(-0.8)}">$${v.toFixed(2)}</text>`;
  });
  for (const [edge] of [[0], ...tr]) L.rule(P.t - 10, P.b, X(edge), "ch-edge", true);
  scale += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-1.0, 0.8)}" d="M${P.l},${P.b} H${P.r}"/>`;
  const hotT = lineT ?? edgeT;
  for (const [edge] of [[0], ...tr]) {
    const hot = edge === st.edge.oz;
    scale += `<text class="ch-tick ch-in${hot ? " ch-hot" : ""}" x="${r1(X(edge))}" y="${P.b + 44}" text-anchor="middle" style="${at(-0.8)}${hot ? `;--hot:${s3(hotT)}` : ""}">${edge}${edge === xMax ? " oz" : ""}</text>`;
  }
  scale += `<text class="ch-axisname ch-in" x="${P.r + 104}" y="${P.t - 52}" text-anchor="end" style="${at(-0.8)}"><tspan>Fee</tspan><tspan x="${P.r + 104}" dy="32">a unit</tspan></text>`;

  // the peak card: a dashed ghost wiped on; its own riser dashed blue when its figure is spoken
  let ghost = `M${r1(X(0))},${r1(Y(al[0][1]))}`;
  al.forEach(([edge, fee], i) => { ghost += ` H${r1(X(edge))}`; if (i + 1 < al.length) ghost += ` V${r1(Y(al[i + 1][1]))}`; });
  svg += `<g class="ch-wipe" style="${at(early(ghostT), 1.4)}"><path class="ch-ghost" d="${ghost}"/></g>`;
  if (PK) svg += `<g class="ch-wipe-up" style="${at(PK.at, 0.45)}"><path class="ch-ghost-leak" d="M${r1(ex)},${r1(Y(peakLo))} V${r1(Y(peakHi))}"/></g>`;

  // the card in force, tread by tread, each riser snapping up with a flare at its top
  const segs = [];
  let x0 = 0;
  tr.forEach(([edge, fee], i) => {
    segs.push({ k: "t", d: `M${r1(X(x0))},${r1(Y(fee))} H${r1(X(edge))}`, len: X(edge) - X(x0), i });
    if (i + 1 < tr.length) segs.push({ k: "r", d: `M${r1(X(edge))},${r1(Y(fee))} V${r1(Y(tr[i + 1][1]))}`, len: Y(fee) - Y(tr[i + 1][1]), i, x: X(edge), y: Y(tr[i + 1][1]) });
    x0 = edge;
  });
  const RISE = 0.18;
  const timeSegs = (list, a, b) => {
    const nr = list.filter((s) => s.k === "r").length, tl = list.filter((s) => s.k === "t").reduce((m, s) => m + s.len, 0);
    const rate = Math.max(0.05, b - a - nr * RISE) / tl;
    let t = a;
    for (const s of list) { s.t = t; s.dur = s.k === "r" ? RISE : s.len * rate; t += s.dur; }
  };
  const ei = tr.findIndex(([e]) => e === st.edge.oz);
  const split = segs.findIndex((s) => s.k === "t" && s.i === ei) + 1;
  if (anchor && split > 0 && split < segs.length) { timeSegs(segs.slice(0, split), drawA, anchor); timeSegs(segs.slice(split), anchor, drawB); }
  else timeSegs(segs, drawA, drawB);
  let stairs = "";
  for (const s of segs) stairs += light(s.d, s.t, s.dur, { extra: s.k === "r" ? " ch-riser" : "" });
  if (!standing) for (const s of segs.filter((q) => q.k === "r")) under += flare(s.x, s.y, s.t + s.dur - 0.05);
  under += spill(P.l - 60, P.r + 60, P.b);

  // each card named above its last tread, when the voice names it
  const nameL = (txt, y, t, cls) => L.label(P.r, y, txt, { cls: `ch-name ${cls} ch-in`, t, a: "r", v: "b", w: L.est(txt, 28, true), h: 30 });
  const names = nameL("Non-peak", Y(tr[tr.length - 1][1]) - 14, npT, "") + nameL("Peak", Y(al[al.length - 1][1]) - 14, pkT, "ch-name--ghost");
  html += `<div class="ch-layer ch-names-${uid}">${names}</div>`;

  // the line: the edge's riser lights in ivory as the voice names "a line"
  if (lineT != null) {
    near += light(`M${r1(ex)},${r1(yLo)} V${r1(yHi)}`, lineT - 0.1, 0.3, { cls: "ch-line-hot", halo: "ch-halo-hot" });
    if (lineT > 0) under += flare(ex, yHi, lineT);
  }

  // the leak: the riser between one step down and this listing, in blue, lighting the desk
  under += bloom(ex, (yLo + yHi) / 2, 230, riserT);
  near += light(`M${r1(ex)},${r1(yLo)} V${r1(yHi)}`, riserT, 0.4, { cls: "ch-leak", halo: "ch-leak-halo" });

  // the listing's dot: a thread of light rises from its weight and the dot lands on its tread;
  // one step down, the hollow dot at the edge
  near += `<path class="ch-thread ch-draw" pathLength="1" style="${at(listT - 0.5, 0.5)}" d="M${r1(lx)},${P.b} V${r1(yHi + 13)}"/>`;
  if (listT > 0) near += `<circle class="ch-ripple" cx="${r1(lx)}" cy="${r1(yHi)}" r="11" style="${at(listT + 0.3)}"/>`;
  near += `<circle class="ch-dot ch-drop" cx="${r1(lx)}" cy="${r1(yHi)}" r="11" style="${at(listT)}"/>`;
  if (edgeT > 0) near += `<circle class="ch-ripple" cx="${r1(ex)}" cy="${r1(yLo)}" r="10" style="${at(edgeT)}"/>`;
  near += `<circle class="ch-dot-hollow ch-pop" cx="${r1(ex)}" cy="${r1(yLo)}" r="10" style="${at(edgeT)}"/>`;
  const dotLab = labT ?? (listT === DONE ? DONE : listT + 0.25), edgeLab = labT ? labT + 0.25 : edgeT === DONE ? DONE : edgeT + 0.25;
  // its weight only as the voice gives it (cs_weight), else the words alone
  const wTxt = `${st.listing.oz.toFixed(1)} oz`, wT = saidAt(job, wTxt);
  const fg = L.label(lx + 22, yHi + 22, `${wT != null ? `<b class="ch-fig ch-fig-s ch-land" style="${at(Math.max(dotLab, wT))}">${esc(wTxt)}</b>` : ""}<i>this listing</i>`,
    { cls: "ch-dotlab ch-in", t: dotLab, v: "t", w: 250, h: 80 });
  html += L.label(ex - 22, yLo + 22, `<i>one step</i><i>down</i>`, { cls: "ch-dotlab ch-dotlab--r ch-in", t: edgeLab, a: "r", v: "t", w: 170, h: 70 });

  // a product mid-tread: an ivory marker, no figure, on the tread above the listing's
  if (markT != null) {
    const ti = tr.findIndex(([e]) => st.listing.oz <= e), k = ti > 0 ? 0 : 1;
    const mx = X(((k ? tr[k - 1][0] : 0) + tr[k][0]) / 2), my = Y(tr[k][1]);
    if (markT > 0) near += `<circle class="ch-ripple" cx="${r1(mx)}" cy="${r1(my)}" r="10" style="${at(markT + 0.3)}"/>`;
    near += `<circle class="ch-mark ch-drop" cx="${r1(mx)}" cy="${r1(my)}" r="10" style="${at(markT)}"/>`;
    // named in words only, above it (it has no weight to give: no thread to the axis)
    html += L.label(mx, my - 24, `<i>mid-tread</i>`, { cls: "ch-dotlab ch-in", t: markT + 0.2, a: "c", v: "b", w: L.est("mid-tread", 28, true), h: 30 });
  }

  // the counterfactual bracket on the riser
  if (cf) {
    const bx = ex - 30;
    near += `<path class="ch-bracket ch-draw" pathLength="1" style="${at(riserT + 0.1, 0.45)}" d="M${r1(bx + 14)},${r1(yLo)} H${r1(bx)} V${r1(yHi)} H${r1(bx + 14)}"/>`;
  }

  // ---- the ledger, upper left, where the staircase rises away: the step, the peak card's step, the units.
  // One blue figure: the peak step when this shot speaks it, else the step.
  const stepT0 = cf ? (R?.at ?? (riserT === DONE ? DONE : Math.max(riserT, cue(job, /differen|riser|turn/, riserT - 0.5) ?? riserT + 0.3))) : riserT === DONE ? DONE : riserT + 0.3;
  const stepSaid = saidAt(job, stepTxt);
  // a figure the voice said before lands with its riser, never as a flash in the last moments of the shot
  const figT = stepSaid == null ? null : R ? R.at : stepT0 > S - 0.9 ? null : stepT0;
  const peakT = PK ? PK.at : ghostT === DONE && saidAt(job, peakTxt) === DONE ? DONE : null;
  const lx0 = 160, ly0 = P.t - 6;
  const big = R ? 120 : 96;
  let rows = "";
  if (figT != null) {
    rows += `<div class="ch-row">${fig(stepTxt, figT, { money: !PK, cls: R ? "ch-fig-l" : "ch-fig-m" })}${unit("a unit", big, figT === DONE ? DONE : cue(job, /^unit/, figT + 0.2) ?? figT + 0.3)}</div>`;
    L.keep(lx0 - 14, ly0 - 10, 640, big + 24);
  }
  if (peakT != null) {
    rows += `<div class="ch-row ch-row--2">${fig(peakTxt, peakT, { money: !!PK, cls: "ch-fig-s2" })}${unit("on the peak card", 72, peakT === DONE ? DONE : pkT)}</div>`;
    L.keep(lx0 - 14, ly0 + big + 30, 640, 100);
  }
  if (U) {
    const v = String(U.value || ""), m = v.match(/\d[\d,.]*/);
    const num = m ? m[0] : v, pre = m ? v.slice(0, m.index).trim() : "", post = m ? v.slice(m.index + m[0].length).trim() : "";
    const preT = cue(job, /^estimat/, U.t - 0.3) ?? U.at - 0.4;
    rows += `<div class="ch-row ch-row--3">${pre ? `<p class="ch-eyebrow ch-in" style="${at(Math.min(preT, U.at))}">${esc(pre)}</p>` : ""}` +
      `<div class="ch-row">${fig(num, U.at, { cls: "ch-fig-s2" })}${unit(post, 72, cue(job, /^units?$/, U.at + 0.1) ?? U.at + 0.4)}</div></div>`;
  }
  if (rows) over += `<div class="ch-ledger" style="left:${lx0}px;top:${ly0}px">${rows}</div>`;

  // ---- depth: a chart-build racks focus to the listing on its word
  let depth = "";
  if (variant === "rack" && listT > 0 && listT + 2.5 < S) depth = `.ch-rack-${uid}{animation:ch-rack 3.6s linear ${s3(listT - 0.2)}s both}`;

  // ---- the camera's own move, on the plot layer
  const fR = { x: ex, y: (yLo + yHi) / 2 }, fL = { x: lx + 70, y: yHi + 24 };
  const centre = { x: (P.l + P.r + 110) / 2, y: (P.t + P.b) / 2 };
  const still = !R && !PK && !E && !U && markT == null && lineT == null && [listT, edgeT, riserT].every((t) => t === DONE);
  const pullEnd = still ? (cue(job, /^staircase/, 0.5) ?? 1.6) + 1.7 : Math.min(S - 0.5, Math.max(2.2, ghostT + 1.4));
  const keys = {
    establish: [{ t: 0, s: 1 }, { t: Math.max(0.2, riserT - 0.4), s: 1 }, { t: riserT + 2.4, ...pin(fR, 1.12) }, { t: S, ...pin(fR, 1.14) }],
    pull: [{ t: 0, ...pin(fR, 1.5, 1010, 580) }, { t: pullEnd, ...(still ? pin(centre, 0.93, 960, 590) : { s: 1 }) }],
    build: [{ t: 0, ...pin(fR, 1.16, 1060, 600) }, { t: Math.max(1.2, (markT ?? listT) - 0.6), s: 1 }, { t: Math.max(1.4, edgeT - 0.5), s: 1 }, { t: Math.min(S, edgeT + 2.4), ...pin(fR, 1.1) }],
    rack: [{ t: 0, s: 1 }, { t: Math.max(0.1, listT - 0.6), s: 1 }, { t: Math.min(S, listT + 2), ...pin(fL, 1.03) }],
  }[variant];
  const nameTop = Y(al[al.length - 1][1]) - 60;
  const css = camera(uid, S, keys, [{ cls: `ch-scale-${uid}`, box: { l: P.l - 30, r: P.r + 110, t: P.t - 92, b: P.b + 64 } },
    { cls: `ch-names-${uid}`, box: { l: P.r - 200, r: P.r + 4, t: nameTop, b: Y(tr[tr.length - 1][1]) - 8 } }]) + depth;

  const p = job.params || {};
  const dashed = /dash/i.test(p.caption || "");
  const head = heading(job, { title: p.heading, caption: p.caption, captionAt: dashed && ghostT > AT_CUT ? ghostT + 0.3 : -0.4 });
  svg = `<g class="ch-rack-${uid}"><g class="ch-scale-${uid}">${L.grid()}${scale}</g>${svg}${stairs}</g>${near}`;
  return stage({ uid, S, css, under, svg, html: `<div class="ch-layer ch-rack-${uid}">${html}</div>${fg}`, over, head });
}

// ---------------------------------------------------------------- the Monte Carlo

/**
 * The simulated years of one listing (built.charts.mc), as the simulation runs: month by month, a
 * column of points (one per simulated year the data carries) lands, with each year's faint thread
 * drawn behind it. The middle year draws as the brightest line; the slow and strong years' lines
 * land in the light; the band between them fills, ivory at 10%, and a bracket closes it.
 *
 * No figure the film does not say (round 3, the critics' severity 1): the data is a year of
 * cumulative profit, which the voice never quotes, so the chart carries no scale and no end values.
 * Its ends are named in words ("A strong year", "A slow year"); the bracket says the band's share in
 * the voice's own words when the film has said it ({{cs_band_share}}, "eight in ten"); the count of
 * years ({{cs_years}}) names the chart when the film has said it. Nothing in it is blue: no money is
 * named. The chart fills the frame's width, so its camera moves in height and depth.
 * params.builds, in order: 6 — the months begin, the months run out, the middle year, the slow year,
 * the strong year, the band; up to 5 — the months run out, the middle, slow, strong, the band.
 */
function montecarlo(job, built, C, uid) {
  const mc = built.charts.mc;
  const { S, on, build, n: nB } = C;
  const L = labeller();
  const p = job.params || {};
  const P = { l: 176, r: 1340, t: Math.max(300, headFoot(p) + 70), b: floorOf(job) };
  const months = mc.months, n = months.length - 1;
  const all = [...mc.paths.flat(), ...mc.percentiles.p10, ...mc.percentiles.p90];
  const yLo = Math.min(0, ...all), yHi = Math.max(...all);
  const ticks = niceTicks(yLo, yHi, 4);
  const d0 = Math.min(yLo, ticks[0]), d1 = Math.max(yHi, ticks[ticks.length - 1]);
  const X = lin(months[0], months[n], P.l, P.r), Y = lin(d0, d1, P.b, P.t);
  const xs = months.map(X);
  const line = (ys) => `M${xs.map((x, i) => `${r1(x)},${r1(Y(ys[i]))}`).join(" L")}`;
  const band = (top, bot) => `M${xs.map((x, i) => `${r1(x)},${r1(Y(top[i]))}`).join(" L")} L${xs.map((x, i) => [x, i]).reverse().map(([x, i]) => `${r1(x)},${r1(Y(bot[i]))}`).join(" L")} Z`;
  const { p10, p50, p90 } = mc.percentiles;

  // ---- time: the months run first; the middle on "number", the ends on "slow" / "strong", the band on "range"
  const six = nB >= 6, b = (i) => build(six ? i + 1 : i);
  const variant = on != null && on >= 0.45 * S ? "truck" : "push";
  const runA = six ? Math.min(build(0) - 0.9, -0.3) : variant === "truck" ? -0.3 : -1.1;   // the run is under way at the cut
  const named = b(1) ?? cue(job, /^number|^median|^middle/, 0.6);
  const runB = clamp(b(0) ?? Math.min((on ?? S * 0.5) - 1.0, (named ?? Infinity) - 0.15), runA + 1.4, runA + 3.2);
  const step = (runB - runA) / n;
  const medT = named ?? snap(job, runB + 0.2);
  const lowT = b(2) ?? cue(job, /^slow|^low|^bad/, medT + 0.3) ?? snap(job, (on ?? runB + 1) + 0.3);
  const highT = b(3) ?? cue(job, /^strong|^high|^good/, lowT + 0.2) ?? snap(job, lowT + 0.8);
  const bandT = b(4) ?? cue(job, /^range/, highT) ?? on ?? highT + 0.6;
  const fillT = Math.max(bandT, highT + 0.3);

  // ---- svg: unlabelled rules for structure, the zero line, the year's span in words
  let svg = "", html = "";
  ticks.forEach((v) => { if (v !== 0) L.rule(P.l, P.r, Y(v)); });
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-1.0, 0.8)}" d="M${P.l},${r1(Y(0))} H${P.r}"/>`;
  svg += `<text class="ch-tick ch-in" x="${P.l}" y="${P.b + 44}" style="${at(-0.8)}">Today</text>`;
  if (months[n] === 12) svg += `<text class="ch-tick ch-in" x="${P.r}" y="${P.b + 44}" text-anchor="end" style="${at(-0.8)}">A year</text>`;
  // the chart's name: the count of years only as the voice gives it
  const yrs = built.fill?.years, yrsT = yrs ? saidAt(job, yrs) : null;
  svg += `<text class="ch-axisname ch-in" x="${P.l}" y="${P.t - 40}" style="${at(-0.8)}">` +
    (yrsT != null ? `<tspan class="ch-land" style="${at(yrsT)}">${esc(yrs)} </tspan>simulated years` : "Simulated years") + `</text>`;

  // the band, born on the middle line, filling on its word
  svg += `<path class="ch-band ch-band-${uid}" d="${band(p50, p50)}" style="${at(fillT, clamp(S - fillT - 0.1, 0.4, 0.9))}"/>`;
  // every simulated year's thread, wiped on as the months run; a column of points lands each month
  let cloud = `<g class="ch-threads ch-wipe" style="${at(runA, runB - runA + 0.2)}">` + mc.paths.map((q) => `<path d="${line(q)}"/>`).join("") + `</g>`;
  months.forEach((_, i) => {
    if (i === 0) return;
    cloud += `<g class="ch-month ch-pop-col" style="${at(runA + step * i)}">` +
      mc.paths.map((q) => `<circle cx="${r1(xs[i])}" cy="${r1(Y(q[i]))}" r="3.2"/>`).join("") + `</g>`;
  });
  // the slow and strong years' lines, then the middle, brightest
  svg += light(line(p10), lowT - 0.5, 0.6, { cls: "ch-pct", halo: "ch-pct-halo" });
  svg += light(line(p90), highT - 0.5, 0.6, { cls: "ch-pct", halo: "ch-pct-halo" });
  svg += light(line(p50), medT - 0.75, 0.75, { cls: "ch-median", halo: "ch-median-halo" });
  svg += `<circle class="ch-end-dot ch-pop" cx="${r1(xs[n])}" cy="${r1(Y(p50[n]))}" r="8" style="${at(medT)}"/>`;

  // the ends, named in words; the bracket closes the band with its share
  const y90 = Y(p90[n]), y10 = Y(p10[n]), bx = P.r + 22;
  svg += `<path class="ch-brace ch-draw" pathLength="1" style="${at(fillT + 0.1, 0.5)}" d="M${bx - 10},${r1(y90)} H${bx} V${r1(y10)} H${bx - 10}"/>`;
  // the band holds the years between its two percentiles: P10 to P90 is eight in ten, in the voice's words
  const inTen = Math.round((90 - 10) / 10), TEN = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const shareTxt = `${TEN[inTen]} in ten`, shareT = saidAt(job, shareTxt);
  const nameAt = (y, txt, t, cls = "") => L.label(bx + 26, y, txt.split("\n").map((x) => `<i class="ch-in" style="${at(t)}">${esc(x)}</i>`).join(""), { cls: `ch-endlab ${cls}`, v: "m" });
  let yS = y90, yW = y10;
  if (yW - yS < 150) { const m = (yS + yW) / 2; yS = m - 75; yW = m + 75; }
  html += nameAt(yS, "A strong year", highT);
  html += nameAt(yW, "A slow year", lowT);
  html += nameAt((yS + yW) / 2, shareT != null ? `${shareTxt.charAt(0).toUpperCase()}${shareTxt.slice(1)}\nyears` : "Most years", Math.max(fillT + 0.2, shareT ?? 0), "ch-endlab--band");

  const under = spill(P.l - 60, P.r + 60, Y(0)) + `<div class="ch-glow-soft" style="left:${r1(xs[n] - 200)}px;top:${r1(Y(p50[n]) - 200)}px;${at(medT, 1.4)}"></div>`;
  const keys = variant === "truck"
    ? [{ t: 0, dy: 44 }, { t: runB + 0.6, dy: 6 }, { t: S, dy: 0 }]
    : [{ t: 0, dy: -10 }, { t: S, dy: 14 }];
  const rack = `.ch-rack-${uid}{animation:ch-recede 0.8s ease ${s3(fillT - 0.3)}s both}`;
  const css = `@keyframes chb-${uid}{from{d:path("${band(p50, p50)}");opacity:0}to{d:path("${band(p90, p10)}");opacity:1}}` +
    `.ch-band-${uid}{animation:chb-${uid} calc(var(--d)*1s) var(--ease-out) calc(var(--at)*1s) both}` +
    pushCSS(uid, S, keys, { l: 160, r: 1680, t: P.t - 70, b: P.b + 60 }, { top: headFoot(p) + 8 }) + rack;
  const head = heading(job, { title: p.heading, caption: p.caption });
  svg = `${L.grid()}<g class="ch-rack-${uid}">${cloud}</g>${svg}`;
  return stage({ uid, S, css, under, svg, html, head });
}

// ---------------------------------------------------------------- the aging cliff

/**
 * What a listing's units cost to store a month by age (built.charts.aging). A playhead walks the
 * units' age from day 0 and each band draws up from the baseline as it is reached, the last below
 * the cliff on its spoken days; at the cliff day the bands beyond it draw up fast, in blue (the
 * leak), the riser flashes and the camera takes the hit. The spoken surcharge rates land in a
 * ledger above the young stock.
 * params.builds, in order: each band below the cliff after the first; then the cliff, unless its day is spoken.
 */
function aging(job, built, C, uid) {
  const ag = built.charts.aging;
  const { S, on, rv, build } = C;
  const L = labeller();
  const xMax = 400;
  const P = { l: 330, r: 1640, t: 330, b: floorOf(job) };
  const vals = ag.bands.map((b) => b.value);
  const yt = niceTicks(0, Math.max(...vals) * 1.08, 3);
  const d1 = Math.max(yt[yt.length - 1], Math.max(...vals) * 1.08);
  const X = lin(0, xMax, P.l, P.r), Y = lin(0, d1, P.b, P.t);
  const ci = ag.bands.findIndex((b) => b.from === ag.cliff);
  if (ci < 1) return fallback(job, built, C, uid);          // no band begins at the cliff: draw nothing we cannot show
  const pre = ag.bands.slice(0, ci), post = ag.bands.slice(ci);
  const right = (b) => X(Math.min(b.to == null ? xMax : b.to + 1, xMax));
  const bandPre = pre[pre.length - 1];

  // ---- time, from the words
  const dayR = rv("cs_aged_day"), bandR = rv("cs_aged_band"), before = rv("cs_aged_before"), after = rv("cs_aged_after"), units = rv("cs_aged_units");
  const cliffT = dayR?.at ?? build(pre.length - 1) ?? on ?? S * 0.6;
  const walkA = -0.4;
  // the walk: a stop at each band's first day (the last below the cliff on its words), then the cliff
  const stops = [...pre.map((b) => b.from), ag.cliff];
  let times;
  if (bandR && bandR.at > walkA + 2 && bandR.at < cliffT - 0.6) times = [...spread(pre.length - 1, walkA, bandR.at - (bandR.at - walkA) / pre.length), bandR.at, cliffT];
  else times = spread(stops.length, walkA, cliffT);
  // the editor's builds place the bands after the first (which is up at the cut), never past the cliff
  for (let i = 1; i < pre.length; i++) { const b = build(i - 1); if (b != null && !(bandR && i === pre.length - 1)) times[i] = Math.min(b, cliffT - 0.3); }
  const lead = before || after;                          // the first rate the voice gives
  const surT = lead ? cue(job, /^surcharge/, 0, lead.at) ?? lead.at : null;
  const cuT = lead ? cue(job, /^cubic/, lead.at) ?? lead.at + 0.4 : null;
  const youngT = cue(job, /^young/, cliffT);
  const p = job.params || {};
  const saysMonth = /a month/i.test(`${p.heading || ""} ${p.caption || ""}`);

  // ---- svg: the fee scale (with its rules and names) and the day scale dim apart when the camera moves in
  let svg = "", under = "", html = "", over = "", yScale = "", dScale = "";
  yt.forEach((v) => {
    if (v > 0) L.rule(P.l, P.r, Y(v));
    yScale += `<text class="ch-tick ch-in" x="${P.l - 22}" y="${r1(Y(v))}" text-anchor="end" dominant-baseline="central" style="${at(-0.4)}">$${v}</text>`;
  });
  // the scale's unit, once: "a month" unless the heading or caption already says it; the units it is for, when spoken
  const unitName = saysMonth ? "" : "A month";
  // (the scale's unit and the units it is for share one line at the scale's top)
  if (unitName) yScale += `<text class="ch-axisname ch-in" x="160" y="${P.t - 30}" style="${at(-0.4)}">${unitName}</text>`;
  if (units) yScale += `<text class="ch-axisname ch-in" x="${unitName ? 300 : 160}" y="${P.t - 30}" style="${at(units.at)}">${unitName ? "· " : ""}${esc(units.value)}</text>`;
  // the day ticks: each lands as the walk reaches it
  const dayTicks = [...new Set([...ag.ticks, ...(bandR ? [bandPre.from] : [])])].sort((m, k) => m - k);
  let lastDay = 0;
  dayTicks.forEach((d) => {
    const si = stops.indexOf(d), hot = d === ag.cliff;
    const t = d === 0 ? -0.4 : si >= 0 ? times[si] : d < ag.cliff ? times[stops.length - 1] : cliffT + 0.3;
    // every day tick is marked as the walk reaches it; its number is a figure (the schedule's thresholds), so it
    // is labelled only when this shot says it (on its word) or the film has said it before (job.known)
    svg += `<path class="ch-dtick ch-fade" style="${at(early(t), 0.4)}" d="M${r1(X(d))},${P.b} V${P.b + 12}"/>`;
    const said = saidAt(job, String(d));
    if (said == null) return;
    const tl = Math.max(early(t), said);
    if (!hot && tl < S) lastDay = Math.max(lastDay, d);
    // the cliff's day is a spoken figure: it lands on its word wherever the camera is, never dimmed with the scale
    (hot ? (x) => { svg += x; } : (x) => { dScale += x; })(`<text class="ch-tick ch-in${hot ? " ch-hot" : ""}" x="${r1(X(d))}" y="${P.b + 44}" text-anchor="${d === 0 ? "start" : "middle"}" style="${at(tl)}${hot ? `;--hot:${s3(Math.max(cliffT, tl))}` : ""}">${d === 0 ? "Day 0" : d}</text>`);
  });

  // the bands: a 2 px edge of light over a flat 6% fill, drawing up from the baseline as the walk reaches them
  const col = (b, cls, t) => {
    const x0 = X(b.from) + 3, x1 = right(b) - 3, y = Y(b.value);
    return `<g class="${cls} ch-grow" style="${at(t, 0.5)}"><rect class="ch-col-fill" x="${r1(x0)}" y="${r1(y)}" width="${r1(x1 - x0)}" height="${r1(P.b - y)}"/>` +
      `<path class="ch-col-top" d="M${r1(x0)},${r1(y)} H${r1(x1)}"/></g>`;
  };
  pre.forEach((b, i) => { svg += col(b, `ch-col${youngT != null && i === 0 ? " ch-young" : ""}`, early(times[i])); });
  post.forEach((b, i) => { svg += col(b, "ch-col ch-col--leak", cliffT + i * 0.07); });
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${P.b} H${P.r}"/>`;

  // the cliff: the riser in blue, a flash of light on the desk
  const cx = X(ag.cliff), yb = Y(bandPre.value), ya = Y(post[0].value);
  under += spill(P.l - 60, P.r + 60, P.b) + bloom(cx, (yb + ya) / 2, 300, cliffT, 1.8, "ch-bloom--hard");
  svg += light(`M${r1(cx)},${r1(yb)} V${r1(ya)}`, cliffT, 0.16, { cls: "ch-leak", halo: "ch-leak-halo" });

  // the playhead: the units' age, walking toward the cliff
  const kf = `0%{transform:translateX(0)}` + stops.map((d, i) => `${r1((Math.max(0, times[i]) / S) * 100)}%{transform:translateX(${r1(X(d) - P.l)}px)}`).join("") +
    `100%{transform:translateX(${r1(X(ag.cliff) - P.l)}px)}`;
  svg += `<g class="ch-play ch-play-${uid}" style="${at(-0.4)};--off:${s3(cliffT + 0.4)}"><path class="ch-play-line" d="M${P.l},${P.b} V${P.t - 20}"/><circle class="ch-play-dot" cx="${P.l}" cy="${P.b}" r="6"/></g>`;

  // the ledger, above the young stock: the surcharge before and after the cliff, on their words (fixed
  // over the plot's camera, so it reads still while the bands move under it)
  if (before || after) {
    const lx = P.l + 120, ly = P.t + 16;
    L.keep(lx - 14, ly - 10, 700, 150);
    if (surT != null) over += L.label(lx, ly, `<i>surcharge</i>`, { cls: "ch-eyebrow ch-in", t: surT, v: "t", w: 190, h: 30 });
    // "$1.50 a cubic foot → $5.45"; with only the rate after the cliff spoken, "$5.45 a cubic foot"
    over += L.label(lx, ly + 44, (before ? fig(before.value, before.at, { cls: "ch-fig-s2" }) + unit("a cubic foot", 72, cuT) : "") +
      (after ? `${before ? `<span class="ch-arrow ch-in" style="${at(after.at - 0.1)}">→</span>` : ""}${fig(after.value, after.at, { money: true, cls: "ch-fig-s2" })}` +
        (before ? "" : unit("a cubic foot", 72, Math.max(cuT, after.at + 0.3))) : ""),
      { cls: "ch-row", v: "t", w: 640, h: 80 });
  }

  const css = `@keyframes chw-${uid}{${kf}}.ch-play-${uid}{animation:chw-${uid} ${s3(S)}s cubic-bezier(.45,0,.3,1) 0s both, ch-fade .4s ease calc(var(--at)*1s) both, ch-out .5s ease calc(var(--off)*1s) forwards}` +
    `@keyframes chj-${uid}{0%,${r1((cliffT / S) * 100)}%{translate:0 0}${r1(((cliffT + 0.05) / S) * 100)}%{translate:0 10px}${r1(((cliffT + 0.15) / S) * 100)}%{translate:0 -4px}${r1(((cliffT + 0.32) / S) * 100)}%,100%{translate:0 0}}` +
    `.ch-jolt-${uid}{animation:chj-${uid} ${s3(S)}s linear 0s both}` +
    (youngT != null ? `.ch-young .ch-col-fill{animation:ch-young-fill 1.2s ease ${s3(youngT)}s both}` : "") + agingCam(uid, S, P, cliffT, { cx, cy: (yb + ya) / 2, walkTo: bandR?.at ?? lead?.at ?? S * 0.5,
      yBox: { l: 160, r: unitName || units ? 640 : P.l - 10, t: unitName || units ? P.t - 58 : Y(yt[yt.length - 1]) - 18, b: P.b + 16 },
      dBox: { l: P.l - 10, r: X(lastDay) + 40, t: P.b + 20, b: P.b + 56 }, rBox: { l: P.l, r: P.r, t: Y(yt[yt.length - 1]), b: P.b } });
  const head = heading(job, { title: p.heading, caption: p.caption });
  svg = `<g class="ch-rules-${uid}">${L.grid()}</g><g class="ch-yscale-${uid}">${yScale}</g><g class="ch-dscale-${uid}">${dScale}</g>${svg}`;
  return stage({ uid, S, css, under, svg: `<g class="ch-jolt-${uid}">${svg}</g>`, html: `<div class="ch-jolt-${uid} ch-layer">${html}</div>`, over, head });
}

/**
 * The aging chart's camera. A shot that ends before the cliff pushes in on the stock as it ages, so
 * the bands it is about fill the frame by the time the surcharge lands. A shot that opens on the cliff
 * (it lands in its first 1.5 s) cuts in close on the riser and pulls back after the slam to show the
 * whole of it; one that reaches the cliff later leans into it as the walk arrives, takes the hit,
 * and pulls back.
 */
function agingCam(uid, S, P, cliffT, { cx, cy, walkTo, yBox, dBox, rBox }) {
  // pushes ride on the plot's bottom-left corner, so the scale at its left and foot stays in frame
  const corner = { x: 160, y: P.b + 10 }, fC = { x: cx, y: cy };
  const keys = cliffT >= S - 0.2
    ? [{ t: 0, s: 1 }, { t: Math.max(1, walkTo - 2.4), s: 1 }, { t: Math.min(S, walkTo + 1.2), ...pin(corner, 1.3) }, { t: S, ...pin(corner, 1.34) }]
    : cliffT < 1.5
      ? [{ t: 0, ...pin(fC, 1.32, 1060, 520) }, { t: cliffT + 0.35, ...pin(fC, 1.3, 1060, 520) }, { t: Math.min(S, cliffT + 2.6), s: 1 }]
      : [{ t: 0, s: 1 }, { t: Math.max(0.2, cliffT - 1.8), s: 1 }, { t: cliffT + 0.05, ...pin(corner, 1.06) }, { t: Math.min(S, cliffT + 2.6), s: 1 }];
  // the rules too: they are cut where the ledger sits at rest, so they leave with any move that carries them off
  return camera(uid, S, keys, [{ cls: `ch-yscale-${uid}`, box: yBox }, { cls: `ch-dscale-${uid}`, box: dBox }, { cls: `ch-rules-${uid}`, box: rBox }]);
}

// ---------------------------------------------------------------- the waterfall

/**
 * One month of the film's demo catalogue, revenue to net (job.chart_data, the waterfall in the
 * film's own run.json), across the frame. Each bar draws up from its own base: revenue, then
 * Amazon's fees on "Amazon's", then landed cost, ads and net. The fees are the leak and the shot's
 * one blue: their share of revenue lands on "32.1%", their figure on "$102,395", set big beside
 * their bar. A bar carries a value only when the voice gives it (saidAt): the rest are drawn to
 * scale and named, never figured. A return (every build at the cut) stands whole at frame 0.
 * params.builds, in order: the fees, landed cost, ads, net (revenue is up at the cut).
 */
function waterfall(job, built, C, uid) {
  const w = job.chart_data;
  if (!w || !Number.isFinite(+w.revenue)) return fallback(job, built, C, uid);
  const { S, on, rv, build, ret } = C;
  const L = labeller();
  const rows = [["Revenue", 0, w.revenue, "rev"]];
  let run = w.revenue;
  for (const [name, key] of [["Amazon fees", "fees"], ["Landed cost", "cogs"], ["Ads", "ads"]]) { rows.push([name, run - w[key], run, key]); run -= w[key]; }
  rows.push(["Net", 0, w.net, "net"]);
  const P = { l: 200, r: 1640, t: 400, b: floorOf(job) };
  const Y = lin(0, w.revenue, P.b, P.t);
  const slot = (P.r - P.l) / rows.length, bw = Math.min(190, slot * 0.6);
  const cxOf = (i) => P.l + slot * (i + 0.5);

  // ---- the figures the voice gives, and when
  const heroTxt = `${MINUS}${money0(w.fees)}`, heroAt = saidAt(job, heroTxt);
  const shareTxt = `${((100 * w.fees) / w.revenue).toFixed(1)}%`, shareAt = saidAt(job, shareTxt);

  // ---- time, from the words
  const heroT = heroAt ?? on ?? S * 0.5;
  const feesT = build(0) ?? cue(job, /^amazon/, 1, heroT) ?? (shareAt > 0 ? shareAt - 4.5 : heroT - 2.2);
  const restA = snap(job, Math.max(heroT, shareAt ?? 0) + 1.3);
  const restT = spread(3, Math.min(restA, S - 4.2), Math.min(restA + 3, S - 1.2)).map((t, i) => build(i + 1) ?? t);
  const T = ret ? rows.map(() => DONE) : [-0.4, Math.max(0.8, feesT), ...restT];

  // ---- svg
  let scale = `<path class="ch-axis ch-draw" pathLength="1" style="${at(ret ? DONE : -1.0, 0.8)}" d="M${P.l - 30},${P.b} H${P.r + 30}"/>`;
  let svg = "", html = "";
  rows.forEach(([name, lo, hi, key], i) => {
    const x0 = cxOf(i) - bw / 2, y0 = Y(hi), y1 = Y(lo), h = Math.max(2, y1 - y0);
    const cls = key === "fees" ? "ch-bar--leak" : "";
    svg += `<g class="ch-bar ${cls} ch-grow" style="${at(T[i], 0.5)}"><rect class="ch-bar-fill" x="${r1(x0)}" y="${r1(y0)}" width="${r1(bw)}" height="${r1(h)}"/>` +
      `<path class="ch-bar-edge" d="M${r1(x0)},${r1(y0)} H${r1(x0 + bw)}"/></g>`;
    if (i + 1 < rows.length && rows[i + 1][3] !== "net") {
      const yl = Y(key === "rev" ? hi : lo);
      svg += `<path class="ch-conn ch-draw" pathLength="1" style="${at(T[i + 1] - 0.2, 0.4)}" d="M${r1(x0 + bw)},${r1(yl)} H${r1(cxOf(i + 1) - bw / 2)}"/>`;
    }
    scale += `<text class="ch-barname ch-in${key === "fees" ? " ch-barname--leak" : ""}" x="${r1(cxOf(i))}" y="${P.b + 44}" text-anchor="middle" style="${at(T[i] === DONE ? DONE : -0.8)}">${esc(name)}</text>`;
    if (key === "fees") return;
    // any other bar's value, only as the voice gives it
    const txt = `${key !== "rev" && key !== "net" ? MINUS : ""}${money0(hi - lo)}`, vAt = saidAt(job, txt);
    if (vAt != null) html += L.label(cxOf(i), y0 - 18, fig(txt, Math.max(vAt, early(T[i] + 0.25)), { cls: "ch-fig-s" }), { cls: "ch-barval", a: "c", v: "b" });
  });
  // the fees' figure is the frame's: it lands, big and blue, beside its bar on its word; its share above it
  const fx = cxOf(1) + bw / 2 + 34, fy0 = Y(rows[1][2]), fy1 = Y(rows[1][1]);
  if (heroAt != null) html += L.label(fx, fy0 + 26, fig(heroTxt, heroT, { money: true, cls: "ch-fig-m" }), { cls: "ch-barval", v: "t" });
  if (shareAt != null) {
    html += L.label(fx, fy0 - 14, `${fig(shareTxt, shareAt, { cls: "ch-fig-s ch-share" })}${unit("of revenue", 40, shareAt === DONE ? DONE : cue(job, /^revenue/, shareAt) ?? shareAt + 0.4)}`,
      { cls: "ch-row", v: "b" });
  }
  const under = spill(P.l - 60, P.r + 60, P.b) + bloom(cxOf(1), (fy0 + fy1) / 2, 260, heroAt != null ? heroT : T[1]);

  // the camera: a first showing leans into the fees as their figure lands; a return opens close on them and pulls back
  const fF = { x: cxOf(1) + 160, y: fy0 + 40 };
  const keys = ret
    ? [{ t: 0, ...pin(fF, 1.28, 900, 470) }, { t: Math.min(S - 0.3, 2.6), s: 1 }]
    : [{ t: 0, s: 1 }, { t: Math.max(0.2, heroT - 0.8), s: 1 }, { t: heroT + 2.2, ...pin(fF, 1.08) }, { t: Math.max(heroT + 2.3, restT[0] - 0.3), ...pin(fF, 1.08) }, { t: S, s: 1 }];
  const css = camera(uid, S, keys, [{ cls: `ch-scale-${uid}`, box: { l: cxOf(0) - 80, r: cxOf(rows.length - 1) + 60, t: P.b + 16, b: P.b + 60 } }]);
  const p = job.params || {};
  const brand = rv("demo_brand");
  const head = heading(job, { kicker: "Revenue to net", title: p.heading || brand?.value || "", caption: p.caption });
  svg = `<g class="ch-scale-${uid}">${scale}</g>${svg}`;
  return stage({ uid, S, css, under, svg, html, head });
}

// ---------------------------------------------------------------- the riser that moves (a schematic)

/**
 * An illustration, not data (the plan's caption says so): a product's dot stays where it is while
 * the card's riser, the edge, slides past it, so the product that sat on the step below sits on the
 * step above. In the staircase's own language (treads of light, the riser blue as the leak, a
 * dashed ghost where the edge was), with no figure, no axis value and no unit: the axes carry only
 * their names. Beats land on the words: the product, "under" (the edge lights), "last year", "over"
 * (the edge slides and the dot is lifted as it passes), "this year", "changing" (the product's own
 * position, unchanged), "moved" (the move, drawn).
 * params.builds, in order: the product, under, last year, over, this year, unchanged, moved.
 */
function riserShift(job, built, C, uid) {
  const { S, build } = C;
  const L = labeller();
  const P = { l: 420, r: 1560, t: 380, b: 760 };
  const yLo = 640, yHi = 470, x0 = 1170, x1 = 790, dx = 960;
  const w = (re, after, i, fb) => build(i) ?? cue(job, re, after) ?? fb;
  const prodT = w(/^product/, 0, 0, 0.4);
  const underT = w(/^under/, prodT, 1, prodT + 1.4);
  const lastT = w(/^last/, underT, 2, underT + 0.8);
  const overT = w(/^over/, lastT, 3, lastT + 1.1);
  const thisT = w(/^this/, overT, 4, overT + 0.5);
  const sameT = w(/^chang|^same/, thisT, 5, thisT + 2.2);
  const movedT = w(/^moved/, sameT, 6, Math.min(S - 1, sameT + 1.8));
  const slide = 0.8, passT = overT + slide * ((x0 - dx) / (x0 - x1));
  const stair = (x) => `M${P.l},${yLo} H${x} V${yHi} H${P.r}`;

  let svg = "", under = "", html = "";
  // the axes, named and unscaled
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.7)}" d="M${P.l},${P.t - 20} V${P.b} H${P.r + 20}"/>`;
  svg += `<path class="ch-axis ch-fade" style="${at(-0.4)}" d="M${P.r + 8},${P.b - 7} L${P.r + 20},${P.b} L${P.r + 8},${P.b + 7} M${P.l - 7},${P.t - 8} L${P.l},${P.t - 20} L${P.l + 7},${P.t - 8}"/>`;
  svg += `<text class="ch-axisname ch-in" x="${P.r + 20}" y="${P.b + 44}" text-anchor="end" style="${at(-0.4)}">Weight</text>`;
  svg += `<text class="ch-axisname ch-in" x="${P.l - 24}" y="${P.t - 4}" text-anchor="end" style="${at(-0.4)}">Fee</text>`;
  // the steps: treads of light; the edge, blue, slides from where it was to where it is
  svg += `<path class="ch-halo ch-draw ch-stair-${uid}" pathLength="1" style="${at(-0.5, 0.75)}" d="${stair(x0)}"/>`;
  svg += `<path class="ch-line ch-draw ch-stair-${uid}" pathLength="1" style="${at(-0.5, 0.75)}" d="${stair(x0)}"/>`;
  svg += `<g class="ch-wipe-up" style="${at(lastT + 0.6, 0.4)}"><path class="ch-ghost ch-ghost-${uid}" d="M${x0},${yLo} V${yHi}"/></g>`;
  svg += `<g class="ch-edge-${uid}">${light(`M${x0},${yLo} V${yHi}`, underT, 0.35, { cls: "ch-leak", halo: "ch-leak-halo" })}</g>`;
  under += `<div class="ch-edgebloom-${uid}">${bloom(x0, (yLo + yHi) / 2, 220, underT)}</div>`;
  // the product: its dot lands on the step below; as the edge passes it, it is lifted to the step above
  svg += `<path class="ch-thread ch-draw" pathLength="1" style="${at(sameT - 0.3, 0.5)}" d="M${dx},${P.b} V${yHi + 14}"/>`;
  svg += `<g class="ch-lift-${uid}"><circle class="ch-ripple" cx="${dx}" cy="${yLo}" r="11" style="${at(prodT + 0.3)}"/>` +
    `<circle class="ch-dot ch-drop" cx="${dx}" cy="${yLo}" r="11" style="${at(prodT)}"/></g>`;
  svg += `<circle class="ch-ripple" cx="${dx}" cy="${yHi}" r="11" style="${at(passT + 0.15)}"/>`;
  // the move, drawn on "moved"
  svg += `<path class="ch-move ch-draw" pathLength="1" style="${at(movedT - 0.45, 0.5)}" d="M${x0 - 6},${yHi - 34} C${x0 - 120},${yHi - 92} ${x1 + 120},${yHi - 92} ${x1 + 12},${yHi - 34}"/>`;
  svg += `<path class="ch-move ch-fade" style="${at(movedT - 0.05)}" d="M${x1 + 30},${yHi - 52} L${x1 + 12},${yHi - 34} L${x1 + 36},${yHi - 30}"/>`;

  html += L.label(x0, yLo + 24, `<i>last year</i>`, { cls: "ch-in", t: lastT, a: "c", v: "t" });
  html += L.label(x1, yLo + 24, `<i>this year</i>`, { cls: "ch-in", t: thisT, a: "c", v: "t" });
  html += L.label(dx, P.b + 30, `<i>same product</i>`, { cls: "ch-in", t: sameT, a: "c", v: "t" });

  const pct = (t) => `${r1((clamp(t, 0, S) / S) * 100)}%`;
  const css = `@keyframes chs-${uid}{0%,${pct(overT)}{d:path("${stair(x0)}")}${pct(overT + slide)},100%{d:path("${stair(x1)}")}}` +
    `.ch-stair-${uid}{animation:ch-draw .75s cubic-bezier(.45,0,.25,1) -.5s both, chs-${uid} ${s3(S)}s linear 0s both}` +
    `@keyframes che-${uid}{0%,${pct(overT)}{transform:translateX(0)}${pct(overT + slide)},100%{transform:translateX(${x1 - x0}px)}}` +
    `.ch-edge-${uid},.ch-edgebloom-${uid}{animation:che-${uid} ${s3(S)}s linear 0s both}` +
    `@keyframes chl-${uid}{0%,${pct(passT)}{transform:translateY(0)}${pct(passT + 0.18)}{transform:translateY(${yHi - yLo - 10}px)}${pct(passT + 0.32)},100%{transform:translateY(${yHi - yLo}px)}}` +
    `.ch-lift-${uid}{animation:chl-${uid} ${s3(S)}s linear 0s both}` +
    pushCSS(uid, S, [{ t: 0, s: 1 }, { t: overT - 0.4, s: 1.015, fx: dx, fy: yHi }, { t: S, s: 1.05, fx: dx, fy: yHi }], { l: P.l - 120, r: P.r + 30, t: P.t - 40, b: P.b + 70 },
      { top: headFoot(job.params) + 8 });
  const p = job.params || {};
  svg = `${L.grid()}${svg}`;
  return stage({ uid, S, css, under, svg, html, head: heading(job, { title: p.heading, caption: p.caption }) });
}

// ---------------------------------------------------------------- any other scene

/**
 * A chart this look has not drawn yet: never a machine name or a guessed picture. Its heading and
 * caption, and each figure the narration speaks landing as light on its word; with no figure, the
 * spoken line itself, set quietly, so the shot carries exactly what the voice says.
 */
function fallback(job, built, C, uid) {
  const { S } = C;
  const p = job.params || {};
  const figs = (job.reveals || []).filter((r) => /\d/.test(String(r.value ?? "")) && Number.isFinite(+r.t) && !/^demo_/.test(r.key)).slice(0, 3);
  const top = p.heading ? (p.caption ? 330 : 290) : 200;
  let svg = "", html = "";
  if (figs.length) {
    svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M160,${top + 40} H1300"/>`;
    figs.forEach((r, i) => { html += `<div class="ch-lab ch-fallfig" style="left:160px;top:${top + 90 + i * 150}px">${fig(r.value, spoken(job, r), { cls: "ch-fig-l" })}</div>`; });
  } else if (job.says) {
    html += `<div class="ch-lab ch-fallsays ch-in" style="left:160px;top:${Math.max(top + 60, 380)}px;${at(-0.4)}">${esc(job.says)}</div>`;
  }
  const css = pushCSS(uid, S, [{ t: 0, s: 1 }, { t: S, s: 1.02, fx: 700, fy: 560 }], { l: 160, r: 1600, t: 120, b: 840 }, { top: 104 });
  return stage({ uid, S, css, svg, html, head: heading(job, { title: p.heading || "", caption: p.caption }) });
}

// ---------------------------------------------------------------- entry

const SCENES = { staircase, montecarlo, aging, waterfall, riser_shift: riserShift };

/** One chart shot as HTML on the v3 stage. */
export function chart(job, built) {
  const uid = String(job.id || "x").replace(/[^a-z0-9]/gi, "") || "x";
  return (SCENES[job.chart?.scene] || fallback)(job, built, clockOf(job), uid);
}
