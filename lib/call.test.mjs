// The call's arithmetic is the engine's: a Seller Central export read the way the
// ingest reads it, the aged-inventory surcharge and the low-inventory-level fee priced
// the way inventory_econ.run prices them (lib/call.golden.json, written by
// engine/scripts/call_golden.py running the engine's own code), and the schedule
// constants the same numbers as fee_schedule.py.
//   node --test lib/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as call from "./call.js";
import * as fees from "./fees.js";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const golden = JSON.parse(read("lib/call.golden.json"));
const rc = JSON.parse(read("ratecard.json"));
const close = (a, b, tol = 0.011) => (a == null || b == null ? a === b : Math.abs(a - b) <= tol);

test("money is cleaned the way the ingest cleans it", () => {
  for (const { args: [v], want } of golden.clean_money) assert.ok(close(call.cleanMoney(v), want, 1e-9), `${JSON.stringify(v)} → ${call.cleanMoney(v)}, engine ${want}`);
});

test("a report with a preamble finds its real header, as read_table does", () => {
  assert.deepEqual(call.readTable(golden.preamble.text).headers, golden.preamble.headers);
});

test("the Inventory Age export parses to the engine's rows", () => {
  const rows = call.parseInventoryHealth(golden.fixture);
  assert.equal(rows.length, golden.parsed.length);
  for (const want of golden.parsed) {
    const got = rows.find((r) => r.sku === want.sku);
    for (const [k, v] of Object.entries(want)) assert.ok(typeof v === "number" ? close(got[k], v, 1e-9) : got[k] === v, `${want.sku}.${k}: ${got[k]} vs engine ${v}`);
  }
});

test("the aged-inventory surcharge and the low-inventory fee are the engine's, both bases", () => {
  for (const [file, priced, basis] of [[golden.fixture, golden.priced_amazon, "amazon"], [golden.fixture_no_ais, golden.priced_schedule, "schedule"]]) {
    for (const r of call.parseInventoryHealth(file)) {
      const want = priced[r.sku];
      const a = call.agedSurcharge(r), l = call.lowInventoryFee(r);
      assert.ok(close(a.month, want.aged_surcharge_month), `${r.sku} aged ${a.month} vs engine ${want.aged_surcharge_month}`);
      if (want.aged_surcharge_month > 0) assert.equal(a.basis, basis);
      assert.ok(close(l.month, want.low_inventory_fee_month), `${r.sku} low ${l.month} vs engine ${want.low_inventory_fee_month}`);
    }
  }
});

test("the low-inventory fee is the engine's on Amazon's 30/90-day rule, its own columns and its exemptions", () => {
  // Amazon's own 30- and 90-day historical days of supply, and its exemption flag, in the report
  for (const r of call.parseInventoryHealth(golden.fixture_lilf)) {
    const want = golden.priced_lilf[r.sku], l = call.lowInventoryFee(r);
    assert.ok(close(l.month, want.low_inventory_fee_month), `${r.sku} low ${l.month} vs engine ${want.low_inventory_fee_month}`);
    assert.equal(l.rate, want.low_inventory_fee_rate, `${r.sku} rate`);
    assert.equal(l.exempt, want.low_inventory_fee_exempt, `${r.sku} exempt`);
    assert.equal(l.basis, want.low_inventory_fee_basis, `${r.sku} basis`);
  }
  // the pace-based fee says which exemption it could check and names the ones it could not
  for (const r of call.parseInventoryHealth(golden.fixture)) {
    const want = golden.priced_amazon[r.sku], l = call.lowInventoryFee(r);
    assert.equal(l.basis, want.low_inventory_fee_basis, `${r.sku} basis`);
    assert.equal(l.tier, want.fee_size_tier, `${r.sku} tier`);
  }
  const k = golden.constants;
  assert.equal(call.LILF_UNMODELLED, k.lilf_unmodelled);
  assert.equal(call.SCHEDULE.low_inventory_min_units_t7, k.low_inventory_min_units_t7);
  assert.deepEqual(call.SCHEDULE.low_inventory_fee, k.low_inventory_fee);
  assert.deepEqual(call.SCHEDULE.low_inventory_assumed_tier, k.low_inventory_assumed_tier);
  for (const [field, synonyms] of Object.entries(k.synonyms)) assert.deepEqual(call.INVENTORY_HEALTH[field][0], synonyms, `${field} reads the engine's headers`);
});

