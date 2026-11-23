import { BILLING_RETURN_URI, decryptToken, graphql, shopsTable, validShop } from "../../lib/shopify.js";

/**
 * Shopify Billing for Hubricon: one usage line item, nothing recurring.
 *
 * createSubscription() is called by api/shopify/auth.js right after the install.
 * The merchant approves it on Shopify's confirmation page, which returns them to
 *   GET /api/shopify/billing?shop=<shop>.myshopify.com&charge_id=...
 * and this handler asks Shopify (not the query string) whether the subscription
 * is active before it marks the shop active.
 *
 * The cap is Shopify's capped amount: Hubricon can never bill past it in a
 * 30-day cycle, and only the merchant can raise it.
 */

export const TERMS =
  "20% of proven profit Shopify or a randomised test confirmed, 10% of estimated profit, only on new highs of your cumulative proven profit; each proven dollar is billable for 12 months; dispute any dollar and it is refunded.";

export const PLAN_NAME = "Hubricon: paid only on proven profit";

const CREATE = `mutation HubriconSubscribe($name: String!, $returnUrl: URL!, $test: Boolean, $lineItems: [AppSubscriptionLineItemInput!]!) {
  appSubscriptionCreate(name: $name, returnUrl: $returnUrl, test: $test, lineItems: $lineItems) {
    userErrors { field message }
    confirmationUrl
    appSubscription { id lineItems { id plan { pricingDetails { __typename } } } }
  }
}`;

const ACTIVE = `query HubriconActive {
  currentAppInstallation { activeSubscriptions { id name status test lineItems { id } } }
}`;

export function capUsd(env = process.env) {
  const n = Number(env.SHOPIFY_USAGE_CAP_USD);
  return Number.isFinite(n) && n > 0 ? n : 500;
}

export function isTest(env = process.env) {
  return env.SHOPIFY_BILLING_LIVE !== "1";
}

/**
 * appSubscriptionCreate with one usage line item. Stores the usage line item id
 * and the cap on the shop row (opts.table), and returns { confirmationUrl,
 * subscriptionId, usageLineItemId }.
 */
export async function createSubscription(shop, token, opts = {}) {
  const env = opts.env ?? process.env;
  const cap = opts.capUsd ?? capUsd(env);
  const test = opts.test ?? isTest(env);
  const data = await graphql({
    shop,
    token,
    fetch: opts.fetch,
    query: CREATE,
    variables: {
      name: PLAN_NAME,
      returnUrl: `${opts.returnUrl ?? BILLING_RETURN_URI}?shop=${encodeURIComponent(shop)}`,
      test,
      lineItems: [{ plan: { appUsagePricingDetails: { terms: TERMS, cappedAmount: { amount: cap, currencyCode: "USD" } } } }],
    },
  });
  const out = data?.appSubscriptionCreate;
  if (out?.userErrors?.length) throw new Error(`appSubscriptionCreate: ${out.userErrors.map((e) => e.message).join("; ")}`);
  const items = out?.appSubscription?.lineItems ?? [];
  const usage = items.find((li) => li.plan?.pricingDetails?.__typename === "AppUsagePricing") ?? items[0];
  if (!out?.confirmationUrl || !usage?.id) throw new Error("appSubscriptionCreate returned no confirmation URL or line item");
  if (opts.table) await opts.table.update(shop, { usage_line_item_id: usage.id, cap_usd: cap });
  return { confirmationUrl: out.confirmationUrl, subscriptionId: out.appSubscription.id, usageLineItemId: usage.id };
}

function defaults() {
  return { env: process.env, fetch: globalThis.fetch };
}

/** The billing return URL. Exported as a factory so the tests inject env and fetch. */
export function billingHandler({ env, fetch } = defaults()) {
  return async function GET(request) {
    const missing = ["SHOPIFY_API_KEY", "SHOPIFY_TOKEN_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((n) => !env[n]);
    if (missing.length) return new Response(`Server not configured: missing ${missing.join(", ")}`, { status: 500 });
    const shop = validShop(new URL(request.url).searchParams.get("shop"));
    if (!shop) return new Response("Bad shop", { status: 400 });

    const table = shopsTable({ url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch });
    const row = await table.get(shop);
    if (!row?.token_enc || row.status === "uninstalled") return new Response("Not installed", { status: 404 });

    const token = decryptToken(row.token_enc, env.SHOPIFY_TOKEN_KEY, shop);
    const data = await graphql({ shop, token, query: ACTIVE, fetch });
    const subs = data?.currentAppInstallation?.activeSubscriptions ?? [];
    const sub = subs.find((s) => s.status === "ACTIVE" && s.lineItems?.some((li) => li.id === row.usage_line_item_id));
    if (!sub) {
      // Declined, or not approved yet: leave the row as it is and say so.
      return new Response("The Hubricon subscription is not active. Open the app in your Shopify admin to approve it.", {
        status: 402,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
    await table.update(shop, { status: "active" });
    return new Response(null, { status: 302, headers: { location: `https://${shop}/admin/apps/${env.SHOPIFY_API_KEY}` } });
  };
}

export const GET = (request) => billingHandler()(request);
