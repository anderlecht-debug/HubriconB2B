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

  // Stripe holds money in integer cents; the ledger holds dollars.
  const dollars = (cents) => (cents == null ? null : cents / 100);
  const stamp = (unix) => (unix ? new Date(unix * 1000).toISOString() : null);

  // Find the client an invoice belongs to: by the Stripe customer we already
  // recorded, else by the email the audit prospect was created under.
  async function findClientId(customer, email) {
    let { data } = await db.from("clients").select("id").eq("stripe_customer_id", customer).maybeSingle();
    if (!data && email) {
      ({ data } = await db.from("clients").select("id").eq("contact_email", email).maybeSingle());
    }
    return data ? data.id : null;
  }

  // Mirror what Stripe says we billed, so the value ledger's denominator is
  // observed rather than assumed. Keyed on stripe_invoice_id, so a retry or a
  // later status change updates the same row instead of adding one.
  async function upsertInvoice(invoice) {
    const email = invoice.customer_email ? invoice.customer_email.toLowerCase() : null;
    const row = {
      client_id: await findClientId(invoice.customer, email),
      stripe_invoice_id: invoice.id,
      stripe_customer_id: invoice.customer,
      number: invoice.number ?? null,
      status: invoice.status ?? "draft",
      currency: invoice.currency ?? "usd",
      amount_due: dollars(invoice.amount_due),
      amount_paid: dollars(invoice.amount_paid) ?? 0,
      period_start: invoice.period_start ? stamp(invoice.period_start).slice(0, 10) : null,
      period_end: invoice.period_end ? stamp(invoice.period_end).slice(0, 10) : null,
      issued_at: stamp(invoice.status_transitions?.finalized_at) ?? stamp(invoice.created),
      paid_at: stamp(invoice.status_transitions?.paid_at),
      voided_at: stamp(invoice.status_transitions?.voided_at),
      hosted_invoice_url: invoice.hosted_invoice_url ?? null,
      raw: invoice,
    };
    const { error } = await db.from("invoices").upsert(row, { onConflict: "stripe_invoice_id" });
    return error;
  }

  const INVOICE_EVENTS = new Set([
    "invoice.created",
    "invoice.finalized",
    "invoice.paid",
    "invoice.payment_failed",
    "invoice.voided",
    "invoice.marked_uncollectible",
  ]);
  if (INVOICE_EVENTS.has(event.type)) {
    const error = await upsertInvoice(event.data.object);
    if (error) {
      return new Response(`Invoice mirror error: ${error.message}`, { status: 500 });
    }
  }

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
        .select("id, retainer_started_at")
        .eq("stripe_customer_id", invoice.customer)
        .maybeSingle();
      if (!findError && !existing && email) {
        ({ data: existing, error: findError } = await db
          .from("clients")
          .select("id, retainer_started_at")
          .eq("contact_email", email)
          .maybeSingle());
      }

      // terms.html §3: the retainer starts the day they say yes. The first
      // invoice is the earliest hard evidence of that yes we ever hold, so it
      // stands in until someone records the real date — but it never overwrites
      // a date already set, which is always better evidence.
      if (!existing?.retainer_started_at && invoice.period_start) {
        patch.retainer_started_at = new Date(invoice.period_start * 1000).toISOString();
        patch.retainer_source = "first_invoice";
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
