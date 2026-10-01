import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
import { handleStripeEvent } from "../lib/stripe_events.js";

/**
 * Stripe → Hubricon. This file proves an event came from Stripe and records
 * that it was handled; lib/stripe_events.js decides what the event means
 * (mirror the invoice, hold a retainer draft for the gate, keep the client's
 * status in step).
 *
 * The key needs Invoices: write, for the hold. scripts/stripe-setup.mjs
 * subscribes the endpoint to every event the handler reads.
 */
export async function POST(request) {
  const missing = [
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
  ].filter((name) => !process.env[name]);
  if (missing.length > 0) {
    return new Response(`Server not configured: missing ${missing.join(", ")}`, { status: 500 });
  }

  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);
  const signature = request.headers.get("stripe-signature");
  const payload = await request.text();

  let event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      payload,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (err) {
    return new Response(`Invalid signature: ${err.message}`, { status: 400 });
  }

  const db = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY,
    { auth: { persistSession: false } }
  );

  const failure = await handleStripeEvent(event, { db, stripe });
  if (failure) {
    // 500 makes Stripe retry later rather than dropping the event.
    return new Response(failure, { status: 500 });
  }

  // Ledger AFTER the work: a failed handler above returns 500 without
  // consuming the event id, so Stripe's retry gets a clean second attempt.
  // Handlers are idempotent upserts/updates, so a concurrent retry that
  // processes twice is harmless.
  const { data: isNew, error: ledgerError } = await db.rpc("record_stripe_event", {
    p_event_id: event.id,
    p_event_type: event.type,
  });
  if (ledgerError) {
    // 500 makes Stripe retry later rather than dropping the event.
    return new Response(`Event ledger error: ${ledgerError.message}`, { status: 500 });
  }
  if (!isNew) {
    return Response.json({ received: true, duplicate: true });
  }

  return Response.json({ received: true });
}
