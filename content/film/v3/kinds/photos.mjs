// v3 photographs (FILM_LOOK_V3.md, "the archive at night"; ROUND2.md). Four kinds, each a pure
// function of a resolved job: `still` (the world room's full-frame picture, which draws its own
// frame), and `archive`, `stack` and `split`, which are prints lying on the dark desk under the
// one key light, inside the shared camera (`.cam > .rig`, base.css). shots.mjs draws every
// caption in the label slot; nothing here draws a credit. Every time is seconds from the shot's
// first frame; every move is a CSS animation the renderer steps frame by frame. No CSS filter
// sits on anything that moves (R4): shadows are box-shadows, focus is opacity.
import { esc, labels } from "../shots.mjs";

const W = 1920, H = 1080;
const f = (n, d = 3) => String(+Number(n).toFixed(d));
const px = (n) => `${f(n, 1)}px`;
const deg = (n) => `${f(n, 3)}deg`;
const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
const safeId = (id) => String(id ?? "x").replace(/[^a-zA-Z0-9_-]/g, "_");

/** A stable number in [0, 1) from a shot's id, so a print's tilt is the same on every render. */
function rand(id, salt = 0) {
  let h = 2166136261 ^ salt;
  for (const c of String(id)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  h = Math.imul(h ^ (h >>> 15), 2246822507);
  return ((h ^ (h >>> 13)) >>> 0) / 4294967296;
}

/** The year a date note carries ("c. 1914" → "1914"). */
const yearOf = (d) => (String(d ?? "").match(/\b(1[5-9]\d\d|20\d\d)\b/) || [])[0] || "";
/** Archival: graded mono, or a provenance year before 1970. */
const archival = (a) => /-mono\./.test(a?.url || "") || (+yearOf(a?.date) > 0 && +yearOf(a?.date) < 1970);

/** A scan's own edges to crop away, [top, right, bottom, left] as fractions: the asset's `trim`
    (or the shot's `params.trim`) when the plan or the grade measured one, else a hair off every
    edge of an archival scan, where scanners leave a line. */
function trimOf(job, a) {
  const t = a?.trim ?? job.params?.trim ?? (archival(a) ? 0.006 : 0);
  const v = Array.isArray(t) ? t : [t, t, t, t];
  return [0, 1, 2, 3].map((i) => clamp(+v[i] || 0, 0, 0.3));
}
const aspect = (a, tr = [0, 0, 0, 0]) => (a?.w && a?.h ? (a.w * (1 - tr[1] - tr[3])) / (a.h * (1 - tr[0] - tr[2])) : 1.4);
const viewBox = (tr) => (tr.some((x) => x > 0) ? `object-view-box:inset(${tr.map((x) => `${f(x * 100, 2)}%`).join(" ")});` : "");

/** Inline keyframes: one animation per element, each segment with its own easing. Stops are
    [fraction, css, easing]; fractions must rise. */
function keyframes(name, stops) {
  return `@keyframes ${name}{${stops.map(([p, css, ease]) => `${f(clamp(p, 0, 1) * 100, 3)}%{${css}${ease ? `;animation-timing-function:${ease}` : ""}}`).join("")}}`;
}
/** Stops in seconds → fractions of the shot, dropping any that would run backwards. */
function timed(stops, T) {
  const out = [];
  for (const [t, css, e] of stops) {
    const p = clamp(t / T, 0, 1);
    if (out.length && p <= out.at(-1)[0] + 0.0005) { if (p >= 0.9995) out[out.length - 1] = [1, css, e]; continue; }
    out.push([p, css, e]);
  }
  if (out[0]?.[0] > 0) out.unshift([0, out[0][1], out[0][2]]);
  if (out.at(-1)?.[0] < 1) out.push([1, out.at(-1)[1]]);
  return out;
}

// The house easings. GLIDE never quite stops, so a cut lands and leaves on motion.
const GLIDE = "cubic-bezier(0.30, 0.10, 0.45, 0.92)";
const SWING = "cubic-bezier(0.55, 0, 0.15, 1)";       // the reveal's pull: gathers, then a long soft landing
const SETTLE = "cubic-bezier(0.22, 1, 0.36, 1)";      // a print coming to rest, a camera arriving
const DIVE = "cubic-bezier(0.65, 0, 0.35, 1)";        // through the border and back (ROUND2 §8)

/** Spoken words (job.words): the onset of the first content word at or after `t`. */
const content = (w) => String(w.w ?? w.word ?? "").replace(/[^\p{L}\p{N}]/gu, "").length >= 4;
function wordAfter(job, t, until = Infinity) {
  const w = (job.words || []).find((x) => x.t >= t - 1e-6 && x.t <= until && content(x));
  return w ? +w.t : null;
}
/** The onset of the first word matching `re`. */
const wordMatch = (job, re) => (job.words || []).find((x) => re.test(String(x.w ?? x.word ?? "")))?.t ?? null;

/** The base camera's state at time t (base.css: +1% scale a second, `--cam-drift` px a second). */
const camScale = (t) => 1 + 0.01 * t;

/** Where the shared label slot will sit (shots.mjs `labels`), measured from its own text, so
    prints keep out of it. Inter at 28 px: about 14.6 px a character; tracked caps about 17.5. */
function labelBox(job) {
  const html = labels(job);
  if (!html) return null;
  const lines = [...html.matchAll(/<p class="(\w+)">([^<]*)<\/p>/g)];
  const wide = Math.max(0, ...lines.map(([, cls, t]) => t.replace(/&\w+;/g, "x").length * (cls === "honesty" ? 17.5 : 14.6)));
  const h = 22 + lines.length * 36 + (lines.length - 1) * 8;
  return { x0: 120, x1: 160 + Math.min(1150, wide) + 36, y0: H - 120 - h - 26, y1: H - 96 };
}
const hits = (r, b) => b && r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0;

// ── the world room ──────────────────────────────────────────────────────────────────────

const HOSTS = /^(wikimedia commons|wikipedia|flickr|pexels|pixabay|unsplash|internet archive|openverse)$/i;

/** What may sit over a world picture (VISUAL_SPEC §3.3), set in the one label slot so the world
    and the desk share a single caption component: place · year — credit (never a host), and
    "Illustration" on anything generated (BRAND: an illustration says it is one). */
function worldLabels(job) {
  const o = job.overlay || {};
  const credit = o.credit && !HOSTS.test(String(o.credit).trim()) && !/^https?:/.test(o.credit) ? o.credit : null;
  const where = [o.place, o.date].filter(Boolean).join(" · ");
  const source = [where, credit].filter(Boolean).join(" — ");
  if (!source && !o.illustration) return "";
  return `<div class="ph-scrim"></div><div class="labels">${source ? `<p class="source">${esc(source)}</p>` : ""}` +
    `${o.illustration ? `<p class="honesty">Illustration</p>` : ""}</div>`;
}

/** The still's own move as timed stops between t0 and t1: scale and a breath of 3D toward the
    focus. `whole` is the scale at which the picture is seen whole (a print's face, for the dive). */
function moveStops(job, t0, t1) {
  const r = job.render || {}, T = Math.max(0.1, t1 - t0), motion = job.motion || "push";
  const [fx] = job.focus || [0.5, 0.5];
  const deep = job.seconds >= 6;                         // long shots get the camera's 3D swing
  const side = fx < 0.5 ? 1 : -1;                        // swing toward the focus
  const ry = deep ? 1.1 * side : 0, rx = deep ? -0.45 : 0;
  const tf = (s, y = 0, x = 0, tx = 0) => `transform:perspective(2400px) translateX(${f(tx, 3)}%) rotateY(${deg(y)}) rotateX(${deg(x)}) scale(${f(s, 4)})`;
  const long = job.seconds > (r.long_after_s ?? Infinity);
  const to = (long ? r.long_to : r.to) ?? 1.07, from = r.from ?? 1;
  if (motion === "pull") return [[t0, tf(to, ry, rx), GLIDE], [t1, tf(from)]];
  if (motion === "drift") return [[t0, tf(from), GLIDE], [t1, tf(r.to ?? 1.03, ry * 0.6, rx * 0.6)]];
  if (motion === "pan-left" || motion === "pan-right") {
    const s = r.scale ?? 1.08, travel = (r.travel ?? 0.05) * 50, dir = motion === "pan-right" ? 1 : -1, sw = deep ? 0.7 : 0;
    return [[t0, tf(s, sw * dir, rx * 0.5, travel * dir), GLIDE], [t1, tf(s, -sw * dir, rx * 0.5, -travel * dir)]];
  }
  if (motion === "reveal") {
    const on = clamp(job.on ?? t0 + T * 0.3, t0, t1 - 0.3), pull = (t1 - on) * (r.pull_share ?? 0.7), hi = r.from ?? 1.35;
    return [[t0, tf(hi, ry, rx), "linear"], [on, tf(hi - 0.012, ry, rx), SWING], [on + pull, tf(r.to ?? 1), "linear"], [t1, tf(r.drift_to ?? 1.01)]];
  }
  return [[t0, tf(from), GLIDE], [t1, tf(to, ry, rx)]];                    // push
}
const FACE = "transform:perspective(2400px) translateX(0%) rotateY(0deg) rotateX(0deg) scale(1)";

export function still(job) {
  const a = job.asset || {}, T = Math.max(0.1, job.seconds), id = safeId(job.id), p = job.params || {};
  const [fx, fy] = job.focus || [0.5, 0.5], film = archival(a), tr = trimOf(job, a);
  const dive = p.enter === "dive", surface = p.exit === "surface";
  const D0 = dive ? Math.min(0.7, T * 0.2) : 0, D1 = dive ? D0 + Math.min(0.85, T * 0.2) : 0;   // print, then through the border
  const S0 = surface ? T - Math.min(0.7, T * 0.2) : T;
  // The picture's own move runs between the dive and the surfacing; as a print it is seen whole.
  let stops = moveStops(job, D1, S0);
  if (dive) stops = [[0, FACE, "linear"], [D0, FACE, DIVE], ...stops];
  if (surface) stops = [...stops.slice(0, -1), [S0, stops.at(-1)[1], DIVE], [T, FACE]];
  const css = [keyframes(`ph-mv-${id}`, timed(stops, T))];
  const at = `${f(fx * 100, 2)}% ${f(fy * 100, 2)}%`;
  const ar = aspect(a, tr);
  const img = `<img class="ph-img${film ? " ph-tone" : ""}" src="${esc(a.url)}" style="${viewBox(tr)}object-position:${at}" alt="">`;
  const move = `<div class="ph-move" style="animation:ph-mv-${id} ${f(T)}s linear both;transform-origin:${at}">${img}</div>`;
  let picture;
  if (dive || surface) {
    // The picture as a print on the desk: the frame-filling picture's own box, scaled down to a
    // print two thirds of the frame tall and laid on the desk; the camera then pushes through its
    // border to full bleed (or, surfacing, pulls back out to it).
    const ow = W * 1.024, oh = H * 1.024;
    const cw = ar > ow / oh ? oh * ar : ow, ch = ar > ow / oh ? oh : ow / ar;
    const left = (W - cw) * fx, top = (H - ch) * fy, k = (0.66 * H) / ch, b = 24 / k;
    const tx = W / 2 - (left + cw / 2), ty = H * 0.47 - (top + ch / 2);
    const desk = (s, r) => `transform:translate(${px(tx)},${px(ty)}) rotate(${deg(r)}) scale(${f(s, 4)})`;
    const bleed = "transform:translate(0px,0px) rotate(0deg) scale(1)";
    const ps = [];
    if (dive) ps.push([0, desk(k, -1.6), "linear"], [D0, desk(k * 1.025, -1.25), DIVE], [D1, bleed, "linear"]);
    else ps.push([0, bleed, "linear"]);
    if (surface) ps.push([S0, bleed, DIVE], [T, desk(k * 1.02, -1.3)]);
    else ps.push([T, bleed]);
    css.push(keyframes(`ph-dv-${id}`, timed(ps, T)));
    const sh = (v) => px(v / k);
    picture = `<div class="ph-desklight"></div><div class="ph-dive" style="left:${px(left)};top:${px(top)};width:${px(cw)};height:${px(ch)};` +
      `animation:ph-dv-${id} ${f(T)}s linear both"><i class="ph-dive-paper" style="inset:${px(-b)};` +
      `box-shadow:${sh(1)} ${sh(2)} ${sh(2)} rgb(0 0 0 / 0.6),${sh(18)} ${sh(28)} ${sh(40)} rgb(0 0 0 / 0.45)"></i>` +
      `<div class="ph-dive-face">${move}</div><i class="ph-sheen"></i></div>`;
  } else {
    picture = `<div class="ph-weave">${move}</div>`;
  }
  // Film dust on archival frames only, and only once the picture fills the frame.
  const dustIn = dive ? D1 - 0.2 : -1, dustOut = surface ? S0 : T + 1;
  const dust = film ? `<div class="ph-dust" style="--in:${f(dustIn)}s;--out:${f(dustOut)}s"></div>` : "";
  return `<section class="ph-world${dive || surface ? " ph-on-desk" : ""}" style="--dur:${f(T)}s">` +
    `<style>${css.join("")}</style>${picture}${dust}<div class="ph-vig"></div>${worldLabels(job)}</section>`;
}

// ── prints on the desk ──────────────────────────────────────────────────────────────────

/** A print: the photograph in its narrow border, the key light raking it from the upper left. */
function print(job, a, iw, ih, b, cls = "", style = "", extra = "") {
  const tr = trimOf(job, a);
  return `<div class="ph-print ${cls}" style="width:${px(iw + 2 * b)};height:${px(ih + 2 * b)};${style}">` +
    `<img src="${esc(a.url)}" style="left:${px(b)};top:${px(b)};width:${px(iw)};height:${px(ih)};${viewBox(tr)}" alt="">` +
    `<i class="ph-sheen"></i>${extra}</div>`;
}

/** Where a print enters from, and how it is tilted, varied by shot so no two land alike. */
function entry(id, salt = 0, k = 1) {
  const r1 = rand(id, salt + 1), r2 = rand(id, salt + 2), r3 = rand(id, salt + 3);
  const rot = (0.7 + 1.1 * r1) * (r2 < 0.5 ? -1 : 1) * Math.min(1, k);     // a wide print tilts less
  const ang = (r3 - 0.5) * 1.4 + (r2 < 0.5 ? Math.PI * 0.75 : Math.PI * 0.25);
  return { rot, lx: Math.cos(ang) * 120, ly: Math.abs(Math.sin(ang)) * 90 + 30, lr: rot * 2 + (r1 - 0.5) * 3 };
}
const landVars = (e, at, dur = 1.1, z = 160) =>
  `--lx:${px(e.lx)};--ly:${px(e.ly)};--lz:${px(z)};--lr:${deg(e.lr)};--land-at:${f(at)}s;--land-dur:${f(dur)}s`;

/** The camera beats of a long shot: something new lands every 3.5 s or sooner (ROUND2 S4), each
    on a spoken word. On a single print the beat is the camera moving into its detail. */
function beats(job, from = 3.0) {
  const out = [], T = job.seconds;
  let t = from;
  while (t < T - 1.2) {
    const w = wordAfter(job, t, t + 1.2);
    if (w == null) { t += 0.6; continue; }                 // land on words only, never between them
    out.push(w);
    t = w + 2.6;
  }
  return out;
}

/** The box a companion print fills: the desk to the right of a figure (type kinds narrow their
    own box to the left of it, shots.mjs draws it). */
export const COMPANION = { x0: 1040, x1: 1760, y0: 100, y1: 980 };

/** A companion print beside a figure: the photograph the sentence is about, landing on the desk on
    its word, with a slower push of its own than the type's camera, so the two read at two depths. */
export function companion(job) {
  const a = job.print;
  if (!a?.url) return "";
  const tr = trimOf(job, a), ar = aspect(a, tr), C = COMPANION, b = 26, T = job.seconds || 6;
  let ih = C.y1 - C.y0 - 2 * b, iw = ih * ar;
  if (iw + 2 * b > C.x1 - C.x0) { iw = C.x1 - C.x0 - 2 * b; ih = iw / ar; }
  const wo = iw + 2 * b, ho = ih + 2 * b, cx = (C.x0 + C.x1) / 2, cy = (C.y0 + C.y1) / 2;
  const [fx, fy] = a.focus || [0.5, 0.42];
  const e = entry(job.id, 7, 1100 / wo);
  const at = a.at == null ? -0.4 : Math.max(-0.4, +a.at - 0.25);   // arriving on its word, never early
  const id = safeId(job.id);
  const ox = cx - wo / 2 + b + fx * iw, oy = cy - ho / 2 + b + fy * ih;
  return `<style>@keyframes ph-comp-${id} { from { transform: scale(1); } to { transform: scale(${f(1 + Math.min(0.008 * T, 0.05), 4)}); } }</style>` +
    `<div class="ph-comp" style="transform-origin:${px(ox)} ${px(oy)};animation:ph-comp-${id} ${f(T)}s linear both">` +
    `<div class="ph-place" style="left:${px(cx - wo / 2)};top:${px(cy - ho / 2)};--rot:${deg(e.rot * 0.6)}">` +
    print(job, a, iw, ih, b, "ph-landing", landVars(e, at, 1.15)) + `</div></div>`;
}

export function archive(job) {
  const a = job.asset || {}, tr = trimOf(job, a), ar = aspect(a, tr);
  if (job.params?.treat === "sheet" || (job.params?.treat == null && ar >= 1.75)) return sheet(job, a, tr, ar);
  const T = job.seconds, id = safeId(job.id), [fx, fy] = job.focus || [0.5, 0.5];
  const sEnd = camScale(T), drift = 8 * T, TOP = 98, lab = labelBox(job);
  // As tall as the frame allows: the top stays inside title-safe (the camera's origin is the
  // print's top edge, so its push grows the print down and out), the bottom stays in frame, and
  // the print keeps clear of the label slot at the lower left for the whole shot.
  let b = 30, ho = Math.min(0.82 * H, (1010 - TOP) / sEnd), wo, cx;
  for (let i = 0; i < 40; i++) {
    const ih = ho - 2 * b; wo = ih * ar + 2 * b;
    cx = Math.max(W / 2 + 30, lab ? lab.x1 + 24 + wo / 2 : 0);
    const right = cx + (wo / 2) * sEnd + drift + 12, low = TOP + ho * sEnd;
    const clear = !lab || low < lab.y0 || cx - wo / 2 >= lab.x1 + 24;
    if (right <= 1800 && clear) break;
    ho -= 12;
  }
  const ih = ho - 2 * b, iw = ih * ar;
  const px0 = cx - wo / 2, py0 = TOP;
  const e = entry(job.id, 0, 1100 / wo);
  // The detail beats: on a spoken word every ~3.5 s, the camera moves into the print toward its
  // focus, arriving with weight; the shared camera keeps its constant push underneath.
  const ox = px0 + b + fx * iw, oy = py0 + b + fy * ih;
  const bs = T > 4.2 ? beats(job) : [];
  // In, deeper, then back out to the whole print to resolve before the cut.
  const steps = [1.12, 1.24, 1.04];
  const tilt = (i) => 4 - 1.1 * i;
  const inner = [[0, `transform:rotateX(4deg) rotateZ(0deg) scale(1)`, GLIDE]];
  let cur = 1.006;
  bs.forEach((t, i) => {
    inner.push([t, `transform:rotateX(${f(tilt(i) - 0.3)}deg) rotateZ(0deg) scale(${f(cur, 4)})`, SETTLE]);
    cur = steps[i] ?? cur;
    inner.push([Math.min(T, t + 1.3), `transform:rotateX(${f(tilt(i + 1))}deg) rotateZ(0deg) scale(${f(cur, 4)})`, GLIDE]);
    cur += 0.006;
  });
  inner.push([T, `transform:rotateX(${f(tilt(bs.length) - 0.4)}deg) rotateZ(0deg) scale(${f(cur + 0.004, 4)})`]);
  // The beats grow the print from its top edge (it never rises out of title-safe) and from as far
  // right as keeps its lower-left edge clear of the label slot: the left edge may not pass the
  // label's right edge, measured in the inner layer's own coordinates when the beat lands.
  let bx = ox;
  if (lab && bs.length && TOP + ho * sEnd * Math.max(...steps) > lab.y0) {
    for (const [i, t] of bs.entries()) {
      const sb = steps[i] ?? 1, lin = cx + (lab.x1 + 24 - cx - 8 * t) / camScale(t);
      if (sb > 1) bx = Math.min(bx, (px0 * sb - lin) / (sb - 1));
    }
    bx = Math.max(px0, bx);
  }
  return `<style>${keyframes(`ph-in-${id}`, timed(inner, T))}</style>` +
    `<div class="cam" style="perspective-origin:${px(cx)} ${px(TOP)}"><div class="rig" style="--cam-origin:${px(cx)} ${px(TOP)};--cam-drift:8px">` +
    `<div class="ph-inner" style="transform-origin:${px(bx)} ${px(TOP)};animation:ph-in-${id} ${f(T)}s linear both">` +
    `<div class="ph-place" style="left:${px(px0)};top:${px(py0)};--rot:${deg(e.rot)}">` +
    print(job, a, iw, ih, b, "ph-landing", landVars(e, -0.4, 1.15)) + `</div></div></div></div>`;
}

/** A sheet of stamps (or any wide sheet of small things): no border of ours, the scan is the
    object. The camera starts in close on the sheet with a rack focus, travels across it at
    reading speed, refocuses on the next subject at a spoken word, and pulls back to the whole
    sheet on the word that names it, landing every ~3.5 s. Depth of field is opacity between a
    sharp face and a soft one, never a filter on something moving. */
function sheet(job, a, tr, ar) {
  const T = job.seconds, id = safeId(job.id), sEnd = camScale(T), lab = labelBox(job);
  const TOP = 104;
  // At rest the whole sheet sits above the label slot for the whole shot.
  const ho = Math.min((Math.min(lab ? lab.y0 - 18 : 1000, 1000) - TOP) / sEnd, 0.78 * H);
  let sw = ho * ar, sh = ho;
  if (sw > 1500) { sw = 1500; sh = sw / ar; }
  const sx = (W - sw) / 2 + 10, sy = TOP;
  // The macro path, in the sheet's own fractions: start on the first row, refocus a row down on
  // the first beat, travel along it, then pull back to the whole sheet on the beat that names it.
  const M = 2.05, cxS = W / 2 + 20, cyS = H * 0.44;
  // Centre a point of the sheet, but never so far that the desk shows past the sheet's edge.
  const at = (u, v, s) => {
    let tx = cxS - (sx + u * sw) * s, ty = cyS - (sy + v * sh) * s;
    if (sw * s >= W) tx = clamp(tx, W - (sx + sw) * s, -sx * s);
    if (sh * s >= H) ty = clamp(ty, H - (sy + sh) * s, -sy * s);
    return `transform:translate(${px(tx)},${px(ty)}) scale(${f(s, 4)})`;
  };
  const whole = "transform:translate(0px,0px) scale(1)";
  const b1 = wordAfter(job, 2.6, 3.8) ?? Math.min(3.0, T * 0.3);
  const named = wordMatch(job, /^(stamps?|sheet|issue[sd]?)\b/i);
  // The pull back starts on the word that turns the sentence ("After") and lands on the word
  // that names the sheet ("stamp"), in and out like a dolly, never arriving early.
  const turn = wordMatch(job, /^(after|then|today|now)\b/i);
  const pullAt = Math.max(b1 + 2.4, turn ?? (named ?? T * 0.78) - 1.9);
  const back = named && named > pullAt + 0.8 ? named : pullAt + 1.9;
  const stops = [[0, at(0.14, 0.19, M * 1.04), GLIDE], [b1, at(0.30, 0.2, M), SETTLE], [b1 + 1.4, at(0.15, 0.5, M), GLIDE],
    [pullAt, at(0.42, 0.52, M * 0.98), DIVE], [back, whole, GLIDE], [T, "transform:translate(0px,0px) scale(1.012)"]];
  // The rack: a soft face over the sharp one at the cut, gone by 0.55 s (it exists only then: a
  // 7 px blur on the sheet costs ~70 ms a frame). The sharp face never animates. The sheet casts
  // its shadow only once it is seen whole on the desk again.
  const rack = [[0, "opacity:0.55;visibility:visible", "ease-out"], [0.55, "opacity:0;visibility:visible", "step-end"], [0.6, "opacity:0;visibility:hidden"], [T, "opacity:0;visibility:hidden"]];
  const shade = [[0, "box-shadow:0 0 0 rgb(0 0 0 / 0), 0 0 0 rgb(0 0 0 / 0)"], [Math.max(0.1, back - 1.2), "box-shadow:0 0 0 rgb(0 0 0 / 0), 0 0 0 rgb(0 0 0 / 0)", "ease-out"],
    [back, "box-shadow:var(--shadow-print)"], [T, "box-shadow:var(--shadow-print)"]];
  const img = `<img src="${esc(a.url)}" style="${viewBox(tr)}" alt="">`;
  return `<style>${keyframes(`ph-sh-${id}`, timed(stops, T))}${keyframes(`ph-rk-${id}`, timed(rack, T))}${keyframes(`ph-sd-${id}`, timed(shade, T))}</style>` +
    `<div class="cam"><div class="rig" style="--cam-origin:${px(sx + sw / 2)} ${px(TOP)}">` +
    `<div class="ph-sheetcam" style="animation:ph-sh-${id} ${f(T)}s linear both">` +
    `<div class="ph-sheet" style="left:${px(sx)};top:${px(sy)};width:${px(sw)};height:${px(sh)};animation:ph-sd-${id} ${f(T)}s linear both">` +
    `${img}<div class="ph-sheet-soft" style="animation:ph-rk-${id} ${f(T)}s linear both">${img}</div><i class="ph-sheen"></i></div>` +
    `</div></div></div>` + (lab ? `<div class="ph-labscrim" style="--at:${f(-1)}s;--out:${f(back - 0.6)}s"></div>` : "");
}

export function stack(job) {
  const list = (job.assets || []).slice(0, 5), n = list.length, T = job.seconds, id = safeId(job.id);
  if (!n) return "";
  const fi = Number.isInteger(job.params?.focus_index) && job.params.focus_index < n ? job.params.focus_index : null;
  const on = job.on ?? null, lab = labelBox(job);
  // Each print lands on a spoken word, about every 1.7 s, the last a breath before the focus.
  const last = on != null ? Math.max(0.6, on - 1.0) : T * 0.66;
  const times = [];
  list.forEach((a, i) => {
    if (a.at != null) return times.push(+a.at);
    if (i === 0) return times.push(0);
    const target = (i * last) / Math.max(1, n - 1);
    times.push(wordAfter(job, Math.max(target - 0.35, times[i - 1] + 1.1), last + 0.3) ?? target);
  });
  // A pile: equal heights; each print offset 120–200 px from the one beneath, tilted −6° and +4°
  // in turn, so every print below still shows; the top one casts its shadow over them.
  const b = 22, ih = n <= 3 ? 620 : 590, trs = list.map((a) => trimOf(job, a));
  const prints = list.map((a, i) => {
    const r = rand(job.id, 10 + i), ar = aspect(a, trs[i]);
    return { a, i, w: ih * ar + 2 * b, h: ih + 2 * b, at: times[i], rot: (i % 2 ? 4 : -6) + (r - 0.5) * 1.6,
      dx: i ? 120 + 80 * r : 0, dy: i ? (i % 2 ? 1 : -1) * (30 + 40 * rand(job.id, 30 + i)) : 0 };
  });
  let x = 0, y = 0;
  for (const p of prints) { x += p.dx; y += p.dy; p.cx = x; p.cy = y; }
  // Centre the pile, then keep it inside title-safe and clear of the label slot.
  const box = (p) => { const c = Math.abs(Math.cos(p.rot * Math.PI / 180)), s = Math.abs(Math.sin(p.rot * Math.PI / 180));
    const hw = (p.w * c + p.h * s) / 2, hh = (p.w * s + p.h * c) / 2; return { x0: p.cx - hw, x1: p.cx + hw, y0: p.cy - hh, y1: p.cy + hh }; };
  const all = () => prints.map(box).reduce((u, r) => ({ x0: Math.min(u.x0, r.x0), x1: Math.max(u.x1, r.x1), y0: Math.min(u.y0, r.y0), y1: Math.max(u.y1, r.y1) }));
  let u = all();
  const shift = (dx, dy) => prints.forEach((p) => { p.cx += dx; p.cy += dy; });
  shift(W / 2 + 40 - (u.x0 + u.x1) / 2, H * 0.47 - (u.y0 + u.y1) / 2);
  u = all();
  if (u.y0 < 100) shift(0, 100 - u.y0);
  for (let k = 0; k < 30 && prints.some((p) => hits(box(p), lab)); k++) shift(14, -6);
  u = all();
  const pcx = (u.x0 + u.x1) / 2, pcy = (u.y0 + u.y1) / 2;
  const fp = fi != null && on != null ? prints[fi] : null;
  const css = [], html = [];
  // The camera leans a little toward each print as it lands, then holds the pile while the one
  // that matters comes up to the lens.
  const follow = [[0, `transform:translate(${px((pcx - prints[0].cx) * 0.25)},${px((pcy - prints[0].cy) * 0.25)})`, GLIDE]];
  prints.slice(1).forEach((p, j) => {
    const c = prints.slice(0, j + 2).reduce((s, q) => [s[0] + q.cx, s[1] + q.cy], [0, 0]).map((v) => v / (j + 2));
    follow.push([p.at + 0.05, follow.at(-1)[1], SETTLE]);
    follow.push([p.at + 1.1, `transform:translate(${px((pcx - c[0]) * 0.25)},${px((pcy - c[1]) * 0.25)})`, GLIDE]);
  });
  follow.push([T, `transform:translate(${px(-6)},${px(0)})`]);
  css.push(keyframes(`ph-fl-${id}`, timed(follow, T)));
  for (const p of prints) {
    const e = { lx: (p.dx || 60) * 0.6, ly: 50 + 30 * rand(job.id, 50 + p.i), lr: p.rot > 0 ? 5 : -5 };
    const left = p.cx - p.w / 2, top = p.cy - p.h / 2;
    let anim = "", cls = "", extra = "";
    if (fp === p) {
      // On the word, the print the voice settles on comes up off the pile to the frame's centre,
      // three quarters of the frame tall, and straightens; its shadow falls longer and softer.
      const sOn = camScale(on), s = clamp((0.72 * H) / (p.h * sOn), 1.05, 1.6);
      // Its centre goes a little left of the frame's, so the dimmed pile still shows beside it;
      // the camera's state on the word (origin, push, drift) is allowed for.
      const vw = p.w * s * sOn, vh = p.h * s * sOn, want = [W / 2 - 70, H * 0.455];
      if (lab && want[1] + vh / 2 > lab.y0) want[0] = Math.max(want[0], lab.x1 + 28 + vw / 2);
      const cam = [pcx + (want[0] - pcx) / sOn + 8 * on, pcy + (want[1] - pcy) / sOn];
      css.push(`@keyframes ph-lift-${id}{from{transform:translate(0px,0px) scale(1) rotate(${deg(p.rot)});z-index:${p.i + 1}}` +
        `1%{z-index:40}to{transform:translate(${px(cam[0] - p.cx)},${px(cam[1] - p.cy)}) scale(${f(s, 4)}) rotate(${deg(-0.8)});z-index:40}}`);
      anim = `animation:ph-lift-${id} 1.1s ${SETTLE} ${f(on)}s both`;
      cls = " ph-focus";
    } else if (fp) {
      extra = `<i class="ph-dimmer" style="--at:${f(on)}s"></i>`;
      cls = " ph-dims";
    }
    html.push(`<div class="ph-place${cls}" style="left:${px(left)};top:${px(top)};z-index:${p.i + 1};--rot:${deg(p.rot)};--lift-at:${f(on ?? 0)}s;--at:${f(on ?? 0)}s;${anim}">` +
      print(job, p.a, p.w - 2 * b, ih, b, "ph-landing", landVars(e, p.i === 0 ? -0.4 : p.at - 0.04, 0.95, 140), extra) + `</div>`);
  }
  return `<style>${css.join("")}</style><div class="cam"><div class="rig" style="--cam-origin:${px(pcx)} ${px(pcy)}">` +
    `<div class="ph-inner" style="animation:ph-fl-${id} ${f(T)}s linear both">${html.join("")}</div></div></div>`;
}

/** The then-and-now's grade for the present-day footage (ROUND2 §2): −35% saturation, a touch
    warm, so the now sits beside the archive. render_shots.py applies it to the footage and to
    its poster; the stage only declares it. */
export const NOW_GRADE = "eq=saturation=0.65,colortemperature=temperature=5400:mix=0.5";

export function split(job) {
  const a = job.asset || {}, tr = trimOf(job, a), ar = aspect(a, tr), T = job.seconds, id = safeId(job.id);
  const right = job.params?.right || {};
  // The now lands on its word: `params.right_at` when the plan sets one, else the word that
  // names the present ("descendants", "today", "now"), else `on`, else the style's moment.
  const said = wordMatch(job, /^(descendants?|today|now|nowadays)\b/i);
  const landAt = +(job.params?.right_at ?? said ?? job.on ?? job.render?.right_at_s ?? 1.2);
  const year = yearOf(a.date);
  // Two prints of one size: the then on the desk inside the shared camera; the now upright on
  // the frame, outside the camera, so the footage composited into it stays registered.
  const ih = 500, iw = Math.min(720, ih * ar), b = 24, G = 96;
  const total = 2 * (iw + 2 * b) + G, x0 = (W - total) / 2, top = 236;
  const nowX = x0 + iw + 2 * b + G, nowY = top, ROT = 1.5;
  const e = entry(job.id);
  const thenRot = -0.8 - Math.abs(e.rot) * 0.5;
  // The then print's exposure eases down on the word that turns to the present, a beat that
  // hands the frame to today.
  const handoff = wordMatch(job, /^(now|today|right)\b/i);
  const dimThen = handoff && handoff > landAt + 1.5 ? `<i class="ph-dimmer ph-dimmer-soft" style="--at:${f(handoff)}s"></i>` : "";
  const poster = right.poster ? `<img src="${esc(right.poster)}" alt="">` : "";
  return `<div class="cam"><div class="rig" style="--cam-origin:${px(x0 + iw / 2 + b)} ${px(top)}">` +
    `<div class="ph-cap" style="left:${px(x0 + b)};top:${px(top - 100)};--at:-0.4s"><p>${esc(year)}</p></div>` +
    `<div class="ph-place" style="left:${px(x0)};top:${px(top)};--rot:${deg(thenRot)}">` +
    print(job, a, iw, ih, b, "ph-landing", landVars({ lx: -140, ly: 60, lr: -4 }, -0.4, 1.1), dimThen) + `</div></div></div>` +
    `<div class="ph-cap" style="left:${px(nowX + b)};top:${px(top - 100)};--at:${f(landAt - 0.1)}s"><p>Today</p></div>` +
    `<div class="ph-now" style="left:${px(nowX)};top:${px(nowY)};width:${px(iw + 2 * b)};height:${px(ih + 2 * b)};--rot:${deg(ROT)};--at:${f(landAt - 0.5)}s">` +
    `<div class="ph-now-face" style="left:${px(b)};top:${px(b)};width:${px(iw)};height:${px(ih)}">${poster}</div><i class="ph-sheen"></i></div>` +
    // The compositing contract (render_shots.py): the footage's unrotated box, its start, its
    // rotation about the box's centre (clockwise, degrees) and its grade.
    `<div class="split-right" data-at="${f(landAt)}" data-rot="${ROT}" data-grade="${esc(NOW_GRADE)}" ` +
    `style="left:${px(nowX + b)};top:${px(nowY + b)};width:${px(iw)};height:${px(ih)}"></div>`;
}
