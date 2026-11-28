/**
 * What the Stripe webhook does with an event once api/stripe-webhook.js has
 * proved it came from Stripe. Split out so it runs against a fake database in
 * lib/stripe_events.test.mjs.
 *
 * Four jobs:
 *
 *   1. Mirror every invoice into `invoices`, so the Profit Record's
 *      denominator is what Stripe billed rather than what we assume.
 *   2. Hold every retainer invoice at draft (auto_advance=false). The hourly
 *      operator judges it against the Profit Record and either sends it or
 *      voids it unsent, so a client never receives a bill the Record has not
 *      covered (terms §3). Without the hold Stripe finalizes and emails a
 *      subscription invoice about an hour after creating it, and the gate
 *      could only void it after the client had read it.
 *   3. Keep the client row's status in step with what Stripe says: paid,
 *      past due, ended.
 *   4. Set up a client who paid by card on /start (plan self_serve): a paid
 *      Checkout Session becomes the client row, the upload link, the portal
 *      seat and the welcome email (lib/provision.js), with no person in the
 *      loop. That is the only way this file ever creates a client.
 *
 * An invoice never creates a client. The operator provisions every booking
 * and a paid Checkout Session provisions every card client, so an invoice for
 * a customer no client matches is not ours to act on.
 *
 * A self-serve invoice is never held (job 2). That client's card is charged
 * $1,000 on the day each month starts and nothing judges the invoice first:
 * the offer on /start is a flat price, and a held draft would simply never be
 * collected.
 */
import { PLAN as SELF_SERVE, isSelfServe } from "./checkout.js";
import { provisionSelfServe } from "./provision.js";

// Stripe holds money in integer cents; the ledger holds dollars.
const dollars = (cents) => (cents == null ? null : cents / 100);
const stamp = (unix) => (unix ? new Date(unix * 1000).toISOString() : null);
const day = (unix) => (unix ? stamp(unix).slice(0, 10) : null);

// Webhooks arrive in any order. A late `invoice.created` must not drag a paid
// invoice back to draft, so a mirrored row only ever moves forward.
const RANK = { draft: 0, open: 1, uncollectible: 2, paid: 3, void: 3 };

export const INVOICE_EVENTS = new Set([
  "invoice.created",
  "invoice.finalized",
  "invoice.paid",
  "invoice.payment_failed",
  "invoice.voided",
  "invoice.marked_uncollectible",
]);

// Every event the endpoint must be subscribed to. scripts/stripe-setup.mjs
// reads this list, so the subscription and the handler cannot drift apart
// again: until 2026-09-25 the endpoint was created with three events and the
// open invoice the gate voids never reached the mirror.
export const CHECKOUT_EVENTS = new Set([
  "checkout.session.completed",
  // Card payments settle at once, so `completed` already says paid. This one
  // only fires for a delayed method, kept so a later change in the dashboard
  // (a bank debit switched on) cannot leave a paid buyer without a setup.
  "checkout.session.async_payment_succeeded",
]);
export const WEBHOOK_EVENTS = [...INVOICE_EVENTS, "customer.subscription.deleted", ...CHECKOUT_EVENTS];

/** The subscription an invoice was raised by. API 2025-03-31 (basil) moved it under `parent`. */
export function subscriptionOf(invoice) {
  const details = invoice.parent?.subscription_details ?? invoice.subscription_details ?? null;
  const raw = details?.subscription ?? invoice.subscription ?? null;
  return { id: raw && typeof raw === "object" ? raw.id : raw, metadata: details?.metadata ?? {} };
}

/**
 * The month an invoice bills for. A subscription invoice's own period_start
 * and period_end describe the period that just ended (Stripe bills a month in
 * advance and reports usage in arrears); its line carries the month served,
 * which is what the letters name.
 */
export function servicePeriod(invoice) {
  const line = invoice.lines?.data?.find((l) => l.period?.start) ?? null;
  return {
    start: day(line?.period?.start ?? invoice.period_start),
    end: day(line?.period?.end ?? invoice.period_end),
  };
}

