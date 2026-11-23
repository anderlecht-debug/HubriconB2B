// api/shopify/app.js and app.html: the installed store's page, its session, its
// limits form and the fee question, against a fake Supabase. No network.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { LABELS, appHandler, parseMandate } from "../api/shopify/app.js";
import { PRICE_SCOPES, SCOPES, signSession, verifySession } from "./shopify.js";

const SHOP = "acme-pets.myshopify.com";
const ENV = { SHOPIFY_API_SECRET: "app-secret", SUPABASE_URL: "https://db.example", SUPABASE_SERVICE_ROLE_KEY: "svc" };
const NOW = Date.UTC(2026, 10, 23, 12);

function signed(params) {
  const msg = Object.entries(params).sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, v]) => `${k}=${v}`).join("&");
  return new URLSearchParams({ ...params, hmac: createHmac("sha256", ENV.SHOPIFY_API_SECRET).update(msg).digest("hex") });
}

function world({ shop = {}, mandate = null, files = {} } = {}) {
  const tables = {
    shopify_shops: { [SHOP]: { shop_domain: SHOP, status: "active", installed_at: "2026-10-01T00:00:00Z", scopes: SCOPES.join(","), cap_usd: 500, fee_question: "none", ...shop } },
    shopify_mandates: mandate ? { [SHOP]: mandate } : {},
  };
  const writes = [];
  const fetch = async (url, init = {}) => {
    const u = new URL(url);
    assert.equal(u.host, "db.example");
    assert.equal(init.headers.authorization, "Bearer svc");
    if (u.pathname.startsWith("/storage/v1/object/intake/")) {
      const path = decodeURIComponent(u.pathname.slice("/storage/v1/object/intake/".length));
      return path in files ? new Response(JSON.stringify(files[path])) : new Response("{}", { status: 404 });
    }
    const name = u.pathname.split("/").pop();
    const t = tables[name];
    const shop = u.searchParams.get("shop_domain")?.replace(/^eq\./, "");
    const body = init.body ? JSON.parse(init.body) : null;
    if (init.method === "GET") return new Response(JSON.stringify(t[shop] ? [t[shop]] : []));
    writes.push({ name, method: init.method, body });
    if (init.method === "POST") t[body.shop_domain] = { ...(t[body.shop_domain] ?? {}), ...body };
    if (init.method === "PATCH") t[shop] = { ...t[shop], ...body };
    return new Response(null, { status: 204 });
  };
  return { fetch, tables, writes };
}

const get = (h, query, headers = {}) => h(new Request(`https://hubricon.com/api/shopify/app?${query ?? ""}`, { headers }));
const post = (h, body, session) => h(new Request("https://hubricon.com/api/shopify/app", {
  method: "POST", headers: { "content-type": "application/json", ...(session ? { authorization: `Bearer ${session}` } : {}) },
  body: JSON.stringify(body),
}));

test("the default install stays read-only; write_products is a separate opt-in", () => {
  assert.ok(!SCOPES.includes("write_products"));
  assert.deepEqual(PRICE_SCOPES, [...SCOPES, "write_products"]);
  const toml = readFileSync(new URL("../shopify.app.toml", import.meta.url), "utf8");
  assert.match(toml, /scopes = "read_orders,read_products,read_inventory"/);
});

test("a session names one shop, an hour, and cannot be forged", () => {
  const s = signSession(SHOP, "k", NOW);
  assert.equal(verifySession(s, "k", NOW), SHOP);
  assert.equal(verifySession(s, "k", NOW + 61 * 60 * 1000), null);
  assert.equal(verifySession(s, "other", NOW), null);
  assert.equal(verifySession(s.replace("acme-pets", "evil-pets"), "k", NOW), null);
  assert.equal(verifySession("nonsense", "k", NOW), null);
});

