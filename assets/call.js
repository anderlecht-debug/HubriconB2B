// /call's behaviour: read the dropped reports with FileReader, price them with
// /lib/call.js, draw the result. Nothing leaves the page: no fetch carries a file,
// and there is no analytics script on /call. "Keep this reading" is the browser's own
// print dialog on this page (call.html's print styles), so keeping it sends nothing either.
import * as call from "/lib/call.js";

const $ = (id) => document.getElementById(id);
const state = { inventory: null, feePreview: null, ppc: null, shopify: null, cost: null };
const names = {};
let rc = null;

const usd = (v) => `$${Math.floor(v).toLocaleString("en-US")}`;
const cents = (v) => `$${v.toFixed(2)}`;
const pct = (v) => `${(v * 100).toFixed(1)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const EDGE = { fee_band_edge: "Weight band", price_band_edge: "Price band", size_tier_edge: "Size tier", dim_weight_overage: "Box (dimensional weight)" };
const n = (v) => v.toLocaleString("en-US");

const READERS = {
  inventory: { label: "Inventory Age", parse: call.parseInventoryHealth, done: (rows) => `${n(rows.length)} SKUs read` },
  fees: { key: "feePreview", label: "Fee Preview", parse: call.parseFeePreview, done: (rows) => `${n(rows.length)} SKUs read` },
  ads: { key: "ppc", label: "Ad campaigns", parse: call.parsePpcCampaign, done: (p) => `${p.campaigns} campaigns, ${p.days ?? "?"} days read` },
  shopify: { label: "Shopify Products", parse: call.parseShopifyProducts, done: (rows) => `${n(rows.length)} variants read` },
  cost: { label: "Landed cost by SKU", parse: call.parseCostFile, done: (c) => `${n(c.skus)} SKUs with their own cost` + (c.example ? " (the template's example row left out)" : "") },
};

function load(which, file) {
  const r = READERS[which], drop = $(`drop-${which}`), msg = $(`state-${which}`);
  drop.classList.remove("loaded", "bad");
  if (/\.xlsx?$/i.test(file.name)) {
    drop.classList.add("bad");
    msg.textContent = "That is an Excel file. Download or save it as .txt or .csv instead.";
    return;
  }
  const fr = new FileReader();
  fr.onload = () => {
    try {
      const parsed = r.parse(String(fr.result));
      state[r.key || which] = parsed;
      names[which] = file.name;
      drop.classList.add("loaded");
      msg.textContent = `${file.name}: ${r.done(parsed)}`;
    } catch (err) {
      state[r.key || which] = null;
      delete names[which];
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
const tile = ([k, v, b, money]) => `<div class="stat"><span class="n${money ? " money" : ""}">${v}</span><span class="k">${k}</span><span class="b">${b}</span></div>`;

/** The reading's own heading on paper: the date, the files read and what was typed. */
function stampReading() {
  const now = new Date();
  $("reading-when").textContent = `Read on ${now.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })} at ${now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}, from your own files, in your own browser.`;
  const files = Object.keys(READERS).filter((w) => names[w]).map((w) => `${READERS[w].label} (${names[w]})`);
  $("reading-files").textContent = files.length ? `Read: ${files.join(" · ")}.` : "";
  const costPct = parseFloat($("cost").value), targetPct = parseFloat($("target").value);
  const typed = [];
  if (Number.isFinite(costPct)) typed.push(`landed cost ${costPct}% of price`);
  if (Number.isFinite(targetPct)) typed.push(`target ACoS ${targetPct}%`);
  $("reading-typed").textContent = typed.length ? `You typed: ${typed.join(" · ")}.` : "Nothing typed.";
}
addEventListener("beforeprint", stampReading);
$("keep").addEventListener("click", () => { stampReading(); window.print(); });

function draw() {
  const amazon = Boolean(state.inventory || state.feePreview);
  if (!rc || (!amazon && !state.shopify)) { $("results").hidden = true; return; }
  $("results").hidden = false;
  $("amazon").hidden = !amazon;
  $("shopify").hidden = !state.shopify;
  if (amazon) drawAmazon();
  if (state.shopify) drawShopify();
  stampReading();
}

function drawAmazon() {
  const costPct = parseFloat($("cost").value), targetPct = parseFloat($("target").value);
  const out = call.analyse(rc, {
    inventory: state.inventory || [], feePreview: state.feePreview || [], ppc: state.ppc,
    costShare: Number.isFinite(costPct) ? costPct / 100 : null, costBySku: state.cost ? state.cost.bySku : {},
    targetAcos: Number.isFinite(targetPct) ? targetPct / 100 : null, today: new Date(),
  });
  const t = out.totals;
  const total = t.aged + t.low + t.edges + t.ads;
  $("total").innerHTML = `${usd(total)}<span class="est">estimate</span>`;
  const parts = [];
  if (state.inventory) parts.push("aged stock and the low-inventory fee from the Inventory Age report");
  if (state.feePreview) parts.push("fee edges from Fee Preview");
  if (out.ads && out.ads.over_month != null) parts.push("ads past break-even from the campaign report");
  $("total-note").textContent = `This month, at the last 30 days' pace: ${parts.join("; ")}.` +
    (t.cliff > 0 ? ` On top of it, ${usd(t.cliff)} more a month from the next snapshot if the oldest stock does not sell.` : "") +
    (total > 0 ? ` Twelve months at this pace would be ${usd(total * 12)}, an estimate: a plain multiplication, not a forecast.` : "");

  const tiles = [
    ["Aged-inventory surcharge, a month", usd(t.aged), state.inventory ? (out.aged.some((a) => a.basis === "amazon") ? "Amazon's own estimate" : "Amazon's schedule, estimate") : "needs Inventory Age", t.aged > 0],
    ["Low-inventory-level fee, a month", usd(t.low), state.inventory ? "at the last 30 days' pace, estimate" : "needs Inventory Age", t.low > 0],
    ["Units past a fee edge, a month", usd(t.edges), state.feePreview ? (state.inventory ? "Amazon's measurement, your units, estimate" : "add Inventory Age for units") : "needs Fee Preview", t.edges > 0],
    ["Ads past break-even, a month", usd(t.ads), out.ads ? (out.ads.over_month != null ? "campaign report, blended, estimate" : "needs a landed cost") : "needs the campaign report", t.ads > 0],
  ];
  $("tiles").innerHTML = tiles.map(tile).join("");

  // Aged stock.
  $("leak-aged").hidden = !state.inventory;
  if (state.inventory) {
    const amazonBasis = out.aged.some((a) => a.basis === "amazon");
    $("why-aged").textContent = `Once a unit has sat 181 days, Amazon adds a surcharge by the cubic foot; at day 271 it goes from ${cents(call.agedRate(270))} to ${cents(call.agedRate(271))} a cubic foot, assessed from a snapshot on the 15th. ` +
      (amazonBasis ? "The surcharge now is Amazon's own estimate from your report." : "Your report carries no surcharge estimate, so it is priced from Amazon's schedule at each age band's midpoint.") +
      " The next-snapshot figure is the units now 241 to 270 days old, if none of them sell first.";
    $("rows-aged").innerHTML = out.aged.slice(0, 15).map((a) => row([
      [esc(a.sku), "sku"], [esc(a.name), "name"], [n(a.aged_units), "num"], [cents(a.month), "num"],
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
      [e.units != null ? n(e.units) : "–", "num"], [e.month != null ? cents(e.month) : "add Inventory Age", "num"],
    ])).join("") || row([["No SKU sits just past an edge worth moving.", ""]]);
  }

  // Ads.
  $("leak-ads").hidden = !state.feePreview;
  if (state.feePreview) {
    const be = out.catalogue_be;
    const lines = [];
    if (!out.margins.length) lines.push("Type a landed cost above, or drop a cost file, to see break-even: it is what an ad sale can cost before the sale loses money.");
    else {
      const yours = out.margins.filter((m) => m.cost_basis === "yours").length;
      lines.push(`Break-even ad cost of sale is what is left of the price after Amazon's own fees and your landed cost. Across these SKUs, weighted by sales, it is ${pct(be)}.`);
      if (state.cost) lines.push(yours === out.margins.length ? "Every SKU here is priced at its own cost from your file." : `${yours} of ${out.margins.length} SKUs are priced at their own cost from your file; the rest at the % you typed, an estimate.`);
      if (out.target != null) lines.push(out.over_target.length ? `At your ${pct(out.target)} target, ${out.over_target.length} of ${out.margins.length} SKUs lose money on every ad sale.` : `Your ${pct(out.target)} target sits under break-even on every SKU here.`);
      if (out.ads) lines.push(`Your campaigns ran at ${pct(out.ads.acos)} over ${out.ads.days ?? "the report's"} days` + (out.ads.over_month ? `: about ${usd(out.ads.over_month)} a month spent past break-even, an estimate.` : ", inside break-even."));
    }
    $("why-ads").textContent = lines.join(" ");
    $("rows-ads").innerHTML = out.margins.slice(0, 20).map((m) => row([
      [esc(m.sku), "sku"], [esc(m.name), "name"], [cents(m.price), "num"], [cents(m.amazon_fees), "num"],
      [`${cents(m.cost)}<span class="basis">${m.cost_basis === "yours" ? "your cost" : "est. from your %"}</span>`, "num"],
      [pct(m.acos), "num"], [out.target != null ? (m.acos < out.target ? `−${cents((out.target - m.acos) * 100)}` : `+${cents((m.acos - out.target) * 100)}`) : "–", "num"],
    ])).join("");
  }
}

