// v3 type: figures and words as light on the dark desk (docs/content/FILM_LOOK_V3.md, "Data is
// light"; round 2, the critique of 2026-10-06). Each kind takes a resolved job and returns the
// shot's inner HTML; ../shots.mjs wraps it in the key light, grade, vignette and the label slot.
//
// The system: time is set in Fraunces, quantities and money in Inter 500 (the hero tokens), and
// a figure's words ("cents", "about", "a ton") small beside it in Fraunces italic, ivory 70%,
// never blue. Only the figure the line lands on is blue. One motif ties the kinds together: 2 px
// hairlines that draw themselves, a bright point at the drawing end. Nothing counts: a figure
// lands on its spoken word (blur, scale, tracking), and every spoken word lands on its onset from
// `job.words`, never early. Data is drawn only where it encodes something: real dates on a line,
// comparable amounts as bars to scale, a share as one 100% bar, a price step as columns, anything
// else as a typeset ledger. Every figure and word on screen is the job's own.
//
// The stage runs no layout script, so layout is decided here, at build time, from the faces'
// measured advances (Chrome, 2026-10-06), inside a box the shared camera's push never carries
// out of title-safe (see stage()).
import { esc } from "../shots.mjs";

/* ---------- measure ---------- */

const CHARS = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~’‘“”—–→×÷·…¢";
const ADV = Object.fromEntries(Object.entries({
  // Measured in Chrome at the settings the CSS uses (thousandths of an em): Inter 440 with tnum
  // (figures), Inter 500 (labels), Fraunces roman 360 / italic 350 at opsz 120 (display), and
  // roman / italic 370 at opsz 64 (text); SOFT 20, WONK 0.
  inter440: "269,223,413,603,619,856,614,256,391,391,645,645,269,645,269,331,645,645,645,645,645,645,645,645,645,645,269,269,645,645,645,530,978,671,639,723,691,583,558,731,709,236,538,641,538,862,712,749,614,749,635,619,614,703,683,970,652,649,616,391,283,391,441,457,249,522,570,527,570,540,283,570,552,211,211,513,211,845,552,553,570,570,330,480,284,552,518,761,511,518,484,391,303,391,645,195,195,352,351,1000,500,924,645,645,223,669,527",
  inter500: "238,229,426,608,627,875,621,260,310,310,491,637,228,434,228,338,625,372,574,605,631,584,595,546,593,595,228,230,637,637,637,539,985,684,640,724,693,589,563,732,711,241,544,651,542,870,715,749,618,749,638,627,619,704,693,980,663,658,620,310,284,310,446,461,259,529,576,534,576,544,291,576,560,219,219,521,219,854,560,560,576,576,342,490,294,560,526,774,517,526,493,403,313,403,637,203,203,370,368,1000,500,926,637,637,228,684,534",
  frD: "169,208,239,545,504,597,695,122,300,298,576,459,168,243,166,341,582,350,520,482,526,502,537,449,512,539,155,163,434,459,433,456,748,599,602,625,691,567,515,678,722,303,356,658,529,786,674,724,582,728,621,540,588,653,592,888,623,592,553,279,330,279,312,332,197,428,479,401,485,414,256,459,492,218,217,473,246,766,492,480,497,477,352,371,274,490,431,659,432,440,385,320,226,320,487,140,148,275,275,698,445,1000,406,459,211,548,400",
  friD: "159,263,232,543,472,579,695,120,314,313,535,465,170,269,170,388,610,378,518,485,522,492,545,427,500,542,232,235,437,465,437,375,728,556,563,591,656,561,514,640,691,325,311,624,485,758,607,680,556,682,597,504,536,605,529,844,572,517,541,325,368,326,319,359,149,446,436,366,445,373,242,413,460,237,208,454,227,690,466,425,431,422,356,335,253,450,388,614,453,401,392,330,229,328,493,134,144,285,272,698,448,1000,419,465,209,628,405",
  frT: "205,271,293,610,558,682,721,141,326,325,606,522,217,354,210,435,620,409,563,514,564,538,568,482,550,571,210,220,484,521,484,475,830,668,645,669,746,616,564,727,785,348,421,716,581,854,741,768,629,770,674,569,640,710,660,976,686,649,605,306,431,308,422,422,213,497,547,466,558,480,321,519,571,268,268,547,290,870,571,543,563,547,411,429,327,561,506,753,492,510,440,362,246,362,584,180,184,354,367,771,487,1000,465,521,248,728,465",
  friT: "187,293,299,608,539,672,696,147,344,342,590,521,214,349,209,425,631,414,560,513,566,530,572,486,538,571,263,270,485,524,485,440,822,615,613,625,712,601,559,680,750,355,343,676,528,811,672,735,602,736,651,538,586,669,587,913,619,565,579,352,408,353,413,422,196,508,494,417,516,442,290,478,528,283,268,514,279,787,543,487,502,492,426,388,320,526,454,696,534,471,453,372,279,371,578,172,182,363,353,769,488,1000,471,521,245,715,461",
}).map(([k, v]) => [k, v.split(",").map(Number)]));
const IX = new Map([...CHARS].map((c, i) => [c, i]));
const adv = (face, s) => [...String(s)].reduce((w, c) => w + ADV[face][IX.get(c) ?? IX.get("n")], 0) / 1000;
/** Fraunces narrows as its optical size grows (here always the pixel size): blend the measured cuts. */
const serifEm = (s, opsz, italic = false) => {
  const k = Math.min(1, Math.max(0, (opsz - 64) / 56)), small = 1 + Math.max(0, 64 - opsz) * 0.002;
  return 1.025 * small * ((1 - k) * adv(italic ? "friT" : "frT", s) + k * adv(italic ? "friD" : "frD", s));
};
const serifW = (s, px, italic = false) => serifEm(s, Math.min(144, px), italic) * px;
const figW = (s, px, ls) => (adv("inter440", s) + ls * [...s].length) * px;
const labelW = (s, px, ls = 0.1) => (adv("inter500", s) + ls * [...s].length) * px;

/* ---------- small helpers ---------- */

