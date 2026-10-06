// v3: one shot of a long film as HTML on the dark archive stage (content/film/v3/stage.html).
// A pure function, like ../shots.mjs: a resolved job in (render_shots.py: figures filled from
// facts.json, every time relative to the shot's first frame, assets graded), a string out.
// This file owns only the frame around a shot (key light, grade, vignette, the honesty label);
// each kind lives in kinds/*.mjs with its own CSS, so the look can be built kind by kind.
import * as documents from "./kinds/documents.mjs";
import * as photos from "./kinds/photos.mjs";
import * as type from "./kinds/type.mjs";
import * as charts from "./kinds/charts.mjs";

export const PROOF = "Modeled from public data · Not a client · Not a result";
export const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const KINDS = {
  document: documents.document, table: documents.table, quote: documents.quote, receipt: documents.receipt,
  still: photos.still, texture: photos.still, archive: photos.archive, stack: photos.stack, split: photos.split,
  number: type.number, pair: type.pair, grid: type.grid, kinetic: type.kinetic, formula: type.formula,
  timeline: type.timeline, chapter: type.chapter, end: type.end,
  chart: charts.chart,
};
const WORLD = new Set(["still", "texture"]);

/** A photograph's provenance as the label reads it: place · year, then the archive. */
function photoSource(job) {
  const list = Array.isArray(job.assets) ? job.assets : job.asset ? [job.asset] : [];
  const a = list[0] || {};
  const year = (String(a.date || "").match(/\b(1[5-9]\d\d|20\d\d)\b/) || [])[0];
  const where = [a.place, year].filter(Boolean).join(" · ");
  // the archive or the photographer, never the site that hosts the scan ("Wikimedia Commons")
  const host = /^(wikimedia commons|commons|pexels|pixabay|internet archive)$/i;
  const clean = (x) => String(x || "").replace(/\s+/g, " ").trim();
  const author = clean(a.author);
  const who = author && !/^https?:|unknown/i.test(author) && author.length <= 80 && !host.test(author) ? author
    : a.credit && !/^https?:/.test(a.credit) && !host.test(clean(a.credit)) ? clean(a.credit) : null;
  return [where, who].filter(Boolean).join(" — ") || null;
}

/** The one label slot every paper shot shares: the source line, then the honesty label (never
 * optional on a proof or demo figure). Kinds draw no captions of their own. */
export function labels(job) {
  const honest = job.label === "proof" ? PROOF : job.label === "demo" ? job.demo_label : null;
  const source = ["document", "table", "receipt"].includes(job.kind) ? job.params?.source
    : ["archive", "split", "stack"].includes(job.kind) ? photoSource(job)
    : ["quote", "kinetic", "chapter", "end"].includes(job.kind) ? null
    : job.source_label;
  if (!honest && !source) return "";
  return `<div class="labels">${source ? `<p class="source">${esc(source)}</p>` : ""}${honest ? `<p class="honesty">${esc(honest)}</p>` : ""}</div>`;
}
/** @deprecated kept for kinds written before the label slot; draws the same slot. */
export const honesty = labels;

export function shotHTML(job, built) {
  const draw = KINDS[job.kind];
  if (!draw) throw new Error(`v3 has no renderer for kind ${job.kind}`);
  const inner = draw(job, built);
  if (WORLD.has(job.kind)) return inner;          // a world picture is its own frame
  return `<section class="v3 v3-${esc(job.kind)}" style="--dur:${job.seconds}s;--dur-n:${job.seconds}"><div class="key"></div>${inner}` +
    `<div class="grade"></div><div class="vignette"></div>${labels(job)}</section>`;
}
