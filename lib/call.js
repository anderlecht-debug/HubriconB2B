/**
 * The call: a prospect's own Seller Central reports, read in their own browser, and
 * the leaks only their data shows, priced in front of them (HUBRICON_SPEC.md, "The
 * funnel" and "Customer experience": exports are opened live and the warm-only cliffs
 * computed, their own named dollars on the screen before they have paid a cent).
 *
 * Nothing here sends anything anywhere. The page reads the files with FileReader and
 * calls these pure functions; a refresh forgets everything.
 *
 * The arithmetic is the engine's, so the number on the call is the number the
 * Profit Record would count after a yes:
 *   - reading a report: engine/src/hubricon_engine/ingest/{readers,headers}.py, ported;
 *   - the aged-inventory surcharge and the low-inventory-level fee:
 *     models/inventory_econ.py and models/fee_schedule.py, ported;
 *   - fee edges on the catalogue: lib/fees.js (itself pinned to the engine);
 * and lib/call.test.mjs holds all of it to lib/call.golden.json, which
 * engine/scripts/call_golden.py writes by running the engine's own code.
 *
 * Two figures are the call's own, and say so: the cliff at the next monthly snapshot
 * (from Amazon's own estimate for the 241-270 day band, the learn spreadsheet's rule)
 * and break-even ACoS from Amazon's own fee estimates in the Fee Preview report.
 *
 * Break-even takes a landed cost per SKU from a cost file where one is given (the COGS
 * template, read the way ingest/cogs.py reads it and added up the way models/margin.py
 * adds it), and the typed % of price for every other SKU; each row says which.
 *
 * A Shopify seller drops the Products export instead: the compare-at gap and the parcel
 * just past a pound line are lib/fees.js's own anchorGap and carrierBandEdge (the cold
 * engine's Shopify detectors, ported), with the catalogue's discount share read from the
 * whole export. The export carries no sales, so these stay per unit and per parcel.
 */
import * as fees from "./fees.js";

// -- reading a report (ingest/readers.py, ingest/headers.py) -------------------------

export const normalize = (h) => String(h).toLowerCase().replace(/﻿/g, "").replace(/[^a-z0-9]/g, "");

/** 'US$1,234.56', '$1,234.56', '1.234,56', '(12.34)' → number; blanks and n/a → null. */
export function cleanMoney(value) {
  let v = String(value ?? "").trim();
  if (!v || ["n/a", "na", "-", "--"].includes(v.toLowerCase())) return null;
  const negative = v.startsWith("(") && v.endsWith(")");
  v = v.replace(/^\(+|\)+$/g, "").replace(/[^\d.,-]/g, "");
  if (!v) return null;
  if (v.includes(",") && v.includes(".")) {
    v = v.lastIndexOf(".") > v.lastIndexOf(",") ? v.replace(/,/g, "") : v.replace(/\./g, "").replace(",", ".");
  } else if (v.includes(",")) {
    v = /^-?\d+,\d{1,2}$/.test(v) ? v.replace(",", ".") : v.replace(/,/g, "");
  }
  if (!/^-?(\d+\.?\d*|\.\d+)$/.test(v)) return null;
  const n = Number(v);
  return Number.isFinite(n) ? (negative ? -n : n) : null;
}
export const cleanInt = (v) => { const n = cleanMoney(v); return n == null ? null : Math.round(n); };
export const cleanPct = (v) => cleanMoney(String(v ?? "").replace("%", ""));
export const cleanStr = (v) => { const s = String(v ?? "").trim(); return s || null; };
export function cleanBool(v) {
  const s = String(v ?? "").trim().toLowerCase();
  if (["yes", "y", "true", "t", "1"].includes(s)) return true;
  if (["no", "n", "false", "f", "0"].includes(s)) return false;
  return null;
}

const DELIMITERS = [",", "\t", ";"];
function detectDelimiter(line) {
  let best = ",", n = 0;
  for (const d of DELIMITERS) { const c = line.split(d).length - 1; if (c > n) { n = c; best = d; } }
  return best;
}

/** One line split quote-aware (a quoted field may hold the delimiter). */
function splitLine(line, d) {
  const out = []; let cur = "", q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) {
      if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === d) { out.push(cur); cur = ""; } else cur += ch;
  }
  out.push(cur);
  return out;
}

