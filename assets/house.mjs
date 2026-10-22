/* ============================================================================
   The house charts: every other chart on the site, as specs for the line and
   the bars, built from the same data the site's charts are built from now
   (scripts/build-pages.mjs). One drawing system: what the Monte Carlo, the
   staircase and the aging cliff do, every chart does: honest shapes, labels on
   the lines, story order, a reading under the finger, a card for a deck.

   Words are worked out from the data, never typed. No calendar labels an
   axis (HUBRICON_SPEC.md, "No time scales on a chart"): a path through days,
   weeks or months keeps its order and loses its dates; a delay ("days late")
   is a quantity, like weight, and keeps its numbers.

   Each builder takes the chart's data and { w, font, paint, id } and returns
   a spec: draw it with lineChart (line.mjs) or barChart (bars.mjs), as `kind`
   says.
   ============================================================================ */

const usd0 = (v) => `${v < 0 ? "−" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
const usd2 = (v) => `${v < 0 ? "−" : ""}$${Math.abs(v).toFixed(2)}`;
const k = (v) => (v === 0 ? "$0" : Math.abs(v) >= 1000 ? `${v < 0 ? "−" : ""}$${+(Math.abs(v) / 1000).toFixed(1)}k` : usd0(v));
const count = (v) => Math.round(v).toLocaleString("en-US");
const range = (n, f) => Array.from({ length: n }, (_, i) => f(i));
const base = (o, id) => ({ w: o.w || 760, h: o.h || 420, font: o.font || 13, paint: o.paint || "css", ground: o.ground, id: o.id || id, source: o.source });

/** The fit: each period's price against units a day, and the demand curve drawn through them. */
export function fitSpec(fit, o = {}) {
  const prices = fit.points.map((p) => p.price), lo = Math.min(...prices) - 0.6, hi = Math.max(...prices) + 0.6;
  const curve = range(41, (i) => { const p = lo + ((hi - lo) * i) / 40; return [p, Math.exp(fit.intercept) * p ** fit.elasticity]; });
  return { kind: "line", ...base(o, "fit"), subtitle: "Units a day, by price",
    label: `Each period's price against units sold a day, with the demand curve fitted through them: elasticity ${fit.elasticity.toFixed(2)}`,
    x: { domain: [lo, hi], ticks: niceDollars(lo, hi), format: (v) => `$${v}`, read: usd2 },
    y: { format: (v) => `${v}`, read: (v) => `${v.toFixed(1)} units a day` },
    series: [
      { id: "periods", points: fit.points.map((p) => [p.price, p.perDay]), kind: "points", role: "context", short: "A period" },
      { id: "curve", points: curve, kind: "monotone", role: "focus", short: "The fit" },
    ],
    notes: [{ x: curve[30][0], y: curve[30][1], title: `Elasticity ${minus(fit.elasticity)}`, body: `interval ${minus(fit.lo)} to ${minus(fit.hi)}`, tone: "ink" }],
    fall: false };
}

/** Profit a month by price: at the fitted elasticity and at both ends of its interval, through today's price. */
export function profitSpec(pc, o = {}) {
  const prof = (e, p) => pc.q0 * (p / pc.p0) ** e * (p * (1 - pc.fee) - pc.cost - pc.fixed);
  const [lo, hi] = pc.range, xs = range(65, (i) => lo + ((hi - lo) * i) / 64);
  const line = (e) => xs.map((p) => [p, prof(e, p)]);
  return { kind: "line", ...base(o, "profit"), subtitle: "Profit a month, by price",
    label: `Profit a month against price at the fitted elasticity ${pc.eps.toFixed(2)} and both ends of its interval; the best price ${usd2(pc.best)}`,
    x: { domain: [lo, hi], ticks: niceDollars(lo, hi), format: (v) => `$${v}`, read: usd2 },
    y: { format: k, read: (v) => `${usd0(v)} a month` },
    series: [
      { id: "lo", points: line(pc.hi), kind: "monotone", role: "context", name: minus(pc.hi), short: minus(pc.hi) },
      { id: "eps", points: line(pc.eps), kind: "monotone", role: "focus", name: `${minus(pc.eps)}, the estimate`, short: "The estimate" },
      { id: "hi", points: line(pc.lo), kind: "monotone", role: "context", name: minus(pc.lo), short: minus(pc.lo) },
    ],
    dots: [
      { x: pc.p0, y: prof(pc.eps, pc.p0), hollow: true, label: `Today ${usd2(pc.p0)}` },
      { x: pc.step, y: prof(pc.eps, pc.step), hollow: true, label: `Next ${usd2(pc.step)}` },
      { x: pc.best, y: prof(pc.eps, pc.best), label: `Best ${usd2(pc.best)}`, emphasis: true },
    ],
    fall: false };
}

