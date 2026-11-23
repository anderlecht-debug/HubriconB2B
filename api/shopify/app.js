import { createSubscription } from "./billing.js";
import {
  decryptToken,
  mandatesTable,
  readStored,
  shopsTable,
  signSession,
  validShop,
  verifyQueryHmac,
  verifySession,
} from "../../lib/shopify.js";

/**
 * The data behind /app (app.html), the page Shopify opens for an installed store
 * (shopify.app.toml application_url).
 *
 *   GET  /api/shopify/app?shop=...&hmac=...&timestamp=...[&host=...]
 *        Shopify signs that query. A valid, fresh one returns the store's page
 *        data and a one-hour session for the writes below. A GET may instead
 *        carry `Authorization: Bearer <session>` (a reload).
 *   POST /api/shopify/app   Authorization: Bearer <session>
 *        { action: "mandate", max_price_step_pct, price_moves_enabled, reorder_needs_tap }
 *        { action: "fee_answer", approved: true | false }
 *          A yes creates the capped usage charge (billing.js createSubscription) and
 *          returns { confirmation_url }, Shopify's page where the brand approves it.
 *
 * The figures come from what the engine already wrote: the look-back, the shadow
 * grades, the moves seen in the store, the fee statements (Supabase Storage,
 * intake/shopify/<shop>/...) and the shop's rows. Every block names what kind of
 * number it is, and the page prints that name beside every number:
 *   hindsight           the look-back: nothing was written down before the fact
 *   sealed call         a shadow call, sealed before its week; nothing executed
 *   observed, not ours  a move someone else made, seen in the data; never billed
 *   proven              a measured dollar on the Profit Record, the only thing a fee is charged on
 */

export const LABELS = Object.freeze({
  lookback: "hindsight",
  shadow: "sealed call",
  observed: "observed, not ours",
  fee: "proven",
  tap: "awaiting your tap",
});

export const MAX_STEP_PCT = 5; // terms.html §6; supabase/migrations/20261124000001 checks it too
const MAX_QUERY_AGE_S = 60 * 60;
const BUCKET = "intake";

function defaults() {
  return { env: process.env, fetch: globalThis.fetch, now: () => Date.now() };
}

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

function bearer(request) {
  const h = request.headers.get("authorization") || "";
  return h.startsWith("Bearer ") ? h.slice(7).trim() : null;
}

/** The shop this request is for, proven, or null. */
export function authenticate(request, env, now) {
  const fromSession = verifySession(bearer(request), env.SHOPIFY_API_SECRET, now);
  if (fromSession) return fromSession;
  if (request.method !== "GET") return null; // a write needs the session, never a replayable query
  const params = new URL(request.url).searchParams;
  const shop = validShop(params.get("shop"));
  const ts = Number(params.get("timestamp"));
  if (!shop || !params.has("hmac") || !Number.isFinite(ts) || Math.abs(now / 1000 - ts) > MAX_QUERY_AGE_S) return null;
  return verifyQueryHmac(params, env.SHOPIFY_API_SECRET) ? shop : null;
}

/** The brand's limits as the engine reads them (engine mandate.settings). */
export function mandateSettings(row) {
  const pct = row?.max_price_step_pct == null ? MAX_STEP_PCT : Number(row.max_price_step_pct);
  return {
    max_price_step_pct: Math.max(0, Math.min(pct, MAX_STEP_PCT)),
    price_moves_enabled: !!row?.price_moves_enabled,
    reorder_needs_tap: row?.reorder_needs_tap ?? true,
    shadow_weeks: Number(row?.shadow_weeks) || 4,
  };
}

/** Validate the settings form. Returns { row } or { error }. */
export function parseMandate(body) {
  const pct = Number(body?.max_price_step_pct);
  if (!Number.isFinite(pct) || pct <= 0 || pct > MAX_STEP_PCT) {
    return { error: `The largest price step must be more than 0% and at most ${MAX_STEP_PCT}%.` };
  }
  for (const k of ["price_moves_enabled", "reorder_needs_tap"]) {
    if (typeof body?.[k] !== "boolean") return { error: `${k} must be true or false.` };
  }
  return {
    row: {
      max_price_step_pct: Math.round(pct * 100) / 100,
      price_moves_enabled: body.price_moves_enabled,
      reorder_needs_tap: body.reorder_needs_tap,
    },
  };
}

function shadowEnds(installedAt, weeks) {
  const t = Date.parse(installedAt ?? "");
  return Number.isFinite(t) ? new Date(t + weeks * 7 * 86400000).toISOString().slice(0, 10) : null;
}

