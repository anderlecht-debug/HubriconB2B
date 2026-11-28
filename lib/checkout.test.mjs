import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  PLAN, MONTHLY_FEE_USD, CHECKOUT_ENV, NOT_SWITCHED_ON, SESSION_ID,
  missingForCheckout, siteBase, returnPath, refererPath, checkoutParams, readPlatform, isSelfServe,
  uploadToken, tokenHash, uploadUrl, billingKey, billingUrl, verifyBillingKey, createCheckout,
} from "./checkout.js";

const ENV = Object.fromEntries(CHECKOUT_ENV.map((k) => [k, `${k.toLowerCase()}_value`]));
const CLIENT_ID = "0b7c1f0e-3c59-4d0a-9d3e-6a1f5a0f9a11";

function fakeStripe({ fail = null, url = "https://checkout.stripe.com/c/pay/cs_test_abc" } = {}) {
  const calls = [];
  return {
    calls,
    checkout: {
      sessions: {
        create: async (params) => {
          calls.push(params);
          if (fail) throw new Error(fail);
          return { id: "cs_test_abc12345", url };
        },
      },
    },
  };
}

test("the plan is self_serve at $1,000 a month", () => {
  assert.equal(PLAN, "self_serve");
  assert.equal(MONTHLY_FEE_USD, 1000);
});

test("the session is one card subscription at the configured price, marked on the session and the subscription", () => {
  const p = checkoutParams({ priceId: "price_1k", base: "https://www.hubricon.com", platform: "Shopify", from: "/start" });
  assert.equal(p.mode, "subscription");
  assert.deepEqual(p.line_items, [{ price: "price_1k", quantity: 1 }]);
  assert.deepEqual(p.payment_method_types, ["card"]);
  assert.equal(p.success_url, "https://www.hubricon.com/start?session_id={CHECKOUT_SESSION_ID}");
  assert.equal(p.cancel_url, "https://www.hubricon.com/start?checkout=cancelled&p=shopify");
  assert.deepEqual(p.metadata, { hubricon_plan: "self_serve", hubricon_platform: "shopify" });
  assert.deepEqual(p.subscription_data.metadata, p.metadata);
  assert.equal(p.custom_fields, undefined, "the page already said where they sell, so the card page does not ask");
});

test("nothing is bundled into the payment: no trial, no coupon field, no consent box, no email asked twice", () => {
  const p = checkoutParams({ priceId: "price_1k", base: "https://www.hubricon.com" });
  for (const key of ["consent_collection", "allow_promotion_codes", "discounts", "customer_email", "phone_number_collection"]) {
    assert.equal(p[key], undefined, key);
  }
  assert.equal(p.subscription_data.trial_period_days, undefined);
  assert.equal(p.subscription_data.trial_end, undefined);
});

test("with no platform from the page, the card page asks the one question the upload page depends on", () => {
  const p = checkoutParams({ priceId: "price_1k", base: "https://www.hubricon.com", platform: "etsy" });
  assert.deepEqual(p.metadata, { hubricon_plan: "self_serve" });
  assert.equal(p.cancel_url, "https://www.hubricon.com/start?checkout=cancelled");
  assert.equal(p.custom_fields.length, 1);
  const [field] = p.custom_fields;
  assert.equal(field.key, "platform");
  assert.ok(field.label.custom.length <= 50, "Stripe caps a custom label at 50 characters");
  assert.deepEqual(field.dropdown.options.map((o) => o.value), ["shopify", "amazon", "both"]);
});

test("where they sell is read from what the page sent, else the card page's answer, else both", () => {
  assert.equal(readPlatform({ metadata: { hubricon_platform: "amazon" } }), "amazon");
  assert.equal(readPlatform({ metadata: {}, custom_fields: [{ key: "platform", dropdown: { value: "shopify" } }] }), "shopify");
  assert.equal(readPlatform({ metadata: {}, custom_fields: [{ key: "platform", dropdown: { value: null } }] }), "both");
  assert.equal(readPlatform({}), "both");
});

test("only a subscription bought on the self-serve button is ours", () => {
  assert.equal(isSelfServe({ mode: "subscription", metadata: { hubricon_plan: "self_serve" } }), true);
  assert.equal(isSelfServe({ mode: "payment", metadata: { hubricon_plan: "self_serve" } }), false);
  assert.equal(isSelfServe({ mode: "subscription", metadata: {} }), false);
  assert.equal(isSelfServe(null), false);
});

test("the way back from the card page is a path on this site and nothing else", () => {
  assert.equal(returnPath("/start"), "/start");
  assert.equal(returnPath("/start?p=amazon#x"), "/start");
  assert.equal(returnPath("/offer"), "/offer");
  for (const bad of ["//evil.example/x", "https://evil.example/start", "javascript:alert(1)", "start", "/a b", "/%2f%2fevil", "", null, 7, "/" + "a".repeat(300)]) {
    assert.equal(returnPath(bad), "/start", String(bad));
  }
});

test("a Referer only counts when it is this site's", () => {
  assert.equal(refererPath("https://www.hubricon.com/start?p=amazon", "https://www.hubricon.com"), "/start");
  assert.equal(refererPath("https://evil.example/start", "https://www.hubricon.com"), null);
  assert.equal(refererPath("not a url", "https://www.hubricon.com"), null);
  assert.equal(refererPath(null, "https://www.hubricon.com"), null);
});

