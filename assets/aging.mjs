/* ============================================================================
   The aging cliff: what Amazon charges a month to keep stock that has sat too
   long, by its age in storage, and the one day the charge jumps.

   It is a stepped schedule like a fee card, so it is drawn by the staircase
   (assets/staircase.mjs): exact steps, only the aged-inventory surcharge (it
   does not change with the season, so the chart is never out of date), the
   jump at day 271 in blue with its multiple worked out from the schedule.
   The horizontal axis is a unit's age, a numerical driver like weight; no
   date or month labels it (HUBRICON_SPEC.md, "No time scales on a chart").

   Rung 9 and 10 in one control: "Your oldest stock" in days. Age only grows,
   so the sentence looks ahead: what it pays now, how many days until the next
   band and what that band pays, and, before day 271, the cliff by name.
   ============================================================================ */

import { stairsSpec, weighIn, weighInHTML, playStairs } from "./staircase.mjs";

const usd = (v) => { const r = Math.round(v); return `${r < 0 ? "−" : ""}$${Math.abs(r).toLocaleString("en-US")}`; };

/**
 * The schedule for one listing, from the case study's aging block: the surcharge a month for
 * 1,000 of its units, by days in storage. Each band's charge applies up to and including the
 * day before the next band starts, so day 270 is still the band below the cliff.
 */
export function agingSchedule(aging, { xMax = 400, source } = {}) {
  const k = aging.cubic_feet_per_unit * 1000;
  const bands = aging.bands.slice().sort((a, b) => a.from - b.from);
  const treads = [[bands[0].from - 1, 0], ...bands.map((b, i) => [bands[i + 1] ? bands[i + 1].from - 1 : xMax, b.surcharge_per_cuft * k])];
  // the cliff: the band whose charge jumps by the largest multiple over the band before it
  let cliff = null;
  for (let i = 1; i < bands.length; i++) {
    const x = bands[i].surcharge_per_cuft / bands[i - 1].surcharge_per_cuft;
    if (!cliff || x > cliff.times) cliff = { day: bands[i].from, times: x, before: bands[i - 1].surcharge_per_cuft * k, after: bands[i].surcharge_per_cuft * k, cuftBefore: bands[i - 1].surcharge_per_cuft, cuftAfter: bands[i].surcharge_per_cuft };
  }
  const times = `${cliff.times.toFixed(1)}×`;
  return {
    treads, unit: "days", xMax, inc: 1, per: "per 1,000 units a month", money: usd, cliff,
    read: (v) => `${Math.round(v)} days in storage`,
    ticks: [0, bands[0].from, cliff.day, ...bands.filter((b) => b.from > cliff.day && b.from <= xMax && b.from >= 360).map((b) => b.from)],
    finding: { x: cliff.day - 1, y0: cliff.before, y1: cliff.after, title: `${times} at day ${cliff.day}`, body: `${usd(cliff.before)} to ${usd(cliff.after)} per 1,000 units a month` },
    title: `Day ${cliff.day}: the aged-stock charge jumps ${times}`,
    subtitle: "Amazon's aged-inventory surcharge for this listing, per 1,000 units a month, by days in storage",
    source: source || "Amazon US FBA aged-inventory surcharge · Modeled from public data · Not a client · Not a result",
    label: `Amazon's aged-inventory surcharge by days in storage, jumping ${times} at day ${cliff.day}`,
    ask: "Your oldest stock", say: ageWords,
    next: { word: "Next band", delta: usd, at: (edge) => `at day ${edge + 1}` },
  };
}

/** Rung 10, for age: what it pays now, and what the coming days bring; before the cliff, the cliff by name. */
export function ageWords(st, days) {
  const w = weighIn(st.treads, days), c = st.cliff;
  if (!w) return `Past the last band on this schedule.`;
  const now = w.fee > 0 ? `At ${Math.round(days)} days it pays ${usd(w.fee)} per 1,000 units a month.` : `At ${Math.round(days)} days it pays no aged-stock charge yet.`;
  if (days < c.day) {
    const to = c.day - Math.round(days);
    const next = w.above && w.above.edge + 1 < c.day ? ` The next band starts in ${w.above.edge + 1 - Math.round(days)} days.` : "";
    const then = w.fee > 0 ? `: ${(c.after / w.fee).toFixed(1)}× what it pays now` : "";
    return `${now}${next} In ${to} day${to === 1 ? "" : "s"} it crosses day ${c.day}, and the charge becomes ${usd(c.after)}${then}.`;
  }
  return w.above ? `${now} It has crossed day ${c.day}. The next band starts in ${w.above.edge + 1 - Math.round(days)} days, at ${usd(w.above.fee)}.` : `${now} It is in the last band.`;
}

/** The chart, the control and the player are the staircase's own, given this schedule. */
export const agingSpec = stairsSpec;
export const ageHTML = weighInHTML;
export const playAging = playStairs;
