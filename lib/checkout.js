/**
 * The self-serve offer: $1,000 a month by card, paid on /start with nobody
 * from Hubricon in the loop.
 *
 * This file holds everything about it that needs no network: the plan's
 * constants, the Checkout Session the pay button asks Stripe for, and the two
 * links a paying client is handed (their upload page and their cancel link).
 * api/checkout.js, api/checkout-session.js, api/billing.js and
 * lib/provision.js all build on it, and lib/checkout.test.mjs runs it.
 *
 * Both links are derived, not stored:
 *
 *   upload token = HMAC(CHECKOUT_TOKEN_SECRET, "upload:" + Checkout session id)
 *   cancel key   = HMAC(CHECKOUT_TOKEN_SECRET, "billing:" + client id)
 *
 * so the webhook and the page that the buyer lands back on, which race each
 * other, both arrive at the same upload link without either having to read
 * what the other wrote. Only the token's SHA-256 is stored (private.
 * intake_tokens), exactly as for every other upload link.
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const PLAN = "self_serve";
export const MONTHLY_FEE_USD = 1000;
export const PLATFORMS = ["shopify", "amazon", "both"];
export const DEFAULT_BASE = "https://www.hubricon.com";
export const START_PATH = "/start";

// Said to a buyer whenever the button cannot take a card. /start prints the
// same sentence (State D), so the page and the API never disagree.
export const NOT_SWITCHED_ON = "Card payment is not switched on yet. Nothing was charged.";

// Everything the whole chain needs: the button, the webhook that provisions,
// and the email with the upload link. The button refuses to take a card unless
// all of it is there, so nobody pays into a half-configured deploy.
export const CHECKOUT_ENV = [
  "STRIPE_SECRET_KEY",
  "STRIPE_CHECKOUT_PRICE_ID",
  "STRIPE_WEBHOOK_SECRET",
  "CHECKOUT_TOKEN_SECRET",
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "RESEND_API_KEY",
];

export function missingForCheckout(env) {
  return CHECKOUT_ENV.filter((name) => !env[name]);
}

/** The site's own address, from the same variable the engine builds its links with. */
export function siteBase(env = {}) {
  const raw = String(env.INTAKE_BASE_URL || DEFAULT_BASE).trim().replace(/\/+$/, "");
  return /^https?:\/\/[^\s/]+/i.test(raw) ? raw : DEFAULT_BASE;
}

export function normalPlatform(value) {
  const v = String(value ?? "").trim().toLowerCase();
  return PLATFORMS.includes(v) ? v : null;
}

/**
 * Where a buyer who backs out of the card page is sent: a path on this site
 * and nothing else. Anything that could leave the site (a scheme, a host, a
 * protocol-relative //) falls back to /start.
 */
