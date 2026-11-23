// api/shopify/{auth,billing,webhooks}.js against a fake Shopify and a fake
// Supabase REST, no network.   node --test lib/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac, randomBytes } from "node:crypto";
import { authHandler } from "../api/shopify/auth.js";
import { TERMS, billingHandler, createSubscription } from "../api/shopify/billing.js";
import { webhookHandler } from "../api/shopify/webhooks.js";
import { STATE_COOKIE, decryptToken, encryptToken } from "./shopify.js";

const SHOP = "acme-pets.myshopify.com";
const ENV = {
  SHOPIFY_API_KEY: "client-id",
  SHOPIFY_API_SECRET: "app-secret",
  SHOPIFY_TOKEN_KEY: randomBytes(32).toString("hex"),
  SUPABASE_URL: "https://db.example",
  SUPABASE_SERVICE_ROLE_KEY: "svc",
};
const NOW = Date.UTC(2026, 10, 23, 12);

/** A fake world: one shopify_shops table behind PostgREST, and one store's Admin API. */
function world({ rows = {}, subscriptionErrors = [], active = null, tokenStatus = 200 } = {}) {
  const calls = [];
  const fetch = async (url, init = {}) => {
    const u = new URL(url);
    const body = init.body ? JSON.parse(init.body) : null;
    calls.push({ url, method: init.method, body, headers: init.headers });
    if (u.host === "db.example") {
      assert.equal(init.headers.authorization, "Bearer svc");
      const shop = u.searchParams.get("shop_domain")?.replace(/^eq\./, "");
      if (init.method === "GET") return new Response(JSON.stringify(rows[shop] ? [rows[shop]] : []));
      if (init.method === "POST") rows[body.shop_domain] = { ...(rows[body.shop_domain] ?? {}), ...body };
      if (init.method === "PATCH") rows[shop] = { ...rows[shop], ...body };
      if (init.method === "DELETE") delete rows[shop];
      return new Response(null, { status: 204 });
    }
    if (u.pathname === "/admin/oauth/access_token") {
      if (tokenStatus !== 200) return new Response("bad", { status: tokenStatus });
      return new Response(JSON.stringify({ access_token: "shpat_live", scope: "read_orders,read_products,read_inventory" }));
    }
    if (u.pathname.endsWith("/graphql.json")) {
      if (body.query.includes("appSubscriptionCreate")) {
        return new Response(JSON.stringify({
          data: { appSubscriptionCreate: {
            userErrors: subscriptionErrors,
            confirmationUrl: subscriptionErrors.length ? null : `https://${SHOP}/admin/charges/1/confirm`,
            appSubscription: subscriptionErrors.length ? null : {
              id: "gid://shopify/AppSubscription/1",
              lineItems: [{ id: "gid://shopify/AppSubscriptionLineItem/9", plan: { pricingDetails: { __typename: "AppUsagePricing" } } }],
            },
          } },
        }));
      }
      if (body.query.includes("currentAppInstallation")) {
        return new Response(JSON.stringify({ data: { currentAppInstallation: { activeSubscriptions: active ?? [] } } }));
      }
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  return { fetch, rows, calls };
}

function signQuery(obj, secret = ENV.SHOPIFY_API_SECRET) {
  const msg = Object.keys(obj).sort().map((k) => `${k}=${obj[k]}`).join("&");
  return new URLSearchParams({ ...obj, hmac: createHmac("sha256", secret).update(msg).digest("hex") });
}

async function install(w, { tamper = false, cookie = true } = {}) {
  const auth = authHandler({ env: ENV, fetch: w.fetch, now: () => NOW });
  const start = await auth(new Request(`https://hubricon.com/api/shopify/auth?${signQuery({ shop: SHOP, timestamp: String(NOW / 1000) })}`));
  assert.equal(start.status, 302);
  const to = new URL(start.headers.get("location"));
  const nonce = start.headers.get("set-cookie").match(new RegExp(`${STATE_COOKIE}=([^;]+)`))[1];
  const q = signQuery({ code: "abc", shop: tamper ? "other.myshopify.com" : SHOP, state: to.searchParams.get("state"), timestamp: String(NOW / 1000) });
  if (tamper) q.set("shop", SHOP);
  const headers = cookie ? { cookie: `${STATE_COOKIE}=${nonce}` } : {};
  return { start, to, done: await auth(new Request(`https://hubricon.com/api/shopify/auth?${q}`, { headers })) };
}

test("install: start redirects to the store's authorize page with state and a cookie", async () => {
  const w = world();
  const { start, to } = await install(w);
  assert.equal(to.host, SHOP);
  assert.equal(to.searchParams.get("client_id"), "client-id");
  assert.match(start.headers.get("set-cookie"), /HttpOnly; Secure; SameSite=Lax/);
});

test("install: the callback stores an encrypted token, creates the usage charge and sends the merchant to approve it", async () => {
  const w = world();
  const { done } = await install(w);
  assert.equal(done.status, 302);
  assert.equal(done.headers.get("location"), `https://${SHOP}/admin/charges/1/confirm`);
  const row = w.rows[SHOP];
  assert.equal(row.status, "pending_billing");
  assert.equal(row.usage_line_item_id, "gid://shopify/AppSubscriptionLineItem/9");
  assert.equal(row.cap_usd, 500);
  assert.ok(!JSON.stringify(row).includes("shpat_live"), "the token is never stored in clear");
  assert.equal(decryptToken(row.token_enc, ENV.SHOPIFY_TOKEN_KEY, SHOP), "shpat_live");
  const sub = w.calls.find((c) => c.body?.query?.includes("appSubscriptionCreate"));
  assert.equal(sub.headers["x-shopify-access-token"], "shpat_live");
});

test("install: a forged query, a missing cookie, a bad shop or a refused code stop it", async () => {
  assert.equal((await install(world(), { tamper: true })).done.status, 401);
  assert.equal((await install(world(), { cookie: false })).done.status, 403);
  assert.equal((await install(world({ tokenStatus: 400 }))).done.status, 502);
  const auth = authHandler({ env: ENV, fetch: world().fetch, now: () => NOW });
  assert.equal((await auth(new Request("https://hubricon.com/api/shopify/auth?shop=evil.com"))).status, 400);
  const unsigned = await auth(new Request(`https://hubricon.com/api/shopify/auth?shop=${SHOP}&code=x&state=y&timestamp=${NOW / 1000}`));
  assert.equal(unsigned.status, 401);
  const old = signQuery({ code: "x", shop: SHOP, state: "y", timestamp: String(NOW / 1000 - 2 * 86400) });
  assert.equal((await auth(new Request(`https://hubricon.com/api/shopify/auth?${old}`))).status, 401);
  const bare = authHandler({ env: {}, fetch: world().fetch });
  assert.equal((await bare(new Request(`https://hubricon.com/api/shopify/auth?shop=${SHOP}`))).status, 500);
});

test("billing: one usage line item, the terms, the cap and test mode unless live", async () => {
  const w = world();
  await createSubscription(SHOP, "t", { env: { ...ENV, SHOPIFY_USAGE_CAP_USD: "750" }, fetch: w.fetch });
  let v = w.calls.at(-1).body.variables;
  assert.equal(v.lineItems.length, 1);
  assert.deepEqual(v.lineItems[0], { plan: { appUsagePricingDetails: { terms: TERMS, cappedAmount: { amount: 750, currencyCode: "USD" } } } });
  assert.equal(v.test, true);
  assert.equal(v.returnUrl, `https://hubricon.com/api/shopify/billing?shop=${SHOP}`);
  assert.match(TERMS, /20% of proven profit/);
  assert.match(TERMS, /12 months/);
  assert.match(TERMS, /refunded/);

  await createSubscription(SHOP, "t", { env: { ...ENV, SHOPIFY_BILLING_LIVE: "1" }, fetch: w.fetch });
  v = w.calls.at(-1).body.variables;
  assert.equal(v.test, false);
  assert.equal(v.lineItems[0].plan.appUsagePricingDetails.cappedAmount.amount, 500);

  await assert.rejects(createSubscription(SHOP, "t", { env: ENV, fetch: world({ subscriptionErrors: [{ message: "nope" }] }).fetch }), /nope/);
});

test("billing return: active only when Shopify says the subscription is", async () => {
  const row = { shop_domain: SHOP, status: "pending_billing", token_enc: encryptToken("shpat_live", ENV.SHOPIFY_TOKEN_KEY, SHOP), usage_line_item_id: "gid://shopify/AppSubscriptionLineItem/9" };
  const req = new Request(`https://hubricon.com/api/shopify/billing?shop=${SHOP}&charge_id=1`);

  const declined = world({ rows: { [SHOP]: { ...row } }, active: [] });
  assert.equal((await billingHandler({ env: ENV, fetch: declined.fetch })(req)).status, 402);
  assert.equal(declined.rows[SHOP].status, "pending_billing");

  const ok = world({ rows: { [SHOP]: { ...row } }, active: [{ id: "s", status: "ACTIVE", lineItems: [{ id: row.usage_line_item_id }] }] });
  const res = await billingHandler({ env: ENV, fetch: ok.fetch })(req);
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), `https://${SHOP}/admin/apps/client-id`);
  assert.equal(ok.rows[SHOP].status, "active");

  const gone = world();
  assert.equal((await billingHandler({ env: ENV, fetch: gone.fetch })(req)).status, 404);
});

