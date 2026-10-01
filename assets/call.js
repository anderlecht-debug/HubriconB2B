// /call's behaviour: read the dropped reports with FileReader, price them with
// /lib/call.js, draw the result. Nothing leaves the page: no fetch carries a file,
// and there is no analytics script on /call.
import * as call from "/lib/call.js";

const $ = (id) => document.getElementById(id);
const state = { inventory: null, feePreview: null, ppc: null };
let rc = null;

const usd = (v) => `$${Math.floor(v).toLocaleString("en-US")}`;
const cents = (v) => `$${v.toFixed(2)}`;
const pct = (v) => `${(v * 100).toFixed(1)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const EDGE = { fee_band_edge: "Weight band", price_band_edge: "Price band", size_tier_edge: "Size tier", dim_weight_overage: "Box (dimensional weight)" };

const READERS = {
  inventory: { parse: call.parseInventoryHealth, done: (rows) => `${rows.length.toLocaleString("en-US")} SKUs read` },
  fees: { key: "feePreview", parse: call.parseFeePreview, done: (rows) => `${rows.length.toLocaleString("en-US")} SKUs read` },
  ads: { key: "ppc", parse: call.parsePpcCampaign, done: (p) => `${p.campaigns} campaigns, ${p.days ?? "?"} days read` },
};

function load(which, file) {
  const r = READERS[which], drop = $(`drop-${which}`), msg = $(`state-${which}`);
  drop.classList.remove("loaded", "bad");
  if (/\.xlsx?$/i.test(file.name)) {
    drop.classList.add("bad");
    msg.textContent = "That is an Excel file. Download the report from Seller Central as .txt or .csv instead.";
    return;
  }
  const fr = new FileReader();
  fr.onload = () => {
    try {
      const parsed = r.parse(String(fr.result));
      state[r.key || which] = parsed;
      drop.classList.add("loaded");
      msg.textContent = `${file.name}: ${r.done(parsed)}`;
    } catch (err) {
      state[r.key || which] = null;
      drop.classList.add("bad");
      msg.textContent = err.message || "This file could not be read.";
    }
    draw();
  };
  fr.readAsText(file);
}

for (const which of Object.keys(READERS)) {
  const input = $(`file-${which}`), drop = $(`drop-${which}`);
  input.addEventListener("change", () => input.files[0] && load(which, input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) load(which, f); });
}
for (const id of ["cost", "target"]) $(id).addEventListener("input", draw);

const row = (cells) => `<tr>${cells.map(([v, cls]) => `<td${cls ? ` class="${cls}"` : ""}>${v}</td>`).join("")}</tr>`;

function draw() {
  if (!rc || (!state.inventory && !state.feePreview)) { $("results").hidden = true; return; }
  const costPct = parseFloat($("cost").value), targetPct = parseFloat($("target").value);
  const out = call.analyse(rc, {
    inventory: state.inventory || [], feePreview: state.feePreview || [], ppc: state.ppc,
    costShare: Number.isFinite(costPct) ? costPct / 100 : null,
    targetAcos: Number.isFinite(targetPct) ? targetPct / 100 : null, today: new Date(),
  });
  const t = out.totals;
  const total = t.aged + t.low + t.edges + t.ads;
  $("results").hidden = false;
  $("total").innerHTML = `${usd(total)}<span class="est">estimate</span>`;
  const parts = [];
  if (state.inventory) parts.push("aged stock and the low-inventory fee from the Inventory Age report");
  if (state.feePreview) parts.push("fee edges from Fee Preview");
  if (out.ads && out.ads.over_month != null) parts.push("ads past break-even from the campaign report");
  $("total-note").textContent = `This month, at the last 30 days' pace: ${parts.join("; ")}.` + (t.cliff > 0 ? ` On top of it, ${usd(t.cliff)} more a month from the next snapshot if the oldest stock does not sell.` : "");

  const tiles = [
    ["Aged-inventory surcharge", t.aged, state.inventory ? (out.aged.some((a) => a.basis === "amazon") ? "Amazon's own estimate" : "Amazon's schedule") : "needs Inventory Age"],
    ["Low-inventory-level fee", t.low, state.inventory ? "at the last 30 days' pace" : "needs Inventory Age"],
    ["Units past a fee edge", t.edges, state.feePreview ? (state.inventory ? "Amazon's measurement, your units" : "add Inventory Age for units") : "needs Fee Preview"],
    ["Ads past break-even", t.ads, out.ads ? (out.ads.over_month != null ? "campaign report, blended" : "needs a landed cost") : "needs the campaign report"],
  ];
  $("tiles").innerHTML = tiles.map(([k, v, b]) => `<div class="tile"><span class="n${v > 0 ? " money" : ""}">${usd(v)}</span><span class="k">${k}, a month</span><span class="b">${b}</span></div>`).join("");

  // Aged stock.
  $("leak-aged").hidden = !state.inventory;
  if (state.inventory) {
    const amazon = out.aged.some((a) => a.basis === "amazon");
    $("why-aged").textContent = `Once a unit has sat 181 days, Amazon adds a surcharge by the cubic foot; at day 271 it goes from ${cents(call.agedRate(270))} to ${cents(call.agedRate(271))} a cubic foot, assessed from a snapshot on the 15th. ` +
      (amazon ? "The surcharge now is Amazon's own estimate from your report." : "Your report carries no surcharge estimate, so it is priced from Amazon's schedule at each age band's midpoint.") +
      " The next-snapshot figure is the units now 241 to 270 days old, if none of them sell first.";
    $("rows-aged").innerHTML = out.aged.slice(0, 15).map((a) => row([
      [esc(a.sku), "sku"], [esc(a.name), "name"], [a.aged_units.toLocaleString("en-US"), "num"], [cents(a.month), "num"],
      [a.cliff ? cents(a.cliff.month) : "–", "num"], [a.basis === "amazon" ? "Amazon's estimate" : "Amazon's schedule, estimate"],
    ])).join("") || row([["No aged units in this report.", ""]]);
  }

  // Low inventory.
  $("leak-low").hidden = !state.inventory;
  if (state.inventory) {
    $("rows-low").innerHTML = out.low.slice(0, 15).map((l) => row([
      [esc(l.sku), "sku"], [esc(l.name), "name"], [l.dos.toFixed(1), "num"], [cents(l.rate), "num"], [cents(l.month), "num"],
      [l.applied_per_amazon == null ? "–" : l.applied_per_amazon ? "Yes" : "No"],
    ])).join("") || row([["No SKU under 28 days of supply at this pace.", ""]]);
  }

  // Fee edges.
  $("leak-edges").hidden = !state.feePreview;
  if (state.feePreview) {
    $("rows-edges").innerHTML = out.edges.slice(0, 20).map((e) => row([
      [esc(e.sku), "sku"], [esc(e.name), "name"], [EDGE[e.kind] || e.kind], [cents(e.per_unit), "num"],
      [e.units != null ? e.units.toLocaleString("en-US") : "–", "num"], [e.month != null ? cents(e.month) : "add Inventory Age", "num"],
    ])).join("") || row([["No SKU sits just past an edge worth moving.", ""]]);
  }

  // Ads.
  $("leak-ads").hidden = !state.feePreview;
  if (state.feePreview) {
    const be = out.catalogue_be;
    const lines = [];
    if (!out.margins.length) lines.push("Type a landed cost above to see break-even: it is what an ad sale can cost before the sale loses money.");
    else {
      lines.push(`Break-even ad cost of sale is what is left of the price after Amazon's own fees and your landed cost. Across these SKUs, weighted by sales, it is ${pct(be)}.`);
      if (out.target != null) lines.push(out.over_target.length ? `At your ${pct(out.target)} target, ${out.over_target.length} of ${out.margins.length} SKUs lose money on every ad sale.` : `Your ${pct(out.target)} target sits under break-even on every SKU here.`);
      if (out.ads) lines.push(`Your campaigns ran at ${pct(out.ads.acos)} over ${out.ads.days ?? "the report's"} days` + (out.ads.over_month ? `: about ${usd(out.ads.over_month)} a month spent past break-even.` : ", inside break-even."));
    }
    $("why-ads").textContent = lines.join(" ");
    $("rows-ads").innerHTML = out.margins.slice(0, 20).map((m) => row([
      [esc(m.sku), "sku"], [esc(m.name), "name"], [cents(m.price), "num"], [cents(m.amazon_fees), "num"], [cents(m.cost) + (m.cost_basis === "assumed" ? " est." : ""), "num"],
      [pct(m.acos), "num"], [out.target != null ? (m.acos < out.target ? `−${cents((out.target - m.acos) * 100)}` : `+${cents((m.acos - out.target) * 100)}`) : "–", "num"],
    ])).join("");
  }
}

fetch("/ratecard.json").then((r) => r.json()).then((j) => { rc = j; draw(); });
