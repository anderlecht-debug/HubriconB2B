/**
 * One-shot Stripe setup for Hubricon.
 *
 *   npm install
 *   STRIPE_SECRET_KEY=sk_... npm run stripe:setup
 *
 * Idempotent: reuses the product/price/webhook endpoint when they already exist.
 */
import Stripe from "stripe";

const key = process.env.STRIPE_SECRET_KEY;
if (!key) {
  console.error("Set STRIPE_SECRET_KEY before running (a restricted key with write access to Products, Prices, and Webhook Endpoints is enough).");
  process.exit(1);
}
const stripe = new Stripe(key);

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
const WEBHOOK_EVENTS = [
  "invoice.paid",
  "invoice.payment_failed",
  "customer.subscription.deleted",
];

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

let endpoint = (await stripe.webhookEndpoints.list({ limit: 100 })).data.find(
  (e) => e.url === WEBHOOK_URL
);
if (!endpoint) {
  endpoint = await stripe.webhookEndpoints.create({
    url: WEBHOOK_URL,
    enabled_events: WEBHOOK_EVENTS,
  });
  console.log("Created webhook endpoint:", endpoint.id);
  console.log("\nSIGNING SECRET — add to Vercel env as STRIPE_WEBHOOK_SECRET:");
  console.log(endpoint.secret);
} else {
  console.log("Webhook endpoint already exists:", endpoint.id);
  console.log("(Signing secret is only revealed at creation — find it in the Stripe dashboard under Developers → Webhooks.)");
}

console.log(`
Client onboarding (after a discovery call) — create the customer, then:

  stripe.subscriptions.create({
    customer: "<customer id>",
    items: [{ price: "${price.id}" }],
    collection_method: "send_invoice",
    days_until_due: 7,
    payment_settings: { payment_method_types: ["us_bank_account"] },
  })

Stripe emails the invoice; the client pays by ACH (0.8% capped at $5,
vs ~$174 by card). When it's paid, the webhook provisions their workspace.
`);