async function first(query) {
  const { data, error } = await query.maybeSingle();
  return error ? null : data;
}

/** The client an invoice belongs to: by the id we stamped on it, the Stripe customer we recorded, or the email. */
export async function findClientId(db, { hint, customer, email }) {
  if (hint) {
    const byId = await first(db.from("clients").select("id").eq("id", hint));
    if (byId) return byId.id;
  }
  if (customer) {
    const byCustomer = await first(db.from("clients").select("id").eq("stripe_customer_id", customer));
    if (byCustomer) return byCustomer.id;
  }
  if (email) {
    const byEmail = await first(db.from("clients").select("id").eq("contact_email", email));
    if (byEmail) return byEmail.id;
  }
  return null;
}

/**
 * Mirror what Stripe says we billed, keyed on stripe_invoice_id, so a retry or
 * a later status change updates the same row. Only the columns Stripe owns are
 * written: the gate's decision and any refund are the operator's, and an
 * upsert leaves columns it does not name alone.
 */
export async function mirrorInvoice(db, invoice) {
  const sub = subscriptionOf(invoice);
  const email = invoice.customer_email ? invoice.customer_email.toLowerCase() : null;
  const hint = sub.metadata?.hubricon_client_id ?? invoice.metadata?.hubricon_client_id ?? null;
  const clientId = await findClientId(db, { hint, customer: invoice.customer, email });

  const { data: stored, error: readError } = await db
    .from("invoices").select("status").eq("stripe_invoice_id", invoice.id).maybeSingle();
  if (readError) return { clientId, stored: null, error: readError };
  const status = invoice.status ?? "draft";
  if (stored && (RANK[stored.status] ?? 0) > (RANK[status] ?? 0)) {
    return { clientId, stored, skipped: true };
  }

  const period = servicePeriod(invoice);
  const row = {
    client_id: clientId,
    stripe_invoice_id: invoice.id,
    stripe_customer_id: invoice.customer,
    number: invoice.number ?? null,
    status,
    currency: invoice.currency ?? "usd",
    amount_due: dollars(invoice.amount_due),
    amount_paid: dollars(invoice.amount_paid) ?? 0,
    period_start: period.start,
    period_end: period.end,
    issued_at: stamp(invoice.status_transitions?.finalized_at) ?? stamp(invoice.created),
    paid_at: stamp(invoice.status_transitions?.paid_at),
    voided_at: stamp(invoice.status_transitions?.voided_at),
    hosted_invoice_url: invoice.hosted_invoice_url ?? null,
    raw: invoice,
  };
  const { error } = await db.from("invoices").upsert(row, { onConflict: "stripe_invoice_id" });
  return { clientId, stored, error };
}

/** Should this invoice wait at draft for the gate? Only a retainer draft of ours, never one already moved on,
 *  never a $0 one (the trial invoice Stripe raises when billing starts bills nothing, so there is nothing to judge),
 *  and never a self-serve one: `plan` is the client row's plan when the caller has read it. */
export function shouldHold(invoice, { clientId, stored, plan }) {
  if (invoice.status !== "draft" || invoice.auto_advance === false) return false;
  if (!(Number(invoice.amount_due) > 0)) return false;
  if (stored && stored.status !== "draft") return false;
  const sub = subscriptionOf(invoice);
  if (sub.metadata?.hubricon_plan === SELF_SERVE || plan === SELF_SERVE) return false;
  return Boolean(sub.id) && Boolean(sub.metadata?.hubricon_client_id || clientId);
}

/** The plan on a client row, or null when it cannot be read (a failed read never lifts a hold). */
async function planOf(db, clientId) {
  if (!clientId) return null;
  const row = await first(db.from("clients").select("plan").eq("id", clientId));
  return row?.plan ?? null;
}

/**
 * Handle one verified event. Returns null when done, or an error message the
 * route turns into a 500 so Stripe retries. Every write is an idempotent
 * upsert or update, so a retry that processes an event twice is harmless.
 */
