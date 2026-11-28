import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
import { handleBilling } from "../lib/checkout_routes.js";

/**
 * The cancel link a card client is emailed the minute they pay.
 *
 *   GET  /api/billing?c=<client id>&k=<key>
 *     303 to Stripe's customer portal, opened on "cancel this subscription".
 *     If Stripe will not open one, 200 with a one-button page that POSTs here.
 *   POST /api/billing   form or JSON { c, k, action: "cancel" }
 *     The subscription ends with the month already paid: no further charge.
 *     200 page, or { ok: true, cancel_at_period_end: true, ends_at } for JSON.
 *
 *   404 a link that does not verify · 503 not configured · 502 Stripe refused
 *
 * The key is an HMAC of the client id (lib/checkout.js), so the link needs no
 * sign-in and no stored token. A GET changes nothing in Stripe. When the
 * subscription ends, Stripe's customer.subscription.deleted marks the client
 * churned (lib/stripe_events.js). The logic and its tests live in
 * lib/checkout_routes.js.
 */
const deps = () => ({
  env: process.env,
  makeStripe: () => new Stripe(process.env.STRIPE_SECRET_KEY),
  makeDb: () => createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  }),
});

export function GET(request) {
  return handleBilling(request, deps());
}

export function POST(request) {
  return handleBilling(request, deps());
}