const r3 = (x) => Math.round(x * 1000) / 1000;
const px0 = (x) => `${Math.round(x)}px`;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const words = (s) => String(s ?? "").trim().split(/\s+/).filter(Boolean);
const LABEL = 28, BODY = 40, HEADING = 64, DISPLAY = [120, 96, 72];
/** Typography hygiene (R3): curly apostrophes and quotes, an en dash between figures. */
const typo = (s) => String(s ?? "")
  .replace(/(\w)'(\w)/g, "$1’$2").replace(/(\w)'(?=\s|$|[.,;:!?])/g, "$1’").replace(/'(\w)/g, "‘$1")
  .replace(/"(?=\S)/g, "“").replace(/"/g, "”").replace(/(\d)\s*-\s*(\d)/g, "$1–$2");
const T = (s) => esc(typo(s));

/* ---------- figures ---------- */

const NUM = /\$?\d+(?:,\d{3})*(?:\.\d+)?%?/g;
const MONTH = /\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b/;
const isMoney = (s) => /\$|¢|\bcents?\b/.test(String(s ?? ""));
const isYear = (n) => /^\d{4}$/.test(n) && +n >= 1500 && +n <= 2100;
/** A figure's text as number tokens and the word runs between them. */
function tokens(s) {
  const str = String(s ?? ""), out = [];
  let i = 0;
  for (const m of str.matchAll(NUM)) {
    if (m.index > i) out.push({ w: str.slice(i, m.index) });
    out.push({ n: m[0] });
    i = m.index + m[0].length;
  }
  if (i < str.length) out.push({ w: str.slice(i) });
  return out;
}
/** Time (a year, a date) is set in Fraunces. */
const timeish = (s) => { const n = tokens(s).filter((t) => t.n); return MONTH.test(s) || (n.length > 0 && n.every((t) => isYear(t.n))); };
/** A figure-led string: a number first, or a qualifier and then a number ("about 5,000"). */
const figureLed = (s) => !timeish(s) && /^(?:(?:about|over|under|more than|nearly|almost|roughly|some|plus)\s+)?\$?\d/i.test(String(s ?? "").trim());
const kindOf = (s) => (timeish(s) ? "time" : isMoney(s) ? "money" : /%/.test(s) ? "pct" : "qty");
/** A figure's value in one unit (cents become dollars), or NaN. */
function amount(s) {
  const n = tokens(s).find((t) => t.n && !isYear(t.n));
  if (!n) return NaN;
  let v = +n.n.replace(/[$,%]/g, "");
  if (/\bcents?\b/.test(s) && !n.n.startsWith("$")) v /= 100;
  if (/\bmillion\b/.test(s)) v *= 1e6;
  return v;
}
/** The words after a figure's last number ("a ton", "cents"), lower-cased, for comparing units. */
const unitOf = (s) => String(s ?? "").replace(/^.*\d%?/, "").trim().toLowerCase();

/* ---------- when each word is spoken (S5) ---------- */

const STOP = new Set("a an the to of in on and or by it is at for as that this with from be was its".split(" "));
const norm = (w) => {
  let s = String(w ?? "").toLowerCase().replace(/[’‘]/g, "'").replace(/^[^a-z0-9$]+|[^a-z0-9%]+$/g, "").replace(/'s$/, "");
  if (/^[a-z]{4,}s$/.test(s)) s = s.slice(0, -1);
  return s;
};
const weight = (s) => (/\d/.test(s) ? 4 : STOP.has(s) ? 1 : 2);
/** Monotone alignment of tokens to the spoken words (a weighted longest common subsequence): onsets or null. */
function align(toks, spoken) {
  const a = toks.map(norm), b = spoken.map((x) => norm(x.w)), n = a.length, m = b.length;
  const L = Array.from({ length: n + 1 }, () => new Float32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = Math.max(a[i] && a[i] === b[j] ? L[i + 1][j + 1] + weight(a[i]) : 0, L[i + 1][j], L[i][j + 1]);
  const out = Array(n).fill(null);
  for (let i = 0, j = 0; i < n && j < m;) {
    if (a[i] && a[i] === b[j] && L[i][j] === L[i + 1][j + 1] + weight(a[i])) { out[i] = spoken[j].t; i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  return out;
}
/** Each token's onset: spoken ones on their word; the rest follow the token before, never after the next spoken one. */
function onsets(toks, spoken, t0 = 0, gap = 0.1) {
  const raw = align(toks, spoken || []), out = [];
  for (let i = 0; i < raw.length; i++) {
    const nextI = raw.findIndex((t, j) => j > i && t != null), next = nextI < 0 ? null : raw[nextI];
    let v = raw[i] ?? (i ? out[i - 1] + gap : t0);
    if (raw[i] == null && next != null) v = i && out[i - 1] != null && out[i - 1] < next - 0.04 ? Math.min(v, next - 0.04) : next - 0.04 * (nextI - i);
    if (i && v < out[i - 1]) v = out[i - 1] + 0.02;
    out.push(v);
  }
  return out;
}
/** When a figure is spoken: its number word nearest the plan's time (or the plan's time). */
function spokenAt(text, spoken, near) {
  const n = tokens(text).find((t) => t.n);
  if (n && spoken?.length) {
    const hits = spoken.filter((x) => norm(x.w) === norm(n.n));
    if (hits.length) return hits.reduce((b, x) => (Math.abs(x.t - (near ?? x.t)) < Math.abs(b.t - (near ?? b.t)) ? x : b)).t;
  }
  return near ?? 0.4;
}
/**
 * Where a short phrase is said: of every place the narration says one of its words, the window that
 * matches it best, discounted by its distance from the plan's time. Each word's onset, or null.
 */
function phraseTimes(text, spoken, near, lam = 0.8) {
  const toks = words(text), keys = toks.map(norm), n = toks.length;
  let best = null;
  (spoken || []).forEach((x, j) => {
    const k = norm(x.w);
    if (!k || STOP.has(k) || !keys.includes(k)) return;
    const raw = align(toks, spoken.slice(Math.max(0, j - n - 1), j + n + 2));
    // said means every number in it is said, and at least a third of its weight
    const got = raw.reduce((a, t, i) => a + (t == null ? 0 : weight(keys[i])), 0), all = keys.reduce((a, k) => a + (k ? weight(k) : 0), 0);
    if (keys.some((k, i) => /\d/.test(k) && raw[i] == null) || got < 0.35 * all) return;
    const score = raw.reduce((a, t, i) => a + (t == null ? 0 : weight(keys[i])), 0) - (near == null ? 0 : lam * Math.max(0, Math.abs(x.t - near) - 0.5));
    if (!best || score > best.score) best = { score, raw };
  });
  if (!best || best.score <= 0) return null;
  const out = [];
  out.raw = best.raw;
  for (let i = 0; i < n; i++) {
    const nextI = best.raw.findIndex((t, j) => j >= i && t != null);
    let v = best.raw[i] ?? (nextI > i && (i === 0 || out[i - 1] == null || out[i - 1] >= best.raw[nextI] - 0.04) ? best.raw[nextI] - 0.04 * (nextI - i) : out[i - 1] + 0.08);
    if (i && v < out[i - 1]) v = out[i - 1] + 0.02;
    out.push(v);
  }
  return out;
}
/** A phrase's onsets: where it is said, else from `t0` with a gentle stagger. */
const sayTimes = (text, spoken, near, t0) => phraseTimes(text, spoken, near) ?? words(text).map((_, i) => (t0 ?? near ?? 0) + i * 0.07);
/** When a phrase starts being said near the plan's time (or `near` when it is not said). */
const phraseAt = (text, spoken, near) => phraseTimes(text, spoken, near)?.[0] ?? near;
const saidAt = (text, spoken, near) => phraseTimes(text, spoken, near)?.[0] ?? null;
/** A phrase said from `t0` on: its words on their onsets and never before `t0` (from `t0`, staggered, when it is not said). */
const sayFrom = (text, spoken, t0) => (phraseTimes(text, (spoken || []).filter((x) => x.t >= t0 - 0.05), t0, 0.12) ?? words(text).map((_, i) => t0 + i * 0.07)).map((t) => Math.max(t, t0));
/** When a phrase is first said at or after `t0` (null when it is not). */
const saidAfter = (text, spoken, t0) => phraseTimes(text, (spoken || []).filter((x) => x.t >= t0 - 0.05), t0, 0.12)?.[0] ?? null;
/** A heading is set at the cut (a title, not narration); only a figure in it waits for its word. */
const headWords = (text, spoken) => words(text).map((w) => (/\d/.test(w) ? (spoken || []).find((x) => norm(x.w) === norm(w))?.t ?? 0 : 0));
/** A heading's words: those the narration says on their onsets, the rest there from `t0` (a heading is set before it is read). */
function headTimes(text, spoken, t0 = 0) {
  const ts = phraseTimes(text, (spoken || []).filter((x) => x.t >= t0 - 0.05), t0 + 1);
  if (!ts) return words(text).map((_, i) => t0 + i * 0.04);
  const first = ts.raw.findIndex((t) => t != null);
  return ts.map((t, i) => (i < first ? t0 + i * 0.04 : Math.max(t, t0)));
}
/** Each number in a figure on its own word: the first at `t0`, a range's second when it is said. */
function figTimes(text, spoken, t0) {
  const nums = tokens(text).filter((t) => t.n);
  return nums.map((t, i) => (i ? Math.max(t0 + 0.2, spokenAt(t.n, (spoken || []).filter((x) => x.t > t0), t0 + 0.6)) : t0));
}

/* ---------- the stage box and the camera ---------- */

/**
 * The box a shot lays out in, and the camera origin that keeps it in title-safe. The shared camera
 * (base.css) pushes 1% of scale a second, capped at 6%, with no sideways drift. Anchored on the
 * left grid line (x = 160) and the box's middle, a box of 1600/s × 760/s at x = 160 ends the shot
 * exactly filling title-safe (y 90–850, above the label slot). `open` kinds (no label) use 90–990.
 * `push` is a kind's own extra push on top (the hook's), counted in the same box.
 */
function stage(job, open = false, push = 1) {
  const dur = job.seconds || 6, s = (1 + Math.min(0.01 * dur, 0.06)) * push, cy = open ? 540 : 470;
  // a line's box runs above its capitals (the font's ascent): keep 30 px of the safe band for it
  const w = Math.floor(1600 / s), h = Math.floor(((open ? 900 : 760) - 60) / s);
  return { dur, s, w, h, top: Math.round(cy - h / 2), ox: 160, oy: cy };
}
function cam(B, inner, extra = "") {
  return `<div class="cam" style="--cam-origin:${B.ox}px ${B.oy}px"><div class="rig"><div class="ty" style="--bx-top:${B.top}px;--bx-w:${B.w}px;--bx-h:${B.h}px">` +
    `${extra ? `<div class="ty-push" style="${extra}">${inner}</div>` : inner}</div></div></div>`;
}

/* ---------- motion ---------- */

/** A figure lands (S3): at or before 0.4 s it cuts in mid-landing (R1); `rack` waits under depth blur. */
function landAt(t, mode = "") {
  if (t <= 0.4) return { cls: "ty-land cut", style: "--at:0;--d:0.27s" };
  return { cls: `ty-land${mode ? ` ${mode}` : ""}`, style: `--at:${r3(t - 0.15)};--d:0.35s` };
}
/** Words that land one by one on their onsets (blur 8 → 0, 6 px → 0, 0.25 s); `pre` keeps them in depth until then. */
function wordSpans(text, times, pre = false) {
  return words(text).map((w, i) => {
    const t = times[i] ?? times[times.length - 1] ?? 0;
    const cut = t <= 0.4;
    return `<span class="ty-w${cut ? " cut" : pre ? " pre" : ""}" style="--at:${r3(cut ? -0.12 : t)}">${T(w)}</span>`;
  }).join(" ");
}
/** A line of words timed from the narration, or from `t0` with a gentle stagger when not spoken. */
const speak = (text, spoken, t0, near) => wordSpans(text, sayTimes(text, spoken, near ?? t0, t0));
/** Elements that enter at a time: the shared rise, but an element due by 0.4 s is already arriving at frame 0. */
const enter = (t) => `--at:${r3(t <= 0.4 ? -0.4 : t)}`;

/**
 * Beats (S4: something new at least every 3.5 s). After the last landing, the frame re-reads what
 * it already shows, on spoken words: `targets` is how many things can take a beat; returns
 * [{ t, k }] for k in 0..targets-1.
 */
function beats(landings, spoken, dur, targets) {
  const out = [];
  if (!targets) return out;
  const ts = [...landings].filter((t) => t != null).sort((a, b) => a - b);
  let last = ts.length ? ts[ts.length - 1] : 0, k = 0;
  const onWord = (t) => { const w = (spoken || []).filter((x) => Math.abs(x.t - t) < 0.7).sort((a, b) => Math.abs(a.t - t) - Math.abs(b.t - t))[0]; return w ? w.t : t; };
  for (let i = 0; i < ts.length; i++) {           // gaps between landings
    let a = i ? ts[i - 1] : 0;
    while (ts[i] - a > 3.5) { a = onWord(a + 3.1); if (a < ts[i] - 0.6) out.push({ t: a, k: k++ % targets }); else break; }
  }
  while (dur - last > 3.5) { last = onWord(last + 3.1); if (last < dur - 0.8) out.push({ t: last, k: k++ % targets }); else break; }
  return out;
}

/* ---------- a figure, set ---------- */

/**
 * One figure line: numbers in Inter 500 (Fraunces when the figure is time), its words beside it in
 * Fraunces italic at 0.3 of the size (never under 28 px), ivory 70%. `blue` marks the figure the
 * line lands on; `times` lands each number on its own word (a range's second figure later).
 */
function figLine(text, px, o = {}) {
  const { times = [0.4], blue = false, quiet = false, time = timeish(text), mode = "", ls = px >= 200 ? -0.04 : -0.02, unitMin = LABEL } = o;
  const toks = tokens(text);
  const up = Math.max(0.3 * px, unitMin), nums = toks.filter((t) => t.n);
  let w = 0, html = "", k = 0;
  toks.forEach((t) => {
    if (t.n) {
      const at = times[Math.min(k, times.length - 1)];
      const { cls, style } = landAt(at, k === 0 ? mode : "");
      w += time ? serifW(t.n, px) - 0.02 * px * t.n.length : figW(t.n, px, ls);
      html += `<span class="${time ? "ty-fd" : "ty-fn"} ${cls}${blue && !time ? " money" : quiet ? " quiet" : ""}" style="${style};--ls:${ls}em">${esc(t.n)}</span>`;
      k++;
      return;
    }
    const raw = t.w, txt = raw.trim();
    if (!txt) { w += 0.25 * px; html += `<span class="ty-sp"></span>`; return; }
    const sl = /^\s/.test(raw), sr = /\s$/.test(raw);
    const at = times[Math.min(Math.max(0, k - (k && k === nums.length ? 1 : 0)), times.length - 1)];
    w += serifW(txt, up, true) + ((sl ? 0.28 : 0) + (sr ? 0.28 : 0)) * up;
    html += `<span class="ty-u${sl ? " sl" : ""}${sr ? " sr" : ""}" style="font-size:${px0(up)}"><span class="ty-w${at <= 0.4 ? " cut" : ""}" style="--at:${r3(at <= 0.4 ? -0.12 : at + 0.05)}">${T(txt)}</span></span>`;
  });
  return { html, w };
}
/** Fit a figure line in `maxw`: the largest size from `max` down to `min`. */
function fitFig(text, maxw, max, min, o = {}) {
  let px = max, f = figLine(text, px, o);
  while (f.w > maxw && px > min) { px -= 4; f = figLine(text, px, o); }
  return { px, ...f };
}
/** The pool of light a landing figure throws on the desk (blue for the money the line lands on). */
const bloom = (w, h, t, blue) => `<i class="ty-bloom${blue ? " blue" : ""}" style="width:${px0(w)};height:${px0(h)};--at:${r3(Math.max(0, t))}"></i>`;
/** A re-read beat on a figure: its glow swells and settles (no fill, so beats stack). */
const pulses = (bs, k, cls = "pulse") => bs.filter((b) => b.k === k).map((b) => `<i class="ty-${cls}" style="--at:${r3(b.t)}"></i>`).join("");

/* ---------- number ---------- */

export function number(job) {
  const B = stage(job), p = job.params || {}, value = String(p.value ?? job.reveals?.[0]?.value ?? "");
  const spoken = job.words || [];
  const on = job.on ?? job.reveals?.[0]?.t ?? 0.4;
  const time = timeish(value), money = isMoney(value);
  let toks = tokens(value), tail = "";
  const last = toks[toks.length - 1];
  if (toks.length > 1 && last.w && words(last.w).length > 3) { tail = last.w.trim(); toks = toks.slice(0, -1); }
  const fig = toks.map((t) => t.n ?? t.w).join("");
  // a range's second figure lands on its own word
  const nums = toks.filter((t) => t.n);
  const times = nums.map((t, i) => (i === 0 ? on : spokenAt(t.n, spoken.filter((x) => x.t > on), on + 0.6)));
  const mode = on > 0.4 && on <= 1.0 ? "rack" : "";
  let f = fitFig(fig, B.w - 20, 320, 220, { times, blue: money, time, mode });
  if (f.w > B.w - 20 && toks.length > 1 && toks[toks.length - 1].w) {
    tail = `${toks[toks.length - 1].w.trim()}${tail ? ` ${tail}` : ""}`;
    f = fitFig(toks.slice(0, -1).map((t) => t.n ?? t.w).join(""), B.w - 20, 320, 160, { times, blue: money, time, mode });
  }
  const html = f.html;
  const fw = Math.min(B.w, f.w);
  // the context line comes first when the figure is spoken late, else it follows on its words
  const subFirst = on > 1.0;
  const sub = p.sub ? `<p class="ty-n-sub">${subFirst ? wordSpans(p.sub, words(p.sub).map(() => 0)) : speak(p.sub, spoken.filter((x) => x.t > on + 0.3), on + 0.55)}</p>` : "";
  const tailT = tail ? phraseAt(tail, spoken, on + 0.5) ?? on + 0.4 : 0;
  const bs = beats([on, ...times, tail ? tailT : null], spoken, B.dur, 1);
  const est = p.estimate ? `<p class="ty-est" style="${enter(on + 0.8)}">Estimate</p>` : "";
  return cam(B, `<div class="ty-box ty-n">` +
    `<div class="ty-n-fig${time ? " time" : ""}" style="font-size:${px0(f.px)}">${bloom(fw * 1.4, f.px * 1.9, on, money)}${html}${pulses(bs, 0, money ? "pulse-blue" : "pulse")}</div>` +
    `<div class="ty-rule" style="--fw:${px0(fw)};margin-top:${px0(f.px * 0.1 + 20)};${enter(on + 0.1)}"><i></i>${bs.map((b) => `<b style="--at:${r3(b.t)}"></b>`).join("")}</div>` +
    est + (tail ? `<p class="ty-n-tail">${speak(tail, spoken.filter((x) => x.t >= on), tailT)}</p>` : "") + sub + `</div>`);
}

/* ---------- pair ---------- */

export function pair(job) {
  const B = stage(job, false, job.params?.push_at != null ? 1.05 : 1), p = job.params || {}, L = p.left || {}, R = p.right || {}, spoken = job.words || [];
  const lAt = L.at ?? 0.3, rAt = Math.max(R.at ?? lAt + 1.2, lAt + 0.4);
  const kl = kindOf(L.value), kr = kindOf(R.value);
  // a price and the moment it is from are not a comparison: stacked, the money the hero
  if (p.layout === "stacked" || ((kl === "money") !== (kr === "money") && (kl === "time" || kr === "time"))) return hook(job, B);
  const same = kl === kr && kl !== "time";
  const blueR = kr === "money", blueL = kl === "money" && !blueR;
  const unitsOf = (v) => { const t = tokens(v), z = t[t.length - 1]; return z?.w && /^\s/.test(z.w) && t.length > 1 ? z.w.trim() : ""; };
  const strip = (v, u) => (u ? String(v).slice(0, String(v).lastIndexOf(u)).trimEnd() : String(v));
  // both figures as large as the box allows, with at least 240 px of line between them; long
  // trailing words set below their figure when inline they would shrink the pair
  const fit = (below) => {
    const lu = below ? unitsOf(L.value) : "", ru = below ? unitsOf(R.value) : "";
    let px = 260, lf, rf;
    for (;; px -= 4) {
      lf = figLine(strip(L.value, lu), px, { times: figTimes(strip(L.value, lu), spoken, lAt), blue: blueL, quiet: kl === "money" && !blueL });
      rf = figLine(strip(R.value, ru), px, { times: figTimes(strip(R.value, ru), spoken, rAt), blue: blueR });
      if (lf.w + rf.w + 240 <= B.w || px <= 120) break;
    }
    return { px, lf, rf, lu, ru };
  };
  let F = fit(false);
  if (F.px < 190) { const G = fit(true); if ((G.lu || G.ru) && G.px > F.px + 24) F = G; }
  const { px, lf, rf } = F;
  const linkW = B.w - lf.w - rf.w, d = 0.7, drawFrom = Math.max(lAt + 0.4, rAt - d - 0.05);
  const gapT = p.gap ? p.gap_at ?? saidAt(p.gap, spoken, rAt + 1.2) ?? rAt + 0.7 : 0;
  const gapIn = p.gap && serifW(p.gap, BODY, true) <= linkW - 90;
  // a label lands on its own words (the plan's `label_at`), else with its figure, else at the cut
  const labT = (c, t) => c.label_at ?? saidAt(c.label, spoken, t) ?? Math.max(0, Math.min(t - 0.3, 0.2));
  const bs = beats([lAt, rAt, p.gap ? gapT : null, L.label_at, R.label_at], spoken, B.dur, 1);
  const col = (c, t, f, unit, side, blue) => `<div class="ty-p-col ${side}" style="--next:${r3(rAt)}">` +
    `<p class="ty-label">${wordSpans(c.label, sayFrom(c.label, spoken, labT(c, t)))}</p>` +
    `<div class="ty-p-fig" style="font-size:${px0(px)}">${bloom(f.w * 1.4, px * 1.8, t, blue)}${f.html}` +
    `${unit ? `<span class="ty-p-unit" style="font-size:${px0(Math.max(LABEL, px * 0.3))}">${wordSpans(unit, sayFrom(unit, spoken, t + 0.1))}</span>` : ""}` +
    `${side === "r" ? pulses(bs, 0, blue ? "pulse-blue" : "pulse") : ""}</div></div>`;
  const link = `<div class="ty-p-link${same ? " arrow" : ""}" style="--lift:${px0(px * 0.42)};--at:${r3(drawFrom)};--d:${r3(rAt - drawFrom)}s">` +
    `<i class="ty-p-line"></i><i class="ty-p-head"></i>${same ? "<b></b>" : "<u></u>"}${bs.map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}` +
    `${gapIn ? `<p class="ty-p-gap in">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : ""}</div>`;
  const q = p.question ? `<p class="ty-head">${wordSpans(p.question, p.question_at ? headTimes(p.question, spoken, p.question_at[0] ?? 0) : headWords(p.question, spoken))}</p>` : "";
  const g = p.gap && !gapIn ? `<p class="ty-p-gap">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : "";
  // `push_at`: from that word the camera leans in toward the figure the line lands on
  const push = p.push_at != null ? `--push-to:1.05;--push-at:${r3(p.push_at)};--push-d:${r3(Math.max(1, B.dur - p.push_at))}s;--push-origin:160px ${B.oy}px` : "";
  return cam(B, `<div class="ty-box ty-p">${q}<div class="ty-p-row${F.lu || F.ru ? " units" : ""}">` +
    `${col(L, lAt, lf, F.lu, "l", blueL)}${link}${col(R, rAt, rf, F.ru, "r", blueR)}</div>${g}</div>`, push);
}

/** The hook (a01): the money lands at frame 0 as the hero; the moment it is from under it, small; then the gap's words. */
function hook(job, B) {
  const p = job.params || {}, spoken = job.words || [], L = p.left || {}, R = p.right || {};
  const [M, W] = isMoney(L.value) ? [L, R] : isMoney(R.value) ? [R, L] : [L, R];
  const mAt = M.at ?? 0.3, wAt = W.at ?? mAt + 1;
  // the hero as large as the box allows with its two lines under it (the shared push is the camera)
  const px = clamp(Math.floor((B.h - (p.gap ? 150 : 40)) / (0.82 + 0.4 * 1.3 + 0.17)), 220, 360);
  const f = figLine(M.value, px, { times: figTimes(M.value, spoken, mAt), blue: isMoney(M.value), ls: -0.04 });
  const wt = sayFrom(W.value, spoken, wAt);
  const gapT = p.gap ? p.gap_at ?? saidAt(p.gap, spoken, wAt + 1) ?? wAt + 1 : 0;
  const bs = beats([mAt, ...wt, ...(p.gap ? sayFrom(p.gap, spoken, gapT) : [])], spoken, B.dur, 1);
  return cam(B, `<div class="ty-box ty-hook"><div class="ty-p-fig hero" style="font-size:${px}px">${bloom(f.w * 1.3, px * 1.6, mAt, isMoney(M.value))}${f.html}${pulses(bs, 0, "pulse-blue")}</div>` +
    `<p class="ty-hook-when" style="font-size:${px0(px * 0.4)}">${words(W.value).map((w, i) => `<span class="${timeish(w) ? "ty-fd" : "ty-hw"} ty-w" style="--at:${r3(wt[i])}">${T(w)}</span>`).join(" ")}</p>` +
    `${p.gap ? `<p class="ty-hook-gap">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : ""}</div>`);
}

/* ---------- grid ---------- */

export function grid(job) {
  const B = stage(job), p = job.params || {}, on = job.on ?? 0.5, spoken = job.words || [];
  const int = (s) => Number(String(s ?? "").replace(/[^\d.]/g, "")) || 0;
  let total = int(p.total), filled = Math.min(int(p.filled), int(p.total) || int(p.filled)), per = 1;
  if (total > 2000) { per = 10; total = Math.ceil(total / 10); filled = Math.round(filled / 10); }
  const leftW = 560, boxW = Math.min(820, B.w - leftW - 60), boxH = Math.min(560, B.h - 200);
  let best = null;
  for (let c = 1; c <= Math.max(1, total); c++) {
    const r = Math.ceil(total / c), pitch = Math.min(boxW / c, boxH / r, 132);
    const score = pitch - (r * c - total) * 3;
    if (!best || score > best.score) best = { c, pitch, score };
  }
  const { c: cols, pitch } = best, dot = Math.round(Math.min(pitch * 0.42, 46));
  const fill = clamp(0.6 + total * 0.012, 0.9, 1.8);
  // the rings are there from the first frame; each lights in order once the count is spoken
  const dots = Array.from({ length: total }, (_, i) => `<i class="${i < filled ? "on" : ""}" style="--ring:${r3(-0.4 + 0.5 * (i / Math.max(total, 1)))}` +
    `${i < filled ? `;--at:${r3(on + fill * Math.pow(i / Math.max(filled - 1, 1), 1.4))}` : ""}"></i>`).join("");
  const money = isMoney(p.filled);
  const ft = String(p.filled ?? "").trim();
  const f = figLine(ft, 300, { times: [on], blue: money });
  const of = p.total && int(p.total) !== int(p.filled) ? `<span class="ty-u sl" style="font-size:90px">${wordSpans(`of ${p.total}`, [on + fill, on + fill])}</span>` : "";
  const caption = per > 1 ? `${p.caption || ""} One dot is ten.`.trim() : p.caption;
  const capT = on + fill + 0.3;
  const bs = beats([on, on + fill, caption ? capT : null], spoken, B.dur, 1);
  const left = `<div class="ty-g-count" style="width:${leftW}px"><div class="ty-g-fig" style="font-size:300px">${bloom(f.w * 1.5, 520, on, money)}${f.html}${of}${pulses(bs, 0, money ? "pulse-blue" : "pulse")}</div>` +
    `${caption ? `<p class="ty-g-cap">${speak(caption, spoken, capT, capT)}</p>` : ""}</div>`;
  const right = `<div class="ty-g-dots${money ? " money" : ""}" style="grid-template-columns:repeat(${cols}, ${px0(pitch)});--dot:${px0(dot)};--pitch:${px0(pitch)}">${dots}</div>`;
  const head = p.heading ? `<p class="ty-head">${wordSpans(p.heading, headWords(p.heading, spoken))}</p>` : "";
  return cam(B, `<div class="ty-box ty-g">${head}<div class="ty-g-row">${left}${right}</div></div>`);
}

/* ---------- kinetic ---------- */

/** Split `text` into at most two balanced lines that fit `maxw`, or null. `w` measures a string. */
function breakLine(text, w, maxw) {
  const ws = words(text);
  if (w(text) <= maxw) return [text];
  let best = null;
  for (let k = 1; k < ws.length; k++) {
    const a = ws.slice(0, k).join(" "), b = ws.slice(k).join(" "), m = Math.max(w(a), w(b));
    if (m <= maxw && (!best || m < best.m)) best = { m, lines: [a, b] };
  }
  return best ? best.lines : null;
}

export function kinetic(job) {
  const B = stage(job, true), p = job.params || {}, spoken = job.words || [];
  const lines = (p.lines?.length ? p.lines : [job.says]).map((l) => String(l ?? "").trim()).filter(Boolean);
  const italic = (i) => i > 0 && /[.!?:]$/.test(lines[i - 1]);
  // every word on its spoken onset (a line the narration does not say lands on the plan's time)
  const all = lines.flatMap((l) => words(l));
  const raw = align(all, spoken);
  let k = 0;
  const times = lines.map((l, i) => {
    const ws = words(l), own = raw.slice(k, k + ws.length);
    const said = own.filter((t) => t != null).length >= Math.ceil(ws.length / 2);
    const t0 = p.at?.[i] ?? i * 0.9;
    const res = said ? onsets(ws, spoken.filter((x) => x.t >= (own.find((t) => t != null) ?? 0) - 0.01), own.find((t) => t != null), 0.08) : ws.map((_, j) => t0 + j * 0.08);
    k += ws.length;
    return res;
  });
  for (let i = 1; i < times.length; i++) if (times[i][0] < times[i - 1][times[i - 1].length - 1]) times[i] = times[i].map((t) => Math.max(t, times[i - 1][times[i - 1].length - 1] + 0.1));
  const n = all.length, maxw = B.w - 10;
  let best = null;
  for (const px of DISPLAY.filter((x) => x <= (n <= 8 ? 120 : n <= 25 ? 96 : 72))) {
    const set = lines.map((l, i) => breakLine(l, (s) => serifW(s, px, italic(i)), maxw));
    if (set.some((s) => !s)) continue;
    const vl = set.reduce((a, s) => a + s.length, 0);
    if (vl * px * 1.08 + (lines.length - 1) * px * 0.3 <= B.h) { best = { px, set }; break; }
  }
  if (!best) best = { px: 72, set: lines.map((l) => [l]) };
  const { px, set } = best;
  // frame 1 is never empty: a first line not yet spoken waits in depth, out of focus
  const first = times[0][0];
  const html = set.map((vls, i) => {
    let j = 0;
    const next = times[i + 1]?.[0];
    const dim = next !== undefined && italic(i + 1) ? `;--dim:${r3(next)}` : "";
    const body = vls.map((v) => { const ws = words(v), ts = times[i].slice(j, j + ws.length); j += ws.length; return `<span class="ty-vl">${wordSpans(v, ts, i === 0 && first > 0.4)}</span>`; }).join("");
    return `<p class="ty-k-line${italic(i) ? " it" : ""}${dim ? " dims" : ""}" style="${dim.slice(1)}">${body}</p>`;
  }).join("");
  return cam(B, `<div class="ty-box ty-k" style="font-size:${px}px">${html}</div>`);
}

/* ---------- formula ---------- */

// Operators drawn as strokes (pathLength 1, so the CSS draws any of them the same way).
const P = (d) => d.map((x) => `<path pathLength="1" d="${x}"/>`).join("");
const SYMBOL = {
  "×": P(["M28 28 72 72", "M72 28 28 72"]),
  "÷": P(["M18 50h64"]) + `<circle cx="50" cy="24" r="6"/><circle cx="50" cy="76" r="6"/>`,
  "=": P(["M18 39h64", "M18 61h64"]),
  "+": P(["M50 18v64", "M18 50h64"]),
  "−": P(["M18 50h64"]), "-": P(["M18 50h64"]),
  "→": P(["M10 50h78", "M66 30l22 20-22 20"]),
};
// what an operator sounds like when it is read aloud
const SAID = { "×": ["times"], "÷": ["divided", "divide"], "=": ["give", "gives", "equal", "equals", "come", "comes", "that's"], "+": ["and", "plus"], "→": ["was", "assigned"] };
/** A graphite pencil stroke: a slightly uneven hand line, heavier in its middle. */
function pencil(w, seed = 3) {
  const pts = [], n = Math.max(6, Math.round(w / 60));
  for (let i = 0; i <= n; i++) pts.push([r3((w * i) / n), r3(5 + Math.sin(i * 1.7 + seed) * 1.1 + Math.sin(i * 0.6 + seed * 2) * 0.8)]);
  return `<svg class="ty-pencil" viewBox="0 0 ${Math.round(w)} 10" preserveAspectRatio="none"><path pathLength="1" d="M${pts.map((q) => q.join(" ")).join(" L")}"/></svg>`;
}
/** A term's width as set: numbers in Inter, inner operators light, words in Fraunces. */
function termW(text, px, italic) {
  const ws = words(text);
  return ws.reduce((a, wd) => a + (/^[×÷=+−→]$/.test(wd) ? 0.62 * px : /\d/.test(wd) && !isYear(wd) ? figW(wd, px, -0.02) : serifW(wd, px, italic)), 0) + Math.max(0, ws.length - 1) * 0.26 * px;
}

export function formula(job) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [];
  const terms = (p.terms || []).slice(0, 6).map((t) => (typeof t === "object" ? t : { text: t }));
  const ops = (p.ops || []).map((o) => String(o ?? "").trim());
  const n = terms.length;
  if (!n) return cam(B, "");
  const result = n > 1 && (ops[n - 2] === "=" || /^(?:is|are|was|costs?|equals?|gives?|makes?|comes? to)$/i.test(ops[n - 2] || ""));
  const isRes = (i) => result && i === n - 1;
  const lone = (i) => isRes(i) && /^[?…]$/.test(String(terms[i].text).trim());
  // a recut plan carries its own times (`ops_at`, `pencil_at`, `caption_at`, each term's `at`, all
  // from the word onsets); otherwise every term is found in the narration
  const recut = Array.isArray(p.ops_at) || p.pencil_at != null || p.caption_at != null;
  const all = terms.flatMap((t) => words(t.text)), raw = recut ? [] : align(all, spoken);
  let k = 0;
  const tt = terms.map((t) => {
    const ws = words(t.text), own = raw.slice(k, k + ws.length); k += ws.length;
    if (recut && t.at != null) return sayFrom(t.text, spoken, t.at);
    const f = own.find((x) => x != null);
    return f != null ? onsets(ws, spoken.filter((x) => x.t >= f - 0.01), f, 0.08) : null;
  });
  const opT = ops.map((o, i) => {
    if (p.ops_at?.[i] != null) return p.ops_at[i];
    const a = tt[i]?.[0] ?? terms[i].at ?? 0.4, said = SYMBOL[o] ? SAID[o] || [] : [norm(o)];
    const hit = spoken.find((x) => x.t > a && said.includes(norm(x.w)) && x.t < (tt[i + 1]?.[0] ?? Infinity) + 0.6);
    return hit ? hit.t : null;
  });
  terms.forEach((t, i) => {
    if (tt[i]) return;
    // a term the narration does not say ("?") lands with weight just after its operator is spoken
    const t0 = opT[i - 1] != null ? opT[i - 1] + 0.35 : t.at ?? 0.4 + i * 0.9;
    tt[i] = words(t.text).map((_, j) => t0 + j * 0.08);
  });
  if (!recut) for (let i = 1; i < n; i++) if (tt[i][0] < tt[i - 1][0]) tt[i] = tt[i].map((t) => t + (tt[i - 1][0] - tt[i][0]) + 0.2);
  const opAt = (i) => opT[i] ?? Math.max(tt[i][tt[i].length - 1] + 0.1, tt[i + 1][0] - 0.3);
  const tw = (i, px) => (lone(i) ? serifW(String(terms[i].text), px * 1.7, true) : termW(terms[i].text, px, isRes(i)));
  const ow = (o, px) => (SYMBOL[o] ? px * 0.62 : serifW(o, px * 0.62, true));
  const gapOf = (px) => px * 0.32, maxw = B.w - 20;
  const rowW = (px) => terms.reduce((a, _, i) => a + tw(i, px) + (i < n - 1 ? ow(ops[i] ?? "+", px) + 2 * gapOf(px) : 0), 0);
  const restW = (px) => Math.max(...terms.slice(1).map((_, j) => ow(ops[j] ?? "+", px) + 2 * gapOf(px) + tw(j + 1, px)));
  const alignW = (px) => tw(0, px) + restW(px);
  const gutOf = (px) => Math.max(px * 1.2, ...ops.map((o) => ow(o, px) + gapOf(px)));
  const ledgerW = (px) => gutOf(px) + Math.max(...terms.map((_, i) => tw(i, px)));
  let layout = null, px;
  for (px = DISPLAY[0]; px >= 96 && !layout; px -= 4) if (rowW(px) <= maxw) layout = "row";
  if (!layout && n > 1) for (px = DISPLAY[1]; px >= 72 && !layout; px -= 4) if (alignW(px) <= maxw) layout = "align";
  if (!layout) for (px = DISPLAY[1]; px >= 60 && !layout; px -= 4) if (ledgerW(px) <= maxw) layout = "ledger";
  px += 4;
  const gp = gapOf(px);
  // the skeleton (the operators faint, a blank under each term) is there from the first frame
  const opHTML = (i) => {
    const o = ops[i] ?? "+", st = `--at:-0.4;--lit:${r3(opAt(i))}`;
    return SYMBOL[o] ? `<span class="ty-f-op sym" style="${st}"><svg viewBox="0 0 100 100">${SYMBOL[o]}</svg></span>`
      : `<span class="ty-f-op word" style="${st}">${T(o)}</span>`;
  };
  // the sum's rule (and an unanswered "?") is graphite pencil, drawn on the word the plan gives
  const sumT = p.pencil_at ?? (result ? opAt(n - 2) - 0.1 : 0);
  const term = (i) => {
    const t0 = tt[i][0];
    const pencilQ = lone(i) && p.pencil_at != null && t0 < p.pencil_at;
    const body = pencilQ
      ? `<span class="ty-f-q pencil" style="--draw:-0.4;--drawd:${r3(Math.max(0.4, t0 + 0.4))}s;--ink:${r3(p.pencil_at)}">${T(terms[i].text)}</span>`
      : lone(i)
        ? `<span class="ty-f-q ty-land" style="--at:${r3(t0 - 0.1)};--d:0.45s">${T(terms[i].text)}</span>`
        : words(terms[i].text).map((wd, j) => {
          const t = tt[i][j], inner = /^[×÷=+−→]$/.test(wd) ? `<span class="ty-f-in">${esc(wd)}</span>` : /\d/.test(wd) && !isYear(wd) ? `<span class="ty-fn${isMoney(wd) ? " money" : ""}">${esc(wd)}</span>` : T(wd);
          return `<span class="ty-w${t <= 0.4 ? " cut" : " pre"}" style="--at:${r3(t <= 0.4 ? -0.12 : t)}">${inner}</span>`;
        }).join(" ");
    return `<span class="ty-f-term${isRes(i) ? " res" : ""}${lone(i) ? " lone" : ""}" style="--at:${r3(t0)};--slot:${r3(-0.4 + i * 0.08)}">` +
      `${isRes(i) ? bloom(tw(i, px) * 1.4, px * 2, pencilQ ? p.pencil_at : t0, false) : ""}<span class="ty-f-text">${body}</span>${pencilQ ? "" : `<i class="ty-f-slot"></i>`}</span>`;
  };
  let body;
  if (layout === "row") {
    body = `<div class="ty-f-row">${terms.map((_, i) => term(i) + (i < n - 1 ? opHTML(i) : "")).join("")}</div>`;
  } else {
    const col = layout === "align" ? Math.round(tw(0, px) + 6) : 0;
    const gut = gutOf(px), sumW = restW(px) + (layout === "ledger" ? gut - 2 * gp : 0);
    const lhs = (inner) => (layout === "align" ? `<span class="ty-f-lhs" style="width:${col}px">${inner}</span>` : `<span class="ty-f-gut" style="width:${px0(gut)}">${inner}</span>`);
    const rows = layout === "align" ? [`<div class="ty-f-line">${lhs(term(0))}${opHTML(0)}${term(1)}</div>`] : [`<div class="ty-f-line">${lhs("")}${term(0)}</div>`];
    for (let i = layout === "align" ? 1 : 0; i < n - 1; i++) {
      const sum = isRes(i + 1) && n > 2;
      rows.push(`<div class="ty-f-line${sum ? " sum" : ""}">${lhs(layout === "ledger" ? opHTML(i) : "")}${layout === "align" ? opHTML(i) : ""}${term(i + 1)}` +
        `${sum ? `<span class="ty-f-sum" style="--at:${r3(sumT)};left:${px0(col)};width:${px0(sumW)}">${pencil(sumW)}</span>` : ""}</div>`);
    }
    body = rows.join("");
  }
  const lastT = Math.max(...tt.map((x) => x[x.length - 1]));
  const capT = p.caption ? p.caption_at ?? Math.max(lastT + 0.6, saidAt(p.caption, spoken, lastT + 1) ?? lastT + 0.8) : 0;
  const cap = p.caption ? `<p class="ty-f-cap">${wordSpans(p.caption, sayFrom(p.caption, spoken, capT))}</p>` : "";
  return cam(B, `<div class="ty-box ty-f ${layout}" style="font-size:${px}px;--gap:${px0(gp)}">${body}${cap}</div>`);
}

/* ---------- timeline: real dates on a line; any other list drawn as what it is ---------- */

/** Which honest form a list of events takes. */
function timelineForm(evs, job) {
  if (evs.every((e) => timeish(e.date))) return "line";
  const fig = (e) => (figureLed(e.label) ? e.label : figureLed(e.date) ? e.date : null);
  const figs = evs.map(fig);
  // a step: the figure the line lands on is the difference of two neighbouring prices
  const key = job.on == null ? -1 : evs.findIndex((e) => Math.abs((e.at ?? -9) - job.on) < 0.25);
  if (key >= 0 && figs[key] && isMoney(figs[key])) {
    const v = figs.map((f) => (f && isMoney(f) ? amount(f) : NaN));
    for (let i = 0; i + 1 < evs.length; i++) if (i !== key && i + 1 !== key && Math.abs(v[i + 1] - v[i] - v[key]) < 0.006) return "step";
  }
  const pcts = figs.filter((f) => f && /%/.test(f));
  if (pcts.length >= 2 && pcts.reduce((a, f) => a + amount(f), 0) <= 100.5) return "shares";
  if (figs.every((f) => f) && evs.length >= 2) {
    const k = figs.map(kindOf), u = figs.map(unitOf);
    if (k.every((x) => x === k[0] && x !== "time") && u.every((x) => x === u[0]) && !figs.some((f) => /\b(more than|over|under)\b/.test(f))) return "bars";
  }
  return "ledger";
}

export function timeline(job) {
  const p = job.params || {};
  const evs = (p.events || []).filter((e) => e && typeof e === "object");
  if (!evs.length) return cam(stage(job), "");
  // the plan's `layout` decides; without it the stage infers the honest form from the events
  const FORMS = { dates: "line", line: "line", bars: "bars", share: "shares", shares: "shares", ledger: "ledger", step: "step" };
  let form = FORMS[p.layout] || timelineForm(evs, job);
  if (form === "step" && stepKey(evs, job) < 0) form = "ledger";
  return { line, bars, shares, step, ledger }[form](job, evs);
}

/** The event's figure side and words side, and when each is said (`name_at` and `at` from the plan win). */
function sides(e, spoken) {
  const figSide = figureLed(e.label) ? "label" : figureLed(e.date) ? "date" : null;
  const fig = figSide ? e[figSide] : null, name = figSide === "label" ? e.date : figSide === "date" ? e.label : null;
  const figT = fig ? spokenAt(fig, spoken, e.at) : e.at ?? 0.4;
  const nameT = e.name_at ?? (name ? saidAt(name, spoken, figT) ?? figT : figT);
  return { fig, name, figT, nameT: e.name_at ?? Math.min(nameT, figT) };
}
const head = (p, spoken) => (p.heading ? `<p class="ty-head">${wordSpans(p.heading, p.heading_at != null ? headTimes(p.heading, spoken, p.heading_at) : headWords(p.heading, spoken))}</p>` : "");
/** The event the line lands on (`on`) for a step: a price that is the difference of two neighbours. */
function stepKey(evs, job) {
  const fig = (e) => (figureLed(e.label) ? e.label : figureLed(e.date) ? e.date : null);
  const v = evs.map((e) => (fig(e) && isMoney(fig(e)) ? amount(fig(e)) : NaN));
  const cands = evs.map((_, i) => i).filter((i) => Number.isFinite(v[i]) && evs.some((_, j) => j + 1 < evs.length && j !== i && j + 1 !== i && Math.abs(v[j + 1] - v[j] - v[i]) < 0.006));
  if (!cands.length) return -1;
  if (job.on == null) return cands[cands.length - 1];
  return cands.reduce((b, i) => (Math.abs((evs[i].at ?? 0) - job.on) < Math.abs((evs[b].at ?? 0) - job.on) ? i : b));
}

/**
 * Real dates: a line drawn across the dark, a tick landing on each spoken date at its true position.
 * The line stays still (the shared camera pushes); where labels would collide, each takes the first
 * free tier, alternately above and below the line, on a stem from its tick.
 */
function line(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], n = evs.length, W = B.w;
  const big0 = n === 1 ? 1.4 : n === 2 ? 1.15 : 1;
  // a date the narration does not say here is the setting: the first one is there from the cut
  const ev = evs.map((e, i) => {
    const said = saidAt(e.date, spoken, e.at);
    const t = said ?? (i === 0 ? 0 : e.at ?? 0.5 + i * 0.9);
    return { e, i, pos: e.pos ?? (n === 1 ? 0.06 : 0.06 + (0.88 * i) / (n - 1)), t, said };
  });
  ev.forEach((v, i) => { v.land = Math.max(v.t, i ? ev[i - 1].land + 0.35 : 0); });
  // the labels' size: as large as lets every tier fit the box (down to 70%)
  const room = B.h - (p.heading ? 150 : 0);
  let levels, blockH, pitch, stem0, above, below;
  for (const fit of [1, 0.9, 0.8, 0.7]) {
  const big = big0 * fit;
  ev.forEach((v) => { v.tier = null; });
  ev.forEach((v) => {
    const date = String(v.e.date ?? ""), lab = String(v.e.label ?? ""), labFig = figureLed(lab);
    v.dpx = Math.round((timeish(date) && date.length <= 18 ? 64 : 52) * big);
    v.lpx = Math.round(BODY * Math.min(big, 1.15));
    const lt = v.e.name_at ?? (labFig ? spokenAt(lab, spoken, v.land) : saidAfter(lab, spoken, v.land) ?? v.land + 0.15);
    v.lt = Math.max(v.land, lt);
    v.dateHTML = `<p class="ty-t-date" style="font-size:${v.dpx}px">${wordSpans(date, v.said != null ? sayTimes(date, spoken, v.land, v.land) : words(date).map(() => v.land), v.i === 0 && v.land <= 1.5)}</p>`;
    v.labelHTML = labFig ? `<div class="ty-t-fig" style="font-size:${Math.round(76 * big)}px">${figLine(lab, Math.round(76 * big), { times: [v.lt], unitMin: LABEL }).html}</div>`
      : `<p class="ty-t-label" style="font-size:${v.lpx}px">${wordSpans(lab, sayFrom(lab, spoken, v.lt))}</p>`;
    v.bw = Math.max(serifW(date, v.dpx), labFig ? figLine(lab, Math.round(76 * big)).w : labelW(lab, v.lpx, 0)) + 40;
    v.bh = v.dpx * 1.1 + (labFig ? 76 * big : v.lpx * 1.2) + 12;
    v.x = Math.round(v.pos * W);
  });
  // tiers: up 0, down 0, up 1, down 1 ... placed from the right, each on the first tier where its
  // label touches no other label, its stem crosses no nearer label, and no farther stem crosses it
  ev.forEach((v) => {
    let l = v.x, r = v.x + v.bw;
    if (r > W) { l = Math.max(0, v.x - v.bw + 16); r = l + v.bw; v.rt = v.x - v.bw + 16 >= 0; if (!v.rt) { l = W - v.bw; r = W; } }
    v.l = l; v.r = r;
  });
  const placed = [];
  [...ev].reverse().forEach((v) => {
    for (let k = 0; k < 10; k++) {
      const side = k % 2, lvl = Math.floor(k / 2);
      const ok = placed.every((u) => {
        if (u.tier % 2 !== side) return true;
        const ul = Math.floor(u.tier / 2);
        if (ul === lvl) return v.r + 24 <= u.l || v.l >= u.r + 24;
        if (ul < lvl) return !(v.x >= u.l - 12 && v.x <= u.r + 12);   // my stem through its label
        return !(u.x >= v.l - 12 && u.x <= v.r + 12);                 // its stem through my label
      });
      if (ok) { v.tier = k; placed.push(v); break; }
    }
    if (v.tier == null) { v.tier = 0; placed.push(v); }
  });
  levels = Math.max(...ev.map((v) => Math.floor(v.tier / 2))) + 1; blockH = Math.max(...ev.map((v) => v.bh));
  pitch = blockH + 30; stem0 = 44;
  const ups = levels, downs = ev.some((v) => v.tier % 2) ? Math.max(...ev.filter((v) => v.tier % 2).map((v) => Math.floor(v.tier / 2))) + 1 : 0;
  above = stem0 + (ups - 1) * pitch + blockH + 8; below = downs ? stem0 + (downs - 1) * pitch + blockH + 8 : 0;
  if (above + below <= room) break;
  }
  const segs = ev.map((v, i) => {
    const x0 = i ? ev[i - 1].x : 0, s = Math.max(-0.4, i ? Math.max(ev[i - 1].land + 0.2, v.land - 0.8) : Math.min(-0.4, v.land - 0.8));
    return { x0, x1: v.x, s, d: Math.max(0.3, v.land - s) };
  });
  const lastV = ev[n - 1], lineEnd = W;
  // after the last date, light runs back along the line to the first, on the narration's next words
  const bs = beats(ev.flatMap((v) => [v.land, v.lt]), spoken, B.dur, 1);
  const back = n > 1 ? bs.map((b) => `<i class="ty-t-back" style="left:${ev[0].x}px;width:${lastV.x - ev[0].x}px;--at:${r3(b.t)}"></i>`).join("")
    : bs.map((b) => `<i class="ty-t-head again" style="left:${ev[0].x}px;--w:${Math.round(lineEnd - ev[0].x)}px;--at:${r3(b.t)};--d:1.6s"></i>`).join("");
  const lineHTML = segs.map((g) => `<i class="ty-t-seg" style="left:${g.x0}px;width:${g.x1 - g.x0}px;--at:${r3(g.s)};--d:${r3(g.d)}s"></i>` +
    `<i class="ty-t-head" style="left:${g.x0}px;--w:${g.x1 - g.x0}px;--at:${r3(g.s)};--d:${r3(g.d)}s"></i>`).join("") +
    `<i class="ty-t-seg tail" style="left:${lastV.x}px;width:${lineEnd - lastV.x}px;--at:${r3(lastV.land + 0.2)};--d:0.8s"></i>`;
  const events = ev.map((v, i) => {
    const k = Math.floor(v.tier / 2), up = v.tier % 2 === 0, stem = stem0 + k * pitch;
    const pos = up ? `bottom:${stem + 8}px` : `top:${stem + 8}px`;
    const anchor = v.rt ? "right:-2px;text-align:right" : `left:${Math.round(v.l - v.x - 2)}px`;
    return `<div class="ty-t-ev" style="left:${v.x}px;--at:${r3(v.land <= 0.4 ? -0.3 : v.land)};--next:${r3(ev[i + 1]?.land ?? 999)};${bs.length && i === 0 ? `--back:${r3(bs[0].t + 0.9)}` : "--back:999"}">` +
      `<i class="ty-t-stem ${up ? "up" : "down"}" style="height:${stem}px"></i><i class="ty-t-node"></i><i class="ty-t-ring"></i>` +
      `<div class="ty-t-blk" style="${pos};${anchor}">${v.dateHTML}${v.labelHTML}</div></div>`;
  }).join("");
  return cam(B, `<div class="ty-box ty-t">${head(p, spoken)}<div class="ty-t-area" style="height:${Math.round(above + below)}px">` +
    `<div class="ty-t-track" style="top:${Math.round(above)}px;width:${lineEnd}px"><i class="ty-t-ghost" style="width:${lineEnd}px"></i>${lineHTML}${back}${events}</div></div></div>`);
}

/** Comparable amounts (one unit): bars to scale from one axis, each growing as it is said; `reveal_scale_at` pulls back to the whole. */
function bars(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [];
  const rows = evs.map((e) => ({ e, ...sides(e, spoken) }));
  rows.forEach((r) => { r.v = amount(r.fig); });
  const max = Math.max(...rows.map((r) => r.v));
  const keyI = job.on == null ? -1 : rows.findIndex((r) => Math.abs(r.figT - job.on) < 0.3);
  const namePx = 44, valPx = 80;
  const leftW = Math.max(...rows.map((r) => Math.max(serifW(r.name || "", namePx), figLine(r.fig, valPx).w))) + 60;
  const barMax = Math.max(240, B.w - leftW - 20);
  const pitch = clamp((B.h - (p.heading ? 140 : 0)) / rows.length, 120, 190);
  // before the reveal the bars are drawn zoomed in, together: the largest runs out of the frame
  const vs = rows.map((r) => r.v).sort((a, b) => b - a);
  const k = p.reveal_scale_at != null && vs.length > 1 ? clamp(0.45 / (vs[1] / vs[0]), 1, 8) : 1;
  const bs = beats([...rows.flatMap((r) => [r.nameT, r.figT]), p.reveal_scale_at], spoken, B.dur, rows.length);
  const html = rows.map((r, i) => {
    const blue = isMoney(r.fig) && (keyI >= 0 ? i === keyI : true);
    const until = keyI >= 0 ? 999 : rows[i + 1]?.figT ?? 999;
    const f = figLine(r.fig, valPx, { times: figTimes(r.fig, spoken, r.figT), blue, unitMin: LABEL });
    return `<div class="ty-b-row" style="height:${Math.round(pitch)}px">` +
      `<div class="ty-b-left" style="width:${Math.round(leftW)}px"><p class="ty-b-name">${wordSpans(r.name || "", sayFrom(r.name || "", spoken, r.nameT))}</p>` +
      `<div class="ty-b-val${blue && keyI < 0 ? " fades" : ""}" style="--until:${r3(until)}">${f.html}</div></div>` +
      `<div class="ty-b-bar" style="width:${r3(Math.max(4, (r.v / max) * barMax))}px;--at:${r3(r.figT - 0.1)}"><i></i>${bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}</div></div>`;
  }).join("");
  const scale = k > 1 ? `--k:${r3(k)};--reveal:${r3(p.reveal_scale_at)}` : "--k:1;--reveal:999";
  return cam(B, `<div class="ty-box ty-b">${head(p, spoken)}<div class="ty-b-rows" style="--axis:${Math.round(leftW)}px;${scale}">${html}</div></div>`);
}

/**
 * A share of a whole: one bar for the whole, split as each part is said. Percentages split a 100%
 * bar (the rest left unfilled); counts make the largest the whole and the others its parts, to scale.
 */
function shares(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [];
  const all = evs.map((e) => ({ e, ...sides(e, spoken) }));
  const pct = all.filter((q) => q.fig && /%/.test(q.fig));
  let parts, context, whole = null;
  if (pct.length) { parts = pct; context = all.filter((q) => !pct.includes(q)); }
  else {
    const figs = all.filter((q) => q.fig);
    whole = figs.reduce((a, q) => (amount(q.fig) > amount(a.fig) ? q : a), figs[0]);
    parts = figs.filter((q) => q !== whole); context = all.filter((q) => !q.fig);
  }
  const W = Math.min(B.w, 1400), total = whole ? amount(whole.fig) : 100;
  let x = 0;
  parts.forEach((q) => { q.v = amount(q.fig); q.x = x; q.w = (q.v / total) * W; x += q.w; });
  const firstT = Math.min(...[...parts, ...(whole ? [whole] : [])].map((q) => Math.min(q.figT, q.nameT)));
  const trackT = whole ? whole.figT - 0.1 : Math.max(-0.4, firstT - 2.2);
  const bs = beats([...context.flatMap((c) => [c.figT, c.nameT]), trackT, ...parts.flatMap((q) => [q.figT, q.nameT])], spoken, B.dur, parts.length);
  const ctx = context.map((c) => {
    const t = saidAt(c.e.date, spoken, c.e.at) ?? c.e.at ?? 0.4, lt = c.e.name_at ?? saidAt(c.e.label, spoken, t + 1) ?? t + 1;
    return `<p class="ty-s-ctx"><span class="ty-fd">${wordSpans(c.e.date, sayFrom(c.e.date, spoken, t), t <= 1.5)}</span>` +
      ` <span class="ty-s-ctx-l">${wordSpans(c.e.label, sayFrom(c.e.label, spoken, lt))}</span></p>`;
  }).join("");
  const figPx = whole ? 88 : 120;
  const lab = (q, below) => {
    const f = figLine(q.fig, figPx, { times: figTimes(q.fig, spoken, q.figT), unitMin: LABEL });
    return { f, html: `<div class="ty-s-fig" style="font-size:${figPx}px">${f.html}</div><p class="ty-s-name">${wordSpans(q.name || "", sayFrom(q.name || "", spoken, Math.min(q.nameT, q.figT + 0.3)))}</p>` };
  };
  // the whole's figure sits over the bar at its left; with a whole, each part's figure sits under its segment
  const top = whole ? `<div class="ty-s-lab" style="left:0">${lab(whole).html}</div>` : "";
  const segs = parts.map((q, i) => {
    const L = lab(q), lx = Math.max(0, Math.min(q.x, W - L.f.w));
    return `<div class="ty-s-seg" style="left:${r3(q.x)}px;width:${r3(q.w)}px;--at:${r3(q.figT - 0.1)}"><i></i>${bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}</div>` +
      `<div class="ty-s-lab${whole ? " under" : ""}" style="left:${r3(lx)}px">${L.html}</div>`;
  }).join("");
  return cam(B, `<div class="ty-box ty-s">${head(p, spoken)}${ctx}<div class="ty-s-bar${whole ? " whole" : ""}" style="width:${Math.round(W)}px;--at:${r3(trackT)}"><i class="ty-s-track"></i>${top}${segs}</div></div>`);
}

/** A price step: the prices on either side of the edge as columns to scale, the jump between them the hero. */
function step(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [];
  const rows = evs.map((e, i) => ({ e, i, ...sides(e, spoken) }));
  rows.forEach((r) => { r.v = r.fig && isMoney(r.fig) ? amount(r.fig) : NaN; });
  const key = stepKey(evs, job);
  const pairs = [];
  for (let i = 0; i + 1 < rows.length; i++) {
    if (i === key || i + 1 === key || rows[i].used) continue;
    if (Number.isFinite(rows[i].v) && Number.isFinite(rows[i + 1].v) && rows[i + 1].v > rows[i].v) { pairs.push([rows[i], rows[i + 1]]); rows[i].used = rows[i + 1].used = true; }
  }
  const stepPair = pairs.find(([a, b]) => Math.abs(b.v - a.v - rows[key].v) < 0.006);
  const context = rows.filter((r) => !r.used && r.i !== key);
  const max = Math.max(...pairs.flat().map((r) => r.v));
  const colW = 160, gapIn = 26, gapOut = 96;
  const colsW = pairs.length * (2 * colW + gapIn) + (pairs.length - 1) * gapOut;
  // the heading, then (when there is any) a strip of the card's context, then the columns
  const topY = (p.heading ? 110 : 0) + (context.length ? 130 : 0);
  const baseY = B.h - 124, H = Math.max(160, baseY - topY - 70);   // three label lines under the base stay inside the box
  const bs = beats(rows.map((r) => r.figT), spoken, B.dur, 1);
  let x = 0;
  const cols = pairs.map(([a, b]) => {
    const out = [a, b].map((r, j) => {
      const h = (r.v / max) * H, isStep = stepPair && j === 1 && r === stepPair[1];
      const riser = isStep ? (stepPair[0].v / max) * H : 0;
      const f = figLine(r.fig, 48, { times: [r.figT], quiet: true, unitMin: LABEL });
      const html = `<div class="ty-c-col" style="left:${x}px;width:${colW}px;height:${r3(h)}px;top:${r3(baseY - h)}px;--at:${r3(r.figT - 0.1)}"><i></i>` +
        `${isStep ? `<b class="ty-c-riser" style="height:${r3(h - riser)}px;--at:${r3(rows[key].figT - 0.15)}"></b>${pulses(bs, 0, "pulse-riser")}` : ""}` +
        `<div class="ty-c-val">${f.html}</div></div>` +
        `<p class="ty-c-lab" style="left:${x}px;width:${colW + 20}px;top:${baseY + 16}px">${wordSpans(r.name || "", sayFrom(r.name || "", spoken, r.nameT))}</p>`;
      x += colW + (j ? 0 : gapIn);
      return html;
    }).join("");
    x += gapOut;
    return out;
  }).join("");
  const strip = context.length ? `<div class="ty-c-strip" style="top:${p.heading ? 110 : 0}px">${context.map((r) => {
    const t = r.fig ? r.figT : saidAt(r.e.date, spoken, r.e.at) ?? r.e.at ?? 0.4;
    const val = r.fig ? figLine(r.fig, 56, { times: figTimes(r.fig, spoken, r.figT), quiet: isMoney(r.fig), unitMin: LABEL }).html
      : `<span class="ty-fd">${wordSpans(r.e.date, sayFrom(r.e.date, spoken, t))}</span>`;
    const nm = r.fig ? r.name : r.e.label, nt = r.fig ? r.nameT : r.e.name_at ?? saidAt(nm, spoken, t) ?? t;
    return `<div class="ty-c-row"><p class="ty-c-rname">${wordSpans(nm || "", sayFrom(nm || "", spoken, Math.min(nt, t)))}</p><div class="ty-c-rval">${val}</div></div>`;
  }).join("")}</div>` : "";
  // the hero: the jump, to the right of its columns
  const r = rows[key], rx = colsW + 110, rw = B.w - rx;
  const heroPx = clamp(Math.min(Math.floor(rw / (figW(String(r.fig).replace(/[^\d$.,%]/g, ""), 1, -0.04) + 0.2)), Math.floor((H - 70) / 0.92)), 110, 240);
  const f = figLine(r.fig, heroPx, { times: [r.figT], blue: true, unitMin: LABEL });
  const hero = `<div class="ty-c-hero" style="left:${rx}px;width:${rw}px;top:${Math.round(baseY - H)}px;height:${Math.round(H)}px">` +
    `<p class="ty-c-name">${wordSpans(r.name || "", sayFrom(r.name || "", spoken, r.nameT))}</p>` +
    `<div class="ty-c-fig" style="font-size:${heroPx}px">${bloom(f.w * 1.4, heroPx * 1.8, r.figT, true)}${f.html}${pulses(bs, 0, "pulse-blue")}</div></div>`;
  return cam(B, `<div class="ty-box ty-c">${head(p, spoken)}<div class="ty-c-cols" style="height:${B.h}px">${strip}` +
    `<i class="ty-c-base" style="top:${baseY}px;width:${colsW + 30}px"></i>${cols}${hero}</div></div>`);
}

/**
 * Anything else: a typeset ledger. Rows aligned, figures right-aligned; in a list of three or more,
 * a row without a figure of the list's kind heads a section. Long names (sources) stack over their
 * figure, set in the plan's `face` (period print, typewriter). A verbatim `words` quote closes it,
 * word by word on its onsets, its key words brightest.
 */
function ledger(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [];
  const rows = evs.map((e) => ({ e, ...sides(e, spoken) }));
  rows.forEach((r) => { if (!r.fig && timeish(r.e.label)) { r.fig = r.e.label; r.name = r.e.date; r.figT = saidAt(r.fig, spoken, r.e.at) ?? r.e.at ?? 0.4; r.nameT = r.e.name_at ?? r.figT; } });
  const kinds = rows.filter((r) => r.fig).map((r) => kindOf(r.fig));
  const main = kinds.slice().sort((a, b) => kinds.filter((x) => x === b).length - kinds.filter((x) => x === a).length)[0];
  rows.forEach((r) => { r.section = !r.fig || (rows.length >= 3 && kindOf(r.fig) !== main); });
  const keyI = job.on == null ? -1 : rows.findIndex((r) => !r.section && Math.abs(r.figT - job.on) < 0.3);
  const W = Math.min(B.w, 1240), namePx = 48;
  const stacked = rows.some((r) => !r.section && serifW(r.name || "", namePx) > W * 0.5);
  const valPx = stacked ? 112 : 64;
  const q = p.words?.text ? p.words : null;
  const qPx = 52, qLines = q ? Math.ceil(serifW(q.text, qPx, true) / W) : 0;
  const pitch = clamp((B.h - (p.heading ? 140 : 0) - (q ? qLines * qPx * 1.3 + 70 : 0)) / rows.length, 64, stacked ? 230 : 110);
  const bs = beats([...rows.flatMap((r) => [r.figT, r.nameT]), ...(q ? [q.at] : [])], spoken, B.dur, rows.length);
  const face = (r) => (r.e.face === "period" ? " period" : r.e.face === "typed" ? " typed" : "");
  const html = rows.map((r, i) => {
    const glints = bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("");
    if (r.section) {
      const a = String(r.e.date ?? ""), b = String(r.e.label ?? "");
      const at = r.e.name_at ?? saidAt(a, spoken, r.e.at) ?? r.e.at ?? 0.4, bt = saidAt(b, spoken, Math.max(at, r.e.at ?? at)) ?? at + 0.4;
      return `<div class="ty-l-sec" style="height:${Math.round(pitch * 0.85)}px">${glints}<span class="ty-l-sa">${wordSpans(a, sayFrom(a, spoken, at))}</span>` +
        `<span class="ty-l-sb">${wordSpans(b, sayFrom(b, spoken, bt))}</span></div>`;
    }
    const blue = isMoney(r.fig) && (keyI >= 0 ? i === keyI : true);
    const until = keyI >= 0 ? 999 : rows.slice(i + 1).find((x) => !x.section && isMoney(x.fig))?.figT ?? 999;
    const f = figLine(r.fig, valPx, { times: figTimes(r.fig, spoken, r.figT), blue, unitMin: LABEL });
    const name = `<p class="ty-l-name${face(r)}" style="font-size:${stacked ? 40 : namePx}px">${wordSpans(r.name || "", sayFrom(r.name || "", spoken, r.nameT))}</p>`;
    return stacked
      ? `<div class="ty-l-entry" style="min-height:${Math.round(pitch)}px">${glints}${name}<div class="ty-l-val${blue && keyI < 0 ? " fades" : ""}" style="--until:${r3(until)};font-size:${valPx}px">${f.html}</div></div>`
      : `<div class="ty-l-row" style="height:${Math.round(pitch)}px">${glints}${name}<i class="ty-l-lead" style="--at:${r3(Math.min(r.nameT, r.figT))}"></i>` +
        `<div class="ty-l-val${blue && keyI < 0 ? " fades" : ""}" style="--until:${r3(until)}">${f.html}</div></div>`;
  }).join("");
  let quote = "";
  if (q) {
    const ts = sayFrom(q.text, spoken, q.at ?? 0.4);
    const keys = (q.key || []).map((k) => words(k).map(norm));
    const ws = words(q.text), bright = ws.map(() => false);
    keys.forEach((kw) => { for (let i = 0; i + kw.length <= ws.length; i++) if (kw.every((x, j) => norm(ws[i + j]) === x)) kw.forEach((_, j) => { bright[i + j] = true; }); });
    quote = `<p class="ty-l-quote" style="font-size:${qPx}px">${ws.map((w, i) => `<span class="ty-w${bright[i] ? " key" : ""}" style="--at:${r3(ts[i])}">${T(w)}</span>`).join(" ")}</p>`;
  }
  return cam(B, `<div class="ty-box ty-l">${head(p, spoken)}<div class="ty-l-rows${stacked ? " stacked" : ""}" style="width:${W}px">${html}</div>${quote}</div>`);
}

/* ---------- chapter ---------- */

const ROMAN = [[10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
const roman = (k) => { let n = Math.floor(+k), s = ""; if (!(n > 0 && n < 40)) return ""; for (const [v, r] of ROMAN) while (n >= v) { s += r; n -= v; } return s; };
/** Fit display serif: the largest token size at which `text` sets in at most two lines. */
function fitTitle(text, sizes, width, italic = false) {
  for (const px of sizes) { const l = breakLine(text, (s) => serifW(s, px, italic), width); if (l) return { px, lines: l }; }
  return { px: sizes[sizes.length - 1], lines: [text] };
}

export function chapter(job) {
  const B = stage(job, true), p = job.params || {}, title = String(p.title || "");
  const num = roman(p.index ?? p.number ?? 0);
  const { px, lines } = fitTitle(title, [DISPLAY[0], DISPLAY[1]], Math.min(B.w, 1400));
  // the title is complete well before the card's end: word by word from the first frame
  let k = 0;
  const t = lines.map((l) => `<span class="ty-vl">${words(l).map((w) => `<span class="ty-cw" style="--at:${r3(-0.15 + k++ * 0.09)}">${T(w)}</span>`).join(" ")}</span>`).join("");
  return cam(B, `<div class="ty-box ty-ch"><div class="ty-ch-top"><p class="ty-ch-kick">Chapter${num ? ` <b>${num}</b>` : ""}</p><i class="ty-ch-hair"></i></div>` +
    `<h2 class="ty-ch-title" style="font-size:${px}px">${bloom(1000, px * 2.4, 0, false)}${t}</h2></div>`);
}

/* ---------- end ---------- */

export function end(job) {
  const B = stage(job, true), p = job.params || {}, spoken = job.words || [];
  const full = String(p.headline || "");
  // the address sets on its own line, in Inter; the headline keeps the rest of its words
  const url = (full.match(/\b[a-z0-9-]+\.(?:com|org|net|io)(?:\/[\w\-/]*)?/i) || [])[0] || "";
  const headline = url ? full.replace(new RegExp(`\\s*(?:at|on|:)?\\s*${url.replace(/[.\/]/g, "\\$&")}\\.?`), ".").replace(/\.\.$/, ".") : full;
  const W = 900;   // the right 45% stays clear for YouTube's end-screen elements
  const { px, lines } = fitTitle(headline, DISPLAY, W);
  let k = 0;
  const h = lines.map((l) => `<span class="ty-vl">${words(l).map((w) => `<span class="ty-cw" style="--at:${r3(-0.2 + k++ * 0.08)}">${T(w)}</span>`).join(" ")}</span>`).join("");
  const sec = p.secondary ? `<p class="ty-e-sec">${speak(p.secondary, spoken, 1.2)}</p>` : "";
  return cam(B, `<div class="ty-box ty-e" style="width:${W}px"><h2 class="ty-e-head" style="font-size:${px}px">${h}</h2>` +
    `${url ? `<p class="ty-e-url"><span class="ty-w" style="--at:0.9">${esc(url)}</span><i class="ty-e-rule" style="--at:1.05"></i></p>` : ""}${sec}</div>`);
}
