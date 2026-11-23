// The Shopify app's plumbing: proving a request came from Shopify, the OAuth
// install, the token at rest, one GraphQL call, and the shopify_shops row
// through Supabase's REST API. No framework and no Shopify SDK: every check is
// a few lines here, tested in lib/shopify.test.mjs without the network.
//
// Secrets (all read from the env the caller passes, process.env by default):
//   SHOPIFY_API_KEY      the app's client id (Partner dashboard → the app → Client credentials)
//   SHOPIFY_API_SECRET   the app's client secret; signs OAuth queries, webhooks and our state
//   SHOPIFY_TOKEN_KEY    32 bytes (64 hex chars or base64) that encrypt each store's token at rest
import { createCipheriv, createDecipheriv, createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

// One constant, everywhere: the Admin API version every call and webhook uses
// (also shopify.app.toml's [webhooks] api_version; the test keeps them equal).
export const API_VERSION = "2026-10";

// Read-only until the merchant opts into price steps (BUILD_PLAN M6). Adding
// write_products later means asking every installed store to re-authorise.
export const SCOPES = ["read_orders", "read_products", "read_inventory"];
export const WRITE_SCOPES = ["write_products"];
// Only for a brand that has turned price moves on in its limits and chosen to
// grant write access. Never the default install (SCOPES above).
export const PRICE_SCOPES = Object.freeze([...SCOPES, ...WRITE_SCOPES]);
// Orders older than 60 days need read_all_orders, which Shopify grants only on
// request (Partner Dashboard → API access). Opt-in, never in the default install:
// until it is approved the engine sees about 8 weeks of orders and labels calls
// made from that short history.
export const READ_ALL_ORDERS = "read_all_orders";

export const APP_ORIGIN = "https://hubricon.com";
export const REDIRECT_URI = `${APP_ORIGIN}/api/shopify/auth`;
export const BILLING_RETURN_URI = `${APP_ORIGIN}/api/shopify/billing`;

const STATE_TTL_MS = 10 * 60 * 1000;
export const STATE_COOKIE = "hubricon_shopify_state";

// ── Signatures ──────────────────────────────────────────────────────────────

function safeEqual(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && timingSafeEqual(x, y);
}

/** A store's own domain, lower-cased, or null. Only *.myshopify.com is accepted. */
export function validShop(shop) {
  if (typeof shop !== "string") return null;
  const s = shop.trim().toLowerCase();
  return /^[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com$/.test(s) ? s : null;
}

/**
 * Shopify signs the query of every install and OAuth callback: HMAC-SHA256 (hex)
 * over the other parameters, sorted and joined as k=v&k=v. Accepts URLSearchParams
 * or a plain object.
 */
export function verifyQueryHmac(params, secret) {
  if (!secret) return false;
  const entries = params instanceof URLSearchParams ? [...params.entries()] : Object.entries(params ?? {});
  const hmac = entries.find(([k]) => k === "hmac")?.[1];
  if (!hmac) return false;
  const message = entries
    .filter(([k]) => k !== "hmac" && k !== "signature")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${k}=${v}`)
    .join("&");
  const digest = createHmac("sha256", secret).update(message).digest("hex");
  return safeEqual(digest, String(hmac).toLowerCase());
}

/** Webhooks: X-Shopify-Hmac-Sha256 is base64 HMAC-SHA256 of the raw body. */
export function verifyWebhookHmac(rawBody, header, secret) {
  if (!secret || !header) return false;
  const digest = createHmac("sha256", secret).update(rawBody).digest("base64");
  return safeEqual(digest, header);
}

// ── OAuth ───────────────────────────────────────────────────────────────────

/**
 * A state that names its shop, expires in ten minutes and is signed with the app
 * secret: `nonce.shop.expiresMs.sig`. The nonce also goes in an HttpOnly cookie,
 * so a callback must come from the browser that started the install.
 */
export function signState(shop, secret, now = Date.now(), nonce = randomBytes(16).toString("hex")) {
  const body = `${nonce}.${shop}.${now + STATE_TTL_MS}`;
  const sig = createHmac("sha256", secret).update(body).digest("hex");
  return { state: `${body}.${sig}`, nonce };
}

export function verifyState(state, { shop, nonce, secret, now = Date.now() }) {
  if (typeof state !== "string" || !secret) return false;
  const parts = state.split(".");
  const sig = parts.pop();
  const expires = Number(parts.pop());
  const stateNonce = parts.shift();
  const stateShop = parts.join(".");
  const body = `${stateNonce}.${stateShop}.${expires}`;
  const expected = createHmac("sha256", secret).update(body).digest("hex");
  return (
    safeEqual(expected, sig ?? "") &&
    stateShop === shop &&
    Number.isFinite(expires) &&
    now <= expires &&
    !!nonce &&
    safeEqual(stateNonce, nonce)
  );
}

/** Where the merchant approves the scopes. No grant_options[]: the token is offline. */
export function authorizeUrl({ shop, apiKey, state, scopes = SCOPES, redirectUri = REDIRECT_URI }) {
  const q = new URLSearchParams({ client_id: apiKey, scope: scopes.join(","), redirect_uri: redirectUri, state });
  return `https://${shop}/admin/oauth/authorize?${q}`;
}

/** Trade the one-time code for the store's offline token. Returns { access_token, scope }. */
export async function exchangeCode({ shop, code, apiKey, apiSecret, fetch = globalThis.fetch }) {
  const res = await fetch(`https://${shop}/admin/oauth/access_token`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ client_id: apiKey, client_secret: apiSecret, code }),
  });
  if (!res.ok) throw new Error(`token exchange failed: ${res.status}`);
  const data = await res.json();
  if (!data?.access_token) throw new Error("token exchange returned no access_token");
  return data;
}