/** The cash path: the median balance in steps from today's, the wire and the low point; with band, the 5th–95th spread. */
export function cashSpec(c, o = {}) {
  const pts = (arr) => arr.map((v, i) => [i, v]);
  const spec = { kind: "line", ...base(o, o.band ? "cone" : "cash"), subtitle: o.band ? "Cash in the bank, the typical path and the spread of 9 in 10" : "Cash in the bank, the typical path",
    label: `The typical cash balance from ${usd0(c.start)}: the wire of ${usd0(c.wire)} and a low point of ${usd0(c.trough_median)}`,
    x: { domain: [0, c.p50.length - 1] }, y: { format: k, read: usd0 },
    series: [{ id: "p50", points: pts(c.p50), kind: "step", role: "focus", short: "Typical" }],
    dots: [
      { x: c.wire_day, y: c.p50[c.wire_day], hollow: true, label: `The wire ${usd0(c.wire)}` },
      { x: c.trough_day, y: c.p50[c.trough_day], label: `Low point ${usd0(c.trough_median)}`, emphasis: true },
    ],
    fall: false };
  if (o.band) {
    spec.areas = [{ lo: pts(c.p5), hi: pts(c.p95), kind: "step" }];
    spec.series.unshift({ id: "p5", points: pts(c.p5), kind: "step", role: "context", short: "1 in 20 lower" });
    spec.dots.push({ x: c.trough_day, y: c.p5[c.trough_day], hollow: true, label: `${usd0(c.trough_p5)} in 1 of 20` });
  }
  return spec;
}

/** The chance of running out before the order lands, by how many days late it is. */
export function lateSpec(l, o = {}) {
  const pct = (v) => `${Math.round(v * 100)}%`;
  const max = l.curve[l.curve.length - 1].days_late;
  return { kind: "line", ...base(o, "late"), subtitle: "Chance of running out before the order lands, by days late",
    label: `The chance of running out: ${pct(l.on_time.p_out)} on time, ${pct(l.two_weeks.p_out)} two weeks late`,
    x: { domain: [0, max], ticks: range(Math.floor(max / 7) + 1, (i) => i * 7), format: (v, last) => (last ? `${v} days late` : `${v}`), read: (v) => (v === 0 ? "On time" : `${v} days late`) },
    y: { domain: [0, Math.max(...l.curve.map((p) => p.p_out)) * 1.15], format: pct, read: (v) => `${(v * 100).toFixed(1)}% chance` },
    series: [{ id: "p", points: l.curve.map((p) => [p.days_late, p.p_out]), kind: "monotone", role: "focus", short: "" }],
    dots: [
      { x: 0, y: l.on_time.p_out, hollow: true, label: `${pct(l.on_time.p_out)} on time` },
      { x: l.two_weeks.days_late, y: l.two_weeks.p_out, label: `${pct(l.two_weeks.p_out)}, two weeks late`, emphasis: true },
    ],
    fall: false };
}

/** USPS rates by weight, the farthest zone and the nearest: anything over a pound bills at the next pound. */
export function parcelSpec(pc, o = {}) {
  const zone = (z) => [[0, pc.rows["0"][z]], [16, pc.rows["32"][z]], [32, pc.rows["48"][z]], [48, pc.rows["48"][z]]];
  const far = zone(7), near = zone(0);
  return { kind: "line", ...base(o, "parcel"), subtitle: "A USPS Ground Advantage label, by weight",
    label: `USPS Ground Advantage rates by weight: crossing a pound adds ${usd2(pc.step[0])} to ${usd2(pc.step[1])} a parcel, by zone`,
    x: { domain: [0, 48], ticks: [0, 16, 32, 48], format: (v, last) => (last ? `${v} oz` : `${v}`), read: (v) => `${v.toFixed(1)} oz`, snap: 0.1 },
    y: { format: usd2, read: (v) => `${usd2(v)} a label` },
    series: [
      { id: "near", points: near, kind: "step", role: "context", name: "The nearest zone (1)", short: "Nearest" },
      { id: "far", points: far, kind: "step", role: "focus", name: "The farthest zone (8)", short: "Farthest", tip: usd2 },
    ],
    risers: [{ x: 16, y0: pc.rows["0"][7], y1: pc.rows["32"][7] }],
    dots: [{ x: pc.parcel_oz, y: pc.rows["32"][7], label: `${pc.parcel_oz} oz · an invented parcel`, emphasis: true }],
    notes: [{ x: 16, y: (pc.rows["0"][7] + pc.rows["32"][7]) / 2, title: `+${usd2(pc.step[0])} to ${usd2(pc.step[1])}`, body: "a parcel, by zone" }],
    fall: false };
}

