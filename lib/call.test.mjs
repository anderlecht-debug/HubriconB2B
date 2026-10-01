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

test("the whole call, from the three reports", () => {
  const inventory = call.parseInventoryHealth(golden.fixture);
  const feePreview = call.parseFeePreview(read("engine/tests/fixtures/fee_preview_clean.txt"));
  const ppc = call.parsePpcCampaign(read("engine/tests/fixtures/ppc_campaign_clean.csv"));
  const out = call.analyse(rc, { inventory, feePreview, ppc, costShare: 0.25, targetAcos: 0.35, today: "2026-09-08" });
  assert.ok(close(out.totals.aged, 51.9));                     // 48.30 + 3.60, Amazon's own
  assert.ok(close(out.totals.low, 119.7));                     // WIDGET-RED, 15 days of supply
  assert.ok(out.edges.length >= 3 && out.edges[0].month > 0);
  assert.ok(out.margins.length === 3 && out.catalogue_be > 0 && out.catalogue_be < 1);
  assert.ok(out.ads && out.ads.acos > 0);
  assert.ok(out.over_target.every((m) => m.acos < 0.35));
});