/** True when every scope we need was granted (Shopify may report implied scopes too). */
export function hasScopes(granted, needed = SCOPES) {
  const have = new Set(String(granted ?? "").split(",").map((s) => s.trim()).filter(Boolean));
  // write_x implies read_x.
  for (const s of [...have]) if (s.startsWith("write_")) have.add(`read_${s.slice(6)}`);
  return needed.every((s) => have.has(s));
}

// ── The token at rest (AES-256-GCM) ────────────────────────────────────────

/**
 * SHOPIFY_TOKEN_KEY as 32 bytes, read exactly as engine shopify_run.token_key
 * reads it: 64 hex characters, or base64 in either alphabet (standard or
 * url-safe, padded or not). Node's own base64 decoder skips characters it does
 * not know, so the key is checked first: anything else is refused, never
 * half-decoded into a key Python would not read.
 */
export function tokenKey(raw) {
  const text = String(raw ?? "").trim();
  if (!text) throw new Error("SHOPIFY_TOKEN_KEY is not set");
  let key;
  if (/^[0-9a-f]{64}$/i.test(text)) {
    key = Buffer.from(text, "hex");
  } else {
    let std = text.replace(/-/g, "+").replace(/_/g, "/").replace(/=+$/, "");
    std += "=".repeat((4 - (std.length % 4)) % 4);
    if (!/^[A-Za-z0-9+/]*={0,2}$/.test(std) || std.length % 4) {
      throw new Error("SHOPIFY_TOKEN_KEY is neither hex nor base64");
    }
    key = Buffer.from(std, "base64");
  }
  if (key.length !== 32) throw new Error("SHOPIFY_TOKEN_KEY must be 32 bytes (64 hex chars or base64)");
  return key;
}

/** "v1:" + base64url(iv[12] | tag[16] | ciphertext). The shop domain is bound as AAD. */
export function encryptToken(token, rawKey, shop = "") {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", tokenKey(rawKey), iv);
  cipher.setAAD(Buffer.from(shop));
  const ct = Buffer.concat([cipher.update(token, "utf8"), cipher.final()]);
  return `v1:${Buffer.concat([iv, cipher.getAuthTag(), ct]).toString("base64url")}`;
}

