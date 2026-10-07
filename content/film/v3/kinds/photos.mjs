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

/** The shared camera's scale at time t of a shot T seconds long (base.css @keyframes cam): one linear
    move over the whole shot to 1 + min(1% × T, 6%), so a long shot pushes more slowly, never further.
    Its drift is linear too: `--cam-drift` × T in all, applied inside the scale. */
const camScale = (t, T) => 1 + Math.min(0.01 * T, 0.06) * clamp(t / Math.max(T, 0.1), 0, 1);
const camDrift = (t, T, perSecond) => perSecond * T * clamp(t / Math.max(T, 0.1), 0, 1) * camScale(t, T);

/** Where the shared label slot will sit (shots.mjs `labels`), measured from its own text, so
    prints keep out of it. Inter at 28 px: about 13.2 px a character (measured on c24b's 82-character
    credit: 1025 px); tracked caps about 17.5. A line longer than the slot wraps, balanced. */
function labelBox(job) {
  const html = labels(job);
  if (!html) return null;
  const lines = [...html.matchAll(/<p class="(\w+)">([^<]*)<\/p>/g)];
  const max = /with-print/.test(html) ? 820 : 1150;
  let rows = 0, wide = 0;
  for (const [, cls, t] of lines) {
    const w = t.replace(/&\w+;/g, "x").length * (cls === "honesty" ? 17.5 : 13.2);
    const n = Math.max(1, Math.ceil(w / max));
    rows += n;
    wide = Math.max(wide, Math.min(max, (w / n) * (n > 1 ? 1.08 : 1)));
  }
  const h = 22 + rows * 36 + (lines.length - 1) * 8;
  return { x0: 120, x1: 160 + wide + 36, y0: H - 120 - h - 26, y1: H - 96 };
}
const hits = (r, b) => b && r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0;
/** The desk's dark under the label slot while a print lies beneath it, sized to the label itself
    (a two-line credit over a white page needs more than a corner's shadow), from `at` to `out`. */
// An even fall of the light across the frame's foot, rising just above the label, never a dark
// ellipse behind it: a blob over a bright picture or a white page reads as a smudge on it.
const scrimBg = (lab, k = 1) => {
  const h = H - lab.y0 + 90;
  return `background:linear-gradient(to top, color-mix(in srgb, var(--ground) ${f(80 * k, 1)}%, transparent) 0, ` +
    `color-mix(in srgb, var(--ground) ${f(62 * k, 1)}%, transparent) ${px(h * 0.42)}, color-mix(in srgb, var(--ground) ${f(24 * k, 1)}%, transparent) ${px(h * 0.78)}, transparent ${px(h)})`;
};
const labScrim = (lab, at, out) => `<div class="ph-labscrim" style="--at:${f(at)}s;--out:${f(out)}s;${scrimBg(lab)}"></div>`;

// ── the world room ──────────────────────────────────────────────────────────────────────

const HOSTS = /^(wikimedia commons|wikipedia|flickr|pexels|pixabay|unsplash|internet archive|openverse)$/i;
/** A picture made after the war is outside this archive's period: it says when it was taken, for as
    long as it fills the frame, so a modern photograph of an old depot never stands in for the past. */
const MODERN = 1946;

/** What a world picture's caption may say, from its record only (the plan's `overlay` first, then the
    asset render_shots resolved): its date as the record gives it (render_shots' display_date, "c."
    kept), else a circa year the record's own title states ("Advertising Postcard, circa 1920"),
    never a year guessed; the place when it is more than a country; the institution that holds it
    (never a host, an uploader or a URL); and the plan's own `caption` ("A posed photograph"). */
