// The Fee Staircase, on the reader's own listing and reports. Lesson 3 prices one listing from
// its five public numbers; lesson 7 reads an Inventory Age report against the 271-day cliff;
// lesson 8 reads a Fee Preview report and ranks every SKU past an edge. Then one printed page.
// The arithmetic is /lib/fees.js and /lib/call.js, the engine's, held to golden cases the engine
// computed (lib/fees.test.mjs, lib/call.test.mjs). Reports are read in this browser with
// FileReader and never uploaded; the one request is Amazon's published rate card, /ratecard.json.
"use strict";
import * as fees from "/lib/fees.js";
import * as call from "/lib/call.js";

const KEY = "hubricon.learn.fee-staircase";
const $ = (s, el = document) => el.querySelector(s);
const listing = document.getElementById("yours-listing");
const stock = document.getElementById("yours-stock");
const catalogue = document.getElementById("yours-catalogue");
const state = { rc: null, inventory: null, feePreview: null, names: {} };

const cents = (v) => `$${v.toFixed(2)}`;
const dollars = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`;
const n = (v) => Math.round(v).toLocaleString("en-US");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (v) => { const s = String(v ?? "").replace(/[$,\s]/g, ""); if (!s) return null; const x = Number(s); return Number.isFinite(x) ? x : null; };
const today = () => new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const longDate = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
const EDGE = { fee_band_edge: "Weight band", price_band_edge: "Price band", size_tier_edge: "Size tier", dim_weight_overage: "The box (dimensional weight)" };
const TIER = { small_standard: "Small standard", large_standard: "Large standard", oversize: "Oversize" };

const store = {
  read() { try { return JSON.parse(localStorage.getItem(KEY) || "null") || {}; } catch (e) { return {}; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} },
};

// ── Lesson 3: one listing ───────────────────────────────────────────────────────────────
function initListing() {
  listing.hidden = false;
  const sel = $("select[name=category]", listing);
  const cats = Object.keys(state.rc.fba.referral_by_category).sort();
  sel.innerHTML = `<option value="">Pick the category</option>` + cats.map((c) => `<option value="${esc(c)}">${esc(c.replace(/\b\w/g, (x) => x.toUpperCase()))}</option>`).join("");
  const saved = store.read().listing || {};
  for (const [k, v] of Object.entries(saved)) { const el = listing.querySelector(`[name="${k}"]`); if (el) el.value = v; }
  listing.addEventListener("input", readListing);
  $("#listing-example", listing).addEventListener("click", () => {
    const ex = JSON.parse(document.getElementById("fs-example").textContent);
    for (const [k, v] of Object.entries(ex)) { const el = listing.querySelector(`[name="${k}"]`); if (el) el.value = v; }
    readListing();
  });
  readListing();
}

function listingInputs() {
  return Object.fromEntries([...listing.querySelectorAll("[name]")].map((el) => [el.name, el.value.trim()]));
}

let listingMemo = "";
function readListing() {
  const v = listingInputs();
  const s = store.read(); s.listing = v; store.write(s);
  const out = $("#listing-out", listing);
  const dims = [num(v.l), num(v.w), num(v.h)];
  const item = fees.describeItem(state.rc, { price: num(v.price), category: v.category || null, bsr: num(v.rank), itemWeightOz: num(v.weight), dims: dims.every((d) => d > 0) ? dims : null });
  if (!item.price || !item.itemWeightOz || !item.dims) {
    out.innerHTML = `<p class="yours-status">Type the price, the weight and the three sides from the listing's page, or fill in the example.</p>`;
    listingMemo = ""; refreshMemo(); return;
  }
  const now = new Date();
  const ue = fees.unitEconomics(state.rc, item, num(v.cost), now);
  const found = fees.detect(state.rc, item, now);
  const peak = fees.cardNamed(state.rc, "peak");
  const card = fees.cardFor(state.rc, now);
  const rows = [
    ["What Amazon sees", `${TIER[item.tier] || "Off the standard card"}, billed at ${item.billableWeightOz.toFixed(1)} oz${item.dimWeightOz && item.dimWeightOz > item.itemWeightOz ? " (the box's dimensional weight, not the item's)" : ""}`],
  ];
  if (ue && ue.fee != null) rows.push(["Fulfilment fee now", `${cents(ue.fee)} a unit, on the card in force through ${longDate(card.through)}`]);
  if (ue && ue.feePeak != null && ue.peakDelta != null) rows.push(["On the holiday card", `${cents(ue.feePeak)} a unit, ${longDate(peak.effective)} to ${longDate(peak.through)}${ue.peakDelta > 0 ? `: ${cents(ue.peakDelta)} more a unit` : ""}`]);
  if (ue) rows.push(["Referral fee", `${cents(ue.referral)} (${pct(ue.referralRate, 0)})`]);
  if (ue && ue.keep != null) rows.push(["What a sale keeps, before your cost", `${cents(ue.keep)} a unit, ${pct(ue.keepPct)} of the price`]);
  if (ue && ue.contribution != null) {
    rows.push(["After your landed cost", `${cents(ue.contribution)} a unit. An ad sale can cost up to ${pct(ue.breakEvenAcos)} of the price before it loses money.`]);
    rows.push(["Price floor", `${cents(ue.priceFloor)} on today's card${ue.priceFloorPeak ? `, ${cents(ue.priceFloorPeak)} on the holiday card` : ""}: below it, every sale loses money.`]);
  }
  if (ue && ue.priceToHoldMargin) rows.push(["To keep the same margin on the holiday card", `${cents(ue.priceToHoldMargin)}${ue.peakWindowLow != null ? `; left at today's price, the three months cost about ${dollars(ue.peakWindowLow)} to ${dollars(ue.peakWindowHigh)} at the volume its rank suggests, an estimate` : ""}`]);
  const edges = found.map((f) => `<li><b>${EDGE[f.kind] || f.kind}.</b> ${cents(f.perUnitLow)}${f.perUnitHigh > f.perUnitLow ? ` to ${cents(f.perUnitHigh)}` : ""} a unit${f.dollarsLow ? `, about ${dollars(f.dollarsLow)} to ${dollars(f.dollarsHigh)} a year at the volume its rank suggests (an estimate)` : ""}.${f.evidence && f.evidence.overByOz != null ? ` It sits ${f.evidence.overByOz} oz past the ${f.evidence.edge}-oz edge.` : ""}</li>`).join("");
  const peakWarn = ue && ue.peakDelta > 0 && now < new Date(`${peak.effective}T00:00:00`) ? `<p class="yours-warn">Amazon's holiday card starts ${longDate(peak.effective)}: this unit pays ${cents(ue.peakDelta)} more each, through ${longDate(peak.through)}.</p>` : "";
  out.innerHTML = `<table class="yours-facts"><tbody>${rows.map(([k, x]) => `<tr><th scope="row">${k}</th><td>${x}</td></tr>`).join("")}</tbody></table>
    ${peakWarn}
    ${found.length ? `<p class="yours-k">Edges it sits just past</p><ul class="yours-list">${edges}</ul>` : `<p>No edge worth moving on this listing: it sits clear of every step the card has, on both cards.</p>`}`;
  listingMemo = `<h3>${esc(v.name || "Your listing")}</h3><table class="memo-table"><tbody>${rows.map(([k, x]) => `<tr><th>${k}</th><td>${x}</td></tr>`).join("")}</tbody></table>` +
    (found.length ? `<p><b>Edges:</b> ${found.map((f) => `${EDGE[f.kind] || f.kind}, ${cents(f.perUnitLow)} a unit`).join("; ")}.</p>` : "<p>No edge worth moving.</p>");
  refreshMemo();
}

// ── Lessons 7 and 8: the reader's own reports ──────────────────────────────────────────
const READERS = {
  inventory: { panel: () => stock, parse: call.parseInventoryHealth, label: "Inventory Age" },
  fees: { panel: () => catalogue, parse: call.parseFeePreview, label: "Fee Preview", key: "feePreview" },
};

function initDrop(which) {
  const r = READERS[which], panel = r.panel();
  panel.hidden = false;
  const drop = $(".yours-drop", panel), input = $("input[type=file]", panel), msg = $(".yours-drop-state", panel);
  const load = (file) => {
    drop.classList.remove("loaded", "bad");
    if (/\.xlsx?$/i.test(file.name)) { drop.classList.add("bad"); msg.textContent = "That is an Excel file. Download the report as .txt or .csv instead."; return; }
    const fr = new FileReader();
    fr.onload = () => {
      try {
        state[r.key || which] = r.parse(String(fr.result));
        state.names[which] = file.name;
        drop.classList.add("loaded");
        msg.textContent = `${file.name}: ${n((state[r.key || which]).length)} SKUs read, here in your browser.`;
      } catch (err) {
        state[r.key || which] = null;
        drop.classList.add("bad");
        msg.textContent = err.message || "This file could not be read.";
      }
      readReports();
    };
    fr.onerror = () => { drop.classList.add("bad"); msg.textContent = "This file could not be opened. Download the report again and drop the new copy."; };
    fr.readAsText(file);
  };
  input.addEventListener("change", () => input.files[0] && load(input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) load(e.dataTransfer.files[0]); });
}

