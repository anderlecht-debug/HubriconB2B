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

test("the Shopify Orders export is read the way ingest/shopify_orders.py reads it, its Email column never", () => {
  const g = golden.shopify_orders;
  const o = call.parseShopifyOrders(g.text);
  assert.deepEqual(Object.keys(o.bySku).sort(), Object.keys(g.by_sku).sort(), "the same SKUs, the gift-wrap line keyed by its name");
  for (const [sku, want] of Object.entries(g.by_sku)) {
    const b = o.bySku[sku];
    assert.equal(b.units, want.units, `${sku} units`);
    assert.ok(close(b.sales, want.sales, 0.03), `${sku} sales ${b.sales} vs engine ${want.sales}`);
    assert.ok(close(call.ordersFee(g.payments, b), want.fee, 0.03), `${sku} fee ${call.ordersFee(g.payments, b)} vs engine ${want.fee}`);
  }
  assert.equal(o.orders, 5, "#1004 cancelled and #1007 pending are dropped: no money moved");
  assert.deepEqual([o.first, o.last, o.days], ["2026-07-10", "2026-08-15", 37]);
  assert.deepEqual([...call.ORDER_DROP_STATUSES].sort(), g.drop_statuses);
  assert.equal(o.bySku["WIDGET-BLUE"].single_parcels, 1, "only #1001 was one unit of it alone");
  // the rate is the rate card's default plan, and that is the engine's own estimate
  assert.deepEqual(call.shopifyPayments(rc), { plan: "basic", ...g.payments });
  // every column the ingest reads, the call reads too, except the email it turns into a customer code
  const py = read("engine/src/hubricon_engine/ingest/shopify_orders.py");
  const spec = [...py.matchAll(/"(\w+)": \{"synonyms": \[([^\]]*)\]/g)].map(([, f, b]) => [f, [...b.matchAll(/"([^"]+)"/g)].map((m) => m[1])]);
  assert.ok(spec.length >= 10 && spec.some(([f]) => f === "email"));
  for (const [field, syns] of spec) {
    if (field === "email") continue;
    for (const s of syns) assert.ok(call.SHOPIFY_ORDERS[field][0].includes(s), `${field}: ${s}`);
  }
  assert.ok(!("email" in call.SHOPIFY_ORDERS), "the call never maps the customer's email");
  assert.ok(!Object.values(call.SHOPIFY_ORDERS).some(([syns]) => syns.some((s) => /email/.test(s))));
});

test("what a Shopify variant keeps: Shopify Payments' 2.9% + 30¢, its own cost, and the ROAS that breaks even", () => {
  const v = call.parseShopifyProducts(read("engine/tests/fixtures/shopify_products_clean.csv"));
  // no cost typed: the two variants with Cost per item are priced at it, the third waits for a cost
  const own = call.analyseShopify(rc, v);
  assert.deepEqual(own.margins.map((m) => [m.sku, m.cost_basis]).sort(), [["GADGET-PRO", "cost_per_item"], ["WIDGET-BLUE", "cost_per_item"]]);
  assert.equal(own.no_cost, 1);
  const blue = own.margins.find((m) => m.sku === "WIDGET-BLUE");
  assert.ok(close(blue.fee, 19.98 * 0.029 + 0.30));                 // one unit an order, without the Orders export
  assert.ok(close(blue.contribution, 19.98 - blue.fee - 4.10));
  assert.ok(close(blue.roas, 19.98 / blue.contribution, 1e-9));
  assert.equal(blue.fee_basis, "one_unit");
  assert.equal(own.orders, null);
  assert.equal(own.totals, null, "no month without the Orders export");
  // the cost file wins over Cost per item; the typed % covers the rest
  const typed = call.analyseShopify(rc, v, { costShare: 0.3, costBySku: { "WIDGET-BLUE": 6.5 } });
  assert.deepEqual(Object.fromEntries(typed.margins.map((m) => [m.sku, m.cost_basis])), { "WIDGET-BLUE": "yours", "WIDGET-RED": "assumed", "GADGET-PRO": "cost_per_item" });
  assert.ok(close(typed.margins.find((m) => m.sku === "WIDGET-RED").cost, 19.95 * 0.3));
  assert.equal(typed.catalogue_roas_basis, "one_each");
  const sum = (k) => typed.margins.reduce((a, m) => a + m[k], 0);
  assert.ok(close(typed.catalogue_roas, sum("price") / sum("contribution"), 1e-9));
  // a variant that keeps nothing has no ROAS that breaks even
  const loss = call.analyseShopify(rc, v, { costBySku: { "GADGET-PRO": 40 } }).margins.find((m) => m.sku === "GADGET-PRO");
  assert.ok(loss.contribution < 0 && loss.roas === null);
});

test("with the Orders export, every Shopify figure becomes a month at the export's own pace", () => {
  const v = call.parseShopifyProducts(read("engine/tests/fixtures/shopify_products_clean.csv"));
  const orders = call.parseShopifyOrders(golden.shopify_orders.text);
  const s = call.analyseShopify(rc, v, { costShare: 0.25, orders });
  const k = 30 / orders.days, pay = call.shopifyPayments(rc);
  const blue = s.margins.find((m) => m.sku === "WIDGET-BLUE"), b = orders.bySku["WIDGET-BLUE"];
  assert.equal(blue.fee_basis, "orders");
  assert.ok(close(blue.fee, 19.98 * 0.029 + 0.30 * b.orders_share / b.units), "the 30¢ shared across the units of an order");
  assert.ok(close(blue.units_month, 8 * k));
  assert.ok(close(blue.kept_month, (b.sales - call.ordersFee(pay, b) - 4.10 * b.units) * k), "sales after refunds, less the engine's fee and the cost");
  assert.equal(s.catalogue_roas_basis, "sales");
  const sold = s.margins.filter((m) => m.sales_month > 0);
  assert.ok(close(s.catalogue_roas, sold.reduce((a, m) => a + m.sales_month, 0) / sold.reduce((a, m) => a + m.kept_month, 0), 1e-9));
  assert.deepEqual(s.orders, { orders: 5, days: 37, first: "2026-07-10", last: "2026-08-15", units: 12, matched_units: 11 }, "the gift wrap matches no variant");
  assert.ok(s.totals && close(s.totals.kept_month, s.margins.reduce((a, m) => a + m.kept_month, 0)));
  // a parcel's month counts orders that were one unit of it alone
  const csv = ["Handle,Title,Option1 Value,Variant SKU,Variant Grams,Variant Price,Variant Compare At Price,Status",
    "mug,Mug,Default Title,MUG-1,470,28.00,36.00,active", "cup,Cup,Default Title,CUP-1,200,12.00,16.00,active"].join("\n");
  const ord = ["Name,Financial Status,Created at,Lineitem quantity,Lineitem price,Lineitem sku",
    "#1,paid,2026-09-01 10:00:00 -0400,1,28.00,MUG-1", "#2,paid,2026-09-10 10:00:00 -0400,2,28.00,MUG-1",
    "#3,paid,2026-09-30 10:00:00 -0400,1,28.00,MUG-1", "#3,,,1,12.00,CUP-1"].join("\n");
  const m = call.analyseShopify(rc, call.parseShopifyProducts(csv), { orders: call.parseShopifyOrders(ord) });
  const mug = m.parcels.find((p) => p.sku === "MUG-1");
  assert.equal(m.orders.days, 30);
  assert.ok(close(mug.parcels_month, 1) && close(mug.month_low, mug.low) && close(mug.month_high, mug.high));
  const gap = m.anchors.find((a) => a.sku === "MUG-1");
  assert.ok(close(gap.units_month, 4) && close(gap.month, 8 * 4), "the compare-at gap on every unit sold");
  assert.ok(close(m.totals.anchors_month, m.anchors.reduce((a, x) => a + x.month, 0)));
  // under a week of orders is not a pace: the figures stay per unit, and the page says why
  const short = call.analyseShopify(rc, call.parseShopifyProducts(csv), { orders: call.parseShopifyOrders(ord.split("\n").slice(0, 2).join("\n")) });
  assert.ok(short.orders_too_short && short.totals === null);
  assert.throws(() => call.parseShopifyOrders("Name,Financial Status,Created at,Lineitem quantity,Lineitem price\n#1,pending,2026-09-01,1,5\n"), /No paid order/);
});
