// The headline tiles are the one piece of the 60-second Teardown two pages show:
// index.html under the hero, teardown.html above its six sections. Pinned here so
// a change to the builder is a change to both, on purpose.
//   node --test lib/teardown_tiles.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as fees from "./fees.js";
import { amazonTiles, shopifyTiles, money, pct } from "./teardown_tiles.js";

const rc = JSON.parse(readFileSync(new URL("../ratecard.json", import.meta.url)));
const DAY = new Date("2026-09-13T12:00:00Z");
const CATEGORY = Object.keys(rc.fba.referral_by_category).sort()[0];
const count = (html) => (html.match(/<div class="tile glass">/g) || []).length;

test("an Amazon listing with its box prices all three tiles off the card", () => {
  const inputs = { price: 24.99, itemWeightOz: 12.6, dims: [12, 8, 2], category: CATEGORY, bsr: 4500, cogs: 6.5 };
  const r = fees.analyse(rc, inputs, DAY);
  const html = amazonTiles(rc, r, DAY);
  assert.equal(count(html), 3);
  assert.ok(html.includes(pct(r.u.amazonTakePct)), "the take is unitEconomics' own figure");
  assert.ok(!html.includes(">?<"), "nothing is left unpriced when the box is known");
});

test("without the box the fulfilment fee stays unpriced rather than guessed", () => {
  const r = fees.analyse(rc, { price: 24.99, itemWeightOz: 12.6, category: CATEGORY }, DAY);
  const html = amazonTiles(rc, r, DAY);
  assert.equal(count(html), 3);
  assert.match(html, /we will not guess a size tier/);
  assert.match(html, /Dimensions needed to price the peak card/);
});

test("a Shopify product an ounce over a pound prices the order, the pound and the zones", () => {
  const inputs = { handle: null, price: 32, compareAtPrice: null, weightOz: 17.2, units: 1, shipCharge: 0,
    plan: rc.shopify.default_plan, thirdParty: false, orders: 400, cogs: 9, catalogueShare: null };
  const r = fees.analyseShopify(rc, inputs);
  const html = shopifyTiles(r);
  assert.equal(count(html), 3);
  assert.ok(html.includes(money(r.econ.charged)));
  assert.ok(html.includes("The pound, per parcel"), "17.2 oz is inside the 3 oz window above a pound");
});
