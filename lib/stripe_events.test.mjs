import { test } from "node:test";
import assert from "node:assert/strict";
import {
  handleStripeEvent, subscriptionOf, servicePeriod, shouldHold, WEBHOOK_EVENTS, INVOICE_EVENTS,
} from "./stripe_events.js";

// A Supabase client wide enough for the handler: select/eq/in/maybeSingle,
// update and upsert, awaited the way supabase-js builders are.
function fakeDb(tables = {}) {
  const store = Object.fromEntries(Object.entries(tables).map(([k, v]) => [k, v.map((r) => ({ ...r }))]));
  const from = (name) => {
    const rows = (store[name] ??= []);
    const filters = [];
    let op = "select", payload = null, conflict = "id";
    const match = () => rows.filter((r) => filters.every((f) => f(r)));
    const run = () => {
      if (op === "update") {
        const hit = match();
        hit.forEach((r) => Object.assign(r, payload));
        return { data: hit, error: null };
      }
      if (op === "upsert") {
        const hit = rows.find((r) => r[conflict] === payload[conflict]);
        if (hit) Object.assign(hit, payload); else rows.push({ ...payload });
        return { data: null, error: null };
      }
      return { data: match(), error: null };
    };
    const q = {
      select() { return q; },
      eq(col, val) { filters.push((r) => r[col] === val); return q; },
      in(col, vals) { filters.push((r) => vals.includes(r[col])); return q; },
      update(patch) { op = "update"; payload = patch; return q; },
      upsert(row, opts) { op = "upsert"; payload = row; conflict = opts?.onConflict ?? "id"; return q; },
      maybeSingle() { return Promise.resolve({ data: match()[0] ?? null, error: null }); },
      then(resolve, reject) { try { resolve(run()); } catch (e) { reject(e); } },
    };
    return q;
  };
  return { from, store };
}

function fakeStripe({ fail = false } = {}) {
  const holds = [];
  return {
    holds,
    invoices: {
      update: async (id, params) => {
        if (fail) throw new Error("permission denied");
        holds.push([id, params]);
        return { id, ...params };
      },
    },
  };
}

const OCT_1 = 1790812800;   // 2026-10-01T00:00:00Z
const NOV_1 = 1793491200;   // 2026-11-01T00:00:00Z

const CLIENT = { id: "c-1", status: "active", contact_email: "founder@alpha.com", stripe_customer_id: "cus_1",
                 stripe_subscription_id: "sub_1", retainer_started_at: "2026-08-02T00:00:00Z", plan: "retainer" };

// A renewal invoice as API 2025-08-27 (basil) shapes it: the subscription
// under `parent`, the month served on the line, the invoice's own period the
// month just gone.
function renewal(over = {}) {
  return {
    id: "in_oct", object: "invoice", status: "draft", auto_advance: true, customer: "cus_1",
    customer_email: "Founder@Alpha.com", currency: "usd", amount_due: 600000, amount_paid: 0,
    period_start: OCT_1 - 30 * 86400, period_end: OCT_1, created: OCT_1, number: null,
    status_transitions: {}, billing_reason: "subscription_cycle",
    parent: { type: "subscription_details",
              subscription_details: { subscription: "sub_1", metadata: { hubricon_client_id: "c-1" } } },
    lines: { data: [{ period: { start: OCT_1, end: NOV_1 } }] },
    ...over,
  };
}

const event = (type, object) => ({ id: `evt_${type}`, type, data: { object } });

test("a retainer draft is mirrored for the month it bills and held for the gate", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [] });
  const stripe = fakeStripe();
  assert.equal(await handleStripeEvent(event("invoice.created", renewal()), { db, stripe }), null);
  const [row] = db.store.invoices;
  assert.equal(row.client_id, "c-1");
  assert.equal(row.status, "draft");
  assert.equal(row.amount_due, 6000);
  assert.deepEqual([row.period_start, row.period_end], ["2026-10-01", "2026-11-01"]);
  assert.deepEqual(stripe.holds, [["in_oct", { auto_advance: false }]]);
});

test("a late invoice.created never drags a paid invoice back to draft, and is not held", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [{ stripe_invoice_id: "in_oct", status: "paid", amount_paid: 6000 }] });
  const stripe = fakeStripe();
  assert.equal(await handleStripeEvent(event("invoice.created", renewal()), { db, stripe }), null);
  assert.equal(db.store.invoices[0].status, "paid");
  assert.equal(db.store.invoices[0].amount_paid, 6000);
  assert.deepEqual(stripe.holds, []);
});

test("the gate's own columns survive a later event for the same invoice", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [{ stripe_invoice_id: "in_oct", status: "open",
                                                     gate_decision: "covered", refunded_usd: 0 }] });
  await handleStripeEvent(event("invoice.paid", renewal({ status: "paid", amount_paid: 600000 })), { db, stripe: fakeStripe() });
  const [row] = db.store.invoices;
  assert.equal(row.status, "paid");
  assert.equal(row.gate_decision, "covered");
});

