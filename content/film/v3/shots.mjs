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
/** Kinds that lay out in type.mjs's box, which narrows to the left when a companion print is set. */
const COMPANION_KINDS = new Set(["number", "pair", "formula", "kinetic", "timeline"]);

/** A record's year as a label prints it; a circa date stays circa ("c. 1900"), never rounded to a fact. */
function yearOf(date) {
  const d = String(date || "").trim();
  // render_shots.display_date has already reduced the record to what may be printed
  if (/^(?:(?:c\.|after|before|since) )?(?:1[5-9]\d\d|20\d\d)(?:–(?:1[5-9]\d\d|20\d\d))?$/.test(d)) return d;
  const y = (d.match(/\b(1[5-9]\d\d|20\d\d)\b/) || [])[0];
  return y && /\b(c\.|ca\.|circa|about)\s*(?=1[5-9]\d\d|20\d\d)/i.test(d) ? `c. ${y}` : y;
}
/** Who made or holds a photograph, as the label names them: the archive or the photographer, never the host. */
function whoOf(a) {
  const host = /^(wikimedia commons|commons|pexels|pixabay|internet archive)$/i;
  // "Smithsonian Institution, National Postal Museum" is the museum's own "Smithsonian National Postal Museum"
  const clean = (x) => String(x || "").replace(/\s+/g, " ").trim().replace(/^Smithsonian Institution, (?:the )?/i, "Smithsonian ");
  const author = clean(a.author);
  // a catalogue's noise is not a name ("API record", "metadata", "see source")
  const noise = /\b(api|record|metadata|see (?:source|file)|original uploader|own work|anonymous)\b/i;
  return author && !/^https?:|unknown/i.test(author) && !noise.test(author) && author.length <= 80 && !host.test(author) ? author
    : a.credit && !/^https?:/.test(a.credit) && !host.test(clean(a.credit)) ? clean(a.credit) : null;
}
/** A photograph's provenance as the label reads it: place · year, then the archive. */
function photoSource(job) {
  const list = Array.isArray(job.assets) ? job.assets : job.asset ? [job.asset] : [];
  const a = list[0] || {};
  const year = yearOf(a.date);
  const where = [a.place, year].filter(Boolean).join(" · ");
  return [where, whoOf(a)].filter(Boolean).join(" — ") || null;
}

/** The one label slot every paper shot shares: the source line, then the honesty label (never
 * optional on a proof or demo figure). Kinds draw no captions of their own. */
/** A typed source as a viewer reads it: never the repository file we keep a figure in
    ("…, as recorded in ratecard.json on September 9, 2026", "(data/case-study.json)"). */
export function cleanSource(text) {
  return String(text || "")
    .replace(/,?\s*as recorded in [\w./-]+\.(?:json|xlsx|csv)(?: on (?:[A-Z][a-z]+ \d{1,2}, \d{4}|[^,·;()]+))?/gi, "")
    .replace(/\s*\([^()]*\.(?:json|xlsx|csv)[^()]*\)/gi, "")
    .replace(/\s*[\w./-]+\.(?:json|xlsx|csv)\b/gi, "")
    .replace(/\s*\((?:[a-z_]+\.)+[a-z_]+\)/g, "")
    .replace(/\s+([,;·])/g, "$1").replace(/[,;\s]+$/, "").trim() || null;
}

/** When a source line may appear: a line that names a figure this shot says ("report of December 1,
    1914") waits for that figure's word, like the figure itself; any other source stands at the cut. */
function sourceAt(job, text) {
  const t = String(text || "");
  let at = 0;
  for (const r of job.reveals || []) {
    const v = String(r.value ?? "").trim();
    if (!v || r.t == null) continue;
    const nums = v.match(/\d[\d,.]*\d|\d/g) || [];
    const hit = t.includes(v) || nums.some((n) => n.length >= 2 && new RegExp(`(^|[^\\d])${n.replace(/[.,]/g, "\\$&")}(?![\\d])`).test(t));
    if (hit) at = Math.max(at, +r.t);
  }
  return at;
}

export function labels(job) {
  const honest = job.label === "proof" ? PROOF : job.label === "demo" ? job.demo_label : null;
  const source = cleanSource(["document", "table", "receipt"].includes(job.kind) ? job.params?.source
    : ["archive", "split", "stack"].includes(job.kind) ? photoSource(job)
    : ["quote", "kinetic", "chapter", "end"].includes(job.kind) ? null
    : job.source_label);
  // a companion print says what it is ("A posed photograph") and where it is from, on its own line,
  // and leaves the desk with the print (`out`)
  const P = job.print || {};
  const comp = P.url ? [[P.caption, yearOf(P.date)].filter(Boolean).join(", "), whoOf(P)].filter(Boolean).join(" · ") : null;
  if (!honest && !source && !comp) return "";
  const wait = source ? sourceAt(job, source) : 0;
  const srcP = source ? `<p class="source${wait > 0.4 ? " lab-wait" : ""}"${wait > 0.4 ? ` style="--at:${(wait - 0.1).toFixed(2)}"` : ""}>${esc(source)}</p>` : "";
  const compP = comp ? `<p class="source${P.out != null ? " lab-leave" : ""}"${P.out != null ? ` style="--at:${(Math.max(0, +P.out - 0.45)).toFixed(2)}"` : ""}>${esc(comp)}</p>` : "";
  // the honesty label is never delayed and never leaves: it is on every frame of a proof or demo figure
  return `<div class="labels${comp ? " with-print" : ""}">${srcP}${compP}${honest ? `<p class="honesty">${esc(honest)}</p>` : ""}</div>`;
}
/** @deprecated kept for kinds written before the label slot; draws the same slot. */
export const honesty = labels;

export function shotHTML(job, built) {
  const draw = KINDS[job.kind];
  if (!draw) throw new Error(`v3 has no renderer for kind ${job.kind}`);
  const inner = draw(job, built);
  if (WORLD.has(job.kind)) return inner;          // a world picture is its own frame
  const comp = COMPANION_KINDS.has(job.kind) ? photos.companion(job) : "";
  return `<section class="v3 v3-${esc(job.kind)}" style="--dur:${job.seconds}s;--dur-n:${job.seconds}"><div class="key"></div>${comp}${inner}` +
    `<div class="grade"></div><div class="vignette"></div>${labels(job)}</section>`;
}
