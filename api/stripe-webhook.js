import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

export async function POST(request) {
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

  // Idempotency: Stripe retries deliveries, so record each event id once.
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

  switch (event.type) {
    case "invoice.paid": {
      // First retainer payment provisions the workspace; renewals keep it active.
      const invoice = event.data.object;
      const client = {
        stripe_customer_id: invoice.customer,
        status: "active",
      };
      if (invoice.customer_email) client.contact_email = invoice.customer_email;
      if (invoice.customer_name) client.company_name = invoice.customer_name;

      const { error } = await db
        .from("clients")
        .upsert(client, { onConflict: "stripe_customer_id" });
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

  return Response.json({ received: true });
}
