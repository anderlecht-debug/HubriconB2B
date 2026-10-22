/* ============================================================================
   The staircase: a fee card drawn as what it is, steps, and the one step that
   is costing the listing money.

   A fee card is not a curve. Inside a band the fee is flat; at the band's edge
   it jumps. So the card is drawn as exact steps from the card itself (the line
   component's "step" shape), and only the card in force today: last season's
   card is not drawn beside it, and no dates label it.

   Built to the scoreboard's ladder (HUBRICON_SPEC.md, "the 11-out-of-5"):
   5  Exact steps from the card in force; the listing's step in blue, with
      what it costs a unit and, estimated, a year.
   7  Touch reads the card at any weight, to a tenth of an ounce: the fee,
      and where the next step comes and what it costs (the line's reading).
   9  It is yours: "Your shipping weight" puts your own parcel on the card.
      The reading moves to it, and a sentence says where you stand.
   10 It meets the scary moment first. Just past an edge: how much lighter
      would save how much a unit. Just under one: what creeping over costs.
      These are the two moments that move money on a fee card.
   11 The card (line.mjs lineCard) takes the chart into someone else's deck.

   Pure functions; the data comes in already priced (scripts/build-pages.mjs
   reads the rate card with lib/fees.js), so this file runs in a browser, in
   Node and in the film renderer alike.
   ============================================================================ */

import { lineChart, lineCard, playLine } from "./line.mjs";

/**
 * st: {
 *   treads: [[edge, fee], ...]     each fee applies up to and including its edge (the card in force)
 *   unit: "oz", xMax                the weight axis
 *   money(v)                        how a fee is said ("$4.64")
 *   listing?: { oz, fee }, edge?: { oz, fee }, step?    the case: where the listing sits, the edge below it, the step
 *   range?: { p10, p90 }            what the step costs a year, 1 in 10 low to 1 in 10 high (simulated)
 *   title?, subtitle?, source?, label?
 * }
 */
export function stairsSpec(st, { w = 760, h = 440, font = 13, paint = "css", ground, id = "stairs", title = true } = {}) {
  const u = st.unit || "oz", xMax = st.xMax ?? st.treads[st.treads.length - 1][0];
  const fmt = (v) => `${+v.toFixed(2)}`;
  const money = st.money || ((v) => `$${v.toFixed(2)}`);
  const rows = st.treads.filter(([e]) => e < xMax);
  const pts = [[0, st.treads[0][1]]];
  rows.forEach(([edge], i) => pts.push([edge, st.treads[i + 1][1]]));
  pts.push([xMax, (st.treads.find(([e]) => e >= xMax) || st.treads[st.treads.length - 1])[1]]);
  const ticks = niceEdges(xMax);
  const spec = {
    w, h, font, paint, ground, id,
    title: title ? st.title : null, subtitle: title ? st.subtitle : null, source: st.source, label: st.label,
    x: { domain: [0, xMax], ticks, format: (v, last) => (last ? `${v} ${u}` : `${v}`), read: (v) => `${v.toFixed(1)} ${u}`, snap: 0.1 },
    y: { format: money, read: (v) => `${money(v)} a unit` },
    series: [{ id: "card", points: pts, kind: "step", role: "focus", short: "", tip: money }],
    risers: [], dots: [], notes: [],
    fall: false,
  };
  if (st.listing && st.edge && st.step) {
    spec.risers.push({ x: st.edge.oz, y0: st.edge.fee, y1: st.listing.fee });
    spec.dots.push({ x: st.edge.oz, y: st.edge.fee, hollow: true, label: `${fmt(st.edge.oz)} ${u}, one step down` });
    spec.dots.push({ x: st.listing.oz, y: st.listing.fee, label: `This listing, ${st.listing.oz.toFixed(1)} ${u}`, emphasis: true });
    spec.notes.push({ x: st.edge.oz, y: (st.edge.fee + st.listing.fee) / 2, title: `+${money(st.step)} a unit`,
      body: st.range ? `${dollars(st.range.p10)}–${dollars(st.range.p90)} a year, estimate` : undefined });
  }
  return spec;
}

/** Where a weight stands on the card: its fee, the edge below and above, and what each would mean. */
export function weighIn(treads, oz) {
  const k = treads.findIndex(([e]) => oz <= e + 1e-9);
  if (k < 0) return null;
  const fee = treads[k][1];
  const below = k > 0 ? { edge: treads[k - 1][0], fee: treads[k - 1][1] } : null;
  const above = k + 1 < treads.length ? { edge: treads[k][0], fee: treads[k + 1][1] } : null;
  return {
    oz, fee,
    below: below && { ...below, overBy: oz - below.edge, saves: fee - below.fee },
    above: above && { ...above, under: above.edge - oz, costs: above.fee - fee },
  };
}