function worldCaption(job) {
  const o = job.overlay || {}, a = job.asset || {};
  const clean = (x) => String(x || "").replace(/\s+/g, " ").trim().replace(/^Smithsonian Institution, (?:the )?/i, "Smithsonian ");
  let date = o.date ?? a.date ?? null;
  if (!date) {
    const m = String(a.title || "").match(/\b(?:circa|ca\.|c\.)\s*(1[5-9]\d\d|20\d\d)\b/i);
    if (m) date = `c. ${m[1]}`;
  }
  const year = +(String(date || "").match(/\b(1[5-9]\d\d|20\d\d)\b/) || [])[1] || 0;
  const modern = year >= MODERN;
  const place = o.place ?? (a.place && !/^(united states( of america)?|usa|u\.s\.a?\.?)$/i.test(a.place.trim()) ? a.place : null);
  const raw = o.credit ?? a.credit;
  const credit = raw && !HOSTS.test(clean(raw)) && !/^https?:/.test(raw) && clean(raw).length <= 90 ? clean(raw) : null;
  const when = date ? (modern ? `Photographed ${/^c\./.test(date) ? "" : "in "}${date}` : String(date)) : null;
  const head = o.caption ? [o.caption, when].filter(Boolean).join(", ") : [place, when].filter(Boolean).join(" · ");
  return { text: [head, credit].filter(Boolean).join(" — "), modern, dated: !!date, illustration: !!o.illustration };
}

/** The caption over a world picture (VISUAL_SPEC §3.3, W1), in the one label slot so the world and
    the desk share a single caption component. It arrives once the picture fills the frame and leaves
    before it surfaces, about four seconds, like a lower third; a modern photograph keeps its date on
    screen the whole time it fills the frame; "Illustration" stays on anything generated (BRAND). */
function worldLabels(job, enter, t1) {
  const c = worldCaption(job);
  if (!c.text && !c.illustration) return "";
  const hold = c.modern || c.illustration;
  const t0 = hold ? enter[0] : enter[1];                  // a modern date is said while the dive is still going
  const out = hold ? t1 : Math.min(t1, t0 + 4.0);
  if (!hold && out - t0 < 1.5) return "";                // too short to read: the description credits it
  const leave = out >= job.seconds - 0.01 ? 99 : out - 0.4;   // held to the cut, never faded before it
  // the scrim is sized to the caption itself: a long credit over a bright photograph stays readable
  const w = Math.min(1150, c.text.length * 13.2), rows = Math.max(1, Math.ceil(c.text.length * 13.2 / 1150)) + (c.illustration ? 1 : 0);
  const lab = { x1: 160 + w + 36, y0: H - 120 - (22 + rows * 36) - 26, y1: H - 96 };
  return `<div class="ph-wlab" style="--in:${f(t0)}s;--out:${f(leave)}s"><div class="ph-scrim" style="${scrimBg(lab)}"></div><div class="labels">` +
    `${c.text ? `<p class="source">${esc(c.text)}</p>` : ""}${c.illustration ? `<p class="honesty">Illustration</p>` : ""}</div></div>`;
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
    `<style>${css.join("")}</style>${picture}${dust}<div class="ph-vig"></div>${worldLabels(job, dive ? [D0 + 0.15, D1 + 0.3] : [0.3, 0.45], surface ? S0 - 0.1 : T)}</section>`;
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
  let a = job.print;
  if (!a?.url) return "";
  let tr = trimOf(job, a), ar = aspect(a, tr);
  const C = COMPANION, b = 26, T = job.seconds || 6;
  // A panorama in a 720 px box is a strip (a06's 2.8:1 plate, 250 px tall): it is printed as a
  // crop of itself, no wider than 1.7:1, about its focus. Framing, never retouching.
  if (ar > 1.7) {
    const keep = 1.7 / ar, fx0 = (a.focus || [0.5])[0], vis = 1 - tr[1] - tr[3];
    const l = clamp(fx0 - keep / 2, 0, 1 - keep);
    tr = [tr[0], tr[1] + (1 - keep - l) * vis, tr[2], tr[3] + l * vis];
    a = { ...a, trim: tr, focus: [(fx0 - l) / keep, (a.focus || [0.5, 0.42])[1]] };
    ar = aspect(a, tr);
  }
  let ih = C.y1 - C.y0 - 2 * b, iw = ih * ar;
  if (iw + 2 * b > C.x1 - C.x0) { iw = C.x1 - C.x0 - 2 * b; ih = iw / ar; }
  const wo = iw + 2 * b, ho = ih + 2 * b, cx = (C.x0 + C.x1) / 2, cy = (C.y0 + C.y1) / 2;
  const [fx, fy] = a.focus || [0.5, 0.42];
  const e = entry(job.id, 7, 1100 / wo);
  const at = a.at == null ? -0.4 : Math.max(-0.4, +a.at - 0.25);   // arriving on its word, never early
  const id = safeId(job.id);
  const ox = cx - wo / 2 + b + fx * iw, oy = cy - ho / 2 + b + fy * ih;
  // `out`: the print is lifted off the desk, gone by then (a sentence it must not seem to illustrate)
  const out = a.out == null ? null : clamp(+a.out, 0.5, T);
  const lift = out == null ? "" : `;animation:ph-comp-out 0.45s cubic-bezier(0.55, 0, 0.75, 0.2) ${f(out - 0.45)}s both`;
  return `<style>@keyframes ph-comp-${id} { from { transform: scale(1); } to { transform: scale(${f(1 + Math.min(0.008 * T, 0.05), 4)}); } }</style>` +
    `<div class="ph-comp" style="transform-origin:${px(ox)} ${px(oy)};animation:ph-comp-${id} ${f(T)}s linear both">` +
    `<div class="ph-comp-lift" style="position:absolute;inset:0${lift}">` +
    `<div class="ph-place" style="left:${px(cx - wo / 2)};top:${px(cy - ho / 2)};--rot:${deg(e.rot * 0.6)}">` +
    print(job, a, iw, ih, b, "ph-landing", landVars(e, at, 1.15)) + `</div></div></div>`;
}

