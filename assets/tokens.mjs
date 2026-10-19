/* ============================================================================
   Hubricon tokens: every look-and-feel value, in one file.

   The site, the charts, the films and their sound all read from here. The
   stylesheet's :root block is generated from this file by
   `node scripts/build-tokens.mjs`, and `scripts/tokens.test.mjs` fails if the two
   ever disagree, so a value is changed here or nowhere.

   Every value under CSS is the one the site already used on 2026-10-19 (the
   founder: "anything token-wise, the repo will win"). What is new is what the
   films need and the site never did: a frame, a type scale in pixels, safe
   areas, holds, and the sound palette. Those are marked "starting value" where
   they still have to be judged on real frames or by ear.

   Plain data plus two pure helpers, no imports, so a browser, Node and the video
   renderer can all load it as it is.
   ============================================================================ */

// ---------------------------------------------------------------- CSS tokens
// [name, value, note]. Order and notes are the stylesheet's. Values are strings,
// exactly as CSS takes them.

export const CSS = [
  ["colour", [
    ["paper", "#ffffff", "every page's ground. A lot of air"],
    ["paper-2", "#f5f6f8", "a quiet panel, never a card shadow"],
    ["ink", "#0a0e17", "headlines, the button, every chart's lines. 19.3:1 on paper"],
    ["ink-2", "#3b4250", "body copy. 10.1:1"],
    ["ink-3", "#636b7a", "captions, labels, axes. 5.4:1"],
    ["ink-4", "#9aa1ae", "a chart's second neutral: a fee, a cost, a ghosted series. 2.6:1: marks, not words"],
    ["rule", "#e4e7ec", "hairlines, gridlines"],
    ["rule-2", "#cdd2da", "chip borders, axes"],
    ["blue", "#0b5fff", "money and the leak. Nothing else. 5.1:1 on paper"],
    ["blue-wash", "rgb(11 95 255 / 0.07)", "the blue as a ground: a range, a band"],
    ["selection", "rgb(11 95 255 / 0.16)", "selected text"],
    null,
    ["night", "#070a11", "a dark section's ground. It separates acts, never decorates"],
    ["night-2", "#0d121c"],
    ["night-ink", "#f3f5f9", "18.1:1 on night"],
    ["night-ink-2", "#a8b0bf", "9.1:1"],
    ["night-ink-3", "#7c8596", "5.3:1"],
    ["night-ink-4", "#4f5768", "2.7:1: marks, not words"],
    ["night-rule", "#1d2431"],
    ["night-rule-2", "#2c3443"],
    ["night-blue", "#5b94ff", "6.7:1 on night"],
    ["night-blue-wash", "rgb(91 148 255 / 0.1)"],
  ]],
  ["type: one sans, two weights. Inter is loaded with its optical-size axis, so text from\n     about 20px up takes Inter Display, the cut drawn for large sizes (2026-09-30).", [
    ["font", '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'],
    ["regular", "400"],
    ["strong", "600"],
    ["t-12", "0.75rem"],
    ["t-14", "0.875rem"],
    ["t-16", "1rem"],
    ["t-18", "1.125rem"],
    ["t-20", "1.25rem"],
    ["t-24", "1.5rem"],
    ["t-display-s", "clamp(1.75rem, 1.2rem + 2.2vw, 2.75rem)"],
    ["t-display-m", "clamp(2.125rem, 1.3rem + 3.4vw, 3.75rem)"],
    ["t-display-l", "clamp(2.375rem, 1.2rem + 4.6vw, 4.5rem)"],
    ["t-display-xl", "clamp(2.75rem, 1rem + 6.2vw, 6rem)", "the one or two lines a page is remembered by"],
    ["track-display", "-0.032em"],
    ["track-label", "0.08em"],
  ]],
  ["space: one scale, everywhere", [
    ["s-1", "4px"],
    ["s-2", "8px"],
    ["s-3", "12px"],
    ["s-4", "16px"],
    ["s-5", "24px"],
    ["s-6", "32px"],
    ["s-7", "48px"],
    ["s-8", "64px"],
    ["s-9", "96px"],
    ["s-10", "128px"],
    ["section", "clamp(var(--s-8), 9vw, var(--s-10))"],
    ["gutter", "clamp(var(--s-4), 4vw, var(--s-6))"],
    ["wide", "1120px"],
    ["measure", "60ch"],
    ["radius", "10px"],
    ["nav-h", "56px", "the bar's height"],
    ["glass", "rgb(255 255 255 / 0.9)", "the bar's white glass"],
    ["scrim", "rgb(255 255 255 / 0.45)", "the page behind an open panel"],
  ]],
  ["charts: weights, washes and motion read from here, never set in a chart", [
    ["line-hair", "1px"],
    ["line-step", "2px"],
    ["line-pct", "2px"],
    ["line-leak", "3px"],
    ["mc-path-draw", "0.28", "a path's opacity while it draws"],
    ["mc-path-rest", "0.07", "and once it has settled"],
    ["mc-band", "0.13", "the P10–P90 band"],
  ]],
  ["motion: one draw-in, then still. Nothing loops and nothing moves again", [
    ["ease-out", "cubic-bezier(0.16, 1, 0.3, 1)", "launches, then settles slowly: everything that arrives"],
    ["ease-in-out", "cubic-bezier(0.65, 0, 0.35, 1)", "films only: a camera that starts and stops moving"],
    ["mc-draw-ms", "2000ms", "a chart's paths sketching in, left to right"],
    ["mc-band-ms", "400ms", "the band filling once the lines have landed"],
    ["mc-settle-ms", "900ms", "the paths fading back to almost nothing"],
    ["count-ms", "1600ms", "a number counting up to the figure the page prints"],
    ["reveal-rise", "20px", "how far a section's parts rise into place"],
    ["reveal-fade-ms", "800ms"],
    ["reveal-move-ms", "1000ms"],
    ["stagger", "120ms", "a beat: the gap between parts arriving"],
    ["calm-ms", "600ms", "the dissolve for a visitor who asked for less motion"],
    ["bar-fill-ms", "1600ms", "the scoreboard's bar filling to the bill and past it"],
  ]],
];

