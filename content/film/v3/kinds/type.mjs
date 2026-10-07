// v3 type: figures and words as light on the dark desk (docs/content/FILM_LOOK_V3.md, "Data is
// light"; round 2, the critique of 2026-10-06; round 3, the finishing editors' findings). Each kind
// takes a resolved job and returns the shot's inner HTML; ../shots.mjs wraps it in the key light,
// grade, vignette and the label slot.
//
// The system: time is set in Fraunces, quantities and money in Inter 500 (the hero tokens), and
// a figure's words ("cents", "about", "a ton") small beside it in Fraunces italic, ivory 70%,
// never blue. Only the figure the line lands on is blue. One motif ties the kinds together: 2 px
// hairlines that draw themselves, a bright point at the drawing end. Nothing counts: a figure
// lands whole on its own spoken word from nothing (never a blur that still reads), a date with its
// month; a figure the voice said before the cut (`job.known`) may stand sharp from the first frame.
// Every spoken word lands on its onset from `job.words`, never early. Data is drawn only where it
// encodes something: real dates on a line, comparable amounts as bars to scale, a share as one
// 100% bar, a price step as columns, a weight step as a staircase, anything else as a typeset
// ledger. Every figure and word on screen is the job's own.
//
// Composition (round 3): a kind fills the 1600 × 760 grid, not its top-left corner. A lone figure
// is centred on the frame's optical centre; a companion print (job.print) narrows the box to the
// left 820 px and the figure keeps to it. The first frame always shows something composed: the
// furniture of the kind (an axis, row names, a formula's operators and its blanks, a rule) stands
// at the cut and only the figures wait for their words.
//
// The stage runs no layout script, so layout is decided here, at build time, from the faces'
// measured advances (Chrome, 2026-10-06), inside a box the shared camera's push never carries
// out of title-safe (see stage()).
import { esc, labels } from "../shots.mjs";

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

const NUM = /\$?\d+(?:,\d{3})*(?:\.\d+)?(?:%|s(?![a-z]))?/g;   // a decade ("1890s") is one figure
const MONTH = /\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b/;
const isMoney = (s) => /\$|¢|\bcents?\b/.test(String(s ?? ""));
const isYear = (n) => /^\d{4}s?$/.test(n) && +n.slice(0, 4) >= 1500 && +n.slice(0, 4) <= 2100;
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
const headWords = (text, spoken) => words(text).map((w) => (/\d/.test(w) || SPELLED.test(norm(w)) ? (spoken || []).find((x) => norm(x.w) === norm(w))?.t ?? 0 : 0));
/** A heading set at the cut, unless it holds a figure the voice says here: then it is read in with the voice, word by word. */
function headSay(text, spoken) {
  const ws = words(text);
  if (!ws.some((w) => /\d/.test(w) || SPELLED.test(norm(w))) || !ws.some((w) => (/\d/.test(w) || SPELLED.test(norm(w))) && (spoken || []).some((x) => norm(x.w) === norm(w)))) return headWords(text, spoken);
  const ts = phraseTimes(text, spoken, 0, 0.1);
  return ts ? ts.map((t) => Math.max(0, t)) : headWords(text, spoken);
}
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
  const own = (n, from, near) => (spoken || []).filter((x) => x.t >= from && x.t <= from + 2 && norm(x.w) === norm(n)).sort((a, b) => Math.abs(a.t - near) - Math.abs(b.t - near))[0]?.t;
  const first = nums.length && !MONTH.test(text) ? own(nums[0].n, t0 - 0.3, t0) : null;   // a date lands on its month
  const t1 = first != null ? Math.max(t0, first) : t0;
  return nums.map((t, i) => (i ? Math.max(t1 + 0.2, spokenAt(t.n, (spoken || []).filter((x) => x.t > t1), t1 + 0.6)) : t1));
}

/* ---------- round 3: what may be read, and when ---------- */

/** A spelled-out number is a figure ("fifty miles", "six years", "fifteen-minute"). */
const SPELLED = /^(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|dozen)(?:-[a-z]+)?$/;
const isFigWord = (w) => /\d/.test(w) || SPELLED.test(norm(w));
const hasFig = (s) => words(s).some(isFigWord);
/** The figures the voice said before this shot's first frame: such a figure may stand sharp at the cut. */
function knownOf(job) {
  const vals = new Set(Object.values(job.known || {}).map((v) => String(v ?? "").trim()).filter(Boolean));
  return (s) => vals.has(String(s ?? "").trim());
}
/** Whether every figure word in a text was said before the cut (job.known): such a name may stand at the cut. */
function knownWords(job) {
  const set = new Set(Object.values(job.known || {}).flatMap((v) => words(v).map(norm)));
  return (text) => words(text).filter(isFigWord).every((w) => set.has(norm(w)));
}
/** When a figure may first be read: its own number word (never a qualifier's, "an estimated"); a date on its month. */
function figOnset(text, spoken, near) {
  const s = String(text ?? "");
  if (MONTH.test(s) || !/\d/.test(s)) return saidAt(s, spoken, near) ?? near ?? 0.4;
  return spokenAt(s, spoken, near);
}
/** The height a frame's heading takes (64 px Fraunces, the 56 px under it), or 0. */
const headH = (text, w) => (text ? Math.min(3, Math.ceil(serifW(text, HEADING) / Math.max(200, w - 12))) * HEADING * 1.1 + 56 : 0);
/** Balanced lines: `ws` broken into exactly `k` lines with the narrowest widest line. */
function breakK(ws, k, w) {
  if (k <= 1 || ws.length < 2) return [ws.join(" ")];
  let best = null;
  const rec = (start, left, acc) => {
    if (left === 1) { const l = ws.slice(start).join(" "), m = Math.max(...acc.map(w), w(l)); if (!best || m < best.m) best = { m, lines: [...acc, l] }; return; }
    for (let e = start + 1; e <= ws.length - left + 1; e++) rec(e, left - 1, [...acc, ws.slice(start, e).join(" ")]);
  };
  if (ws.length > 26) return [ws.join(" ")];
  rec(0, Math.min(k, ws.length), []);
  return best.lines;
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
  // a line's box runs above its capitals (the font's ascent): keep 30 px of the safe band for it;
  // a companion print (photos.COMPANION) takes the desk right of x = 1040, 60 px of air before it
  const w = Math.floor((job.print?.url ? 1040 - 60 - 160 : 1600) / s);
  let h = Math.floor(((open ? 900 : 760) - 60) / s);
  const top = Math.round(cy - h / 2);
  // the label slot grows upward with its lines (a print's caption wraps at 820 px): the box ends 28 px above it
  if (!open) h = Math.min(h, Math.floor((slotTop(job) - 28 - cy) / s + cy - top));
  return { dur, s, w, h, top, ox: 160, oy: cy, narrow: !!job.print?.url };
}
/** Where the label slot's first line starts (base.css .labels: bottom 120, 36 px lines, a 12 px rule). */
function slotTop(job) {
  const html = labels(job);
  if (!html) return 960;
  const maxw = /with-print/.test(html) ? 820 : 1150;
  const un = (x) => x.replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
  const paras = [...html.matchAll(/<p class="(source|honesty)">(.*?)<\/p>/g)];
  let h = 12 + 8 * Math.max(0, paras.length - 1);
  for (const [, cls, txt] of paras) {
    const w = cls === "honesty" ? labelW(un(txt).toUpperCase(), LABEL) : adv("inter440", un(txt)) * LABEL;
    h += Math.ceil((w * 1.06) / maxw) * (cls === "honesty" ? 28 : 36);
  }
  return 1080 - 120 - h;
}
function cam(B, inner, extra = "") {
  return `<div class="cam" style="--cam-origin:${B.ox}px ${B.oy}px"><div class="rig"><div class="ty" style="--bx-top:${B.top}px;--bx-w:${B.w}px;--bx-h:${B.h}px">` +
    `${extra ? `<div class="ty-push" style="${extra}">${inner}</div>` : inner}</div></div></div>`;
}

/* ---------- motion ---------- */

/**
 * A figure lands on its word (S3), from nothing: no depth blur that could still be read before it
 * is said. Spoken within 0.12 s of the cut it cuts in mid-landing (R1); a figure the voice said
 * before the cut (`known`) and due at the cut stands sharp from the first frame.
 */
function landAt(t, known = false) {
  if (known && t <= 0.4) return { cls: "ty-land set", style: "--at:-1;--d:0.3s" };
  if (t <= 0.12) return { cls: "ty-land cut", style: "--at:0;--d:0.27s" };
  return { cls: "ty-land", style: `--at:${r3(t - 0.12)};--d:0.32s` };
}
/**
 * Words that land one by one on their onsets (blur 8 → 0, 6 px → 0, 0.25 s), from nothing. A word
 * due by 0.4 s is already arriving at the cut, except a figure word, which waits for its onset;
 * `set` stands words due at the cut fully formed (a label, a heading's furniture).
 */
