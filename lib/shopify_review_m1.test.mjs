// REVIEW_M1.md's Node findings, one test each: #2 (redaction erases the store
// and the customer), #8 (a late app/uninstalled cannot undo a reinstall) and
// #9 (the token key reads the same in Node as in Python).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes } from "node:crypto";
import { webhookHandler } from "../api/shopify/webhooks.js";
import { decryptToken, encryptToken } from "./shopify.js";

const SHOP = "acme-pets.myshopify.com";
const CLIENT = "00000000-0000-0000-0000-00000000cccc";
const ENV = {
  SHOPIFY_API_SECRET: "app-secret",
  SHOPIFY_TOKEN_KEY: randomBytes(32).toString("hex"),
  SUPABASE_URL: "https://db.example",
  SUPABASE_SERVICE_ROLE_KEY: "svc",
};

/** PostgREST and Storage, in memory: tables of rows, eq. filters, and a bucket of paths. */
function world({ tables = {}, files = [] } = {}) {
  const calls = [];
  const bucket = new Set(files);
  const match = (row, params) =>
    [...params.entries()].every(([k, v]) => {
      if (k === "select" || k === "on_conflict") return true;
      const [op, ...rest] = v.split(".");
      const want = rest.join(".");
      if (op === "eq") return String(row[k]) === want;
      if (op === "lte") return row[k] != null && new Date(row[k]) <= new Date(want);
      throw new Error(`filter ${op}`);
    });
  const fetch = async (url, init = {}) => {
    const u = new URL(url);
    const body = init.body ? JSON.parse(init.body) : null;
    calls.push({ method: init.method, path: u.pathname, search: u.search, body });
    if (u.pathname.startsWith("/storage/v1/object/list/intake")) {
      const prefix = body.prefix.replace(/\/?$/, "/");
      const names = new Map();
      for (const p of bucket) {
        if (!p.startsWith(prefix)) continue;
        const rest = p.slice(prefix.length);
        const [head, ...more] = rest.split("/");
        names.set(head, more.length ? null : "file-id");
      }
      return new Response(JSON.stringify([...names].map(([name, id]) => ({ name, id }))));
    }
    if (u.pathname === "/storage/v1/object/intake" && init.method === "DELETE") {
      for (const p of body.prefixes) bucket.delete(p);
      return new Response("[]");
    }
    const name = u.pathname.replace("/rest/v1/", "");
    const rows = (tables[name] ??= []);
    if (init.method === "GET") return new Response(JSON.stringify(rows.filter((r) => match(r, u.searchParams))));
    if (init.method === "PATCH") {
      for (const r of rows) if (match(r, u.searchParams)) Object.assign(r, body);
      return new Response(null, { status: 204 });
    }
    if (init.method === "DELETE") {
      tables[name] = rows.filter((r) => !match(r, u.searchParams));
      return new Response(null, { status: 204 });
    }
    throw new Error(`unexpected ${init.method} ${url}`);
  };
  return { fetch, tables, bucket, calls };
}

function webhook(topic, body, headers = {}) {
  const raw = JSON.stringify(body);
  return new Request("https://hubricon.com/api/shopify/webhooks", {
    method: "POST",
    body: raw,
    headers: {
      "x-shopify-topic": topic,
      "x-shopify-shop-domain": SHOP,
      "x-shopify-webhook-id": "w1",
      "x-shopify-hmac-sha256": createHmac("sha256", ENV.SHOPIFY_API_SECRET).update(raw).digest("base64"),
      ...headers,
    },
  });
}

const handler = (w) => webhookHandler({ env: ENV, fetch: w.fetch, log: () => {}, now: () => Date.UTC(2026, 10, 23) });

test("REVIEW_M1 #2: shop/redact erases every row and stored file of the store", async () => {
  const mine = `shopify/${SHOP}`;
  const w = world({
    tables: {
      shopify_shops: [{ shop_domain: SHOP, client_id: CLIENT }, { shop_domain: "other.myshopify.com", client_id: "x" }],
      clients: [{ id: CLIENT }, { id: "x" }],
    },
    files: [`${mine}/lookback.json`, `${mine}/shadow/2026-11-23.json`, `${mine}/shadow/summary.json`,
      "shopify/other.myshopify.com/lookback.json"],
  });
  assert.equal((await handler(w)(webhook("shop/redact", { shop_domain: SHOP }))).status, 200);
  // The store's client goes, and with it every client_id table (ON DELETE CASCADE)
  // and the words of its seal entries (record_seals: client_id set null, document wiped).
  assert.deepEqual(w.tables.clients, [{ id: "x" }]);
  assert.deepEqual(w.tables.shopify_shops.map((r) => r.shop_domain), ["other.myshopify.com"]);
  assert.deepEqual([...w.bucket], ["shopify/other.myshopify.com/lookback.json"]);
});

test("REVIEW_M1 #2: customers/redact deletes that customer's rows", async () => {
  const email = "Pat@Example.com";
  const key = createHash("sha256").update(`${email.trim().toLowerCase()}|${CLIENT}`).digest("hex");
  const w = world({
    tables: {
      shopify_shops: [{ shop_domain: SHOP, client_id: CLIENT }],
      customer_orders: [{ client_id: CLIENT, customer_key: key, order_name: "#1" },
        { client_id: CLIENT, customer_key: "someone-else", order_name: "#2" }],
    },
  });
  const res = await handler(w)(webhook("customers/redact", { shop_domain: SHOP, customer: { id: 1, email } }));
  assert.equal(res.status, 200);
  assert.deepEqual(w.tables.customer_orders.map((r) => r.order_name), ["#2"]);
});

test("REVIEW_M1 #8: a late app/uninstalled does not wipe a newer install's token", async () => {
  const w = world({ tables: { shopify_shops: [{ shop_domain: SHOP, status: "active", token_enc: "v1:new",
    installed_at: "2026-11-23T10:00:00.000Z" }] } });
  const stale = webhook("app/uninstalled", { id: 1 }, { "x-shopify-triggered-at": "2026-11-23T09:00:00.000Z" });
  assert.equal((await handler(w)(stale)).status, 200);
  assert.equal(w.tables.shopify_shops[0].token_enc, "v1:new");
  assert.equal(w.tables.shopify_shops[0].status, "active");
  const fresh = webhook("app/uninstalled", { id: 1 }, { "x-shopify-triggered-at": "2026-11-23T11:00:00.000Z" });
  await handler(w)(fresh);
  assert.equal(w.tables.shopify_shops[0].token_enc, null);
  assert.equal(w.tables.shopify_shops[0].status, "uninstalled");
});

// The same pair engine/tests/test_review_m1.py decrypts.
const URL_KEY = "-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_8";
const VECTOR = "v1:AAECAwQFBgcICQoL8KLOxuzDkfwBGQ_RCdBEPnSjwSS77pIjnN_U_g";

test("REVIEW_M1 #9: the token key reads the same in Node as in Python", () => {
  assert.equal(decryptToken(VECTOR, URL_KEY, "acme.myshopify.com"), "shpat_vector");
  const std = URL_KEY.replace(/-/g, "+").replace(/_/g, "/");
  assert.equal(decryptToken(encryptToken("t", std, SHOP), URL_KEY, SHOP), "t");
  // Characters neither alphabet has are refused, not skipped (Python refuses them too).
  const junk = `${randomBytes(32).toString("base64").slice(0, 10)}*${randomBytes(32).toString("base64").slice(10)}`;
  assert.throws(() => encryptToken("t", junk, SHOP));
});
