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
  },
};

// Each group below starts from what is physically true about how the thing is seen,
// and derives its numbers from that, in the file, so a rule can be checked rather
// than argued. Rockefeller asked how many drops of solder sealed a can: forty, then
// thirty-eight leaked, thirty-nine held. Same standard: the least that works, measured.

// ---------------------------------------------------------------- the thumbnail
// True: it is judged in under a second, at its smallest about 168px wide (the
// watch-next column), in a feed of saturated, dark, shouting images, on a dark
// page for many viewers and a white one for the rest. So: anything that does not
// survive being shrunk to 168px does not exist; the way to be seen is contrast with
// the feed, not volume; and recognition comes from the same layout every time,
// because a logo is a smudge at that size.

const THUMB_W = 1280, SMALLEST_SHOWN = 168;
const AT_SMALLEST = SMALLEST_SHOWN / THUMB_W;           // 0.131: one unit here is 0.13px there
const INTER_CAP = 0.727;                               // Inter's capital height, as a share of its size

export const THUMB = {
  frame: { w: THUMB_W, h: 720 },
  render: { scale: 3 },                                 // 3840×2160, YouTube's recommended size; upload from desktop (50 MB cap; the phone app's is 2 MB)
  smallestShown: SMALLEST_SHOWN,
  // A stroke thinner than one screen pixel at the smallest size vanishes, so no
  // hairline exists in a thumbnail: nothing is drawn under 8 units. The chart's lines
  // are as heavy as the title's letter stems (Inter 600 at 144 is about 16 units), so
  // the words and the chart read as one object. The leak, the only colour, is twice that.
  minStroke: Math.ceil(1 / AT_SMALLEST),                // 8: one screen pixel at 168px
  lineStroke: 16,                                       // 2.1px at 168px, the weight of the letters
  leakStroke: 32,                                       // 4.2px at 168px: the heaviest mark in the image
  // Words: three at most, two lines at most, and a capital at least 12 screen
  // pixels tall at 168px wide, the smallest text a phone's own interface uses.
  words: { max: 3, lines: 2, px: 144, leading: 1, weight: 600, track: "-0.032em",
    capAtSmallestPx: +(144 * INTER_CAP * AT_SMALLEST).toFixed(1) },      // 13.7
  // One layout, every video. The claim top-left where the eye lands first, the
  // film's own chart beneath it as the evidence and the face. Units of the 1280×720 frame.
  boxes: {
    words: { x: 72, y: 56, w: 1136, h: 288 },
    chart: { x: 72, y: 368, w: 928, h: 300 },
  },
  // YouTube paints over these: the running time bottom-right, and a progress bar
  // along the bottom on anything the viewer has started. Nothing of ours goes there.
  keepOut: [
    { name: "running time", x: 1040, y: 600, w: 240, h: 120 },
    { name: "progress bar", x: 0, y: 688, w: 1280, h: 32 },
  ],
  ground: "paper",       // white in a dark feed is the brightest thing on the page; in a white feed the ink carries it
  blue: "the leak only, and the only colour in the image",
  honesty: "every figure on a thumbnail is stated, sourced and labelled in the film's first minute",
  variants: { max: 3, change: "the words only", decidedBy: "watch time share" },   // YouTube's Test & Compare; Shorts excluded
  judge: { feeds: ["dark", "light"], widths: [168, 360] },                       // look at it where it lives before it ships
  never: ["a face", "arrows or circles", "emoji", "outlined or shadowed text", "a gradient", "a second colour",
    "the logo", "more than three words", "a number the film does not state"],
};

// ---------------------------------------------------------------- captions
// True: captions exist for a viewer with the sound off, and reading is a fixed
// cost: the eye has to find the line, then read it. Words that move, bounce or
// change colour make the eye find them again on every change. So captions sit
// still, appear a phrase at a time, and change colour once, for one reason.

const CPS = 17;                                         // characters a second: the reading speed subtitle standards hold to