test("the size tier comes from Fee Preview, priced on the engine's five rows", () => {
  for (const { args: [label, w], want } of golden.low_inventory_tier) assert.deepEqual(call.lowInventoryTier(label, w), want, `${label} at ${w} lb`);
  const inventory = call.parseInventoryHealth(golden.fixture);
  const feePreview = call.parseFeePreview(golden.fee_preview_tiers);
  const out = call.analyse(rc, { inventory, feePreview, today: "2026-09-08" });
  for (const r of inventory) {
    const want = golden.priced_tiers[r.sku];
    const l = call.lowInventoryFee(r, feePreview.find((f) => f.sku === r.sku) || null);
    assert.ok(close(l.month, want.low_inventory_fee_month), `${r.sku} low ${l.month} vs engine ${want.low_inventory_fee_month}`);
    assert.equal(l.tier, want.fee_size_tier, `${r.sku} tier`);
    assert.equal(l.basis, want.low_inventory_fee_basis, `${r.sku} basis`);
  }
  // WIDGET-RED at 4.10 lb is large standard, 3 to 20 lb: 16 days of supply, $0.87 a unit, 190 a month
  const red = out.low.find((x) => x.sku === "WIDGET-RED");
  assert.equal(red.tier, "large_standard_20lb");
  assert.ok(close(red.month, 0.87 * 190));
});

test("the schedule steps are the engine's", () => {
  for (const { args: [d, t], want } of golden.low_inventory_rate) assert.equal(call.lowInventoryRate(d, t), want, `${t} at ${d} days`);
  for (const { args: [a], want } of golden.aged_rate) assert.equal(call.agedRate(a), want, `day ${a}`);
  assert.deepEqual(call.BUCKET_MID_AGE, golden.constants.bucket_mid_age);
  assert.deepEqual(call.SCHEDULE.default_item_volume_cuft, golden.constants.default_volume);
  assert.equal(call.SCHEDULE.effective, golden.constants.effective);
  const py = read("engine/src/hubricon_engine/models/fee_schedule.py");
  for (const [lo, , r] of call.SCHEDULE.aged_per_cuft) assert.match(py, new RegExp(`\\(${lo}, [^,]+, ${r.toFixed(2)}\\)`), `aged ${lo} at ${r}`);
});

test("the cliff at the next snapshot: Amazon's 241-270 day estimate, scaled from $1.50 to $5.45", () => {
  const r = { ais_241_270: 15.0 };
  const c = call.cliffAhead(r);
  assert.ok(close(c.month, 15.0 * (5.45 - 1.5) / 1.5));
  assert.equal(call.cliffAhead({ ais_241_270: null }), null, "no estimate, no cliff figure");
});

test("Fee Preview: Amazon's measurement, in ounces and inches, and its fee estimates", () => {
  const rows = call.parseFeePreview(read("engine/tests/fixtures/fee_preview_clean.txt"));
  assert.equal(rows.length, 3);
  const blue = rows.find((r) => r.sku === "WIDGET-BLUE");
  assert.equal(blue.weight_oz, 13.12);
  assert.deepEqual(blue.dims_in, [9, 6, 2]);
  assert.equal(blue.price, 19.98);
  assert.equal(blue.fulfilment_fee, 4.76);
  assert.equal(blue.referral_fee, 3.0);
});

test("fee edges on the catalogue are lib/fees.js's own, priced at the real units", () => {
  const f = call.parseFeePreview(read("engine/tests/fixtures/fee_preview_clean.txt")).find((r) => r.sku === "WIDGET-BLUE");
  const found = call.feeEdges(rc, f, 310, "2026-09-08");
  const item = fees.describeItem(rc, { price: f.price, category: f.product_group, itemWeightOz: f.weight_oz, dims: f.dims_in });
  const direct = fees.detect(rc, item, "2026-09-08");
  assert.deepEqual(found.map((x) => x.kind), direct.map((x) => x.kind));
  assert.ok(close(found[0].month, direct[0].perUnitLow * 310));
});