/** One order's price, split by who takes it, at the nearest zone and the farthest. */
export function orderSpec(od, o = {}) {
  const rows = od.zones.map((z, i) => {
    const parts = [["Shopify Payments", od.fee], ["The label", od.labels[i]], ["Packing", od.packing], ["Landed cost", od.landed]];
    const kept = od.price - parts.reduce((a, [, v]) => a + v, 0);
    return { name: `Zone ${z}`, parts: [...parts.map(([name, value]) => ({ name, value })), { name: "Kept before ads", value: kept, money: true }] };
  });
  const kept = rows.map((r) => r.parts[r.parts.length - 1].value);
  return { kind: "bars", type: "stack", ...base(o, "order"), subtitle: `One order at ${usd2(od.price)}, split by who takes it`,
    label: `An order at ${usd2(od.price)}: kept before ads ${usd2(kept[0])} at the nearest zone, ${usd2(kept[kept.length - 1])} at the farthest`,
    format: usd2, rows,
    note: { title: `The label alone moves ${usd2(kept[0] - kept[kept.length - 1])} of it`, body: "between the nearest zone and the farthest" } };
}

/** One order's money top to bottom: the price, each cost where it falls, what is kept before and after ads. */
export function waterfallSpec(wf, o = {}) {
  const before = wf.price - wf.costs.reduce((a, [, v]) => a + v, 0), after = before - wf.ads;
  return { kind: "bars", type: "waterfall", ...base(o, "wf"), subtitle: "One order, from its price to what it keeps",
    label: `An order at ${usd2(wf.price)} keeps ${usd2(before)} before ads and ${usd2(after)} after`,
    format: usd2,
    rows: [{ name: "Price", value: wf.price, total: true }, ...wf.costs.map(([name, v]) => ({ name, value: -v })),
      { name: "Kept before ads", value: before, total: true, money: true }, { name: "Ads per order", value: -wf.ads }, { name: "Kept after ads", value: after, total: true, money: true }] };
}

/** One campaign's days, the curve fitted through them, the average return and the last dollar's, and where it stops paying. */
export function responseSpec(rs, o = {}) {
  const f = rs.model === "hill" ? (s) => (rs.params.a * s ** rs.params.h) / (rs.params.k ** rs.params.h + s ** rs.params.h)
    : rs.model === "linear" ? (s) => rs.params.roas * s : (s) => rs.params.a * Math.log1p(rs.params.b * s);
  const xMax = Math.max(rs.max_seen, ...rs.points.map((p) => p[0])) * 1.1, s0 = rs.spend, v0 = f(s0);
  const curve = range(61, (i) => { const s = (xMax * i) / 60; return [s, f(s)]; });
  const slope = rs.marginal, ex = Math.min(xMax, s0 + xMax * 0.16);
  return { kind: "line", ...base(o, "resp"), subtitle: "Sales a day the platform credits, by ad spend a day",
    label: `Ad spend against credited sales: today ${usd0(s0)} a day, the average return ${rs.average.toFixed(2)}, the last dollar's ${rs.marginal.toFixed(2)}`,
    x: { domain: [0, xMax], ticks: niceDollars(0, xMax), format: k, read: (v) => `${usd0(v)} a day` },
    y: { format: k, read: (v) => `${usd0(v)} a day` },
    series: [
      { id: "days", points: rs.points.map(([s, v]) => [s, v]), kind: "points", role: "context", r: 2.4, short: "A day" },
      { id: "average", points: [[0, 0], [s0, v0]], kind: "linear", role: "ghost", name: `Average ${rs.average.toFixed(2)}`, short: "Average" },
      { id: "fit", points: curve, kind: "monotone", role: "focus", short: "The fit" },
      { id: "last", points: [[s0 - xMax * 0.16, v0 - slope * xMax * 0.16], [ex, v0 + slope * (ex - s0)]], kind: "linear", role: "context", name: `Last dollar ${rs.marginal.toFixed(2)}`, short: "Last dollar" },
    ],
    dots: [
      { x: s0, y: v0, label: `Today ${usd0(s0)} a day`, emphasis: true },
      { x: rs.breakeven, y: f(rs.breakeven), hollow: true, label: `Break-even, first order: ${usd0(rs.breakeven)}` },
    ],
    fall: false };
}