/** The header is the first line in the top 20 with 3+ fields whose count matches the
 *  modal count of the next five non-blank lines; else the first 3+ field line. A cost
 *  file may be two columns (a sku and a landed cost), so its floor is 2. */
function findHeader(lines, minFields = 3) {
  const nonblank = lines.map((l, i) => [l, i]).filter(([l]) => l.trim()).map(([, i]) => i);
  let fallback = null;
  for (let pos = 0; pos < nonblank.length; pos++) {
    const i = nonblank[pos];
    if (i >= 20) break;
    const d = detectDelimiter(lines[i]);
    const n = splitLine(lines[i], d).length;
    if (n < minFields) continue;
    if (fallback == null) fallback = i;
    const following = nonblank.slice(pos + 1, pos + 6);
    if (following.length) {
      const counts = new Map();
      for (const j of following) { const c = splitLine(lines[j], d).length; counts.set(c, (counts.get(c) || 0) + 1); }
      const modal = [...counts.entries()].sort((a, b) => b[1] - a[1] || [...counts.keys()].indexOf(a[0]) - [...counts.keys()].indexOf(b[0]))[0][0];
      if (modal === n) return i;
    }
  }
  if (fallback == null) throw new Error("No header row in the first 20 lines: is this the right report?");
  return fallback;
}