function wordSpans(text, times, o = {}) {
  return words(text).map((w, i) => {
    const t = times[i] ?? times[times.length - 1] ?? 0, fig = isFigWord(w);
    if (o.set && t <= 0.4 && !(fig && t > 0.12 && !o.known)) return `<span class="ty-w set" style="--at:-1">${T(w)}</span>`;
    const cut = t <= (fig ? 0.12 : 0.4);
    return `<span class="ty-w${cut ? " cut" : ""}" style="--at:${r3(cut ? -0.12 : fig ? t - 0.05 : t)}">${T(w)}</span>`;
  }).join(" ");
}
/** A line of words timed from the narration, or from `t0` with a gentle stagger when not spoken. */
const speak = (text, spoken, t0, near) => wordSpans(text, sayTimes(text, spoken, near ?? t0, t0));
/** Elements that enter at a time: the shared rise, but an element due by 0.4 s is already arriving at frame 0. */
const enter = (t) => `--at:${r3(t <= 0.4 ? -0.4 : t)}`;
/** A label's words: formed at the cut when it holds no figure and the plan pins no time, else on its words. */
const labelSpans = (text, spoken, at, kw = null) => (at <= 0.4 && (!hasFig(text) || kw?.(text)) ? wordSpans(text, [-1], { set: true, known: true }) : wordSpans(text, sayFrom(text, spoken, Math.max(0, at))));

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
 * line lands on; `times` lands each number on its own word (a range's second figure later). A date
 * is one figure: month, day and year in Fraunces at full size, landing together on the month.
 */
function figLine(text, px, o = {}) {
  const { times = [0.4], blue = false, quiet = false, time = timeish(text), ls = px >= 200 ? -0.04 : -0.02, unitMin = LABEL, known = false } = o;
  const str = String(text ?? "").trim();
  if (time && MONTH.test(str)) {
    const m = str.match(/^(.*?\d{1,2},?)(\s+)(\d{4})$/), w = serifW(str, px) - 0.012 * px * str.length;
    const part = (s, t) => { const { cls, style } = landAt(t, known); return `<span class="ty-fd ty-date ${cls}" style="${style};--ls:-0.012em">${T(s)}</span>`; };
    if (!m) return { html: part(str, times[0]), w };
    return { html: `${part(m[1], times[0])}<span class="ty-sp"></span>${part(m[3], known && times[0] <= 0.4 ? times[0] : Math.max(times[0], times[times.length - 1]))}`, w };
  }
  const toks = tokens(str);
  const up = Math.max(0.3 * px, unitMin), nums = toks.filter((t) => t.n);
  let w = 0, html = "", k = 0;
  toks.forEach((t) => {
    if (t.n) {
      const at = times[Math.min(k, times.length - 1)];
      const { cls, style } = landAt(at, known);
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
    const st = known && at <= 0.4 ? `class="ty-w set" style="--at:-1"` : at <= 0.12 ? `class="ty-w cut" style="--at:-0.12"` : `class="ty-w" style="--at:${r3(at)}"`;
    html += `<span class="ty-u${sl ? " sl" : ""}${sr ? " sr" : ""}" style="font-size:${px0(up)}"><span ${st}>${T(txt)}</span></span>`;
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
const bloom = (w, h, t, blue) => `<i class="ty-bloom${blue ? " blue" : ""}" style="width:${px0(w)};height:${px0(h)};--at:${r3(Math.max(-1, t))}"></i>`;
/** A re-read beat on a figure: its glow swells and settles (no fill, so beats stack). */
const pulses = (bs, k, cls = "pulse") => bs.filter((b) => b.k === k).map((b) => `<i class="ty-${cls}" style="--at:${r3(b.t)}"></i>`).join("");

/* ---------- number ---------- */

/**
 * One figure, the hero. Without a companion print it is centred on the frame's optical centre and
 * fills about 80% of the grid (up to 340 px); with one it keeps to the left box. It lands on its own
 * number word. Its context line is set at body size on its own words: above the figure when the
 * voice says it first, under it when after (or, unsaid, just after the figure). While a late
 * figure waits, its rule is already drawing: the frame is never an empty desk at the cut.
 */
export function number(job) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], known = knownOf(job), narrow = B.narrow;
  const value = String(p.value ?? job.reveals?.[0]?.value ?? "").trim();
  const on = job.on ?? job.reveals?.[0]?.t ?? 0.4;
  const time = timeish(value), money = isMoney(value), isK = known(value);
  let toks = tokens(value), tail = "";
  const last = toks[toks.length - 1];
  if (toks.length > 1 && last.w && words(last.w).length > 3) { tail = last.w.trim(); toks = toks.slice(0, -1); }
  let fig = toks.map((t) => t.n ?? t.w).join("").trim();
  const t0 = isK && on <= 0.4 ? on : figOnset(fig, spoken, on);
  const timesOf = (s) => tokens(s).filter((t) => t.n).map((t, i) => (i === 0 ? t0 : Math.max(t0 + 0.2, spokenAt(t.n, spoken.filter((x) => x.t > t0), t0 + 0.6))));
  const maxw = narrow ? B.w - 20 : Math.round(B.w * 0.84), top = narrow ? 300 : 340;
  let f, figHTML, fw, fpx;
  if (/\d/.test(fig)) {
    const o = { times: timesOf(fig), blue: money, time, known: isK };
    f = fitFig(fig, maxw, top, 200, o);
    const lastW = toks[toks.length - 1]?.w;
    if ((f.w > maxw || (f.px < 280 && lastW && words(lastW).length >= 2)) && toks.length > 1 && lastW && !MONTH.test(fig)) {
      tail = `${toks[toks.length - 1].w.trim()}${tail ? ` ${tail}` : ""}`;
      fig = toks.slice(0, -1).map((t) => t.n ?? t.w).join("").trim();
      f = fitFig(fig, maxw, top, 160, { ...o, times: timesOf(fig) });
    }
    if (f.w > maxw) f = fitFig(fig, maxw, f.px, 96, { ...o, times: timesOf(fig) });
    fpx = f.px; fw = Math.min(maxw, f.w); figHTML = f.html;
  } else {
    // a value in words ("six years") is the hero itself, in display Fraunces, landing whole on its words
    const ws = words(fig);
    let lines = [fig];
    for (fpx = narrow ? 200 : 240; fpx > 96; fpx -= 8) {
      lines = [1, 2].map((k) => breakK(ws, k, (s) => serifW(s, fpx))).find((ls) => Math.max(...ls.map((s) => serifW(s, fpx))) <= maxw);
      if (lines) break;
    }
    lines = lines || [fig];
    fw = Math.min(maxw, Math.max(...lines.map((s) => serifW(s, fpx))));
    const { cls, style } = landAt(t0, isK);
    figHTML = `<span class="ty-fd ty-words ${cls}" style="${style};--ls:-0.02em">${lines.map((l) => `<span class="ty-vl">${T(l)}</span>`).join("")}</span>`;
  }
  // the context line on its own words, never before them
  const subTimes = p.sub ? phraseTimes(p.sub, spoken, null) : null;
  const subFirst = !!subTimes && subTimes[0] < t0 - 0.25;
  const subT = subTimes ? subTimes.map((t) => Math.max(0, t)) : words(p.sub || "").map((_, i) => Math.max(t0, 0.4) + 0.55 + i * 0.07);
  const subPx = narrow ? 44 : 52;
  const sub = p.sub ? `<p class="ty-n-sub${subFirst ? " above" : ""}" style="font-size:${subPx}px">${wordSpans(p.sub, subT)}</p>` : "";
  const tailT = tail ? phraseAt(tail, spoken.filter((x) => x.t >= t0), t0 + 0.5) ?? t0 + 0.4 : 0;
  const bs = beats([t0, tail ? tailT : null, subTimes ? subT[subT.length - 1] : null], spoken, B.dur, 1);
  const estAt = spoken.find((x) => /^estimat/.test(norm(x.w)))?.t ?? t0 + 0.8;
  const est = p.estimate ? `<p class="ty-est" style="${enter(estAt)}">Estimate</p>` : "";
  // a late figure's rule is drawing at the cut, its bright point running ahead of the figure
  const ruleAt = t0 > 0.4 ? -0.8 : t0 + 0.1;
  const lineH = /\d/.test(fig) ? fpx * 0.84 : fpx * 1.0;
  return cam(B, `<div class="ty-box ty-n${narrow ? "" : " centre"}">${subFirst ? sub : ""}` +
    `<div class="ty-n-fig${time ? " time" : ""}" style="font-size:${px0(fpx)};line-height:${r3(lineH / fpx)}">${bloom(fw * 1.4, fpx * 1.9, t0, money)}${figHTML}${pulses(bs, 0, money ? "pulse-blue" : "pulse")}</div>` +
    `<div class="ty-rule" style="--fw:${px0(fw)};width:${px0(narrow ? B.w : fw + 80)};margin-top:${px0(fpx * 0.1 + 22)};--at:${r3(ruleAt)}"><i></i>${bs.map((b) => `<b style="--at:${r3(b.t)}"></b>`).join("")}</div>` +
    (tail ? `<p class="ty-n-tail">${speak(tail, spoken.filter((x) => x.t >= t0), tailT)}</p>` : "") + (subFirst ? "" : sub) + est + `</div>`);
}

/* ---------- pair ---------- */

export function pair(job) {
  const p = job.params || {}, L = p.left || {}, R = p.right || {};
  const kl = kindOf(L.value), kr = kindOf(R.value);
  // a price and the moment it is from are not a comparison: stacked, the money the hero
  if (p.layout === "stacked" || !R.value || ((kl === "money") !== (kr === "money") && (kl === "time" || kr === "time"))) return hook(job, stage(job));
  const B = stage(job, false, p.push_at != null ? 1.05 : 1), spoken = job.words || [], known = knownOf(job);
  const lAt = L.at ?? 0.3, rAt = Math.max(R.at ?? lAt + 1.2, lAt + 0.4);
  const same = kl === kr && kl !== "time";
  const blueR = kr === "money", blueL = kl === "money" && !blueR;
  const kL = known(L.value), kR = known(R.value);
  const unitsOf = (v) => { const t = tokens(v), z = t[t.length - 1]; return z?.w && /^\s/.test(z.w) && t.length > 1 && !MONTH.test(v) ? z.w.trim() : ""; };
  const strip = (v, u) => (u ? String(v).slice(0, String(v).lastIndexOf(u)).trimEnd() : String(v));
  const lineOf = (c, u, px, t, blue, quiet, k) => figLine(strip(c.value, u), px, { times: figTimes(strip(c.value, u), spoken, t), blue, quiet, known: k });
  // both figures as large as the box allows, with at least 240 px of line between them; long
  // trailing words set below their figure when inline they would shrink the pair
  const fit = (below) => {
    const lu = below ? unitsOf(L.value) : "", ru = below ? unitsOf(R.value) : "";
    let px = 260, lf, rf;
    for (;; px -= 4) {
      lf = lineOf(L, lu, px, lAt, blueL, kl === "money" && !blueL, kL);
      rf = lineOf(R, ru, px, rAt, blueR, false, kR);
      if (lf.w + rf.w + 240 <= B.w || px <= 120) break;
    }
    return { px, lf, rf, lu, ru, ok: lf.w + rf.w + 240 <= B.w };
  };
  let F = fit(false);
  if (F.px < 190) { const G = fit(true); if ((G.lu || G.ru) && G.px > F.px + 24) F = G; }
  const gapT = p.gap ? p.gap_at ?? saidAt(p.gap, spoken, rAt + 1.2) ?? rAt + 0.7 : 0;
  // a label stands formed at the cut (the plan's `label_at` lands it on its words; a figure in it waits)
  const labT = (c, t) => c.label_at ?? (hasFig(c.label) ? saidAt(c.label, spoken, t) ?? t : -0.4);
  const bs = beats([lAt, rAt, p.gap ? gapT : null, L.label_at, R.label_at], spoken, B.dur, 1);
  const q = p.question ? `<p class="ty-head">${wordSpans(p.question, p.question_at ? headTimes(p.question, spoken, p.question_at[0] ?? 0) : headSay(p.question, spoken))}</p>` : "";
  const push = p.push_at != null ? `--push-to:1.05;--push-at:${r3(p.push_at)};--push-d:${r3(Math.max(1, B.dur - p.push_at))}s;--push-origin:160px ${B.oy}px` : "";
  if (!F.ok) {
    // too wide side by side (a companion print's narrow box): one over the other, a short drop between
    const qH = headH(p.question, B.w), gH = p.gap ? 120 : 0;
    let px = Math.floor(clamp((B.h - qH - gH - 2 * 64 - 96 - 24) / 1.8, 64, 220)), lf, rf;
    for (;; px -= 4) {
      lf = lineOf(L, "", px, lAt, blueL, kl === "money" && !blueL, kL); rf = lineOf(R, "", px, rAt, blueR, false, kR);
      if (Math.max(lf.w, rf.w) <= B.w - 10 || px <= 64) break;
    }
    const drawFrom = Math.max(lAt + 0.4, rAt - 0.6);
    const col = (c, t, f, side, blue) => `<div class="ty-p-col ${side} v" style="--next:${r3(rAt)}"><p class="ty-label">${labelSpans(c.label || "", spoken, labT(c, t))}</p>` +
      `<div class="ty-p-fig" style="font-size:${px0(px)}">${bloom(f.w * 1.4, px * 1.8, t, blue)}${f.html}${side === "r" ? pulses(bs, 0, blue ? "pulse-blue" : "pulse") : ""}</div></div>`;
    const drop = `<div class="ty-p-drop${same ? " arrow" : ""}" style="--at:${r3(drawFrom)};--d:${r3(Math.max(0.3, rAt - drawFrom))}s"><i></i>${same ? "<b></b>" : ""}</div>`;
    const g = p.gap ? `<p class="ty-p-gap">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : "";
    return cam(B, `<div class="ty-box ty-p v">${q}${col(L, lAt, lf, "l", blueL)}${drop}${col(R, rAt, rf, "r", blueR)}${g}</div>`, push);
  }
  const { px, lf, rf } = F;
  const linkW = B.w - lf.w - rf.w, d = 0.7, drawFrom = Math.max(lAt + 0.4, rAt - d - 0.05);
  const gapIn = p.gap && serifW(p.gap, BODY, true) <= linkW - 90;
  const col = (c, t, f, unit, side, blue, k) => `<div class="ty-p-col ${side}" style="--next:${r3(rAt)}">` +
    `<p class="ty-label">${labelSpans(c.label || "", spoken, labT(c, t))}</p>` +
    `<div class="ty-p-fig" style="font-size:${px0(px)}">${bloom(f.w * 1.4, px * 1.8, t, blue)}${f.html}` +
    `${unit ? `<span class="ty-p-unit" style="font-size:${px0(Math.max(LABEL, px * 0.3))}">${k && t <= 0.4 ? wordSpans(unit, [-1], { set: true }) : wordSpans(unit, sayFrom(unit, spoken, t + 0.1))}</span>` : ""}` +
    `${side === "r" ? pulses(bs, 0, blue ? "pulse-blue" : "pulse") : ""}</div></div>`;
  const link = `<div class="ty-p-link${same ? " arrow" : ""}" style="--lift:${px0(px * 0.42)};--at:${r3(drawFrom)};--d:${r3(rAt - drawFrom)}s">` +
    `<i class="ty-p-line"></i><i class="ty-p-head"></i>${same ? "<b></b>" : "<u></u>"}${bs.map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}` +
    `${gapIn ? `<p class="ty-p-gap in">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : ""}</div>`;
  const g = p.gap && !gapIn ? `<p class="ty-p-gap">${wordSpans(p.gap, sayFrom(p.gap, spoken, gapT))}</p>` : "";
  return cam(B, `<div class="ty-box ty-p">${q}<div class="ty-p-row${F.lu || F.ru ? " units" : ""}">` +
    `${col(L, lAt, lf, F.lu, "l", blueL, kL)}${link}${col(R, rAt, rf, F.ru, "r", blueR, kR)}</div>${g}</div>`, push);
}

/** The hook (a01): the money lands at frame 0 as the hero; the moment it is from under it, small; then the gap's words. */
function hook(job, B) {
  const p = job.params || {}, spoken = job.words || [], L = p.left || {}, R = p.right || {}, known = knownOf(job);
  const [M, W] = isMoney(L.value) ? [L, R] : isMoney(R.value) ? [R, L] : [L, R];
  const mAt = M.at ?? 0.3, wAt = W.at ?? mAt + 1;
  const when = String(W.value ?? "").trim();
  // the hero as large as the box allows with its lines under it (the shared push is the camera)
  const px = clamp(Math.floor((B.h - (p.gap ? 150 : 40)) / (0.82 + (when ? 0.4 * 1.3 : 0) + 0.17)), 220, 360);
  const f = figLine(M.value, px, { times: figTimes(M.value, spoken, mAt), blue: isMoney(M.value), ls: -0.04, known: known(M.value) });
  const wt = when ? sayFrom(when, spoken, wAt) : [];
  const gapT = p.gap ? p.gap_at ?? saidAt(p.gap, spoken, wAt + 1) ?? wAt + 1 : 0;
  const bs = beats([mAt, ...wt, ...(p.gap ? sayFrom(p.gap, spoken, gapT) : [])], spoken, B.dur, 1);
  return cam(B, `<div class="ty-box ty-hook${B.narrow ? "" : " centre"}"><div class="ty-p-fig hero" style="font-size:${px}px">${bloom(f.w * 1.3, px * 1.6, mAt, isMoney(M.value))}${f.html}${pulses(bs, 0, "pulse-blue")}</div>` +
    (when ? `<p class="ty-hook-when" style="font-size:${px0(px * 0.4)}">${words(when).map((w, i) => `<span class="${timeish(w) ? "ty-fd" : "ty-hw"} ty-w" style="--at:${r3(wt[i])}">${T(w)}</span>`).join(" ")}</p>` : "") +
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

/**
 * A thesis line: the act's sentence as display type across the full measure, set low on the
 * frame (the lower third), every word on its onset. A short thesis (six words or fewer) sets at
 * 180–200 px on two balanced lines; longer ones at up to 144 px on up to three. `params.key`
 * names the words that carry it: those in full ivory, the rest at 70%. The last word lands with
 * the bloom a figure throws.
 */
export function kinetic(job) {
  const B = stage(job, true), p = job.params || {}, spoken = job.words || [];
  let lines = (p.lines?.length ? p.lines : [job.says]).map((l) => String(l ?? "").trim()).filter(Boolean);
  // lines the plan split only for balance are one statement: set it as one, broken here
  const statements = lines.length > 1 && lines.slice(0, -1).every((l) => /[.!?:]$/.test(l));
  if (!statements) lines = [lines.join(" ")];
  const italic = (i) => i > 0;
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
  const maxPx = n <= 6 ? 200 : n <= 14 ? 144 : n <= 25 ? 96 : 72, minLines = n <= 6 && n >= 3 ? 2 : 1;
  let best = null;
  for (let px = maxPx; px >= 60 && !best; px -= 4) {
    const set = lines.map((l, i) => {
      const ws = words(l), mw = (s) => serifW(s, px, italic(i));
      for (let kk = i === 0 ? minLines : 1; kk <= 3; kk++) { const ls = breakK(ws, kk, mw); if (Math.max(...ls.map(mw)) <= maxw) return ls; }
      return null;
    });
    if (set.some((s) => !s)) continue;
    const vl = set.reduce((a, s) => a + s.length, 0);
    if (vl * px * 1.06 + (lines.length - 1) * px * 0.3 <= B.h * 0.86) best = { px, set };
  }
  if (!best) best = { px: 60, set: lines.map((l) => [l]) };
  const { px, set } = best;
  const keys = (p.key || []).map((kw) => words(kw).map(norm));
  const flat = lines.flatMap((l) => words(l)), bright = flat.map(() => !keys.length);
  keys.forEach((kw) => { for (let i = 0; i + kw.length <= flat.length; i++) if (kw.every((x, j) => norm(flat[i + j]) === x)) kw.forEach((_, j) => { bright[i + j] = true; }); });
  let g = 0;
  const lastAll = times[times.length - 1][times[times.length - 1].length - 1];
  const html = set.map((vls, i) => {
    let j = 0;
    const next = times[i + 1]?.[0];
    const dim = next !== undefined && italic(i + 1) ? `;--dim:${r3(next)}` : "";
    const body = vls.map((v) => {
      const ws = words(v), ts = times[i].slice(j, j + ws.length); j += ws.length;
      return `<span class="ty-vl">${ws.map((w, m) => {
        const t = ts[m] ?? 0, cut = t <= (isFigWord(w) ? 0.12 : 0.4), isLast = i === set.length - 1 && j === times[i].length && m === ws.length - 1;
        const cls = `ty-w${cut ? " cut" : ""}${bright[g++] ? "" : " soft"}${isLast ? " last" : ""}`;
        return `<span class="${cls}" style="--at:${r3(cut ? -0.12 : t)}">${isLast ? bloom(serifW(w, px) * 2.2, px * 1.8, lastAll, false) : ""}${T(w)}</span>`;
      }).join(" ")}</span>`;
    }).join("");
    return `<p class="ty-k-line${italic(i) ? " it" : ""}${dim ? " dims" : ""}" style="${dim.slice(1)}">${body}</p>`;
  }).join("");
  return cam(B, `<div class="ty-box ty-k" style="font-size:${px}px;padding-bottom:${px0(B.h * 0.12)}">${html}</div>`);
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

/**
 * A sum worked as the voice says it. The skeleton is there at the cut, sharp: the operators at 60%
 * and, for every term not yet said, a graphite blank of its width (never the term itself under a
 * blur). Each term lands on its words and its blank lifts. Three terms or fewer sit on one row as
 * large as fills the grid (to 150 px); four or more stack as a ledger whose result row is the
 * largest. The block is centred in the box, its caption on the same left edge under it.
 */
export function formula(job) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], narrow = B.narrow;
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
  const resK = (i) => (isRes(i) && n >= 3 && !lone(i) ? 1.18 : 1);   // the result row is the largest
  const tw = (i, px) => (lone(i) ? serifW(String(terms[i].text), px * 1.7, true) : termW(terms[i].text, px * resK(i), isRes(i)));
  const ow = (o, px) => (SYMBOL[o] ? px * 0.62 : serifW(o, px * 0.62, true));
  const gapOf = (px) => px * 0.32, maxw = B.w - 20;
  const rowW = (px) => terms.reduce((a, _, i) => a + tw(i, px) + (i < n - 1 ? ow(ops[i] ?? "+", px) + 2 * gapOf(px) : 0), 0);
  const restW = (px) => Math.max(...terms.slice(1).map((_, j) => ow(ops[j] ?? "+", px) + 2 * gapOf(px) + tw(j + 1, px)));
  const alignW = (px) => tw(0, px) + restW(px);
  const gutOf = (px) => Math.max(px * 1.2, ...ops.map((o) => ow(o, px) + gapOf(px)));
  const ledgerW = (px) => gutOf(px) + Math.max(...terms.map((_, i) => tw(i, px)));
  const capPx = narrow ? 40 : 44;
  const capH = (px, w) => (p.caption ? 0.6 * px + Math.ceil(serifW(p.caption, capPx, true) / Math.max(300, w)) * capPx * 1.25 : 0);
  const rows = { row: 1, align: n - 1, ledger: n };
  const W = { row: rowW, align: alignW, ledger: ledgerW };
  const fits = (lay, px) => {
    const w = W[lay](px), hgt = rows[lay] * px * 1.44 + (lay !== "row" && result ? px * 0.5 : 0) + (lone(n - 1) && lay === "row" ? px * 0.5 : 0);
    return w <= maxw && hgt + capH(px, Math.max(w, maxw * 0.6)) <= B.h;
  };
  let layout = null, px;
  const capRow = n === 1 ? (narrow ? 180 : 220) : narrow ? 120 : n <= 3 ? 150 : 132;
  if (n <= 4) for (px = capRow; px >= (n <= 3 ? 84 : 96) && !layout; px -= 4) if (fits("row", px)) layout = "row";
  if (!layout && n > 1) for (px = narrow ? 108 : 132; px >= 56 && !layout; px -= 4) if (fits("align", px)) layout = "align";
  if (!layout) for (px = narrow ? 108 : 132; px >= 44 && !layout; px -= 4) if (fits("ledger", px)) layout = "ledger";
  if (!layout) { layout = n > 1 ? "align" : "row"; px = 44; } else px += 4;
  const gp = gapOf(px);
  // the skeleton: each operator formed at the cut at 60%, lit on its word
  const opHTML = (i) => {
    const o = ops[i] ?? "+", st = `--at:-0.6;--lit:${r3(opAt(i))}`;
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
          const t = tt[i][j], fig = isFigWord(wd), cut = t <= (fig ? 0.12 : 0.4);
          const inner = /^[×÷=+−→]$/.test(wd) ? `<span class="ty-f-in">${esc(wd)}</span>` : /\d/.test(wd) && !isYear(wd) ? `<span class="ty-fn${isMoney(wd) ? " money" : ""}">${esc(wd)}</span>` : T(wd);
          return `<span class="ty-w${cut ? " cut" : ""}" style="--at:${r3(cut ? -0.12 : fig ? t - 0.05 : t)}">${inner}</span>`;
        }).join(" ");
    const big = resK(i) > 1 ? `font-size:${resK(i)}em;` : "";
    return `<span class="ty-f-term${isRes(i) ? " res" : ""}${lone(i) ? " lone" : ""}" style="${big}--at:${r3(t0)};--slot:${r3(-0.6 + i * 0.05)}">` +
      `${isRes(i) ? bloom(tw(i, px) * 1.4, px * 2, pencilQ ? p.pencil_at : t0, false) : ""}<span class="ty-f-text">${body}</span>${pencilQ ? "" : `<i class="ty-f-slot"></i>`}</span>`;
  };
  let body, blockW;
  if (layout === "row") {
    body = `<div class="ty-f-row">${terms.map((_, i) => term(i) + (i < n - 1 ? opHTML(i) : "")).join("")}</div>`;
    blockW = rowW(px);
  } else {
    const col = layout === "align" ? Math.round(tw(0, px) + 6) : 0;
    const gut = gutOf(px), sumW = restW(px) + (layout === "ledger" ? gut - 2 * gp : 0);
    const lhs = (inner) => (layout === "align" ? `<span class="ty-f-lhs" style="width:${col}px">${inner}</span>` : `<span class="ty-f-gut" style="width:${px0(gut)}">${inner}</span>`);
    const rowsH = layout === "align" ? [`<div class="ty-f-line">${lhs(term(0))}${opHTML(0)}${term(1)}</div>`] : [`<div class="ty-f-line">${lhs("")}${term(0)}</div>`];
    for (let i = layout === "align" ? 1 : 0; i < n - 1; i++) {
      const sum = isRes(i + 1) && n > 2;
      rowsH.push(`<div class="ty-f-line${sum ? " sum" : ""}">${lhs(layout === "ledger" ? opHTML(i) : "")}${layout === "align" ? opHTML(i) : ""}${term(i + 1)}` +
        `${sum ? `<span class="ty-f-sum" style="--at:${r3(sumT)};left:${px0(col)};width:${px0(sumW)}">${pencil(sumW)}</span>` : ""}</div>`);
    }
    body = rowsH.join("");
    blockW = W[layout](px);
  }
  const lastT = Math.max(...tt.map((x) => x[x.length - 1]));
  const capT = p.caption ? p.caption_at ?? Math.max(lastT + 0.6, saidAt(p.caption, spoken, lastT + 1) ?? lastT + 0.8) : 0;
  const cap = p.caption ? `<p class="ty-f-cap" style="margin-top:${px0(0.6 * px)};font-size:${capPx}px;max-width:${px0(Math.max(blockW, Math.min(maxw, 1100)))}">${wordSpans(p.caption, sayFrom(p.caption, spoken, capT))}</p>` : "";
  const centre = !narrow && blockW < maxw * 0.9;
  return cam(B, `<div class="ty-box ty-f-box${centre ? " centre" : ""}"><div class="ty-f ${layout}" style="font-size:${px}px;--gap:${px0(gp)}">${body}${cap}</div></div>`);
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
  const form = FORMS[p.layout] || timelineForm(evs, job);
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
const head = (p, spoken) => (p.heading ? `<p class="ty-head">${wordSpans(p.heading, p.heading_at != null ? headTimes(p.heading, spoken, p.heading_at) : headSay(p.heading, spoken))}</p>` : "");
/** The event the line lands on (`on`) for a step: a price that is the difference of two neighbours. */
function stepKey(evs, job) {
  const fig = (e) => (figureLed(e.label) ? e.label : figureLed(e.date) ? e.date : null);
  const v = evs.map((e) => (fig(e) && isMoney(fig(e)) ? amount(fig(e)) : NaN));
  const cands = evs.map((_, i) => i).filter((i) => Number.isFinite(v[i]) && evs.some((_, j) => j + 1 < evs.length && j !== i && j + 1 !== i && Math.abs(v[j + 1] - v[j] - v[i]) < 0.006));
  if (!cands.length) return -1;
  if (job.on == null) return cands[cands.length - 1];
  return cands.reduce((b, i) => (Math.abs((evs[i].at ?? 0) - job.on) < Math.abs((evs[b].at ?? 0) - job.on) ? i : b));
}

const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];
/** A date as days (a bare year at its middle), or NaN: what a line's positions are computed from. */
function dayOf(s) {
  const t = String(s ?? "").trim().replace(/^(?:c\.|ca\.|circa|about|in)\s*/i, "");
  let m = t.match(/^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$/);
  if (m && MONTHS.includes(m[1].toLowerCase())) return Date.UTC(+m[3], MONTHS.indexOf(m[1].toLowerCase()), +m[2]) / 864e5;
  m = t.match(/^([A-Za-z]+)\s+(\d{4})$/);
  if (m && MONTHS.includes(m[1].toLowerCase())) return Date.UTC(+m[2], MONTHS.indexOf(m[1].toLowerCase()), 15) / 864e5;
  m = t.match(/^(\d{4})$/);
  if (m && isYear(m[1])) return Date.UTC(+m[1], 6, 1) / 864e5;
  return NaN;
}

/**
 * Real dates: a line drawn across the dark, a tick landing on each spoken date at its true position
 * (computed from the dates themselves; a plan's `pos` overrides). The line stays still (the shared
 * camera pushes); where labels would collide, each takes the first free tier, alternately above and
 * below the line, on a stem from its tick, at least 60 px from any label on its tier. The type
 * grows with the free height. `params.bracket` {from, to, at, label} draws a span under the line
 * between two events, its label on its words.
 */
function line(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], n = evs.length, W = B.w, known = knownOf(job);
  const days = evs.map((e) => dayOf(e.date)), d0 = Math.min(...days), d1 = Math.max(...days);
  const scaled = n > 1 && days.every(Number.isFinite) && d1 > d0;
  const big0 = n === 1 ? 1.5 : n === 2 ? 1.3 : n === 3 ? 1.15 : 1;
  // an event the plan pins at the cut is set from the cut; a date the narration does not say is the setting
  const ev = evs.map((e, i) => {
    const pinned = e.at != null && e.at <= 0.4;
    const said = pinned ? null : saidAt(e.date, spoken, e.at);
    const t = pinned ? e.at : said ?? (i === 0 ? 0 : e.at ?? 0.5 + i * 0.9);
    const pos = e.pos ?? (scaled ? 0.06 + (0.88 * (days[i] - d0)) / (d1 - d0) : n === 1 ? 0.06 : 0.06 + (0.88 * i) / (n - 1));
    return { e, i, pos, t, said, k: known(e.date) };
  });
  ev.forEach((v, i) => { v.land = Math.max(v.t, i ? ev[i - 1].land + 0.35 : 0); });
  const bk = p.bracket && n > 1 ? p.bracket : null;
  const room = B.h - headH(p.heading, W);
  let levels, blockH, pitch, stem0, above, below, brkH = 0;
  for (const fit of [1.45, 1.3, 1.15, 1, 0.9, 0.8, 0.7]) {
    const big = big0 * fit;
    ev.forEach((v) => { v.tier = null; });
    ev.forEach((v) => {
      const date = String(v.e.date ?? ""), lab = String(v.e.label ?? ""), labFig = figureLed(lab);
      v.dpx = Math.round((timeish(date) && date.length <= 18 ? 64 : 52) * big);
      v.lpx = Math.round(BODY * Math.min(big, 1.25));
      const lt = v.e.name_at ?? (labFig ? spokenAt(lab, spoken, v.land) : saidAfter(lab, spoken, v.land) ?? v.land + 0.15);
      v.lt = Math.max(v.land, lt);
      const dk = v.k && v.land <= 0.4;
      const yr = (date.match(/\b(\d{4})$/) || [])[1], yT = yr && MONTH.test(date) ? Math.max(v.land, (spoken.filter((x) => x.t >= v.land - 0.1 && x.t <= v.land + 2.5 && norm(x.w) === yr)[0]?.t) ?? v.land) : v.land;
      v.dateHTML = `<p class="ty-t-date" style="font-size:${v.dpx}px">${timeish(date) ? figLine(date, v.dpx, { times: [v.land, yT], known: dk, time: true }).html : wordSpans(date, v.said != null ? sayTimes(date, spoken, v.land, v.land) : words(date).map(() => v.land))}</p>`;
      v.labelHTML = labFig ? `<div class="ty-t-fig" style="font-size:${Math.round(76 * big)}px">${figLine(lab, Math.round(76 * big), { times: [v.lt], unitMin: LABEL, known: known(lab) }).html}</div>`
        : `<p class="ty-t-label" style="font-size:${v.lpx}px">${v.lt <= 0.4 ? wordSpans(lab, [-1], { set: true }) : wordSpans(lab, sayFrom(lab, spoken, v.lt))}</p>`;
      v.bw = Math.max(serifW(date, v.dpx), labFig ? figLine(lab, Math.round(76 * big)).w : labelW(lab, v.lpx, 0)) + 40;
      v.bh = v.dpx * 1.1 + (labFig ? 76 * big : v.lpx * 1.2) + 12;
      v.x = Math.round(v.pos * W);
    });
    // tiers: up 0, down 0, up 1, down 1 ... placed from the right, each on the first tier where its
    // label keeps 60 px from every other label, its stem crosses no nearer label, and no farther stem crosses it
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
          if (ul === lvl) return v.r + 60 <= u.l || v.l >= u.r + 60;
          if (ul < lvl) return !(v.x >= u.l - 12 && v.x <= u.r + 12);   // my stem through its label
          return !(u.x >= v.l - 12 && u.x <= v.r + 12);                 // its stem through my label
        });
        if (ok) { v.tier = k; placed.push(v); break; }
      }
      if (v.tier == null) { v.tier = 0; placed.push(v); }
    });
    levels = Math.max(...ev.map((v) => Math.floor(v.tier / 2))) + 1; blockH = Math.max(...ev.map((v) => v.bh));
    pitch = blockH + 30; stem0 = Math.round(44 * Math.min(1.3, big));
    const ups = levels, downs = ev.some((v) => v.tier % 2) ? Math.max(...ev.filter((v) => v.tier % 2).map((v) => Math.floor(v.tier / 2))) + 1 : 0;
    above = stem0 + (ups - 1) * pitch + blockH + 8; below = downs ? stem0 + (downs - 1) * pitch + blockH + 8 : 0;
    brkH = bk ? 40 + Math.round(BODY * Math.min(big, 1.2) * 1.3) + 14 : 0;
    if (above + below + brkH <= room && ev.every((v) => v.bw <= W)) break;
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
  // the span the narration names ("six years"), drawn under the line between two of its events
  let brk = "";
  if (bk) {
    const find = (r) => (typeof r === "number" ? ev[r] : ev.find((v) => v.e.date === r || v.e.label === r));
    const a = find(bk.from ?? 0), b = find(bk.to ?? n - 1);
    if (a && b && b.x > a.x) {
      const bt = bk.at ?? saidAt(bk.label || "", spoken, b.land) ?? b.land + 0.5;
      const lt = bk.label_at ?? saidAt(bk.label || "", spoken, bt) ?? bt + 0.2;
      brk = `<div class="ty-t-brk" style="left:${a.x}px;width:${b.x - a.x}px;top:${Math.round(below + 34)}px;--at:${r3(bt)}"><i></i>` +
        `${bk.label ? `<p class="ty-t-brk-l" style="font-size:${Math.round(BODY * 1.15)}px">${wordSpans(bk.label, sayFrom(bk.label, spoken, Math.max(lt, bt + 0.2)))}</p>` : ""}</div>`;
    }
  }
  return cam(B, `<div class="ty-box ty-t">${head(p, spoken)}<div class="ty-t-area" style="height:${Math.round(above + below + brkH)}px">` +
    `<div class="ty-t-track" style="top:${Math.round(above)}px;width:${lineEnd}px"><i class="ty-t-ghost" style="width:${lineEnd}px"></i>${lineHTML}${back}${events}${brk}</div></div></div>`);
}