let reportMemo = "";
function readReports() {
  const out = call.analyse(state.rc, { inventory: state.inventory || [], feePreview: state.feePreview || [], today: new Date() });
  // Lesson 7: the cliff.
  const s = $("#stock-out", stock);
  if (state.inventory) {
    const aged = out.aged.slice().sort((a, b) => (b.month + (b.cliff ? b.cliff.month : 0)) - (a.month + (a.cliff ? a.cliff.month : 0)));
    const now = aged.reduce((t, a) => t + a.month, 0), ahead = aged.reduce((t, a) => t + (a.cliff ? a.cliff.month : 0), 0);
    s.innerHTML = `<p>Aged-inventory surcharge this month: <b class="money">${dollars(now)}</b>${ahead > 0 ? `. If the units now 241 to 270 days old do not sell before the next snapshot on the 15th, another <b class="money">${dollars(ahead)}</b> a month` : ""}, an estimate.</p>
      ${aged.length ? `<table class="yours-table-wide"><thead><tr><th>SKU</th><th>Aged units</th><th>This month</th><th>At the next snapshot</th></tr></thead><tbody>${aged.slice(0, 12).map((a) => `<tr><td>${esc(a.sku)}</td><td class="num">${n(a.aged_units || 0)}</td><td class="num">${cents(a.month)}</td><td class="num">${a.cliff ? cents(a.cliff.month) : "–"}</td></tr>`).join("")}</tbody></table>` : "<p>No unit in this report has reached 181 days.</p>"}`;
    s.hidden = false;
  }
  // Lesson 8: every SKU, in order.
  const c = $("#catalogue-out", catalogue);
  if (state.feePreview) {
    const edges = out.edges.slice().sort((a, b) => (b.month ?? -1) - (a.month ?? -1) || b.per_unit - a.per_unit);
    const month = edges.reduce((t, e) => t + (e.month || 0), 0);
    c.innerHTML = `<p>${edges.length ? `${n(edges.length)} of ${n(state.feePreview.length)} SKUs sit just past an edge.` : "No SKU sits just past an edge worth moving."}${state.inventory ? ` At the last 30 days' pace, together about <b class="money">${dollars(month)}</b> a month, an estimate.` : " Drop your Inventory Age report in lesson 7 to put units, and dollars a month, on each."}</p>
      ${edges.length ? `<table class="yours-table-wide"><thead><tr><th>SKU</th><th>Edge</th><th>A unit</th><th>Units, last 30 days</th><th>A month</th></tr></thead><tbody>${edges.slice(0, 25).map((e) => `<tr><td>${esc(e.sku)}<span class="yours-sub">${esc((e.name || "").slice(0, 48))}</span></td><td>${EDGE[e.kind] || e.kind}</td><td class="num">${cents(e.per_unit)}</td><td class="num">${e.units != null ? n(e.units) : "–"}</td><td class="num">${e.month != null ? cents(e.month) : "–"}</td></tr>`).join("")}</tbody></table>` : ""}`;
    c.hidden = false;
    reportMemo = `<h3>Every SKU, in order</h3><p>${edges.length} of ${state.feePreview.length} SKUs past an edge${state.inventory ? `, about ${dollars(month)} a month at the last 30 days' pace (an estimate)` : ""}.</p>` +
      (edges.length ? `<table class="memo-table"><thead><tr><th>SKU</th><th>Edge</th><th>A unit</th><th>A month</th></tr></thead><tbody>${edges.slice(0, 15).map((e) => `<tr><td>${esc(e.sku)}</td><td>${EDGE[e.kind] || e.kind}</td><td>${cents(e.per_unit)}</td><td>${e.month != null ? cents(e.month) : "–"}</td></tr>`).join("")}</tbody></table>` : "");
  }
  if (state.inventory && out.aged.length) {
    const now = out.aged.reduce((t, a) => t + a.month, 0);
    reportMemo += `<p><b>Aged stock:</b> about ${dollars(now)} a month in aged-inventory surcharge now (an estimate).</p>`;
  }
  refreshMemo();
}

// ── The page to keep ────────────────────────────────────────────────────────────────────
function refreshMemo() {
  const memo = document.querySelector('[data-yours="memo"]');
  if (!memo) return;
  const body = listingMemo + reportMemo;
  memo.innerHTML = body ? `<header class="memo-head"><p class="memo-k">Fee memo · ${today()}</p><h2>Amazon's fee staircase, on your own listings</h2>
    <p>Prepared with The Fee Staircase, a free course from Hubricon (hubricon.com/learn/fee-staircase), on Amazon's published 2026 cards. Read in the browser it was typed into: no report left it.</p></header>
    ${body}<p class="memo-foot">Figures marked estimate use a volume or an age assumption. Amazon bills the packed weight, which can only be heavier than the listing's. Hubricon · Paid on proof.</p>` : "";
  document.body.classList.toggle("has-memo", Boolean(body));
  document.querySelectorAll("[data-memo-print]").forEach((b) => { b.hidden = !body; });
}

document.querySelectorAll("[data-memo-print]").forEach((b) => b.addEventListener("click", () => window.print()));

if (listing || stock || catalogue) {
  fetch("/ratecard.json").then((r) => r.json()).then((rc) => {
    state.rc = rc;
    if (listing) initListing();
    if (stock) initDrop("inventory");
    if (catalogue) initDrop("fees");
  }).catch(() => {});
}