/** The dark section: the same names, swapped. Generated as the `.night` rule. */
export const NIGHT = [
  ["paper", "night"], ["paper-2", "night-2"],
  ["ink", "night-ink"], ["ink-2", "night-ink-2"], ["ink-3", "night-ink-3"], ["ink-4", "night-ink-4"],
  ["rule", "night-rule"], ["rule-2", "night-rule-2"],
  ["blue", "night-blue"], ["blue-wash", "night-blue-wash"],
];

// ---------------------------------------------------------------- the films
// Pixels at the 1920×1080 design frame. A final render doubles it to 3840×2160:
// YouTube encodes higher-resolution uploads at a higher quality, so even a viewer
// at 1080p sees crisper type and lines.

export const VIDEO = {
  frame: { w: 1920, h: 1080 },
  vertical: { w: 1080, h: 1920 },                       // the clips: Shorts, Reels, TikTok
  render: {
    draft: { scale: 1, fps: 30 },                       // for looking at, fast
    final: { scale: 2, fps: 60 },                       // for uploading
  },
  // Keep type and the one hero element inside these. The bottom margin clears the
  // player's progress bar and captions. Vertical: clears the like/share column and
  // the caption block. Starting values, to check against a real upload.
  safe: { x: 128, top: 96, bottom: 144 },
  safeVertical: { left: 64, right: 176, top: 240, bottom: 440 },
  grid: { columns: 12, gap: 32 },
  // Four sizes and no others. The smallest still reads on a phone held upright.
  type: {
    label: { px: 40, leading: 1.3, weight: 600, track: "0.08em", caps: true },     // "Fig. 2 · …", axes, captions
    statement: { px: 88, leading: 1.15, weight: 600, track: "-0.032em" },          // the one line on screen
    display: { px: 136, leading: 1.05, weight: 600, track: "-0.032em" },           // the claim a film is remembered by
    hero: { px: 216, leading: 1, weight: 600, track: "-0.032em" },                 // one number, alone
  },
  // BRAND.md: tabular digits are for columns; a figure standing alone at display
  // size in a film takes proportional digits.
  numerals: { charts: "tabular-nums", hero: "proportional-nums" },
  wordsOnScreen: 7,                                      // at most, at once
  ground: { scene: "paper", actBreak: "night" },         // the site's rule: dark separates acts
  motion: {
    holdMs: 1500,              // a finished visual sits still before the next thing moves. Starting value
    silenceMs: 500,            // everything drops out before a reveal
    turnMs: 600,               // the move from one scene to the next. Starting value
    cameraEase: "ease-in-out", // a camera glide; everything that arrives still uses ease-out
  },
};