/**
 * Comparable amounts (one unit): bars to scale from one axis. The axis and every row's name stand
 * at the cut over a short stub of light (a name holding a figure waits for its words); each bar
 * grows to its value on its word. The value sits left of the axis on the bar's centre line, the
 * name over the bar, so a name never reads as the label of the value above it. The rows spread
 * over the box's height (pitch to 250 px, bars at least 24 px thick). `reveal_scale_at` pulls back
 * to the whole.
 */
function bars(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], known = knownOf(job), narrow = B.narrow;
  const rows = evs.map((e) => ({ e, ...sides(e, spoken) })), kw = knownWords(job);
  rows.forEach((r) => { r.v = amount(r.fig); r.k = known(r.fig); r.set = r.k && r.figT <= 0.4; });
  const n = rows.length, max = Math.max(...rows.map((r) => r.v));
  const keyI = job.on == null ? -1 : rows.findIndex((r) => Math.abs(r.figT - job.on) < 0.3);
  const hH = headH(p.heading, B.w), avail = B.h - hH;
  const pitch = Math.floor(clamp(avail / n, 92, narrow ? 210 : 250));
  const thick = Math.round(clamp(pitch * 0.25, 24, 56));
  let namePx = pitch >= 140 ? 40 : 34;
  const blueOf = (i) => isMoney(rows[i].fig) && (keyI >= 0 ? i === keyI : true);
  let valPx = Math.round(clamp(pitch * 0.48, 52, narrow ? 84 : 104)), fl;
  const lines = (px) => rows.map((r, i) => figLine(r.fig, px, { times: figTimes(r.fig, spoken, r.figT), blue: blueOf(i), unitMin: LABEL, known: r.k }));
  for (fl = lines(valPx); Math.max(...fl.map((f) => f.w)) > B.w * 0.46 && valPx > 44; fl = lines(valPx)) valPx -= 4;
  const axis = Math.round(Math.max(...fl.map((f) => f.w)) + 40);
  const barMax = Math.max(160, B.w - axis - 24);
  // a name keeps to the room right of the axis: smaller, then on two lines
  const nameRoom = B.w - axis - 20, widest = Math.max(...rows.map((r) => serifW(r.name || "", 1)));
  namePx = Math.round(clamp(nameRoom / widest, 28, namePx));
  const nameLines = widest * namePx > nameRoom ? 2 : 1;
  const nameH = Math.round(namePx * 1.18 * nameLines), barTop = nameH + 12;
  // before the reveal the bars are drawn zoomed in, together: the largest runs out of the frame
  const vs = rows.map((r) => r.v).sort((a, b) => b - a);
  const k = p.reveal_scale_at != null && vs.length > 1 ? clamp(0.45 / (vs[1] / vs[0]), 1, 8) : 1;
  const bs = beats([...rows.flatMap((r) => [r.nameT, r.figT]), p.reveal_scale_at], spoken, B.dur, rows.length);
  const html = rows.map((r, i) => {
    const blue = blueOf(i);
    const until = keyI >= 0 ? 999 : rows[i + 1]?.figT ?? 999;
    const len = Math.max(6, (r.v / max) * barMax), stub = Math.min(len, 18);
    const nT = r.e.name_at ?? (hasFig(r.name || "") && !kw(r.name || "") ? r.nameT : -0.4);
    const name = r.set && nT <= 0.4 ? wordSpans(r.name || "", [-1], { set: true, known: true }) : labelSpans(r.name || "", spoken, nT, kw);
    return `<div class="ty-b-row" style="height:${pitch}px">` +
      `<div class="ty-b-val${blue && keyI < 0 ? " fades" : ""}" style="width:${axis - 40}px;top:${Math.round(barTop + thick / 2)}px;font-size:${valPx}px;--until:${r3(until)}">${fl[i].html}</div>` +
      `<p class="ty-b-name${nameLines > 1 ? " wrap" : ""}" style="left:${axis + 16}px;font-size:${namePx}px;max-width:${nameRoom}px">${name}</p>` +
      `<div class="ty-b-bar" style="left:${axis + 2}px;top:${barTop}px;width:${r3(len)}px;height:${thick}px;--s0:${r3(stub / len)};--at:${r3(r.set ? -1 : r.figT - 0.1)}"><i></i>` +
      `${bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}</div></div>`;
  }).join("");
  const scale = k > 1 ? `--k:${r3(k)};--reveal:${r3(p.reveal_scale_at)}` : "--k:1;--reveal:999";
  return cam(B, `<div class="ty-box ty-b">${head(p, spoken)}<div class="ty-b-rows" style="--axis:${axis}px;height:${n * pitch}px;${scale}">${html}</div></div>`);
}