/** A new customer's margin back, in order, against what that customer cost; where it pays back. */
export function paybackSpec(pb, o = {}) {
  const n = pb.weekly.length, back = pb.weekly.findIndex((v) => v >= pb.cac);
  return { kind: "line", ...base(o, "payback"), subtitle: "Margin back from one new customer, as it adds up",
    label: `Margin back from one new customer against the ${usd2(pb.cac)} it cost to win them${back >= 0 ? ", paid back within the first year" : ""}`,
    x: { domain: [0, n - 1] }, y: { format: k, read: usd2 },
    series: [
      { id: "cac", points: [[0, pb.cac], [n - 1, pb.cac]], kind: "linear", role: "context", name: `What they cost ${usd2(pb.cac)}`, short: "Cost" },
      { id: "back", points: pb.weekly.map((v, i) => [i, v]), kind: "monotone", role: "focus", short: "Margin back", tip: usd2 },
    ],
    dots: [{ x: 0, y: pb.weekly[0], hollow: true, label: "First order" }, ...(back >= 0 ? [{ x: back, y: pb.weekly[back], label: "Paid back", emphasis: true }] : [])],
    fall: false };
}

/** Repeat orders after the cut: the engine's call, made with nothing after it, and what the store measured. */
export function callsSpec(c, o = {}) {
  const p = c.path, last = p.weeks.length - 1, diff = ((c.ratio - 1) * 100).toFixed(1);
  return { kind: "line", ...base(o, "calls"), subtitle: "Repeat orders after the cut, as they add up",
    label: "What the engine called before, and what the store's own orders measured after",
    x: { domain: [0, p.weeks[last]] }, y: { format: (v) => (v === 0 ? "0" : `${v / 1000}k`), read: count },
    series: [
      { id: "called", points: p.weeks.map((x, i) => [x, p.called[i]]), kind: "monotone", role: "ghost", name: `Called ${count(c.called)}`, short: "Called" },
      { id: "measured", points: p.weeks.map((x, i) => [x, p.measured[i]]), kind: "monotone", role: "focus", name: `Measured ${count(c.measured)}`, short: "Measured", tip: count },
    ],
    compare: (m, cl) => `${Math.abs((m / cl - 1) * 100).toFixed(1)}% ${m >= cl ? "above" : "below"} the call`,
    notes: [{ x: p.weeks[last], y: p.measured[last], title: `Within ${diff}%`, body: "of the number called in advance", tone: "ink" }],
    fall: false };
}

/** The regulars the engine named as slipping, against the rest: how many of each never ordered again. */
export function slippingSpec(s, o = {}) {
  const share = (lost, all) => (lost / all) * 100;
  const a = share(s.named_did_not, s.named), b = share(s.steady - s.steady_came_back, s.steady);
  const row = (name, lost) => ({ name, parts: [{ name: "Never came back", value: lost, money: true }, { name: "Came back", value: 100 - lost }] });
  return { kind: "bars", type: "stack", ...base(o, "slip"), subtitle: "Regulars at the cut-off, by whether they ordered again",
    label: `${Math.round(a)}% of the regulars the engine named never came back, against ${Math.round(b)}% of the rest`,
    format: (v) => `${Math.round(v)}%`,
    rows: [row(`Named at the cut-off (${count(s.named)})`, a), row(`Not named (${count(s.steady)})`, b)],
    note: { title: `${(a / b).toFixed(1)}× as likely never to come back`, body: `The ones who never came back had spent ${usd0(s.lost_spend_year_before)} the year before` } };
}

/** The best sellers' units in order, and the three months the engine called a month ahead: the call against what sold. */
export function demandSpec(d, o = {}) {
  const idx = Object.fromEntries(d.history.map((h, i) => [h.month, i]));
  const calls = d.calls.filter((c) => c.month in idx);
  const err = d.quarter.error;
  return { kind: "line", ...base(o, "demand"), subtitle: `Units sold a month, its ${d.top_n} best sellers, in order`,
    label: `Units sold by the ${d.top_n} best sellers, and three months called a month ahead`,
    x: { domain: [0, d.history.length - 1] }, y: { format: (v) => (v === 0 ? "0" : `${v / 1000}k`), read: count },
    series: [
      { id: "sold", points: d.history.map((h, i) => [i, h.units]), kind: "monotone", role: "focus", name: "What sold", short: "Sold", tip: count },
      { id: "called", points: calls.map((c) => [idx[c.month], c.called]), kind: "points", role: "focus", hollow: true, name: "Called a month ahead", short: "Called" },
    ],
    notes: [{ x: idx[calls[calls.length - 1].month], y: calls[calls.length - 1].called, title: `Called within ${Math.abs(err * 100).toFixed(1)}% in total`, body: "three calls, each a month ahead", tone: "ink" }],
    fall: false };
}

// ---------------------------------------------------------------- helpers

const minus = (v) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}`;
function niceDollars(lo, hi) {
  const span = hi - lo, step = [1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500].find((s) => span / s <= 5) || 1000;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(2));
  return out;
}