test("the site base comes from INTAKE_BASE_URL, without a trailing slash, and falls back to the live site", () => {
  assert.equal(siteBase({ INTAKE_BASE_URL: "https://preview.hubricon.com/" }), "https://preview.hubricon.com");
  assert.equal(siteBase({}), "https://www.hubricon.com");
  assert.equal(siteBase({ INTAKE_BASE_URL: "hubricon.com" }), "https://www.hubricon.com");
});

test("the upload token is the same every time for one session, different for another, and fits the link resolver", () => {
  const a = uploadToken("secret", "cs_test_aaaaaaaa");
  assert.equal(a, uploadToken("secret", "cs_test_aaaaaaaa"));
  assert.notEqual(a, uploadToken("secret", "cs_test_bbbbbbbb"));
  assert.notEqual(a, uploadToken("other", "cs_test_aaaaaaaa"));
  assert.match(a, /^[A-Za-z0-9_-]{43}$/);
  assert.ok(a.length >= 20 && a.length <= 200, "lib/token.js accepts 20 to 200 characters");
  assert.equal(tokenHash(a), createHash("sha256").update(a).digest("hex"));
  assert.equal(uploadUrl("https://www.hubricon.com", a), `https://www.hubricon.com/intake?t=${a}`);
  assert.throws(() => uploadToken("", "cs_test_aaaaaaaa"), /CHECKOUT_TOKEN_SECRET/);
});

test("the cancel link verifies for its own client and for nobody else", () => {
  const url = new URL(billingUrl("https://www.hubricon.com", "secret", CLIENT_ID));
  assert.equal(url.pathname, "/api/billing");
  const [c, k] = [url.searchParams.get("c"), url.searchParams.get("k")];
  assert.equal(c, CLIENT_ID);
  assert.equal(k, billingKey("secret", CLIENT_ID));
  assert.equal(verifyBillingKey("secret", c, k), true);
  assert.equal(verifyBillingKey("secret", "1b7c1f0e-3c59-4d0a-9d3e-6a1f5a0f9a11", k), false);
  assert.equal(verifyBillingKey("other", c, k), false);
  assert.equal(verifyBillingKey("secret", c, k.slice(0, -1)), false);
  assert.equal(verifyBillingKey("secret", c, ""), false);
  assert.equal(verifyBillingKey("secret", "not-a-uuid", billingKey("secret", "not-a-uuid")), false);
  assert.equal(verifyBillingKey("", c, k), false);
  assert.equal(verifyBillingKey("secret", c, undefined), false);
});

test("a Checkout session id is recognised by its shape", () => {
  assert.match("cs_test_a1B2c3D4e5F6g7H8", SESSION_ID);
  assert.match("cs_live_a1B2c3D4e5F6g7H8", SESSION_ID);
  for (const bad of ["", "cs_test_", "sub_123456789", "cs_test_abc/../x", "{CHECKOUT_SESSION_ID}"]) {
    assert.doesNotMatch(bad, SESSION_ID);
  }
});

test("the button opens Stripe's card page when everything behind it is configured", async () => {
  const stripe = fakeStripe();
  const out = await createCheckout({ env: ENV, makeStripe: () => stripe, platform: "amazon", from: "/start" });
  assert.deepEqual(out, { ok: true, url: "https://checkout.stripe.com/c/pay/cs_test_abc", id: "cs_test_abc12345" });
  assert.equal(stripe.calls.length, 1);
  assert.equal(stripe.calls[0].line_items[0].price, ENV.STRIPE_CHECKOUT_PRICE_ID);
  assert.equal(stripe.calls[0].metadata.hubricon_platform, "amazon");
});

test("a missing key is an honest 503 and Stripe is never called", async () => {
  for (const name of CHECKOUT_ENV) {
    const env = { ...ENV, [name]: "" };
    assert.deepEqual(missingForCheckout(env), [name]);
    const out = await createCheckout({
      env, makeStripe: () => assert.fail(`Stripe must not be built without ${name}`), platform: "shopify",
    });
    assert.equal(out.ok, false);
    assert.equal(out.status, 503);
    assert.equal(out.error, "not_configured");
    assert.equal(out.message, NOT_SWITCHED_ON);
    assert.match(out.message, /Nothing was charged/);
  }
});

test("a Stripe failure says nothing was charged and is a 502", async () => {
  const out = await createCheckout({ env: ENV, makeStripe: () => fakeStripe({ fail: "No such price" }) });
  assert.equal(out.ok, false);
  assert.equal(out.status, 502);
  assert.match(out.message, /Nothing was charged/);
  assert.equal(out.detail, "No such price");
});

test("a form post that names no page returns to the page it came from, when that page is ours", async () => {
  const stripe = fakeStripe();
  await createCheckout({ env: ENV, makeStripe: () => stripe, referer: "https://www.hubricon.com/offer?x=1" });
  assert.equal(stripe.calls[0].cancel_url, "https://www.hubricon.com/offer?checkout=cancelled");
  await createCheckout({ env: ENV, makeStripe: () => stripe, referer: "https://evil.example/phish" });
  assert.equal(stripe.calls[1].cancel_url, "https://www.hubricon.com/start?checkout=cancelled");
});
