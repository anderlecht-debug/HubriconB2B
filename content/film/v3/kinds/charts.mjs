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
// start their entrances at -0.4 s. The camera is base.css's one rig, anchored on the left grid and
// capped for a chart's length (see camCSS); each chart's own move rides on an inner layer.
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
// Title-safe for what the plot layer may push into, inside the chart camera's own 3.5% push.
const SAFE = { l: 168, r: 1700, t: 104, b: 940 };
const ORIGIN = { x: 160, y: 486 };                           // the rig pushes about the left grid
/** The heading block's foot: a heading line, and a caption line under it when there is one. */
const headFoot = (p) => (p?.caption ? 252 : p?.heading ? 186 : 104);
/** The plot's baseline: its tick labels clear shots.mjs's label slot (taller when a source line sits in it). */
const floorOf = (job) => (job.source_label ? 676 : 776);

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

/** The shot's clock: length, `on`, reveals by key (with the onset their figure is spoken). */
function clockOf(job) {
  const S = Number(job.seconds) || 8;
  const reveals = Array.isArray(job.reveals) ? job.reveals : [];
  const rv = (k) => {
    const r = reveals.find((x) => x.key === k && Number.isFinite(+x.t) && +x.t >= 0 && +x.t <= S);
    return r ? { ...r, at: spoken(job, r) } : null;
  };
  const on = Number.isFinite(job.on) && job.on >= 0 && job.on <= S ? job.on : null;
  return { S, on, rv };
}

/** Times spread evenly over [a, b] (n of them; one lands at a). */
const spread = (n, a, b) => Array.from({ length: n }, (_, i) => (n === 1 ? a : a + ((b - a) * i) / (n - 1)));
/** A small stable hash of a shot id, for choosing among camera variants. */
const hash = (s) => [...String(s)].reduce((h, c) => (h * 33 + c.charCodeAt(0)) >>> 0, 5381);

// ---------------------------------------------------------------- the camera

/**
 * base.css's rig pushes 1% of scale a second and drifts 8 px a second: on a 20 s chart that is a
 * 20% push that carries the left grid 360 px out of frame. This inner layer turns the rig, for a
 * chart, into the same kind of move at a rate the chart can hold: a constant push of at most 3.5%
 * over the shot about the left grid (so the heading stays on the grid), and no lateral drift.
 * It is the exact inverse of the rig composed with that move, sampled so the speed stays constant.
 */
function camCSS(uid, S) {
  const a = Math.min(0.01, 0.035 / S);
  const n = 10;
  const kf = Array.from({ length: n + 1 }, (_, i) => {
    const t = (S * i) / n, k = (1 + a * t) / (1 + 0.01 * t);
    return `${r1((i / n) * 100)}%{transform:translateX(${s3(8 * t)}px) scale(${k.toFixed(5)})}`;
  }).join("");
  return `@keyframes chc-${uid}{${kf}}.ch-cam-${uid}{animation:chc-${uid} ${s3(S)}s linear 0s both}`;
}

/**
 * The plot layer's own move, on top of the camera: keyframes of translate and scale about a focus
 * point, kept inside SAFE for the content's bounds. Between keys it eases; the rig under it never
 * stops, so the frame never comes to rest.
 */