export function returnPath(value) {
  if (typeof value !== "string") return START_PATH;
  let path = value.trim();
  if (/^https?:\/\//i.test(path)) return START_PATH;
  path = path.split(/[?#]/)[0];
  if (path.length > 200 || !/^\/[A-Za-z0-9\-._~/]*$/.test(path) || path.startsWith("//")) return START_PATH;
  return path;
}

/** The path of a same-site Referer, for a plain form post that names no return page. */
export function refererPath(referer, base) {
  if (!referer) return null;
  try {
    const from = new URL(referer);
    return from.origin === new URL(base).origin ? from.pathname : null;
  } catch {
    return null;
  }
}

const PLATFORM_FIELD = {
  key: "platform",
  label: { type: "custom", custom: "Where do you sell?" },
  type: "dropdown",
  dropdown: {
    options: [
      { label: "Shopify", value: "shopify" },
      { label: "Amazon", value: "amazon" },
      { label: "Both", value: "both" },
    ],
  },
};

/**
 * The Checkout Session behind "Start my Profit Record". One subscription line
 * at the $1,000 price, card only. Stripe collects the email and the card; the
 * one thing the engine must know before a file arrives is where they sell
 * (it decides which files the upload page asks for), so that is asked on the
 * card page only when /start has not already told us. No trial, no coupon
 * field, no consent box: nothing is bundled into the payment.
 */
export function checkoutParams({ priceId, base, platform, from }) {
  const sells = normalPlatform(platform);
  const metadata = { hubricon_plan: PLAN, ...(sells ? { hubricon_platform: sells } : {}) };
  const back = new URLSearchParams({ checkout: "cancelled", ...(sells ? { p: sells } : {}) });
  return {
    mode: "subscription",
    line_items: [{ price: priceId, quantity: 1 }],
    payment_method_types: ["card"],
    success_url: `${base}${START_PATH}?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}${returnPath(from)}?${back}`,
    metadata,
    subscription_data: { metadata },
    ...(sells ? {} : { custom_fields: [PLATFORM_FIELD] }),
  };
}

/** Where a paid session says they sell: what /start sent, else the card page's own question. */
export function readPlatform(session) {
  const posted = normalPlatform(session?.metadata?.hubricon_platform);
  if (posted) return posted;
  const field = (session?.custom_fields ?? []).find((f) => f?.key === "platform");
  return normalPlatform(field?.dropdown?.value) ?? "both";
}

/** Is this Checkout Session one of ours: a subscription bought on the self-serve button? */
export function isSelfServe(session) {
  return Boolean(session) && session.mode === "subscription" && session.metadata?.hubricon_plan === PLAN;
}

export const SESSION_ID = /^cs_(test|live)_[A-Za-z0-9]{8,250}$/;

const hmac = (secret, text) => createHmac("sha256", secret).update(text).digest("base64url");

/** The upload link's token for one paid Checkout Session. 43 characters, the same every time it is asked. */
export function uploadToken(secret, sessionId) {
  if (!secret) throw new Error("CHECKOUT_TOKEN_SECRET not set");
  return hmac(secret, `upload:${sessionId}`);
}

/** What private.intake_tokens stores for a token (lib/token.js hashes the same way when a link is opened). */
export const tokenHash = (token) => createHash("sha256").update(token).digest("hex");

export const uploadUrl = (base, token) => `${base}/intake?t=${token}`;

export function billingKey(secret, clientId) {
  if (!secret) throw new Error("CHECKOUT_TOKEN_SECRET not set");
  return hmac(secret, `billing:${clientId}`);
}

/** The cancel link in the welcome email. It needs no sign-in and never expires. */
export function billingUrl(base, secret, clientId) {
  return `${base}/api/billing?c=${clientId}&k=${billingKey(secret, clientId)}`;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function verifyBillingKey(secret, clientId, key) {
  if (!secret || typeof clientId !== "string" || typeof key !== "string" || !UUID.test(clientId)) return false;
  const want = Buffer.from(billingKey(secret, clientId));
  const got = Buffer.from(key);
  return want.length === got.length && timingSafeEqual(want, got);
}

/**
 * Ask Stripe for the card page. Resolves to
 *   { ok: true, url }                         the hosted Checkout page
 *   { ok: false, status: 503, error, message } not switched on (a key is missing)
 *   { ok: false, status: 502, error, message } Stripe refused or could not be reached
 * `makeStripe` is only called once the environment is complete.
 */
export async function createCheckout({ env, makeStripe, platform, from, referer }) {
  const missing = missingForCheckout(env);
  if (missing.length > 0) {
    return { ok: false, status: 503, error: "not_configured", message: NOT_SWITCHED_ON, missing };
  }
  const base = siteBase(env);
  const params = checkoutParams({
    priceId: env.STRIPE_CHECKOUT_PRICE_ID,
    base,
    platform,
    from: from ?? refererPath(referer, base) ?? START_PATH,
  });
  try {
    const session = await makeStripe().checkout.sessions.create(params);
    if (!session?.url) throw new Error("Stripe returned no checkout URL");
    return { ok: true, url: session.url, id: session.id };
  } catch (err) {
    return {
      ok: false, status: 502, error: "stripe_error", detail: err?.message ?? String(err),
      message: "The card page could not be opened. Nothing was charged. Press the button again.",
    };
  }
}