export function decryptToken(blob, rawKey, shop = "") {
  if (typeof blob !== "string" || !blob.startsWith("v1:")) throw new Error("unknown token format");
  const buf = Buffer.from(blob.slice(3), "base64url");
  const decipher = createDecipheriv("aes-256-gcm", tokenKey(rawKey), buf.subarray(0, 12));
  decipher.setAAD(Buffer.from(shop));
  decipher.setAuthTag(buf.subarray(12, 28));
  return Buffer.concat([decipher.update(buf.subarray(28)), decipher.final()]).toString("utf8");
}

// ── GraphQL ─────────────────────────────────────────────────────────────────

export async function graphql({ shop, token, query, variables = {}, fetch = globalThis.fetch }) {
  const res = await fetch(`https://${shop}/admin/api/${API_VERSION}/graphql.json`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-shopify-access-token": token },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`Shopify GraphQL ${res.status}`);
  const body = await res.json();
  if (body.errors?.length) throw new Error(`Shopify GraphQL: ${body.errors.map((e) => e.message).join("; ")}`);
  return body.data;
}

// ── The app page's session ──────────────────────────────────────────────────

export const SESSION_TTL_MS = 60 * 60 * 1000;

/**
 * After the app page's first load proves itself with Shopify's signed query,
 * the page gets this: `expiresMs.shop.sig`, HMAC-SHA256 with the app secret. It
 * names one shop and lives an hour. Every write must carry it.
 */
export function signSession(shop, secret, now = Date.now(), ttlMs = SESSION_TTL_MS) {
  const body = `${now + ttlMs}.${shop}`;
  return `${body}.${createHmac("sha256", secret).update(`session|${body}`).digest("hex")}`;
}

/** The shop a session names, or null when it is forged, expired or malformed. */
export function verifySession(token, secret, now = Date.now()) {
  if (typeof token !== "string" || !secret) return null;
  const parts = token.split(".");
  if (parts.length < 4) return null;
  const sig = parts.pop();
  const expires = Number(parts.shift());
  const shop = validShop(parts.join("."));
  const expected = createHmac("sha256", secret).update(`session|${expires}.${parts.join(".")}`).digest("hex");
  if (!shop || !Number.isFinite(expires) || now > expires || !safeEqual(expected, sig)) return null;
  return shop;
}

// ── Supabase REST (service role, server only) ──────────────────────────────

/** One JSON object from Supabase Storage, or null when it is not there yet. */
export async function readStored({ url, key, fetch = globalThis.fetch }, bucket, path) {
  const res = await fetch(`${url.replace(/\/$/, "")}/storage/v1/object/${bucket}/${path.split("/").map(encodeURIComponent).join("/")}`, {
    headers: { apikey: key, authorization: `Bearer ${key}` },
  });
  if (res.status === 404 || res.status === 400) return null;
  if (!res.ok) throw new Error(`Supabase storage ${path}: ${res.status}`);
  try {
    return JSON.parse(await res.text());
  } catch {
    return null;
  }
}

/** shopify_mandates: the brand's limits, keyed like shopify_shops. */
export function mandatesTable(opts) {
  return keyedTable("shopify_mandates", opts);
}

export function shopsTable(opts) {
  return keyedTable("shopify_shops", opts);
}

function keyedTable(name, { url, key, fetch = globalThis.fetch }) {
  if (!url || !key) throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required");
  const base = `${url.replace(/\/$/, "")}/rest/v1/${name}`;
  const headers = { apikey: key, authorization: `Bearer ${key}`, "content-type": "application/json" };
  const call = async (path, init) => {
    const res = await fetch(`${base}${path}`, { ...init, headers: { ...headers, ...init.headers } });
    if (!res.ok) throw new Error(`Supabase ${init.method} ${name}: ${res.status} ${await res.text()}`);
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  };
  const eq = (shop) => `?shop_domain=eq.${encodeURIComponent(shop)}`;
  return {
    async get(shop) {
      const rows = await call(`${eq(shop)}&select=*`, { method: "GET" });
      return rows?.[0] ?? null;
    },
    upsert(row) {
      return call("?on_conflict=shop_domain", {
        method: "POST",
        headers: { prefer: "resolution=merge-duplicates,return=minimal" },
        body: JSON.stringify(row),
      });
    },
    /** `where` adds PostgREST filters, e.g. { installed_at: "lte.2026-11-23T09:00:00Z" }. */
    update(shop, patch, where = {}) {
      const extra = Object.entries(where).map(([k, v]) => `&${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("");
      return call(`${eq(shop)}${extra}`, { method: "PATCH", headers: { prefer: "return=minimal" }, body: JSON.stringify(patch) });
    },
    remove(shop) {
      return call(eq(shop), { method: "DELETE", headers: { prefer: "return=minimal" } });
    },
  };
}

/** DELETE every row of `table` matching `filters` ({ column: value }, all eq). */
export async function deleteRows({ url, key, fetch = globalThis.fetch }, table, filters) {
  const q = Object.entries(filters).map(([k, v]) => `${encodeURIComponent(k)}=eq.${encodeURIComponent(v)}`).join("&");
  if (!q) throw new Error("deleteRows needs a filter");
  const res = await fetch(`${url.replace(/\/$/, "")}/rest/v1/${table}?${q}`, {
    method: "DELETE",
    headers: { apikey: key, authorization: `Bearer ${key}`, prefer: "return=minimal" },
  });
  if (!res.ok) throw new Error(`Supabase DELETE ${table}: ${res.status} ${await res.text()}`);
}

/** Every object path under `prefix` in a Storage bucket, folders walked. */
export async function listStored({ url, key, fetch = globalThis.fetch }, bucket, prefix) {
  const base = url.replace(/\/$/, "");
  const out = [];
  const walk = async (dir) => {
    for (let offset = 0; ; offset += 1000) {
      const res = await fetch(`${base}/storage/v1/object/list/${bucket}`, {
        method: "POST",
        headers: { apikey: key, authorization: `Bearer ${key}`, "content-type": "application/json" },
        body: JSON.stringify({ prefix: dir, limit: 1000, offset }),
      });
      if (!res.ok) throw new Error(`Supabase storage list ${dir}: ${res.status}`);
      const items = (await res.json()) ?? [];
      for (const it of items) {
        const path = `${dir.replace(/\/$/, "")}/${it.name}`;
        if (it.id == null) await walk(path);
        else out.push(path);
      }
      if (items.length < 1000) return;
    }
  };
  await walk(prefix);
  return out;
}

/** Delete these object paths from a Storage bucket. */
export async function removeStored({ url, key, fetch = globalThis.fetch }, bucket, paths) {
  for (let i = 0; i < paths.length; i += 1000) {
    const res = await fetch(`${url.replace(/\/$/, "")}/storage/v1/object/${bucket}`, {
      method: "DELETE",
      headers: { apikey: key, authorization: `Bearer ${key}`, "content-type": "application/json" },
      body: JSON.stringify({ prefixes: paths.slice(i, i + 1000) }),
    });
    if (!res.ok) throw new Error(`Supabase storage delete: ${res.status}`);
  }
}

/** engine ingest/shopify_orders.customer_key: sha256(lower(trim(email)) | client_id), or null. */
export function customerKey(email, clientId) {
  const e = String(email ?? "").trim().toLowerCase();
  return e ? createHash("sha256").update(`${e}|${clientId}`).digest("hex") : null;
}

/** Parse one cookie from a Cookie header. */
export function readCookie(header, name) {
  for (const part of String(header ?? "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}
