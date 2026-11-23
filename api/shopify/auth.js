import {
  SCOPES,
  STATE_COOKIE,
  authorizeUrl,
  encryptToken,
  exchangeCode,
  hasScopes,
  readCookie,
  shopsTable,
  signState,
  validShop,
  verifyQueryHmac,
  verifyState,
} from "../../lib/shopify.js";
import { capUsd } from "./billing.js";

/**
 * The install, both legs, on one URL (shopify.app.toml's redirect_urls):
 *
 *   GET /api/shopify/auth?shop=x.myshopify.com[&hmac&timestamp...]
 *       -> 302 to the store's authorize page, with a signed state and its nonce in a cookie
 *   GET /api/shopify/auth?code=...&shop=...&state=...&hmac=...&timestamp=...
 *       -> verify HMAC and state, trade the code for an offline token, store it
 *          encrypted, 302 to the app. Ingest, the free look-back and shadow mode
 *          start from here. No billing is created at install: the capped usage
 *          charge is created only when the brand says yes to the fee question
 *          (api/shopify/app.js, action fee_answer).
 *
 * The token is read-only (lib/shopify.js SCOPES). Nothing here acts on the store.
 */

const MAX_CALLBACK_AGE_S = 24 * 60 * 60;

function defaults() {
  return { env: process.env, fetch: globalThis.fetch, now: () => Date.now() };
}

const text = (body, status) => new Response(body, { status, headers: { "content-type": "text/plain; charset=utf-8" } });

export function authHandler({ env, fetch, now = () => Date.now() } = defaults()) {
  return async function GET(request) {
    const missing = ["SHOPIFY_API_KEY", "SHOPIFY_API_SECRET", "SHOPIFY_TOKEN_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter(
      (n) => !env[n],
    );
    if (missing.length) return text(`Server not configured: missing ${missing.join(", ")}`, 500);

    const params = new URL(request.url).searchParams;
    const shop = validShop(params.get("shop"));
    if (!shop) return text("Bad shop: expected <store>.myshopify.com", 400);

    // A query that carries an hmac must carry a valid one, on either leg.
    if (params.has("hmac") && !verifyQueryHmac(params, env.SHOPIFY_API_SECRET)) return text("Bad signature", 401);

    if (!params.has("code")) {
      const { state, nonce } = signState(shop, env.SHOPIFY_API_SECRET, now());
      return new Response(null, {
        status: 302,
        headers: {
          location: authorizeUrl({ shop, apiKey: env.SHOPIFY_API_KEY, state }),
          "set-cookie": `${STATE_COOKIE}=${nonce}; Path=/api/shopify; Max-Age=600; HttpOnly; Secure; SameSite=Lax`,
        },
      });
    }

    // The callback: Shopify always signs it.
    if (!params.has("hmac")) return text("Bad signature", 401);
    const ts = Number(params.get("timestamp"));
    if (!Number.isFinite(ts) || Math.abs(now() / 1000 - ts) > MAX_CALLBACK_AGE_S) return text("Stale request", 401);
    const nonce = readCookie(request.headers.get("cookie"), STATE_COOKIE);
    if (!verifyState(params.get("state"), { shop, nonce, secret: env.SHOPIFY_API_SECRET, now: now() })) {
      return text("This install link has expired. Start the install again from the Shopify App Store.", 403);
    }

    let grant;
    try {
      grant = await exchangeCode({ shop, code: params.get("code"), apiKey: env.SHOPIFY_API_KEY, apiSecret: env.SHOPIFY_API_SECRET, fetch });
    } catch {
      return text("Shopify did not accept the install code. Start the install again.", 502);
    }
    if (!hasScopes(grant.scope, SCOPES)) return text("The install did not grant the read access Hubricon needs.", 403);

    const table = shopsTable({ url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch });
    await table.upsert({
      shop_domain: shop,
      token_enc: encryptToken(grant.access_token, env.SHOPIFY_TOKEN_KEY, shop),
      scopes: grant.scope,
      status: "active",
      billing_status: "none",
      usage_line_item_id: null,
      installed_at: new Date(now()).toISOString(),
      uninstalled_at: null,
      cap_usd: capUsd(env),
    });

    return new Response(null, {
      status: 302,
      headers: {
        location: `https://${shop}/admin/apps/${env.SHOPIFY_API_KEY}`,
        "set-cookie": `${STATE_COOKIE}=; Path=/api/shopify; Max-Age=0; HttpOnly; Secure; SameSite=Lax`,
      },
    });
  };
}

export const GET = (request) => authHandler()(request);
