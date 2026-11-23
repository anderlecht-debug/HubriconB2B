import { shopsTable, validShop, verifyWebhookHmac } from "../../lib/shopify.js";

/**
 * Shopify → Hubricon webhooks (shopify.app.toml subscribes these topics here):
 *
 *   app/uninstalled         mark the shop uninstalled and wipe its token
 *   customers/data_request  Hubricon asks for no customer PII (read_orders is
 *   customers/redact        read for totals, nothing about a customer is stored),
 *                           so there is nothing to return or erase: 200, logged
 *   shop/redact             48 hours after uninstall: delete the shop's rows
 *
 * A bad signature is 401, which is what Shopify's review checks for.
 */

// What shop/redact erases. A table added later that holds a store's data must
// reference shopify_shops(shop_domain) ON DELETE CASCADE.
export const SHOP_TABLES = ["shopify_shops"];

function defaults() {
  return { env: process.env, fetch: globalThis.fetch, log: console.log, now: () => Date.now() };
}

export function webhookHandler({ env, fetch, log = console.log, now = () => Date.now() } = defaults()) {
  return async function POST(request) {
    if (!env.SHOPIFY_API_SECRET || !env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
      return new Response("Server not configured", { status: 500 });
    }
    const raw = Buffer.from(await request.arrayBuffer());
    if (!verifyWebhookHmac(raw, request.headers.get("x-shopify-hmac-sha256"), env.SHOPIFY_API_SECRET)) {
      return new Response("Unauthorized", { status: 401 });
    }
    const topic = request.headers.get("x-shopify-topic");
    const shop = validShop(request.headers.get("x-shopify-shop-domain"));
    if (!shop) return new Response("Bad shop", { status: 400 });
    const id = request.headers.get("x-shopify-webhook-id");

    const table = shopsTable({ url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch });
    switch (topic) {
      case "app/uninstalled":
        await table.update(shop, { status: "uninstalled", token_enc: null, uninstalled_at: new Date(now()).toISOString() });
        log(JSON.stringify({ shopify_webhook: topic, shop, id }));
        break;
      case "customers/data_request":
      case "customers/redact":
        log(JSON.stringify({ shopify_webhook: topic, shop, id, note: "no customer data held" }));
        break;
      case "shop/redact":
        // Every later table keyed on the shop references shopify_shops with
        // ON DELETE CASCADE, so this one delete erases all of the store's rows.
        await table.remove(shop);
        log(JSON.stringify({ shopify_webhook: topic, shop, id, deleted: SHOP_TABLES }));
        break;
      default:
        log(JSON.stringify({ shopify_webhook: topic, shop, id, note: "unhandled topic" }));
    }
    return new Response("ok", { status: 200 });
  };
}

export const POST = (request) => webhookHandler()(request);