function pushCSS(uid, S, keys, box, top = SAFE.t) {
  const fit = ({ s = 1, fx = 960, fy = 540 }) => {
    let tx = fx * (1 - s), ty = fy * (1 - s);
    const xlo = SAFE.l - box.l * s, xhi = SAFE.r - box.r * s, ylo = top - box.t * s, yhi = SAFE.b - box.b * s;
    tx = xlo <= xhi ? clamp(tx, xlo, xhi) : (xlo + xhi) / 2;
    ty = ylo <= yhi ? clamp(ty, ylo, yhi) : (ylo + yhi) / 2;
    return `translate(${r1(tx)}px,${r1(ty)}px) scale(${s})`;
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
  return `<style>${camCSS(uid, S)}${css}</style>` +
    `<div class="cam ch" style="--cam-origin:${ORIGIN.x}px ${ORIGIN.y}px"><div class="rig"><div class="ch-cam ch-cam-${uid}">` +
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
  /** Gridlines and rules masked wherever a label sits over them. */
  const mask = (uid) => `<mask id="chm-${uid}" maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080"><rect width="1920" height="1080" fill="#fff"/>` +
    boxes.map(([x, y, w, h]) => `<rect x="${r1(x)}" y="${r1(y)}" width="${r1(w)}" height="${r1(h)}" rx="10" fill="#000"/>`).join("") + `</mask>`;
  return { label, est, mask, boxes };
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
 */
function staircase(job, built, C, uid) {
  const st = built.charts.stairs;
  const { S, on, rv } = C;
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
    edgeT = E?.at ?? (on ?? S * 0.45);
    riserT = R?.at ?? snap(job, edgeT + 0.35);
  } else {
    listT = on ?? S * 0.45;
    edgeT = snap(job, listT + 0.3);
    riserT = snap(job, edgeT + 0.3);
  }
  const first = Math.min(edgeT, riserT, listT ?? Infinity);
  let drawB = recall ? Math.min(first - 0.2, 0.4) : clamp(cue(job, /^tread|^staircase/, 0.8, first - 0.2) ?? first - 0.3, drawA + 1.0, drawA + 2.6);
  const anchor = E && E.at > drawA + 0.6 ? E.at : null;     // the pen reaches the edge as "8" is spoken
  if (anchor) drawB = Math.max(drawB, anchor + 0.9);
  if (cf) listT = edgeT < riserT - 1.5 ? snap(job, (edgeT + riserT) / 2) : (cue(job, /candidate|listing|product/, drawB, edgeT - 0.3) ??
    clamp(snap(job, (drawB + edgeT) / 2), drawB + 0.15, Math.max(drawB + 0.15, edgeT - 0.4)));
  const figT = cf ? (R?.at ?? Math.max(riserT, cue(job, /differen|riser|turn/, riserT - 0.5) ?? riserT + 0.3)) : riserT + 0.3;
  const ghostT = PK?.at ?? cue(job, /^staircases$|^peak$/, 0.5) ?? (cf ? (riserT + 2.4 <= S - 1.6 ? snap(job, riserT + 2.4) : recall ? S - 2 : drawA + 0.6) : snap(job, (drawB + listT) / 2));
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

  let grid = "", svg = "", under = "", html = "", over = "";
  yt.forEach((v) => {
    grid += `<path class="ch-grid ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${r1(Y(v))} H${P.r}"/>`;
    svg += `<text class="ch-tick ch-in" x="${P.r + 26}" y="${r1(Y(v))}" dominant-baseline="central" style="${at(-0.4)}">$${v.toFixed(2)}</text>`;
  });
  for (const [edge] of [[0], ...tr]) grid += `<path class="ch-edge ch-fade" style="${at(-0.4)}" d="M${r1(X(edge))},${P.b} V${P.t - 10}"/>`;
  svg += `<path class="ch-axis ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${P.b} H${P.r}"/>`;
  for (const [edge] of [[0], ...tr]) {
    const hot = edge === st.edge.oz;
    svg += `<text class="ch-tick ch-in${hot ? " ch-hot" : ""}" x="${r1(X(edge))}" y="${P.b + 44}" text-anchor="middle" style="${at(-0.4)}${hot ? `;--hot:${s3(edgeT)}` : ""}">${edge}${edge === xMax ? " oz" : ""}</text>`;
  }
  svg += `<text class="ch-axisname ch-in" x="1690" y="${P.t - 52}" text-anchor="end" style="${at(-0.4)}"><tspan>Fee</tspan><tspan x="1690" dy="32">a unit</tspan></text>`;

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
  const css = pushCSS(uid, S, keys, { l: P.l - 20, r: 1700, t: P.t - 76, b: P.b + 60 }, headFoot(job.params) + 8) + depth;

  const p = job.params || {};
  const dashed = /dash/i.test(p.caption || "");
  const head = heading({ title: p.heading, caption: p.caption, captionAt: dashed ? ghostT + 0.3 : -0.4 });
  svg = `<defs>${L.mask(uid)}</defs><g mask="url(#chm-${uid})">${grid}</g>${svg}` +
    `<g class="ch-rack-${uid}">${stairs}</g>${near}`;
  return stage({ uid, S, css, under, svg, html: `<div class="ch-layer ch-rack-${uid}">${html}</div>${fg}`, over, head });
}

// ---------------------------------------------------------------- the Monte Carlo

/**
 * The simulated years of one listing's cumulative profit (built.charts.mc), as the simulation runs:
 * month by month, a column of points (one per simulated year the data carries) lands, with each
 * year's faint thread drawn behind it. The median, the one number, draws in blue with its figure;
 * the slow and strong years' ends land in the light; the P10–P90 band fills, ivory at 10%, on
 * "range". A return of the same chart takes another camera: a truck along the months, or a push
 * into the band's end.
 */
function montecarlo(job, built, C, uid) {
  const mc = built.charts.mc;
  const { S, on } = C;
  const L = labeller();
  const P = { l: 330, r: 1360, t: 350, b: floorOf(job) };
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
  const named = cue(job, /^number|^median|^middle/, 0.6);
  const runB = clamp(Math.min((on ?? S * 0.5) - 1.0, (named ?? Infinity) - 0.15), runA + 1.4, runA + 3.2);
  const step = (runB - runA) / n;
  const medT = named ?? snap(job, runB + 0.2);
  const lowT = cue(job, /^slow|^low|^bad/, medT + 0.3) ?? snap(job, (on ?? runB + 1) + 0.3);
  const highT = cue(job, /^strong|^high|^good/, lowT + 0.2) ?? snap(job, lowT + 0.8);
  const bandT = cue(job, /^range/, highT) ?? on ?? highT + 0.6;
  const fillT = Math.max(bandT, highT + 0.3);

  // ---- svg
  let grid = "", svg = "", html = "";
  ticks.forEach((v) => {
    grid += `<path class="ch-grid ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${r1(Y(v))} H${P.r}"/>`;
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
  svg += `<g class="ch-threads ch-wipe" style="${at(runA, runB - runA + 0.2)}">` +
    mc.paths.map((p) => `<path d="${line(p)}"/>`).join("") + `</g>`;
  months.forEach((_, i) => {
    if (i === 0) return;
    svg += `<g class="ch-month ch-pop-col" style="${at(runA + step * i)}">` +
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
  const keys = variant === "truck"
    ? [{ t: 0, s: 1.05, fx: P.l + 60, fy: P.b - 80 }, { t: runB, s: 1.05, fx: P.r - 100, fy: Y(p50[n]) }, { t: S, s: 1.03, fx: P.r, fy: Y(p50[n]) }]
    : [{ t: 0, s: 1 }, { t: Math.max(0.1, bandT - 1.5), s: 1.02, fx: P.r, fy: Y(p50[n]) }, { t: S, s: 1.09, fx: P.r + 80, fy: Y(p50[n]) }];
  const css = `@keyframes chb-${uid}{from{d:path("${band(p50, p50)}");opacity:0}to{d:path("${band(p90, p10)}");opacity:1}}` +
    `.ch-band-${uid}{animation:chb-${uid} calc(var(--d)*1s) var(--ease-out) calc(var(--at)*1s) both}` +
    pushCSS(uid, S, keys, { l: 160, r: 1690, t: P.t - 60, b: P.b + 60 }, headFoot(job.params) + 8);
  const p = job.params || {};
  const head = heading({ title: p.heading, caption: p.caption });
  svg = `<defs>${L.mask(uid)}</defs><g mask="url(#chm-${uid})">${grid}</g>${svg}`;
  return stage({ uid, S, css, under, svg, html, head });
}

// ---------------------------------------------------------------- the aging cliff

/**
 * What a listing's units cost to store a month by age (built.charts.aging). A playhead walks the
 * units' age from day 0 and each band draws up from the baseline as it is reached, the last below
 * the cliff on its spoken days; at the cliff day the bands beyond it draw up fast, in blue (the
 * leak), the riser flashes and the camera takes the hit. The spoken surcharge rates land in a
 * ledger above the young stock.
 */
function aging(job, built, C, uid) {
  const ag = built.charts.aging;
  const { S, on, rv } = C;
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
  const cliffT = dayR?.at ?? on ?? S * 0.6;
  const walkA = -0.4;
  // the walk: a stop at each band's first day (the last below the cliff on its words), then the cliff
  const stops = [...pre.map((b) => b.from), ag.cliff];
  let times;
  if (bandR && bandR.at > walkA + 2 && bandR.at < cliffT - 0.6) times = [...spread(pre.length - 1, walkA, bandR.at - (bandR.at - walkA) / pre.length), bandR.at, cliffT];
  else times = spread(stops.length, walkA, cliffT);
  const surT = before ? cue(job, /^surcharge/, 0, before.at) ?? before.at : null;
  const cuT = before ? cue(job, /^cubic/, before.at) ?? before.at + 0.6 : null;
  const youngT = cue(job, /^young/, cliffT);
  const p = job.params || {};
  const saysMonth = /a month/i.test(`${p.heading || ""} ${p.caption || ""}`);

  // ---- svg
  let grid = "", svg = "", under = "", html = "";
  yt.forEach((v) => {
    if (v > 0) grid += `<path class="ch-grid ch-draw" pathLength="1" style="${at(-0.4, 0.8)}" d="M${P.l},${r1(Y(v))} H${P.r}"/>`;
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
    html += L.label(lx, ly + 44, (before ? fig(before.value, before.at, { cls: "ch-fig-s2" }) + unit("a cubic foot", 72, cuT) : "") +
      (after ? `<span class="ch-arrow ch-in" style="${at(after.at - 0.1)}">→</span>${fig(after.value, after.at, { money: true, cls: "ch-fig-s2" })}` : ""),
      { cls: "ch-row", v: "t", w: 640, h: 80 });
  }

  const css = `@keyframes chw-${uid}{${kf}}.ch-play-${uid}{animation:chw-${uid} ${s3(S)}s cubic-bezier(.45,0,.3,1) 0s both, ch-fade .4s ease calc(var(--at)*1s) both, ch-out .5s ease calc(var(--off)*1s) forwards}` +
    `@keyframes chj-${uid}{0%,${r1((cliffT / S) * 100)}%{translate:0 0}${r1(((cliffT + 0.05) / S) * 100)}%{translate:0 10px}${r1(((cliffT + 0.15) / S) * 100)}%{translate:0 -4px}${r1(((cliffT + 0.32) / S) * 100)}%,100%{translate:0 0}}` +
    `.ch-jolt-${uid}{animation:chj-${uid} ${s3(S)}s linear 0s both}` +
    (youngT != null ? `.ch-young .ch-col-fill{animation:ch-young-fill 1.2s ease ${s3(youngT)}s both}` : "") +
    pushCSS(uid, S, [{ t: 0, s: 1 }, { t: Math.max(0.1, cliffT - 1.4), s: 1.02, fx: cx, fy: 620 }, { t: cliffT + 0.05, s: 1.025, fx: cx, fy: 620 },
      { t: cliffT + 0.6, s: 1.06, fx: cx, fy: 600 }, { t: S, s: 1.07, fx: cx + 100, fy: 600 }], { l: 160, r: 1660, t: P.t - 60, b: P.b + 60 }, headFoot(p) + 8);
  const head = heading({ title: p.heading, caption: p.caption });
  svg = `<defs>${L.mask(uid)}</defs><g mask="url(#chm-${uid})">${grid}</g>${svg}`;
  return stage({ uid, S, css, under, svg: `<g class="ch-jolt-${uid}">${svg}</g>`, html: `<div class="ch-jolt-${uid} ch-layer">${html}</div>`, head });
}

// ---------------------------------------------------------------- the waterfall

/**
 * One month of the film's demo catalogue, revenue to net (job.chart_data, the waterfall in the
 * film's own run.json). Each bar draws up from its own base: revenue, then Amazon's fees on
 * "Amazon's", then landed cost, ads and net. The fees are the leak and the shot's one blue: their
 * share of revenue lands on "32.1%", their figure on "$102,395", the figure the line lands on.
 * Every value sits above its bar; costs carry a true minus.
 */
function waterfall(job, built, C, uid) {
  const w = job.chart_data;
  if (!w || !Number.isFinite(+w.revenue)) return fallback(job, built, C, uid);
  const { S, on, rv } = C;
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
  const feesT = cue(job, /^amazon/, 1, heroT) ?? (share ? share.at - 4.5 : heroT - 2.2);
  const shareT = share?.at ?? null;
  const restA = snap(job, Math.max(heroT, shareT ?? 0) + 1.3);
  const restT = spread(3, Math.min(restA, S - 4.2), Math.min(restA + 3, S - 1.2));
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
      { t: restT[0] - 0.2, s: 1.07, fx: cxOf(1) + 120, fy: fy0 - 40 }, { t: S, s: 1.03, fx: 900, fy: 600 }], { l: 160, r: 1660, t: fy0 - 210, b: P.b + 60 }, 224);
  const p = job.params || {};
  const period = /^\d{4}-\d{2}/.test(String(w.period || "")) ? new Date(`${String(w.period).slice(0, 7)}-15T00:00:00Z`).toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" }) : "";
  const head = heading({ kicker: ["Revenue to net", period].filter(Boolean).join(" · "), title: p.heading || brand?.value || "", titleAt: brand?.at ?? -0.4, caption: p.caption });
  return stage({ uid, S, css, under, svg, html, head });
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
  const css = pushCSS(uid, S, [{ t: 0, s: 1 }, { t: S, s: 1.02, fx: 700, fy: 560 }], { l: 160, r: 1600, t: 120, b: 840 });
  return stage({ uid, S, css, svg, html, head: heading({ title: p.heading || "", caption: p.caption }) });
}

// ---------------------------------------------------------------- entry

const SCENES = { staircase, montecarlo, aging, waterfall };

/** One chart shot as HTML on the v3 stage. */
export function chart(job, built) {
  const uid = String(job.id || "x").replace(/[^a-z0-9]/gi, "") || "x";
  return (SCENES[job.chart?.scene] || fallback)(job, built, clockOf(job), uid);
}