// The desk's frame for a print: the top stays inside title-safe, the bottom inside the frame at
// the end of the shared push, the sides inside 120…1800 (a print is a picture, not type).
const TOP = 98, BOT = 1010, XL = 120, XR = 1800;
/** Kinds that leave a page or a print on the desk: a print cut after one opens at a second scale. */
const DESK = new Set(["document", "table", "receipt", "quote", "archive", "stack", "split"]);

/** Where a print lies for the whole shot: the largest print that fits, centred a little right of
    the frame's middle (the key light is upper left, the label slot lower left); if at the end of
    the shared push it would reach down into the label slot, it is first lowered to clear it, and
    moved right of the label instead only when lowering would leave it under 60% of the frame, or
    when moving gains a third of its area without leaving the middle (a portrait print beside a long
    credit). A long credit never shrinks a print to a corner (c24b). */
function layPrint(ar, T, lab, b = 30) {
  const sEnd = camScale(T, T), drift = camDrift(T, T, 8), hMax = Math.min(0.84 * H, (BOT - TOP) / sEnd);
  const wOf = (ho) => (ho - 2 * b) * ar + 2 * b;
  // its footprint over the shot: the rig grows it about its top centre and drifts it right
  const foot = (ho, cx) => {
    const wo = wOf(ho);
    return { x0: Math.min(cx - wo / 2, cx - (wo / 2) * sEnd + drift), x1: cx + (wo / 2) * sEnd + drift, y0: TOP, y1: TOP + ho * sEnd };
  };
  const fits = (ho, cx) => { const r = foot(ho, cx); return r.x1 + 12 <= XR && r.x0 >= XL; };
  const C = W / 2 + 30;
  let hA = hMax;
  while (hA > 240 && !fits(hA, C)) hA -= 4;
  const clash = !!lab && hits(foot(hA, C), lab);
  if (clash) hA = Math.min(hA, (lab.y0 - 18 - TOP) / sEnd);
  let hB = 0, cB = C;
  if (clash) {
    for (hB = hMax; hB > 240; hB -= 4) {
      cB = Math.max(C, lab.x1 + 24 + wOf(hB) / 2);
      if (fits(hB, cB)) break;
    }
  }
  // right of the label only when lowering would leave the print under 60% of the frame, or when it
  // gains a third of its area for a modest move (a print far off to the right empties the middle)
  const area = (h) => h * wOf(h);
  const right = clash && hB > hA && (hA < 0.6 * H || (cB - C < 300 && area(hB) > 1.3 * area(hA)));
  const ho = right ? hB : hA, cx = right ? cB : C;
  return { ho, wo: wOf(ho), cx, b, sEnd };
}