/** Everything the page shows, each block labelled with the kind of number it holds. */
export async function pageData(shop, { env, fetch, now }) {
  const db = { url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch };
  const row = await shopsTable(db).get(shop);
  if (!row || row.status === "uninstalled") return null;
  const limits = mandateSettings(await mandatesTable(db).get(shop));
  const base = `shopify/${shop}`;
  const [lookback, shadow, observed, fee, tap] = await Promise.all(
    ["lookback.json", "shadow/summary.json", "ledger.json", "fee.json", "awaiting_tap.json"].map((p) =>
      readStored(db, BUCKET, `${base}/${p}`).catch(() => null),
    ),
  );
  const ends = shadowEnds(row.installed_at, limits.shadow_weeks);
  const latest = fee?.closing ?? fee?.statements?.at?.(-1) ?? null;
  return {
    shop,
    status: row.status,
    lookback: { label: LABELS.lookback, data: lookback },
    shadow: { label: LABELS.shadow, data: shadow },
    observed: { label: LABELS.observed, data: observed },
    fee: {
      label: LABELS.fee,
      statement: latest,
      lines: latest?.explanation ?? [],
      cap_usd: Number(row.cap_usd ?? 500),
      peak_usd: Number(row.peak_usd ?? 0),
    },
    awaiting_tap: { label: LABELS.tap, data: tap },
    fee_question: {
      state: row.fee_question ?? "none",
      billing_status: row.billing_status ?? "none",
      first_proven_usd: row.first_proven_usd ?? null,
      label: LABELS.fee,
    },
    mandate: {
      ...limits,
      write_access: String(row.scopes ?? "").split(",").map((s) => s.trim()).includes("write_products"),
      shadow_ends: ends,
      in_shadow: ends === null || new Date(now()).toISOString().slice(0, 10) < ends,
    },
  };
}

export function appHandler({ env, fetch, now = () => Date.now() } = defaults()) {
  return async function handle(request) {
    const missing = ["SHOPIFY_API_SECRET", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((n) => !env[n]);
    if (missing.length) return json({ error: `Server not configured: missing ${missing.join(", ")}` }, 500);
    const shop = authenticate(request, env, now());
    if (!shop) return json({ error: "Open Hubricon from your Shopify admin." }, 401);
    const deps = { env, fetch, now };

    if (request.method === "GET") {
      const data = await pageData(shop, deps);
      if (!data) return json({ error: "Hubricon is not installed on this store." }, 404);
      return json({ ...data, session: signSession(shop, env.SHOPIFY_API_SECRET, now()) });
    }
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Bad JSON" }, 400);
    }
    const db = { url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch };
    const row = await shopsTable(db).get(shop);
    if (!row || row.status === "uninstalled") return json({ error: "Hubricon is not installed on this store." }, 404);

    if (body?.action === "mandate") {
      const { row: limits, error } = parseMandate(body);
      if (error) return json({ error }, 400);
      await mandatesTable(db).upsert({ shop_domain: shop, ...limits });
      return json({ ok: true, mandate: mandateSettings(limits) });
    }
    if (body?.action === "fee_answer") {
      if (typeof body.approved !== "boolean") return json({ error: "approved must be true or false." }, 400);
      const state = row.fee_question ?? "none";
      // A yes whose Shopify charge is not approved yet may tap again: the charge is re-issued.
      const retry = state === "approved" && body.approved && row.billing_status !== "active";
      if (state !== "ask" && !retry) return json({ error: "There is no open fee question." }, 409);
      if (!retry) {
        const patch = { fee_question: body.approved ? "approved" : "declined", fee_answered_at: new Date(now()).toISOString() };
        await shopsTable(db).update(shop, patch);
      }
      if (!body.approved) return json({ ok: true, fee_question: "declined" });
      // Only now, on the brand's yes, is the capped usage charge created; Shopify's
      // confirmation page is where the brand approves it.
      try {
        const token = decryptToken(row.token_enc, env.SHOPIFY_TOKEN_KEY, shop);
        const sub = await createSubscription(shop, token, { env, fetch, table: shopsTable(db) });
        return json({ ok: true, fee_question: "approved", confirmation_url: sub.confirmationUrl });
      } catch {
        return json({ error: "Your yes is recorded, but Shopify did not create the charge. Tap Yes again to retry.",
                      fee_question: "approved" }, 502);
      }
    }
    return json({ error: "Unknown action" }, 400);
  };
}

export const GET = (request) => appHandler()(request);
export const POST = (request) => appHandler()(request);
