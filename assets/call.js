// /call's behaviour: read the dropped reports with FileReader, price them with
// /lib/call.js, draw the result. Nothing leaves the page: no fetch carries a file,
// and there is no analytics script on /call. "Keep this reading" is the browser's own
// print dialog on this page (call.html's print styles), so keeping it sends nothing either.
import * as call from "/lib/call.js";

const $ = (id) => document.getElementById(id);
const state = { inventory: null, feePreview: null, ppc: null, shopify: null, orders: null, cost: null };
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
  orders: { label: "Shopify Orders", parse: call.parseShopifyOrders,
    done: (o) => `${n(o.orders)} paid orders over ${n(o.days)} day${o.days === 1 ? "" : "s"} read` + (o.days < call.MIN_ORDER_DAYS ? ", under a week: too short to read a month from" : "") },
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

/* Where the booker said they sell: ?p=shopify|amazon|both, else the answer /apply kept in this
   browser when the call was booked (the same origin's "hubricon_booked", kept 14 days), else
   nobody knows and every card shows in the usual order. A Shopify seller gets the Shopify cards
   first, the Shopify lede, and no ACoS box; the Amazon cards wait below a line, still there. */
const CHANNEL = (() => {
  const p = String(new URLSearchParams(location.search).get("p") || "").toLowerCase();
  if (["amazon", "shopify", "both"].includes(p)) return p;
  try {
    const b = JSON.parse(localStorage.getItem("hubricon_booked") || "null");
    if (b && Date.now() - b.at < 14 * 864e5 && ["Amazon", "Shopify", "Both"].includes(b.channel)) return b.channel.toLowerCase();
  } catch {}
  return null;
})();
const LEDE = {
  shopify: "Drop in your Shopify Products export, and your Orders export if you have it. This page reads them and prices what only your own data shows: prices sitting under their own compare-at, parcels just past a pound line, and what each variant keeps after Shopify Payments and your cost, with the return on ad spend it needs to break even.",
  amazon: "Drop in your Seller Central reports. This page reads them and prices the costs only your own data shows: aged stock heading for day 271, the low-inventory fee, units just past a fee edge, and ads spending past break-even.",
};
const ORDER = {
  shopify: [["shopify", "orders", "cost"], "Also selling on Amazon? These read your Seller Central reports.", ["inventory", "fees", "ads"]],
  amazon: [["inventory", "fees", "ads", "cost"], "Also selling on Shopify? These read your Shopify exports.", ["shopify", "orders"]],
};
if (ORDER[CHANNEL]) {
  const [first, line, rest] = ORDER[CHANNEL];
  const grid = document.querySelector(".inputs");
  const also = document.createElement("p");
  also.className = "also";
  also.textContent = line;
  for (const w of first) grid.append($(`drop-${w}`));
  grid.append(also);
  for (const w of rest) grid.append($(`drop-${w}`));
  $("lede").textContent = LEDE[CHANNEL];
}
if (CHANNEL === "shopify") $("results").insertBefore($("shopify"), $("amazon"));

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
  // the ACoS box is Amazon's: a Shopify seller sees it only once an Amazon report is in
  $("knob-target").hidden = CHANNEL === "shopify" && !amazon;
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
    ["Low-inventory-level fee, a month", usd(t.low), state.inventory ? (state.feePreview ? "by your size tiers, estimate" : "size tier assumed, estimate") : "needs Inventory Age", t.low > 0],
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
    // the arithmetic the rows below rest on, said in full (lib/call.js lowInventoryFee)
    $("leak-low").querySelector(".why").textContent = "Amazon charges this on each unit shipped while both your 30-day and your 90-day days of supply sit under 28; the higher of the two sets the rate. " +
      (out.low_amazon_dos ? "Days of supply here are Amazon's own 30- and 90-day figures from your report where it has them, else what you have on hand at the last 30 and 90 days' shipping pace. "
        : "Days of supply here is what you have on hand at the last 30 and 90 days' shipping pace. ") +
      (state.feePreview ? "The rate is each SKU's size tier, from your Fee Preview. "
        : "Without Fee Preview the size tier is assumed to be small standard, the lowest rate, so no figure here is overstated; add Fee Preview for your own tiers. ") +
      (out.low_exempt ? `${n(out.low_exempt)} SKU${out.low_exempt === 1 ? " is" : "s are"} left out as exempt (under 20 units shipped in 7 days, or marked exempt in your report). ` : "") +
      "Not checked, because no report shows them: the exemptions for a new seller, a New Selection listing and stock auto-replenished through AWD. Each figure a month is an estimate at the last 30 days' pace.";
    $("rows-low").innerHTML = out.low.slice(0, 15).map((l) => row([
      [esc(l.sku), "sku"], [esc(l.name), "name"], [l.dos.toFixed(1), "num"],
      [`${cents(l.rate)}<span class="basis">${esc(call.SCHEDULE.low_inventory_tier_label[l.tier] || "")}${/assumed/.test(l.tier_basis) ? ", assumed" : ""}</span>`, "num"],
      [`${cents(l.month)}<span class="basis">estimate</span>`, "num"],
      [l.applied_per_amazon == null ? "–" : l.applied_per_amazon ? "Yes" : "No"],
    ])).join("") || row([["No SKU under 28 days of supply on both the 30 and 90 days.", ""]]);
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

