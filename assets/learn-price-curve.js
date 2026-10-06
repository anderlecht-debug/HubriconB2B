// The Price Curve, on the reader's own numbers. Lesson 2 takes a history and a few costs;
// lessons 3 to 7 then read them back the way the lesson just taught, and lesson 7 prints a
// one-page pricing memo. The arithmetic is assets/price-curve.mjs, which is the engine's
// (scripts/learn/price-curve-tool.test.mjs). Everything stays in this browser: the numbers are
// kept in its own storage and nothing is sent anywhere.
"use strict";
import * as pc from "/assets/price-curve.mjs";
import { fitSVG, profitSVG } from "/assets/charts.mjs";

const KEY = "hubricon.learn.price-curve";
const ROWS = 12, MAX_ROWS = 26;
const $ = (s, el = document) => el.querySelector(s);
const tool = document.getElementById("yours");

function num(v) {
  if (v == null) return null;
  const s = String(v).replace(/[$,\s]/g, "").replace(/%$/, "");
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}
const money = (v) => `$${v.toFixed(2)}`;
const dollars = (v) => `${v < 0 ? "−" : "+"}$${Math.abs(Math.round(v)).toLocaleString("en-US")}`;
const pct = (v, d = 1) => `${(Math.abs(v) * 100).toFixed(d)}%`;
const signedPct = (v, d = 1) => `${v < 0 ? "−" : "+"}${pct(v, d)}`;
const e2 = (v) => (v < 0 ? `−${Math.abs(v).toFixed(2)}` : v.toFixed(2));
const today = () => new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const inDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }); };

const store = {
  read() { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} },
  clear() { try { localStorage.removeItem(KEY); } catch (e) {} },
};

function init() {
  tool.hidden = false;
  const body = $("tbody", tool);
  const addRow = (r = {}) => {
    const i = body.rows.length + 1;
    const tr = document.createElement("tr");
    tr.innerHTML = `<th scope="row">${i}</th>` +
      `<td><input inputmode="numeric" aria-label="Period ${i}: days" data-k="days" value="${r.days ?? ""}"></td>` +
      `<td><input inputmode="numeric" aria-label="Period ${i}: units sold" data-k="units" value="${r.units ?? ""}"></td>` +
      `<td><input inputmode="decimal" aria-label="Period ${i}: average price" data-k="price" value="${r.price ?? ""}"></td>`;
    body.append(tr);
  };
  const saved = store.read();
  const rows = saved?.rows?.length ? saved.rows : Array.from({ length: ROWS }, () => ({}));
  rows.forEach(addRow);
  for (const [k, v] of Object.entries(saved?.econ || {})) { const el = tool.querySelector(`[name="${k}"]`); if (el) el.value = v; }

  $("#yours-add", tool).addEventListener("click", () => { if (body.rows.length < MAX_ROWS) { addRow(); update(); } });
  $("#yours-example", tool).addEventListener("click", () => {
    const ex = JSON.parse(document.getElementById("pc-example").textContent);
    body.replaceChildren();
    ex.history.forEach((h) => addRow({ days: h.days, units: h.units, price: h.price }));
    const e = ex.economics;
    Object.entries({ sku: "The example (an invented listing)", price: e.price, units: e.units_month, cost: e.landed_cost,
      referral: e.referral * 100, fba: e.fba_fee, other: e.other_fixed || "", discount: ex.discount * 100 })
      .forEach(([k, v]) => { const el = tool.querySelector(`[name="${k}"]`); if (el) el.value = v; });
    update();
  });
  $("#yours-clear", tool).addEventListener("click", () => {
    store.clear();
    body.replaceChildren();
    for (let i = 0; i < ROWS; i++) addRow();
    tool.querySelectorAll("[name]").forEach((el) => { el.value = el.name === "referral" ? "15" : el.name === "discount" ? "20" : ""; });
    update();
  });
  tool.addEventListener("input", update);
  update();
}

function collect() {
  const rows = [...$("tbody", tool).rows].map((tr) => Object.fromEntries([...tr.querySelectorAll("input")].map((i) => [i.dataset.k, i.value.trim()])));
  const econ = Object.fromEntries([...tool.querySelectorAll("[name]")].map((el) => [el.name, el.value.trim()]));
  return { rows, econ };
}

function update() {
  const { rows, econ } = collect();
  store.write({ rows, econ });
  const points = rows.map((r, i) => ({ row: i + 1, days: num(r.days), units: num(r.units), price: num(r.price) }))
    .filter((p) => p.units != null || p.price != null);
  const e = {
    price: num(econ.price), units: num(econ.units), cost: num(econ.cost), referral: (num(econ.referral) ?? 15) / 100,
    fixed: (num(econ.fba) ?? 0) + (num(econ.other) ?? 0), discount: (num(econ.discount) ?? 20) / 100,
  };
  const r = pc.read(points, e);
  const name = econ.sku || "Your SKU";
  paint(r, e, name, points);
}