test("a failed hold is a 500, so Stripe retries while it waits to finalize", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [] });
  const failure = await handleStripeEvent(event("invoice.created", renewal()), { db, stripe: fakeStripe({ fail: true }) });
  assert.match(failure, /^Hold error on in_oct: permission denied/);
});

test("a recovery-share invoice and a stranger's invoice are mirrored but never held", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [] });
  const stripe = fakeStripe();
  const oneOff = renewal({ id: "in_rec", parent: null, billing_reason: "manual",
                           metadata: { hubricon_client_id: "c-1", hubricon_plan: "recovery" } });
  await handleStripeEvent(event("invoice.created", oneOff), { db, stripe });
  const stranger = renewal({ id: "in_x", customer: "cus_x", customer_email: "x@else.com",
                             parent: { subscription_details: { subscription: "sub_x", metadata: {} } } });
  await handleStripeEvent(event("invoice.created", stranger), { db, stripe });
  assert.deepEqual(stripe.holds, []);
  assert.equal(db.store.invoices.find((r) => r.stripe_invoice_id === "in_rec").client_id, "c-1");
  assert.equal(db.store.invoices.find((r) => r.stripe_invoice_id === "in_x").client_id, null);
});

test("a payment for a customer no client matches creates no client", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [] });
  const paid = renewal({ id: "in_x", status: "paid", customer: "cus_x", customer_email: "x@else.com",
                         parent: { subscription_details: { subscription: "sub_x", metadata: {} } } });
  assert.equal(await handleStripeEvent(event("invoice.paid", paid), { db, stripe: fakeStripe() }), null);
  assert.equal(db.store.clients.length, 1);
});

test("a payment activates a pending client, dates the yes only if nobody has, and never revives one who left", async () => {
  const db = fakeDb({
    clients: [
      { ...CLIENT, id: "c-p", status: "pending", stripe_customer_id: null, retainer_started_at: null,
        contact_email: "p@p.com" },
      { ...CLIENT, id: "c-gone", status: "churned", stripe_customer_id: "cus_g", contact_email: "g@g.com" },
    ],
    invoices: [],
  });
  const stripe = fakeStripe();
  await handleStripeEvent(event("invoice.paid", renewal({ id: "in_p", status: "paid", customer: "cus_p",
    customer_email: "p@p.com", parent: { subscription_details: { subscription: "sub_p", metadata: { hubricon_client_id: "c-p" } } } })),
  { db, stripe });
  await handleStripeEvent(event("invoice.paid", renewal({ id: "in_g", status: "paid", customer: "cus_g",
    customer_email: "g@g.com", parent: { subscription_details: { subscription: "sub_g", metadata: {} } } })),
  { db, stripe });
  const [pending, gone] = db.store.clients;
  assert.equal(pending.status, "active");
  assert.equal(pending.stripe_customer_id, "cus_p");
  assert.equal(pending.retainer_source, "first_invoice");
  assert.equal(gone.status, "churned");
});

test("a failed ACH payment marks the client past due, which the operator still gates", async () => {
  const db = fakeDb({ clients: [CLIENT], invoices: [] });
  await handleStripeEvent(event("invoice.payment_failed", renewal({ status: "open" })), { db, stripe: fakeStripe() });
  assert.equal(db.store.clients[0].status, "past_due");
});

test("only the subscription on the client's row ends the engagement", async () => {
  const db = fakeDb({ clients: [
    CLIENT,
    // switched to Recovery Only: the row was cleared before the old subscription was ended
    { ...CLIENT, id: "c-r", plan: "recovery", stripe_subscription_id: null, stripe_customer_id: "cus_r" },
  ] });
  await handleStripeEvent(event("customer.subscription.deleted", { id: "sub_old", customer: "cus_r" }), { db, stripe: fakeStripe() });
  assert.equal(db.store.clients[1].status, "active");
  await handleStripeEvent(event("customer.subscription.deleted", { id: "sub_1", customer: "cus_1" }), { db, stripe: fakeStripe() });
  assert.equal(db.store.clients[0].status, "churned");
});

test("reads the subscription across API versions, and the month served from the line", () => {
  assert.deepEqual(subscriptionOf(renewal()), { id: "sub_1", metadata: { hubricon_client_id: "c-1" } });
  const older = { subscription: "sub_9", subscription_details: { metadata: { hubricon_client_id: "c-9" } } };
  assert.deepEqual(subscriptionOf(older), { id: "sub_9", metadata: { hubricon_client_id: "c-9" } });
  assert.deepEqual(servicePeriod({ period_start: OCT_1, period_end: OCT_1 }), { start: "2026-10-01", end: "2026-10-01" });
  assert.equal(shouldHold(renewal({ auto_advance: false }), { clientId: "c-1" }), false);
  assert.equal(shouldHold(renewal(), { clientId: null }), true);     // our id is on the subscription
});

test("the endpoint is subscribed to every event the handler reads", () => {
  for (const type of [...INVOICE_EVENTS, "customer.subscription.deleted"]) {
    assert.ok(WEBHOOK_EVENTS.includes(type), type);
  }
});