/**
 * Rung 10, in one sentence: just past an edge, how much lighter saves how much; just under one,
 * what creeping over costs; otherwise, how far the nearest edge is. `near` is how close counts.
 */
export function weighInWords(st, oz, { near = 1 } = {}) {
  const w = weighIn(st.treads, oz), u = st.unit || "oz";
  const money = st.money || ((v) => `$${v.toFixed(2)}`);
  if (!w) return `Past the last band on this card.`;
  const at = `At ${ozs(oz)} ${u} the fee is ${money(w.fee)} a unit.`;
  const trim = w.below && Math.ceil(w.below.overBy * 100 - 1e-6) / 100;
  if (w.below && w.below.overBy <= near && w.below.saves > 0)
    return `${at} You are ${ozs(trim)} ${u} past the ${ozs(w.below.edge)} ${u} edge: ${ozs(trim)} ${u} lighter would save ${money(w.below.saves)} a unit.`;
  if (w.above && w.above.under <= near / 2 && w.above.costs > 0)
    return `${at} You are ${ozs(w.above.under)} ${u} under the ${ozs(w.above.edge)} ${u} edge: creep over it and each unit costs ${money(w.above.costs)} more.`;
  const gaps = [w.below && w.below.overBy, w.above && w.above.under].filter((g) => g != null);
  return gaps.length ? `${at} The nearest edge is ${ozs(Math.min(...gaps))} ${u} away.` : at;
}

/**
 * The control, as HTML: a number to type and a slider to drag, both "Your shipping weight", and
 * the sentence. Finished with no script (it says where the case listing stands); a script makes it live.
 */
export function weighInHTML(st, { id = "weigh", start } = {}) {
  const u = st.unit || "oz", xMax = st.xMax ?? st.treads[st.treads.length - 1][0];
  const oz = start ?? st.listing?.oz ?? st.treads[0][0];
  const v = (+oz).toFixed(1);
  return `<div class="weigh" id="${esc(id)}">` +
    `<label class="weigh-field"><span>Your shipping weight</span><span class="weigh-in"><input type="number" inputmode="decimal" min="0.1" max="${xMax}" step="0.1" value="${v}" aria-describedby="${esc(id)}-says"><span>${esc(u)}</span></span></label>` +
    `<input class="weigh-slide" type="range" min="0.1" max="${xMax}" step="0.1" value="${v}" aria-label="Your shipping weight, in ${esc(u)}">` +
    `<output class="weigh-says" id="${esc(id)}-says" aria-live="polite">${esc(weighInWords(st, +oz))}</output>` +
    `</div>`;
}

/**
 * Play the staircase in a page, with its control: the draw-in, then the reading follows the
 * visitor's weight, typed or dragged, and touch still reads anywhere. Returns a stop function.
 */
export function playStairs(host, st, opts = {}, control = null) {
  const stop = playLine(host, stairsSpec(st, opts), opts.player);
  if (!control) return stop;
  const num = control.querySelector('input[type="number"]'), slide = control.querySelector(".weigh-slide"), says = control.querySelector(".weigh-says");
  const xMax = st.xMax ?? st.treads[st.treads.length - 1][0];
  const set = (raw, from) => {
    const oz = Math.min(xMax, Math.max(0.1, Math.round(+raw * 10) / 10));
    if (!Number.isFinite(oz)) return;
    if (from !== num) num.value = oz.toFixed(1);
    if (from !== slide) slide.value = oz.toFixed(1);
    says.textContent = weighInWords(st, oz);
    stop.read(oz);
  };
  num.addEventListener("input", () => { if (num.value !== "") set(num.value, num); });
  slide.addEventListener("input", () => set(slide.value, slide));
  set(num.value, null);
  return stop;
}

/** The staircase's card for a deck. */
export const stairsCard = (st, opts = {}) => lineCard({ ...stairsSpec(st, { ...opts, paint: "inline" }), cardTitle: st.title });

// ---------------------------------------------------------------- helpers

const ozs = (v) => `${+(+v).toFixed(2)}`;
const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
/** Weight ticks every 4 up to the axis's end (or every 2 on a short card), ending on it. */
function niceEdges(xMax) {
  const step = xMax > 12 ? 4 : 2, out = [];
  for (let v = 0; v < xMax - 1e-9; v += step) out.push(v);
  out.push(xMax);
  return out;
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