/**
 * A share of a whole: one bar for the whole, split as each part is said. Percentages split a 100%
 * bar (the rest left unfilled); counts make the largest the whole and the others its parts, to scale.
 * The bar runs the full grid, its figures at up to 150 px over (or, with a whole, under) their parts.
 */
function shares(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], known = knownOf(job), narrow = B.narrow;
  const all = evs.map((e) => ({ e, ...sides(e, spoken) }));
  const pct = all.filter((q) => q.fig && /%/.test(q.fig));
  let parts, context, whole = null;
  if (pct.length) { parts = pct; context = all.filter((q) => !pct.includes(q)); }
  else {
    const figs = all.filter((q) => q.fig);
    whole = figs.reduce((a, q) => (amount(q.fig) > amount(a.fig) ? q : a), figs[0]);
    parts = figs.filter((q) => q !== whole); context = all.filter((q) => !q.fig);
  }
  const W = B.w, total = whole ? amount(whole.fig) : 100;
  let x = 0;
  parts.forEach((q) => { q.v = amount(q.fig); q.x = x; q.w = (q.v / total) * W; x += q.w; });
  const firstT = Math.min(...[...parts, ...(whole ? [whole] : [])].map((q) => Math.min(q.figT, q.nameT)));
  const trackT = whole ? (known(whole.fig) && whole.figT <= 0.4 ? -1 : whole.figT - 0.1) : Math.max(-0.4, firstT - 2.2);
  const bs = beats([...context.flatMap((c) => [c.figT, c.nameT]), trackT, ...parts.flatMap((q) => [q.figT, q.nameT])], spoken, B.dur, parts.length);
  const ctxPx = narrow ? 64 : 80;
  const ctx = context.map((c) => {
    const t = saidAt(c.e.date, spoken, c.e.at) ?? c.e.at ?? 0.4, lt = c.e.name_at ?? saidAt(c.e.label, spoken, t + 1) ?? t + 1;
    return `<p class="ty-s-ctx"><span class="ty-fd" style="font-size:${ctxPx}px">${wordSpans(c.e.date, sayFrom(c.e.date, spoken, t))}</span>` +
      ` <span class="ty-s-ctx-l">${wordSpans(c.e.label, sayFrom(c.e.label, spoken, lt))}</span></p>`;
  }).join("");
  const figPx = whole ? (narrow ? 84 : 108) : narrow ? 112 : 150;
  const lab = (q) => {
    const f = figLine(q.fig, figPx, { times: figTimes(q.fig, spoken, q.figT), unitMin: LABEL, known: known(q.fig) });
    const nT = Math.min(q.nameT, q.figT + 0.3);
    return { f, html: `<div class="ty-s-fig" style="font-size:${figPx}px">${f.html}</div><p class="ty-s-name">${labelSpans(q.name || "", spoken, hasFig(q.name || "") ? nT : Math.max(nT, q.figT - 0.2))}</p>` };
  };
  const labH = Math.round(figPx * 0.92 + 14 + 36 + 26);
  // the whole's figure sits over the bar at its left; with a whole, each part's figure sits under its segment
  const top = whole ? `<div class="ty-s-lab" style="left:0">${lab(whole).html}</div>` : "";
  const segs = parts.map((q, i) => {
    const L = lab(q), lx = Math.max(0, Math.min(q.x, W - L.f.w));
    const at = known(q.fig) && q.figT <= 0.4 ? -1 : q.figT - 0.1;
    return `<div class="ty-s-seg" style="left:${r3(q.x)}px;width:${r3(q.w)}px;--at:${r3(at)}"><i></i>${bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("")}</div>` +
      `<div class="ty-s-lab${whole ? " under" : ""}" style="left:${r3(lx)}px">${L.html}</div>`;
  }).join("");
  const barH = narrow ? 56 : 72;
  return cam(B, `<div class="ty-box ty-s">${head(p, spoken)}${ctx}<div class="ty-s-bar${whole ? " whole" : ""}" style="width:${Math.round(W)}px;height:${barH}px;margin-top:${labH}px;margin-bottom:${whole ? labH : 0}px;--at:${r3(trackT)}"><i class="ty-s-track"></i>${top}${segs}</div></div>`);
}