const out = (k) => document.querySelector(`[data-yours="${k}"]`);
function show(k, html) { const el = out(k); if (!el) return; el.innerHTML = html; el.hidden = !html; }

function paint(r, e, name, points) {
  const f = r.fit;
  const status = $("#yours-status", tool);
  const any = points.length > 0;
  if (!any) {
    status.textContent = "Type a history above, or fill in the example, and each lesson from here reads it back.";
    ["fit", "best", "raise", "discount", "next", "memo"].forEach((k) => show(k, ""));
    document.body.classList.remove("has-memo");
    return;
  }
  if (f.status === "insufficient_data") {
    document.body.classList.remove("has-memo");
    status.textContent = `${f.n} of ${pc.MIN_PERIODS} periods with both units and a price. The fit needs at least ${pc.MIN_PERIODS}.`;
    ["fit", "best", "raise", "discount", "next", "memo"].forEach((k) => show(k, ""));
    return;
  }
  if (f.status === "insufficient_price_variation") {
    document.body.classList.remove("has-memo");
    status.textContent = `The price has varied ${pct(f.priceCv)}; the fit needs at least ${pct(pc.MIN_PRICE_CV, 0)}. A price that never moved cannot say what another would do: lesson 7 is how to move it on purpose.`;
    ["fit", "best", "raise", "discount", "next", "memo"].forEach((k) => show(k, ""));
    return;
  }
  const typical = Math.sqrt(f.residuals.reduce((a, v) => a + v * v, 0) / Math.max(1, f.dof));
  const odd = f.residuals.map((v, i) => [i, v]).filter(([, v]) => Math.abs(v) > 2.5 * typical);
  status.textContent = `Read: elasticity ${e2(f.elasticity)}, 95% interval ${e2(f.ci[0])} to ${e2(f.ci[1])}, on ${f.n} periods.`;

  const points2 = f.used.map((p) => ({ price: p.price, perDay: p.units / (p.days || 1) }));
  const fitChart = fitSVG({ points: points2, intercept: f.intercept, elasticity: f.elasticity, lo: f.ci[0], hi: f.ci[1] },
    { id: "yf", w: 680, h: 340, m: { t: 40, r: 16, b: 46, l: 56 }, font: 13 });
  const oddLine = odd.length ? `<p class="yours-warn">${odd.length === 1 ? "One period sits" : `${odd.length} periods sit`} far off the curve (${odd.map(([i]) => `period ${f.used[i].row}`).join(", ")}). A stockout, an event deal or a listing change? If so, leave ${odd.length === 1 ? "it" : "them"} out: lesson 2.</p>` : "";
  show("fit", `<p class="yours-k">On your numbers · ${esc(name)}</p>
    <p>Elasticity <b>${e2(f.elasticity)}</b>, standard error ${f.stdErr.toFixed(2)}, 95% interval <b>${e2(f.ci[0])} to ${e2(f.ci[1])}</b>, on ${f.n} periods. The line explains ${f.rSquared.toFixed(2)} of the variation.</p>
    <p>${r.guard ? `<b>Too close to −1 to name a price.</b> ${r.way === "up" ? "The estimate puts the best price above today's, so the direction is up; lesson 7 is how to learn the distance." : r.way === "hold" ? "The estimate puts the best price below today's while the range reaches −1, so the data cannot say which way: hold." : "Add your price and costs below to see which way the estimate points."}` : "<b>Clear of −1:</b> the interval can name a best price."}</p>
    ${oddLine}<div class="yours-chart">${fitChart}</div>`);

  if (r.best === undefined) { ["best", "raise", "discount", "next", "memo"].forEach((k) => show(k, `<p class="yours-k">On your numbers</p><p>Add today's price, units a month, landed cost and fees above to read this lesson on your SKU.</p>`)); return; }

  const curve = { p0: e.price, q0: e.units, cost: e.cost, fee: e.referral, fixed: e.fixed, eps: f.elasticity, lo: f.ci[0], hi: f.ci[1],
    best: r.best, step: r.next, range: [e.price * 0.76, e.price * 1.4] };
  const profitChart = profitSVG(curve, { id: "yp", w: 680, h: 360, m: { t: 40, r: 132, b: 46, l: 64 }, font: 13 });
  const why = r.best != null ? "" : r.guard ? (r.way === "up" ? "Too close to −1: the estimate points up, the distance unknown." : "Too close to −1, and the estimate points below today's price: hold, the data cannot say which way.") : f.elasticity >= -1 ? "Inelastic: profit rises with the price, so there is no peak to find. Walk up, and measure." : "No best price at these costs.";
  const edge = r.edge ? `<p class="yours-warn">The move crosses $10 or $50, where Amazon's fulfilment fee itself changes. Price both sides with The Fee Staircase before you take it.</p>` : "";
  show("best", `<p class="yours-k">On your numbers · ${esc(name)}</p>
    <p>${r.best != null ? `Best price <b class="money">${money(r.best)}</b>, ${signedPct(r.best / e.price - 1)} from today's ${money(e.price)}. At it, profit changes ${dollars(r.bestDelta)} a month on ${dollars(r.profitNow).replace("+", "")}.` : `<b>No best price.</b> ${why}`}</p>
    ${edge}<div class="yours-chart">${profitChart}</div>`);

  show("raise", `<p class="yours-k">On your numbers · ${esc(name)}</p>
    <p>You make ${money(r.margin)} a unit today. A 5% raise breaks even if units fall up to <b>${pct(-r.raise.breakEven)}</b>; your elasticity says they fall <b>${pct(-r.raise.implied)}</b>. ${r.raise.delta >= 0 ? `It makes <b class="money">${dollars(r.raise.delta)}</b> a month.` : `It costs <b>${dollars(r.raise.delta)}</b> a month.`}</p>`);

  const d = r.discount;
  show("discount", `<p class="yours-k">On your numbers · ${esc(name)}</p>
    <p>${d.needed == null ? `At ${pct(d.rate, 0)} off, every unit sold loses money.` : `A ${pct(d.rate, 0)} sale must sell <b>${pct(d.needed, 0)}</b> more units to break even; your elasticity says it sells <b>${pct(d.implied, 0)}</b> more. ${d.delta >= 0 ? `It pays: ${dollars(d.delta)} a month.` : `It costs <b>${dollars(d.delta)}</b> a month.`}`}</p>`);

  const way = { up: "up", down: "down", hold: "nowhere" }[r.way];
  show("next", `<p class="yours-k">On your numbers · ${esc(name)}</p>
    <p>Next price <b>${money(r.next)}</b> (${way === "nowhere" ? "hold" : `${way} ${pct(Math.abs(r.next / e.price - 1))}`}). Expected change: <b>${dollars(r.nextDelta)}</b> a month. Write it down today, ${today()}; measure it after ${inDays(14)}.</p>
    <p><button class="link-btn" type="button" id="memo-print-2">Print your pricing memo</button> <span class="yours-note">One page, from your numbers, to keep or to show someone.</span></p>`);
  document.getElementById("memo-print-2")?.addEventListener("click", () => window.print());

  const memoFit = fitSVG({ points: points2, intercept: f.intercept, elasticity: f.elasticity, lo: f.ci[0], hi: f.ci[1] },
    { id: "mf", w: 680, h: 340, m: { t: 40, r: 16, b: 46, l: 56 }, font: 13 });
  const memoProfit = profitSVG(curve, { id: "mp", w: 680, h: 360, m: { t: 40, r: 132, b: 46, l: 64 }, font: 13 });
  show("memo", memo(r, e, name, memoFit, memoProfit));
  document.body.classList.add("has-memo");
}

function memo(r, e, name, fitChart, profitChart) {
  const f = r.fit, d = r.discount;
  return `<header class="memo-head"><p class="memo-k">Pricing memo · ${today()}</p><h2>${esc(name)}</h2>
      <p>Prepared with The Price Curve, a free course from Hubricon (hubricon.com/learn/price-curve). The arithmetic is the one Hubricon's engine runs; these numbers never left the browser they were typed into.</p></header>
    <table class="memo-table"><tbody>
      <tr><th>Elasticity</th><td>${e2(f.elasticity)} (95% interval ${e2(f.ci[0])} to ${e2(f.ci[1])}, ${f.n} periods, R² ${f.rSquared.toFixed(2)})</td></tr>
      <tr><th>Today</th><td>${money(e.price)}, ${Math.round(e.units).toLocaleString("en-US")} units a month, ${money(r.margin)} a unit, ${dollars(r.profitNow).replace("+", "")} a month</td></tr>
      <tr><th>Best price</th><td>${r.best != null ? `${money(r.best)} (${dollars(r.bestDelta)} a month)` : (r.guard ? "None named: too close to −1. Direction: up." : "None: profit rises with the price. Direction: up.")}</td></tr>
      <tr><th>Next step</th><td>${money(r.next)}, expected ${dollars(r.nextDelta)} a month. Called ${today()}; measure after ${inDays(14)}.</td></tr>
      <tr><th>A 5% raise</th><td>Breaks even at ${pct(-r.raise.breakEven)} fewer units; the elasticity says ${pct(-r.raise.implied)} fewer: ${dollars(r.raise.delta)} a month.</td></tr>
      <tr><th>A ${pct(d.rate, 0)} discount</th><td>${d.needed == null ? "Loses money on every unit sold." : `Must sell ${pct(d.needed, 0)} more; the elasticity says ${pct(d.implied, 0)} more: ${dollars(d.delta)} a month.`}</td></tr>
    </tbody></table>
    <div class="memo-charts"><div>${fitChart}</div><div>${profitChart}</div></div>
    <p class="memo-foot">One SKU's own history is read here without pooling it with its catalogue, correcting for prices set because demand moved, or putting a range on the profit change. Measure the step before taking the next. Hubricon · Paid on proof.</p>`;
}

function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]); }

if (tool) init();
