import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as fees from "./fees.js";
import { composeToolEmail, sendResend, findingLine } from "./tool_email.js";

const rc = JSON.parse(readFileSync(new URL("../ratecard.json", import.meta.url)));
const inputs = { asin: "B0TESTASIN", price: 24.99, itemWeightOz: 17.2, dims: [12, 9, 3], category: "baby", bsr: 1200, cogs: 6.5 };

test("the email restates the result from numbers and never from client prose", () => {
  const result = fees.analyse(rc, inputs, "2026-09-08");
  const link = "https://www.hubricon.com/teardown" + fees.resultHash(inputs);
  const m = composeToolEmail({ firstName: "<b>Ada</b>", asin: "B0TESTASIN", result, link, applyUrl: "https://www.hubricon.com/#apply", postalAddress: "1 Test St, Dallas TX" });
  assert.match(m.subject, /^Your 60-second Teardown: 1\.2 oz over a fee band$/);
  assert.match(m.text, /you keep \$16\.02 of \$24\.99/);
  assert.match(m.text, /Break-even ACoS 38\.1%/);
  assert.match(m.text, /holiday peak card adds 31c/);
  assert.match(m.text, /Ten thousand simulated months/);
  assert.ok(m.text.includes(link), "the plain text carries the link verbatim");
  assert.ok(m.html.includes(link.replace(/&/g, "&amp;")), "the HTML carries it escaped");
  assert.ok(m.html.includes("&lt;b&gt;Ada&lt;/b&gt;") && !m.html.includes("<b>Ada</b>"), "the name is escaped");
  assert.match(m.text, /1 Test St, Dallas TX/);
});

test("a listing with no cliff and no cost still gets an honest email", () => {
  const result = fees.analyse(rc, { price: 29.99, itemWeightOz: 8.0, dims: [10, 7, 2], category: "home & kitchen", bsr: 8000 }, "2026-09-08");
  const m = composeToolEmail({ firstName: "", asin: null, result, link: "https://www.hubricon.com/teardown#p=29.99", applyUrl: "https://www.hubricon.com/#apply" });
  assert.match(m.subject, /you keep \$/);
  assert.match(m.text, /No cliff/);
  assert.doesNotMatch(m.text, /Break-even/);
  assert.match(m.text, /^Hello,/);
});

test("finding lines cover every kind", () => {
  for (const kind of ["price_band_edge", "fee_band_edge", "dim_weight_overage", "size_tier_edge"]) {
    const f = { kind, perUnitLow: 0.4, perUnitHigh: 0.4, dollarsLow: 100, dollarsHigh: 300, evidence: { yourPrice: 10.49, targetPrice: 9.99, edge: 10, feeJumpLow: 0.8, feeJumpHigh: 0.9, breakEvenPrice: 11.1, yourWeightOz: 17.2, overByOz: 1.2, dims: [14, 13, 13], dimWeightOz: 272, axis: "thickness", actualIn: 0.9, limitIn: 0.75 } };
    assert.match(findingLine(f), /40c a unit.*\$100–\$300 a month/);
  }
});

test("sendResend reports Resend's answer and never throws", async () => {
  const calls = [];
  const okFetch = async (url, init) => { calls.push({ url, init }); return { ok: true, status: 200, json: async () => ({ id: "re_123" }) }; };
  const r = await sendResend({ apiKey: "k", from: "Hagen <h@hubricon.com>", to: "a@b.co", replyTo: "h@hubricon.com", subject: "s", text: "t", html: "<p>t</p>", fetchImpl: okFetch });
  assert.deepEqual(r, { ok: true, status: 200, id: "re_123" });
  const sent = JSON.parse(calls[0].init.body);
  assert.deepEqual(sent.to, ["a@b.co"]); assert.equal(sent.reply_to, "h@hubricon.com");
  const bad = await sendResend({ apiKey: "k", from: "f", to: "t", subject: "s", text: "t", fetchImpl: async () => ({ ok: false, status: 403, json: async () => ({ message: "domain not verified" }) }) });
  assert.deepEqual(bad, { ok: false, status: 403, error: "domain not verified" });
  const none = await sendResend({ apiKey: "", from: "f", to: "t", subject: "s", text: "t" });
  assert.equal(none.ok, false);
  const boom = await sendResend({ apiKey: "k", from: "f", to: "t", subject: "s", text: "t", fetchImpl: async () => { throw new Error("offline"); } });
  assert.equal(boom.error, "offline");
});

test("the Shopify email restates one order by zone, the pound, the anchor and the ROAS", () => {
  const result = fees.analyseShopify(rc, { handle: "shop.example/products/mug", price: 32, compareAtPrice: 45, weightOz: 17.2, orders: 400, units: 1, plan: "basic", shipCharge: 5.95, cogs: 9, catalogueShare: 0.7 });
  const link = "https://www.hubricon.com/teardown" + fees.resultHashShopify({ handle: "shop.example/products/mug", price: 32, compareAtPrice: 45, weightOz: 17.2, units: 1, shipCharge: 5.95, plan: "basic", orders: 400, cogs: 9 });
  const m = composeToolEmail({ firstName: "Ada", asin: "shop.example/products/mug", result, link, applyUrl: "https://www.hubricon.com/#apply" });
  assert.match(m.subject, /^Your 60-second Teardown: 1\.2 oz over a pound$/);
  assert.match(m.text, /One order charged at \$37\.95/);
  assert.match(m.text, /loses money in 8 of 8 zones/);
  assert.match(m.text, /The pound: your product ships at 17\.2 oz/);
  assert.match(m.text, /\$384–\$1,788 a month at the orders you typed/);
  assert.match(m.text, /The anchor: the product page says \$45\.00/);
  assert.match(m.text, /Break-even ROAS \d+\.\d\d–\d+\.\d\d across zones/);
  assert.ok(m.text.includes(link));
  assert.doesNotMatch(m.text, /ten thousand/i, "no simulation on the Shopify side");
});
