// v3 charts: data drawn as light on the dark desk (docs/content/FILM_LOOK_V3.md, "Data is light";
// round 2: scratchpad ROUND2.md, the shared base in base.css / clock.js / shots.mjs).
//
// chart(job, built) draws one chart shot as hand-set SVG and HTML: the fee staircase, the Monte
// Carlo, the aging cliff and the engine's waterfall, plus a quiet typographic fallback for any other
// scene. The figures are the site's own (built = scripts/build-pages.mjs figures(): built.charts.stairs
// / .aging / .mc), the waterfall is the film's own run.json (job.chart_data), the spoken values are the
// job's reveals. Nothing here types a figure: every number is formatted from that data with the
// site's own helpers, and none counts up (S3): a figure lands, whole and exact, on its spoken word.
//
// Time comes from the words (S5): job.words gives each spoken word's onset in seconds from the shot's
// first frame. A figure lands on the onset of the word that speaks it, never before; the other builds
// land on the words that name them (a card on "peak", the median on "number", the band on "range"),
// and fall back to times spread between those. Frame 1 is never empty (R1): the heading and the axes
// start their entrances at -0.4 s. The camera is base.css's one rig; each chart's own move rides
// on an inner layer (pushCSS), kept inside title-safe for the rig's push.
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
// Title-safe for what the plot layer may push into, inside base.css's camera (a push of at most 6%
// about the left grid at 45% height, no drift): x 1680 ends at 1771 and y 114 at 90.
const SAFE = { l: 168, r: 1680, t: 114, b: 930 };
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

/**
 * The shot's clock: length, `on`, reveals by key (with the onset their figure is spoken), and the
 * editor's `params.builds` (PLAN_PARAMS.md: seconds from the shot's first frame at which something
 * new lands). Builds written in film seconds (the retired form) are not read. Priority, for every
 * beat: the word that speaks a figure, then the editor's build, then a word that names the beat,
 * then a time spread between them.
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
  return { S, on, rv, build };
}

/** Times spread evenly over [a, b] (n of them; one lands at a). */
const spread = (n, a, b) => Array.from({ length: n }, (_, i) => (n === 1 ? a : a + ((b - a) * i) / (n - 1)));
/** A small stable hash of a shot id, for choosing among camera variants. */
const hash = (s) => [...String(s)].reduce((h, c) => (h * 33 + c.charCodeAt(0)) >>> 0, 5381);

// ---------------------------------------------------------------- the camera

/**
 * The plot layer's own move, on top of the camera: keyframes of translate and scale about a focus
 * point, kept inside SAFE for the content's bounds. Between keys it eases; the rig under it never
 * stops, so the frame never comes to rest.
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

// ---------------------------------------------------------------- the frame

/** The frame every chart shares: the camera, the plot layer that moves, the still layers over it. */
function stage({ uid, S, css = "", under = "", svg, html = "", over = "", head = "" }) {
  return `<style>${css}</style>` +
    `<div class="cam ch"><div class="rig"><div class="ch-cam">` +
    `<div class="ch-push" style="animation:chp-${uid} ${s3(S)}s linear 0s both">${under}` +
    `<svg class="ch-svg" viewBox="0 0 1920 1080" width="1920" height="1080" aria-hidden="true">${svg}</svg>${html}</div>` +
    `${over}${head}</div></div></div>`;
}

/** Heading and caption: Fraunces at its own size (the --heading-font token), Inter for the caption. */
function heading({ kicker, title, titleAt = -0.4, caption, captionAt = 0.4 }) {
  if (!kicker && !title && !caption) return "";
  return `<header class="ch-head">` +
    (kicker ? `<p class="ch-kicker ch-in" style="${at(-0.4)}">${esc(kicker)}</p>` : "") +
    (title ? `<h2 class="ch-title ch-in" style="${at(early(titleAt))}">${esc(title)}</h2>` : "") +
    (caption ? `<p class="ch-cap ch-in" style="${at(early(captionAt))}">${esc(caption)}</p>` : "") +
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
    return d ? `<path class="${cls} ch-fade" style="${at(-0.4, 0.6)}" d="${d}"/>` : "";
  }).join("");
  return { label, est, rule, grid, boxes };
}

/** A figure that lands (S3): blur, scale and tracking settle on its word; money then blooms. */
const fig = (text, t, { cls = "", money = false } = {}) =>
  `<span class="ch-fig ch-land${money ? " money" : ""}${cls ? ` ${cls}` : ""}" style="${at(t)}">${esc(text)}</span>`;
/** A unit beside its figure: 0.3 of its size (never under 28 px), italic, ivory 70%, never blue. */
const unit = (text, px, t) => `<span class="ch-unit-t ch-in" style="font-size:${Math.max(28, Math.round(px * 0.3))}px;${at(t)}">${esc(text)}</span>`;

