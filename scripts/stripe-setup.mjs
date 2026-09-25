/**
 * One-shot Stripe setup for Hubricon.
 *
 *   npm install
 *   STRIPE_SECRET_KEY=sk_... npm run stripe:setup
 *
 * Idempotent: reuses the product, price and webhook endpoint when they exist,
 * and brings an existing endpoint's events up to what the handler reads.
 * Ends with a checklist of what it could verify and what only you can do.
 */
import Stripe from "stripe";
import { WEBHOOK_EVENTS } from "../lib/stripe_events.js";

const key = process.env.STRIPE_SECRET_KEY;
if (!key) {
  console.error("Set STRIPE_SECRET_KEY before running. A restricted key needs write access to Products, " +
                "Prices, Webhook Endpoints, Customers, Subscriptions, Invoices and Credit Notes, and read " +
                "access to Payment Method Configurations.");
  process.exit(1);
}
const stripe = new Stripe(key);
const live = /^(sk|rk)_live_/.test(key);

const PRODUCT_NAME = "Hubricon Managed Profit";
// The product was created under this name before the 2026-09-10 repositioning.
// It is found by either name and renamed in place, never duplicated: the live
// STRIPE_PRICE_ID hangs off it.
const LEGACY_PRODUCT_NAME = "Hubricon Quantitative CFO Protocol";
const PRODUCT_DESCRIPTION = "$6,000 a month, flat — proven or void: an invoice the client's Profit Record has not covered is void.";
const MONTHLY_USD_CENTS = 600000; // $6,000.00 / month
// www, never the apex: hubricon.com 308-redirects and Stripe treats
// redirected webhook deliveries as failures.
const WEBHOOK_URL = "https://www.hubricon.com/api/stripe-webhook";

const checks = [];
const check = (ok, what) => checks.push(`${ok ? "  ok  " : "  !!  "} ${what}`);

console.log(`Stripe account in ${live ? "LIVE" : "TEST"} mode.\n`);

const products = (await stripe.products.list({ active: true, limit: 100 })).data;
let product = products.find((p) => p.name === PRODUCT_NAME) || products.find((p) => p.name === LEGACY_PRODUCT_NAME);
if (!product) {
  product = await stripe.products.create({ name: PRODUCT_NAME, description: PRODUCT_DESCRIPTION });
  console.log("Created product:", product.id);
} else if (product.name !== PRODUCT_NAME || product.description !== PRODUCT_DESCRIPTION) {
  product = await stripe.products.update(product.id, { name: PRODUCT_NAME, description: PRODUCT_DESCRIPTION });
  console.log("Renamed product in place:", product.id);
} else {
  console.log("Product already exists:", product.id);
}
check(product.name === PRODUCT_NAME, `product "${product.name}" (${product.id})`);

let price = (await stripe.prices.list({ product: product.id, active: true, limit: 100 })).data.find(
  (p) => p.unit_amount === MONTHLY_USD_CENTS && p.recurring?.interval === "month" && p.currency === "usd"
);
if (!price) {
  price = await stripe.prices.create({
    product: product.id,
    unit_amount: MONTHLY_USD_CENTS,
    currency: "usd",
    recurring: { interval: "month" },
    nickname: "Managed Profit — monthly",
  });
  console.log("Created price:", price.id);
} else {
  console.log("Price already exists:", price.id);
}
check(true, `price ${price.id}: $6,000.00 a month`);

// The endpoint pins the SDK's API version at creation, so event payloads come
// in the shape lib/stripe_events.js and the engine (billing.STRIPE_VERSION) read.
let endpoint = (await stripe.webhookEndpoints.list({ limit: 100 })).data.find((e) => e.url === WEBHOOK_URL);
if (!endpoint) {
  endpoint = await stripe.webhookEndpoints.create({
    url: WEBHOOK_URL,
    enabled_events: WEBHOOK_EVENTS,
    api_version: Stripe.API_VERSION,
    description: "Hubricon: invoice mirror, the hold for the gate, client status",
  });
  console.log("Created webhook endpoint:", endpoint.id);
  console.log("\nSIGNING SECRET — add to Vercel (Production) as STRIPE_WEBHOOK_SECRET, then redeploy:");
  console.log(endpoint.secret);
} else {
  const wants = new Set(WEBHOOK_EVENTS);
  const has = new Set(endpoint.enabled_events);
  const missing = [...wants].filter((e) => !has.has(e) && !has.has("*"));
  if (missing.length || endpoint.status !== "enabled") {
    endpoint = await stripe.webhookEndpoints.update(endpoint.id, {
      enabled_events: [...new Set([...endpoint.enabled_events.filter((e) => e !== "*"), ...wants])],
      disabled: false,
    });
    console.log(`Webhook endpoint ${endpoint.id} updated: ${missing.length ? `added ${missing.join(", ")}` : "re-enabled"}.`);
  } else {
    console.log("Webhook endpoint already exists with every event:", endpoint.id);
  }
  console.log("(Its signing secret is only revealed at creation: Developers → Webhooks → the endpoint → Reveal.)");
}
const subscribed = new Set(endpoint.enabled_events);
check(endpoint.status === "enabled" && WEBHOOK_EVENTS.every((e) => subscribed.has(e) || subscribed.has("*")),
      `webhook ${endpoint.id} → ${WEBHOOK_URL}, ${WEBHOOK_EVENTS.length} events, ${endpoint.status}`);
if (endpoint.api_version && endpoint.api_version !== Stripe.API_VERSION) {
  checks.push(`  --   webhook payloads arrive at ${endpoint.api_version}; the handler reads fields common to both ` +
              `versions, so this is fine (a new endpoint would pin ${Stripe.API_VERSION})`);
}

// Invoices go out as ACH only (us_bank_account). If ACH Direct Debit is not
// on for the account, the day-30 pass cannot create a subscription.
try {
  const configs = (await stripe.paymentMethodConfigurations.list({ limit: 20 })).data;
  const ach = configs.some((c) => c.active !== false && c.us_bank_account?.available);
  check(ach, ach ? "ACH Direct Debit is available for invoices"
                 : "ACH Direct Debit is not showing as available: check Settings → Payment methods → ACH Direct Debit");
} catch (err) {
  checks.push(`  ??   could not read payment method settings (${err.message.slice(0, 80)}); ` +
              "confirm ACH Direct Debit is on under Settings → Payment methods");
}

console.log(`
Checks:
${checks.join("\n")}

Only you can do these (values never go in chat or in the repo):

  1. The hourly operator is the only code that starts, sends, voids or refunds a
     bill. Give it the key and the price, in GitHub → Settings → Environments →
     Production (gh prompts for the value):

       gh secret set STRIPE_SECRET_KEY --env Production
       gh secret set STRIPE_PRICE_ID   --env Production --body ${price.id}

  2. Vercel (hubricon-b2-b → Settings → Environment Variables, Production):
     STRIPE_SECRET_KEY (with Invoices: write, for the hold) and
     STRIPE_WEBHOOK_SECRET. Redeploy after changing either.

  3. Then: cd engine && uv run hubricon promises

Never create a subscription or an invoice by hand in the dashboard. Record the
client's yes with \`hubricon retainer <client>\`; the operator's day-30 pass
checks the Profit Record and starts billing only if it clears, and every later
invoice waits at draft until the gate has judged it. \`hubricon cancel <client>\`
ends one.
`);