export const CAPTIONS = {
  // Long films: nothing burned into the picture. The exact script, timed from the
  // recording, is uploaded as the caption file, so anyone who turns captions on
  // reads your words instead of a machine's guesses, and nobody else sees two copies.
  longForm: "the exact script as the caption file; nothing burned in",
  // Clips (Shorts, Reels, TikTok), mostly watched muted: burned in, in their own band.
  clips: {
    px: 64, leading: 1.2, weight: 600, track: "-0.01em",
    maxLines: 2,
    maxCharsPerLine: 22,                                // 22 × about 35px = the 840px between the safe-area edges, with room
    cps: CPS,
    minMs: 900,                                         // a short phrase still gets time to be read
    fadeMs: 100,                                        // appears whole; never pops, slides or scales
    breakAt: "phrase ends; a figure is never split from its unit",
    colour: "ink; a dollar figure turns blue on the same frame its chart turns blue",
    band: "captions own a band at the foot of the safe area; no data sits in it",
  },
  never: ["word-by-word reveal", "bouncing, popping or scaling", "karaoke highlighting", "a colour per word",
    "outlines or boxes behind the text", "emoji", "all capitals"],
};

// ---------------------------------------------------------------- the finish
// True: grain, vignettes and glow were invented to hide what a camera got wrong:
// noise, soft corners, blown highlights. A film drawn from exact numbers has nothing
// to hide, and a precision brand should not look like it is hiding anything. So the
// finish is sharpness: rendered at twice the size it is watched and scaled down,
// at 60 frames, with the colours exactly the tokens. The one thing borrowed from
// real cameras is motion blur, and only where a real shutter would show it.

export const FINISH = {
  sharpness: "rendered at 2× (3840×2160) and 60 frames; scaled down, every edge is clean",
  // A fast move at 60 frames jumps in visible steps. A real 180° shutter smears an
  // object by the distance it travels in half a frame. Below this speed nothing is
  // blurred, so type stays crisp on every ordinary move. Starting value.
  motionBlur: { shutterAngle: 180, samples: 8, onlyAbovePxPerFrame: 16 },   // 16px a frame at 1080p = 960px a second
  // Depth from movement, never from blur: while the camera travels, the scene it is
  // travelling to arrives a little slower than the one it leaves, then lands exactly.
  // Never inside a chart: its grid is the measurement and stays locked to the data.
  depth: { parallax: 0.92, appliesTo: "the scene the camera is travelling to", never: "inside a chart" },
  grade: "none: the colours on screen are the tokens' values, exactly",
  never: ["film grain", "vignette", "glow or bloom", "drop shadows", "lens flare", "chromatic aberration",
    "light leaks or film burns", "a colour grade or LUT", "letterbox bars", "camera shake"],
};

// ---------------------------------------------------------------- the camera
// True: a camera move tells the viewer "look here", and nothing else. Two moves at
// once, or a move while they are reading, splits attention; Napoleon's rule was to
// mass force at the decisive point, and a frame works the same way. So: one move a
// beat, only towards the data the next line is about, never while text is being read.
// And the film is one continuous canvas: every chart sits beside the last, and the
// camera travels between them instead of cutting, so the viewer sees how one idea
// leads to the next. The only cut is an act break, to night.

export const CAMERA = {
  ease: "ease-in-out",                                  // starts and stops like something with mass; arrivals still use ease-out
  movesPerBeat: 1,
  target: "the data the next line is about",
  waitsForReading: { cps: CPS },                        // a move starts once the text on screen has had its reading time
  zoom: { min: 1, max: 3, maxPerMove: 2 },              // past 3×, the viewer loses where they are on the canvas. Starting value
  // Travel time grows with distance, so speed stays calm: 700 ms plus 500 ms for
  // each frame-width crossed, never under 0.9 s or over 2 s. Starting value.
  travel: { baseMs: 700, perFrameMs: 500, minMs: 900, maxMs: 2000 },
  canvas: { continuous: true, gap: 0.25 },              // scenes side by side, a quarter frame apart
  cutsOnlyAt: "an act break, to night",
  never: ["rotation", "shake", "two moves at once", "a move while text is being read", "a zoom for emphasis alone"],
};

/** How long the camera takes to travel `frames` frame-widths. */
export function travelMs(frames) {
  const t = CAMERA.travel;
  return Math.round(Math.min(t.maxMs, Math.max(t.minMs, t.baseMs + t.perFrameMs * frames)));
}

/** How long a line of text must stay readable before anything moves: its length at the reading speed. */
export const readingMs = (text) => Math.max(CAPTIONS.clips.minMs, Math.round((String(text).length / CPS) * 1000));

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
      job: "the camera travelling to the next scene: a breath of texture, never a swoosh" },
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
