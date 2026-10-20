// The number: every digit on screen is either true or visibly moving.
//   node --test scripts/number.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { parse, formatLike, numberState, numberLayout, numberSVG, numberHTML } from "../assets/number.mjs";
import { ms, SOUND, FINISH } from "../assets/tokens.mjs";

const final = (spec) => numberState(spec, Infinity).slots.map((s) => (s.kind === "wheel" ? String(s.a) : s.shown)).join("");

test("the finished frame is the figure, character for character", () => {
  for (const text of ["$48,210", "+$0.28", "$6,400–$19,200", "−$1,870", "7,865", "2.5%"]) assert.equal(final({ text }), text);
});

test("magnitude first: wheels land left to right, and a landed digit is always its true digit", () => {
  const spec = { text: "$6,400–$19,200" }, D = ms("count-ms"), digits = parse(spec.text).filter((s) => s.wheel !== null);
  let landedBefore = 0;
  for (let at = 0; at <= D + 50; at += 7) {
    const wheels = numberState(spec, at).slots.filter((s) => s.kind === "wheel");
    const landed = wheels.map((w) => w.landed);
    const count = landed.filter(Boolean).length;
    assert.ok(landed.every((l, i) => !l || landed.slice(0, i).every(Boolean)), `a digit landed before the one to its left at ${at} ms`);
    wheels.forEach((w, i) => { if (w.landed) assert.equal(w.a, digits[i].digit, `wheel ${i} landed on a wrong digit`); });
    assert.ok(count >= landedBefore, "a landed digit started moving again");
    landedBefore = count;
  }
  assert.equal(landedBefore, digits.length);
});

test("a wrong digit is never readable: a moving wheel shows its true digit before it slows enough to read", () => {
  // a digit that travels more than 4% of its own height a frame is visibly moving, not readable
  const spec = { text: "$6,400–$19,200" }, digits = parse(spec.text).filter((s) => s.wheel !== null);
  const frameMs = 1000 / 60;
  for (let at = 0; at < ms("count-ms"); at += 3) {
    numberState(spec, at).slots.filter((s) => s.kind === "wheel").forEach((w, i) => {
      if (w.landed) return;
      const share = w.speed * frameMs;             // of its height, each frame
      const showing = w.frac > 0.5 ? w.b : w.a;
      assert.ok(share > 0.04 || showing === digits[i].digit,
        `wheel ${i} shows ${showing} almost still (${(share * 100).toFixed(1)}% of its height a frame) at ${at} ms`);
    });
  }
});

test("a spinning wheel is fast enough to be blurred at every film type size", () => {
  const st = numberState({ text: "$48,210" }, 200);
  const spin = Math.max(...st.slots.filter((s) => s.kind === "wheel").map((s) => s.speed));
  for (const px of [40, 88, 136, 216]) assert.ok(spin * px * 1.1 * (1000 / 60) > FINISH.motionBlur.onlyAbovePxPerFrame, `not blurred at ${px}px`);
});

test("with a real series, the number shows only those values, ending on the figure", () => {
  const series = [39070, 42170, 44550, 46050, 47250, 47860, 48210];
  const spec = { text: "$48,210", series };
  const allowed = new Set(series.map((v) => "$" + formatLike("$48,210", v)));
  for (let at = 0; at <= ms("count-ms") + 20; at += 5) {
    const shown = numberState(spec, at).slots.map((s) => s.shown).join("");
    assert.ok(allowed.has(shown), `showed ${shown} at ${at} ms`);
  }
  assert.throws(() => numberState({ text: "$48,210", series: [1, 2, 3] }, 0), /ends on/);
  assert.throws(() => numberState({ text: "$6,400–$19,200", series: [19200] }, 0), /exactly one number/);
});

test("a growing series fills from the right and never pushes the figure sideways", () => {
  const spec = { text: "7,865", series: [0, 294, 1006, 7865] };
  const L = numberLayout(spec);
  const shown = new Set();
  for (let at = 0; at <= ms("count-ms"); at += 5) {
    const st = numberState(spec, at);
    assert.equal(st.slots.length, L.places.length);
    shown.add(st.slots.map((s) => s.shown || "_").join(""));
  }
  assert.deepEqual([...shown], ["____0", "__294", "1,006", "7,865"]);
});