test("GET needs Shopify's signed, fresh query; then every block is labelled", async () => {
  const files = {
    [`shopify/${SHOP}/lookback.json`]: { label: "hindsight, not a sealed call", total: { usd: 120 }, summary: ["Hindsight, not a sealed call: x"] },
    [`shopify/${SHOP}/shadow/summary.json`]: { n_graded: 6, hits: 5, hit_rate: 0.8333 },
    [`shopify/${SHOP}/ledger.json`]: { label: "observed, not ours", entries: [] },
    [`shopify/${SHOP}/fee.json`]: { statements: [{ month: "2026-11", cumulative: 400, fee: 80, net: 80, explanation: ["Fee this month: $80.00."] }] },
  };
  const w = world({ files });
  const h = appHandler({ env: ENV, fetch: w.fetch, now: () => NOW });
  assert.equal((await get(h, `shop=${SHOP}`)).status, 401);
  const stale = signed({ shop: SHOP, timestamp: String(NOW / 1000 - 2 * 3600) });
  assert.equal((await get(h, stale)).status, 401);
  const bad = signed({ shop: SHOP, timestamp: String(NOW / 1000) });
  bad.set("shop", "other.myshopify.com");
  assert.equal((await get(h, bad)).status, 401);

  const res = await get(h, signed({ shop: SHOP, timestamp: String(NOW / 1000), host: "abc" }));
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(verifySession(data.session, ENV.SHOPIFY_API_SECRET, NOW), SHOP);
  assert.equal(data.lookback.label, "hindsight");
  assert.equal(data.shadow.label, "sealed call");
  assert.equal(data.observed.label, "observed, not ours");
  assert.equal(data.fee.label, "proven");
  assert.deepEqual(data.fee.lines, ["Fee this month: $80.00."]);
  assert.equal(data.awaiting_tap.data, null);
  assert.deepEqual(data.mandate, { max_price_step_pct: 5, price_moves_enabled: false, reorder_needs_tap: true,
    shadow_weeks: 4, write_access: false, shadow_ends: "2026-10-29", in_shadow: false });
  // a reload with the session works too
  assert.equal((await get(h, "", { authorization: `Bearer ${data.session}` })).status, 200);
});

test("an uninstalled store gets nothing", async () => {
  const w = world({ shop: { status: "uninstalled" } });
  const h = appHandler({ env: ENV, fetch: w.fetch, now: () => NOW });
  assert.equal((await get(h, signed({ shop: SHOP, timestamp: String(NOW / 1000) }))).status, 404);
});

test("the limits form: a session is required, the terms' 5% is the ceiling", async () => {
  const w = world();
  const h = appHandler({ env: ENV, fetch: w.fetch, now: () => NOW });
  const session = signSession(SHOP, ENV.SHOPIFY_API_SECRET, NOW);
  const form = { action: "mandate", max_price_step_pct: 3, price_moves_enabled: true, reorder_needs_tap: true };
  assert.equal((await post(h, form)).status, 401);                     // no session, no write
  assert.equal((await post(h, { ...form, max_price_step_pct: 8 }, session)).status, 400);
  assert.equal((await post(h, { ...form, price_moves_enabled: "yes" }, session)).status, 400);
  const ok = await post(h, form, session);
  assert.equal(ok.status, 200);
  assert.deepEqual(w.tables.shopify_mandates[SHOP], { shop_domain: SHOP, max_price_step_pct: 3, price_moves_enabled: true, reorder_needs_tap: true });
  assert.ok(parseMandate({ max_price_step_pct: 0, price_moves_enabled: true, reorder_needs_tap: true }).error);
});

test("the fee question is answered once, only when it is open", async () => {
  const w = world({ shop: { fee_question: "ask" } });
  const h = appHandler({ env: ENV, fetch: w.fetch, now: () => NOW });
  const session = signSession(SHOP, ENV.SHOPIFY_API_SECRET, NOW);
  assert.equal((await post(h, { action: "fee_answer", approved: "y" }, session)).status, 400);
  assert.equal((await post(h, { action: "fee_answer", approved: true }, session)).status, 200);
  assert.equal(w.tables.shopify_shops[SHOP].fee_question, "approved");
  assert.equal((await post(h, { action: "fee_answer", approved: false }, session)).status, 409);
});

test("app.html: the one stylesheet, no HTML from the server, every number labelled", () => {
  const html = readFileSync(new URL("../app.html", import.meta.url), "utf8");
  assert.match(html, /<link rel="stylesheet" href="\/assets\/hubricon.css">/);
  assert.doesNotMatch(html, /innerHTML|insertAdjacentHTML|document\.write/);
  for (const label of ["hindsight", "sealed call", "observed, not ours", "proven"]) assert.ok(html.includes(label), label);
  assert.deepEqual(Object.values(LABELS).slice(0, 4), ["hindsight", "sealed call", "observed, not ours", "proven"]);
  // every figure the script prints goes through fig(text, label): no bare usd(...) appended
  const script = html.split("<script")[1];
  for (const m of script.matchAll(/usd\(/g)) {
    const before = script.slice(Math.max(0, m.index - 6), m.index);
    assert.ok(before.includes("fig(") || before.includes("const ") || before.endsWith("= "), `a bare number near ${script.slice(m.index - 40, m.index + 20)}`);
  }
  // the retired client words stay off this client surface
  const words = html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, " ");
  assert.doesNotMatch(words, /\bledger\b|\bdirective/i);
});