const roasText = (r) => (r == null ? "none" : r.toFixed(2));

function drawShopify() {
  const costPct = parseFloat($("cost").value);
  const s = call.analyseShopify(rc, state.shopify, {
    costShare: Number.isFinite(costPct) ? costPct / 100 : null, costBySku: state.cost ? state.cost.bySku : {}, orders: state.orders,
  });
  const t = s.totals, o = s.orders;
  const share = s.catalogue_share != null ? `${Math.round(s.catalogue_share * 100)}%` : "–";

  // The headline: a month once the Orders export sets the pace, else a unit and a parcel.
  $("shop-label").textContent = t ? "In your Shopify exports, a month" : "In your Shopify export, a unit and a parcel";
  const total = t ? t.anchors_month + t.parcels_low_month : 0;
  $("shop-total").hidden = !t;
  $("shop-total").innerHTML = t ? `${usd(total)}<span class="est">estimate</span>` : "";
  let note = `${n(s.priced)} live variants with a price, read from your own Products export.`;
  if (t) {
    const parts = [s.policy ? "the compare-at gap on every unit sold" : null, "the pound line on every order of one unit, at the nearest zone's rate"].filter(Boolean);
    note += ` ${n(o.orders)} paid orders over ${n(o.days)} days, from your Orders export, set the pace. The figure above is ${parts.join(", and ")}, a month.`
      + (o.matched_units < o.units ? ` ${n(o.matched_units)} of the ${n(o.units)} units sold match a variant in the Products export; the rest are left out.` : "")
      + (total > 0 ? ` Twelve months at this pace would be ${usd(total * 12)}, an estimate: a plain multiplication, not a forecast.` : "");
  } else if (s.orders_too_short) {
    note += " Your Orders export covers under a week, too short to read a month from, so these stay per unit and per parcel.";
  } else {
    note += " A Products export carries no sales, so these are per unit and per parcel; drop your Orders export too and each becomes a month.";
  }
  if (s.no_weight) note += ` ${n(s.no_weight)} have no weight set, so their parcels could not be checked.`;
  $("shop-note").textContent = note;

  const roasTile = ["Break-even ROAS, across the catalogue", s.catalogue_roas != null ? `${s.catalogue_roas.toFixed(2)}<span class="est">estimate</span>` : "–",
    !s.margins.length ? "needs a cost" : s.catalogue_roas_basis === "sales" ? "on your sales, after Shopify Payments and your cost" : "one unit of each variant, after Shopify Payments and your cost", false];
  $("shop-tiles").innerHTML = [
    ["Listed below their own compare-at", `${n(s.below)} of ${n(s.priced)}`, `${share} of the live catalogue`, false],
    t && s.policy
      ? ["The compare-at gap, a month", `${usd(t.anchors_month)}<span class="est">estimate</span>`, "on every unit your orders show", t.anchors_month > 0]
      : ["The gap, a unit, on average", s.gap_mean != null ? `${cents(s.gap_mean)}<span class="est">estimate</span>` : "–", s.policy ? "over half the catalogue, so it reads as the price" : "under half the catalogue: promotions, not the price", s.gap_mean != null],
    t
      ? ["Parcels past a pound line, a month", `${usd(t.parcels_low_month)}–${usd(t.parcels_high_month)}<span class="est">estimate</span>`, "orders of one unit, nearest zone to farthest", t.parcels_low_month > 0]
      : ["Parcels just past a pound line", n(s.parcels.length), "within 3 oz over, one unit a parcel", false],
    roasTile,
  ].map(tile).join("");

  $("why-anchor").textContent = `Your export's own two numbers for each variant: the price, and the compare-at it is listed under. ${n(s.below)} of ${n(s.priced)} live variants (${share}) sit below their compare-at. ` +
    (s.policy
      ? "When most of the catalogue sits there, the compare-at stops being a sale and becomes a price no customer is shown, and the gap is margin decided in advance. The gap is your two numbers subtracted; what it costs you depends on whether anyone would pay the compare-at, so it is an estimate. One export cannot say how long the prices have sat there; that is the question for the call."
        + (t ? " A month is the gap on every unit of it your orders show, at their pace." : "")
      : "That is under half the catalogue, which reads as promotions rather than the price, so no gap is counted here.");
  $("head-anchor").innerHTML = `<tr><th>SKU</th><th>Product</th><th class="num">Price</th><th class="num">Compare-at</th><th class="num">The gap, a unit</th><th class="num">Under it by</th>${t ? '<th class="num">Units a month</th><th class="num">A month</th>' : ""}</tr>`;
  $("rows-anchor").innerHTML = s.anchors.slice(0, 20).map((a) => row([
    [esc(a.sku), "sku"], [esc(a.name), "name"], [cents(a.price), "num"], [cents(a.compare_at), "num"], [`${cents(a.per_unit)} est.`, "num"], [`${Math.round(a.share * 100)}%`, "num"],
    ...(t ? [[a.units_month.toFixed(1), "num"], [`${cents(a.month)} est.`, "num"]] : []),
  ])).join("") || row([[s.policy ? "No variant sits far enough below its compare-at to count." : "Not counted: under half the catalogue is below its compare-at.", ""]]);

  $("why-parcel").textContent = "USPS Ground Advantage bills anything over a pound at the next whole pound, so a parcel a few tenths of an ounce over the line pays the heavier rate on every order. The weight is the one set on your own product, the one Shopify hands the carrier; if your shipping settings add a box's weight, the parcel is heavier than this. A range across zones 1 to 8, because only your orders show your zone mix: an estimate."
    + (t ? " A month counts your orders of one unit of the variant alone, the parcels that weigh what it weighs; an order of several is a different parcel." : "");
  $("head-parcel").innerHTML = `<tr><th>SKU</th><th>Product</th><th class="num">Weight</th><th class="num">Over the line by</th><th>Bills at, not</th><th class="num">A parcel, nearest zone to farthest</th>${t ? '<th class="num">Parcels a month</th><th class="num">A month</th>' : ""}</tr>`;
  $("rows-parcel").innerHTML = s.parcels.slice(0, 20).map((p) => row([
    [esc(p.sku), "sku"], [esc(p.name), "name"], [`${p.weight_oz.toFixed(2)} oz`, "num"], [`${p.over_by} oz`, "num"], [`${esc(p.band_above)}, not ${esc(p.band_below)}`],
    [p.priced ? `${cents(p.low)}–${cents(p.high)} est.` : "not on the loaded card", "num"],
    ...(t ? [[p.parcels_month.toFixed(1), "num"], [p.priced ? `${cents(p.month_low)}–${cents(p.month_high)} est.` : "–", "num"]] : []),
  ])).join("") || row([["No parcel sits within 3 oz over a pound line.", ""]]);

  // What each variant keeps a unit, and the ROAS at which an ad sale keeps nothing.
  const pay = s.payments, b = s.cost_bases;
  const lines = [];
  if (!s.margins.length) {
    lines.push("Type a landed cost above, fill in Cost per item in Shopify before you export, or drop a cost file, to see what each variant keeps and the return on ad spend it needs to break even.");
  } else {
    lines.push(`Kept a unit is the price, less Shopify Payments' standard online card fee of ${(pay.rate * 100).toFixed(1)}% + ${Math.round(pay.fixed * 100)}¢ and your cost, before postage and ads. The fee is an estimate: it is the Basic plan's rate; Grow, Advanced and Plus pay less, and another processor charges its own.`
      + (o ? " The 30¢ is shared across the units of each order, as your orders show." : " The 30¢ is counted on every unit, as if every order were one unit."));
    lines.push(`Break-even ROAS is the return an ad must bring before the sale keeps nothing: the price over what it keeps. Across these variants, ${s.catalogue_roas_basis === "sales" ? "weighted by your sales" : "one unit of each"}, it is ${roasText(s.catalogue_roas)}; an ad returning less loses money on the sale.`);
    const bases = [b.cost_per_item ? `${n(b.cost_per_item)} at the Cost per item in your export (the unit cost alone: freight and packaging are not in it)` : null,
      b.yours ? `${n(b.yours)} at their own cost from your file` : null,
      b.assumed ? `${n(b.assumed)} at the ${costPct}% of price you typed, an estimate` : null].filter(Boolean);
    lines.push(`Costs: ${bases.join("; ")}.` + (s.no_cost ? ` ${n(s.no_cost)} variant${s.no_cost === 1 ? " has" : "s have"} no cost yet, so ${s.no_cost === 1 ? "it is" : "they are"} left out.` : ""));
    if (t) lines.push("A month is your sales after refunds, less the same fee and your cost on every unit sold, at your orders' pace: an estimate.");
    lines.push("This break-even counts the first order alone. A customer who orders again makes the same ad worth more; the full read checks for that in six months of your orders, and counts it only where it predicts your own last quarter.");
  }
  $("why-keep").textContent = lines.join(" ");
  $("head-keep").innerHTML = s.margins.length ? `<tr><th>SKU</th><th>Product</th><th class="num">Price</th><th class="num">Shopify Payments, a unit</th><th class="num">Cost</th><th class="num">Kept a unit</th><th class="num">Break-even ROAS</th>${t ? '<th class="num">Units a month</th><th class="num">Kept a month</th>' : ""}</tr>` : "";
  const BASIS = { yours: "your cost", cost_per_item: "Cost per item", assumed: "est. from your %" };
  $("rows-keep").innerHTML = s.margins.slice(0, 25).map((m) => row([
    [esc(m.sku), "sku"], [esc(m.name), "name"], [cents(m.price), "num"], [`${cents(m.fee)}<span class="basis">estimate</span>`, "num"],
    [`${cents(m.cost)}<span class="basis">${BASIS[m.cost_basis]}</span>`, "num"],
    [`${m.contribution < 0 ? "−" : ""}${cents(Math.abs(m.contribution))}<span class="basis">estimate</span>`, "num"],
    [m.roas != null ? `${m.roas.toFixed(2)}<span class="basis">estimate</span>` : "none: it keeps nothing", "num"],
    ...(t ? [[m.units_month.toFixed(1), "num"], [`${m.kept_month < 0 ? "−" : ""}${usd(Math.abs(m.kept_month))}<span class="basis">estimate</span>`, "num"]] : []),
  ])).join("");
}

fetch("/ratecard.json").then((r) => r.json()).then((j) => { rc = j; draw(); });
