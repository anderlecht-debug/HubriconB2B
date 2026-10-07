// v3 documents (docs/content/FILM_LOOK_V3.md, "the archive at night"; round 2, ROUND2.md).
// A source is a physical page on the desk under the one key light. Period dress (aged stock, Old
// Standard) only for real pre-1920 primary sources; a modern source is a modern object (clean laser
// stock, Inter). Words the film wrote itself (a table's heading, a house card's title) are never
// printed on the paper: they are a label on the desk, which also says the page was typeset.
//
// Every word on a page is the job's own text; every time is the job's own (`words`, `on`,
// `seconds`). Layout is computed here with the faces' real advance widths, so the camera, the
// highlighter and the depth of field know where every word sits before the browser draws it.
//   - The camera is one path through waypoints (≥ 1.2 s a segment, eased, arriving 0.1 s before
//     the word), riding on base.css's constant push and drift. Four moves: push, pull out from the
//     line, track along the line behind the highlighter, and a page sliding onto the stack.
//   - The highlighter follows the voice: it passes each word of the line as it is spoken.
//   - A figure (digits, or a spelled-out number: "fifty miles") is readable only as the narration
//     licenses it: sharp from the cut if the voice said it before this shot (job.known), landing
//     on its word if it is said in this shot, and never, for the whole shot, if it is not (a
//     stroke or a camera visit never lands it). The money figure the line lands on turns blue
//     (amber stays the highlighter).
//   - A modern source dresses as the object it is (dressOf): a ruled pad, a typed index card, a
//     ledger page, a printout, a clipped fee card, a laser print; short ones fill ~70% of the frame.
//   - Depth of field follows the camera: 0 / 1.5 / 3 / 5 px across ±1 / 2 / 3 lines.
import { esc } from "../shots.mjs";

// ── the faces' advance widths (per mille of the em, from the self-hosted fonts' hmtx) ───────
const CH = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~“”‘’—–…·éè§¢−";
const ADV = {
  period: [280, 280, 394, 684, 580, 860, 786, 240, 370, 370, 502, 940, 280, 370, 280, 450, 580, 580, 580, 580, 580, 580, 580, 580, 580, 580, 280, 280, 940, 940, 940, 470, 820, 764, 690, 670, 780, 690, 676, 720, 788, 394, 540, 756, 670, 838, 770, 700, 680, 700, 716, 620, 714, 780, 772, 1068, 750, 728, 652, 380, 450, 380, 580, 520, 369, 494, 512, 436, 522, 460, 330, 540, 544, 270, 320, 520, 270, 794, 540, 496, 518, 502, 410, 434, 350, 534, 530, 776, 520, 530, 440, 420, 284, 420, 660, 466, 466, 280, 280, 1000, 620, 840, 280, 460, 460, 640, 580, 580],
  periodBold: [280, 280, 394, 712, 580, 860, 786, 240, 370, 370, 502, 940, 280, 370, 280, 450, 580, 580, 580, 580, 580, 580, 580, 580, 580, 580, 280, 280, 940, 940, 940, 470, 820, 754, 710, 660, 786, 690, 670, 720, 824, 440, 540, 770, 670, 890, 764, 712, 702, 712, 730, 620, 716, 794, 772, 1076, 750, 736, 652, 380, 450, 380, 580, 520, 380, 508, 528, 468, 538, 472, 350, 554, 560, 296, 320, 560, 308, 800, 556, 504, 544, 524, 434, 430, 364, 550, 530, 776, 520, 524, 460, 420, 284, 420, 660, 500, 500, 280, 280, 1000, 620, 840, 280, 472, 472, 640, 580, 580],
  periodItalic: [280, 280, 394, 684, 580, 860, 740, 240, 370, 370, 580, 940, 280, 370, 280, 440, 580, 580, 580, 580, 580, 580, 580, 580, 580, 580, 280, 280, 940, 940, 940, 436, 820, 728, 690, 670, 750, 700, 680, 740, 800, 400, 540, 756, 680, 894, 790, 710, 654, 710, 720, 620, 690, 784, 752, 1078, 840, 720, 680, 380, 440, 380, 580, 520, 350, 536, 480, 424, 530, 410, 320, 480, 512, 334, 326, 490, 290, 806, 572, 462, 540, 480, 430, 420, 320, 572, 472, 716, 564, 512, 440, 420, 284, 420, 660, 440, 440, 280, 280, 1000, 620, 840, 280, 410, 410, 620, 580, 580],
  inter: [281, 288, 466, 633, 642, 982, 644, 300, 365, 365, 501, 662, 288, 460, 288, 360, 631, 407, 610, 618, 646, 593, 620, 566, 619, 620, 288, 302, 662, 662, 662, 511, 966, 690, 654, 730, 722, 601, 590, 746, 743, 269, 571, 672, 565, 903, 753, 765, 639, 765, 644, 642, 646, 744, 690, 985, 682, 679, 629, 365, 360, 365, 471, 456, 323, 562, 612, 571, 612, 583, 370, 613, 591, 242, 242, 549, 242, 876, 591, 600, 612, 612, 376, 528, 327, 591, 562, 818, 546, 562, 552, 426, 333, 426, 662, 440, 440, 261, 261, 1000, 500, 864, 288, 583, 583, 568, 571, 662],
  interSemi: [252, 321, 523, 644, 650, 1004, 663, 326, 373, 373, 540, 673, 319, 465, 319, 379, 660, 423, 623, 636, 666, 612, 640, 576, 640, 640, 319, 329, 673, 673, 673, 543, 999, 728, 659, 737, 722, 605, 588, 749, 746, 277, 580, 703, 565, 922, 759, 769, 645, 773, 652, 650, 660, 736, 728, 1020, 720, 713, 652, 373, 379, 373, 481, 469, 351, 574, 624, 583, 624, 591, 389, 625, 612, 262, 262, 569, 262, 900, 612, 609, 624, 624, 397, 549, 353, 612, 587, 839, 569, 588, 566, 455, 359, 455, 673, 507, 501, 294, 294, 1000, 500, 956, 319, 591, 591, 568, 583, 673],
};
// Inter's display cut (InterDisplay hmtx): the variable font's optical size follows the pixel
// size from 14 to 32 px, so its widths are the text cut's blended toward these.
ADV.interD = [250, 220, 403, 600, 614, 844, 608, 254, 299, 299, 469, 628, 220, 429, 220, 325, 613, 362, 561, 599, 618, 577, 584, 516, 582, 584, 220, 223, 628, 628, 628, 524, 974, 653, 638, 722, 689, 580, 554, 730, 708, 232, 535, 634, 535, 857, 710, 749, 612, 749, 632, 614, 610, 703, 653, 949, 646, 643, 613, 299, 325, 299, 438, 454, 241, 518, 565, 523, 565, 536, 306, 565, 547, 206, 206, 507, 206, 839, 547, 549, 565, 565, 322, 475, 311, 547, 512, 752, 507, 512, 479, 385, 296, 385, 628, 339, 340, 190, 190, 1000, 500, 659, 220, 536, 536, 537, 523, 628];
ADV.interSemiD = [226, 238, 449, 617, 640, 906, 634, 266, 321, 321, 513, 646, 236, 439, 236, 351, 638, 380, 586, 613, 644, 592, 606, 539, 604, 606, 236, 239, 646, 646, 646, 553, 996, 693, 643, 725, 697, 599, 572, 734, 715, 250, 553, 668, 550, 882, 720, 748, 625, 748, 644, 640, 627, 704, 688, 981, 680, 674, 627, 321, 351, 321, 455, 468, 277, 541, 587, 544, 587, 553, 349, 587, 573, 232, 233, 536, 232, 869, 573, 570, 587, 587, 356, 505, 350, 573, 540, 796, 527, 540, 508, 421, 330, 421, 646, 402, 397, 214, 214, 1000, 500, 709, 236, 553, 553, 538, 544, 646];
// Special Elite (a typed index card) and Instrument Serif italic (quotations), from their hmtx.
ADV.typed = [293, 276, 352, 555, 527, 667, 676, 196, 279, 282, 523, 496, 336, 636, 350, 557, 611, 570, 574, 557, 612, 538, 588, 555, 599, 584, 343, 329, 463, 637, 463, 470, 665, 550, 604, 579, 623, 639, 605, 615, 653, 495, 541, 583, 603, 698, 628, 617, 553, 602, 637, 589, 594, 622, 611, 644, 582, 561, 592, 312, 557, 312, 400, 682, 218, 565, 565, 547, 603, 544, 473, 583, 617, 568, 416, 621, 541, 664, 632, 583, 587, 568, 579, 520, 510, 639, 605, 679, 661, 593, 529, 275, 260, 277, 559, 470, 469, 265, 264, 1114, 612, 1064, 233, 544, 544, 435, 524, 578];
ADV.quoteI = [170, 275, 374, 629, 424, 591, 525, 235, 346, 346, 449, 531, 219, 426, 219, 258, 461, 248, 404, 373, 394, 387, 411, 365, 437, 414, 299, 301, 531, 531, 531, 358, 665, 457, 479, 475, 536, 454, 411, 514, 545, 250, 251, 499, 414, 665, 542, 540, 469, 541, 525, 424, 461, 537, 458, 653, 545, 478, 427, 326, 256, 326, 431, 372, 355, 474, 431, 351, 474, 348, 273, 401, 476, 288, 266, 447, 240, 745, 521, 414, 450, 425, 368, 302, 272, 508, 412, 609, 450, 418, 385, 320, 252, 320, 531, 316, 316, 166, 166, 715, 505, 539, 103, 348, 348, 379, 351, 531];
const IDX = new Map([...CH].map((c, i) => [c, i]));
/** The width of `s` set in `face` at `size` px, with `track` em of letter-spacing (kerning off, 1.5% spare). */
const tw = (s, face, size, track = 0) => {
  const disp = ADV[face + "D"], k = disp ? clamp((size - 14) / 18, 0, 1) : 0;
  let u = 0, n = 0;
  for (const c of String(s)) { const i = IDX.get(c), a = ADV[face][i], d = disp ? disp[i] : a; u += a > 0 ? a * (1 - k) + d * k : 560; n++; }
  return (u / 1000) * size * 1.012 + track * size * n;
};