/* ---------- a step: prices either side of an edge, or the staircase itself ---------- */

/**
 * The step. Prices either side of an edge draw as columns to scale with the jump the hero; when
 * the events carry no money but weights ("a pound and an ounce"), the staircase itself is drawn.
 * A step that can draw neither fails the build: it never falls back to a ledger.
 */
function step(job, evs) {
  const key = stepKey(evs, job);
  if (key >= 0) return stepMoney(job, evs, key);
  const fig = (e) => (figureLed(e.label) ? e.label : figureLed(e.date) ? e.date : null);
  if (evs.filter((e) => fig(e) && isMoney(fig(e))).length >= 2) return stepMoney(job, evs, -1);
  if (evs.some((e) => weightOf(e))) return stepWeight(job, evs);
  throw new Error(`${job.id}: layout "step" needs prices either side of an edge or weights on a staircase, and has neither`);
}

/**
 * A price step on the full grid: each pair of prices as columns to scale (250 px wide, as tall as
 * the box allows), their values over them; the jump the hero at up to 250 px beside the riser it
 * measures, a leader from the riser to it; the card's context (the band, the date, a surcharge) as
 * label/value rows under the hero, or on one line under the heading when the panel is full. At the
 * cut the axis, the context names and every column already spoken stand formed.
 */