// ---------------------------------------------------------------- the sound
// Six cues, each with one job, so a viewer learns the language without noticing.
// No file is a cue until its licence is recorded beside it, and every sound comes
// from Freesound (CC0 only) or Pixabay. Nothing here is generated by ElevenLabs:
// the voice is the founder's own (the founder, 2026-10-19).
// Levels are in dB against the voice and are starting values, to be set by ear.

export const SOUND = {
  master: { lufs: -14, truePeakDb: -1 },   // YouTube's loudness reference; louder only gets turned down
  voice: { gainDb: 0, note: "the founder's own recorded voice, the reference everything sits under" },
  bed: { gainDb: -24, duckDb: -6, file: null, licence: null, note: "the music bed; dips a further 6 dB while the voice speaks" },
  ambience: { gainDb: -30, file: null, licence: null, note: "room tone under everything, so silence is never digital zero" },
  cues: {
    reveal: { gainDb: -10, file: null, licence: null, maxPerFilm: 4, afterSilence: true,
      job: "the click: a finding lands. Felt more than heard. Rare, so it stays powerful" },
    leak: { gainDb: -16, file: null, licence: null,
      job: "money leaving: a loss with its minus sign, a riser drawing in blue. Falls and thins" },
    sealed: { gainDb: -14, file: null, licence: null,
      job: "a leak shown sealed, held shut. The opposite of the leak: settles and closes" },
    tick: { gainDb: -26, file: null, licence: null, maxPerSecond: 20,
      job: "a number counting: one tick per change it shows, like a watch movement" },
    turn: { gainDb: -20, file: null, licence: null,
      job: "the move between scenes: a breath of texture, never a swoosh" },
  },
  silence: { ms: VIDEO.motion.silenceMs, job: "everything out before a reveal; scheduled like a sound" },
};

// ---------------------------------------------------------------- helpers

/** Every CSS token as [name, value, note], in stylesheet order. */
export const cssTokens = () => CSS.flatMap(([, rows]) => rows.filter(Boolean));

/** A CSS token's value by name ("blue" → "#0b5fff"). */
export function css(name) {
  const row = cssTokens().find(([n]) => n === name);
  if (!row) throw new Error(`no token --${name}`);
  return row[1];
}

/** A duration token in milliseconds ("count-ms" → 1600). */
export const ms = (name) => parseFloat(css(name));

/**
 * The same curve the browser draws for cubic-bezier(x1, y1, x2, y2), as a
 * function of progress 0..1, so a film frame and a web page land on the same
 * point at the same moment. Newton's method, then bisection where it stalls.
 */
export function cubicBezier(x1, y1, x2, y2) {
  const bx = (t) => ((1 - 3 * x2 + 3 * x1) * t + (3 * x2 - 6 * x1)) * t * t + 3 * x1 * t;
  const by = (t) => ((1 - 3 * y2 + 3 * y1) * t + (3 * y2 - 6 * y1)) * t * t + 3 * y1 * t;
  const dx = (t) => (3 * (1 - 3 * x2 + 3 * x1) * t + 2 * (3 * x2 - 6 * x1)) * t + 3 * x1;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const e = bx(t) - x, d = dx(t);
      if (Math.abs(e) < 1e-7) return by(t);
      if (Math.abs(d) < 1e-6) break;
      t -= e / d;
    }
    let lo = 0, hi = 1;
    t = x;
    for (let i = 0; i < 40; i++) {
      const v = bx(t);
      if (Math.abs(v - x) < 1e-7) break;
      if (v < x) lo = t; else hi = t;
      t = (lo + hi) / 2;
    }
    return by(t);
  };
}

const EASES = {
  "ease-out": () => cubicBezier(...bezierOf("ease-out")),
  "ease-in-out": () => cubicBezier(...bezierOf("ease-in-out")),
  count: () => (p) => 1 - Math.pow(1 - p, 4),           // the count-up's curve (site.js)
  linear: () => (p) => p,
};

function bezierOf(name) {
  const m = css(name).match(/cubic-bezier\(([^)]+)\)/);
  return m[1].split(",").map(Number);
}

/** An easing by name: "ease-out", "ease-in-out", "count" or "linear". */
export function ease(name) {
  const make = EASES[name];
  if (!make) throw new Error(`no easing "${name}"`);
  return make();
}