test("ticks: one per change, never more than the tick's limit a second", () => {
  const gap = 1000 / SOUND.cues.tick.maxPerSecond;
  for (const spec of [{ text: "$6,400–$19,200" }, { text: "$48,210", series: [39070, 42170, 44550, 46050, 47250, 47860, 48210] }]) {
    const ticks = numberState(spec, 0).cues.filter((c) => c.name === "tick").map((c) => c.at);
    assert.ok(ticks.length >= 6);
    for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i] - ticks[i - 1] >= gap - 1e-9, "ticks too close");
  }
  const s = { text: "$48,210", series: [39070, 42170, 44550, 46050, 47250, 47860, 48210] };
  assert.equal(numberState(s, 0).cues.length, 6, "six receipts, six ticks");
  assert.deepEqual(numberState({ text: "+$0.28", finding: true, start: 500 }, 0).cues.at(-1), { name: "reveal", at: 500 + ms("count-ms") });
});

test("nothing before its start; the film frame and the site's markup agree on the figure", () => {
  assert.equal(numberState({ text: "$48,210", start: 300 }, 200).op, 0);
  const svg = numberSVG({ text: "+$0.28", tone: "money" }, Infinity).svg;
  assert.match(svg, /fill:#0b5fff/);
  assert.equal([...svg.matchAll(/>([^<>]+)<\/text>/g)].map((m) => m[1]).join(""), "+$0.28");
  const html = numberHTML({ text: "$48,210", series: [48210] });
  assert.equal(html.replace(/<span class="num-w"[^>]*><\/span>/g, "").replace(/<[^>]+>/g, ""), "$48,210", "with no script the page shows the figure");
  assert.match(html, /aria-label="\$48,210"/);
});

test("a moving digit in a film is blurred along its travel, and only when it moves fast", () => {
  const fast = numberSVG({ text: "$48,210" }, 80).svg, slow = numberSVG({ text: "$48,210" }, ms("count-ms") - 30).svg;
  assert.match(fast, /feGaussianBlur stdDeviation="0 [\d.]+"/);
  assert.doesNotMatch(slow, /feGaussianBlur/);
  assert.doesNotMatch(numberSVG({ text: "$48,210", paint: "css" }, 80).svg, /feGaussianBlur/, "the site never blurs");
});

test("in a page, the figure plays and leaves the markup exactly as it found it", async () => {
  const { playNumber } = await import("../assets/number.mjs");
  // a minimal stand-in for the browser: elements with classes, styles and children
  const node = (cls, kids = [], text = "") => {
    const n = { className: cls, children: kids, style: {}, _text: text, firstChild: null,
      classList: { set: new Set(cls.split(" ")), add(...c) { c.forEach((x) => this.set.add(x)); }, remove(...c) { c.forEach((x) => this.set.delete(x)); }, contains(c) { return this.set.has(c); } },
      querySelector(sel) { return kids.find((k) => k.className === sel.slice(1)) || null; },
      set innerHTML(h) { this._text = h; this.firstChild = { style: {} }; }, get textContent() { return this._text; }, set textContent(v) { this._text = v; this.firstChild = v ? { style: {} } : null; } };
    return n;
  };
  const spec = { text: "$48,210", series: [39070, 42170, 48210] };
  const kids = [...spec.text].map((ch) => (/\d/.test(ch) ? node("num-d", [node("num-g", [], ch), node("num-w")]) : node("num-f", [], ch)));
  const el = node("num", kids);
  let clock = 0; const queue = [];
  playNumber(el, spec, { now: () => clock, raf: (f) => queue.push(f), caf: () => {} });
  assert.ok(el.classList.contains("num-live"));
  let shown = new Set();
  while (queue.length) { clock += 16; queue.shift()(); shown.add(kids.map((k) => (k.className === "num-d" ? k.children[1].textContent : k.style.visibility === "hidden" ? "" : k._text)).join("")); }
  assert.ok(!el.classList.contains("num-live"), "still marked as playing");
  assert.ok(kids.filter((k) => k.className === "num-d").every((k) => k.children[1].textContent === ""), "a wheel kept its digits");
  assert.ok([...shown].includes("$42,170"), "the series' middle value never showed");
});
