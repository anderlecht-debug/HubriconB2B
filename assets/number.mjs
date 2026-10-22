/* ============================================================================
   The number: how a Hubricon figure arrives on screen.

   A number on screen is a claim, so the rule is: every digit on screen is
   either true or visibly moving. Never a still, wrong figure.

   1. Magnitude first, precision last. Each digit is a wheel. All start
      spinning together and land left to right, so the size of the number is
      settled first and the last digit lands last. Precision arrives.
   2. Real growth when there is one. Given the real running values behind a
      figure (receipts adding up, orders accumulating), the number steps
      through those values and only those. Growth shown by its numbers.
   3. Nothing moves sideways. Every digit has its own fixed place from the
      first frame, sized to the digit it will end on, so the figure never
      jiggles or reflows while it counts, and the comma never jumps.
   4. One tick per change, at most twenty a second, slowing as the wheels
      settle: the sound of a watch movement, reported as cues for the film.
   5. Finished on the page before it ever moves. The figure is in the HTML as
      itself; with no script, or for a visitor who asked for less motion, it
      simply is the figure.

   Taken to 11 (the scoreboard's ladder), a figure can carry its receipt:
   7  A heartbeat: "The working" under the figure opens the rows it is made
      from, each one landing in turn. Native <details>: it opens with no script.
   8  It tells you what you did not ask: where the figure sits in its range,
      the 1-in-10 low to the 1-in-10 high, drawn to scale.
   10 It meets the scary moment first: the low end is printed, not hidden.
   11 Copy with its source: one click copies the figure as a citation, with
      its range, its label and its date, so it is quoted honestly elsewhere.
   In a film, numberReceiptSVG builds the working row by row, each value
   landing on its wheels, the total last: the figure showing its work.

   numberState(spec, at) is pure: the same spec and moment give the same
   frame, so a film rendered frame by frame and a page playing live agree.
   numberSVG draws a frame for the films; numberHTML and playNumber are the
   site's. Blue only for money and the leak (tone "money"); our own price
   and everything else is ink.
   ============================================================================ */

import { css, ms, ease, NIGHT, SOUND, FINISH, VIDEO } from "./tokens.mjs";
import { glyphWidth, CAP } from "./inter.mjs";