export async function handleStripeEvent(event, { db, stripe, env = {}, fetchImpl }) {
  let clientId = null;

  if (CHECKOUT_EVENTS.has(event.type)) {
    const session = event.data.object;
    // Another Checkout on this Stripe account is not ours to act on, and a
    // session that completed without the money is not a client yet.
    if (!isSelfServe(session) || session.payment_status !== "paid") return null;
    const made = await provisionSelfServe({ db, session, env, welcome: true, fetchImpl });
    if (!made.ok) {
      return `Self-serve setup error on ${session.id}: ${made.error}${made.detail ? ` (${made.detail})` : ""}`;
    }
    // The first invoice's events can land before the session's does, and were
    // mirrored against no client. Now there is one.
    const customer = typeof session.customer === "object" ? session.customer?.id : session.customer;
    if (customer) {
      const { error } = await db.from("invoices").update({ client_id: made.clientId })
        .eq("stripe_customer_id", customer).is("client_id", null);
      if (error) return `Invoice backfill error on ${session.id}: ${error.message}`;
    }
    return null;
  }

  if (INVOICE_EVENTS.has(event.type)) {
    const invoice = event.data.object;
    const mirrored = await mirrorInvoice(db, invoice);
    if (mirrored.error) return `Invoice mirror error: ${mirrored.error.message}`;
    clientId = mirrored.clientId;

    if (event.type === "invoice.created" && shouldHold(invoice, mirrored)
        && (await planOf(db, clientId)) !== SELF_SERVE) {
      try {
        await stripe.invoices.update(invoice.id, { auto_advance: false });
      } catch (err) {
        // A 500 makes Stripe retry, and Stripe waits on a failing
        // invoice.created before it finalizes. If the hold never lands, the
        // gate still judges the invoice once it is open.
        return `Hold error on ${invoice.id}: ${err.message}`;
      }
    }
  }

  switch (event.type) {
    case "invoice.paid": {
      // A payment keeps a client in good standing, or puts a pending one
      // there; it never brings back a client who has left.
      if (!clientId) break;
      const invoice = event.data.object;
      const { data: client, error: findError } = await db
        .from("clients").select("id, status, stripe_customer_id, retainer_started_at")
        .eq("id", clientId).maybeSingle();
      if (findError) return `Provisioning lookup error: ${findError.message}`;
      if (!client) break;
      const patch = {};
      if (!client.stripe_customer_id) patch.stripe_customer_id = invoice.customer;
      if (client.status === "pending" || client.status === "past_due") patch.status = "active";
      // terms.html §3: the retainer starts the day they say yes. The first
      // invoice is the earliest hard evidence of that yes we ever hold, so it
      // stands in until someone records the real date, but it never
      // overwrites a date already set, which is always better evidence.
      if (!client.retainer_started_at && invoice.period_start) {
        patch.retainer_started_at = stamp(invoice.period_start);
        patch.retainer_source = "first_invoice";
      }
      if (Object.keys(patch).length === 0) break;
      const { error } = await db.from("clients").update(patch).eq("id", client.id);
      if (error) return `Provisioning error: ${error.message}`;
      break;
    }
    case "invoice.payment_failed": {
      if (!clientId) break;
      const { error } = await db.from("clients").update({ status: "past_due" })
        .eq("id", clientId).in("status", ["pending", "active"]);
      if (error) return `Status error: ${error.message}`;
      break;
    }
    case "customer.subscription.deleted": {
      // Only the subscription on the client row ends the engagement. The
      // downsell to Recovery Only ends the retainer's subscription too, after
      // clearing it from the row, and that client has not left.
      const subscription = event.data.object;
      const { error } = await db.from("clients").update({ status: "churned" })
        .eq("stripe_subscription_id", subscription.id).in("status", ["pending", "active", "past_due"]);
      if (error) return `Status error: ${error.message}`;
      break;
    }
    default:
      break;
  }
  return null;
}
