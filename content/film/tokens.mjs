// The films' one source of colour and type: the site's own tokens, read from
// /assets/hubricon.css (the file the film stage itself loads) and written to
// content/assets/tokens.json for everything that is not a web page: Manim, the
// subtitles, the thumbnail, the shorts, the grade (VISUAL_SPEC.md §3.1). Run before
// every render, so a token change on the site reaches the films the same day. The
// stage's own measures (content/film/film.css) come along, so Manim sets type at the
// stage's sizes and margins without a second copy of them.
//
//   node content/film/tokens.mjs            write tokens.json (prints "unchanged" when it is)
//   node content/film/tokens.mjs --check    exit 1 if tokens.json is behind the CSS
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../../", import.meta.url).pathname;
export const CSS = join(ROOT, "assets/hubricon.css");
export const FILM_CSS = join(ROOT, "content/film/film.css");
export const OUT = join(ROOT, "content/assets/tokens.json");

// The stage's own measures, read from film.css so Manim, the thumbnail and the
// subtitles lay type out exactly as the stage does: [selector, property].
const STAGE = {
  pad_px: [".scene", "padding"], pad_top_chart_px: [".scene.top", "padding-top"],
  kicker_px: [".kicker", "font-size"], display_px: [".display", "font-size"], display_track_em: [".display", "letter-spacing"],
  display_small_px: [".display.small", "font-size"], heading_px: [".heading", "font-size"],
  heading_track_em: [".heading", "letter-spacing"], caption_px: [".caption", "font-size"],
  number_px: [".number", "font-size"], number_track_em: [".number", "letter-spacing"],
  number_sub_px: [".number-sub", "font-size"], number_sub_track_em: [".number-sub", "letter-spacing"],
  corner_bottom_px: [".corner", "bottom"], label_px: [".corner .label-box", "font-size"],
  label_pad_px: [".corner .label-box", "padding"], label_track_em: [".corner .label-box", "letter-spacing"],
  mark_px: [".mark", "font-size"], mark_track_em: [".mark", "letter-spacing"], mark_icon_px: [".mark svg", "width"],
};

/** A property of the film.css rule whose selector list holds `selector` exactly. */
function declared(css, selector, prop) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, sel, body] of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!sel.split(",").map((x) => x.trim()).includes(selector)) continue;
    const m = new RegExp(`(?:^|[;\\s])${prop}\\s*:\\s*([^;]+)`).exec(body);
    if (m) return m[1].trim();
  }
  throw new Error(`content/film/film.css sets no ${prop} on ${selector}`);
}

/** "120px 160px 132px" → [120, 160, 132]; "var(--track-display)" → -0.032; "-0.02em" → -0.02. */
function measure(v, root) {
  const r = /^var\(--([a-z0-9-]+)\)$/.exec(v);
  if (r) v = root[r[1]];
  const parts = v.split(/\s+/).map((x) => {
    const m = /^(-?[\d.]+)(px|em)$/.exec(x);
    if (!m) throw new Error(`not a px or em measure: ${v}`);
    return Number(m[1]);
  });
  return parts.length === 1 ? parts[0] : parts;
}

/** Every custom property declared in a top-level `:root { … }` block, in order. */
export function rootProperties(css) {
  const props = {};
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, body] of text.matchAll(/(?:^|\n):root\s*\{([^}]*)\}/g)) {
    for (const [, name, value] of body.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)) props[name] = value.trim();
  }
  return props;
}

const px = (v) => {
  const m = /^(-?[\d.]+)px$/.exec(v);
  if (!m) throw new Error(`not a px length: ${v}`);
  return Number(m[1]);
};
const em = (v) => Number(/^(-?[\d.]+)em$/.exec(v)[1]);
const hex = (v) => {
  if (!/^#[0-9a-f]{6}$/i.test(v)) throw new Error(`not a six-digit colour: ${v}`);
  return v.toLowerCase();
};

const COLOURS = ["paper", "paper-2", "ink", "ink-2", "ink-3", "ink-4", "rule", "rule-2", "blue",
  "night", "night-2", "night-ink", "night-ink-2", "night-ink-3", "night-ink-4", "night-rule", "night-blue"];

export function tokens(css = readFileSync(CSS, "utf8"), film = readFileSync(FILM_CSS, "utf8")) {
  const p = rootProperties(css);
  const need = (k) => { if (!(k in p)) throw new Error(`--${k} is not in /assets/hubricon.css`); return p[k]; };
  const family = /^"([^"]+)"/.exec(need("font"))[1];
  const bezier = /cubic-bezier\(([^)]+)\)/.exec(need("ease-out"))[1].split(",").map(Number);
  return {
    source: "assets/hubricon.css",
    colour: Object.fromEntries(COLOURS.map((k) => [k.replace(/-/g, "_"), hex(need(k))])),
    // rgb(11 95 255 / 0.07): kept as the CSS writes it; Python reads it with tokens.rgba().
    blue_wash: need("blue-wash"),
    font: { family, display: `${family} Display`, regular: Number(need("regular")), strong: Number(need("strong")),
            track_display_em: em(need("track-display")), track_label_em: em(need("track-label")) },
    space: Object.fromEntries(Array.from({ length: 10 }, (_, i) => [`s${i + 1}`, px(need(`s-${i + 1}`))])),
    radius: px(need("radius")),
    line: { hair: px(need("line-hair")), step: px(need("line-step")), pct: px(need("line-pct")), leak: px(need("line-leak")) },
    chart: { path_draw: Number(need("mc-path-draw")), path_rest: Number(need("mc-path-rest")), band: Number(need("mc-band")) },
    ease_out: bezier,
    stage: Object.fromEntries(Object.entries(STAGE).map(([k, [sel, prop]]) => [k, measure(declared(film, sel, prop), p)])),
  };
}

export function write() {
  const text = JSON.stringify(tokens(), null, 2) + "\n";
  const same = existsSync(OUT) && readFileSync(OUT, "utf8") === text;
  if (!same) writeFileSync(OUT, text);
  return same;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv.includes("--check")) {
    const ok = existsSync(OUT) && readFileSync(OUT, "utf8") === JSON.stringify(tokens(), null, 2) + "\n";
    console.log(ok ? "tokens.json matches /assets/hubricon.css" : "tokens.json is behind /assets/hubricon.css: run node content/film/tokens.mjs");
    process.exit(ok ? 0 : 1);
  }
  console.log(write() ? `${OUT} unchanged` : `${OUT} written`);
}