/** Light falling on the desk around a figure as it lands; and the plot's light spilling below its baseline. */
const bloom = (x, y, r, t, d = 1.4, cls = "") =>
  `<div class="ch-bloom ${cls}" style="left:${r1(x - r)}px;top:${r1(y - r)}px;width:${2 * r}px;height:${2 * r}px;${at(t, d)}"></div>`;
const spill = (x0, x1, y) => `<div class="ch-spill" style="left:${r1(x0)}px;top:${r1(y - 70)}px;width:${r1(x1 - x0)}px;height:200px;${at(-0.4, 1.2)}"></div>`;
const flare = (x, y, t) => `<div class="ch-flare" style="left:${r1(x)}px;top:${r1(y)}px;${at(t)}"></div>`;

/** A stroke of light: a wide faint halo under a crisp core, drawn on together (no filter: R4). */
const light = (d, t, dur, { cls = "ch-line", halo = "ch-halo", extra = "" } = {}) =>
  `<path class="${halo} ch-draw${extra}" pathLength="1" style="${at(t, dur)}" d="${d}"/><path class="${cls} ch-draw${extra}" pathLength="1" style="${at(t, dur)}" d="${d}"/>`;

// ---------------------------------------------------------------- the fee staircase

/**
 * The fulfilment fee staircase (built.charts.stairs). The card in force draws on tread by tread,
 * each riser snapping up; the peak card wipes on as a dashed ghost. The listing's dot lands at its
 * weight and the hollow dot one step down; the riser between them is the leak, the frame's one blue,
 * with its per-unit figure set in the ledger to the plot's left, out of the plot, on its word.
 * The staircase returns in several shots, so each return takes its own camera: the first is wide
 * and pushes in as the figure lands; a return pushes into the riser, or starts tight on it and pulls
 * back; a chart-build racks focus to the listing at 8.8 oz.
 * params.builds, in order: counterfactual — the treads drawn, the listing, one step down, the riser,
 * the peak card; chart-build — the treads drawn, the peak card, the listing, one step down, the riser.
 */