/** Text → { headers, rows } with every value a string, the way read_table returns it. */
export function readTable(text, minFields = 3) {
  const clean = String(text).replace(/^﻿/, "");
  const lines = clean.split(/\r\n|\n|\r/);
  const h = findHeader(lines, minFields);
  const d = detectDelimiter(lines[h]);
  // A full parse from the header down, so a quoted field may even span lines.
  const body = lines.slice(h).join("\n");
  const records = []; let row = [], cur = "", q = false;
  for (let i = 0; i < body.length; i++) {
    const ch = body[i];
    if (q) {
      if (ch === '"') { if (body[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === d) { row.push(cur); cur = ""; }
    else if (ch === "\n") { row.push(cur); records.push(row); row = []; cur = ""; }
    else cur += ch;
  }
  if (cur !== "" || row.length) { row.push(cur); records.push(row); }
  const headers = records.shift().map((s) => String(s));
  const rows = records.filter((r) => r.some((c) => String(c).trim() !== "")).map((r) => Object.fromEntries(headers.map((k, i) => [k, r[i] ?? ""])));
  if (!rows.length) throw new Error("The file has a header but no rows.");
  return { headers, rows };
}

/** spec: canonical → [synonyms, cleaner, required]; returns canonical rows (headers.map_columns). */
export function mapColumns({ headers, rows }, spec) {
  const byNorm = new Map();
  for (const hd of headers) if (!byNorm.has(normalize(hd))) byNorm.set(normalize(hd), hd);
  const source = {}, missing = [];
  for (const [canonical, [synonyms, , required]] of Object.entries(spec)) {
    source[canonical] = synonyms.map((s) => byNorm.get(s)).find(Boolean) ?? null;
    if (!source[canonical] && required) missing.push(canonical);
  }
  if (missing.length) throw new Error(`This doesn't look like the right report: no ${missing.join(", ")} column.`);
  return rows.map((r) => Object.fromEntries(Object.entries(spec).map(([c, [, clean]]) => [c, source[c] ? clean(r[source[c]]) : null])));
}

// -- the reports --------------------------------------------------------------------

/** Manage Inventory Health / Inventory Age (ingest/inventory_health.py SPEC, the columns the call reads). */
export const INVENTORY_HEALTH = {
  sku: [["sku", "msku", "sellersku", "merchantsku"], cleanStr],
  fnsku: [["fnsku"], cleanStr],
  asin: [["asin"], cleanStr],
  product_name: [["productname", "title", "itemname"], cleanStr],
  available: [["available", "availablequantity", "fulfillablequantity", "afnfulfillablequantity", "sellable"], cleanInt],
  inv_age_0_to_90: [["invage0to90days", "inventoryage0to90days", "0to90days"], cleanInt],
  inv_age_91_to_180: [["invage91to180days", "inventoryage91to180days", "91to180days"], cleanInt],
  inv_age_181_to_270: [["invage181to270days", "inventoryage181to270days", "181to270days"], cleanInt],
  inv_age_271_to_365: [["invage271to365days", "inventoryage271to365days", "271to365days"], cleanInt],
  inv_age_365_plus: [["invage365plusdays", "inventoryage365plusdays", "365plusdays", "invage365days"], cleanInt],
  units_shipped_t30: [["unitsshippedt30", "unitsshippedlast30days", "unitsshipped30days"], cleanInt],
  item_volume: [["itemvolume", "itemvolumecubicfeet"], cleanMoney],
  storage_volume: [["storagevolume", "totalstoragevolume", "storagevolumecubicfeet"], cleanMoney],
  ais_181_210: [["estimatedais181210days"], cleanMoney],
  ais_211_240: [["estimatedais211240days"], cleanMoney],
  ais_241_270: [["estimatedais241270days"], cleanMoney],
  ais_271_300: [["estimatedais271300days"], cleanMoney],
  ais_301_330: [["estimatedais301330days"], cleanMoney],
  ais_331_365: [["estimatedais331365days"], cleanMoney],
  ais_365_plus: [["estimatedais365plusdays"], cleanMoney],
  low_inventory_level_fee_applied: [["lowinventorylevelfeeapplied", "lowinventorylevelfee"], cleanBool],
  storage_type: [["storagetype", "sizetier"], cleanStr],
  your_price: [["yourprice"], cleanMoney],
};
const AIS = ["ais_181_210", "ais_211_240", "ais_241_270", "ais_271_300", "ais_301_330", "ais_331_365", "ais_365_plus"];
const round2 = (x) => Math.round(x * 100) / 100;

/** The parsed rows, as ingest/inventory_health.parse keeps them: SKU or FNSKU, the last row per SKU. */
export function parseInventoryHealth(text) {
  const mapped = mapColumns(readTable(text), INVENTORY_HEALTH);
  const bySku = new Map();
  for (const r of mapped) {
    const sku = r.sku || r.fnsku;
    if (!sku) continue;
    const surcharges = AIS.map((k) => r[k]).filter((v) => v != null);
    bySku.set(sku, { ...r, sku, estimated_aged_surcharge: surcharges.length ? round2(surcharges.reduce((a, b) => a + b, 0)) : null });
  }
  return [...bySku.values()];
}

/** Fee Preview (Reports, Fulfillment): Amazon's own measurement and fee estimate per SKU. */
export const FEE_PREVIEW = {
  sku: [["sku", "sellersku", "msku"], cleanStr, true],
  asin: [["asin"], cleanStr],
  product_name: [["productname", "title", "itemname"], cleanStr],
  product_group: [["productgroup", "category"], cleanStr],
  your_price: [["yourprice", "price"], cleanMoney],
  sales_price: [["salesprice"], cleanMoney],
  longest_side: [["longestside"], cleanMoney],
  median_side: [["medianside"], cleanMoney],
  shortest_side: [["shortestside"], cleanMoney],
  unit_of_dimension: [["unitofdimension"], cleanStr],
  item_package_weight: [["itempackageweight", "itemweight"], cleanMoney],
  unit_of_weight: [["unitofweight"], cleanStr],
  product_size_tier: [["productsizetier", "sizetier"], cleanStr],
  referral_fee: [["estimatedreferralfeeperunit", "referralfeeperunit", "estimatedreferralfee"], cleanMoney],
  fulfilment_fee: [["expectedfulfillmentfeeperunit", "expecteddomesticfulfilmentfeeperunit", "expecteddomesticfulfillmentfeeperunit", "estimatedfulfillmentfeeperunit", "fbafee"], cleanMoney],
  fee_total: [["estimatedfeetotal"], cleanMoney],
};

const OZ_PER = { pounds: 16, pound: 16, lb: 16, lbs: 16, ounces: 1, ounce: 1, oz: 1, kilograms: 35.274, kilogram: 35.274, kg: 35.274, grams: 0.035274, gram: 0.035274, g: 0.035274 };
const IN_PER = { inches: 1, inch: 1, in: 1, centimeters: 1 / 2.54, centimetres: 1 / 2.54, cm: 1 / 2.54, millimeters: 1 / 25.4, mm: 1 / 25.4 };

export function parseFeePreview(text) {
  return mapColumns(readTable(text), FEE_PREVIEW).filter((r) => r.sku).map((r) => {
    const wu = OZ_PER[String(r.unit_of_weight || "pounds").toLowerCase()] ?? 16;
    const du = IN_PER[String(r.unit_of_dimension || "inches").toLowerCase()] ?? 1;
    const sides = [r.longest_side, r.median_side, r.shortest_side];
    return {
      ...r,
      price: r.sales_price ?? r.your_price,
      weight_oz: r.item_package_weight != null ? Math.round(r.item_package_weight * wu * 1000) / 1000 : null,
      dims_in: sides.every((s) => s > 0) ? sides.map((s) => Math.round(s * du * 100) / 100) : null,
    };
  });
}

/** Sponsored Products campaign report (ingest/ppc_campaign.py SPEC): spend and sales over its dates. */
export const PPC_CAMPAIGN = {
  report_date: [["date", "startdate", "day"], cleanStr],
  campaign_name: [["campaignname", "campaign"], cleanStr, true],
  spend: [["spend", "cost", "totalspend"], cleanMoney, true],
  sales: [["7daytotalsales", "14daytotalsales", "sales", "totalsales"], cleanMoney],
};

export function parsePpcCampaign(text) {
  const rows = mapColumns(readTable(text), PPC_CAMPAIGN);
  const spend = rows.reduce((a, r) => a + (r.spend || 0), 0);
  const sales = rows.reduce((a, r) => a + (r.sales || 0), 0);
  const days = new Set(rows.map((r) => r.report_date).filter(Boolean));
  return { spend: round2(spend), sales: round2(sales), days: days.size || null, campaigns: new Set(rows.map((r) => r.campaign_name)).size };
}

// -- the schedule (models/fee_schedule.py, EFFECTIVE 2026-01-15) ----------------------

export const SCHEDULE = {
  effective: "2026-01-15",
  storage_per_cuft: { standard: { offpeak: 0.78, peak: 2.40 }, oversize: { offpeak: 0.56, peak: 1.40 } },
  aged_per_cuft: [[181, 210, 0.50], [211, 240, 1.00], [241, 270, 1.50], [271, 300, 5.45], [301, 330, 5.70], [331, 365, 5.90], [366, 1e6, 6.90]],
  low_inventory_fee: { standard: { lt14: 0.89, "14to21": 0.63, "21to28": 0.32 }, oversize: { lt14: 2.09, "14to21": 1.14, "21to28": 0.72 } },
  low_inventory_days: 28,
  default_item_volume_cuft: { standard: 0.08, oversize: 1.20 },
};
/** models/inventory_econ.py BUCKET_MID_AGE: the age each export bucket is priced at. */
export const BUCKET_MID_AGE = { inv_age_181_to_270: 225, inv_age_271_to_365: 318, inv_age_365_plus: 400 };

export function agedRate(age) {
  for (const [lo, hi, r] of SCHEDULE.aged_per_cuft) if (lo <= age && age <= hi) return r;
  return 0;
}
export function lowInventoryRate(dos, tier = "standard") {
  const t = SCHEDULE.low_inventory_fee[tier] || SCHEDULE.low_inventory_fee.standard;
  if (dos >= SCHEDULE.low_inventory_days) return 0;
  if (dos < 14) return t.lt14;
  if (dos < 21) return t["14to21"];
  return t["21to28"];
}
const tierOf = (r) => (String(r.storage_type || "").toLowerCase().startsWith("over") ? "oversize" : "standard");

/** Cubic feet per unit, as inventory_econ.run finds it. */
export function cubicFeet(r) {
  if (r.item_volume != null) return { cuft: r.item_volume, assumed: false };
  if (r.storage_volume && r.available) return { cuft: r.storage_volume / r.available, assumed: false };
  return { cuft: SCHEDULE.default_item_volume_cuft.standard, assumed: true };
}

/** This month's aged-inventory surcharge for one SKU: Amazon's own estimate when the
 *  report carries it, else the schedule at each bucket's mid-age (inventory_econ.run). */
export function agedSurcharge(r) {
  const aged = (r.inv_age_181_to_270 || 0) + (r.inv_age_271_to_365 || 0) + (r.inv_age_365_plus || 0);
  if (r.estimated_aged_surcharge != null) return { month: round2(r.estimated_aged_surcharge), basis: "amazon", aged_units: aged };
  if (!aged) return { month: 0, basis: "none", aged_units: 0 };
  const { cuft, assumed } = cubicFeet(r);
  const month = Object.entries(BUCKET_MID_AGE).reduce((a, [k, age]) => a + (r[k] || 0) * cuft * agedRate(age), 0);
  return { month: round2(month), basis: "schedule", aged_units: aged, cuft, volume_assumed: assumed };
}

/** The step at the next monthly snapshot: the units Amazon now prices in the 241-270 day
 *  band are 271-300 days old a month on, and their surcharge goes from $1.50 to $5.45 a
 *  cubic foot, unless they sell first. Amazon's own band estimate, scaled by the two rates. */
export function cliffAhead(r) {
  if (r.ais_241_270 == null) return null;
  const before = agedRate(255), after = agedRate(285);
  return { month: round2(r.ais_241_270 * (after - before) / before), from: r.ais_241_270, ratio: after / before };
}

/** The low-inventory-level fee at the last 30 days' pace: days of supply = available ÷
 *  units shipped a day; per unit shipped by the schedule, as inventory_econ.run prices it. */
export function lowInventoryFee(r) {
  const t30 = r.units_shipped_t30 || 0;
  if (!t30 || r.available == null) return { month: 0, dos: null, rate: 0, applied_per_amazon: r.low_inventory_level_fee_applied };
  const daily = t30 / 30, dos = r.available / daily, tier = tierOf(r);
  const rate = lowInventoryRate(dos, tier);
  return { month: round2(rate * daily * 30), dos: Math.round(dos * 10) / 10, rate, tier, applied_per_amazon: r.low_inventory_level_fee_applied };
}

// -- the catalogue, from Fee Preview ---------------------------------------------------

/** Fee edges on one SKU (lib/fees.js detect on Amazon's own measurement), priced at its real units. */
export function feeEdges(rc, f, unitsMonth, today) {
  if (!f.price || !f.weight_oz || !f.dims_in) return [];
  const item = fees.describeItem(rc, { price: f.price, category: f.product_group, itemWeightOz: f.weight_oz, dims: f.dims_in });
  return fees.detect(rc, item, today).map((x) => ({
    kind: x.kind, per_unit: x.perUnitLow, month: unitsMonth ? round2(x.perUnitLow * unitsMonth) : null, evidence: x.evidence,
  }));
}

/** Break-even ad cost of sale from Amazon's own fee estimates and a landed cost. */
export function breakEven(f, cost) {
  if (!f.price || f.referral_fee == null || f.fulfilment_fee == null || cost == null) return null;
  const contribution = f.price - f.referral_fee - f.fulfilment_fee - cost;
  return { price: f.price, amazon_fees: round2(f.referral_fee + f.fulfilment_fee), cost: round2(cost), contribution: round2(contribution), acos: contribution / f.price };
}

// -- the landed cost per SKU, from a cost file ------------------------------------------

/** cogs-template.csv (ingest/cogs.py SPEC), or any CSV with a sku and a landed cost, or a
 *  Shopify Products export's own Cost per item. */
export const COST_FILE = {
  sku: [["sku", "sellersku", "msku", "merchantsku", "variantsku"], cleanStr],
  landed: [["landedcost", "landedcostusd", "landedcostperunit", "landedcostperunitusd", "landedunitcost", "unitlandedcost", "cogs", "cogsusd", "cogsperunit"], cleanMoney],
  unit_cost_usd: [["unitcostusd", "unitcost", "costperitem", "variantcost", "cost"], cleanMoney],
  inbound_freight_per_unit_usd: [["inboundfreightperunitusd", "freightperunit"], cleanMoney],
  packaging_per_unit_usd: [["packagingperunitusd", "packagingperunit"], cleanMoney],
  fulfillment_per_unit_usd: [["fulfillmentperunitusd", "fulfillmentperunit", "pickpackpostageperunit", "shippingperunitusd", "shippingperunit"], cleanMoney],
  other_cost_per_unit_usd: [["othercostperunitusd", "otherperunit"], cleanMoney],
};
/** The template's own example row (ingest/cogs.py EXAMPLE_SKUS): never a cost. */
export const EXAMPLE_SKUS = new Set(["EXAMPLE-001"]);
/** What a unit costs landed, as models/margin.py adds it up: the unit and every per-unit cost beside it. */
const COST_PARTS = ["unit_cost_usd", "inbound_freight_per_unit_usd", "packaging_per_unit_usd", "fulfillment_per_unit_usd", "other_cost_per_unit_usd"];

/** → { bySku: { sku: landed cost }, skus, example } ; a stated landed-cost column wins over the parts. */
export function parseCostFile(text) {
  const table = readTable(text, 2);
  const has = new Set(table.headers.map(normalize));
  const seen = (k) => COST_FILE[k][0].some((s) => has.has(s));
  if (!seen("sku") || !(seen("landed") || seen("unit_cost_usd"))) {
    throw new Error("This doesn't look like a cost file: it needs a sku column and a landed cost (or unit_cost_usd, as in the template).");
  }
  const bySku = Object.create(null);
  let example = 0;
  for (const r of mapColumns(table, COST_FILE)) {
    if (!r.sku) continue;
    if (EXAMPLE_SKUS.has(r.sku)) { example += 1; continue; }
    const cost = r.landed ?? (r.unit_cost_usd != null ? COST_PARTS.reduce((a, k) => a + (r[k] || 0), 0) : null);
    if (cost != null && cost >= 0) bySku[r.sku] = round2(cost);
  }
  const skus = Object.keys(bySku).length;
  if (!skus) throw new Error(example ? "Only the template's example row is filled in: add a row for each of your SKUs." : "No SKU in this file states a cost.");
  return { bySku, skus, example };
}

// -- Shopify: the Products export --------------------------------------------------------

/** Shopify Admin, Products, Export (ingest/shopify_products.py SPEC, plus the compare-at it does not keep). */
export const SHOPIFY_PRODUCTS = {
  handle: [["handle"], cleanStr, true],
  title: [["title"], cleanStr],
  option1_value: [["option1value"], cleanStr],
  option2_value: [["option2value"], cleanStr],
  option3_value: [["option3value"], cleanStr],
  sku: [["variantsku", "sku"], cleanStr],
  grams: [["variantgrams"], cleanMoney],
  price: [["variantprice"], cleanMoney, true],
  compare_at: [["variantcompareatprice", "compareatprice"], cleanMoney],
  cost: [["costperitem", "variantcost", "cost"], cleanMoney],
  status: [["status"], cleanStr],
};
const GRAMS_PER_OZ = 28.349523125;
const DEFAULT_OPTION = "Default Title";   // Shopify's placeholder on a single-variant product

/** shopify_products.product_name: the title, and the options that are not the placeholder. */
export function productName(title, options) {
  const values = options.filter((v) => v && v !== DEFAULT_OPTION);
  if (!title) return values.join(" / ") || null;
  return values.length ? `${title} — ${values.join(" / ")}` : title;
}

/** One row per variant that has a price. Title and status sit on a product's first line only,
 *  so they are carried down by Handle; an image-only line has no price and is skipped. */
export function parseShopifyProducts(text) {
  const products = new Map();
  const out = [];
  for (const r of mapColumns(readTable(text), SHOPIFY_PRODUCTS)) {
    if (!r.handle) continue;
    const p = products.get(r.handle) || { title: null, status: null };
    if (!p.title && r.title) p.title = r.title;
    if (!p.status && r.status) p.status = r.status;
    products.set(r.handle, p);
    if (r.price == null) continue;
    const name = productName(p.title, [r.option1_value, r.option2_value, r.option3_value]);
    out.push({
      sku: r.sku || name || r.handle, has_sku: Boolean(r.sku), handle: r.handle, name, status: p.status,
      price: r.price, compare_at: r.compare_at, cost: r.cost,
      weight_oz: r.grams > 0 ? Math.round((r.grams / GRAMS_PER_OZ) * 100) / 100 : null,
    });
  }
  if (!out.length) throw new Error("No variant in this export has a price: is it Shopify's Products export?");
  return out;
}

/** The Shopify reading: lib/fees.js's own anchorGap and carrierBandEdge on every live variant,
 *  with the catalogue's discount share read from the whole export rather than guessed. */
export function analyseShopify(rc, variants) {
  const live = variants.filter((v) => !/^(draft|archived)$/i.test(v.status || ""));
  const priced = live.filter((v) => v.price > 0);
  const below = priced.filter((v) => v.compare_at > v.price);
  const share = priced.length ? Math.round((below.length / priced.length) * 1000) / 1000 : null;
  const anchors = [], parcels = [];
  for (const v of priced) {
    const item = fees.describeShopifyItem(rc, { price: v.price, compareAtPrice: v.compare_at, weightOz: v.weight_oz });
    const gap = fees.anchorGap(item, share);
    if (gap) anchors.push({ sku: v.sku, name: v.name, price: v.price, compare_at: v.compare_at, per_unit: gap.perUnitLow, share: gap.evidence.discountShare });
    const edge = fees.carrierBandEdge(rc, item);
    if (edge) {
      const e = edge.evidence;
      parcels.push({ sku: v.sku, name: v.name, weight_oz: v.weight_oz, edge: e.edge, over_by: e.overByOz, band_below: e.bandBelow, band_above: e.bandAbove,
        low: edge.perUnitLow, high: edge.perUnitHigh, priced: edge.perUnitHigh > 0 });
    }
  }
  const pricedParcels = parcels.filter((p) => p.priced);
  return {
    variants: variants.length, live: live.length, priced: priced.length, below: below.length, catalogue_share: share,
    policy: share != null && share >= fees.CATALOGUE_DISCOUNT_SHARE,
    anchors: anchors.sort((a, b) => b.per_unit - a.per_unit),
    gap_mean: anchors.length ? round2(anchors.reduce((a, x) => a + x.per_unit, 0) / anchors.length) : null,
    parcels: parcels.sort((a, b) => b.high - a.high || a.over_by - b.over_by),
    parcel_low: pricedParcels.length ? Math.min(...pricedParcels.map((p) => p.low)) : null,
    parcel_high: pricedParcels.length ? Math.max(...pricedParcels.map((p) => p.high)) : null,
    no_weight: priced.filter((v) => !v.weight_oz).length,
  };
}

/** Everything the call shows, from whatever reports were dropped. */
export function analyse(rc, { inventory = [], feePreview = [], ppc = null, costShare = null, costBySku = {}, targetAcos = null, today = new Date() } = {}) {
  const units = new Map(inventory.map((r) => [r.sku, r.units_shipped_t30 || 0]));
  const aged = inventory.map((r) => ({ sku: r.sku, name: r.product_name, ...agedSurcharge(r), cliff: cliffAhead(r) })).filter((x) => x.month > 0 || (x.cliff && x.cliff.month > 0));
  const low = inventory.map((r) => ({ sku: r.sku, name: r.product_name, ...lowInventoryFee(r) })).filter((x) => x.month > 0);
  const edges = [], margins = [];
  for (const f of feePreview) {
    const found = feeEdges(rc, f, units.get(f.sku) ?? null, today);
    if (found.length) {
      const best = found.reduce((a, b) => (b.per_unit > a.per_unit ? b : a));
      edges.push({ sku: f.sku, name: f.product_name, units: units.get(f.sku) ?? null, ...best, all: found });
    }
    const cost = costBySku[f.sku] ?? (costShare != null && f.price ? f.price * costShare : null);
    const be = breakEven(f, cost);
    if (be) margins.push({ sku: f.sku, name: f.product_name, units: units.get(f.sku) ?? null, cost_basis: costBySku[f.sku] != null ? "yours" : "assumed", ...be });
  }
  // The catalogue's break-even, weighted by sales where the units are known.
  const weighted = margins.filter((m) => m.units);
  const w = weighted.reduce((a, m) => a + m.units * m.price, 0);
  const catalogueBE = w ? weighted.reduce((a, m) => a + m.units * m.price * m.acos, 0) / w : (margins.length ? margins.reduce((a, m) => a + m.acos, 0) / margins.length : null);
  const ads = ppc && ppc.sales > 0 ? (() => {
    const acos = ppc.spend / ppc.sales, months = ppc.days ? ppc.days / 30 : 1;
    const over = catalogueBE != null ? Math.max(0, ppc.spend - ppc.sales * Math.max(catalogueBE, 0)) / months : null;
    return { spend: ppc.spend, sales: ppc.sales, acos, days: ppc.days, over_month: over != null ? round2(over) : null };
  })() : null;
  const sum = (xs, k) => round2(xs.reduce((a, x) => a + (x[k] || 0), 0));
  return {
    aged: aged.sort((a, b) => b.month - a.month), low: low.sort((a, b) => b.month - a.month),
    edges: edges.sort((a, b) => (b.month ?? 0) - (a.month ?? 0) || b.per_unit - a.per_unit),
    margins: margins.sort((a, b) => a.acos - b.acos), catalogue_be: catalogueBE, ads,
    target: targetAcos, over_target: targetAcos != null ? margins.filter((m) => m.acos < targetAcos) : [],
    totals: {
      aged: sum(aged, "month"), cliff: round2(aged.reduce((a, x) => a + (x.cliff?.month || 0), 0)), low: sum(low, "month"),
      edges: round2(edges.reduce((a, x) => a + (x.month || 0), 0)), ads: ads?.over_month ?? 0,
    },
  };
}
