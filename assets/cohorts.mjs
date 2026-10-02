// The Operator's Math, lessons 3 and 4, on the reader's own store: how many times a new
// customer comes back, month by month, and the month they have paid back what they cost.
// Counting, not a model: for each month k, the customers whose first order is at least k
// months before the export's last day, and their repeat orders within k months of it.
// Orders are read the way the engine reads them (ingest/shopify_orders.py): one order per
// name, cancelled, voided and pending dropped, revenue after line discounts and the refund.
// A customer is the lower-cased email, held in this browser only and never sent anywhere.
// scripts/learn/operators_math.py customer_curve is the reference this is held to
// (scripts/learn/operators-math.golden.json). Pure functions: no page, no network.

export const DROP_STATUSES = new Set(["voided", "pending"]);
export const DAYS_A_MONTH = 365.25 / 12;
export const MONTHS = 12;
const ORDER_FIELDS = ["financial_status", "created_at", "cancelled_at", "refunded_amount", "email"];

const dayNumber = (iso) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 864e5;
const cents = (v) => Math.round(v * 100) / 100;

/** Rows mapped from Shopify's Orders export (lib/call.js SHOPIFY_ORDERS plus an email column)
 *  → one order each: {email, name, created, cancelled, status, revenue}. `isoDate` is lib/call.js's. */
export function ordersFromRows(rows, isoDate) {
  const byName = new Map();
  for (const r of rows) {
    if (!r.name) continue;
    const o = byName.get(r.name) || { financial_status: null, created_at: null, cancelled_at: null, refunded_amount: null, email: null, lines: [] };
    for (const k of ORDER_FIELDS) if (o[k] == null && r[k] != null) o[k] = r[k];
    o.lines.push(r);
    byName.set(r.name, o);
  }
  const out = [];
  for (const [name, o] of byName) {
    let revenue = 0, lines = 0;
    for (const l of o.lines) {
      const qty = l.quantity || 0;
      if (qty <= 0 || !(l.sku || l.line_name)) continue;
      revenue += (l.price || 0) * qty - (l.discount || 0);
      lines++;
    }
    if (!lines) continue;
    const refund = Math.max(0, Math.min(o.refunded_amount || 0, revenue));
    out.push({ email: o.email || "", name, created: isoDate(o.created_at), cancelled: o.cancelled_at || "",
      status: o.financial_status || "", revenue: cents(revenue - refund) });
  }
  return out;
}

/** The cohort curve, as scripts/learn/operators_math.py customer_curve computes it. */
export function customerCurve(orders, months = MONTHS) {
  const by = new Map();
  let last = null;
  for (const o of orders) {
    if (o.cancelled || DROP_STATUSES.has(String(o.status || "").trim().toLowerCase()) || !o.created) continue;
    if (last == null || o.created > last) last = o.created;
    const email = String(o.email || "").trim().toLowerCase();
    if (!email) continue;
    if (!by.has(email)) by.set(email, []);
    by.get(email).push([o.created, Number(o.revenue)]);
  }
  if (!by.size) return { customers: 0 };
  const lastDay = dayNumber(last);
  const people = [...by.values()].map((v) => v.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] - b[1])))
    .map((v) => ({ first: dayNumber(v[0][0]), firstValue: v[0][1], repeats: v.slice(1).map(([d, r]) => [dayNumber(d), r]) }));
  const round6 = (v) => Math.round(v * 1e6) / 1e6;
  const curve = [];
  for (let k = 1; k <= months; k++) {
    const span = k * DAYS_A_MONTH;
    const eligible = people.filter((p) => lastDay - p.first >= span);
    if (!eligible.length) { curve.push({ month: k, customers: 0, repeats: null, repeat_revenue: null }); continue; }
    let reps = 0, revs = 0;
    for (const p of eligible) for (const [d, r] of p.repeats) if (d - p.first <= span) { reps += 1; revs += r; }
    curve.push({ month: k, customers: eligible.length, repeats: round6(reps / eligible.length), repeat_revenue: round6(revs / eligible.length) });
  }
  const repeatValues = people.flatMap((p) => p.repeats.map(([, r]) => r));
  const cameBack = people.filter((p) => p.repeats.length).length;
  return {
    customers: people.length,
    came_back: cameBack,
    came_back_share: round6(cameBack / people.length),
    first_value: round6(people.reduce((a, p) => a + p.firstValue, 0) / people.length),
    repeat_value: repeatValues.length ? round6(repeatValues.reduce((a, b) => a + b, 0) / repeatValues.length) : null,
    last,
    curve,
  };
}

/** The first month a new customer's margin back (margin rate × (first order + repeat revenue so far))
 *  covers what they cost; null when no month in the export's reach does. */
export function paybackMonth(cv, marginRate, cac) {
  for (const row of cv.curve || []) {
    if (row.repeat_revenue == null) return null;
    if (marginRate * (cv.first_value + row.repeat_revenue) >= cac) return row.month;
  }
  return null;
}