function staircase(job, built, C, uid) {
  const st = built.charts.stairs;
  const { S, on, rv, build } = C;
  const L = labeller();
  const cf = job.style !== "chart-build";
  const xMax = 16;
  const tr = st.treads.filter(([e]) => e <= xMax), al = st.alt.filter(([e]) => e <= xMax);
  const fees = [...tr, ...al].map(([, f]) => f);
  const lo = Math.min(...fees), hi = Math.max(...fees);
  const yt = niceTicks(lo - 0.15, hi + 0.1, 4);
  const d0 = Math.min(yt[0], lo - 0.15), d1 = Math.max(yt[yt.length - 1], hi + 0.1);
  const P = { l: 740, r: 1560, t: 330, b: floorOf(job) };
  const X = lin(0, xMax, P.l, P.r), Y = lin(d0, d1, P.b, P.t);
  const feeAt = (rows, oz) => (rows.find(([e]) => oz <= e) || rows[rows.length - 1])[1];
  const ei = tr.findIndex(([e]) => e === st.edge.oz);
  const ex = X(st.edge.oz), yLo = Y(st.edge.fee), yHi = Y(st.listing.fee), lx = X(st.listing.oz);
  const peakLo = feeAt(al, st.edge.oz), peakHi = feeAt(al, st.listing.oz);
  const stepTxt = `+${cents(st.step)}`, peakTxt = `+${cents(peakHi - peakLo)}`;

  // ---- time, from the words
  const R = rv("cs_step"), E = rv("cs_edge"), PK = rv("cs_step_peak"), U = rv("cs_units");
  const variant = R || E ? "establish" : !cf ? "rack" : (on ?? 9) < 3 ? "pull" : hash(job.id) % 2 ? "push" : "truck";
  const recall = variant === "pull";                  // a quick return: the staircase is up at the cut
  const drawA = recall ? -1.4 : -0.2;
  let listT, edgeT, riserT;
  if (cf) {
    edgeT = E?.at ?? build(2) ?? (on ?? S * 0.45);
    riserT = R?.at ?? build(3) ?? snap(job, edgeT + 0.35);
  } else {
    listT = build(2) ?? on ?? S * 0.45;
    edgeT = build(3) ?? snap(job, listT + 0.3);
    riserT = build(4) ?? snap(job, edgeT + 0.3);
  }
  const first = Math.min(edgeT, riserT, listT ?? Infinity);
  let drawB = recall ? Math.min(first - 0.2, 0.4) : clamp(build(0) ?? cue(job, /^tread|^staircase/, 0.8, first - 0.2) ?? first - 0.3, drawA + 1.0, drawA + 2.6);
  const anchor = E && E.at > drawA + 0.6 ? E.at : null;     // the pen reaches the edge as "8" is spoken
  if (anchor) drawB = Math.max(drawB, anchor + 0.9);
  if (cf) listT = build(1) ?? (edgeT < riserT - 1.5 ? snap(job, (edgeT + riserT) / 2) : null) ?? (cue(job, /candidate|listing|product/, drawB, edgeT - 0.3) ??
    clamp(snap(job, (drawB + edgeT) / 2), drawB + 0.15, Math.max(drawB + 0.15, edgeT - 0.4)));
  const figT = cf ? (R?.at ?? Math.max(riserT, cue(job, /differen|riser|turn/, riserT - 0.5) ?? riserT + 0.3)) : riserT + 0.3;
  const ghostT = PK?.at ?? build(cf ? 4 : 1) ?? cue(job, /^staircases$|^peak$/, 0.5) ?? (cf ? (riserT + 2.4 <= S - 1.6 ? snap(job, riserT + 2.4) : recall ? S - 2 : drawA + 0.6) : snap(job, (drawB + listT) / 2));
  const npT = cue(job, /^non-peak$/, 0) ?? Math.max(early(drawB - 0.4), 0.2);
  const pkT = cue(job, /^peak$/, ghostT - 0.1) ?? ghostT + 1.0;
  const labT = cf ? null : riserT + 2.2 <= S - 0.8 ? snap(job, riserT + 2.2) : riserT + 0.4;

  // ---- the card in force, tread by tread
  const segs = [];
  let x0 = 0;
  tr.forEach(([edge, fee], i) => {
    segs.push({ k: "t", d: `M${r1(X(x0))},${r1(Y(fee))} H${r1(X(edge))}`, len: X(edge) - X(x0), i });
    if (i + 1 < tr.length) segs.push({ k: "r", d: `M${r1(X(edge))},${r1(Y(fee))} V${r1(Y(tr[i + 1][1]))}`, len: Y(fee) - Y(tr[i + 1][1]), i, x: X(edge), y: Y(tr[i + 1][1]) });
    x0 = edge;
  });
  const RISE = 0.18;
  const timeSegs = (list, a, b) => {
    const nr = list.filter((s) => s.k === "r").length, tl = list.filter((s) => s.k === "t").reduce((n, s) => n + s.len, 0);
    const rate = Math.max(0.05, b - a - nr * RISE) / tl;
    let t = a;
    for (const s of list) { s.t = t; s.dur = s.k === "r" ? RISE : s.len * rate; t += s.dur; }
  };
  const cut = segs.findIndex((s) => s.k === "t" && s.i === ei) + 1;
  if (anchor && cut > 0 && cut < segs.length) { timeSegs(segs.slice(0, cut), drawA, anchor); timeSegs(segs.slice(cut), anchor, drawB); }
  else timeSegs(segs, drawA, drawB);

  let svg = "", under = "", html = "", over = "";
  yt.forEach((v) => {
    L.rule(P.l, P.r, Y(v));
    svg += `<text class="ch-tick ch-in" x="${P.r + 26}" y="${r1(Y(v))}" dominant-baseline="central" style="${at(-0.4)}">$${v.toFixed(2)}</text>`;
  });
  for (const [edge] of [[0], ...tr]) L.rule(P.t - 10, P.b, X(edge), "ch-edge", true);
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${P.b} H${P.r}"/>`;
  for (const [edge] of [[0], ...tr]) {
    const hot = edge === st.edge.oz;
    svg += `<text class="ch-tick ch-in${hot ? " ch-hot" : ""}" x="${r1(X(edge))}" y="${P.b + 44}" text-anchor="middle" style="${at(-0.4)}${hot ? `;--hot:${s3(edgeT)}` : ""}">${edge}${edge === xMax ? " oz" : ""}</text>`;
  }
  svg += `<text class="ch-axisname ch-in" x="1660" y="${P.t - 52}" text-anchor="end" style="${at(-0.4)}"><tspan>Fee</tspan><tspan x="1660" dy="32">a unit</tspan></text>`;

  // the peak card: a dashed ghost wiped on; its own riser dashed blue when its figure is spoken
  let ghost = `M${r1(X(0))},${r1(Y(al[0][1]))}`;
  al.forEach(([edge, fee], i) => { ghost += ` H${r1(X(edge))}`; if (i + 1 < al.length) ghost += ` V${r1(Y(al[i + 1][1]))}`; });
  svg += `<g class="ch-wipe" style="${at(early(ghostT), 1.4)}"><path class="ch-ghost" d="${ghost}"/></g>`;
  if (PK) svg += `<g class="ch-wipe-up" style="${at(PK.at, 0.45)}"><path class="ch-ghost-leak" d="M${r1(ex)},${r1(Y(peakLo))} V${r1(Y(peakHi))}"/></g>`;

  // the solid card, then the flare at each riser's top
  let stairs = "";
  for (const s of segs) stairs += light(s.d, s.t, s.dur, { extra: s.k === "r" ? " ch-riser" : "" });
  for (const s of segs.filter((q) => q.k === "r")) under += flare(s.x, s.y, s.t + s.dur - 0.05);
  under += spill(P.l - 60, P.r + 60, P.b);

  // each card named above its last tread, when the voice names it
  const nameL = (txt, y, t, cls) => L.label(P.r, y, txt, { cls: `ch-name ${cls} ch-in`, t, a: "r", v: "b", w: L.est(txt, 28, true), h: 30 });
  html += nameL("Non-peak", Y(tr[tr.length - 1][1]) - 14, npT, "");
  html += nameL("Peak", Y(al[al.length - 1][1]) - 14, pkT, "ch-name--ghost");

  // the leak: the riser between one step down and this listing, in blue, lighting the desk
  under += bloom(ex, (yLo + yHi) / 2, 230, riserT);
  let near = "";
  near += light(`M${r1(ex)},${r1(yLo)} V${r1(yHi)}`, riserT, 0.4, { cls: "ch-leak", halo: "ch-leak-halo" });

  // the listing's dot: a thread of light rises from its weight and the dot lands on its tread;
  // one step down, the hollow dot at the edge
  near += `<path class="ch-thread ch-draw" pathLength="1" style="${at(listT - 0.5, 0.5)}" d="M${r1(lx)},${P.b} V${r1(yHi + 13)}"/>`;
  near += `<circle class="ch-ripple" cx="${r1(lx)}" cy="${r1(yHi)}" r="11" style="${at(listT + 0.3)}"/>`;
  near += `<circle class="ch-dot ch-drop" cx="${r1(lx)}" cy="${r1(yHi)}" r="11" style="${at(listT)}"/>`;
  near += `<circle class="ch-ripple" cx="${r1(ex)}" cy="${r1(yLo)}" r="10" style="${at(edgeT)}"/>`;
  near += `<circle class="ch-dot-hollow ch-pop" cx="${r1(ex)}" cy="${r1(yLo)}" r="10" style="${at(edgeT)}"/>`;
  const dotLab = labT ?? listT + 0.25, edgeLab = labT ? labT + 0.25 : edgeT + 0.25;
  const fg = L.label(lx + 22, yHi + 22, `<b class="ch-fig ch-fig-s">${st.listing.oz.toFixed(1)} oz</b><i>this listing</i>`,
    { cls: "ch-dotlab ch-in", t: dotLab, v: "t", w: 250, h: 80 });
  html += L.label(ex - 22, yLo + 22, `<i>one step</i><i>down</i>`, { cls: "ch-dotlab ch-dotlab--r ch-in", t: edgeLab, a: "r", v: "t", w: 170, h: 70 });

  // the counterfactual bracket on the riser
  if (cf) {
    const bx = ex - 30;
    near += `<path class="ch-bracket ch-draw" pathLength="1" style="${at(riserT + 0.1, 0.45)}" d="M${r1(bx + 14)},${r1(yLo)} H${r1(bx)} V${r1(yHi)} H${r1(bx + 14)}"/>`;
  }

  // ---- the ledger, left of the plot: the step, then the peak card's step, then the units
  const lx0 = 160;
  const big = R ? 120 : 96;
  over += `<div class="ch-ledger" style="left:${lx0}px;top:${P.t + 10}px">` +
    `<div class="ch-row">${fig(stepTxt, figT, { money: true, cls: R ? "ch-fig-l" : "ch-fig-m" })}${unit("a unit", big, cue(job, /^unit/, figT + 0.2) ?? figT + 0.3)}</div>`;
  if (PK) over += `<div class="ch-row ch-row--2">${fig(peakTxt, PK.at, { money: true, cls: "ch-fig-s2" })}${unit("on the peak card", 72, pkT)}</div>`;
  if (U) {
    const v = String(U.value || ""), m = v.match(/\d[\d,.]*/);
    const num = m ? m[0] : v, pre = m ? v.slice(0, m.index).trim() : "", post = m ? v.slice(m.index + m[0].length).trim() : "";
    const preT = cue(job, /^estimat/, U.t - 0.3) ?? U.at - 0.4;
    over += `<div class="ch-row ch-row--3">${pre ? `<p class="ch-eyebrow ch-in" style="${at(Math.min(preT, U.at))}">${esc(pre)}</p>` : ""}` +
      `<div class="ch-row">${fig(num, U.at, { cls: "ch-fig-s2" })}${unit(post, 72, cue(job, /^units?$/, U.at + 0.1) ?? U.at + 0.4)}</div></div>`;
  }
  over += `</div>`;

  // ---- depth: a chart-build racks focus to the listing on its word
  let depth = "";
  if (variant === "rack") depth = `.ch-rack-${uid}{animation:ch-rack 3.6s linear ${s3(listT - 0.2)}s both}`;

  // ---- the camera's own move, on the plot layer
  const fR = { fx: ex - 40, fy: (yLo + yHi) / 2 }, fL = { fx: lx + 60, fy: yHi + 30 };
  const keys = {
    establish: [{ t: 0, s: 1 }, { t: Math.max(0.1, riserT - 0.5), s: 1.005, ...fR }, { t: riserT + 3, s: 1.05, ...fR },
      ...(U ? [{ t: U.at - 0.5, s: 1.055, ...fR }, { t: Math.min(S, U.at + 3), s: 1.04, ...fL }] : [])],
    push: [{ t: 0, s: 1 }, { t: Math.max(0.1, riserT - 1.2), s: 1.01, ...fR }, { t: riserT + 1.8, s: 1.13, ...fR }],
    truck: [{ t: 0, s: 1.06, fx: P.l + 80, fy: P.b - 60 }, { t: riserT + 0.6, s: 1.08, ...fR }, { t: S, s: 1.1, fx: lx + 120, fy: yHi }],
    pull: [{ t: 0, s: 1.14, ...fR }, { t: Math.min(S - 0.5, Math.max(riserT + 1.2, 2.2)), s: 1.0, ...fR }],
    rack: [{ t: 0, s: 1 }, { t: Math.max(0.1, listT - 0.6), s: 1.01, ...fL }, { t: listT + 2, s: 1.08, ...fL }],
  }[variant];
  const css = pushCSS(uid, S, keys, { l: P.l - 20, r: 1664, t: P.t - 76, b: P.b + 60 }, { top: headFoot(job.params) + 8, left: 724 }) + depth;

  const p = job.params || {};
  const dashed = /dash/i.test(p.caption || "");
  const head = heading({ title: p.heading, caption: p.caption, captionAt: dashed ? ghostT + 0.3 : -0.4 });
  svg = `<g class="ch-rack-${uid}">${L.grid()}${svg}${stairs}</g>${near}`;
  return stage({ uid, S, css, under, svg, html: `<div class="ch-layer ch-rack-${uid}">${html}</div>${fg}`, over, head });
}

