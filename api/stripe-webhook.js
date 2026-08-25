import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

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

  switch (event.type) {
    case "invoice.paid": {
      // First retainer payment provisions the workspace; renewals keep it
      // active. Audit prospects already exist as pending rows keyed by email
      // (scripts/new-client.mjs), so conversion must merge, not insert.
      const invoice = event.data.object;
      const email = invoice.customer_email ? invoice.customer_email.toLowerCase() : null;
      const patch = { stripe_customer_id: invoice.customer, status: "active" };
      if (invoice.customer_name) patch.company_name = invoice.customer_name;

      let { data: existing, error: findError } = await db
        .from("clients")
        .select("id")
        .eq("stripe_customer_id", invoice.customer)
        .maybeSingle();
      if (!findError && !existing && email) {
        ({ data: existing, error: findError } = await db
          .from("clients")
          .select("id")
          .eq("contact_email", email)
          .maybeSingle());
      }
      if (findError) {
        return new Response(`Provisioning lookup error: ${findError.message}`, { status: 500 });
      }

      const { error } = existing
        ? await db.from("clients").update(patch).eq("id", existing.id)
        : await db.from("clients").insert(email ? { ...patch, contact_email: email } : patch);
      if (error) {
        return new Response(`Provisioning error: ${error.message}`, { status: 500 });
      }
      break;
    }
    case "invoice.payment_failed": {
      const invoice = event.data.object;
      await db
        .from("clients")
        .update({ status: "past_due" })
        .eq("stripe_customer_id", invoice.customer);
      break;
    }
    case "customer.subscription.deleted": {
      const subscription = event.data.object;
      await db
        .from("clients")
        .update({ status: "churned" })
        .eq("stripe_customer_id", subscription.customer);
      break;
    }
    default:
      break;
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