function stepMoney(job, evs, key) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], known = knownOf(job), narrow = B.narrow;
  const rows = evs.map((e, i) => ({ e, i, ...sides(e, spoken) })), kw = knownWords(job);
  rows.forEach((r) => { r.v = r.fig && isMoney(r.fig) ? amount(r.fig) : NaN; r.k = !!r.fig && known(r.fig); r.set = r.k && r.figT <= 0.4; });
  const pairs = [];
  for (let i = 0; i + 1 < rows.length; i++) {
    if (i === key || i + 1 === key || rows[i].used) continue;
    if (Number.isFinite(rows[i].v) && Number.isFinite(rows[i + 1].v) && rows[i + 1].v > rows[i].v) { pairs.push([rows[i], rows[i + 1]]); rows[i].used = rows[i + 1].used = true; }
  }
  if (!pairs.length) {   // two prices in any order: the lower first
    const m = rows.filter((r) => Number.isFinite(r.v) && r.i !== key).sort((a, b) => a.v - b.v);
    if (m.length < 2) throw new Error(`${job.id}: a price step needs two prices`);
    pairs.push([m[0], m[m.length - 1]]); m[0].used = m[m.length - 1].used = true;
  }
  const K = key >= 0 ? rows[key] : null;
  const stepPair = (K && pairs.find(([a, b]) => Math.abs(b.v - a.v - K.v) < 0.006)) || pairs.reduce((m, q) => (q[1].v - q[0].v > m[1].v - m[0].v ? q : m));
  const context = rows.filter((r) => !r.used && r !== K);
  const max = Math.max(...pairs.flat().map((r) => r.v)), np = pairs.length;
  const keyT = K ? K.figT : Math.max(...stepPair.map((r) => r.figT)) + 0.6;
  const keySet = K ? K.set : stepPair.every((r) => r.set);
  // the grid
  const hH = headH(p.heading, B.w);
  const colW = Math.round((narrow ? 150 : 250) * (np > 1 ? 0.72 : 1)), gapIn = Math.round(colW * 0.16), gapOut = Math.round(colW * 0.5);
  const colsW = np * (2 * colW + gapIn) + (np - 1) * gapOut;
  const valPx = narrow ? 48 : np > 1 ? 56 : 64, labPx = LABEL;
  const baseY = B.h - Math.round(labPx * 1.25 * 2 + 18);
  const rx = colsW + (narrow ? 56 : 100), rw = B.w - rx;
  // the hero: the jump, as large as the panel allows
  const heroName = K ? K.name || "" : "the difference";
  let heroPx = narrow ? 180 : 250, hf = null;
  const heroOf = (px) => (K ? figLine(K.fig, px, { times: [keyT], blue: true, unitMin: LABEL, known: K.k }) : { w: serifW(heroName, px * 0.5, true), html: "" });
  for (hf = heroOf(heroPx); hf.w > rw - 10 && heroPx > 96; hf = heroOf(heroPx)) heroPx -= 4;
  const heroNamePx = 48, heroGap = (px) => Math.round(18 + px * 0.16);
  let heroNameH = heroName ? Math.round(heroNamePx * 1.15) + heroGap(heroPx) : 0;
  // the context: label over value, packed in rows
  const items = context.map((r) => {
    const valTxt = r.fig ?? (timeish(r.e.label) ? r.e.label : r.e.date), name = r.fig ? r.name || "" : timeish(r.e.label) ? r.e.date : r.e.label;
    const t = r.fig ? r.figT : saidAt(valTxt, spoken, r.e.at) ?? r.e.at ?? 0.4;
    const vPx = 52, f = figLine(valTxt, vPx, { times: figTimes(valTxt, spoken, t), quiet: isMoney(valTxt), known: known(valTxt), time: timeish(valTxt) });
    return { r, name: name || "", f, t, w: Math.max(labelW(String(name || "").toUpperCase(), labPx), f.w), h: Math.round(labPx * 1.2 + 8 + vPx * 0.95) };
  });
  const pack = (width) => {
    let rowsN = items.length ? 1 : 0, x = 0;
    items.forEach((it) => { if (x && x + 48 + it.w > width) { rowsN++; x = it.w; } else x += (x ? 48 : 0) + it.w; });
    return rowsN ? rowsN * Math.max(...items.map((it) => it.h)) + (rowsN - 1) * 22 : 0;
  };
  let ctxAt = null;   // "panel" (under the hero) or "strip" (under the heading)
  if (items.length) {
    for (let px = heroPx; px >= Math.max(96, heroPx - 70) && !ctxAt; px -= 6) {
      const h = (heroName ? Math.round(heroNamePx * 1.15) + heroGap(px) : 0) + px * 0.86;
      if (h + 44 + pack(rw) <= B.h - hH) { heroPx = px; hf = heroOf(px); ctxAt = "panel"; }
    }
    if (!ctxAt) ctxAt = "strip";
  }
  const stripH = ctxAt === "strip" ? pack(B.w) + 36 : 0;
  const top0 = hH + stripH, colTop = top0 + valPx + 26, H = Math.max(160, baseY - colTop);
  const yOf = (v) => baseY - (v / max) * H;
  const bs = beats(rows.map((r) => r.figT), spoken, B.dur, 1);
  // columns
  let x = 0;
  const geo = new Map();
  const cols = pairs.map(([a, b]) => {
    const out = [a, b].map((r, j) => {
      const h = (r.v / max) * H, hi = r === stepPair[1];
      const riser = hi ? (stepPair[0].v / max) * H : 0;
      geo.set(r, { x, w: colW });
      const f = figLine(r.fig, valPx, { times: [r.figT], quiet: true, unitMin: LABEL, known: r.k });
      const at = r.set ? -1 : r.figT - 0.1;
      const nT = r.set ? -0.4 : r.e.name_at ?? (hasFig(r.name || "") && !kw(r.name || "") ? r.nameT : -0.4);
      const html = `<div class="ty-c-col${r.k ? " known" : ""}" style="left:${x}px;width:${colW}px;height:${r3(h)}px;top:${r3(baseY - h)}px;--at:${r3(at)}"><i></i>` +
        `${hi ? `<b class="ty-c-riser" style="height:${r3(h - riser)}px;--at:${r3(keySet ? -1 : keyT - 0.15)}"></b>${pulses(bs, 0, "pulse-riser")}` : ""}` +
        `<div class="ty-c-val" style="font-size:${valPx}px">${f.html}</div></div>` +
        `<p class="ty-c-lab" style="left:${x}px;width:${colW + gapIn - 8}px;top:${baseY + 16}px">${labelSpans(r.name || "", spoken, nT, kw)}</p>`;
      x += colW + (j ? 0 : gapIn);
      return html;
    }).join("");
    x += gapOut;
    return out;
  }).join("");
  // the step itself: the lower price's level carried across the riser, and a leader from the riser to the hero
  const [lo, hi] = stepPair, gl = geo.get(lo), gh = geo.get(hi);
  const yLo = yOf(lo.v), yHi = yOf(hi.v), yr = (yLo + yHi) / 2;
  const levelT = keySet ? -1 : keyT - 0.45;
  const level = `<i class="ty-c-level" style="left:${gl.x}px;width:${gh.x + gh.w - gl.x}px;top:${r3(yLo)}px;--at:${r3(levelT)}"></i>`;
  heroNameH = heroName ? Math.round(heroNamePx * 1.15) + heroGap(heroPx) : 0;
  const heroH = heroNameH + heroPx * 0.86;
  const panelBottom = ctxAt === "panel" ? B.h - pack(rw) - 44 : B.h;
  const heroTop = Math.round(clamp(yr - heroNameH - heroPx * 0.45, top0, panelBottom - heroH));
  const figMid = heroTop + heroNameH + heroPx * 0.45;
  const lead = `<i class="ty-c-lead" style="left:${gh.x + gh.w + 14}px;width:${Math.max(20, rx - gh.x - gh.w - 34)}px;top:${r3(yr)}px;--rise:${r3(figMid - yr)}px;--at:${r3(keySet ? -1 : keyT - 0.1)}"></i>`;
  const hero = `<div class="ty-c-hero" style="left:${rx}px;width:${rw}px;top:${heroTop}px;gap:${heroGap(heroPx)}px">` +
    `${heroName ? `<p class="ty-c-name" style="font-size:${heroNamePx}px">${K ? labelSpans(heroName, spoken, K.set ? -0.4 : Math.max(0.41, K.nameT)) : wordSpans(heroName, [keyT])}</p>` : ""}` +
    `${K ? `<div class="ty-c-fig" style="font-size:${heroPx}px">${bloom(hf.w * 1.4, heroPx * 1.8, keyT, true)}${hf.html}${pulses(bs, 0, "pulse-blue")}</div>` : ""}</div>`;
  const ctxHTML = items.length ? `<div class="ty-c-ctx" style="left:${ctxAt === "panel" ? rx : 0}px;top:${ctxAt === "panel" ? B.h - pack(rw) : hH}px;width:${ctxAt === "panel" ? rw : B.w}px">` +
    items.map((it) => `<div class="ty-c-row" style="width:${Math.ceil(it.w)}px"><p class="ty-c-rname">${labelSpans(it.name, spoken, hasFig(it.name) && !kw(it.name) ? it.r.nameT : -0.4, kw)}</p><div class="ty-c-rval">${it.f.html}</div></div>`).join("") + `</div>` : "";
  return cam(B, `<div class="ty-box ty-c">${head(p, spoken)}<div class="ty-c-cols" style="height:${B.h}px">${ctxHTML}` +
    `<i class="ty-c-base" style="top:${baseY}px;width:${colsW + 30}px"></i>${cols}${level}${lead}${hero}</div></div>`);
}