// ---------------------------------------------------------------- the Monte Carlo

/**
 * The simulated years of one listing's cumulative profit (built.charts.mc), as the simulation runs:
 * month by month, a column of points (one per simulated year the data carries) lands, with each
 * year's faint thread drawn behind it. The median, the one number, draws in blue with its figure;
 * the slow and strong years' ends land in the light; the P10–P90 band fills, ivory at 10%, on
 * "range". The chart fills the frame's width, so its camera moves in height and depth: the first
 * time a crane settles onto the months as they run; a return racks focus from the cloud of years to
 * the band as it fills.
 * params.builds, in order: the months run, the median, the slow year, the strong year, the band.
 */
function montecarlo(job, built, C, uid) {
  const mc = built.charts.mc;
  const { S, on, build } = C;
  const L = labeller();
  const P = { l: 370, r: 1280, t: 350, b: floorOf(job) };
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

  // ---- time: the months run first; the median on "number", the ends on "slow" / "strong", the band on "range"
  const variant = on != null && on >= 0.45 * S ? "truck" : "push";
  const runA = variant === "truck" ? -0.3 : -1.1;            // a return opens with the run under way
  const named = build(1) ?? cue(job, /^number|^median|^middle/, 0.6);
  const runB = clamp(build(0) ?? Math.min((on ?? S * 0.5) - 1.0, (named ?? Infinity) - 0.15), runA + 1.4, runA + 3.2);
  const step = (runB - runA) / n;
  const medT = named ?? snap(job, runB + 0.2);
  const lowT = build(2) ?? cue(job, /^slow|^low|^bad/, medT + 0.3) ?? snap(job, (on ?? runB + 1) + 0.3);
  const highT = build(3) ?? cue(job, /^strong|^high|^good/, lowT + 0.2) ?? snap(job, lowT + 0.8);
  const bandT = build(4) ?? cue(job, /^range/, highT) ?? on ?? highT + 0.6;
  const fillT = Math.max(bandT, highT + 0.3);

  // ---- svg
  let svg = "", html = "";
  ticks.forEach((v) => {
    if (v !== 0) L.rule(P.l, P.r, Y(v));
    svg += `<text class="ch-tick ch-in" x="${P.l - 22}" y="${r1(Y(v))}" text-anchor="end" dominant-baseline="central" style="${at(-0.4)}">${esc(usd(v, { compact: true }))}</text>`;
  });
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${r1(Y(0))} H${P.r}"/>`;
  const last = months[n];
  for (const [m, txt, a] of [[months[0], "Today", "start"], [last / 2, `${last / 2} months`, "middle"], [last, `${last} months`, "end"]]) {
    svg += `<text class="ch-tick ch-in" x="${r1(X(m))}" y="${P.b + 44}" text-anchor="${a}" style="${at(-0.4)}">${esc(txt)}</text>`;
  }
  svg += `<text class="ch-axisname ch-in" x="160" y="${P.t - 34}" style="${at(-0.4)}">Cumulative profit</text>`;

  // the band, born on the median, filling on its word (ivory: the one blue is the median)
  svg += `<path class="ch-band ch-band-${uid}" d="${band(p50, p50)}" style="${at(fillT, clamp(S - fillT - 0.1, 0.4, 0.9))}"/>`;
  // every simulated year's thread, wiped on as the months run; a column of points lands each month
  let cloud = "";
  cloud += `<g class="ch-threads ch-wipe" style="${at(runA, runB - runA + 0.2)}">` +
    mc.paths.map((p) => `<path d="${line(p)}"/>`).join("") + `</g>`;
  months.forEach((_, i) => {
    if (i === 0) return;
    cloud += `<g class="ch-month ch-pop-col" style="${at(runA + step * i)}">` +
      mc.paths.map((p) => `<circle cx="${r1(xs[i])}" cy="${r1(Y(p[i]))}" r="3.2"/>`).join("") + `</g>`;
  });
  // the slow and strong years' lines, then the median in blue
  svg += light(line(p10), lowT - 0.5, 0.6, { cls: "ch-pct", halo: "ch-pct-halo" });
  svg += light(line(p90), highT - 0.5, 0.6, { cls: "ch-pct", halo: "ch-pct-halo" });
  svg += light(line(p50), medT - 0.75, 0.75, { cls: "ch-median", halo: "ch-median-halo" });
  svg += `<circle class="ch-end-dot ch-pop" cx="${r1(xs[n])}" cy="${r1(Y(p50[n]))}" r="9" style="${at(medT)}"/>`;

  // the three ends, named
  const tail = (q) => `1 in ${Math.round(100 / Math.min(+q.slice(1), 100 - +q.slice(1)))}`;
  const ends = [["p90", `${tail("p90")} above`, p90[n], highT], ["p50", "Median", p50[n], medT], ["p10", `${tail("p10")} below`, p10[n], lowT]];
  const ys = ends.map(([, , v]) => Y(v));
  for (let i = 1; i < ys.length; i++) if (ys[i] - ys[i - 1] < 128) ys[i] = ys[i - 1] + 128;
  const fill = built.fill || {};
  ends.forEach(([q, name, v, t], i) => {
    const txt = fill[`mc_${q}`] || usd(v, { step: 1000 });
    const med = q === "p50";
    html += L.label(P.r + 34, ys[i], `<i class="ch-in" style="${at(t - 0.1)}">${esc(name)}</i>${fig(txt, t, { money: med, cls: med ? "ch-fig-s2" : "ch-fig-s" })}`,
      { cls: `ch-endlab${med ? " ch-endlab--med" : ""}`, t });
  });

  const under = spill(P.l - 60, P.r + 60, Y(0)) + bloom(xs[n], Y(p50[n]), 200, medT, 1.4, "ch-bloom--soft");
  // the chart fills the frame's width, so its camera moves in depth and height, not across:
  // the first time a crane settles onto the months as they run; a return racks focus from the
  // cloud of years to the band as the range is named
  const keys = variant === "truck"
    ? [{ t: 0, dy: 44 }, { t: runB + 0.6, dy: 6 }, { t: S, dy: 0 }]
    : [{ t: 0, dy: -10 }, { t: S, dy: 14 }];
  const rack = variant === "push" ? `.ch-rack-${uid}{animation:ch-recede 0.8s ease ${s3(fillT - 0.3)}s both}` : "";
  const css = `@keyframes chb-${uid}{from{d:path("${band(p50, p50)}");opacity:0}to{d:path("${band(p90, p10)}");opacity:1}}` +
    `.ch-band-${uid}{animation:chb-${uid} calc(var(--d)*1s) var(--ease-out) calc(var(--at)*1s) both}` +
    pushCSS(uid, S, keys, { l: 160, r: 1660, t: P.t - 60, b: P.b + 60 }, { top: headFoot(job.params) + 8 }) + rack;
  const p = job.params || {};
  const head = heading({ title: p.heading, caption: p.caption });
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

  // ---- svg
  let svg = "", under = "", html = "";
  yt.forEach((v) => {
    if (v > 0) L.rule(P.l, P.r, Y(v));
    svg += `<text class="ch-tick ch-in" x="${P.l - 22}" y="${r1(Y(v))}" text-anchor="end" dominant-baseline="central" style="${at(-0.4)}">$${v}</text>`;
  });
  // the scale's unit, once: "a month" unless the heading or caption already says it; the units it is for, when spoken
  const unitName = saysMonth ? "" : "A month";
  // (the scale's unit and the units it is for share one line at the scale's top)
  if (unitName) svg += `<text class="ch-axisname ch-in" x="160" y="${P.t - 30}" style="${at(-0.4)}">${unitName}</text>`;
  if (units) svg += `<text class="ch-axisname ch-in" x="${unitName ? 300 : 160}" y="${P.t - 30}" style="${at(units.at)}">${unitName ? "· " : ""}${esc(units.value)}</text>`;
  // the day ticks: each lands as the walk reaches it
  const dayTicks = [...new Set([...ag.ticks, ...(bandR ? [bandPre.from] : [])])].sort((m, k) => m - k);
  dayTicks.forEach((d) => {
    const si = stops.indexOf(d), hot = d === ag.cliff;
    const t = d === 0 ? -0.4 : si >= 0 ? times[si] : d < ag.cliff ? times[stops.length - 1] : cliffT + 0.3;
    svg += `<text class="ch-tick ch-in${hot ? " ch-hot" : ""}" x="${r1(X(d))}" y="${P.b + 44}" text-anchor="${d === 0 ? "start" : "middle"}" style="${at(early(t))}${hot ? `;--hot:${s3(cliffT)}` : ""}">${d === 0 ? "Day 0" : d}</text>`;
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

  // the ledger, above the young stock: the surcharge before and after the cliff, on their words
  if (before || after) {
    const lx = P.l + 30, ly = P.t + 16;
    if (surT != null) html += L.label(lx, ly, `<i>surcharge</i>`, { cls: "ch-eyebrow ch-in", t: surT, v: "t", w: 190, h: 30 });
    // "$1.50 a cubic foot → $5.45"; with only the rate after the cliff spoken, "$5.45 a cubic foot"
    html += L.label(lx, ly + 44, (before ? fig(before.value, before.at, { cls: "ch-fig-s2" }) + unit("a cubic foot", 72, cuT) : "") +
      (after ? `${before ? `<span class="ch-arrow ch-in" style="${at(after.at - 0.1)}">→</span>` : ""}${fig(after.value, after.at, { money: true, cls: "ch-fig-s2" })}` +
        (before ? "" : unit("a cubic foot", 72, Math.max(cuT, after.at + 0.3))) : ""),
      { cls: "ch-row", v: "t", w: 640, h: 80 });
  }

  const css = `@keyframes chw-${uid}{${kf}}.ch-play-${uid}{animation:chw-${uid} ${s3(S)}s cubic-bezier(.45,0,.3,1) 0s both, ch-fade .4s ease calc(var(--at)*1s) both, ch-out .5s ease calc(var(--off)*1s) forwards}` +
    `@keyframes chj-${uid}{0%,${r1((cliffT / S) * 100)}%{translate:0 0}${r1(((cliffT + 0.05) / S) * 100)}%{translate:0 10px}${r1(((cliffT + 0.15) / S) * 100)}%{translate:0 -4px}${r1(((cliffT + 0.32) / S) * 100)}%,100%{translate:0 0}}` +
    `.ch-jolt-${uid}{animation:chj-${uid} ${s3(S)}s linear 0s both}` +
    (youngT != null ? `.ch-young .ch-col-fill{animation:ch-young-fill 1.2s ease ${s3(youngT)}s both}` : "") +
    pushCSS(uid, S, [{ t: 0, s: 1 }, { t: Math.max(0.1, cliffT - 1.4), s: 1.02, fx: cx, fy: 620 }, { t: cliffT + 0.05, s: 1.025, fx: cx, fy: 620 },
      { t: cliffT + 0.6, s: 1.05, fx: cx, fy: 600 }, { t: S, s: 1.06, fx: cx + 100, fy: 600 }], { l: 160, r: 1600, t: P.t - 60, b: P.b + 60 }, { top: headFoot(p) + 8 });
  const head = heading({ title: p.heading, caption: p.caption });
  svg = `${L.grid()}${svg}`;
  return stage({ uid, S, css, under, svg: `<g class="ch-jolt-${uid}">${svg}</g>`, html: `<div class="ch-jolt-${uid} ch-layer">${html}</div>`, head });
}

// ---------------------------------------------------------------- the waterfall

/**
 * One month of the film's demo catalogue, revenue to net (job.chart_data, the waterfall in the
 * film's own run.json). Each bar draws up from its own base: revenue, then Amazon's fees on
 * "Amazon's", then landed cost, ads and net. The fees are the leak and the shot's one blue: their
 * share of revenue lands on "32.1%", their figure on "$102,395", the figure the line lands on.
 * Every value sits above its bar; costs carry a true minus.
 * params.builds, in order: the fees, landed cost, ads, net (revenue is up at the cut).
 */
function waterfall(job, built, C, uid) {
  const w = job.chart_data;
  if (!w || !Number.isFinite(+w.revenue)) return fallback(job, built, C, uid);
  const { S, on, rv, build } = C;
  const L = labeller();
  const rows = [["Revenue", 0, w.revenue, "rev"]];
  let run = w.revenue;
  for (const [name, key] of [["Amazon fees", "fees"], ["Landed cost", "cogs"], ["Ads", "ads"]]) { rows.push([name, run - w[key], run, key]); run -= w[key]; }
  rows.push(["Net", 0, w.net, "net"]);
  const P = { l: 220, r: 1620, t: floorOf(job) - 310, b: floorOf(job) };
  const Y = lin(0, w.revenue, P.b, P.t);
  const slot = (P.r - P.l) / rows.length, bw = Math.min(150, slot * 0.54);
  const cxOf = (i) => P.l + slot * (i + 0.5);

  // ---- time, from the words
  const brand = rv("demo_brand"), share = rv("fee_share_latest"), fv = rv("fees_latest");
  const heroT = fv?.at ?? on ?? S * 0.5;
  const feesT = build(0) ?? cue(job, /^amazon/, 1, heroT) ?? (share ? share.at - 4.5 : heroT - 2.2);
  const shareT = share?.at ?? null;
  const restA = snap(job, Math.max(heroT, shareT ?? 0) + 1.3);
  const restT = spread(3, Math.min(restA, S - 4.2), Math.min(restA + 3, S - 1.2)).map((t, i) => build(i + 1) ?? t);
  const T = [-0.4, Math.max(0.8, feesT), ...restT];

  // ---- svg
  let svg = `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l - 30},${P.b} H${P.r + 30}"/>`;
  let html = "";
  rows.forEach(([name, lo, hi, key], i) => {
    const x0 = cxOf(i) - bw / 2, y0 = Y(hi), y1 = Y(lo), h = Math.max(2, y1 - y0);
    const cls = key === "fees" ? "ch-bar--leak" : "";
    svg += `<g class="ch-bar ${cls} ch-grow" style="${at(T[i], 0.5)}"><rect class="ch-bar-fill" x="${r1(x0)}" y="${r1(y0)}" width="${r1(bw)}" height="${r1(h)}"/>` +
      `<path class="ch-bar-edge" d="M${r1(x0)},${r1(y0)} H${r1(x0 + bw)}"/></g>`;
    if (i + 1 < rows.length && rows[i + 1][3] !== "net") {
      const yl = Y(key === "rev" ? hi : lo);
      svg += `<path class="ch-conn ch-draw" pathLength="1" style="${at(T[i + 1] - 0.2, 0.4)}" d="M${r1(x0 + bw)},${r1(yl)} H${r1(cxOf(i + 1) - bw / 2)}"/>`;
    }
    svg += `<text class="ch-barname ch-in${key === "fees" ? " ch-barname--leak" : ""}" x="${r1(cxOf(i))}" y="${P.b + 44}" text-anchor="middle" style="${at(early(T[i] + 0.1))}">${esc(name)}</text>`;
    const v = hi - lo, cost = key !== "rev" && key !== "net";
    const txt = `${cost ? MINUS : ""}${money0(v)}`;
    if (key === "fees") {
      // the fees' figure is the frame's: it lands, big and blue, on its word
      const fx = cxOf(i) - bw / 2;
      if (shareT != null) html += L.label(fx, y0 - 154, `${fig(share.value, shareT, { cls: "ch-fig-s ch-share" })}${unit("of revenue", 40, cue(job, /^revenue/, shareT) ?? shareT + 0.4)}`,
        { cls: "ch-row", v: "b" });
      html += L.label(fx - 6, y0 - 22, fig(txt, heroT, { money: true, cls: "ch-fig-m" }), { cls: "ch-barval", v: "b" });
    } else {
      html += L.label(cxOf(i), y0 - 18, fig(txt, early(T[i] + 0.25), { cls: "ch-fig-s" }), { cls: "ch-barval", a: "c", v: "b" });
    }
  });
  const fy0 = Y(rows[1][2]), fy1 = Y(rows[1][1]);
  const under = spill(P.l - 60, P.r + 60, P.b) + bloom(cxOf(1), (fy0 + fy1) / 2, 240, heroT);

  const css = pushCSS(uid, S, [{ t: 0, s: 1 }, { t: Math.max(0.2, heroT - 0.8), s: 1.02, fx: cxOf(1), fy: fy0 }, { t: heroT + 2.2, s: 1.07, fx: cxOf(1) + 120, fy: fy0 - 40 },
      { t: restT[0] - 0.2, s: 1.07, fx: cxOf(1) + 120, fy: fy0 - 40 }, { t: S, s: 1.03, fx: 900, fy: 600 }], { l: 190, r: 1650, t: fy0 - 210, b: P.b + 60 }, { top: 224 });
  const p = job.params || {};
  const period = /^\d{4}-\d{2}/.test(String(w.period || "")) ? new Date(`${String(w.period).slice(0, 7)}-15T00:00:00Z`).toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" }) : "";
  const head = heading({ kicker: ["Revenue to net", period].filter(Boolean).join(" · "), title: p.heading || brand?.value || "", titleAt: brand?.at ?? -0.4, caption: p.caption });
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
  return stage({ uid, S, css, under, svg, html, head: heading({ title: p.heading, caption: p.caption }) });
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
  return stage({ uid, S, css, svg, html, head: heading({ title: p.heading || "", caption: p.caption }) });
}

// ---------------------------------------------------------------- entry

const SCENES = { staircase, montecarlo, aging, waterfall, riser_shift: riserShift };

/** One chart shot as HTML on the v3 stage. */
export function chart(job, built) {
  const uid = String(job.id || "x").replace(/[^a-z0-9]/gi, "") || "x";
  return (SCENES[job.chart?.scene] || fallback)(job, built, clockOf(job), uid);
}