function webhook(topic, body, { secret = ENV.SHOPIFY_API_SECRET } = {}) {
  const raw = JSON.stringify(body);
  return new Request("https://hubricon.com/api/shopify/webhooks", {
    method: "POST",
    body: raw,
    headers: {
      "x-shopify-topic": topic,
      "x-shopify-shop-domain": SHOP,
      "x-shopify-webhook-id": "w1",
      "x-shopify-hmac-sha256": createHmac("sha256", secret).update(raw).digest("base64"),
    },
  });
}

test("webhooks: a bad signature is 401 and touches nothing", async () => {
  const w = world({ rows: { [SHOP]: { shop_domain: SHOP, status: "active", token_enc: "v1:x" } } });
  const res = await webhookHandler({ env: ENV, fetch: w.fetch, log: () => {} })(webhook("app/uninstalled", {}, { secret: "wrong" }));
  assert.equal(res.status, 401);
  assert.equal(w.rows[SHOP].status, "active");
});

test("webhooks: uninstall wipes the token; privacy requests are 200", async () => {
  const logs = [];
  const w = world({ rows: { [SHOP]: { shop_domain: SHOP, status: "active", token_enc: "v1:x" } } });
  const h = webhookHandler({ env: ENV, fetch: w.fetch, log: (m) => logs.push(m), now: () => NOW });

  assert.equal((await h(webhook("app/uninstalled", { id: 1 }))).status, 200);
  assert.equal(w.rows[SHOP].status, "uninstalled");
  assert.equal(w.rows[SHOP].token_enc, null);
  assert.equal(w.rows[SHOP].uninstalled_at, new Date(NOW).toISOString());

  for (const t of ["customers/data_request", "customers/redact"]) {
    const before = w.calls.length;
    assert.equal((await h(webhook(t, { customer: { id: 1 } }))).status, 200);
    assert.ok(w.calls.slice(before).every((c) => c.method === "GET"), `${t} writes nothing it does not hold`);
  }
  assert.ok(logs.some((l) => l.includes("customers/redact")));
  // shop/redact's full erasure (rows, client, stored files): lib/shopify_review_m1.test.mjs.
});
