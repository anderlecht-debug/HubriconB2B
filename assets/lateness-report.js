// /lateness: your own lateness report, built in your browser from rows you paste or a CSV you pick.
// Nothing leaves the page unless you press Send.
import { simulate, PROMISE } from "./lateness-sim.mjs";

const $ = id => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const esc = t => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function parseDate(t) {
  t = String(t || "").trim().replace(/^"|"$/g, "");
  let m;
  if ((m = t.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/))) return Date.UTC(+m[1], m[2] - 1, +m[3]);
  if ((m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/))) { const y = +m[3] < 100 ? 2000 + +m[3] : +m[3]; return Date.UTC(y, m[1] - 1, +m[2]); }  // US month/day
  const d = Date.parse(t); return isNaN(d) ? null : d;
}

export function parse(text) {
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  if (!lines.length) return { rows: [], skipped: 0 };
  const split = l => l.split(/\t|;|,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(c => c.trim().replace(/^"|"$/g, ""));
  let cols = { sup: 0, order: 1, promised: 2, actual: 3 };
  const head = split(lines[0]).map(h => h.toLowerCase());
  if (head.every(h => parseDate(h) === null)) {
    const taken = new Set();   // keywords in priority order; a column is used once
    const find = (...ks) => { for (const k of ks) { const i = head.findIndex((h, j) => !taken.has(j) && h.includes(k)); if (i >= 0) { taken.add(i); return i; } } return -1; };
    const c = { sup: find("supplier", "factory", "vendor", "manufacturer"), promised: find("promis", "expected", "eta", "due"), actual: find("actual", "completed", "done", "ready"), order: find("order", "po", "placed") };
    if (c.order >= 0 && c.promised >= 0 && c.actual >= 0) cols = { ...c, sup: c.sup >= 0 ? c.sup : -1 };
    lines.shift();
  }
  const rows = []; let skipped = 0;
  for (const l of lines) {
    const c = split(l);
    const o = parseDate(c[cols.order]), p = parseDate(c[cols.promised]), a = parseDate(c[cols.actual]);
    if (o === null || p === null || a === null || p < o) { skipped++; continue; }
    rows.push({ sup: (cols.sup >= 0 && c[cols.sup]) || "Your supplier", order: o, promised: p, actual: a, late: Math.round((a - p) / 864e5) });
  }
  return { rows, skipped };
}

function sample() {   // two suppliers from Hubricon's simulation: a busy one and a quiet one
  const out = ["supplier,order_date,promised_ready_date,actual_ready_date"];
  const iso = d => new Date(Date.UTC(2025, 0, 1) + Math.round(d) * 864e5).toISOString().slice(0, 10);
  for (const [name, load, seed, every] of [["Sample supplier A (busy)", 0.9, 133, 23], ["Sample supplier B (quiet)", 0.6, 55, 29]]) {
    const l = simulate(load, seed);
    let next = 4;
    for (let i = 0; i < l.length; i++) { const d = l.when[i]; if (d < next || d >= 365) continue; next = d + every;
      out.push(`${name},${iso(d)},${iso(d + PROMISE)},${iso(d + PROMISE + l[i])}`); }
  }
  return out.join("\n");
}

function strip(rows) {     // one dot per order, by days early or late
  const W = 220, H = 44, lo = -10, hi = 40, x = v => 6 + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (W - 12);
  const stack = new Map();
  const dots = rows.map(r => { const k = Math.round(r.late / 2); const n = stack.get(k) || 0; stack.set(k, n + 1);
    return `<circle cx="${x(r.late).toFixed(1)}" cy="${(H - 5 - n * 6.5).toFixed(1)}" r="3" class="${r.late > 0 ? "late" : "ok"}"/>`; }).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="mini" aria-hidden="true"><line x1="${x(0)}" x2="${x(0)}" y1="0" y2="${H}" class="prom"/>${dots}</svg>`;
}

function months(rows) {    // average days late by the month the order was placed
  const s = Array(12).fill(0), n = Array(12).fill(0);
  rows.forEach(r => { const m = new Date(r.order).getUTCMonth(); s[m] += Math.max(0, r.late); n[m]++; });
  return `<div class="months" aria-hidden="true">${MONTHS.map((m, i) => { const v = n[i] ? s[i] / n[i] : null;
    const a = v === null ? 0 : Math.min(1, v / 15);
    return `<span title="${m}: ${v === null ? "no orders" : `${v.toFixed(1)} days late on average`}" style="--a:${a.toFixed(2)}" class="${v === null ? "none" : a > 0.45 ? "hot" : ""}">${m[0]}</span>`; }).join("")}</div>`;
}

function render({ rows, skipped }) {
  const out = $("mine-out");
  if (!rows.length) { out.innerHTML = `<p class="mine-empty">No rows I could read yet. Each row needs an order date, a promised ready date and an actual ready date${skipped ? ` (${skipped} skipped)` : ""}.</p>`; $("mine-send").hidden = true; return; }
  const by = new Map(); rows.forEach(r => { if (!by.has(r.sup)) by.set(r.sup, []); by.get(r.sup).push(r); });
  const pct = a => Math.round(a.filter(r => r.late <= 0).length / a.length * 100);
  const avgLate = a => { const l = a.filter(r => r.late > 0); return l.length ? l.reduce((t, r) => t + r.late, 0) / l.length : 0; };
  const worst = a => Math.max(...a.map(r => r.late));
  const d = v => `${Math.round(v)} day${Math.round(v) === 1 ? "" : "s"}`;
  out.innerHTML = `
    <dl class="mine-big">
      <div><dt>${rows.length}</dt><dd>orders read${skipped ? `, ${skipped} skipped` : ""}</dd></div>
      <div><dt>${pct(rows)}%</dt><dd>ready by the promised date</dd></div>
      <div class="leak"><dt>${d(avgLate(rows))}</dt><dd>late, on average, when an order was late</dd></div>
      <div class="leak"><dt>${d(Math.max(0, worst(rows)))}</dt><dd>the latest any order ran</dd></div>
    </dl>
    <div class="mine-table" role="table">
      <div class="mt-row mt-head" role="row"><span>Supplier</span><span>Orders</span><span>On time</span><span>Days late, every order</span><span>When it slips</span></div>
      ${[...by].map(([s, a]) => `<div class="mt-row" role="row"><span class="sup">${esc(s)}</span><span>${a.length}</span><span>${pct(a)}%</span><span>${strip(a)}</span><span>${months(a)}</span></div>`).join("")}
    </div>`;
  const csv = ["supplier,order_date,promised_ready_date,actual_ready_date", ...rows.map(r => [r.sup, r.order, r.promised, r.actual].map((v, i) => i ? new Date(v).toISOString().slice(0, 10) : `"${v}"`).join(","))].join("\n");
  const body = `Here are my order dates for a lateness report.\n\n${csv.length > 1500 ? csv.slice(0, 1500) + "\n(and more, attached)" : csv}\n`;
  $("mine-send").href = `mailto:hagen.simmons@hubricon.com?subject=${encodeURIComponent("Lateness report: my order dates")}&body=${encodeURIComponent(body)}`;
  $("mine-send").hidden = false;
}

const run = () => render(parse($("mine-text").value));
$("mine-text").addEventListener("input", run);
$("mine-file").addEventListener("change", e => { const f = e.target.files[0]; if (!f) return; f.text().then(t => { $("mine-text").value = t; run(); }); });
$("mine-sample").addEventListener("click", () => { $("mine-text").value = sample(); run(); });