test("break-even ACoS from Amazon's own fees and a landed cost", () => {
  const be = call.breakEven({ price: 20, referral_fee: 3, fulfilment_fee: 4.5 }, 5);
  assert.ok(close(be.acos, (20 - 3 - 4.5 - 5) / 20, 1e-9));
  assert.equal(call.breakEven({ price: 20, referral_fee: 3, fulfilment_fee: 4.5 }, null), null, "no cost, no break-even: never guessed silently");
});

test("a cost file is read the way ingest/cogs.py reads it and added up the way models/margin.py adds it", () => {
  const c = call.parseCostFile(read("engine/tests/fixtures/cogs_clean.csv"));
  assert.deepEqual({ ...c.bySku }, { "WIDGET-BLUE": 4.87, "WIDGET-RED": 4.82, "GADGET-PRO": 11.45 });   // unit + freight + packaging + other
  assert.equal(c.example, 1, "the template's example row is never a cost");
  assert.throws(() => call.parseCostFile(read("cogs-template.csv")), /Only the template's example row/);
  assert.throws(() => call.parseCostFile("sku,asin,notes\nA,B,C\nD,E,F\n"), /needs a sku column and a landed cost/);
  assert.deepEqual({ ...call.parseCostFile("SKU,Landed cost,unit_cost_usd\nA-1,7.25,3.00\nB-2,,4.00\n").bySku }, { "A-1": 7.25, "B-2": 4 }, "a stated landed cost wins over the parts");
  // Every column name the ingest accepts, the call accepts too.
  const py = read("engine/src/hubricon_engine/ingest/cogs.py");
  for (const field of ["sku", "unit_cost_usd", "inbound_freight_per_unit_usd", "packaging_per_unit_usd", "other_cost_per_unit_usd", "fulfillment_per_unit_usd"]) {
    const block = py.match(new RegExp(`"${field}": \\{\\s*"synonyms": \\[([^\\]]*)\\]`))[1];
    for (const [, syn] of block.matchAll(/"([^"]+)"/g)) assert.ok(call.COST_FILE[field][0].includes(syn), `${field}: ${syn}`);
  }
  const margin = read("engine/src/hubricon_engine/models/margin.py");
  for (const f of ["unit_cost_usd", "inbound_freight_per_unit_usd", "packaging_per_unit_usd", "fulfillment_per_unit_usd", "other_cost_per_unit_usd"]) assert.match(margin, new RegExp(`"${f}"`));
});

test("break-even takes a SKU's own cost where the file has one, and says which cost it used", () => {
  const feePreview = call.parseFeePreview(read("engine/tests/fixtures/fee_preview_clean.txt"));
  const costBySku = call.parseCostFile("sku,unit_cost_usd\nWIDGET-BLUE,5.00\n").bySku;
  const both = call.analyse(rc, { feePreview, costShare: 0.25, costBySku, today: "2026-09-08" });
  const blue = both.margins.find((m) => m.sku === "WIDGET-BLUE"), red = both.margins.find((m) => m.sku === "WIDGET-RED");
  assert.equal(blue.cost_basis, "yours");
  assert.equal(blue.cost, 5);
  assert.equal(red.cost_basis, "assumed");
  assert.ok(close(red.cost, 19.95 * 0.25));
  const fileOnly = call.analyse(rc, { feePreview, costBySku, today: "2026-09-08" });
  assert.deepEqual(fileOnly.margins.map((m) => m.sku), ["WIDGET-BLUE"], "no % typed: only the SKUs with their own cost, never a guess");
});

test("the Shopify Products export is read the way ingest/shopify_products.py reads it", () => {
  const v = call.parseShopifyProducts(read("engine/tests/fixtures/shopify_products_clean.csv"));
  assert.deepEqual(v.map((x) => x.sku), ["WIDGET-BLUE", "WIDGET-RED", "GADGET-PRO"], "the image-only line is skipped");
  assert.deepEqual(v.map((x) => x.name), ["Widget — Blue", "Widget — Red", "Gadget Pro"], "product_name, with Shopify's Default Title left out");
  assert.equal(v[1].status, "active", "status rides down from the product's first line");
  assert.equal(v[0].compare_at, 24.99);
  assert.equal(v[0].weight_oz, 8.82);                                    // 250 g
  const py = read("engine/src/hubricon_engine/ingest/shopify_products.py");
  for (const field of ["handle", "title", "sku", "grams", "price", "cost", "status"]) {
    const block = py.match(new RegExp(`"${field}": \\{"synonyms": \\[([^\\]]*)\\]`))[1];
    for (const [, syn] of block.matchAll(/"([^"]+)"/g)) assert.ok(call.SHOPIFY_PRODUCTS[field][0].includes(syn), `${field}: ${syn}`);
  }
  assert.equal(call.analyseShopify(rc, v).policy, false, "a third of the catalogue under its compare-at is a promotion");
  assert.deepEqual(call.analyseShopify(rc, v).anchors, []);
});

test("the Shopify reading is lib/fees.js's own anchorGap and carrierBandEdge, on every live variant", () => {
  const csv = [
    "Handle,Title,Option1 Value,Variant SKU,Variant Grams,Variant Price,Variant Compare At Price,Status",
    "mug,Mug,Sand,MUG-SAND,470,28.00,36.00,active",
    "mug,,Slate,MUG-SLATE,470,28.00,36.00,",
    "kettle,Kettle,Default Title,KETTLE-1,935,64.00,79.00,active",
    "board,Board,Default Title,BOARD-1,1290,48.00,,active",
    "set,Gift Set,Default Title,SET-1,470,89.00,110.00,draft",
  ].join("\n");
  const s = call.analyseShopify(rc, call.parseShopifyProducts(csv));
  assert.equal(s.priced, 4, "a draft is not on sale");
  assert.equal(s.below, 3);
  assert.equal(s.catalogue_share, 0.75);
  for (const a of s.anchors) {
    const v = call.parseShopifyProducts(csv).find((x) => x.sku === a.sku);
    const direct = fees.anchorGap(fees.describeShopifyItem(rc, { price: v.price, compareAtPrice: v.compare_at, weightOz: v.weight_oz }), 0.75);
    assert.equal(a.per_unit, direct.perUnitLow, a.sku);
  }
  assert.deepEqual(s.anchors.map((a) => [a.sku, a.per_unit]), [["KETTLE-1", 15], ["MUG-SAND", 8], ["MUG-SLATE", 8]]);
  const mug = s.parcels.find((p) => p.sku === "MUG-SAND");
  const direct = fees.carrierBandEdge(rc, fees.describeShopifyItem(rc, { price: 28, weightOz: 16.58 }));
  assert.equal(mug.edge, 16);
  assert.deepEqual([mug.low, mug.high], [direct.perUnitLow, direct.perUnitHigh]);
  assert.ok(mug.priced && mug.low > 0 && mug.high > mug.low);
  assert.ok(!s.parcels.some((p) => p.sku === "BOARD-1"), "45.5 oz is 13.5 oz past the line: a different product, not a packaging change");
  assert.equal(s.parcel_low, Math.min(...s.parcels.filter((p) => p.priced).map((p) => p.low)));
});

test("the whole call, from the three reports", () => {
  const inventory = call.parseInventoryHealth(golden.fixture);
  const feePreview = call.parseFeePreview(read("engine/tests/fixtures/fee_preview_clean.txt"));
  const ppc = call.parsePpcCampaign(read("engine/tests/fixtures/ppc_campaign_clean.csv"));
  const out = call.analyse(rc, { inventory, feePreview, ppc, costShare: 0.25, targetAcos: 0.35, today: "2026-09-08" });
  assert.ok(close(out.totals.aged, 51.9));                     // 48.30 + 3.60, Amazon's own
  // WIDGET-RED: 15.2 days of supply on 30 days, 16.0 on 90, so the 14-21 band; Fee Preview
  // says large standard at 0.27 lb, so $0.70 a unit, not the small-standard $0.63 (119.70)
  assert.ok(close(out.totals.low, 0.70 * 190));
  assert.ok(out.edges.length >= 3 && out.edges[0].month > 0);
  assert.ok(out.margins.length === 3 && out.catalogue_be > 0 && out.catalogue_be < 1);
  assert.ok(out.ads && out.ads.acos > 0);
  assert.ok(out.over_target.every((m) => m.acos < 0.35));
});