/** A print on the desk (archive-framed). Two openings, so consecutive desk shots never cut at one
    scale: `whole` lands the print and moves into its detail on spoken words; `tight` opens close on
    its focus (a portrait print, or a print cut after a page or another print) and pulls back to the
    whole print on a word, then keeps the shared push. `params.opening` chooses; else the shot
    before it does (`job.prev_kind`, `job.prev_print`) and a portrait print opens tight, except a
    printed page, which always opens whole. */
export function archive(job) {
  const a = job.asset || {}, tr = trimOf(job, a), ar = aspect(a, tr), p = job.params || {};
  if (p.treat === "sheet" || (p.treat == null && ar >= 1.75)) return sheet(job, a, tr, ar);
  const T = job.seconds, id = safeId(job.id), [fx, fy] = job.focus || [0.5, 0.45], lab = labelBox(job);
  const { ho, wo, cx, b } = layPrint(ar, T, lab);
  const ih = ho - 2 * b, iw = ih * ar, px0 = cx - wo / 2, py0 = TOP;
  const portrait = ar < 0.92;
  // A printed page (a catalogue's rate table, a guidebook page) is not opened in close: its small
  // print would read sharp, figures the voice never says among it. The plan may still ask for it.
  const page = /\bpage \d+|\bcatalog(ue)?\b/i.test(a.title || "");
  const opening = p.opening === "tight" || p.opening === "whole" ? p.opening
    : !page && (portrait || DESK.has(job.prev_kind) || job.prev_print) ? "tight" : "whole";
  const e = entry(job.id, 0, 1100 / wo);
  // The camera's moves ride on an inner layer about the print's focus; the shared camera keeps its
  // constant push underneath. A state is [seconds, scale, x, y], x/y a shift of the whole print.
  const ox = px0 + b + fx * iw, oy = py0 + b + fy * ih;
  const states = [];
  const tilt = (k) => clamp(4 - 1.1 * k, 1.2, 4);
  if (opening === "tight") {
    // Close enough that the print fills the frame's height or more, never past 1.7 screen pixels to
    // a source pixel; the focus drawn toward the frame's middle, so the close-up is composed.
    const srcW = (a.w || iw) * (1 - tr[1] - tr[3]);
    const s0 = clamp(Math.min(portrait ? 1180 / wo : 1.34, (1.7 * srcW) / iw), 1.18, 1.95);
    const sx = (W * 0.5 - ox) * 0.85, sy = (H * 0.47 - oy) * 0.85;
    const tp = T < 3 ? T * 0.34 : wordAfter(job, Math.max(1.0, T * 0.34), T * 0.62) ?? T * 0.42;
    const pd = clamp(T - tp - 0.7, 0.8, 1.5);
    states.push([0, s0, sx, sy, "linear"], [tp, s0 * 1.012, sx * 1.01, sy * 1.01, SWING], [tp + pd, 1, 0, 0, GLIDE]);
    // a long shot moves in once more, on a word, after the whole print has been seen
    const more = T - (tp + pd) > 3.6 ? wordAfter(job, tp + pd + 1.6, T - 1.6) : null;
    if (more != null) states.push([more, 1.006, 0, 0, SETTLE], [more + 1.3, 1.1, 0, 0, GLIDE]);
    const last = states.at(-1);
    states.push([T, last[1] + 0.012, 0, 0]);
  } else {
    // In on each beat, deeper, then back out to the whole print to resolve before the cut.
    const steps = [1.12, 1.24, 1.04];
    const bs = T > 4.2 ? beats(job) : [];
    states.push([0, 1, 0, 0, GLIDE]);
    let cur = 1.006;
    bs.forEach((t, i) => {
      states.push([t, cur, 0, 0, SETTLE]);
      cur = steps[i] ?? cur;
      states.push([Math.min(T, t + 1.3), cur, 0, 0, GLIDE]);
      cur += 0.006;
    });
    states.push([T, cur + 0.004, 0, 0]);
  }
  const css = timed(states.map(([t, s, x, y, ease], k) =>
    [t, `transform:translate(${px(x)},${px(y)}) rotateX(${f(tilt(k / 2))}deg) scale(${f(s, 4)})`, ease]), T);
  // Where the label slot is covered by the print (in close, or deep in a beat), a soft fall of the
  // desk's dark sits under the label until the print has left it.
  const covers = ([t, s, x, y]) => {
    const k = camScale(t, T), d = camDrift(t, T, 8), at = (u, c, o) => c + ((o + (u - o) * s) - c) * k;
    const r = { x0: at(px0, cx, ox) + x * k + d, x1: at(px0 + wo, cx, ox) + x * k + d, y0: TOP + (oy + (py0 - oy) * s + y - TOP) * k, y1: TOP + (oy + (py0 + ho - oy) * s + y - TOP) * k };
    return hits(r, lab);
  };
  let scrim = "";
  if (lab) {
    const i = states.findIndex(covers);
    if (i >= 0) {
      const j = states.findIndex((s, k) => k > i && !covers(s));
      const on = i === 0 ? -1 : states[i - 1][0] + 0.2, off = j < 0 ? 99 : (states[j - 1][0] + states[j][0]) / 2;
      scrim = labScrim(lab, on, off);
    }
  }
  // a tight opening is already lying on the desk at the cut; a whole one is set down on it
  const land = opening === "tight" ? landVars(e, -3, 0.2) : landVars(e, -0.4, 1.15);
  return `<style>${keyframes(`ph-in-${id}`, css)}</style>` +
    `<div class="cam" style="perspective-origin:${px(cx)} ${px(TOP)}"><div class="rig" style="--cam-origin:${px(cx)} ${px(TOP)};--cam-drift:8px">` +
    `<div class="ph-inner" style="transform-origin:${px(ox)} ${px(oy)};animation:ph-in-${id} ${f(T)}s linear both">` +
    `<div class="ph-place" style="left:${px(px0)};top:${px(py0)};--rot:${deg(e.rot)}">` +
    print(job, a, iw, ih, b, "ph-landing", land) + `</div></div></div></div>` + scrim;
}

