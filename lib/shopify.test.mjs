// The Shopify plumbing, with no network.   node --test lib/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import {
  API_VERSION,
  SCOPES,
  WRITE_SCOPES,
  authorizeUrl,
  decryptToken,
  encryptToken,
  exchangeCode,
  graphql,
  hasScopes,
  readCookie,
  shopsTable,
  signState,
  validShop,
  verifyQueryHmac,
  verifyState,
  verifyWebhookHmac,
} from "./shopify.js";

const SECRET = "hush";
const KEY = randomBytes(32).toString("hex");

function signedQuery(obj, secret = SECRET) {
  const msg = Object.keys(obj).sort().map((k) => `${k}=${obj[k]}`).join("&");
  return new URLSearchParams({ ...obj, hmac: createHmac("sha256", secret).update(msg).digest("hex") });
}

test("shop domains: only <store>.myshopify.com", () => {
  assert.equal(validShop("Acme-Pets.myshopify.com"), "acme-pets.myshopify.com");
  for (const bad of ["acme.com", "evil.com/.myshopify.com", "a.myshopify.com.evil.com", "-x.myshopify.com", "", null, "x.myshopify.com/admin"]) {
    assert.equal(validShop(bad), null, String(bad));
  }
});

test("query HMAC: Shopify's documented example verifies, a changed value does not", () => {
  // shopify.dev's OAuth example.
  const q = new URLSearchParams(
    "code=0907a61c0c8d55e99db179b68161bc00&hmac=700e2dadb827fcc8609e9d5ce208b2e9cdaab9df07390d2cbca10d7c328fc4bf&shop=some-shop.myshopify.com&state=0.6784241404160823&timestamp=1337178173",
  );
  assert.ok(verifyQueryHmac(q, "hush"));
  q.set("shop", "other.myshopify.com");
  assert.ok(!verifyQueryHmac(q, "hush"));
  assert.ok(!verifyQueryHmac(new URLSearchParams("shop=a.myshopify.com"), "hush"), "no hmac");
  assert.ok(!verifyQueryHmac(signedQuery({ shop: "a.myshopify.com" }), ""), "no secret");
});

test("webhook HMAC: base64 over the raw body", () => {
  const body = Buffer.from('{"id":1}');
  const good = createHmac("sha256", SECRET).update(body).digest("base64");
  assert.ok(verifyWebhookHmac(body, good, SECRET));
  assert.ok(!verifyWebhookHmac(Buffer.from('{"id":2}'), good, SECRET));
  assert.ok(!verifyWebhookHmac(body, null, SECRET));
  assert.ok(!verifyWebhookHmac(body, "short", SECRET));
});

test("state: bound to shop, nonce and ten minutes", () => {
  const shop = "a.myshopify.com";
  const { state, nonce } = signState(shop, SECRET, 1_000);
  assert.ok(verifyState(state, { shop, nonce, secret: SECRET, now: 2_000 }));
  assert.ok(!verifyState(state, { shop: "b.myshopify.com", nonce, secret: SECRET, now: 2_000 }), "other shop");
  assert.ok(!verifyState(state, { shop, nonce: "x", secret: SECRET, now: 2_000 }), "other nonce");
  assert.ok(!verifyState(state, { shop, nonce: null, secret: SECRET, now: 2_000 }), "no cookie");
  assert.ok(!verifyState(state, { shop, nonce, secret: SECRET, now: 1_000 + 11 * 60_000 }), "expired");
  assert.ok(!verifyState(state, { shop, nonce, secret: "other", now: 2_000 }), "other secret");
  assert.ok(!verifyState(state.replace(".a.", ".b."), { shop: "b.myshopify.com", nonce, secret: SECRET, now: 2_000 }));
});

test("authorize URL: read-only scopes, offline, our redirect", () => {
  const u = new URL(authorizeUrl({ shop: "a.myshopify.com", apiKey: "k", state: "s" }));
  assert.equal(u.origin, "https://a.myshopify.com");
  assert.equal(u.pathname, "/admin/oauth/authorize");
  assert.equal(u.searchParams.get("scope"), "read_orders,read_products,read_inventory");
  assert.equal(u.searchParams.get("redirect_uri"), "https://hubricon.com/api/shopify/auth");
  assert.equal(u.searchParams.get("grant_options[]"), null, "online tokens are per-user; we want offline");
  assert.ok(!SCOPES.some((s) => s.startsWith("write_")));
  assert.deepEqual(WRITE_SCOPES, ["write_products"]);
});

test("scopes: write implies read; a missing scope fails", () => {
  assert.ok(hasScopes("read_orders,read_products,read_inventory"));
  assert.ok(hasScopes("read_orders,write_products,read_inventory"));
  assert.ok(!hasScopes("read_orders,read_products"));
});

