/**
 * One-shot Stripe setup for Hubricon.
 *
 *   npm install
 *   npm run stripe:setup          (reads STRIPE_SECRET_KEY from .env)
 *
 * Idempotent: reuses the product, price and webhook endpoint when they exist,
 * and brings an existing endpoint's events up to what the handler reads.
 * STRIPE_PRICE_ID and a new endpoint's STRIPE_WEBHOOK_SECRET are written into
 * .env, never printed, so neither lands in a terminal log or a chat.
 * Ends with a checklist of what it could verify and what only you can do.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import Stripe from "stripe";
import { WEBHOOK_EVENTS } from "../lib/stripe_events.js";

const ENV_FILE = new URL("../.env", import.meta.url);

/** Set NAME=value in .env, replacing the line (or its commented example) if there is one. */
function remember(name, value) {
  const text = existsSync(ENV_FILE) ? readFileSync(ENV_FILE, "utf8") : "";
  const line = new RegExp(`^#?\\s*${name}=.*$`, "m");
  const next = line.test(text) ? text.replace(line, `${name}=${value}`)
                               : `${text}${text.endsWith("\n") || !text ? "" : "\n"}${name}=${value}\n`;
  if (next !== text) writeFileSync(ENV_FILE, next);
  return next !== text;
}

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
// HUBRICON_SPEC.md, "Offer, attribution and the scoreboard": the offer is one line.
const PRODUCT_DESCRIPTION = "More profit than our bill every month, or you don't pay: a month is invoiced only " +
                            "when your Profit Record measured more than the $6,000 fee.";
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
if (remember("STRIPE_PRICE_ID", price.id)) console.log("STRIPE_PRICE_ID written to .env");

// The endpoint pins the SDK's API version at creation, so event payloads come
// in the shape lib/stripe_events.js and the engine (billing.STRIPE_VERSION) read.
// An endpoint made without a pinned version takes the account's default, which
// moves with the account and cannot be changed afterwards, so it is replaced:
// a new pinned one is made beside it, and the old one is deleted once the
// website verifies with the new secret.
const atUrl = (await stripe.webhookEndpoints.list({ limit: 100 })).data.filter((e) => e.url === WEBHOOK_URL);
let endpoint = atUrl.find((e) => e.api_version === Stripe.API_VERSION && e.status === "enabled")
            ?? atUrl.find((e) => e.api_version === Stripe.API_VERSION);
const unpinned = atUrl.filter((e) => e !== endpoint);
if (!endpoint) {
  endpoint = await stripe.webhookEndpoints.create({
    url: WEBHOOK_URL,
    enabled_events: WEBHOOK_EVENTS,
    api_version: Stripe.API_VERSION,
    description: "Hubricon: invoice mirror, the hold for the gate, client status",
  });
  console.log("Created webhook endpoint:", endpoint.id, `(pinned to ${Stripe.API_VERSION})`);
  remember("STRIPE_WEBHOOK_SECRET", endpoint.secret);
  console.log("Its signing secret is written to .env as STRIPE_WEBHOOK_SECRET. Vercel needs it, then a redeploy.");
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
for (const old of unpinned) {
  checks.push(`  --   ${old.id} also posts to ${WEBHOOK_URL} (${old.api_version ?? "account default version"}, ` +
              `${old.status}): delete it once the site verifies with the new secret`);
}

// Invoices go out as ACH only: each subscription and invoice names
// us_bank_account itself, so what decides it is the account's capability, not
// the payment-method settings page (which governs Checkout and Elements and
// may show ACH as off while invoices take it).
try {
  const account = await stripe.accounts.retrieve();
  const ach = account.capabilities?.us_bank_account_ach_payments;
  check(ach === "active", ach === "active" ? "ACH Direct Debit is active on the account"
        : `ACH Direct Debit is ${ach ?? "missing"}: Settings → Payment methods → ACH Direct Debit → Turn on`);
} catch (err) {
  checks.push(`  ??   could not read the account (${err.message.slice(0, 80)}); ` +
              "confirm ACH Direct Debit is on under Settings → Payment methods");
}

console.log(`
Checks:
${checks.join("\n")}

Then, from .env (values never go in chat or in the repo):

  1. The hourly operator is the only code that starts, sends, voids or refunds a
     bill. Give it the key and the price, in GitHub's Production environment:

       node --env-file=.env -p process.env.STRIPE_SECRET_KEY | gh secret set STRIPE_SECRET_KEY --env Production
       gh secret set STRIPE_PRICE_ID --env Production --body ${price.id}

  2. Vercel (hubricon-b2-b, Production): STRIPE_SECRET_KEY (it places the hold,
     so it needs Invoices: write) and STRIPE_WEBHOOK_SECRET, then a redeploy.

  3. Then: cd engine && uv run hubricon promises

  4. Stripe's own customer emails, in the dashboard (no API reaches them):
     Settings → Billing → Subscriptions and emails: trial-ending and
     upcoming-renewal reminders OFF (each would announce a $6,000 bill before
     the Record has judged the month); Settings → Customer emails: successful
     payments and refunds ON; Settings → Branding: brand/stripe-mark-512.png
     as icon and logo, brand colour #0a0e17, accent #0b5fff (buttons: money);
     Settings → Public details: support email.

Never create a subscription or an invoice by hand in the dashboard. Record the
client's yes with \`hubricon retainer <client>\`; the operator's day-30 pass
checks the Profit Record and starts billing only if it clears, and every later
invoice waits at draft until the gate has judged it. \`hubricon cancel <client>\`
ends one.
`);