/** A sheet of stamps (or any wide sheet of small things): no border of ours, the scan is the
    object. The camera starts in close on the sheet with a rack focus, travels across it at
    reading speed, refocuses on the next subject at a spoken word, and pulls back to the whole
    sheet on the word that names it, landing every ~3.5 s. Depth of field is opacity between a
    sharp face and a soft one, never a filter on something moving. */
function sheet(job, a, tr, ar) {
  const T = job.seconds, id = safeId(job.id), sEnd = camScale(T, T), lab = labelBox(job);
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
    `</div></div></div>` + (lab ? labScrim(lab, -1, back - 0.6) : "");
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
  // as large as a pile can be and still show every print beneath the top one
  const b = 22, ih = n <= 3 ? 700 : 640, trs = list.map((a) => trimOf(job, a));
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
  else if (u.y1 > 1000) shift(0, Math.max(100 - u.y0, 1000 - u.y1));
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
      const sOn = camScale(on, T), s = clamp((0.72 * H) / (p.h * sOn), 1.05, 1.6);
      // Its centre goes a little left of the frame's, so the dimmed pile still shows beside it;
      // the camera's state on the word (its origin and push; the pile has no drift) is allowed for.
      const vw = p.w * s * sOn, vh = p.h * s * sOn, want = [W / 2 - 70, H * 0.455];
      if (lab && want[1] + vh / 2 > lab.y0) want[0] = Math.max(want[0], lab.x1 + 28 + vw / 2);
      const cam = [pcx + (want[0] - pcx) / sOn, pcy + (want[1] - pcy) / sOn];   // the pile's camera has no drift
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
  // the then's date as its record gives it ("c. 1914" stays circa), else its year
  const when = a.date && String(a.date).length <= 12 ? String(a.date) : yearOf(a.date) || "Then";
  // Two prints of one size, as large as the frame takes side by side (x 150…1790, a 64 px gutter),
  // centred on the frame's optical middle. The then lies on the desk inside the shared camera, its
  // push growing it away from the now; the now is upright on the frame, outside the camera, so the
  // footage composited into it stays registered. The captions sit above, outside the camera.
  const b = 24, G = 64, X0 = 150, X1 = 1790;
  let iw = (X1 - X0 - G) / 2 - 2 * b, ih = iw / ar;
  if (ih > 600) { ih = 600; iw = ih * ar; }
  const pw = iw + 2 * b, ph = ih + 2 * b, x0 = (W - (2 * pw + G)) / 2, top = H * 0.47 - ph / 2;
  const nowX = x0 + pw + G, nowY = top, ROT = 1.5;
  const e = entry(job.id);
  const thenRot = -0.8 - Math.abs(e.rot) * 0.5;
  // Before the now arrives the then print lies alone in the frame's middle; as the now drops it is
  // slid aside to make room for it (a frame is never half empty while the voice is still on then).
  const slide = landAt > 0.9 ? W / 2 - (x0 + pw / 2) : 0;
  const s0 = Math.max(0.2, landAt - 0.75), s1 = landAt + 0.05;
  const css = slide ? keyframes(`ph-sl-${id}`, timed([[0, `transform:translateX(${px(slide)})`, "linear"], [s0, `transform:translateX(${px(slide)})`, SETTLE],
    [s1, "transform:translateX(0px)"], [T, "transform:translateX(0px)"]], T)) : "";
  const sl = slide ? `animation:ph-sl-${id} ${f(T)}s linear both;` : "";
  // The then print's exposure eases down on the word that turns to the present, a beat that
  // hands the frame to today.
  const handoff = wordMatch(job, /^(now|today|right)\b/i);
  const dimThen = handoff && handoff > landAt + 1.5 ? `<i class="ph-dimmer ph-dimmer-soft" style="--at:${f(handoff)}s"></i>` : "";
  const poster = right.poster ? `<img src="${esc(right.poster)}" alt="">` : "";
  const capY = Math.max(96, top - 92);
  // the camera's push on the then is held to 1.5%, so the two prints stay one size (VISUAL_SPEC W11)
  return `<style>${css}</style><div class="cam"><div class="rig" style="--cam-origin:${px(x0 + pw)} ${px(top)};--cam-to:scale(1.015) translateX(-10px)">` +
    `<div class="ph-inner" style="${sl}">` +
    `<div class="ph-place" style="left:${px(x0)};top:${px(top)};--rot:${deg(thenRot)}">` +
    print(job, a, iw, ih, b, "ph-landing", landVars({ lx: -140, ly: 60, lr: -4 }, -0.4, 1.1), dimThen) + `</div></div></div></div>` +
    `<div class="ph-inner" style="${sl}"><div class="ph-cap" style="left:${px(x0 + b)};top:${px(capY)};--at:-0.4s"><p>${esc(when)}</p></div></div>` +
    `<div class="ph-cap" style="left:${px(nowX + b)};top:${px(capY)};--at:${f(landAt - 0.1)}s"><p>Today</p></div>` +
    `<div class="ph-now" style="left:${px(nowX)};top:${px(nowY)};width:${px(pw)};height:${px(ph)};--rot:${deg(ROT)};--at:${f(landAt - 0.5)}s">` +
    `<div class="ph-now-face" style="left:${px(b)};top:${px(b)};width:${px(iw)};height:${px(ih)}">${poster}</div><i class="ph-sheen"></i></div>` +
    // The compositing contract (render_shots.py): the footage's unrotated box, its start, its
    // rotation about the box's centre (clockwise, degrees) and its grade.
    `<div class="split-right" data-at="${f(landAt)}" data-rot="${ROT}" data-grade="${esc(NOW_GRADE)}" ` +
    `style="left:${px(nowX + b)};top:${px(nowY + b)};width:${px(iw)};height:${px(ih)}"></div>`;
}