const PITCH = 1.1;                 // the distance between digits on a wheel, in ems: one line
const SPIN = 0.022;                // digits a millisecond while a wheel spins: fast enough to be a blur at any film size, never a readable wrong digit
const EDGE = 0.16;                 // the wheel's window fades over this share at top and bottom, just outside the capitals
const NUM = /(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?/;

// ---------------------------------------------------------------- reading the figure

/** The figure's characters, each a wheel (a digit) or fixed (everything else). */
export function parse(text) {
  const chars = [...String(text)];
  let wheel = 0;
  return chars.map((ch) => (/\d/.test(ch) ? { ch, digit: +ch, wheel: wheel++ } : { ch, digit: null, wheel: null }));
}

/** Format a value the way the figure's own number is written: same grouping, same decimals. */
export function formatLike(text, v) {
  const m = String(text).match(NUM);
  if (!m) throw new Error(`no number in "${text}"`);
  const decimals = m[2] ? m[2].length - 1 : 0, grouped = m[1].includes(",");
  const s = Math.abs(v).toFixed(decimals);
  const [int, frac] = s.split(".");
  const g = grouped ? int.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : int;
  return frac ? `${g}.${frac}` : g;
}

// ---------------------------------------------------------------- the schedule

function schedule(spec) {
  const slots = parse(spec.text);
  const wheels = slots.filter((s) => s.wheel !== null);
  const D = spec.duration ?? ms("count-ms"), start = spec.start ?? 0, fade = ms("mc-band-ms");
  const n = wheels.length;
  let series = null;
  if (spec.series) {
    if ((String(spec.text).match(new RegExp(NUM.source, "g")) || []).length !== 1) throw new Error("a series needs exactly one number in the text");
    const m = String(spec.text).match(NUM), numStart = String(spec.text).indexOf(m[0]);
    const strs = spec.series.map((v) => formatLike(spec.text, v));
    if (strs[strs.length - 1] !== m[0]) throw new Error(`the series ends on ${strs[strs.length - 1]}, not on the figure ${m[0]}`);
    if (strs.some((s) => s.length > m[0].length)) throw new Error("a series value is longer than the figure");
    const chars = [...String(spec.text)].length;
    series = { strs, from: [...String(spec.text).slice(0, numStart)].length, len: m[0].length, chars };
  }
  // the wheels land left to right, from just over half the count to its end. Each spins at one
  // steady speed, then settles across its last digit only, in the time that keeps the speed
  // continuous: the ease-out leaves at 1/0.16 of its average speed, so a settle of one digit
  // takes 6.25 / SPIN.
  const land = wheels.map((_, i) => D * (n > 1 ? 0.55 + 0.45 * (i / (n - 1)) : 1));
  const settle = Math.min(D * 0.5, (1 / bezierX1()) / SPIN);
  return { slots, wheels, D, start, fade, land, settle, series };
}

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const quadOut = (p) => 1 - (1 - p) * (1 - p);

/** The ease-out's first control point's x: its starting slope is 1 over this. */
function bezierX1() {
  return +css("ease-out").match(/\(([^,]+)/)[1];
}

/**
 * Where wheel i is at local time t, in digits: its final digit minus one, minus the steady spin
 * still to come, until the settle carries it the last digit home.
 */
function wheelPos(sc, i, t) {
  const d = sc.wheels[i].digit, from = sc.land[i] - sc.settle;
  if (t < from) return d - 1 - SPIN * (from - t);
  return d - 1 + ease("ease-out")(clamp01((t - from) / sc.settle));
}

/** Which series value is showing at local time t. */
function seriesIndex(sc, t) {
  const L = sc.series.strs.length;
  return Math.min(L - 1, Math.floor(quadOut(clamp01(t / sc.D)) * L));
}

// ---------------------------------------------------------------- the state at a moment

/**
 * spec: { text, series?, px?, weight?, tone?, numerals?, start?, duration?, finding? }
 * Returns { op, slots: [{ ch, kind: "fixed" | "wheel" | "char", a, b, frac, landed, shown, speed }], cues, end }.
 * `speed` is in digits a millisecond, for motion blur.
 */
export function numberState(spec, at = Infinity) {
  const sc = schedule(spec);
  const t = at - sc.start;
  const op = t === Infinity ? 1 : ease("ease-out")(clamp01(t / sc.fade));
  let shownSeries = null;
  if (sc.series && t < Infinity) {
    const s = sc.series.strs[seriesIndex(sc, Math.max(0, t))];
    shownSeries = s.padStart(sc.series.len, " ");
  }
  const slots = sc.slots.map((s, k) => {
    if (s.wheel === null) {
      if (shownSeries !== null && k >= sc.series.from && k < sc.series.from + sc.series.len) {
        const ch = shownSeries[k - sc.series.from];
        return { ch: s.ch, kind: "char", shown: ch === " " ? "" : ch };
      }
      return { ch: s.ch, kind: "fixed", shown: s.ch };
    }
    if (sc.series) {
      if (shownSeries === null) return { ch: s.ch, kind: "char", shown: s.ch, landed: true };
      const ch = shownSeries[k - sc.series.from];
      return { ch: s.ch, kind: "char", shown: ch === " " ? "" : ch, landed: t >= sc.D };
    }
    const i = s.wheel;
    if (t >= sc.land[i]) return { ch: s.ch, kind: "wheel", a: s.digit, b: (s.digit + 1) % 10, frac: 0, landed: true, speed: 0 };
    const p = wheelPos(sc, i, Math.max(0, t));
    const speed = Math.abs(wheelPos(sc, i, Math.max(0, t) + 1) - p);
    const a = ((Math.floor(p) % 10) + 10) % 10;
    return { ch: s.ch, kind: "wheel", a, b: (a + 1) % 10, frac: p - Math.floor(p), landed: false, speed };
  });
  return { op, slots, cues: cues(spec, sc), end: sc.start + sc.D };
}

/** The sound cues: a tick each time a digit changes, thinned to the tick's own limit. */
function cues(spec, sc) {
  const raw = [];
  if (sc.series) {
    let last = sc.series.strs[0];
    for (let t = 0; t <= sc.D; t += 2) {
      const s = sc.series.strs[seriesIndex(sc, t)];
      if (s !== last) { raw.push(t); last = s; }
    }
  } else {
    sc.wheels.forEach((_, i) => {
      let prev = Math.floor(wheelPos(sc, i, 0));
      for (let t = 2; t <= sc.land[i]; t += 2) {
        const f = Math.floor(wheelPos(sc, i, t));
        if (f !== prev) { raw.push(t); prev = f; }
      }
    });
  }
  raw.sort((a, b) => a - b);
  const gap = 1000 / SOUND.cues.tick.maxPerSecond, out = [];
  for (const t of raw) if (!out.length || t - out[out.length - 1].at + sc.start >= gap) out.push({ name: "tick", at: Math.round(sc.start + t) });
  if (spec.finding) out.push({ name: "reveal", at: Math.round(sc.start + sc.D) });
  return out;
}

// ---------------------------------------------------------------- layout

/** Each character's place, fixed for the whole count: x, width, in px. */
export function numberLayout(spec) {
  const px = spec.px ?? 216, weight = spec.weight ?? 600, tabular = spec.numerals === "tabular";
  const cut = spec.cut ?? (spec.paint === "css" ? "auto" : "display");
  let x = 0;
  const places = parse(spec.text).map((s) => {
    const w = glyphWidth(s.ch, px, weight, { tabular: tabular && s.wheel !== null, cut });
    const p = { x, w };
    x += w;
    return p;
  });
  return { places, width: x, height: px * 1.2, baseline: px * 0.95, px, weight };
}

// ---------------------------------------------------------------- the film's frame

const NIGHT_OF = Object.fromEntries(NIGHT);
const paint = (mode, ground) => (name) => (mode === "css" ? `var(--${name})` : css(ground === "night" ? NIGHT_OF[name] || name : name));
const r2 = (v) => Math.round(v * 100) / 100;
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * The figure at one moment, as an SVG. In a film (paint "inline") a digit moving
 * faster than FINISH's threshold is blurred along its travel, as a real shutter
 * would: half a frame of motion at 60 frames a second.
 *
 * Inside another drawing (a chart's label), pass `at: [x, y]`: the figure comes back
 * as a plain group placed there, not a nested <svg>, so no page CSS written for
 * charts ("svg { width: 100% }") can reach in and resize it.
 */
export function numberSVG(spec, at = Infinity, { fps = VIDEO.render.final.fps, id = "n", place = null } = {}) {
  const P = paint(spec.paint ?? "inline", spec.ground);
  const L = numberLayout(spec), st = numberState(spec, at);
  const fill = P(spec.tone === "money" ? "blue" : spec.tone === "quiet" ? "ink-3" : "ink");
  const px = L.px, pitch = px * PITCH, capTop = L.baseline - CAP * px, mid = (capTop + L.baseline) / 2;
  const winTop = mid - pitch / 2;
  const font = `font-family:${spec.paint === "css" ? "var(--font)" : "Inter Display, Inter, sans-serif"};font-size:${r2(px)}px;font-weight:${L.weight}`;
  const shutterMs = (1000 / fps) * (FINISH.motionBlur.shutterAngle / 360);
  let defs = "", body = "";
  st.slots.forEach((s, k) => {
    const { x, w } = L.places[k], cx = x + w / 2;
    if (s.kind === "fixed" || s.kind === "char") {
      if (s.shown) body += `<text x="${r2(cx)}" y="${r2(L.baseline)}" text-anchor="middle">${esc(s.shown)}</text>`;
      return;
    }
    if (s.landed) { body += `<text x="${r2(cx)}" y="${r2(L.baseline)}" text-anchor="middle">${s.a}</text>`; return; }
    const off = s.frac * pitch;
    // the window a wheel shows through: one digit tall, its edges fading so digits roll in and out, never cut
    // each digit rolls inside its own place, a hair wider, so a wide digit never spills onto its neighbour
    const mx = x - px * 0.06, mw = w + px * 0.12;
    defs += `<mask id="${id}-c${k}" maskUnits="userSpaceOnUse" x="${r2(mx)}" y="${r2(winTop)}" width="${r2(mw)}" height="${r2(pitch)}"><rect x="${r2(mx)}" y="${r2(winTop)}" width="${r2(mw)}" height="${r2(pitch)}" fill="url(#${id}-fade)"/></mask>`;
    const pxPerFrame = s.speed * pitch * (1000 / fps);
    let filter = "";
    if (spec.paint !== "css" && pxPerFrame > FINISH.motionBlur.onlyAbovePxPerFrame) {
      const sd = (s.speed * pitch * shutterMs) / 2;
      defs += `<filter id="${id}-b${k}" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="0 ${r2(sd)}"/></filter>`;
      filter = ` filter="url(#${id}-b${k})"`;
    }
    body += `<g mask="url(#${id}-c${k})"><g${filter}>` +
      `<text x="${r2(cx)}" y="${r2(L.baseline - off)}" text-anchor="middle">${s.a}</text>` +
      `<text x="${r2(cx)}" y="${r2(L.baseline - off + pitch)}" text-anchor="middle">${s.b}</text></g></g>`;
  });
  if (defs) defs = `<linearGradient id="${id}-fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="${EDGE}" stop-color="#fff"/><stop offset="${1 - EDGE}" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>` + defs;
  // a figure at no strength is left out of the drawing, not drawn invisible: an empty layer can trip a renderer
  const inner = (defs ? `<defs>${defs}</defs>` : "") + `<g style="${font};fill:${fill};opacity:${r2(st.op)}${st.op > 0.0005 ? "" : ";display:none"}">${body}</g>`;
  const svg = place
    ? `<g class="num-g" transform="translate(${r2(place[0])} ${r2(place[1])})" role="img" aria-label="${esc(spec.text)}">${inner}</g>`
    : `<svg class="num-svg" viewBox="0 0 ${r2(L.width)} ${r2(L.height)}" width="${r2(L.width)}" height="${r2(L.height)}" role="img" aria-label="${esc(spec.text)}">${inner}</svg>`;
  return { svg, width: L.width, height: L.height, cues: st.cues, end: st.end };
}

// ---------------------------------------------------------------- the site's

/**
 * The figure as HTML, finished: what a visitor sees with no script, with less
 * motion, and before it plays. playNumber brings it in live.
 */
export function numberHTML(spec, { cls = "" } = {}) {
  const tone = spec.tone === "money" ? " num--money" : "";
  const data = esc(JSON.stringify({ text: spec.text, series: spec.series, duration: spec.duration, numerals: spec.numerals }));
  const inner = parse(spec.text).map((s) =>
    s.wheel === null
      ? `<span class="num-f">${esc(s.ch)}</span>`
      : `<span class="num-d"><span class="num-g">${s.ch}</span><span class="num-w" aria-hidden="true"></span></span>`).join("");
  return `<span class="num${tone}${cls ? " " + cls : ""}" data-number="${data}" aria-label="${esc(spec.text)}">${inner}</span>`;
}

/**
 * Play a figure built by numberHTML, in a browser. `spec` defaults to the one the
 * element carries. Returns a function that stops it and leaves the finished figure.
 */
export function playNumber(el, spec = JSON.parse(el.dataset.number), { now = () => performance.now(), raf = requestAnimationFrame, caf = cancelAnimationFrame } = {}) {
  const slots = [...el.children];
  const marks = parse(spec.text);
  const wheels = slots.map((node, k) => (marks[k].wheel === null ? null : node.querySelector(".num-w")));
  // a wheel is a column of the ten digits and a second zero, so 9 rolls into 0 without a seam
  for (const w of wheels) if (w && !w.firstChild) w.innerHTML = `<span class="num-col">${"01234567890".split("").map((d) => `<span>${d}</span>`).join("")}</span>`;
  const series = !!spec.series;
  el.classList.add("num-live");
  if (series) el.classList.add("num-series");
  const t0 = now();
  let id = 0;
  // finished, the figure is exactly the markup it started as: the wheels are emptied again
  const finish = () => { caf(id); el.classList.remove("num-live", "num-series"); el.style.opacity = ""; for (const node of slots) node.style.visibility = ""; for (const w of wheels) if (w) w.textContent = ""; };
  const frame = () => {
    const at = now() - t0, st = numberState(spec, at);
    el.style.opacity = String(st.op);
    st.slots.forEach((s, k) => {
      const node = slots[k];
      if (s.kind === "fixed") return;
      if (s.kind === "char") {
        if (marks[k].wheel === null) { node.style.visibility = s.shown ? "" : "hidden"; return; }
        const w = wheels[k];
        w.textContent = s.shown;
        return;
      }
      const col = wheels[k].firstChild;
      col.style.transform = `translateY(${-(s.a + s.frac) * PITCH}em)`;
    });
    if (at < st.end) id = raf(frame); else finish();
  };
  id = raf(frame);
  return finish;
}

// ---------------------------------------------------------------- the receipt (rungs 7–11)

/**
 * receipt: {
 *   rows: [[what, value], ...]     the inputs, in words and figures, each true on its own
 *   total: [what, value]           the figure itself, said in words
 *   range?: { lo, hi, at, read(v), say }   the 1-in-10 low and high, where the figure sits, how to say a value, the range in words
 *   note?                          how the rows make the total, honestly ("From 10,000 simulated years ...")
 *   source                         the label that never comes off
 *   dated?                         when it was priced
 * }
 */

/** The figure as a citation: what it is, its range, its label and date, for pasting elsewhere. */
export function numberCitation(spec) {
  const r = spec.receipt;
  const range = r.range ? ` (${r.range.say}: ${r.range.read(r.range.lo)} to ${r.range.read(r.range.hi)})` : "";
  return `${spec.text} — ${r.total[0].replace(/^./, (c) => c.toLowerCase())}${range}. ${r.source}. Hubricon${r.dated ? `, ${r.dated}` : ""}.`;
}

/**
 * The working, as HTML for the site: a quiet "The working" under the figure that opens the rows,
 * the range drawn to scale, the source, and a copy button that a script reveals (no script, no
 * button, nothing broken). Place it right after the figure.
 */
export function receiptHTML(spec, { id = "r" } = {}) {
  const r = spec.receipt;
  const rows = r.rows.map(([k, v], i) => `<div class="rc-row" style="--i:${i}"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("") +
    `<div class="rc-row rc-total" style="--i:${r.rows.length}"><dt>${esc(r.total[0])}</dt><dd>${esc(r.total[1])}</dd></div>`;
  let range = "";
  if (r.range) {
    const at = (r.range.at - r.range.lo) / (r.range.hi - r.range.lo);
    range = `<div class="rc-range" style="--at:${Math.min(1, Math.max(0, at)).toFixed(4)};--i:${r.rows.length + 1}" role="img" aria-label="${esc(`${r.range.say}: ${r.range.read(r.range.lo)} to ${r.range.read(r.range.hi)}; this figure, ${spec.text}`)}">` +
      `<span class="rc-track"><span class="rc-mark"></span></span><span class="rc-lo">${esc(r.range.read(r.range.lo))}</span><span class="rc-say">${esc(r.range.say)}</span><span class="rc-hi">${esc(r.range.read(r.range.hi))}</span></div>`;
  }
  return `<details class="receipt" id="${esc(id)}"><summary>The working</summary><div class="rc-body">` +
    `<dl class="rc-rows">${rows}</dl>${range}` +
    (r.note ? `<p class="rc-note">${esc(r.note)}</p>` : "") +
    `<p class="rc-source">${esc(r.source)}</p>` +
    `<button class="rc-copy" type="button" hidden data-cite="${esc(numberCitation(spec))}">Copy with its source</button>` +
    `</div></details>`;
}

/** Arm the copy buttons inside `root`: revealed only where the clipboard works. */
export function armReceipts(root = document) {
  if (!globalThis.navigator?.clipboard) return;
  for (const b of root.querySelectorAll(".rc-copy[hidden]")) {
    b.hidden = false;
    b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(b.dataset.cite); b.textContent = "Copied, with its source"; }
      catch { b.textContent = "Select the text to copy"; }
      setTimeout(() => { b.textContent = "Copy with its source"; }, 2400);
    });
  }
}

/**
 * The working as a film frame: the rows arrive one by one, each value landing on its wheels,
 * then a hairline and the total, larger, last. Pure: the same moment gives the same frame.
 * Returns { svg, width, height, cues, end }.
 */
export function numberReceiptSVG(spec, at = Infinity, { w = 1200, px = VIDEO.type.label.px, start = 0, fps = VIDEO.render.final.fps, id = "rc" } = {}) {
  const P = paint(spec.paint ?? "inline", spec.ground);
  const r = spec.receipt, lineH = px * 1.9, gap = ms("stagger") * 3, land = ms("count-ms") * 0.6;
  const font = spec.paint === "css" ? "var(--font)" : "Inter Display, Inter, sans-serif";
  const ez = ease("ease-out");
  let body = "", y = 0;
  const cues = [];
  const rowAt = (i) => start + i * (gap + land * 0.5);
  r.rows.forEach(([k, v], i) => {
    const t0 = rowAt(i), op = ez(clamp01((at - t0) / ms("reveal-fade-ms"))), rise = (1 - op) * parseFloat(css("reveal-rise"));
    y += lineH;
    if (op <= 0.0005) return;
    body += `<g style="opacity:${r2(op)}" transform="translate(0 ${r2(rise)})">` +
      `<text x="0" y="${r2(y)}" style="font-size:${r2(px)}px;font-weight:400;fill:${P("ink-3")}">${esc(k)}</text>`;
    const fig = numberSVG({ text: v, px, weight: 600, tone: "ink", paint: spec.paint ?? "inline", ground: spec.ground, start: t0, duration: land }, at, { fps, id: `${id}-${i}`, place: [0, 0] });
    body += `<g transform="translate(${r2(w - fig.width)} ${r2(y - px * 0.95)})">${fig.svg}</g></g>`;
    for (const c of fig.cues) if (c.name === "tick") cues.push(c);
  });
  // the total: a hairline, then the figure in its own tone, larger, landing last
  const tT = rowAt(r.rows.length), opT = ez(clamp01((at - tT) / ms("reveal-fade-ms"))), tpx = px * 1.6;
  y += px * 0.9;
  const ruleY = y;
  y += tpx * 1.35;
  if (opT > 0.0005) {
    body += `<line x1="0" x2="${r2(w)}" y1="${r2(ruleY)}" y2="${r2(ruleY)}" style="stroke:${P("rule-2")};stroke-width:${r2(Math.max(1, px / 24))}px;opacity:${r2(opT)}"/>`;
    body += `<text x="0" y="${r2(y)}" style="font-size:${r2(px)}px;font-weight:600;fill:${P("ink")};opacity:${r2(opT)}">${esc(r.total[0])}</text>`;
    const fig = numberSVG({ text: spec.text, px: tpx, weight: 600, tone: spec.tone, paint: spec.paint ?? "inline", ground: spec.ground, start: tT, finding: true }, at, { fps, id: `${id}-t`, place: [0, 0] });
    body += `<g transform="translate(${r2(w - fig.width)} ${r2(y - tpx * 0.95)})">${fig.svg}</g>`;
    cues.push(...fig.cues);
  }
  // the range, to scale: the 1-in-10 low and high in their own tone, the figure's mark gliding to where it sits
  let endAt = tT + ms("count-ms");
  if (r.range) {
    const tR = endAt + ms("stagger") * 2, opR = ez(clamp01((at - tR) / ms("reveal-fade-ms")));
    const glide = ease("ease-in-out")(clamp01((at - tR - ms("stagger")) / ms("mc-draw-ms")));
    const where = (r.range.at - r.range.lo) / (r.range.hi - r.range.lo);
    y += px * 1.6;
    const ty = y, sw = Math.max(1, px / 24);
    y += px * 1.7;
    if (opR > 0.0005) {
      const o = `opacity:${r2(opR)}`;
      body += `<line x1="0" x2="${r2(w)}" y1="${r2(ty)}" y2="${r2(ty)}" style="stroke:${P("rule-2")};stroke-width:${r2(sw)}px;${o}"/>` +
        `<line x1="0" x2="0" y1="${r2(ty - px * 0.22)}" y2="${r2(ty + px * 0.22)}" style="stroke:${P("ink-3")};stroke-width:${r2(sw)}px;${o}"/>` +
        `<line x1="${r2(w)}" x2="${r2(w)}" y1="${r2(ty - px * 0.22)}" y2="${r2(ty + px * 0.22)}" style="stroke:${P("ink-3")};stroke-width:${r2(sw)}px;${o}"/>` +
        `<circle cx="${r2(w * where * glide)}" cy="${r2(ty)}" r="${r2(px * 0.2)}" style="fill:${P("ink")};${o}"/>` +
        `<text x="0" y="${r2(y)}" style="font-size:${r2(px)}px;font-weight:600;fill:${P("blue")};font-variant-numeric:tabular-nums;${o}">${esc(r.range.read(r.range.lo))}</text>` +
        `<text x="${r2(w / 2)}" y="${r2(y)}" text-anchor="middle" style="font-size:${r2(px)}px;font-weight:400;fill:${P("ink-3")};${o}">${esc(r.range.say)}</text>` +
        `<text x="${r2(w)}" y="${r2(y)}" text-anchor="end" style="font-size:${r2(px)}px;font-weight:600;fill:${P("blue")};font-variant-numeric:tabular-nums;${o}">${esc(r.range.read(r.range.hi))}</text>`;
    }
    endAt = tR + ms("stagger") + ms("mc-draw-ms");
  }
  const height = y + px * 0.6;
  const svg = `<svg class="num-receipt" viewBox="0 0 ${r2(w)} ${r2(height)}" width="${r2(w)}" height="${r2(height)}" style="font-family:${font}">${body}</svg>`;
  return { svg, width: w, height, cues: cues.sort((a, b) => a.at - b.at), end: endAt };
}
