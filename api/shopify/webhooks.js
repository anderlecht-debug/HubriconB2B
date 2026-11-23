import {
  customerKey,
  deleteRows,
  listStored,
  removeStored,
  shopsTable,
  validShop,
  verifyWebhookHmac,
} from "../../lib/shopify.js";

/**
 * Shopify → Hubricon webhooks (shopify.app.toml subscribes these topics here):
 *
 *   app/uninstalled         mark the shop uninstalled and wipe its token, unless
 *                           the store has installed again since the event fired
 *                           (x-shopify-triggered-at earlier than installed_at)
 *   customers/data_request  the app pulls no customer email or name, so nothing
 *                           about a customer is held: 200, logged
 *   customers/redact        delete that customer's customer_orders rows (only a
 *                           CSV upload can have written any: a salted hash of
 *                           the email, which the payload lets us recompute)
 *   shop/redact             48 hours after uninstall: erase the store. Every
 *                           stored file under intake/shopify/<shop>/, the
 *                           store's clients row (every client_id table cascades
 *                           with it, and its seal entries lose their words), and
 *                           last the shopify_shops row (mandates, fee months and
 *                           disputes cascade). Deleting the shop row last means
 *                           a failure part way leaves it for Shopify's retry.
 *
 * A bad signature is 401, which is what Shopify's review checks for.
 */

// What shop/redact erases. A store's client_id is the store's own tenant: the
// ingest, shadow and meter jobs write under it and nothing else does.
export const SHOP_TABLES = ["shopify_shops", "shopify_mandates", "shopify_fee_months", "shopify_disputes", "clients (and every table keyed to it)"];
export const BUCKET = "intake";

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
    const db = { url: env.SUPABASE_URL, key: env.SUPABASE_SERVICE_ROLE_KEY, fetch };
    switch (topic) {
      case "app/uninstalled": {
        // A late delivery must not undo a reinstall: only an install that began
        // at or before the event is marked uninstalled.
        const at = Date.parse(request.headers.get("x-shopify-triggered-at") ?? "");
        const when = Number.isFinite(at) ? new Date(at).toISOString() : new Date(now()).toISOString();
        await table.update(shop, { status: "uninstalled", token_enc: null, uninstalled_at: when }, { installed_at: `lte.${when}` });
        log(JSON.stringify({ shopify_webhook: topic, shop, id, triggered_at: when }));
        break;
      }
      case "customers/data_request":
        log(JSON.stringify({ shopify_webhook: topic, shop, id, note: "no customer data held" }));
        break;
      case "customers/redact": {
        const body = JSON.parse(raw.toString("utf8") || "{}");
        const row = await table.get(shop);
        const k = row?.client_id ? customerKey(body?.customer?.email, row.client_id) : null;
        if (k) await deleteRows(db, "customer_orders", { client_id: row.client_id, customer_key: k });
        log(JSON.stringify({ shopify_webhook: topic, shop, id, deleted: k ? "customer_orders" : "nothing held" }));
        break;
      }
      case "shop/redact": {
        const row = await table.get(shop);
        const files = await listStored(db, BUCKET, `shopify/${shop}`);
        if (files.length) await removeStored(db, BUCKET, files);
        if (row?.client_id) await deleteRows(db, "clients", { id: row.client_id });
        await table.remove(shop);
        log(JSON.stringify({ shopify_webhook: topic, shop, id, deleted: SHOP_TABLES, files: files.length }));
        break;
      }
      default:
        log(JSON.stringify({ shopify_webhook: topic, shop, id, note: "unhandled topic" }));
    }
    return new Response("ok", { status: 200 });
  };
}

export const POST = (request) => webhookHandler()(request);