test("code exchange posts the secret to the store and returns the token", async () => {
  let seen;
  const fetch = async (url, init) => {
    seen = { url, body: JSON.parse(init.body) };
    return new Response(JSON.stringify({ access_token: "shpat_x", scope: "read_orders" }));
  };
  const out = await exchangeCode({ shop: "a.myshopify.com", code: "c", apiKey: "k", apiSecret: "s", fetch });
  assert.equal(out.access_token, "shpat_x");
  assert.equal(seen.url, "https://a.myshopify.com/admin/oauth/access_token");
  assert.deepEqual(seen.body, { client_id: "k", client_secret: "s", code: "c" });
  await assert.rejects(exchangeCode({ shop: "a.myshopify.com", code: "c", apiKey: "k", apiSecret: "s", fetch: async () => new Response("no", { status: 400 }) }));
});

test("token at rest: round-trips, is bound to its shop, refuses tampering and a wrong key", () => {
  const blob = encryptToken("shpat_secret", KEY, "a.myshopify.com");
  assert.match(blob, /^v1:/);
  assert.ok(!blob.includes("shpat"));
  assert.equal(decryptToken(blob, KEY, "a.myshopify.com"), "shpat_secret");
  assert.notEqual(encryptToken("shpat_secret", KEY, "a.myshopify.com"), blob, "fresh IV each time");
  assert.throws(() => decryptToken(blob, KEY, "b.myshopify.com"));
  assert.throws(() => decryptToken(blob, randomBytes(32).toString("hex"), "a.myshopify.com"));
  const raw = Buffer.from(blob.slice(3), "base64url");
  raw[raw.length - 1] ^= 1;
  assert.throws(() => decryptToken(`v1:${raw.toString("base64url")}`, KEY, "a.myshopify.com"));
  const b64 = randomBytes(32).toString("base64");
  assert.equal(decryptToken(encryptToken("t", b64), b64), "t", "a base64 key works too");
  assert.throws(() => encryptToken("t", "too-short"));
  assert.throws(() => encryptToken("t", ""));
});

test("GraphQL: versioned endpoint, token header, errors thrown", async () => {
  let seen;
  const fetch = async (url, init) => {
    seen = { url, headers: init.headers };
    return new Response(JSON.stringify({ data: { shop: { name: "A" } } }));
  };
  const data = await graphql({ shop: "a.myshopify.com", token: "t", query: "{ shop { name } }", fetch });
  assert.deepEqual(data, { shop: { name: "A" } });
  assert.equal(seen.url, `https://a.myshopify.com/admin/api/${API_VERSION}/graphql.json`);
  assert.equal(seen.headers["x-shopify-access-token"], "t");
  await assert.rejects(graphql({ shop: "a.myshopify.com", token: "t", query: "x", fetch: async () => new Response(JSON.stringify({ errors: [{ message: "boom" }] })) }), /boom/);
  await assert.rejects(graphql({ shop: "a.myshopify.com", token: "t", query: "x", fetch: async () => new Response("", { status: 401 }) }), /401/);
});

test("Supabase REST: service key, filtered by shop, upsert merges", async () => {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, ...init });
    return new Response(init.method === "GET" ? JSON.stringify([{ shop_domain: "a.myshopify.com" }]) : "", { status: init.method === "POST" ? 201 : 200 });
  };
  const t = shopsTable({ url: "https://db.example/", key: "svc", fetch });
  assert.equal((await t.get("a.myshopify.com")).shop_domain, "a.myshopify.com");
  await t.upsert({ shop_domain: "a.myshopify.com" });
  await t.update("a.myshopify.com", { status: "active" });
  await t.remove("a.myshopify.com");
  assert.equal(calls[0].url, "https://db.example/rest/v1/shopify_shops?shop_domain=eq.a.myshopify.com&select=*");
  assert.match(calls[1].url, /on_conflict=shop_domain/);
  assert.match(calls[1].headers.prefer, /merge-duplicates/);
  assert.equal(calls[2].method, "PATCH");
  assert.equal(calls[3].method, "DELETE");
  for (const c of calls) assert.equal(c.headers.authorization, "Bearer svc");
});

test("cookie reader", () => {
  assert.equal(readCookie("a=1; hubricon_shopify_state=abc; b=2", "hubricon_shopify_state"), "abc");
  assert.equal(readCookie(null, "x"), null);
});

test("shopify.app.toml: the same API version, scopes and URLs as the code", () => {
  const toml = readFileSync(new URL("../shopify.app.toml", import.meta.url), "utf8");
  assert.match(toml, new RegExp(`api_version = "${API_VERSION}"`));
  assert.match(toml, new RegExp(`scopes = "${SCOPES.join(",")}"`));
  assert.match(toml, /redirect_urls = \["https:\/\/hubricon\.com\/api\/shopify\/auth"\]/);
  for (const t of ["app/uninstalled", "customers/data_request", "customers/redact", "shop/redact"]) assert.ok(toml.includes(`"${t}"`), t);
  assert.doesNotMatch(toml, /client_secret|shpss_/);
});
