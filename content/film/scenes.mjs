// A film scene as HTML on the site's design system. Pure functions: a scene's spec and
// the site's built figures in, a string out. The charts are the site's own blocks
// (scripts/build-pages.mjs, drawn by /assets/charts.mjs), so the staircase in a film
// is the staircase on the home page, never a redrawing of it.
import { staircaseSVG, monteCarloSVG, agingSVG } from "../../assets/charts.mjs";

// The house visuals at film size: the same functions that draw them on the home page,
// on a wider stage with labels a phone can read (font 30 in a 1200-wide box renders
// near 40 px at 1080p).
export const FILM_CHART = {
  staircase: (c) => staircaseSVG(c.stairs, { id: "fs", w: 1200, h: 560, m: { t: 104, r: 48, b: 76, l: 124 }, font: 30, xMax: 16 }),
  montecarlo: (c) => monteCarloSVG(c.mc, { id: "fm", w: 1200, h: 480, m: { t: 24, r: 270, b: 76, l: 150 }, font: 30 }),
  aging: (c) => agingSVG(c.aging, { id: "fa", w: 1200, h: 480, m: { t: 64, r: 48, b: 76, l: 124 }, font: 30 }),
};

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const LABEL = "Modeled from public data · Not a client · Not a result";
const MARK = `<span class="mark"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>Hubricon</span>`;

/** Text with {{key}} placeholders filled from the site's figures; an unknown key is an error, never a guess. */
export function fill(text, figures) {
  return String(text).replace(/\{\{\s*([a-z0-9_]+)\s*\}\}/g, (_, k) => {
    if (!(k in figures)) throw new Error(`no figure ${k}`);
    return figures[k];
  });
}

const corner = (proof) => `<div class="corner">${proof ? `<span class="label label-box">${LABEL}</span>` : ""}${MARK}</div>`;
const at = (ms) => `style="--at:${ms}ms"`;

/** The scene kinds the script guard knows (content/src/hubricon_content/script.py). */
export function sceneHTML(spec, built, facts = {}) {
  const F = { ...built.fill, ...facts };
  const t = (s) => esc(fill(s, F));
  switch (spec.kind) {
    case "kinetic":
      return `<section class="scene">${spec.kicker ? `<p class="kicker in">${t(spec.kicker)}</p>` : ""}${spec.lines.map((l, i) =>
        `<p class="display${spec.small ? " small" : ""} in" ${at(300 + i * 900)}>${t(l)}</p>`).join("")}${corner(spec.proof)}</section>`;
    case "number":
      return `<section class="scene"><p class="number${spec.ink ? " ink" : ""} in">${t(spec.value)}${spec.estimate ? `<span class="est">estimate</span>` : ""}</p>` +
        `${spec.sub ? `<p class="number-sub in" ${at(600)}>${t(spec.sub)}</p>` : ""}${corner(spec.proof)}</section>`;
    case "staircase":
    case "montecarlo":
    case "aging": {
      return `<section class="scene top"><h2 class="heading in">${t(spec.heading)}</h2>` +
        `${spec.caption ? `<p class="caption in" ${at(250)}>${t(spec.caption)}</p>` : ""}` +
        `<figure class="chart-frame figure" data-play>${FILM_CHART[spec.kind](built.charts)}</figure>${corner(true)}</section>`;
    }
    case "formula":
      return `<section class="scene">${spec.kicker ? `<p class="kicker in">${t(spec.kicker)}</p>` : ""}<div class="formula in" ${at(300)}>` +
        spec.lines.map((l) => `<p>${t(l)}</p>`).join("") + `</div>${spec.caption ? `<p class="caption in" ${at(900)}>${t(spec.caption)}</p>` : ""}${corner(spec.proof)}</section>`;
    case "end":
      return `<section class="scene"><p class="display small in">${t(spec.headline)}</p><div class="ctas in" ${at(700)}>` +
        `<span class="cta-btn">${t(spec.primary)} <span aria-hidden="true">→</span></span>` +
        `${spec.secondary ? `<span class="cta-quiet">${t(spec.secondary)}</span>` : ""}</div>${corner(false)}</section>`;
    default:
      throw new Error(`unknown scene kind ${spec.kind}`);
  }
}

/**
 * The style reel: the look, frozen before any approved script is rendered. Every word
 * on it is already published on the home page; every number is the site's own figure.
 */
export const STYLE_REEL = {
  name: "style-reel",
  scenes: [
    { id: "s1", kind: "kinetic", seconds: 5, lines: ["Your mental model is linear.", "Amazon's cost structure is a staircase."] },
    { id: "s2", kind: "staircase", seconds: 7, heading: "Less than an ounce past the edge. Paid on every unit.",
      caption: "Dashed: the holiday card." },
    { id: "s3", kind: "number", seconds: 5, value: "{{leak_p10}} to {{leak_p90}}", estimate: true, sub: "a year, paid on one step of Amazon's fee staircase.", proof: true },
    { id: "s4", kind: "montecarlo", seconds: 7, heading: "Ten thousand years of this one listing",
      caption: "Each faint line is one simulated year. The band holds eight in ten." },
    { id: "s5", kind: "aging", seconds: 7, heading: "The cliff public pages can't see",
      caption: "From day 271: {{aged_rate_before}} to {{aged_rate_after}} a cubic foot." },
    { id: "s6", kind: "end", seconds: 5, headline: "More profit than our bill every month, or you don't pay.", primary: "Book your call", secondary: "or learn the method, free, at hubricon.com/learn" },
  ],
};