function drawShopify() {
  const s = call.analyseShopify(rc, state.shopify);
  const share = s.catalogue_share != null ? `${Math.round(s.catalogue_share * 100)}%` : "–";
  $("shop-note").textContent = `${n(s.priced)} live variants with a price, read from your own export. A Products export carries no sales, so these are per unit and per parcel; your Orders export, or your own count, turns them into a month on the call.` +
    (s.no_weight ? ` ${n(s.no_weight)} have no weight set, so their parcels could not be checked.` : "");
  $("shop-tiles").innerHTML = [
    ["Listed below their own compare-at", `${n(s.below)} of ${n(s.priced)}`, `${share} of the live catalogue`, false],
    ["The gap, a unit, on average", s.gap_mean != null ? `${cents(s.gap_mean)}<span class="est">estimate</span>` : "–", s.policy ? "over half the catalogue, so it reads as the price" : "under half the catalogue: promotions, not the price", s.gap_mean != null],
    ["Parcels just past a pound line", n(s.parcels.length), "within 3 oz over, one unit a parcel", false],
    ["A parcel, nearest zone to farthest", s.parcel_low != null ? `${cents(s.parcel_low)}–${cents(s.parcel_high)}<span class="est">estimate</span>` : "–", "USPS Ground Advantage card", s.parcel_low != null],
  ].map(tile).join("");

  $("why-anchor").textContent = `Your export's own two numbers for each variant: the price, and the compare-at it is listed under. ${n(s.below)} of ${n(s.priced)} live variants (${share}) sit below their compare-at. ` +
    (s.policy
      ? "When most of the catalogue sits there, the compare-at stops being a sale and becomes a price no customer is shown, and the gap is margin decided in advance. The gap is your two numbers subtracted; what it costs you depends on whether anyone would pay the compare-at, so it is an estimate. One export cannot say how long the prices have sat there; that is the question for the call."
      : "That is under half the catalogue, which reads as promotions rather than the price, so no gap is counted here.");
  $("rows-anchor").innerHTML = s.anchors.slice(0, 20).map((a) => row([
    [esc(a.sku), "sku"], [esc(a.name), "name"], [cents(a.price), "num"], [cents(a.compare_at), "num"], [`${cents(a.per_unit)} est.`, "num"], [`${Math.round(a.share * 100)}%`, "num"],
  ])).join("") || row([[s.policy ? "No variant sits far enough below its compare-at to count." : "Not counted: under half the catalogue is below its compare-at.", ""]]);

  $("why-parcel").textContent = "USPS Ground Advantage bills anything over a pound at the next whole pound, so a parcel a few tenths of an ounce over the line pays the heavier rate on every order. The weight is the one set on your own product, the one Shopify hands the carrier; if your shipping settings add a box's weight, the parcel is heavier than this. A range across zones 1 to 8, because only your orders show your zone mix: an estimate.";
  $("rows-parcel").innerHTML = s.parcels.slice(0, 20).map((p) => row([
    [esc(p.sku), "sku"], [esc(p.name), "name"], [`${p.weight_oz.toFixed(2)} oz`, "num"], [`${p.over_by} oz`, "num"], [`${esc(p.band_above)}, not ${esc(p.band_below)}`],
    [p.priced ? `${cents(p.low)}–${cents(p.high)} est.` : "not on the loaded card", "num"],
  ])).join("") || row([["No parcel sits within 3 oz over a pound line.", ""]]);
}

fetch("/ratecard.json").then((r) => r.json()).then((j) => { rc = j; draw(); });
