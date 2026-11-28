import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
import { handleCheckoutSession } from "../lib/checkout_routes.js";

/**
 * What /start asks when a buyer lands back from Stripe's card page.
 *
 *   GET /api/checkout-session?session_id=cs_...
 *     200 { status: "open" }        not paid; the card page still works
 *     200 { status: "processing" }  paid or completing, setup not finished: do not pay again
 *     200 { status: "paid", email, upload_url, upload_token, platform, cancel_url }
 *     200 { status: "expired" }
 *     404 { error: "not_found" }    unknown or malformed session id
 *     503 / 502 { error, message }  status cannot be checked right now
 *
 * `upload_url` is the upload page with the client's token in `?t=`, the
 * parameter intake.html and /api/intake already read. A paid session is set
 * up here if the webhook has not done it yet (the same idempotent step), so
 * the link never waits on Stripe's delivery. The logic and its tests live in
 * lib/checkout_routes.js.
 */
export function GET(request) {
  return handleCheckoutSession(request, {
    env: process.env,
    makeStripe: () => new Stripe(process.env.STRIPE_SECRET_KEY),
    makeDb: () => createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    }),
  });
}
