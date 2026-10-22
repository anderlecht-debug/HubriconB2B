// The design tokens: one file, read by the site, the charts, the films and their sound.
//   node --test scripts/tokens.test.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { CSS, NIGHT, VIDEO, SOUND, THUMB, CAPTIONS, FINISH, CAMERA, cssTokens, css, ms, ease, cubicBezier, travelMs, readingMs } from "../assets/tokens.mjs";
import { tokenBlock, STYLESHEET } from "./build-tokens.mjs";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const sheet = readFileSync(STYLESHEET, "utf8");
const names = new Set(cssTokens().map(([n]) => n));

test("the stylesheet's tokens are the ones in tokens.mjs (run node scripts/build-tokens.mjs)", () => {
  assert.ok(sheet.includes(tokenBlock()), "hubricon.css's token block was edited by hand or is stale");
});

test("no token is declared anywhere else in the stylesheet", () => {
  const outside = sheet.replace(tokenBlock(), "").replace(/@media print\s*\{[\s\S]*?\n\}/g, "");
  for (const m of outside.matchAll(/(?:^|[;{\s])--([a-z0-9-]+)\s*:/g)) {
    assert.ok(!names.has(m[1]), `--${m[1]} is a token, declared again outside the generated block`);
  }
  assert.doesNotMatch(outside, /(^|\n)\s*:root\s*\{/, "a second :root rule: put the value in tokens.mjs");
});

test("every var() the stylesheet reads is defined somewhere", () => {
  // Tokens, plus the few properties a page or chart sets on an element (--d, --delay, …).
  const set = new Set(names);
  const files = [];
  const walk = (dir) => {
    for (const f of readdirSync(dir)) {
      if (["node_modules", ".git", "archive", "engine", "supabase", "brand"].includes(f)) continue;
      const p = join(dir, f);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(html|css|mjs|js)$/.test(f)) files.push(p);
    }
  };
  walk(ROOT);
  for (const p of files) for (const m of readFileSync(p, "utf8").matchAll(/--([a-z][a-z0-9-]*)\s*:/g)) set.add(m[1]);
  for (const m of sheet.matchAll(/var\(--([a-z0-9-]+)/g)) assert.ok(set.has(m[1]), `var(--${m[1]}) is read but never defined`);
});

test("the dark section swaps every colour it names, to a token that exists", () => {
  for (const [to, from] of NIGHT) {
    assert.ok(names.has(to), `--${to}`);
    assert.ok(names.has(from), `--${from}`);
  }
});

// WCAG relative luminance and contrast, for #rrggbb.
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

test("every ink that carries words reads at 4.5:1 or better on both grounds, day and night", () => {
  for (const ground of ["paper", "paper-2"]) {
    for (const ink of ["ink", "ink-2", "ink-3", "blue"]) {
      const r = contrast(css(ink), css(ground));
      assert.ok(r >= 4.5, `--${ink} on --${ground}: ${r.toFixed(2)}:1`);
    }
  }
  for (const ground of ["night", "night-2"]) {
    for (const ink of ["night-ink", "night-ink-2", "night-ink-3", "night-blue"]) {
      const r = contrast(css(ink), css(ground));
      assert.ok(r >= 4.5, `--${ink} on --${ground}: ${r.toFixed(2)}:1`);
    }
  }
});

test("the contrast a note claims is the contrast it has", () => {
  for (const [name, value, note] of cssTokens()) {
    const m = note && note.match(/(\d+\.\d):1(?: on (night|paper))?/);
    if (!m || !/^#[0-9a-f]{6}$/i.test(value)) continue;
    const ground = name.startsWith("night") ? css("night") : css("paper");
    assert.equal(contrast(value, ground).toFixed(1), m[1], `--${name}'s note says ${m[1]}:1`);
  }
});

test("the blue is the only accent: no other saturated colour is a token", () => {
  const hues = cssTokens().filter(([, v]) => /^#[0-9a-f]{6}$/i.test(v)).map(([n, v]) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16));
    return [n, (Math.max(r, g, b) - Math.min(r, g, b)) / 255];
  });
  for (const [n, chroma] of hues) {
    if (n === "blue" || n === "night-blue") continue;
    assert.ok(chroma < 0.2, `--${n} is a second accent (chroma ${chroma.toFixed(2)})`);
  }
});

test("durations are milliseconds, and the easings land where the browser's do", () => {
  for (const [n, v] of cssTokens()) if (n.endsWith("-ms")) assert.match(v, /^\d+ms$/, `--${n}`);
  assert.equal(ms("count-ms"), 1600);
  for (const name of ["ease-out", "ease-in-out", "ease-sweep", "count", "linear"]) {
    const f = ease(name);
    assert.equal(f(0), 0, name);
    assert.equal(f(1), 1, name);
    let last = -1;
    for (let i = 0; i <= 200; i++) { const y = f(i / 200); assert.ok(y >= last - 1e-9, `${name} goes backwards at ${i / 200}`); last = y; }
  }
  // Against the curve's own parametric form: x(t), y(t) for cubic-bezier(0.16, 1, 0.3, 1).
  const [x1, y1, x2, y2] = [0.16, 1, 0.3, 1];
  const B = (a, b, t) => 3 * a * t * (1 - t) ** 2 + 3 * b * t * t * (1 - t) + t ** 3;
  const f = cubicBezier(x1, y1, x2, y2);
  for (let i = 1; i < 50; i++) { const t = i / 50; assert.ok(Math.abs(f(B(x1, x2, t)) - B(y1, y2, t)) < 1e-5, `t=${t}`); }
});

test("a film has four type sizes, and the smallest reads on a phone", () => {
  const sizes = Object.values(VIDEO.type).map((t) => t.px);
  assert.equal(sizes.length, 4);
  assert.ok(Math.min(...sizes) >= 40, "the smallest film text is under 40px at 1080p");
  assert.deepEqual([...sizes].sort((a, b) => a - b), sizes, "sizes run small to large");
  for (const k of ["statement", "display", "hero"]) assert.equal(VIDEO.type[k].track, css("track-display"));
  assert.equal(VIDEO.type.label.track, css("track-label"));
});

test("the safe areas leave room for the picture", () => {
  const { w, h } = VIDEO.frame, s = VIDEO.safe;
  assert.ok(w - 2 * s.x >= w * 0.8 && h - s.top - s.bottom >= h * 0.7);
  const v = VIDEO.vertical, sv = VIDEO.safeVertical;
  assert.ok(v.w - sv.left - sv.right > 0 && v.h - sv.top - sv.bottom > v.h / 2);
});

test("no sound is used without its licence, and the reveal stays rare", () => {
  const all = { bed: SOUND.bed, ambience: SOUND.ambience, ...SOUND.cues };
  for (const [name, s] of Object.entries(all)) {
    if (s.file) assert.match(String(s.licence), /CC0|Pixabay/, `${name}: a file with no licence on record`);
    assert.ok(s.gainDb < 0, `${name} must sit under the voice`);
  }
  assert.ok(Number.isInteger(SOUND.cues.reveal.maxPerFilm) && SOUND.cues.reveal.maxPerFilm > 0);
  assert.equal(SOUND.silence.ms, VIDEO.motion.silenceMs);
  assert.ok(SOUND.master.truePeakDb < 0);
});

test("the CSS table has no duplicate names", () => {
  const all = CSS.flatMap(([, rows]) => rows.filter(Boolean).map(([n]) => n));
  assert.equal(new Set(all).size, all.length);
});

// ---- the four derived groups: each rule is arithmetic on what is true about how it is seen

const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const inside = (a, f) => a.x >= 0 && a.y >= 0 && a.x + a.w <= f.w && a.y + a.h <= f.h;

test("a thumbnail survives being shrunk to the smallest place it is shown", () => {
  const scale = THUMB.smallestShown / THUMB.frame.w;
  assert.ok(THUMB.minStroke * scale >= 1, "a line under one screen pixel at the smallest size vanishes");
  assert.ok(THUMB.lineStroke >= THUMB.minStroke, "a chart line under the floor vanishes");
  assert.ok(THUMB.leakStroke >= 2 * THUMB.lineStroke, "the leak must be the heaviest mark");
  assert.ok(THUMB.words.px * 0.727 * scale >= 12, "a capital under 12px at the smallest size cannot be read");
  assert.ok(THUMB.words.max <= 3 && THUMB.words.lines <= 2);
  assert.equal(THUMB.frame.w * THUMB.render.scale, 3840, "YouTube's recommended thumbnail is 3840 wide");
  assert.equal(THUMB.frame.w / THUMB.frame.h, 16 / 9);
});

test("a thumbnail's words and chart stay clear of each other and of what YouTube paints over", () => {
  const { words, chart } = THUMB.boxes;
  for (const b of [words, chart]) assert.ok(inside(b, THUMB.frame), "a box leaves the frame");
  assert.ok(!overlaps(words, chart), "words sit on the data");
  assert.ok(words.h >= THUMB.words.lines * THUMB.words.px * THUMB.words.leading, "the words box cannot hold its lines");
  for (const k of THUMB.keepOut) for (const b of [words, chart]) assert.ok(!overlaps(b, k), `a box sits under YouTube's ${k.name}`);
  assert.equal(THUMB.variants.max, 3);
  assert.ok(THUMB.never.includes("a face") && THUMB.never.includes("a second colour"));
});

test("clip captions are readable at a glance and sit inside the safe area", () => {
  const c = CAPTIONS.clips, sv = VIDEO.safeVertical, v = VIDEO.vertical;
  assert.ok(c.cps <= 20, "faster than subtitle reading standards");
  assert.ok(c.maxLines <= 2);
  const safeW = v.w - sv.left - sv.right;
  assert.ok(c.maxCharsPerLine * c.px * 0.56 <= safeW, "a full line runs out of the safe area");
  assert.ok(c.px >= 56, "too small for a phone held upright");
  assert.ok(c.fadeMs <= 150, "a caption must appear, not perform");
  assert.equal(readingMs("ab"), c.minMs);
  assert.equal(readingMs("x".repeat(34)), 2000);
  for (const n of ["word-by-word reveal", "karaoke highlighting", "bouncing, popping or scaling"]) assert.ok(CAPTIONS.never.includes(n));
  assert.match(CAPTIONS.longForm, /nothing burned in/);
});

test("the finish hides nothing", () => {
  for (const n of ["film grain", "vignette", "glow or bloom", "drop shadows", "a colour grade or LUT"]) assert.ok(FINISH.never.includes(n), n);
  assert.equal(VIDEO.render.final.scale, 2);
  assert.equal(VIDEO.render.final.fps, 60);
  assert.ok(FINISH.motionBlur.onlyAbovePxPerFrame > 0, "blur on every move softens the type");
  assert.ok(FINISH.motionBlur.shutterAngle > 0 && FINISH.motionBlur.shutterAngle <= 360);
  assert.ok(FINISH.depth.parallax > 0.8 && FINISH.depth.parallax < 1);
  assert.equal(FINISH.depth.never, "inside a chart");
});

test("the camera moves once a beat, calmly, and never while text is read", () => {
  assert.equal(CAMERA.ease, "ease-in-out");
  assert.equal(CAMERA.movesPerBeat, 1);
  assert.ok(CAMERA.zoom.max <= 3 && CAMERA.zoom.maxPerMove <= CAMERA.zoom.max && CAMERA.zoom.min === 1);
  assert.equal(CAMERA.waitsForReading.cps, CAPTIONS.clips.cps, "the camera and the captions read at the same speed");
  assert.equal(travelMs(0), CAMERA.travel.minMs);
  assert.equal(travelMs(1 + CAMERA.canvas.gap), 1325);
  assert.equal(travelMs(10), CAMERA.travel.maxMs);
  for (let f = 0; f < 6; f += 0.25) assert.ok(travelMs(f + 0.25) >= travelMs(f), "a longer trip never takes less time");
  for (const n of ["rotation", "shake", "a move while text is being read"]) assert.ok(CAMERA.never.includes(n));
  assert.ok(CAMERA.canvas.continuous);
});
