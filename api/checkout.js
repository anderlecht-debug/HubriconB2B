import Stripe from "stripe";
import { handleCheckout } from "../lib/checkout_routes.js";

/**
 * The pay button on /start: $1,000 a month by card, no call and no calendar.
 *
 *   POST /api/checkout   JSON { platform?: "shopify" | "amazon", from?: "/start" }
 *     -> 200 { url, session_id }     go to `url` (Stripe's card page)
 *   POST /api/checkout   as a plain form (the button works without script)
 *     -> 303 to Stripe's card page
 *
 *   400 { error: "bad_platform", message }     platform is neither shopify nor amazon
 *   503 { error: "not_configured", message }   card payment is not switched on; nothing was charged
 *   502 { error: "stripe_error", message }     Stripe refused or could not be reached
 *   429, 413                                   rate limit, body over 4 KB
 *
 * The button refuses with 503 unless the whole chain is configured
 * (lib/checkout.js CHECKOUT_ENV), so nobody pays into a deploy that could not
 * set them up. The logic and its tests live in lib/checkout_routes.js.
 */
export function POST(request) {
  return handleCheckout(request, {
    env: process.env,
    makeStripe: () => new Stripe(process.env.STRIPE_SECRET_KEY),
  });
}