const OZ = 1 / 16;
/** A weight in pounds from its words: a point ({x}), a span ({a, b}) or the staircase under the first step ({sub}). */
function parseWeight(s) {
  const t = String(s ?? "").toLowerCase().replace(/[’']/g, "'").trim();
  if (/\bbelow the first (?:step|tread|pound)\b|\bsmaller staircase\b/.test(t)) return { sub: true };
  if (/\b(?:a|an|one) ounce over\b/.test(t)) return { a: 1, b: 1 + OZ };
  if (/\bwhisker (?:under|below) the next pound\b/.test(t)) return { x: 2 - 0.06 };
  if (/\b(?:whole|full) next pound\b/.test(t)) return { a: 1, b: 2 };
  if (/\b(?:a|one) pound and (?:an|one) ounce\b/.test(t)) return { x: 1 + OZ };
  if (/^(?:a|one|the first) pound$/.test(t)) return { x: 1 };
  return null;
}
/** An event's weight: the plan's `span` [a, b] or `pos` (pounds), else read from its words. */
function weightOf(e) {
  if (Array.isArray(e.span) && e.span.length === 2) return { a: +e.span[0], b: +e.span[1], side: "date" };
  if (typeof e.pos === "number") return { x: e.pos, side: "date" };
  const d = parseWeight(e.date);
  if (d) return { ...d, side: "date" };
  const l = parseWeight(e.label);
  return l ? { ...l, side: "label" } : null;
}

/**
 * The staircase by weight (no figures needed: the drawing is the comparison). Weight runs along
 * the line in pounds; each pound's tread sits one step higher, its riser at the pound line, the
 * first riser the hero, blue when it lights. Each event is a point on its tread ("a pound and an
 * ounce" just past the first riser, "a whisker under the next pound" at the tread's far end, both
 * one price), a span lit along a tread ("one ounce over", "the whole next pound", to scale), or
 * the smaller staircase drawn under the first step; its words land on their onsets, set where
 * they touch no riser, tread or other label. Without a print it fills the grid; with one, the left box.
 */
function stepWeight(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], narrow = B.narrow;
  const ev = evs.map((e) => {
    const w = weightOf(e), phrase = String((w?.side === "label" ? e.label : e.date) ?? ""), cap = String((w?.side === "label" ? e.date : e.label) ?? "");
    const said = saidAt(phrase, spoken, e.at);
    const at = e.at ?? said ?? 0.4;
    const markT = w?.sub ? at : said != null ? Math.max(at, said) : at;
    const pt = sayFrom(phrase, spoken, Math.max(0, markT - 0.4));
    const near = spoken.filter((x) => Math.abs(x.t - at) <= 1.5);
    const ct0 = cap ? phraseTimes(cap, near, at) : null;
    const ct = ct0 ? ct0.map((t) => Math.max(0, t)) : words(cap).map((_, i) => markT + 0.3 + i * 0.06);
    return { e, w, phrase, cap, at, markT, pt, ct };
  }).filter((v) => v.w);
  const xs = ev.flatMap((v) => (v.w.sub ? [0.25, 1] : v.w.x != null ? [v.w.x] : [v.w.a, v.w.b]));
  const hasSub = ev.some((v) => v.w.sub);
  const lo = hasSub ? 0 : Math.max(0, Math.min(...xs) - 0.45), hi = Math.max(...xs, 1) + 0.6;
  const W = B.w, hH = headH(p.heading, W), top0 = hH + 24, baseY = B.h - 12;
  const nLev = Math.ceil(hi - 1e-9), u = (baseY - top0 - 20) / nLev;
  const X = (lb) => Math.round(((lb - lo) / (hi - lo)) * W);
  const lev = (lb) => Math.max(1, Math.ceil(lb - 1e-9));
  const Y = (k) => Math.round(baseY - k * u);
  // the staircase stands at the cut on a callback (its first event due by 1 s), else draws as the heading is read
  const first = Math.min(...ev.map((v) => v.at));
  const drawT = first <= 1 ? -2 : -0.3;
  const pts = [[X(lo), Y(lev(Math.max(lo, 1e-6)))]];
  for (let k = Math.floor(lo) + 1; k < hi; k++) pts.push([X(k), Y(k)], [X(k), Y(k + 1)]);
  pts.push([X(hi), Y(lev(hi))]);
  const d = `M${pts.map((q) => q.join(" ")).join(" L")}`;
  const fill = `${d} L${X(hi)} ${baseY} L${X(lo)} ${baseY} Z`;
  // when the first riser lights: the first event at or past the line
  const past = ev.filter((v) => (v.w.x != null && v.w.x > 1) || (v.w.a != null && v.w.a >= 1));
  const riserT = past.length ? Math.min(...past.map((v) => v.at)) : null;
  const guides = Array.from({ length: Math.max(0, Math.ceil(hi) - Math.floor(lo) - 1) }, (_, i) => Math.floor(lo) + 1 + i).filter((k) => k > lo && k < hi);
  // obstacles a label must not touch
  const obs = [{ x0: -999, x1: 9999, y0: -999, y1: hH }];
  for (let k = Math.floor(lo) + 1; k <= nLev; k++) obs.push({ x0: X(Math.max(lo, k - 1)), x1: X(Math.min(hi, k)), y0: Y(k) - 8, y1: Y(k) + 8 });
  guides.forEach((k) => obs.push({ x0: X(k) - 8, x1: X(k) + 8, y0: Y(k + 1) - 4, y1: Y(k) + 4 }));
  const fp = narrow ? 40 : 52, cp = narrow ? 32 : 40;
  const marks = [], labels = [];
  const hit = (a, b, m = 0) => a.x0 < b.x1 + m && b.x0 < a.x1 + m && a.y0 < b.y1 + m && b.y0 < a.y1 + m;
  const blockOf = (v, nl) => {
    const pl = nl === 1 ? [v.phrase] : breakK(words(v.phrase), 2, (s) => serifW(s, fp));
    const w = Math.max(...pl.map((l) => serifW(l, fp)), v.cap ? serifW(v.cap, cp, true) : 0);
    return { pl, w, h: pl.length * fp * 1.12 + (v.cap ? 8 + cp * 1.22 : 0) };
  };
  const place = (v, cands) => {
    let best = null;
    for (const c of cands) {
      const r = { x0: c.x, x1: c.x + c.w, y0: c.y, y1: c.y + c.h };
      if (r.x0 < 0 || r.x1 > W || r.y0 < hH || r.y1 > baseY - 6) continue;
      const bad = obs.filter((o) => hit(r, o)).length + labels.filter((l) => hit(r, l.r, 20)).length;
      if (!bad) { best = { c, r }; break; }
      if (!best || bad < best.bad) best = { c, r, bad };
    }
    if (!best) best = { c: cands[0], r: { x0: cands[0].x, x1: cands[0].x + cands[0].w, y0: cands[0].y, y1: cands[0].y + cands[0].h } };
    labels.push({ v, ...best });
  };
  // spans first (the larger), then the sub staircase, then points
  const order = [...ev].sort((a, b) => (a.w.a != null ? 0 : a.w.sub ? 1 : 2) - (b.w.a != null ? 0 : b.w.sub ? 1 : 2));
  // a span is a dimension bracket under its tread, to scale: the narrowest nearest the tread
  ev.filter((v) => v.w.a != null).sort((a, b) => (a.w.b - a.w.a) - (b.w.b - b.w.a)).forEach((v, i) => { v.depth = 24 + 30 * i; });
  let sub = null;
  order.forEach((v) => {
    const c1 = blockOf(v, 1), c2 = blockOf(v, 2), cands = [];
    if (v.w.sub) {
      const x0 = X(Math.max(lo, 0)), x1 = X(1), steps = 4, sw = X(OZ) - X(0), rise = (u * 0.62) / steps;
      sub = { x0, sw, rise, steps };
      obs.push({ x0, x1: x0 + steps * sw + 10, y0: baseY - steps * rise - 10, y1: baseY });
      for (const c of [c1, c2]) cands.push({ ...c, x: x0 + steps * sw + 28, y: Y(1) + 22, al: "l" }, { ...c, x: x0 + 18, y: Y(1) - 26 - c.h, al: "l" });
      marks.push(v);
      return place(v, cands);
    }
    const py = Y(lev(v.w.x ?? v.w.b));
    if (v.w.a != null) {
      const xa = X(v.w.a), xb = X(v.w.b), cx = (xa + xb) / 2, by = py + v.depth;
      for (const c of [c1, c2]) {
        if (xb - xa > c.w) cands.push({ ...c, x: cx - c.w / 2, y: py - 30 - c.h, al: "c" }, { ...c, x: cx - c.w / 2, y: by + 22, al: "c" });
        cands.push({ ...c, x: xb + 18, y: py - 30 - c.h, al: "l" }, { ...c, x: xb + 18, y: by - c.h / 2, al: "l" }, { ...c, x: xa - 18 - c.w, y: by + 22, al: "r" }, { ...c, x: xa - 18 - c.w, y: py - 30 - c.h, al: "r" }, { ...c, x: xa + 18, y: by + 22, al: "l" });
      }
      obs.push({ x0: xa - 4, x1: xb + 4, y0: by - 14, y1: by + 8 });
    } else {
      const px = X(v.w.x), corner = Math.abs(v.w.x - Math.round(v.w.x)) < 1e-6;
      for (const c of [c1, c2]) {
        const right = [{ ...c, x: px + 18, y: py - 26 - c.h, al: "l" }, { ...c, x: px + 18, y: py + 26, al: "l" }];
        const left = [{ ...c, x: px - 18 - c.w, y: py - 26 - c.h, al: "r" }, { ...c, x: px - 18 - c.w, y: py + 26, al: "r" }];
        cands.push(...(corner ? [...left, ...right] : [...right, ...left]));
      }
      obs.push({ x0: px - 16, x1: px + 16, y0: py - 16, y1: py + 16 });
    }
    marks.push(v);
    place(v, cands);
  });
  // two points on one tread pay one price: the tread lights between them when the second lands
  const pts1 = ev.filter((v) => v.w.x != null).sort((a, b) => a.w.x - b.w.x);
  const same = [];
  for (let i = 0; i + 1 < pts1.length; i++) if (lev(pts1[i].w.x) === lev(pts1[i + 1].w.x)) same.push([pts1[i], pts1[i + 1]]);
  const bs = beats(ev.flatMap((v) => [v.markT, ...v.ct]), spoken, B.dur, 1);
  const subT = ev.find((v) => v.w.sub);
  const dim = subT ? `;--dimAt:${r3(subT.pt[0])}` : "";
  const svg = `<svg class="ty-sw-svg${subT ? " dims" : ""}" style="${dim.slice(1)}" viewBox="0 0 ${W} ${B.h}" width="${W}" height="${B.h}">` +
    guides.map((k) => `<line class="ty-sw-guide" x1="${X(k)}" y1="${baseY}" x2="${X(k)}" y2="${top0}"/>`).join("") +
    `<path class="ty-sw-fill" d="${fill}" style="--at:${r3(drawT + 0.6)}"/>` +
    `<line class="ty-sw-base" x1="${X(lo)}" y1="${baseY}" x2="${X(hi)}" y2="${baseY}"/>` +
    `<path class="ty-sw-line" pathLength="1" d="${d}" style="--at:${r3(drawT)}"/>` +
    (lo < 1 && hi > 1 && riserT != null ? `<path class="ty-sw-riser" pathLength="1" d="M${X(1)} ${Y(1)} L${X(1)} ${Y(2)}" style="--at:${r3(riserT - 0.1)}"/>` +
      bs.map((b) => `<path class="ty-sw-riser-beat" d="M${X(1)} ${Y(1)} L${X(1)} ${Y(2)}" style="--at:${r3(b.t)}"/>`).join("") : "") +
    same.map(([a, b]) => `<path class="ty-sw-same" pathLength="1" d="M${X(a.w.x)} ${Y(lev(a.w.x))} L${X(b.w.x)} ${Y(lev(b.w.x))}" style="--at:${r3(b.markT + 0.15)}"/>`).join("") +
    marks.filter((v) => v.w.a != null).map((v) => {
      const y = Y(lev(v.w.b)) + v.depth, xa = X(v.w.a), xb = Math.max(xa + 6, X(v.w.b));
      return `<path class="ty-sw-span" pathLength="1" d="M${xa} ${y - 10} L${xa} ${y} L${xb} ${y} L${xb} ${y - 10}" style="--at:${r3(v.markT - 0.05)}"/>`;
    }).join("") + `</svg>`;
  const subSvg = sub ? (() => {
    let q = `M${sub.x0} ${baseY}`;
    for (let i = 0; i < sub.steps; i++) q += ` L${sub.x0 + i * sub.sw} ${r3(baseY - (i + 1) * sub.rise)} L${sub.x0 + (i + 1) * sub.sw} ${r3(baseY - (i + 1) * sub.rise)}`;
    q += ` L${sub.x0 + sub.steps * sub.sw} ${baseY}`;
    return `<svg class="ty-sw-svg sub" viewBox="0 0 ${W} ${B.h}" width="${W}" height="${B.h}"><path class="ty-sw-subline" pathLength="1" d="${q}" style="--at:${r3(subT.markT - 0.1)}"/></svg>`;
  })() : "";
  const dots = marks.filter((v) => v.w.x != null).map((v) => `<div class="ty-sw-dot${subT ? " dims" : ""}" style="left:${X(v.w.x)}px;top:${Y(lev(v.w.x))}px;--at:${r3(v.markT - 0.05)};${dim.slice(1)}"><i class="ty-t-node"></i><i class="ty-t-ring"></i></div>`).join("");
  const labs = labels.map(({ v, c, r }) => {
    let j = 0;
    const ph = c.pl.map((l) => { const ws = words(l), ts = v.pt.slice(j, j + ws.length); j += ws.length; return `<span class="ty-vl">${wordSpans(l, ts)}</span>`; }).join("");
    const isSub = v.w.sub, dm = subT && !isSub ? ` dims` : "";
    return `<div class="ty-sw-lab ${c.al}${dm}" style="left:${Math.round(r.x0)}px;top:${Math.round(r.y0)}px;width:${Math.ceil(c.w) + 2}px;${dim.slice(1)}">` +
      `<p class="ty-sw-ph" style="font-size:${fp}px">${ph}</p>${v.cap ? `<p class="ty-sw-cap" style="font-size:${cp}px">${wordSpans(v.cap, v.ct)}</p>` : ""}</div>`;
  }).join("");
  return cam(B, `<div class="ty-box ty-sw">${head(p, spoken)}<div class="ty-sw-area" style="height:${B.h}px">${svg}${subSvg}${dots}${labs}</div></div>`);
}

/**
 * Anything else: a typeset ledger spread over the box's height. A list of dates sets each date as
 * the hero (Fraunces, to 96 px) over its label in italic; other figures sit right-aligned on
 * leaders, and money in one unit draws a thin bar to scale under each figure (the total's blue). A
 * row without a figure heads a section. Long names (sources) stack over their figure, set in the
 * plan's `face` (period print, typewriter). A row's name lands whole at its row's time; only words
 * the voice says within 1.5 s of its figure follow their onsets. Ruled lines stand at the cut, so
 * the page is there before its entries. A verbatim `words` quote closes it, word by word.
 */
function ledger(job, evs) {
  const B = stage(job), p = job.params || {}, spoken = job.words || [], known = knownOf(job), narrow = B.narrow;
  const rows = evs.map((e) => ({ e, ...sides(e, spoken) }));
  rows.forEach((r) => {
    if (r.fig) return;
    const side = timeish(r.e.label) ? "label" : timeish(r.e.date) ? "date" : null;
    if (!side) return;
    r.fig = r.e[side]; r.name = side === "label" ? r.e.date : r.e.label;
    r.figT = r.e.at != null && r.e.at <= 0.4 ? r.e.at : saidAt(r.fig, spoken, r.e.at) ?? r.e.at ?? 0.4;
    r.nameT = r.e.name_at ?? Math.min(r.figT, saidAt(r.name, spoken, r.figT) ?? r.figT);
  });
  rows.forEach((r) => { r.section = !r.fig; r.k = !!r.fig && known(r.fig); });
  const figRows = rows.filter((r) => !r.section);
  const dates = figRows.length && figRows.filter((r) => kindOf(r.fig) === "time").length > figRows.length / 2;
  const keyI = job.on == null ? -1 : rows.findIndex((r) => !r.section && Math.abs(r.figT - job.on) < 0.3);
  const W = B.w;
  const q = p.words?.text ? p.words : null;
  const qPx = narrow ? 44 : 52, qLines = q ? Math.ceil(serifW(q.text, qPx, true) / Math.min(W, 1240)) : 0;
  const avail = B.h - headH(p.heading, W) - (q ? qLines * qPx * 1.3 + 64 : 0);
  const units = rows.reduce((a, r) => a + (r.section && !dates ? 0.7 : 1), 0), per = avail / Math.max(1, units);
  // a name that cannot share its line with its figure (a source's full title) stacks over it
  const rowPx = Math.round(clamp(per * 0.34, 36, 56)), rowVal = Math.round(clamp(per * 0.52, 56, narrow ? 84 : 96));
  const stacked = !dates && rows.some((r) => !r.section && serifW(r.name || "", rowPx) + 80 + figLine(r.fig, rowVal).w > W);
  const money = !dates && !stacked && figRows.length >= 3 && figRows.every((r) => isMoney(r.fig) && unitOf(r.fig) === unitOf(figRows[0].fig));
  const vmax = money ? Math.max(...figRows.map((r) => amount(r.fig))) : 1;
  const bs = beats([...rows.flatMap((r) => [r.figT, r.nameT]), ...(q ? [q.at] : [])], spoken, B.dur, rows.length);
  const face = (r) => (r.e.face === "period" ? " period" : r.e.face === "typed" ? " typed" : "");
  // a name lands whole at its row's time; words said near its figure (and any figure in it) on their onsets
  const nameSpans = (name, r) => {
    const rowT = r.e.name_at ?? Math.min(r.nameT, r.figT);
    const ws = words(name);
    if (!ws.length) return "";
    const near = phraseTimes(name, spoken.filter((x) => Math.abs(x.t - r.figT) <= 1.5), r.figT)?.raw || [];
    const later = phraseTimes(name, spoken.filter((x) => x.t >= rowT - 0.05), rowT)?.raw || [];
    const ts = ws.map((w, i) => Math.max(rowT, isFigWord(w) ? later[i] ?? near[i] ?? rowT : near[i] ?? rowT));
    return rowT <= 0.4 && ts.every((t) => t <= 0.4) ? wordSpans(name, [-1], { set: true, known: true }) : wordSpans(name, ts);
  };
  const rule = (i) => `<i class="ty-l-rule" style="--at:${r3(-0.6 + i * 0.05)}"></i>`;
  let html;
  if (dates) {
    const dpx = Math.round(clamp(per * 0.5, 56, narrow ? 84 : 96));
    // a label keeps to the box: smaller, then on two balanced lines (a source's full title)
    const labOf = (r) => (r.fig ? r.name || "" : String(r.e.label ?? "")), widest = Math.max(...rows.map((r) => serifW(labOf(r), 1, true) * (r.e.face === "typed" ? 1.25 : 1)));
    const lpx = Math.round(clamp(Math.min(dpx * 0.56, (W - 8) / widest), Math.min(36, dpx * 0.56), 52));
    html = rows.map((r, i) => {
      const glints = bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("");
      const top = r.fig ? figLine(r.fig, dpx, { times: figTimes(r.fig, spoken, r.figT), known: r.k, time: kindOf(r.fig) === "time" }).html
        : wordSpans(String(r.e.date ?? ""), sayFrom(String(r.e.date ?? ""), spoken, r.e.name_at ?? r.e.at ?? 0.4));
      const name = r.fig ? r.name || "" : String(r.e.label ?? "");
      return `<div class="ty-l-entry dated" style="min-height:${Math.round(per)}px">${glints}<div class="ty-l-date" style="font-size:${dpx}px">${top}</div>` +
        `<p class="ty-l-dlab${face(r)}" style="font-size:${lpx}px">${r.fig ? nameSpans(name, r) : wordSpans(name, sayFrom(name, spoken, r.e.name_at ?? r.e.at ?? 0.4))}</p>${rule(i)}</div>`;
    }).join("");
  } else {
    // a name keeps to the box (a print narrows it): its face measured as set (typewriter ~0.6 em a character), then wrapped
    const faceW = (r) => (r.e.face === "typed" ? 0.6 * String(r.name || "").length : serifW(r.name || "", 1) * (r.e.face === "period" ? 1.08 : 1));
    const fitName = Math.floor((W - 8) / Math.max(1e-6, ...rows.filter((r) => !r.section).map(faceW)));
    const namePx = Math.round(clamp(Math.min(per * (stacked ? 0.26 : 0.34), stacked ? Math.max(fitName, 32) : 99), stacked ? 32 : 36, stacked ? 44 : 56));
    const valPx = Math.round(clamp(per * (stacked ? 0.5 : 0.52), 56, narrow ? 84 : stacked ? 112 : 96));
    const pitch = Math.round(clamp(per, 72, stacked ? 230 : 170));
    html = rows.map((r, i) => {
      const glints = bs.filter((b) => b.k === i).map((b) => `<s style="--at:${r3(b.t)}"></s>`).join("");
      if (r.section) {
        const a = String(r.e.date ?? ""), b = String(r.e.label ?? "");
        const at = r.e.name_at ?? saidAt(a, spoken, r.e.at) ?? r.e.at ?? 0.4, bt = saidAt(b, spoken, Math.max(at, r.e.at ?? at)) ?? (at <= 0.4 ? at : at + 0.4);
        const part = (x, t) => (t <= 0.4 && !hasFig(x) ? wordSpans(x, [-1], { set: true }) : wordSpans(x, sayFrom(x, spoken, t)));
        return `<div class="ty-l-sec" style="height:${Math.round(pitch * 0.8)}px">${glints}<span class="ty-l-sa">${part(a, at)}</span>` +
          `<span class="ty-l-sb" style="font-size:${Math.max(BODY, Math.round(namePx * 0.85))}px">${part(b, bt)}</span>${rule(i)}</div>`;
      }
      const blue = isMoney(r.fig) && (keyI >= 0 ? i === keyI : true);
      const until = keyI >= 0 ? 999 : rows.slice(i + 1).find((x) => !x.section && isMoney(x.fig))?.figT ?? 999;
      const f = figLine(r.fig, valPx, { times: figTimes(r.fig, spoken, r.figT), blue, unitMin: LABEL, known: r.k });
      const name = `<p class="ty-l-name${face(r)}" style="font-size:${namePx}px">${nameSpans(r.name || "", r)}</p>`;
      const vAt = r.k && r.figT <= 0.4 ? -1 : r.figT - 0.1;
      const bar = money ? `<i class="ty-l-bar${i === keyI ? " key" : ""}" style="width:${r3((amount(r.fig) / vmax) * W)}px;--at:${r3(vAt)}"></i>` : "";
      return stacked
        ? `<div class="ty-l-entry" style="min-height:${pitch}px">${glints}${name}<div class="ty-l-val${blue && keyI < 0 ? " fades" : ""}" style="--until:${r3(until)};font-size:${valPx}px">${f.html}</div>${rule(i)}</div>`
        : `<div class="ty-l-row${money ? " barred" : ""}" style="height:${pitch}px">${glints}${name}<i class="ty-l-lead" style="--at:${r3(Math.max(-0.4, Math.min(r.e.name_at ?? r.nameT, r.figT)))}"></i>` +
          `<div class="ty-l-val${blue && keyI < 0 ? " fades" : ""}" style="--until:${r3(until)};font-size:${valPx}px">${f.html}</div>${bar}${rule(i)}</div>`;
    }).join("");
  }
  let quote = "";
  if (q) {
    const ts = sayFrom(q.text, spoken, q.at ?? 0.4);
    const keys = (q.key || []).map((k) => words(k).map(norm));
    const ws = words(q.text), bright = ws.map(() => false);
    keys.forEach((kw) => { for (let i = 0; i + kw.length <= ws.length; i++) if (kw.every((x, j) => norm(ws[i + j]) === x)) kw.forEach((_, j) => { bright[i + j] = true; }); });
    quote = `<p class="ty-l-quote" style="font-size:${qPx}px">${ws.map((w, i) => `<span class="ty-w${bright[i] ? " key" : ""}" style="--at:${r3(ts[i])}">${T(w)}</span>`).join(" ")}</p>`;
  }
  return cam(B, `<div class="ty-box ty-l">${head(p, spoken)}<div class="ty-l-rows${stacked ? " stacked" : ""}${dates ? " dates" : ""}" style="width:${W}px">${html}</div>${quote}</div>`);
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
  // the site's one action, pointing right to where YouTube's end-screen elements sit; it lands on
  // the voice's own offer ("this is what I do"), never before the film has said it
  const ctaT = Math.max(1.6, phraseAt("this is what I do", spoken, 2.4));
  const cta = p.primary ? `<p class="ty-e-cta" style="${enter(ctaT)}">${esc(p.primary)}<b>→</b></p>` : "";
  return cam(B, `<div class="ty-box ty-e" style="width:${W}px"><h2 class="ty-e-head" style="font-size:${px}px">${h}</h2>` +
    `${url ? `<p class="ty-e-url"><span class="ty-w" style="--at:0.9">${esc(url)}</span><i class="ty-e-rule" style="--at:1.05"></i></p>` : ""}${sec}${cta}</div>`);
}