// ── small helpers ──────────────────────────────────────────────────────────────────────────
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const n2 = (x) => Math.round(x * 100) / 100;
const n1 = (x) => Math.round(x * 10) / 10;
const sum = (a) => a.reduce((s, x) => s + x, 0);
const style = (o) => Object.entries(o).map(([k, v]) => `${k}:${v}`).join(";");
/** A deterministic random stream per shot, so every render of a shot draws the same page. */
const rng = (key) => {
  let h = 2166136261;
  for (const c of String(key)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => { h = (h + 0x6d2b79f5) | 0; let t = h; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
};
/** Typesetting, not editing: straight quotes become the printer's curly ones. */
const curly = (s) => String(s ?? "")
  .replace(/(\w)'(\w)/g, "$1’$2").replace(/(\s|^|[(“‘—])'/g, "$1‘").replace(/'/g, "’")
  .replace(/(\s|^|[(‘—])"/g, "$1“").replace(/"/g, "”");
const words = (s) => curly(String(s ?? "").replace(/\s+/g, " ").trim()).split(" ").filter(Boolean);
/** A word as the narration and the page can both be compared on. */
const nrm = (s) => String(s ?? "").toLowerCase().replace(/[’‘]/g, "'").replace(/^[^\w$%]+|[^\w%]+$/g, "");
/** A page token as the voice would say it: of a dash-joined pair ("endless—45,000"), the figure. */
const said = (tok) => { const parts = String(tok).split(/[—–]/); return nrm(parts.find((x) => /\d/.test(x)) ?? parts.at(-1)); };

// ── figures: digits and spelled-out numbers ────────────────────────────────────────────────
// A spelled-out number is a figure ("fifty miles", "seventy-two inches", "one thousand four
// hundred miles"): it is one unit with the digits the voice may say instead ("50 miles"). A lone
// "one" is a figure only before a unit or a scale ("one minute", "one hundred"); before anything
// else it is the pronoun ("each one's", "a strong one", "one of the largest"). Ordinals are words.
const SMALL = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40,
  fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const SCALE = { hundred: 100, thousand: 1e3, million: 1e6, billion: 1e9 };
const UNIT = /^(cents?|pounds?|ounces?|miles?|inch(es)?|dollars?|years?|days?|weeks?|months?|minutes?|hours?|zones?|feet|foot|yards?|percent|times|parcels?|orders?|cars?)$/;
const wordNum = (w) => {
  const k = nrm(w);
  if (k in SMALL) return { v: SMALL[k] };
  if (k in SCALE) return { s: SCALE[k] };
  const [a, b, c] = k.split("-");
  return c == null && b && SMALL[a] >= 20 && SMALL[a] % 10 === 0 && SMALL[b] > 0 && SMALL[b] < 10 ? { v: SMALL[a] + SMALL[b] } : null;
};
/** A digit token's figure as the voice and the page compare it: "$1,000,000" → "$1000000", "1," → "1". */
const digitKey = (tok) => { const m = said(tok).match(/[$]?\d[\d,.:]*\d%?|[$]?\d%?/); return m ? m[0].replace(/,/g, "") : null; };
/** The figures in a run of words: per word, null or {key, a, b} (the unit's first and last word).
 *  `brk(i)` says word i starts a new cell or block, which a spelled number never crosses. */
function figUnits(list, brk = () => false) {
  const out = new Array(list.length).fill(null);
  for (let i = 0; i < list.length;) {
    const w = String(list[i]);
    if (/\d/.test(w)) { const key = digitKey(w); if (key) out[i] = { key, a: i, b: i }; i++; continue; }
    if (!wordNum(w)) { i++; continue; }
    // a spelled number: number words, "and" between a scale and a smaller number, never past punctuation
    let j = i, total = 0, cur = 0, any = false;
    for (; j < list.length; j++) {
      if (j > i && brk(j)) break;
      const x = String(list[j]), n = wordNum(x);
      if (!n) { if (j > i && nrm(x) === "and" && any && cur % 100 === 0 && cur >= 100 && wordNum(list[j + 1] ?? "")?.v != null && !/[,.;:]$/.test(list[j - 1])) continue; break; }
      if (n.v != null) cur += n.v; else if (n.s === 100) cur = (cur || 1) * 100; else { total += (cur || 1) * n.s; cur = 0; }
      any = true;
      if (/[,.;:!?)”"’]$/.test(x)) { j++; break; }
    }
    while (j - 1 > i && nrm(list[j - 1]) === "and") j--;
    const v = total + cur, next = nrm(list[j] ?? "");
    if (j - i === 1 && nrm(w) === "one" && !UNIT.test(next)) { i = j; continue; }   // the pronoun
    for (let k = i; k < j; k++) out[k] = { key: String(v), a: i, b: j - 1 };
    i = j;
  }
  return out;
}
/** What a word is compared on: a figure's first word by its value ("#50"), its other words as
 *  its continuation ("~50"), any other word as said. */
const cmpKeys = (list, units) => list.map((w, i) => (units[i] ? (units[i].a === i ? "#" : "~") + units[i].key : said(w)));
const keyLen = (k) => String(k).replace(/^\$/, "").length;
const uid = (job) => String(job.id ?? "x").replace(/[^\w-]/g, "");
const EASE = "cubic-bezier(0.45, 0, 0.2, 1)";

// ── which object a source is ───────────────────────────────────────────────────────────────
// Period dress only for real pre-1920 primary sources (the Act, A Visit to Sears 1914, the Joint
// Committee report 1914, the 1917 catalogue, The Cosmopolitan 1904, the Congressional Record,
// Printers' Ink 1918). Anything else, and anything the house made, is a modern object.
const PERIOD = /Parcel Post Act|Statutes at Large|Visit to Sears|Joint Committee|Cosmopolitan|Congressional Record|Printers.? Ink|catalogue|\b1[89]\d\d\b/i;
const MODERN = /USPS|United States Postal Service|Inspector General|\.json|Amazon|house design|Hubricon|worksheet|\b(19[2-9]\d|20\d\d)\b/i;
const HOUSE = /Hubricon['’]s|house design|worksheet|this film|film['’]s own|your own reports/i;
const periodOf = (src) => PERIOD.test(String(src ?? "")) && !MODERN.test(String(src ?? ""));

// ── the narration ──────────────────────────────────────────────────────────────────────────
/** The page's tokens matched to the spoken words, in order (a longest common subsequence). A
 *  match counts when it has a matched neighbour or is a figure of two or more characters, so a
 *  lone "the" or "pounds" elsewhere in the narration never steers the highlighter. */
function align(tokens, spoken, brk) {
  const A = cmpKeys(tokens, figUnits(tokens, brk)), sw = spoken.map((w) => w.w), B = cmpKeys(sw, figUnits(sw)), n = A.length, m = B.length;
  const fig = (k) => /^[#~]/.test(k) && keyLen(k.slice(1)) >= 2;
  const out = new Map();
  if (!n || !m) return out;
  const L = Array.from({ length: n + 1 }, () => new Int16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    L[i][j] = A[i] && A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const pairs = [];
  for (let i = 0, j = 0; i < n && j < m;) {
    if (A[i] && A[i] === B[j] && L[i][j] === L[i + 1][j + 1] + 1) { pairs.push([i, j]); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  const has = new Set(pairs.map(([i, j]) => `${i}:${j}`));
  for (const [i, j] of pairs) {
    const nb = has.has(`${i - 1}:${j - 1}`) || has.has(`${i + 1}:${j + 1}`);
    if (nb || fig(A[i])) out.set(i, spoken[j].t);
  }
  return out;
}

/** When each figure is first spoken in the shot, by its value (two characters or more: "$50",
 *  "1913", "fifty" → "50"); a one-digit figure is only placed by its words (align). */
function figureOnsets(spoken) {
  const map = new Map(), sw = spoken.map((w) => w.w), units = figUnits(sw);
  units.forEach((u, i) => { if (u && u.a === i && keyLen(u.key) >= 2 && !map.has(u.key)) map.set(u.key, spoken[i].t); });
  return map;
}

/** The figures on a page the narration licenses, token by token (toks: page words in reading
 *  order; brk: a new cell or block). Returns per token null (not a figure) or the second it may
 *  be read: -0.4 for a figure the voice said before this shot (job.known; a recall is not a
 *  reveal), its onset for one said in this shot, Infinity for one it never says here: that one is
 *  never readable at any moment of the shot (an unspoken figure, or one a later shot speaks). */
function licence(job, toks, brk, matched) {
  const list = toks.map((t) => t.t), units = figUnits(list, brk), cmp = cmpKeys(list, units);
  const spans = (v) => { const ws = words(String(v ?? "")); return cmpKeys(ws, figUnits(ws)); };
  /** every place on the page a value is printed whole (its words in order) */
  const find = (want, fn) => {
    if (!want.some((k) => /^#/.test(k))) return;
    for (let i = 0; i + want.length <= cmp.length; i++) if (want.every((k, d) => cmp[i + d] === k)) fn(i, i + want.length - 1);
  };
  const knownKeys = new Set(Object.keys(job.known || {}));
  // the figures said earlier: printed whole as they were said, or (two characters or more) by value
  const knownTok = new Set(), knownVal = new Set();
  for (const v of Object.values(job.known || {})) {
    const want = spans(v);
    want.forEach((k) => { if (/^#/.test(k) && keyLen(k.slice(1)) >= 2) knownVal.add(k.slice(1)); });
    find(want, (a, b) => { for (let i = a; i <= b; i++) knownTok.add(i); });
  }
  // the figures this shot reveals that the film had not said before land on their onsets, even
  // where an earlier fact happens to share the value ("$50" insured, then a "$50" price edge)
  const revealAt = new Map(), revealVal = new Map();
  for (const r of job.reveals || []) {
    if (knownKeys.has(r.key)) continue;
    const want = spans(r.value);
    want.forEach((k) => { if (/^#/.test(k) && keyLen(k.slice(1)) >= 2 && !revealVal.has(k.slice(1))) revealVal.set(k.slice(1), r.t); });
    find(want, (a, b) => { for (let i = a; i <= b; i++) if (!revealAt.has(i)) revealAt.set(i, r.t); });
  }
  const onsets = figureOnsets(job.words || []);
  return units.map((u, i) => {
    if (!u) return null;
    const span = Array.from({ length: u.b - u.a + 1 }, (_, k) => u.a + k);
    const fresh = span.some((k) => revealAt.has(k)) || revealVal.has(u.key);
    // each figure lands on its own word: its aligned onset, else its value's first onset in the shot,
    // else (no word found) the reveal's time. A reveal's time is its first word's, so "July 12,
    // 2026" must not land "2026" on "July".
    const own = span.map((k) => matched?.get(k)).filter((t) => t != null);
    const rv = [...span.map((k) => revealAt.get(k)), revealVal.get(u.key)].filter((t) => t != null);
    const here = own.length ? Math.min(...own) : keyLen(u.key) >= 2 && onsets.has(u.key) ? onsets.get(u.key) : rv.length ? Math.max(...rv) : null;
    if (!fresh && (span.every((k) => knownTok.has(k)) || (keyLen(u.key) >= 2 && knownVal.has(u.key)))) return { at: -0.4, here, unit: u };
    return { at: here ?? Infinity, here, unit: u };
  });
}

/** The highlighter's clock: when it reaches and leaves each word of the target. Spoken words are
 *  passed as they are said; the words between are swept at a steady hand's pace; the run of
 *  spoken words stops at a long silence (the narrator has moved on). */
function strokeClock(toks, anchors, fallbackAt, v = 1300) {
  // toks: [{X, w}] cumulative x along the stroke and width (sheet px)
  const keep = [];
  for (const i of [...anchors.keys()].sort((a, b) => a - b)) {
    const t = anchors.get(i), prev = keep.at(-1);
    if (prev && (t <= prev.t || t - prev.t > 2.5)) { if (t - prev.t > 2.5) break; continue; }
    keep.push({ i, t });
  }
  const s = new Array(toks.length), e = new Array(toks.length);
  if (!keep.length) keep.push({ i: 0, t: fallbackAt });
  const a0 = keep[0];
  for (let i = 0; i < toks.length; i++) {
    const k = keep.findIndex((a) => a.i >= i);
    if (k === 0) s[i] = a0.t - (toks[a0.i].X - toks[i].X) / v;          // before the first spoken word
    else if (k > 0) {                                                       // between two spoken words
      const a = keep[k - 1], b = keep[k], aEnd = Math.min(b.t, a.t + Math.max(0.15, toks[a.i].w / v));
      const span = toks[b.i].X - (toks[a.i].X + toks[a.i].w);
      s[i] = i === b.i ? b.t : aEnd + ((toks[i].X - (toks[a.i].X + toks[a.i].w)) / Math.max(1, span)) * (b.t - aEnd);
      if (i === a.i) s[i] = a.t;
    } else {                                                                // after the last one
      const z = keep.at(-1), zEnd = z.t + Math.max(0.15, toks[z.i].w / v);
      s[i] = i === z.i ? z.t : zEnd + (toks[i].X - (toks[z.i].X + toks[z.i].w)) / v;
    }
  }
  for (let i = 0; i < toks.length; i++) {
    if (i > 0) s[i] = Math.max(s[i], e[i - 1]);
    const next = i + 1 < toks.length ? s[i + 1] : Infinity;
    e[i] = Math.max(s[i] + 0.06, Math.min(next, s[i] + Math.max(0.12, toks[i].w / v)));
  }
  return { s, e };
}

/** A highlighter stroke's outline: a chisel nib's slanted ends, edges that wander a little. */
function nib(r, wpx) {
  const cut = (px) => n2((100 * px) / Math.max(40, wpx)), k = Math.max(4, Math.round(wpx / 80)), pts = [];
  const top = () => n2(r() * 10), bot = () => n2(100 - r() * 10);
  pts.push(`${cut(5 + r() * 7)}% ${top()}%`);
  for (let i = 1; i < k; i++) pts.push(`${n2((100 * i) / k)}% ${top()}%`);
  pts.push(`${n2(100 - cut(1 + r() * 3))}% ${top()}%`, `100% ${n2(35 + r() * 25)}%`, `${n2(100 - cut(4 + r() * 7))}% ${bot()}%`);
  for (let i = k - 1; i >= 1; i--) pts.push(`${n2((100 * i) / k)}% ${bot()}%`);
  pts.push(`${cut(r() * 3)}% ${bot()}%`, `0% ${n2(40 + r() * 25)}%`);
  return `polygon(${pts.join(",")})`;
}

/** One stroke in a box (sheet px), revealed along `marks` [[t, x]] (x from the box's left). */
function stroke(css, name, r, box, marks) {
  const t0 = marks[0][0], t1 = marks.at(-1)[0], dur = Math.max(0.05, t1 - t0);
  const kf = marks.map(([t, x]) => `${n2((100 * (t - t0)) / dur)}% { clip-path: inset(-30% ${n2(clamp(100 - (100 * x) / box.w, 0, 100))}% -30% 0); }`);
  css.push(`@keyframes ${name} { ${kf.join(" ")} }`);
  return `<i class="mk" style="left:${n1(box.x)}px;top:${n1(box.y)}px;width:${n1(box.w)}px;height:${n1(box.h)}px;` +
    `--rot:${n2((r() - 0.5) * 0.6)}deg;animation:${name} ${n2(dur)}s linear ${n2(t0)}s both"><b style="clip-path:${nib(r, box.w)}"></b></i>`;
}

/** A word's text with its figures wrapped: each lands when it is first spoken (blurred till then);
 *  `blue` marks the money figure the line lands on. */
function figured(tok, at, blue, blueAt = at) {
  if (at == null) return esc(tok);
  // the figure's own characters land (a spelled number's letters); trailing punctuation stays ink.
  // One the voice never says here is never readable: it holds under a blur too deep to read.
  const m = String(tok).match(/^(.*?)([$]?\d[\d,.:%]*\d%?|[$]?\d%?)(.*)$/) || String(tok).match(/^([^\p{L}]*)([\p{L}-]*\p{L})(.*)$/u) || [null, "", tok, ""];
  const soft = !Number.isFinite(at) || at >= 900;
  const cls = soft ? "fig fig-soft" : `fig${blue ? " fig-money" : ""}${at <= -0.3 ? " fig-said" : ""}`;
  const st = soft ? "" : ` style="--ft:${n2(at)}${blue && blueAt !== at ? `;--fb:${n2(blueAt)}` : ""}"`;
  return `${esc(m[1])}<span class="${cls}"${st}>${esc(m[2])}</span>${esc(m[3])}`;
}

// ── the camera ─────────────────────────────────────────────────────────────────────────────
// base.css's rig pushes 1% of scale a second about --cam-origin and drifts −8 px a second. A pose
// places sheet point P at screen point Q at on-screen scale S, composed for the rig as it stands at
// time tc; a hold keeps the inner camera still so the rig's own motion carries the frame, and the
// last segment adds a slow push on top of it, so the camera never stops.
/** The label slot as shots.mjs labels() draws it for this job (x 160, last baseline at 960, at most
 *  1150 px wide: a rule, the source line in one or two lines, the honesty label), with 16 px of air
 *  above it. Paper never sits under it unless a tight frame must, and then the flag darkens it. */
function slotOf(job) {
  const src = ["document", "table", "receipt"].includes(job.kind) ? String(job.params?.source ?? "").replace(/,?\s*as recorded in \S+\.json/i, "").trim() : "";
  const honest = job.label === "proof" || job.label === "demo";
  if (!src && !honest) return { x0: 150, x1: 1770, y0: 990, y1: 1080 };
  const wsrc = src ? tw(src, "inter", 28) : 0, lines = src ? Math.max(1, Math.ceil(wsrc / 1150)) : 0;
  const w = Math.min(1150, Math.max(lines ? wsrc / lines : 0, honest ? 980 : 0));
  return { x0: 150, x1: 175 + w, y0: Math.round(960 - (20 + 36 * lines + (honest ? 36 : 0)) - 16), y1: 980 };
}
let BAND = { x0: 150, x1: 1320, y0: 846, y1: 980 };
// base.css's rig as it now stands: a linear push from scale 1 to 1 + min(1% × duration, 6%) over the
// shot, about --cam-origin, and no drift unless a kind sets --cam-drift (this one does not). The
// poses are composed against it, so a match cut lands where it is aimed. (Set per shot by camera().)
let RIG_D = 10;
const rigAt = (t) => ({ k: 1 + Math.min(0.01 * RIG_D, 0.06) * clamp(t / RIG_D, 0, 1), d: 0 });
const n4 = (x) => Math.round(x * 10000) / 10000;
/** The inner (pre-rig) transform of pose p: translate then scale, origin 0 0. */
function inner(p, O) {
  const { k, d } = rigAt(p.tc);
  const s = p.S / k, qx = O.x + (p.Q.x - O.x) / k - d, qy = O.y + (p.Q.y - O.y) / k;
  return { s, tx: qx - s * p.P.x, ty: qy - s * p.P.y };
}
/** A sheet box (x, y, w, h) on screen at time t, with the inner camera at pose p (tilt ignored). */
function onScreen(box, p, O, t) {
  const m = inner(p, O), { k, d } = rigAt(t);
  const f = (x, y) => ({ x: O.x + k * (m.tx + m.s * x - O.x + d), y: O.y + k * (m.ty + m.s * y - O.y) });
  const a = f(box.x, box.y), b = f(box.x + box.w, box.y + box.h);
  return { x0: a.x, y0: a.y, x1: b.x, y1: b.y };
}
/** The establishing frame: the whole page, ~62% of the frame (a modern sheet ~70%), its foot clear
 *  of the label slot. A small sheet is brought up to that size rather than left a card in the dark. */
function establishing(W, H, frac = 0.62, label = 0, foot = 822) {
  // with a desk label the page's head stays low enough for the label (one line or two) to stand
  // above it inside title-safe; its foot stays above the label slot
  const top = label ? 160 + 37 * label : 110;
  const SE = clamp(Math.min((frac * 1920) / W, (foot - top) / H, 1.45), 0.42, 1.45);
  const y = Math.max(Math.min(452 + (label ? 40 : 0), foot - (SE * H) / 2), top + (SE * H) / 2);
  return { SE, E: { P: { x: W / 2, y: H / 2 }, S: SE, Q: { x: 992, y } } };
}

/** The camera's path. G: W, H, P (the line's point), maxS, move, and either visits (the plan's
 *  waypoints, resolved: [{arrive, cx, cy, box, label}], opening, endPush) or the line's stroke
 *  times (strokeStart, strokeEnd, track). Returns the poses, the keyframes and the flag. */
function camera(job, G, css) {
  const sec = job.seconds, end = sec + 1.0, id = uid(job), r = rng(job.id + ":cam");
  RIG_D = Math.max(0.5, sec);
  BAND = G.band || slotOf(job);
  const FOOT = Math.min(822, BAND.y0 - 14);                 // where a sheet's foot may rest
  const { W, H, P } = G, { SE, E } = establishing(W, H, G.frac, G.hasLabel, FOOT);
  // the line: the page at 85–90% of the frame's width (a modern sheet 80%), a corner and its shadow in frame
  const ST = clamp(((G.read ?? 0.865) * 1920) / W, 0.95, G.maxS ?? 1.5);
  // a reading frame on a line at cy: the page's foot above the label slot if it can be. A line
  // near the top of a tall page settles smaller so the whole sheet stands above the slot when
  // that keeps the type legible (≥ 40 px, ≥ 72% of the reading scale); a sheet too tall for that
  // keeps its reading scale, its foot runs under the slot, and the flag puts the label on dark.
  // The line read is never lower than 180 px above the slot (clear of the flag's falloff).
  const minS = (G.minS ?? 0.9), LOW = Math.min(700, BAND.y0 - 180);
  const read = (cy) => {
    const S = ST, qy = FOOT - S * (H - cy);
    if (qy >= 300) return { S, y: Math.min(qy, LOW) };
    const fit = (FOOT - 100) / H;
    if (fit < S && fit >= Math.max(G.fitS ?? minS, 0.72 * S)) return { S: fit, y: Math.min(FOOT - fit * (H - cy), LOW), fit: true };
    return { S, y: clamp(110 + S * cy, 300, Math.min(640, LOW)) };
  };
  const rT = read(P.y);
  const T = { P, S: rT.S, Q: { x: 960 + rT.S * (P.x - W / 2), y: rT.y } };
  const poses = [];
  const at = (t, q, tc = t, tight = false) => poses.push({ P: q.P, S: q.S, Q: { ...q.Q }, t, tc, tight, fit: !!q.fit });
  const hold = (t) => { if (t > poses.at(-1).t + 0.02) poses.push({ ...poses.at(-1), t, hold: true }); };   // shares Q
  const drift = (q, tc) => at(end, { P: q.P, S: q.S * 1.03, Q: { x: q.Q.x - 14, y: q.Q.y + 4 } }, tc, q.tight);
  let tiltA = -0.6, tiltB = sec * 0.5, O = { x: 960, y: 500 }, move = G.move;
  if (G.visits?.length) {
    // the editors' waypoints: a spline through them, each reached 0.1 s before its word
    move = `visits:${G.opening}`;
    const V = G.visits;
    const vPose = (v, tight) => tight ? { P: { x: v.cx, y: v.cy }, S: Math.min(ST * 1.32, 2.1), Q: { x: 960, y: 470 } }
      : v.label ? { P: E.P, S: E.S * 1.08, Q: { x: E.Q.x, y: E.Q.y + 16 } }
      : (() => { const q = read(v.cy); return { P: { x: P.x, y: v.cy }, S: q.S, Q: { x: 960 + q.S * (P.x - W / 2), y: q.y }, fit: q.fit }; })();
    const seen = (v, p) => { if ((p.S < 0.9 * ST && !p.fit) || p.tight) return false; const q = onScreen(v.box, p, O, v.arrive); return q.x0 > 170 && q.x1 < 1750 && q.y0 > 110 && q.y1 < LOW + 40; };
    let i0 = 0, first = null;
    if (G.opening === "tight") { at(-0.6, vPose(V[0], true), -0.6, true); if (V[0].arrive <= 0.6) i0 = 1; }
    else at(-0.6, E);
    for (let i = i0; i < V.length; i++) {
      const v = V[i], prev = poses.at(-1);
      if (seen(v, prev)) continue;
      let start = Math.max(prev.t + 0.2, v.arrive - 1.8);
      if (v.arrive - start < 1.2) start = v.arrive - 1.2;
      if (start < prev.t + 0.05) continue;
      hold(start); first ??= start;
      at(v.arrive, vPose(v, false)); tiltB = v.arrive;
    }
    tiltA = first ?? -0.6;
    const last = poses.at(-1);
    // the end push arrives on the cut (a match cut is judged on the last frame), then keeps creeping
    if (G.endPush && G.endPush.from < sec - 0.6) {
      const f0 = Math.max(G.endPush.from, last.t + 0.1), f1 = Math.max(sec - 0.04, f0 + 0.9);
      hold(f0); at(f1, G.endPush.pose); poses.at(-1).fixed = true;
      at(Math.max(end, f1 + 0.3), { ...G.endPush.pose, S: G.endPush.pose.S * 1.02 }, f1); poses.at(-1).fixed = true;
    }
    else drift(last, last.t);
  } else if (move === "pull") {
    // open tight on the line (it racks into focus as it is spoken), then pull out to the page
    const tight = { P, S: Math.min(ST * 1.3, 2.0), Q: { x: 960, y: 470 } };
    const wide = { P: E.P, S: E.S * 1.08, Q: { x: E.Q.x, y: E.Q.y + 20 } };
    O = tight.Q;
    at(-0.6, tight, -0.6, true);
    const out0 = Math.max(G.strokeEnd + 0.25, 1.4), out1 = Math.min(Math.max(out0 + 1.8, sec * 0.7), end - 0.3);
    if (out1 - out0 >= 1.2) { hold(out0); at(out1, wide); at(end, { ...wide, S: wide.S * 0.975 }, out1); tiltA = out0; tiltB = out1; }
    else { at(end, { ...tight, S: tight.S * 0.96 }, -0.6, true); tiltA = -0.6; tiltB = end; }
  } else {
    const arrive = clamp(G.strokeStart - 0.1, 0.6, sec - 0.4);
    O = G.track ? { x: 960, y: 470 } : T.Q;
    at(-0.6, E);
    let start = Math.max(-0.4, arrive - (G.track ? 2.3 : 2.8));
    if (arrive - start < 1.2) start = Math.max(-0.6, arrive - 1.2);
    hold(start);
    tiltA = start; tiltB = arrive;
    if (G.track) {
      const S = Math.min(ST * 1.22, 1.9), a = { P: G.track.a, S, Q: { x: 960, y: 470 } }, b = { P: G.track.b, S, Q: { x: 960, y: 470 } };
      const t1 = Math.min(Math.max(G.strokeEnd + 0.05, arrive + 1.2), end - 0.1);
      at(arrive, a, arrive, true); at(t1, b, t1, true);
      if (end - t1 >= 1.4) at(end, T, t1); else at(end, { ...b, S: S * 1.02 }, t1, true);
    } else {
      at(arrive, T);
      drift(poses.at(-1), arrive);
    }
  }
  // the label slot stays clear: a composed pose whose paper would reach under it, rig and all,
  // is lifted; only a tight frame (on the line) may cover it, and then the flag cuts the light
  const page = { x: 0, y: 0, w: W, h: H };
  // (the projected foot runs ~20 px below the flat estimate under the tilt and the lens)
  const covers = (q) => q.x0 < BAND.x1 && q.x1 > BAND.x0 && q.y1 + 20 > BAND.y0;
  // a pose whose own sheet would reach under the slot is lifted as far as its line may rise. Only
  // its own frame counts: lifting a pose because the move INTO it passes the slot (from a covering
  // pose) threw f18's last line to the top and its heading out of frame. Between two poses the foot
  // moves monotonically (scale and translate share one easing), so the poses decide.
  for (let pass = 0; pass < 3; pass++) for (let i = 0; i < poses.length; i++) {
    const p = poses[i];
    if (p.fixed) continue;                                       // a match cut's pose is where it is aimed
    const q = onScreen(page, p, O, Math.max(p.t, 0));
    if (!covers(q)) continue;
    const room = p.Q.y - (p.tight ? 300 : 260);                 // how far the line may rise
    p.Q.y -= clamp(q.y1 + 20 - BAND.y0, 0, Math.max(0, room));
  }
  const t0 = poses[0].t, dur = end - t0, name = `dcam-${id}`;
  const kf = poses.map((p, i) => {
    const m = inner(p, O), still = poses[i + 1]?.hold;
    return `${n2((100 * (p.t - t0)) / dur)}% { transform: translate(${n1(m.tx)}px, ${n1(m.ty)}px) scale(${n4(m.s)}); animation-timing-function: ${still ? "linear" : EASE}; }`;
  });
  css.push(`@keyframes ${name} { ${kf.join(" ")} }`);
  // the page's tilt: steep while the page is seen whole, flatter as the camera cranes over it
  // (a fee card's extract lies a degree and a half further askew under its clip)
  const rz = G.rz || 0;
  const tilt = [`rotateX(${n1(10 + r() * 3)}deg) rotateY(${n1(-2.5 - r() * 1.5)}deg) rotateZ(${n1(rz - (0.5 + r() * 0.4))}deg)`,
    `rotateX(${n1(4 + r() * 1.5)}deg) rotateY(${n1(-1 - r() * 0.6)}deg) rotateZ(${n1(rz - (0.2 + r() * 0.2))}deg)`];
  if (move === "pull" || poses[0].tight) tilt.reverse();
  // the flag follows the sheet's foot, not the poses: the path is sampled every 0.1 s (each segment
  // eased as its keyframes are), and the light is cut 0.3 s before the foot reaches the slot and
  // restored 0.3 s after it leaves, so the label never stands on paper mid-move
  const mats = poses.map((p) => inner(p, O));
  const bez = (u) => { // cubic-bezier(0.45, 0, 0.2, 1) progress at time fraction u
    let lo = 0, hi = 1;
    for (let i = 0; i < 24; i++) { const m = (lo + hi) / 2, x = 3 * (1 - m) ** 2 * m * 0.45 + 3 * (1 - m) * m * m * 0.2 + m ** 3; if (x < u) lo = m; else hi = m; }
    const m = (lo + hi) / 2; return 3 * (1 - m) * m * m + m ** 3;
  };
  const footAt = (t) => {
    let i = poses.findIndex((p) => p.t > t);
    if (i < 0) i = poses.length - 1; if (i === 0) i = 1;
    if (poses.length < 2) { const m = mats[0], { k } = rigAt(t); return { x0: O.x + k * (m.tx - O.x), x1: O.x + k * (m.tx + m.s * W - O.x), y1: O.y + k * (m.ty + m.s * H - O.y) }; }
    const a = poses[i - 1], b = poses[i], u = clamp((t - a.t) / Math.max(0.001, b.t - a.t), 0, 1), e = b.hold ? u : bez(u);
    const A = mats[i - 1], B = mats[i], sc = A.s + (B.s - A.s) * e, tx = A.tx + (B.tx - A.tx) * e, ty = A.ty + (B.ty - A.ty) * e, { k } = rigAt(t);
    return { x0: O.x + k * (tx - O.x), x1: O.x + k * (tx + sc * W - O.x), y1: O.y + k * (ty + sc * H - O.y) };
  };
  const spans = [];
  for (let t = t0; t <= t0 + dur + 0.001; t += 0.1) {
    if (!covers(footAt(t))) continue;
    if (spans.length && t - spans.at(-1)[1] <= 0.75) spans.at(-1)[1] = t; else spans.push([t, t]);
  }
  const flag = spans.length > 0;
  if (flag) {
    const tE = t0 + dur, f = (t) => Math.max(0, ...spans.map(([a, b]) => (t >= a && t <= b ? 1 : t < a ? clamp(1 - (a - t) / 0.3, 0, 1) : clamp(1 - (t - b) / 0.3, 0, 1))));
    const ts = [...new Set([t0, tE, ...spans.flatMap(([a, b]) => [a - 0.3, a, b, b + 0.3])].map((t) => n2(clamp(t, t0, tE))))].sort((x, y) => x - y);
    css.push(`@keyframes dflag-${id} { ${ts.map((t) => `${n2(clamp((100 * (t - t0)) / dur, 0, 100))}% { opacity: ${n2(f(t))}; }`).join(" ")} }`);
  }
  return {
    poses, ST, SE, O, flag, flagH: Math.round(1080 - BAND.y0 + 6), move: move + (G.track && move === "push" ? "+track" : ""),
    vars: {
      "--cam-origin": `${n1(O.x)}px ${n1(O.y)}px`, "--cx": `${n1(P.x)}px`, "--cy": `${n1(P.y)}px`,
      "--cam-path": `${name} ${n2(dur)}s linear ${n2(t0)}s both`,
      "--flag": flag ? `dflag-${id} ${n2(dur)}s linear ${n2(t0)}s both` : "none",
      "--t0": tilt[0], "--t1": tilt[1], "--tilt-at": `${n2(Math.max(-0.6, tiltA))}s`, "--tilt-dur": `${n2(Math.max(0.6, tiltB - tiltA))}s`,
    },
  };
}

/** Depth of field that follows the camera: per row, keyframes of blur and opacity at each pose,
 *  by the row's distance in lines from the row the camera is on (a far pose sees deeper focus). */
function depthOfField(css, cam, rowsY, lh, name, focus, pins = []) {
  const t0 = cam.poses[0].t, t1 = cam.poses.at(-1).t, dur = t1 - t0;
  const BL = [0, 1.5, 3, 5], OP = [1, 0.93, 0.86, 0.8];
  const scaleAt = (t) => { let s = cam.poses[0].S; for (const p of cam.poses) if (p.t <= t + 0.01) s = p.S; return s; };
  const sched = (focus && focus.length ? focus : cam.poses.map((p) => ({ t: p.t, y: p.P.y }))).filter((f) => f.t >= t0 - 0.01 && f.t <= t1 + 0.01);
  // Out of focus is drawn as the ink's own soft shadow (a text-shadow, painted with the glyphs)
  // rather than a filter on the line, which is what kept a moving page under 350 ms a frame:
  // blur σ px reads as a 2σ px shadow, the sharp glyph fading out as the blur grows.
  const ink = (pct) => `color-mix(in srgb, var(--dc-ink) ${Math.round(pct)}%, transparent)`;
  const look = (b, o) => (b <= 0.05 ? `color: ${ink(100 * o)}; text-shadow: 0 0 0 ${ink(0)}`
    : `color: ${ink(100 * o * clamp(1 - b / 1.5, 0, 1))}; text-shadow: 0 0 ${n1(2 * b)}px ${ink(100 * o * clamp(0.75 + b / 12, 0, 1))}`);
  return rowsY.map((y, ri) => {
    // a pinned row (an address, a phrase once swiped) stays in the focus band from its pin on
    const pin = pins[ri] ?? Infinity;
    const at = (f) => {
      const d = Math.min(3, Math.round(Math.abs(y - f.y) / lh)), depth = clamp((scaleAt(f.t) / cam.ST) ** 2, 0.2, 1.1);
      return f.t >= pin - 0.001 ? { t: f.t, b: 0, o: 1 } : { t: f.t, b: n1(BL[d] * depth), o: n2(1 - (1 - OP[d]) * Math.min(1, depth)) };
    };
    const pts = sched.slice();
    if (pin > t0 && pin < t1) {
      const before = [...sched].reverse().find((f) => f.t < pin) || sched[0];
      pts.push({ t: Math.max(t0, pin - 0.35), y: before.y }, { t: pin, y: before.y });
      pts.sort((a, b) => a.t - b.t);
    }
    const vals = pts.map(at);
    if (vals.every((v) => v.b === vals[0].b && v.o === vals[0].o)) return vals[0].b || vals[0].o < 1 ? look(vals[0].b, vals[0].o).replace(/: /g, ":") : "";
    css.push(`@keyframes ${name}-${ri} { ${vals.map((v) => `${n2(clamp((100 * (v.t - t0)) / dur, 0, 100))}% { ${look(v.b, v.o)}; animation-timing-function: ${EASE}; }`).join(" ")} }`);
    return `animation:${name}-${ri} ${n2(dur)}s linear ${n2(t0)}s both`;
  });
}

// ── the plan on the page: visits, marks, figures ──────────────────────────────────────────
/** Find a phrase among the page's words (the first occurrence at or after `from`, else anywhere). */
function locate(text, toks, from = 0) {
  const want = words(text).map(nrm).filter(Boolean);
  if (!want.length) return null;
  const hit = (i) => want.every((w, k) => toks[i + k] && nrm(toks[i + k].t) === w);
  for (let i = from; i + want.length <= toks.length; i++) if (hit(i)) return [i, i + want.length - 1];
  for (let i = 0; i < from && i + want.length <= toks.length; i++) if (hit(i)) return [i, i + want.length - 1];
  return null;
}
const boxOf = (toks, a, b) => {
  const ts = toks.slice(a, b + 1), x0 = Math.min(...ts.map((t) => t.x)), y0 = Math.min(...ts.map((t) => t.y));
  return { x: x0, y: y0, w: Math.max(...ts.map((t) => t.x + t.w)) - x0, h: Math.max(...ts.map((t) => t.y + t.h)) - y0 };
};

/** Everything a page shot needs once its words are laid out (toks in sheet px, reading order,
 *  each {t, x, w, y, h, size, line, ri, label?}): the plan's visits found on the page (or the
 *  line at `on`), each marked phrase's stroke on its words, every figure's time, the camera. */
function plan(job, M, css) {
  const p = job.params || {}, spoken = job.words || [], toks = M.toks, id = uid(job);
  const brk = M.brk || (() => false);
  const matched = align(toks.map((t) => t.t), spoken, brk);
  // the line (or row) that matters is what the voice reads: align it on its own, so a word printed
  // earlier on the page ("plus" in the row above) never takes its onset
  const tm = align(M.target.map((i) => toks[i].t), spoken, (n) => brk(M.target[n]) || M.target[n] - 1 !== M.target[n - 1]);
  M.target.forEach((i, n) => { if (tm.has(n)) matched.set(i, tm.get(n)); else matched.delete(i); });
  // what the narration licenses: every figure's second (said before: sharp from the cut; said
  // here: on its word; never said here: never readable)
  const lic = licence(job, toks, brk, matched);
  const fig = (i) => lic[i] != null;
  // the visits: the editors' own, or the line at `on`
  const visits = [];
  let from = 0;
  for (const v of p.visits || []) {
    const rg = locate(v.text, toks, from);
    if (!rg) continue;
    from = rg[1] + 1;
    visits.push({ rg, at: +v.at || 0, mark: !!v.mark && !toks[rg[0]].label });
  }
  const covered = visits.some((v) => M.target.some((i) => i >= v.rg[0] && i <= v.rg[1]));
  if (!covered && M.target.length) for (const g of M.groups || [M.target]) visits.push({ rg: [g[0], g.at(-1)], idx: g, at: null, mark: true, implicit: true });
  // the strokes' clocks: spoken words passed as they are said; an explicit mark lands its key word
  // on its time and starts no earlier than the camera's arrival allows
  const clock = new Map();
  for (const v of visits.filter((x) => x.mark)) {
    const idx = v.idx || Array.from({ length: v.rg[1] - v.rg[0] + 1 }, (_, k) => v.rg[0] + k);
    let X = 0;
    const path = idx.map((i, n) => { if (n && toks[i].line !== toks[idx[n - 1]].line) X += 40; const o = { X, w: toks[i].w }; X += toks[i].w + 0.28 * toks[i].size; return o; });
    const anchors = new Map();
    // a word is passed as it is said; a figure (which may be printed more than once) as it is said here
    idx.forEach((i, n) => {
      const at = matched.has(i) ? matched.get(i) : fig(i) && lic[i].here != null ? lic[i].here : undefined;
      if (at != null) anchors.set(n, at);
    });
    let c;
    if (v.implicit) {
      const reveal = (job.reveals || []).find((rv) => Math.abs(rv.t - (job.on ?? -9)) < 0.25);
      const before = visits.filter((x) => x.implicit && x.end != null).at(-1);
      let fb = before ? before.end + 0.05 : job.on ?? Math.min(1.5, job.seconds * 0.3);
      if (!anchors.size && reveal) { const n = idx.findIndex((i) => nrm(toks[i].t) === nrm(String(reveal.value).split(" ")[0])); if (n > 0) fb -= path[n].X / 1300; }
      c = strokeClock(path, anchors, Math.max(0.05, fb));
      v.at = c.s[0];
    } else {
      let key = -1, best = 0.3;
      anchors.forEach((t, n) => { if (Math.abs(t - v.at) <= best) { best = Math.abs(t - v.at); key = n; } });
      const A = key >= 0 ? new Map([...anchors].filter(([n]) => n >= key)) : new Map([[0, v.at]]);
      c = strokeClock(path, A, v.at);
      const T0 = v.at - 0.55, k = key >= 0 ? key : 0;
      for (let n = 0; n < k; n++) c.s[n] = T0 + ((path[n].X - path[0].X) / Math.max(1, path[k].X - path[0].X)) * (c.s[k] - T0);
      for (let n = 0; n < idx.length; n++) { if (n) c.s[n] = Math.max(c.s[n], c.e[n - 1]); c.e[n] = Math.max(c.s[n] + 0.06, Math.min(c.s[n + 1] ?? Infinity, c.s[n] + Math.max(0.12, toks[idx[n]].w / 1300))); }
    }
    idx.forEach((i, n) => clock.set(i, { s: c.s[n], e: c.e[n] }));
    v.end = c.e.at(-1);
  }
  // without the editors' waypoints, a figure the voice reads off the page before the line draws
  // the camera to it as it is said (the reading camera)
  if (!(p.visits || []).length) {
    const first = Math.min(...visits.filter((v) => v.mark).map((v) => v.at));
    let last = -9;
    toks.forEach((t, i) => {
      if (t.label || M.target.includes(i) || !matched.has(i) || !fig(i) || keyLen(lic[i].unit.key) < 2) return;
      const at = matched.get(i);
      if (at >= 1.0 && at <= first - 1.5 && at - last >= 1.4) { visits.push({ rg: [i, i], at, mark: false, auto: true }); last = at; }
    });
  }
  visits.forEach((v) => { v.arrive = v.at - 0.1; });
  visits.sort((a, b) => a.at - b.at);
  // a figure is read when the voice has said it: before the shot (sharp from the cut) or in it (on
  // its word). One it never says here stays under the blur for the whole shot, whatever the
  // highlighter or the camera does (a02 showed "$50" seven seconds before its word).
  const figTime = (i) => (fig(i) ? lic[i].at : null);
  // the money figure the line lands on turns blue: the main mark's figures (units stay ink)
  const main = visits.find((v) => v.implicit) || visits.filter((v) => v.mark).find((v) => M.target.some((i) => i >= v.rg[0] && i <= v.rg[1])) || visits.find((v) => v.mark);
  const cand = [];
  const pool = visits.some((v) => v.implicit) ? visits.filter((v) => v.implicit) : main ? [main] : [];
  for (const v of pool) for (let i = v.rg[0]; i <= v.rg[1]; i++) {
    const t = toks[i].t;
    if (!fig(i) || lic[i].unit.a !== i || (M.cell != null && toks[i].j !== M.cell)) continue;
    const after = toks[lic[i].unit.b + 1]?.t || "";
    if (/\$\d/.test(t) || /^(cents?|¢|dollars?)\b/i.test(after)) cand.push(i);
  }
  const ref = job.on ?? main?.at ?? 0;
  const pick = cand.filter((i) => figTime(i) < job.seconds).sort((a, b) => Math.abs(figTime(a) - ref) - Math.abs(figTime(b) - ref))[0];
  const blue = new Set();
  if (pick != null) for (let k = lic[pick].unit.a; k <= lic[pick].unit.b; k++) blue.add(k);
  // the blue blooms on the figure's word when it is said here, else as the stroke reaches it
  const blueAt = (i) => (lic[i]?.here ?? (clock.has(i) ? clock.get(i).s + 0.1 : main?.at ?? 0));
  return { visits, clock, figTime, blue, blueAt, matched, lic };
}

/** Where the lens is focused over time: the first pose's point, then each visit's line, racked over
 *  the half second before it is reached (a mark without a camera move still pulls focus to it). */
function focusPlan(cam, P, M) {
  const page = M.toks.filter((t) => !t.label), top = Math.min(...page.map((t) => t.y + t.h / 2));
  const out = [{ t: cam.poses[0].t, y: Math.max(top, cam.poses[0].P.y) }];
  for (const v of P.visits) {
    const b = boxOf(M.toks, v.rg[0], v.rg[1]), y = M.toks[v.rg[0]].label ? top : b.y + b.h / 2;
    const t = Math.max(out.at(-1).t + 0.05, v.arrive - 0.45);
    if (Math.abs(y - out.at(-1).y) < 1) continue;
    out.push({ t, y: out.at(-1).y }, { t: Math.max(t + 0.05, v.arrive), y });
  }
  out.push({ t: cam.poses.at(-1).t, y: out.at(-1).y });
  return out;
}

/** The strokes: one per line of each marked phrase, hugging its words with a 10–12 px overshoot. */
function strokesHTML(job, M, P, css) {
  const mr = rng(job.id + ":nib"), id = uid(job), out = [];
  for (const v of P.visits.filter((x) => x.mark)) {
    const idx = v.idx || Array.from({ length: v.rg[1] - v.rg[0] + 1 }, (_, k) => v.rg[0] + k);
    const lines = new Map();
    for (const i of idx) { const l = M.toks[i].line; if (!lines.has(l)) lines.set(l, []); lines.get(l).push(i); }
    for (const [l, all] of lines) {
      // a figure that never lands is not swiped: an amber bar over a blur reads as a hidden word
      const soft = (i) => (P.figTime(i) ?? 0) >= 900;
      const ids = all.slice();
      while (ids.length && soft(ids[0])) ids.shift();
      while (ids.length && soft(ids.at(-1))) ids.pop();
      if (!ids.length) continue;
      const a = M.toks[ids[0]], b = M.toks[ids.at(-1)], ov = Math.max(10, 0.22 * a.size);
      const box = { x: a.x - ov, y: a.y + (a.h - a.size) / 2 + 0.1 * a.size, w: b.x + b.w - a.x + 2 * ov, h: 0.92 * a.size };
      const c = (i) => P.clock.get(i);
      const marks = [[c(ids[0]).s - 0.03, 0]];
      for (const i of ids) marks.push([c(i).s, M.toks[i].x - a.x + ov * 0.6], [c(i).e, M.toks[i].x + M.toks[i].w - a.x + ov]);
      marks.push([c(ids.at(-1)).e + 0.04, box.w]);
      for (let k = 1; k < marks.length; k++) marks[k][0] = Math.max(marks[k][0], marks[k - 1][0] + 0.01);
      out.push(stroke(css, `mk-${id}-${out.length}`, mr, box, marks));
    }
  }
  return out.join("");
}

/** The camera for a planned page: the visits, or (without them) a move chosen for the line. */
function shoot(job, M, P, css, extra = {}) {
  const p = job.params || {};
  const explicit = P.visits.filter((v) => !v.implicit), main = P.visits.find((v) => v.implicit) || explicit.find((v) => v.mark) || P.visits[0];
  const tBox = boxOf(M.toks, M.target[0], M.target.at(-1));
  const Pt = { x: M.colCX, y: tBox.y + tBox.h / 2 };
  const vis = P.visits.map((v) => {
    const b = boxOf(M.toks, v.rg[0], v.rg[1]);
    return { arrive: v.arrive, cx: b.x + b.w / 2, cy: b.y + b.h / 2, box: b, label: !!M.toks[v.rg[0]].label };
  });
  if (explicit.length) {
    // a table enters whole (a card cut off at the frame's foot, its heading alone above it, reads as
    // an accident); a page may open tight on an early first word
    const opening = p.opening || (M.kind !== "table" && vis[0].arrive <= 0.4 ? "tight" : "page");
    return camera(job, { W: M.W, H: M.H, P: Pt, maxS: M.maxS, minS: M.minS, frac: M.frac, read: M.read, rz: M.rz, fitS: M.fitS, hasLabel: new Set(M.toks.filter((t) => t.label).map((t) => t.y)).size, visits: vis, opening, endPush: extra.endPush }, css);
  }
  // no plan: the line's own move (pull out from it, track along it, slide a page on, or push)
  const start = main?.at ?? (job.on || 1), end = main?.end ?? start + 1;
  const tRows = [...new Set(M.target.map((i) => M.toks[i].line))];
  const trackable = M.kind === "doc" && end - start >= 1.2 && tRows.length <= 3 && M.obj !== "clip";
  const a = M.toks[M.target[0]], b = M.toks[M.target.at(-1)];
  const track = trackable ? {
    a: { x: M.textX + clamp(a.x - M.textX + 0.32 * M.m, 0.3 * M.m, 0.55 * M.m), y: a.y + a.h / 2 },
    b: { x: M.textX + clamp(b.x + b.w - M.textX - 0.32 * M.m, 0.45 * M.m, 0.7 * M.m), y: b.y + b.h / 2 },
  } : null;
  const h = [...String(job.id)].reduce((s, c) => s + c.charCodeAt(0), 0);
  const move = start < 1.9 ? "pull" : track ? "push" : M.obj === "clip" || h % 2 ? "slide" : "push";
  return camera(job, { W: M.W, H: M.H, P: Pt, maxS: M.maxS, minS: M.minS, frac: M.frac, read: M.read, rz: M.rz, fitS: M.fitS, hasLabel: new Set(M.toks.filter((t) => t.label).map((t) => t.y)).size, strokeStart: start, strokeEnd: end, track, move, endPush: extra.endPush }, css);
}

// ── the paper ──────────────────────────────────────────────────────────────────────────────
/** Foxing: a few faint age spots, placed by the shot's own seed (period stock only). */
function foxing(key, n = 3) {
  const r = rng(key + ":fox"), out = [];
  for (let i = 0; i < n; i++) {
    const x = n1(r() * 100), y = n1(r() * 100), s = Math.round(18 + r() * 80), a = n2(0.05 + r() * 0.07);
    out.push(`radial-gradient(circle at ${x}% ${y}%, color-mix(in srgb, var(--sepia) ${Math.round(a * 100)}%, transparent) 0, color-mix(in srgb, var(--sepia) ${Math.round(a * 33)}%, transparent) ${Math.round(s * 0.45)}px, transparent ${s}px)`);
  }
  return out.join(",");
}
/** A torn foot: a random walk with uneven bites, never a regular zigzag. Scissor-cut sides and head. */
function tornEdge(key, W, H) {
  const r = rng(key + ":tear"), pts = [], j = (a) => (r() - 0.5) * 2 * a;
  const lean = j(4);
  for (let x = 0; x <= W; x += 30) pts.push([x, 2.5 + j(0.9) + (lean * x) / W]);
  for (let y = 0; y <= H - 30; y += 40) pts.push([W - 2 + j(0.8), y]);
  let y = H - 9, x = W;
  while (x > 0) {
    const step = 3 + r() * 9;
    y = clamp(y + j(2.2) + (H - 9 - y) * 0.18 + (r() < 0.07 ? -4 - r() * 5 : 0), H - 22, H - 1);
    pts.push([x, y]); x -= step;
  }
  pts.push([0, H - 8 + j(3)]);
  for (let yy = H - 30; yy >= 0; yy -= 40) pts.push([2 + j(0.8), yy]);
  return `polygon(${pts.map(([a, b]) => `${n1(clamp(a, 0, W))}px ${n1(clamp(b, 0, H))}px`).join(",")})`;
}
/** The object on the desk: the back sheet (its own shadow, a degree askew), the page (its contact
 *  and key shadows from one pre-blurred layer, no filters), and on it the type and the strokes. */
function pageHTML({ obj, dress, W, H, inner: body, key, slide, furniture = "", vars = {} }) {
  const r = rng(key + ":under");
  const rot = n2((r() < 0.5 ? -1 : 1) * (0.6 + r() * 0.6)), ux = Math.round(10 + r() * 10), uy = Math.round(8 + r() * 10);
  const modern = obj === "laser";
  // only a cut clipping has a ragged edge; a sheet's cut edge is straight (and a clip-path on a page
  // the camera moves costs a repaint of its whole area every frame)
  const clip = obj === "clip" ? `clip-path:${tornEdge(key, W, H)};` : "";
  const bg = modern ? "" : `background-image:${foxing(key)},var(--dc-age),url(/content/assets/film/paper.jpg);`;
  // a pad's sheet and an index card lie alone; a print has the sheet under it
  const under = obj === "clip" || dress === "index" || dress === "pad" ? "" : obj === "book" ? `<div class="dc-edges"></div>`
    : `<div class="dc-under" style="transform:translate(${ux}px, ${uy}px) rotate(${rot}deg)"></div>`;
  // a fee card's extract is clipped to its sheet: the clip sits over the head, a third in
  const clipObj = dress === "card" ? `<i class="dc-pclip" style="left:${Math.round(W * (0.12 + r() * 0.06))}px"><b></b></i>` : "";
  const v = Object.entries(vars).map(([k, x]) => `${k}:${x}`).join(";");
  return `<div class="dc-stack dc-o-${obj}${dress ? ` dc-d-${dress}` : ""}" style="width:${Math.round(W)}px;height:${Math.round(H)}px${v ? `;${v}` : ""}">${under}` +
    `<div class="dc-slide${slide ? " dc-slid" : ""}"${typeof slide === "number" ? ` style="animation-duration:${n2(Math.max(0.8, slide + 0.4))}s"` : ""}><div class="dc-shadow"></div>` +
    `<div class="dc-paper" style="${clip}${bg}"><div class="dc-fibre"></div>${furniture}${body}<div class="dc-light"></div></div>${clipObj}</div></div>`;
}

/** The desk label: what the film says the page is (its own words, never printed on the paper) and
 *  that the page was typeset. At x = 160, 48 px above the page in the establishing frame; it lives
 *  on the desk, so the camera can visit it. Returns its HTML and its words (sheet px). */
function deskLabel(parts, W, H, frac, foot = 822) {
  if (!parts.length) return { html: "", toks: [] };
  const one = establishing(W, H, frac, 1, foot);
  const two = parts.length > 1 && one.E.Q.x - (one.SE * W) / 2 + tw(parts.map(([t]) => t).join(" · "), "interSemi", 28, 0.12) > 1720;
  const { SE } = two ? establishing(W, H, frac, 2, foot) : one;
  const fs = 28 / SE, x0 = 0, lh = 1.3 * fs;
  const y0 = -(48 / SE) - (two ? 2 : 1) * lh;
  const toks = [];
  let x = x0, y = y0;
  parts.forEach(([text], pi) => {
    if (pi) { if (two) { x = x0; y += lh; } else x += 1.4 * fs; }
    for (const w of text.split(" ")) { const ww = tw(w, "interSemi", fs, 0.12); toks.push({ t: w, x, w: ww, y, h: lh, size: fs, line: `L${pi}`, ri: -1, label: true }); x += ww + tw(" ", "interSemi", fs, 0.12); }
  });
  const build = (figTime, fade = "") => {
    let k = 0;
    const html = parts.map(([text, dim]) => `<span${dim ? ` class="dl-dim"` : ""}>${text.split(" ").map((w) => { const i = k++, at = figTime(toks[i]); return at != null ? figured(w, at, false) : esc(w); }).join(" ")}</span>`).join(`<i></i>`);
    return `<p class="dc-desk${two ? " dl-two" : ""}" style="left:${n1(x0)}px;top:${n1(y0)}px;font-size:${n2(fs)}px;--at:-0.4">` +
      `<span class="dl-fade"${fade ? ` style="animation:${fade}"` : ""}>${html}</span></p>`;
  };
  return { toks, build };
}

/** The desk label stays on the desk: when a pose would carry it past the title-safe margins (or
 *  over the top edge), it dims out as the camera leaves it behind, and returns when it comes back. */
function labelFade(job, cam, ltoks, css) {
  if (!ltoks.length) return "";
  const box = boxOf(ltoks, 0, ltoks.length - 1);
  const ok = cam.poses.map((p) => { const q = onScreen(box, p, cam.O, Math.max(p.t, 0)); return q.x0 >= 150 && q.x1 <= 1770 && q.y0 >= 60 ? 1 : 0; });
  if (ok.every(Boolean)) return "";
  const t0 = cam.poses[0].t, dur = cam.poses.at(-1).t - t0, name = `dl-${uid(job)}`;
  css.push(`@keyframes ${name} { ${cam.poses.map((p, i) => `${n2((100 * (p.t - t0)) / dur)}% { opacity: ${ok[i]}; animation-timing-function: ${EASE}; }`).join(" ")} }`);
  return `${name} ${n2(dur)}s linear ${n2(t0)}s both`;
}

function frame(cam, page, label, css) {
  return `<style>${css.join("\n")}</style><div class="cam dc" data-move="${cam.move}" style="${style(cam.vars)}"><div class="rig"><div class="dc-push">` +
    `${label}${page}</div></div></div>${cam.flag ? `<div class="dc-flag" style="animation:${cam.vars["--flag"]};--flag-h:${cam.flagH}px"></div>` : ""}`;
}
const typesetNote = (src, house) => !house && !/^(typeset|redrawn) from/i.test(String(src).trim());

// ── document: doc-highlight and doc-clipping ───────────────────────────────────────────────
// Body sizes are set so the line the camera lands on reads at 50 to 65 px; set ragged right (at
// these sizes a justified column opens rivers), the rag evened by settle().
const DOC = {
  period: { face: "period", head: "periodBold", sub: "periodItalic", b: 46, lh: 68, m: 1100, padX: 128, padT: 112, padB: 128, indent: 2, gap: 0, hb: 46, hlh: 62, htrack: 0.08, hgap: 40, caps: true },
  modern: { face: "inter", head: "interSemi", sub: "inter", b: 42, lh: 62, m: 1060, padX: 120, padT: 108, padB: 120, indent: 0, gap: 28, hb: 50, hlh: 66, htrack: 0, hgap: 30, caps: false },
  clip: { face: "period", head: "periodBold", sub: "periodItalic", b: 41, lh: 56, m: 640, padX: 60, padT: 72, padB: 86, indent: 1.6, gap: 0, hb: 38, hlh: 52, htrack: 0.08, hgap: 28, caps: true },
  // the film's own rule or list, typed on a ruled index card: the rules fall on the type's baselines
  index: { face: "typed", head: "typed", sub: "typed", b: 42, lh: 68, m: 1060, padX: 112, padT: 120, padB: 104, indent: 0, gap: 0, hb: 46, hlh: 68, htrack: 0.02, hgap: 0, caps: false },
};

// ── what a modern source is, as an object (the critics: "eleven of the section's shots are the
// same flat white card"). A worksheet is a sheet torn from a ruled pad; the film's own rule and
// lists are typed index cards; a house layout (a P&L, a settlement report) is a ledger page whose
// figures column stays empty; a web page (a museum record, a company archive, Hubricon's own
// pages) is its printout; a fee card's extract is a laser print clipped to its sheet, a little
// askew; anything else (a report, an address) is a laser print with a printer's head rule. No
// dress adds a word to the page: the furniture is rules, a clip and the stock.
function dressOf(src) {
  const s = String(src ?? "");
  if (/worksheet|workbook/i.test(s)) return "pad";
  if (/as this film states it|this film['’]s own|film['’]s own|typeset for this film/i.test(s)) return "index";
  if (/house design/i.test(s)) return "ledger";
  if (/hubricon\.com|public-data case study|postalmuseum|Sears Archives|“Rural Free Delivery”/i.test(s)) return "web";
  if (/fee card|ratecard|Notice \d|Ground Advantage|fulfil?ment fee|FBA/i.test(s)) return "card";
  return "report";
}
/** A row worth keeping sharp whatever the lens does: an address the viewer must remember. */
const URLISH = /\b[\w-]+\.(com|org|gov|net|edu|io)\b|https?:|www\./i;

/** Body text: the breaks that spread the slack most evenly (least squared slack, a lone last
 *  word discouraged), so the rag is even. */
function settle(items, face, size, measure, indent = 0, balance = false, track = 0) {
  const n = items.length, w = items.map((it) => tw(it.t, face, size, track)), sp = tw(" ", face, size, track);
  const best = new Array(n + 1).fill(Infinity), prev = new Array(n + 1).fill(-1);
  best[0] = 0;
  for (let i = 0; i < n; i++) {
    if (best[i] === Infinity) continue;
    const lim = measure - (i === 0 ? indent : 0);
    let lw = -sp;
    for (let j = i; j < n; j++) {
      lw += sp + w[j];
      if (lw > lim + 1 && j > i) break;
      const slack = Math.max(0, lim - lw);
      let cost = j === n - 1 && !balance ? (j === i && n > 1 ? (lim * 0.4) ** 2 : 0) : slack * slack;
      if (balance && j < n - 1 && /[,;:]$/.test(items[j].t)) cost *= 0.3;
      if (best[i] + cost < best[j + 1]) { best[j + 1] = best[i] + cost; prev[j + 1] = i; }
    }
  }
  const cuts = [];
  for (let k = n; k > 0; k = prev[k]) cuts.unshift([prev[k], k]);
  return cuts.map(([a, b]) => items.slice(a, b));
}
/** Greedy breaking (headings). */
function wrap(items, face, size, measure, track = 0) {
  const sp = tw(" ", face, size, track), rows = [];
  let row = [], w = 0;
  for (const it of items) {
    const ww = tw(it.t, face, size, track);
    if (row.length && w + sp + ww > measure + 1) { rows.push(row); row = []; w = 0; }
    w += (row.length ? sp : 0) + ww; row.push(it);
  }
  if (row.length) rows.push(row);
  return rows;
}

/** Lines → paragraphs. A short first line is the page's heading. Lines that are a printed page's
 *  own rows flow as one paragraph and break where the source breaks. */
function paragraphs(L) {
  const len = L.map((l) => l.length), avg = sum(len) / Math.max(1, L.length), max = Math.max(0, ...len);
  const ends = (l) => /[.:;!?…]["”’)]?$/.test(l);
  const head = L.length > 1 && L[0].length <= 36 && /^[A-Z]/.test(L[0]) && !/[.,;:…]$/.test(L[0]) && L[0] !== L[0].toUpperCase();
  const flow = L.length >= 3 && avg >= 36 && max <= 72 && L.filter(ends).length <= L.length / 2;
  const list = !flow && L.length >= 3 && avg < 36;
  const paras = [];
  let cur = null;
  L.forEach((l, i) => {
    if (i === 0 && head) { paras.push({ segs: [0], head: true }); return; }
    if (!flow) { paras.push({ segs: [i] }); return; }
    if (!cur) { cur = { segs: [] }; paras.push(cur); }
    cur.segs.push(i);
    if (ends(l) && i + 1 < L.length && /^[A-Z“"‘]/.test(L[i + 1])) cur = null;
  });
  if (head && L.length === 2 && L[1] && L[1].length <= 44) paras[1].sub = true;
  return { paras, list, head };
}

const TYPESET = "Typeset from the source";

export function document(job) {
  const p = job.params || {};
  let L = (p.lines || []).slice(0, job.render?.max_lines || 9).map((l) => String(l ?? "").replace(/\s+/g, " ").trim());
  if (!L.length) return "";
  const src = String(p.source ?? ""), period = periodOf(src), house = HOUSE.test(src);
  const obj = p.clipping ? (period ? "clip" : "laser") : !period ? "laser" : /catalogue|Visit to Sears|guide/i.test(src) ? "book" : "sheet";
  const dress = obj === "laser" ? dressOf(src) : null;
  const S = { ...(obj === "clip" ? DOC.clip : period ? DOC.period : dress === "index" ? DOC.index : DOC.modern) };
  let target = clamp(p.line || 1, 1, L.length) - 1;
  // a house card's title is the film's own words: it goes on the desk, not on the paper
  let { paras, list, head } = paragraphs(L);
  const label = [];
  if (head && house && target > 0) {
    label.push([curly(L[0]).toUpperCase(), false]); L = L.slice(1); target = Math.max(0, target - 1);
    ({ paras, list } = paragraphs(L));
    paras = paras.map((q) => ({ segs: q.segs }));          // what is left is the card's own entries
  }
  const short = L.length <= 3 || list;
  if (obj === "laser" && short) {
    // a short modern sheet is not a card in the dark: its type is set up (48–56 px on screen at
    // rest) and its sheet keeps a page's width, the lines set from the grid's left
    S.b = Math.round(S.b * 1.1); S.lh = dress === "index" ? S.lh : Math.round(S.lh * 1.1);
  }
  if (list) {
    const hw = paras[0]?.head ? tw(S.caps ? L[0].toUpperCase() : L[0], S.head, S.hb, S.htrack) : 0;
    // (a modern list keeps a sheet's width; a ledger's width is its empty figures column's too)
    const floor = obj !== "laser" ? 520 : dress === "ledger" ? 600 : 900;
    S.m = Math.round(clamp(Math.max(hw, ...L.map((l) => tw(curly(l), S.face, S.b))) + 24, floor, Math.max(S.m, obj === "laser" ? 1060 : 0)));
  }
  // a line that stops mid-sentence is finished on the lines that complete it (at most two)
  const targets = new Set([target]);
  for (let i = target; i < Math.min(L.length - 1, target + 2) && !/[.,;:!?…]["”’)]?$/.test(L[i]) && /^[a-z]/.test(L[i + 1]); i++) targets.add(i + 1);

  // lay out every row: y, height, its words (each tagged with its source line), each word's x
  const rows = [];
  let y = 0;
  paras.forEach((para, pi) => {
    if (para.head) {
      let hb = S.hb;
      const ht = S.caps ? L[0].toUpperCase() : L[0];
      while (hb > 34 && tw(ht, S.head, hb, S.htrack) > S.m) hb -= 2;
      wrap(words(ht).map((t) => ({ t, seg: 0 })), S.head, hb, S.m, S.htrack).forEach((r) => { rows.push({ y, h: S.hlh, items: r, head: true, hb }); y += S.hlh; });
      y += S.hgap;
      return;
    }
    if (para.sub && obj !== "laser") {
      rows.push({ y, h: S.lh, items: words(L[para.segs[0]]).map((t) => ({ t, seg: para.segs[0] })), sub: true });
      y += S.lh;
      return;
    }
    const items = para.segs.flatMap((s) => words(L[s]).map((t) => ({ t, seg: s })));
    const ind = S.indent && !list && pi > 0 && !paras[pi - 1].head ? S.indent * S.b : 0;
    settle(items, S.face, S.b, S.m, ind).forEach((r, ri) => { rows.push({ y, h: S.lh, items: r, ind: ri === 0 ? ind : 0 }); y += S.lh; });
    if (pi < paras.length - 1) y += list ? 0 : S.gap;
  });
  if (!rows.length) return "";
  // a ledger page keeps an empty figures column at its right (the layout has no figures)
  const FIG = dress === "ledger" ? 380 : 0;
  let W = S.m + 2 * S.padX + FIG, H = S.padT + y + S.padB;
  // the stock's proportion: an index card is a card (near 5 by 3); no modern sheet is a strip
  if (dress === "index") H = Math.max(H, Math.round(W / 1.75));
  else if (obj === "laser") H = Math.max(H, Math.round(W * 0.5));
  const frac = obj === "laser" ? 0.70 : 0.62, rd = obj === "laser" ? 0.80 : 0.865;
  const DL = deskLabel(label, W, H, frac, Math.min(822, slotOf(job).y0 - 14));
  const toks = [...DL.toks];
  rows.forEach((row, ri) => {
    const f = row.head ? S.head : row.sub ? S.sub : S.face, size = row.head ? row.hb : S.b, track = row.head ? S.htrack : 0;
    const ww = row.items.map((it) => tw(it.t, f, size, track));
    const space = tw(" ", f, size) + track * size, nat = sum(ww) + space * (row.items.length - 1);
    let x = (row.head || row.sub) && obj !== "laser" ? (S.m - nat) / 2 : row.ind || 0;
    row.items.forEach((it, k) => { toks.push({ t: it.t, seg: it.seg, x: S.padX + x, w: ww[k], y: S.padT + row.y, h: row.h, size, line: ri, ri }); x += ww[k] + space; });
  });
  const tIdx = toks.map((t, i) => (!t.label && targets.has(t.seg) ? i : -1)).filter((i) => i >= 0);
  if (!tIdx.length) return "";
  const brk = (i) => i > 0 && (!!toks[i].label !== !!toks[i - 1].label || toks[i].seg !== toks[i - 1].seg || (toks[i].label && toks[i].line !== toks[i - 1].line));
  const M = { W, H, obj, kind: "doc", toks, target: tIdx, brk, frac, read: rd, rz: dress === "card" ? -1.4 : 0,
    colCX: S.padX + S.m / 2 + FIG / 2, textX: S.padX, m: S.m, maxS: obj === "clip" ? 1.45 : list ? 1.5 : 1.45, minS: 44 / S.b, fitS: 44 / S.b };   // a page read at under 44 px stays pushed in, its foot under the dark flag (e08 kept moving)
  const css = [], id = uid(job);
  const P = plan(job, M, css);
  const cam = shoot(job, M, P, css);
  const rowsY = rows.map((r) => S.padT + r.y + r.h / 2);
  // what the lens never loses: an address (from the cut), and a phrase once it is swiped
  const pins = rows.map((row, ri) => {
    if (row.items.some((it) => URLISH.test(it.t))) return -9;
    const ids = toks.map((t, i) => (t.ri === ri && !t.label ? i : -1)).filter((i) => i >= 0);
    const ats = P.visits.filter((v) => v.mark && ids.some((i) => i >= v.rg[0] && i <= v.rg[1] && (!v.idx || v.idx.includes(i)))).map((v) => v.arrive - 0.45);
    return ats.length ? Math.min(...ats) : null;
  });
  const dof = depthOfField(css, cam, rowsY, S.lh, `ddof-${id}`, focusPlan(cam, P, M), pins);
  const first = DL.toks.length;
  let k = first;
  const rowsHTML = rows.map((row, ri) => {
    const body = row.items.map(() => { const i = k++, t = toks[i].t, at = P.figTime(i); return at != null ? figured(t, at, P.blue.has(i), P.blueAt(i)) : esc(t); }).join(" ");
    const cls = ["dc-row", row.head ? "dc-head" : "", row.sub ? "dc-sub" : ""].filter(Boolean).join(" ");
    const st = [`top:${n1(row.y)}px`, `height:${row.h}px`, `line-height:${row.h}px`];
    if (row.ind) st.push(`padding-left:${n1(row.ind)}px`);
    if (row.head) st.push(`font-size:${row.hb}px`);
    if (row.head && !S.caps && S.face !== "typed") st.push("letter-spacing:-0.01em");
    if (dof[ri]) st.push(dof[ri]);
    return `<div class="${cls}" style="${st.join(";")}">${body}</div>`;
  }).join("");
  const body = strokesHTML(job, M, P, css) +
    `<div class="dc-text dc-${S.face}" style="left:${S.padX}px;top:${S.padT}px;width:${S.m}px;font-size:${S.b}px">${rowsHTML}</div>`;
  // the dress's furniture: rules on the stock (never a word)
  const fur = [], vars = {};
  if (dress === "index" || dress === "ledger") {
    // ruled lines on the type's baselines, from the first line to the foot
    const base = S.padT + Math.round(S.lh * 0.78);
    vars["--rule-y"] = `${base % S.lh}px`; vars["--rule-p"] = `${S.lh}px`;
    fur.push(`<i class="dc-ruled" style="top:${n1(S.padT - S.lh + Math.round(S.lh * 0.78))}px"></i>`);
    if (dress === "index") fur.push(`<i class="dc-headrule" style="top:${n1(S.padT - Math.round(S.lh * 0.22))}px"></i>`);
    if (dress === "ledger") {
      const fx = S.padX + S.m + 40;
      fur.push(`<i class="dc-figcol" style="left:${fx}px;width:${W - fx - S.padX * 0.6}px;top:${S.padT - 24}px;bottom:${S.padB * 0.6}px"></i>`);
    }
  } else if (dress) {
    fur.push(`<i class="dc-printrule" style="left:${S.padX}px;right:${S.padX}px;top:${Math.round(S.padT * 0.45)}px"></i>`);
    if (dress === "web") fur.push(`<i class="dc-printrule dc-foot" style="left:${S.padX}px;right:${S.padX}px;bottom:${Math.round(S.padB * 0.42)}px"></i>`);
  }
  const page = pageHTML({ obj, dress, W, H, inner: body, key: job.id, slide: cam.move === "slide", furniture: fur.join(""), vars });
  return frame(cam, page, DL.build ? DL.build((t) => P.figTime(toks.indexOf(t)), labelFade(job, cam, DL.toks, css)) : "", css);
}

// ── table: a typeset rate table (period) or a laser-printed card (modern) ─────────────────
const TB = {
  period: { face: "period", f: 42, cf: 28, cface: "period", ctrack: 0.12, ccaps: true, lead: true },
  modern: { face: "inter", f: 38, cf: 28, cface: "interSemi", ctrack: 0.06, ccaps: true, lead: false },
  typed: { face: "typed", f: 38, cf: 28, cface: "typed", ctrack: 0.06, ccaps: true, lead: false },
};

export function table(job) { return tableHTML(job, periodOf(job.params?.source) ? "period" : "modern", { nil: true }); }

function tableHTML(job, kind, opt = {}) {
  const p = job.params || {}, period = kind === "period";
  const src = String(p.source ?? ""), house = HOUSE.test(src);
  const dress = period ? null : opt.dress ?? dressOf(src);
  const S = { ...TB[dress === "index" ? "typed" : kind] };
  const rows = (p.rows || []).slice(0, job.render?.rows_max || 10).map((r) => (r || []).map((c) => curly(String(c ?? ""))));
  if (!rows.length) return "";
  const ncol = Math.max((p.columns || []).length, ...rows.map((r) => r.length));
  const cols = Array.from({ length: ncol }, (_, j) => curly(String((p.columns || [])[j] ?? "")));
  rows.forEach((r) => { while (r.length < ncol) r.push(""); });
  const R = clamp(p.row || 1, 1, rows.length) - 1;
  const C = p.cell ? clamp(p.cell, 1, ncol) - 1 : -1;
  const worksheet = rows.flat().filter((c) => !c.trim()).length >= rows.flat().length / 2;
  const numeric = cols.map((_, j) => j > 0 && rows.some((r) => r[j].trim()) && rows.every((r) => !r[j].trim() || (r[j].length <= 12 && /\d/.test(r[j]))));
  const lead = S.lead && ncol > 1 && rows.some((r) => r[0].trim());
  // a short table (three rows or fewer) is set up a size, so its sheet is a page in the frame and
  // not a strip in the dark; a header band whose every title is empty is not printed (two empty
  // rules read as a fault)
  const short = rows.length <= 3;
  const heads = cols.some((c) => c.trim());
  const f = short ? Math.round(S.f * 1.3) : S.f, cf = short ? 32 : S.cf;
  const lh = Math.round(f * 1.32), padX = short ? 32 : 26, padY = short ? 20 : 15, clh = Math.round(cf * 1.3), LEAD = lead ? 70 : 0;
  const cap = (c) => (S.ccaps ? c.toUpperCase().replace(/(\d)S\b/g, "$1s") : c);
  const nat = cols.map((c, j) => {
    const full = tw(cap(c), S.cface, cf, S.ctrack), wmax = Math.max(0, ...words(cap(c)).map((w) => tw(w, S.cface, cf, S.ctrack)));
    const hw = c.length <= 16 ? full : Math.max(wmax, full * 0.56);
    const cw = Math.max(0, ...rows.map((r) => tw(r[j], S.face, f)));
    return Math.max(hw, cw, worksheet ? 220 : 60) + 2 * padX + (j === 0 ? LEAD : 0);
  });
  const MAXW = short ? 1400 : 1320;
  let colW = nat.slice();
  if (sum(nat) > MAXW) {
    let lo = 200, hi = Math.max(...nat);
    for (let i = 0; i < 40; i++) { const mid = (lo + hi) / 2; if (sum(nat.map((w) => Math.min(w, mid))) > MAXW) hi = mid; else lo = mid; }
    colW = nat.map((w) => Math.min(w, lo));
  }
  // a modern sheet keeps a page's width: a narrow table's columns share out the difference
  const MINW = period ? 0 : 1000;
  if (sum(colW) < MINW) { const add = (MINW - sum(colW)) / ncol; colW = colW.map((w) => w + add); }
  const tableW = sum(colW);
  const measureOf = (j) => colW[j] - 2 * padX - (j === 0 ? LEAD : 0);
  const lines = (txt, j, size, face, track = 0) => settle(words(txt).map((t) => ({ t })), face, size, measureOf(j), 0, true, track).map((r) => r.map((i) => i.t).join(" "));
  const headLines = cols.map((c, j) => lines(cap(c), j, cf, S.cface, S.ctrack));
  const bodyLines = rows.map((r) => r.map((c, j) => lines(c, j, f, S.face)));
  const headH = heads ? Math.max(1, ...headLines.map((l) => l.length)) * clh + 30 : 14;
  const rowH = bodyLines.map((r) => Math.max(1, ...r.map((l) => l.length)) * lh + 2 * padY);
  const side = 100;
  let padT = dress === "pad" ? 120 : 92, padB = 104;
  const W = tableW + 2 * side, tx = side;
  // no sheet is a strip: a short table's page has a page's depth (the extra mostly below it)
  const bodyH = headH + sum(rowH), minH = period ? 0 : Math.round(W * 0.48);
  if (padT + bodyH + padB < minH) { const extra = minH - (padT + bodyH + padB); padT += Math.round(extra * 0.35); padB += extra - Math.round(extra * 0.35); }
  const colX = colW.map((_, j) => tx + sum(colW.slice(0, j)));
  const headY = padT, tTop = padT;
  let y = headY + headH;
  const rowY = [];
  rows.forEach((_, i) => { rowY.push(y); y += rowH[i]; });
  const H = y + padB;
  // the film's heading is a desk label; the table says it was typeset (unless its source does)
  const label = [];
  const hd = curly(String(p.heading ?? "")).trim();
  if (hd) label.push([hd.toUpperCase().replace(/(\d)S\b/g, "$1s"), false]);
  if (typesetNote(src, house) && !/redrawn|typeset/i.test(hd)) label.push([TYPESET.toUpperCase(), !!hd]);
  const frac = period ? 0.62 : 0.70, rd = period ? 0.865 : 0.80;
  const DL = deskLabel(label, W, H, frac, Math.min(822, slotOf(job).y0 - 14));
  // every word, in reading order (label, column heads, cells), with its place
  const toks = [...DL.toks];
  if (heads) headLines.forEach((ls, j) => ls.forEach((ln, k) => {
    const lw = tw(ln, S.cface, cf, S.ctrack);
    let x = colX[j] + (colW[j] - lw) / 2;
    for (const w of ln.split(" ")) { const ww = tw(w, S.cface, cf, S.ctrack); toks.push({ t: w, x, w: ww, y: headY + 15 + k * clh, h: clh, size: cf, line: `h${j}:${k}`, ri: 0, head: true, j }); x += ww + tw(" ", S.cface, cf, S.ctrack); }
  }));
  rows.forEach((r, i) => r.forEach((c, j) => bodyLines[i][j].forEach((ln, k) => {
    const lw = tw(ln, S.face, f);
    let x = numeric[j] ? colX[j] + colW[j] - padX - lw : colX[j] + padX;
    for (const w of ln.split(" ")) { const ww = tw(w, S.face, f); toks.push({ t: w, x, w: ww, y: rowY[i] + padY + k * lh, h: lh, size: f, line: `${i}:${j}:${k}`, ri: i + 1, i, j }); x += ww + tw(" ", S.face, f); }
  })));
  // the row the voice reads; a blank worksheet's row has no words, so its column heads stand in
  let tIdx = toks.map((t, n) => (t.i === R ? n : -1)).filter((n) => n >= 0);
  if (!tIdx.length) tIdx = toks.map((t, n) => (t.head && (C < 0 || t.j === C) ? n : -1)).filter((n) => n >= 0);
  if (!tIdx.length) tIdx = toks.map((t, n) => (t.head ? n : -1)).filter((n) => n >= 0);
  if (!tIdx.length) return "";
  let groups = [...new Set(tIdx.map((n) => toks[n].j))].map((j) => tIdx.filter((n) => toks[n].j === j));
  if (p.figures === "soft") groups = groups.filter((g) => toks[g[0]].j === 0);
  const cellKey = (t) => (t.label ? `L${t.line}` : t.head ? `h${t.j}` : `${t.i}:${t.j}`);
  const brk = (n) => n > 0 && cellKey(toks[n]) !== cellKey(toks[n - 1]);
  const M = { W, H, obj: period ? "sheet" : "laser", kind: "table", toks, target: tIdx, groups, brk, frac, read: rd, rz: dress === "card" ? -1.4 : 0,
    cell: C >= 0 ? C : null, colCX: tx + tableW / 2, maxS: 1.5, minS: 44 / f, fitS: 40 / f };
  const css = [], id = uid(job);
  const P = plan(job, M, css);
  // a value is typed on as it is spoken, the whole cell together (never a unit before its figure);
  // with type_values every value cell is; a row label keeps its place, its figures under blur. A
  // cell whose figures the voice said before this shot is printed whole from the cut (a recall).
  const cellIds = new Map();
  toks.forEach((t, n) => { if (t.i != null) { const k = `${t.i}:${t.j}`; if (!cellIds.has(k)) cellIds.set(k, []); cellIds.get(k).push(n); } });
  const cellAt = new Map(), typedBy = new Map();
  for (const [, ids] of cellIds) {
    const t = toks[ids[0]];
    if (t.j === 0) continue;
    const figs = ids.filter((n) => P.figTime(n) != null);
    if (!figs.length && !p.type_values) continue;
    if (figs.length && figs.every((n) => P.figTime(n) >= job.seconds)) continue;   // soft: it stays soft
    if (figs.length && figs.every((n) => P.figTime(n) < 0)) continue;               // said before: printed
    const said = ids.find((n) => P.matched.has(n));
    const at = figs.length ? Math.min(...figs.map((n) => P.figTime(n) - 0.1), said != null ? P.matched.get(said) - 0.1 : Infinity)
      : said != null ? P.matched.get(said) - 0.1 : P.clock.has(ids[0]) ? P.clock.get(ids[0]).s - 0.05 : Math.max(0, ...[...P.clock.values()].map((c) => c.e)) + 0.5;
    let t0 = at;
    ids.forEach((n) => { cellAt.set(n, t0); t0 += (toks[n].t.length + 1) / 26; });
    ids.forEach((n) => typedBy.set(n, t0));
  }
  // the highlighter never swipes a cell before its words are in: a stroke over a typed cell waits
  // for the cell to finish (an amber bar over nothing read as a fault)
  for (const v of P.visits.filter((x) => x.mark)) {
    const idx = v.idx || Array.from({ length: v.rg[1] - v.rg[0] + 1 }, (_, k) => v.rg[0] + k);
    const ready = Math.max(-9, ...idx.map((n) => (typedBy.has(n) ? typedBy.get(n) + 0.05 : P.figTime(n) != null && P.figTime(n) < 900 ? P.figTime(n) + 0.2 : -9)));
    const s0 = Math.min(...idx.map((n) => P.clock.get(n)?.s ?? Infinity));
    if (Number.isFinite(s0) && ready > s0) {
      const d = ready - s0;
      idx.forEach((n) => { const c = P.clock.get(n); if (c) P.clock.set(n, { s: c.s + d, e: c.e + d }); });
      v.end = (v.end ?? 0) + d;
    }
  }
  // the editors' end push: into the cell, until it fills the frame (a match cut). The cell's start
  // lands on the cut where the next shot's first figure stands (`end_push.to`, else the plan's
  // `focal`, else x 0.10, y 0.38: where a14's bars set "$320" on the grid's left), so the eye does
  // not jump the frame
  let endPush = null;
  if (p.end_push && p.end_push.from != null) {
    const er = clamp(p.end_push.row || 1, 1, rows.length) - 1, ec = clamp(p.end_push.cell || 1, 1, ncol) - 1;
    const ids = toks.map((t, n) => (t.i === er && t.j === ec ? n : -1)).filter((n) => n >= 0);
    if (ids.length) {
      const b = boxOf(toks, ids[0], ids.at(-1)), to = p.end_push.to || p.focal || [0.1, 0.38];
      const Sx = clamp(1100 / b.w, 1.6, 3.4), Sc = Math.min(Sx, (1920 * (0.92 - clamp(to[0], 0.08, 0.5))) / b.w);
      endPush = { from: +p.end_push.from, pose: { P: { x: b.x, y: b.y + b.h / 2 }, S: Math.max(1.4, Sc), Q: { x: 1920 * clamp(to[0], 0.08, 0.5), y: 1080 * clamp(to[1], 0.2, 0.7) } } };
    }
  }
  const cam = shoot(job, M, P, css, { endPush });
  const allY = [headY + headH / 2, ...rowY.map((ry, i) => ry + rowH[i] / 2)];
  // what the lens never loses: an address (from the cut), a phrase once swiped
  const pins = allY.map((_, ri) => {
    const ids = toks.map((t, n) => (!t.label && t.ri === ri ? n : -1)).filter((n) => n >= 0);
    if (ids.some((n) => URLISH.test(toks[n].t))) return -9;
    const ats = P.visits.filter((v) => v.mark && ids.some((n) => n >= v.rg[0] && n <= v.rg[1] && (!v.idx || v.idx.includes(n)))).map((v) => (P.clock.get(v.idx?.[0] ?? v.rg[0])?.s ?? v.arrive) - 0.45);
    return ats.length ? Math.min(...ats) : null;
  });
  const dof = depthOfField(css, cam, allY, Math.max(lh + 2 * padY, 60), `tdof-${id}`, focusPlan(cam, P, M), pins);
  const word = (n) => {
    const t = toks[n].t, at = cellAt.get(n), ft = P.figTime(n);
    if (at == null) return ft != null ? figured(t, ft, P.blue.has(n), P.blueAt(n)) : esc(t);
    // a figure is never typed a character at a time (half a figure is not a fact): it lands whole
    if (ft != null) return figured(t, Math.max(at + 0.1, ft), P.blue.has(n), Math.max(at + 0.1, P.blueAt(n)));
    return `<span class="tw${P.blue.has(n) ? " fig-blue" : ""}" style="--ft:${n2(at)}" data-type-at="${n2(at)}" data-type-cps="26">${esc(t)}</span>`;
  };
  const parts = [];
  parts.push(`<i class="tb-rule tb-double" style="top:${tTop - 8}px;left:${tx}px;width:${tableW}px"></i>`);
  if (heads) {
    const headHTML = headLines.map((l, j) => `<div class="tb-cell" style="left:${n1(colX[j])}px;width:${n1(colW[j])}px">${l.map(esc).join("<br>")}</div>`).join("");
    parts.push(`<div class="tb-row tb-cols" style="top:${headY}px;height:${headH}px;line-height:${clh}px;font-size:${cf}px;${dof[0]}">${headHTML}</div>`);
    parts.push(`<i class="tb-rule" style="top:${headY + headH}px;left:${tx}px;width:${tableW}px"></i>`);
  }
  rows.forEach((r, i) => {
    const cells = r.map((c, j) => {
      let extra = "";
      if (j === 0 && lead && c.trim() && r.slice(1).some((x) => x.trim())) {
        const last = bodyLines[i][0].at(-1) || "";
        const lx = padX + tw(last, S.face, f) + 16, rx = colW[0] - padX;
        if (rx - lx > 30) extra = `<i class="tb-lead" style="left:${n1(lx)}px;width:${n1(rx - lx)}px;top:${padY + (bodyLines[i][0].length - 1) * lh}px;height:${lh}px"></i>`;
      }
      if (!c.trim() && worksheet) extra = `<i class="tb-write" style="top:${padY}px;height:${lh}px"></i>`;
      // an empty cell in a printed table is the printer's dash, never a hole
      else if (!c.trim() && opt.nil && j > 0) extra = `<i class="tb-nil${numeric[j] ? " tb-nil-r" : ""}" style="top:${padY + lh / 2}px"></i>`;
      const html = bodyLines[i][j].map((ln, k) => toks.map((t, n) => (t.i === i && t.j === j && t.line === `${i}:${j}:${k}` ? n : -1)).filter((n) => n >= 0).map(word).join(" ")).join("<br>");
      return `<div class="tb-cell${numeric[j] ? " tb-num" : ""}" style="left:${n1(colX[j])}px;width:${n1(colW[j])}px;padding-top:${padY}px;padding-left:${padX}px;padding-right:${padX}px">${html}${extra}</div>`;
    }).join("");
    parts.push(`<div class="tb-row" style="top:${rowY[i]}px;height:${rowH[i]}px;line-height:${lh}px;${dof[i + 1]}">${cells}</div>`);
    if (i < rows.length - 1) parts.push(`<i class="tb-rule tb-hair" style="top:${rowY[i] + rowH[i]}px;left:${tx}px;width:${tableW}px"></i>`);
  });
  parts.push(`<i class="tb-rule tb-double tb-foot" style="top:${y + 4}px;left:${tx}px;width:${tableW}px"></i>`);
  colX.slice(1).forEach((x) => parts.push(`<i class="tb-vrule" style="left:${n1(x)}px;top:${tTop}px;height:${y - tTop}px"></i>`));
  const lights = (p.light || []).map((L, k, all) => {
    let box;
    if (L.rows?.length) {
      const a = clamp(Math.min(...L.rows), 1, rows.length) - 1, b = clamp(Math.max(...L.rows), 1, rows.length) - 1;
      box = { x: tx - 14, y: rowY[a] - 4, w: tableW + 28, h: rowY[b] + rowH[b] - rowY[a] + 8 };
    } else if (L.columns?.length) {
      const a = clamp(Math.min(...L.columns), 1, ncol) - 1, b = clamp(Math.max(...L.columns), 1, ncol) - 1;
      box = { x: colX[a] - 6, y: headY - 12, w: colX[b] + colW[b] - colX[a] + 12, h: y - headY + 24 };
    } else return "";
    const t1 = +L.at || 0, t2 = all[k + 1] ? +all[k + 1].at : job.seconds + 2, name = `tl-${id}-${k}`;
    css.push(`@keyframes ${name} { 0% { opacity: 0; } ${n2(Math.min(99, (100 * 0.5) / (t2 - t1 + 0.5)))}% { opacity: 1; } ${n2(Math.max(1, (100 * (t2 - t1)) / (t2 - t1 + 0.5)))}% { opacity: 1; } 100% { opacity: 0; } }`);
    return `<i class="tb-light" style="left:${n1(box.x)}px;top:${n1(box.y)}px;width:${n1(box.w)}px;height:${n1(box.h)}px;animation:${name} ${n2(t2 - t1 + 0.5)}s ease-in-out ${n2(t1 - 0.25)}s both"></i>`;
  }).join("");
  // the pad's furniture: rules at the rows' pitch down the whole sheet, a margin, the perforation
  const fur = [], vars = {};
  if (dress === "pad") {
    vars["--rule-p"] = `${rowH[0]}px`;
    fur.push(`<i class="dc-ruled" style="top:${n1(rowY[0] + rowH[0])}px"></i><i class="dc-margin" style="left:${tx - 30}px"></i><i class="dc-perf"></i>`);
  }
  const body = `${strokesHTML(job, M, P, css)}<div class="tb tb-${kind}${dress === "index" ? " tb-typed" : ""}" style="font-size:${f}px">${parts.join("")}</div>${lights}`;
  const lands = p.settle_at != null ? +p.settle_at : null;
  const page = pageHTML({ obj: M.obj, dress, W, H, inner: body, key: job.id, slide: lands != null ? lands : cam.move === "slide", furniture: fur.join(""), vars });
  return frame(cam, page, DL.build ? DL.build((t) => P.figTime(toks.indexOf(t)), labelFade(job, cam, DL.toks, css)) : "", css);
}

// ── quote: words that matter, as light ─────────────────────────────────────────────────────
/** When each word of the quotation is spoken: matched to the narration's own words, the words
 *  it does not say placed between their neighbours. */
function quoteTimes(job, ws, raw) {
  const spoken = job.words || [], sw = spoken.map((w) => w.w);
  const A = cmpKeys(ws, figUnits(ws)), B = cmpKeys(sw, figUnits(sw)), n = A.length, m = B.length;
  const t = new Array(n).fill(null), J = new Array(n).fill(null);
  if (n && m) {
    const L = Array.from({ length: n + 1 }, () => new Int16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      L[i][j] = A[i] && A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    for (let i = 0, j = 0; i < n && j < m;) {
      if (A[i] && A[i] === B[j] && L[i][j] === L[i + 1][j + 1] + 1) { t[i] = spoken[j].t; J[i] = j; i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
    }
  }
  // keep a match only inside a run (its neighbour matched the next spoken word too), or a long
  // word; a lone "the" three words early is a guess, and a guess can land a word before it is said
  const keepT = t.map((v, i) => (v != null && ((J[i - 1] != null && J[i - 1] === J[i] - 1) || (J[i + 1] != null && J[i + 1] === J[i] + 1) || A[i].length >= 6) ? v : null));
  for (let i = 0; i < n; i++) { t[i] = keepT[i]; if (raw && t[i] != null) raw.set(i, t[i]); }
  const known = t.map((v, i) => (v == null ? null : i)).filter((i) => i != null);
  if (!known.length) return ws.map((_, i) => 0.3 + i * 0.32);
  return t.map((v, i) => {
    if (v != null) return v;
    const a = known.filter((k) => k < i).at(-1), b = known.find((k) => k > i);
    if (a == null) return Math.max(0, t[b] - (b - i) * 0.14);      // just before its neighbour: never early
    if (b == null) return t[a] + (i - a) * 0.3;
    return t[a] + ((t[b] - t[a]) * (i - a)) / (b - a);
  });
}

/** The books and periodicals this film quotes from: set in italics wherever an attribution names them. */
const TITLES = ["A Visit to Sears, Roebuck and Co.", "Catalogues and Counters", "RFD: The Changing Face of Rural America", "The Crossroads of Freedom", "The Cosmopolitan", "Printers’ Ink", "Printers' Ink"];
function attribution(s, figure = (w) => w) {
  let out = esc(curly(s).toUpperCase().replace(/(\d)S\b/g, "$1s")).replace(/[$]?\d[\d,.]*\d|\d/g, (w) => figure(w));
  for (const t of TITLES) {
    const u = esc(curly(t).toUpperCase());
    out = out.split(u).join(`<i>${u}</i>`);
  }
  // "Quoted in A and B, Title": the title after the authors
  out = out.replace(/(QUOTED IN [^,<]+, )([^<,.][^<]*?)$/, (_, a, b) => `${a}<i>${b}</i>`);
  return out;
}

export function quote(job) {
  const p = job.params || {}, text = String(p.text ?? "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const ws = words(text);
  // one size system, set to fill a 1300 px measure centred on the frame: 120 px up to 8 words,
  // then the largest of 108 / 96 / 88 / 84 / 76 / 72 that sets the quotation in at most five lines
  const fits = (size) => { const n = settle(ws.map((t) => ({ t })), "quoteI", size, 1300, 0, true).length; return n <= 5 && n * size * 1.08 <= 600; };
  const size = ws.length <= 8 ? 120 : [108, 96, 88, 84, 76, 72].find((z) => (ws.length <= 20 || z <= 96) && fits(z)) ?? 72;
  const raw = new Map();
  const times = quoteTimes(job, ws, raw).map((t) => clamp(t, -0.3, job.seconds - 0.6));
  // a figure in the quotation lands on its own word; one the voice has not said (here or before)
  // stays a ghost of light for the whole shot
  const lic = licence(job, ws.map((t) => ({ t })), () => false, raw);
  // each word lands on its own onset; one spoken by 0.4 s is already landing at the cut (R1)
  const land = (t, i) => (lic[i] && !Number.isFinite(lic[i].at) ? 1e3 : t <= 0.4 ? -0.4 : t - 0.1);
  const html = ws.map((w, i) => `<span class="qt-w" style="--at:${n2(land(times[i], i))}">${esc(w)}</span>`).join(" ");
  // the attribution's figures follow the same rule (a year the film has not said is not printed)
  // (read as a whole, so a date said before, "December 1, 1914", is known with its day)
  const aw = p.attribution ? words(String(p.attribution)) : [];
  const alic = licence(job, aw.map((t) => ({ t })), () => false, null), aAt = new Map();
  aw.forEach((w, i) => { if (alic[i]) { const k = digitKey(w) ?? ""; aAt.set(k, Math.max(aAt.get(k) ?? -Infinity, alic[i].at)); } });
  const by = p.attribution ? attribution(p.attribution, (w) => {
    const at = aAt.get(digitKey(w) ?? "") ?? licence(job, [{ t: w }], () => false, null)[0]?.at;
    return at == null ? w : !Number.isFinite(at) ? `<span class="fig fig-soft">${w}</span>` : at > 0 ? `<span class="fig" style="--ft:${n2(at)}">${w}</span>` : w;
  }) : "";
  return `<div class="cam qt-cam"><div class="rig">` +
    `<div class="qt" style="--qs:${size}px">` +
    `<p class="qt-by" style="--at:-0.4"><i class="qt-rule"></i>${by ? `<span>${by}</span>` : ""}</p>` +
    `<blockquote class="qt-text"><span class="qt-mark" style="--at:${n2(land(times[0], 0) - 0.02)}">“</span>${html}</blockquote></div></div></div>`;
}

// ── receipt: the site's receipt as a laser-printed ledger (demo data only, and labelled so) ──
export function receipt(job) {
  const p = job.params || {}, list = p.rows || [];
  const rows = list.map((x) => [x.move, x.how, x.before, x.after, x.counts].map((c) => String(c ?? "")));
  if (p.total) rows.push([p.total_label || "This month, counted once", "", "", "", String(p.total)]);
  // a receipt is demo data, always: the label slot (shots.mjs, drawn after this) reads job.label
  if (!job.label) job.label = "demo";
  const ledger = {
    ...job,
    on: job.on ?? Math.min(job.seconds * 0.55, 0.6 + rows.length * 0.5),
    params: { heading: p.heading, columns: ["Move", "How we know", "Called before", "Measured after", "Counts"], rows, row: rows.length, cell: 5, source: "Hubricon receipt" },
  };
  return tableHTML(ledger, "modern");
}
