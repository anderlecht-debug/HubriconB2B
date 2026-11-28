import { test } from "node:test";
import assert from "node:assert/strict";
import {
  handleStripeEvent, subscriptionOf, servicePeriod, shouldHold, WEBHOOK_EVENTS, INVOICE_EVENTS, CHECKOUT_EVENTS,
} from "./stripe_events.js";
import { ENV, fakeDb as cardDb, fakeStripe as cardStripe, fakeResend, paidSession } from "./checkout_fakes.mjs";
import { uploadToken, tokenHash } from "./checkout.js";

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
  // The trial invoice Stripe raises when billing starts in arrears bills nothing: nothing to hold or judge.
  assert.equal(shouldHold(renewal({ amount_due: 0, billing_reason: "subscription_create" }), { clientId: "c-1" }), false);
});

test("the endpoint is subscribed to every event the handler reads", () => {
  for (const type of [...INVOICE_EVENTS, "customer.subscription.deleted", ...CHECKOUT_EVENTS, "checkout.session.completed"]) {
    assert.ok(WEBHOOK_EVENTS.includes(type), type);
  }
});

// ---------------------------------------------------------------------------
// The card offer on /start (plan self_serve). The fakes are the wider ones in
// lib/checkout_fakes.mjs: unique constraints, the token RPC, auth and Resend.

const SELF_META = { hubricon_plan: "self_serve", hubricon_platform: "shopify" };
// The $1,000 invoices of a Checkout subscription. They carry the plan in the
// subscription's metadata and never a hubricon_client_id.
const cardInvoice = (over = {}) => renewal({
  id: "in_card", customer: "cus_new1", customer_email: "Owner@Brand.com", amount_due: 100000,
  parent: { type: "subscription_details", subscription_details: { subscription: "sub_new1", metadata: SELF_META } },
  ...over,
});

test("a paid Checkout Session sets the client up: row, upload link, seat, one email", async () => {
  const db = cardDb();
  const mail = fakeResend();
  const done = await handleStripeEvent(event("checkout.session.completed", paidSession()),
    { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl });
  assert.equal(done, null);
  const [client] = db.store.clients;
  assert.equal(client.plan, "self_serve");
  assert.equal(client.status, "active");
  assert.equal(client.contact_email, "owner@brand.com");
  assert.equal(Number(client.monthly_fee_usd), 1000);
  assert.equal(client.free_months, 0);
  assert.equal(client.platform, "shopify");
  assert.equal(client.stripe_subscription_id, "sub_new1");
  assert.equal(db.store.intake_tokens[0].token_hash, tokenHash(uploadToken(ENV.CHECKOUT_TOKEN_SECRET, paidSession().id)));
  assert.equal(db.store.client_users.length, 1);
  assert.equal(mail.sent.length, 1);
  assert.equal(mail.sent[0].to[0] ?? mail.sent[0].to, "owner@brand.com");
});

test("Stripe sending the same session twice leaves one client, one link and one email", async () => {
  const db = cardDb();
  const mail = fakeResend();
  const deps = { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl };
  assert.equal(await handleStripeEvent(event("checkout.session.completed", paidSession()), deps), null);
  assert.equal(await handleStripeEvent(event("checkout.session.completed", paidSession()), deps), null);
  assert.equal(await handleStripeEvent(event("checkout.session.async_payment_succeeded", paidSession()), deps), null);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.intake_tokens.length, 1);
  assert.equal(db.store.client_users.length, 1);
  assert.equal(mail.sent.length, 1);
});

test("a Checkout that is not ours, or not paid, sets nothing up and is not an error", async () => {
  const db = cardDb();
  const mail = fakeResend();
  const deps = { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl };
  const strangers = [
    paidSession({ metadata: {} }),
    paidSession({ mode: "payment" }),
    paidSession({ payment_status: "unpaid" }),
  ];
  for (const session of strangers) {
    assert.equal(await handleStripeEvent(event("checkout.session.completed", session), deps), null);
  }
  assert.equal((db.store.clients ?? []).length, 0);
  assert.equal(mail.sent.length, 0);
});

test("a setup that fails answers Stripe with an error, so Stripe sends the session again", async () => {
  const db = cardDb();
  const down = fakeResend({ status: 500 });
  const failure = await handleStripeEvent(event("checkout.session.completed", paidSession()),
    { db, stripe: cardStripe(), env: ENV, fetchImpl: down.fetchImpl });
  assert.match(failure, /^Self-serve setup error on cs_test_a1b2c3d4e5f6: email/);
  // The retry, with email back, sends the one email. The client was not made twice.
  const mail = fakeResend();
  assert.equal(await handleStripeEvent(event("checkout.session.completed", paidSession()),
    { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl }), null);
  assert.equal(db.store.clients.length, 1);
  assert.equal(mail.sent.length, 1);

  const unset = await handleStripeEvent(event("checkout.session.completed", paidSession({ id: "cs_test_zzzz99998888" })),
    { db: cardDb(), stripe: cardStripe() });
  assert.match(unset, /not_configured/);
});

test("a live client on another plan who pays by card is a conflict for a person, never an overwrite", async () => {
  const db = cardDb({ clients: [{ ...CLIENT, contact_email: "owner@brand.com" }] });
  const mail = fakeResend();
  const failure = await handleStripeEvent(event("checkout.session.completed", paidSession()),
    { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl });
  assert.match(failure, /conflict/);
  assert.equal(db.store.clients[0].plan, "retainer");
  assert.equal(db.store.clients[0].stripe_subscription_id, "sub_1");
  assert.equal(mail.sent.length, 0);
});

test("a self-serve invoice is mirrored and never held, whichever way it is recognised", async () => {
  // By the plan on the subscription, before the client exists.
  const early = cardDb({ invoices: [] });
  const stripe = cardStripe();
  assert.equal(await handleStripeEvent(event("invoice.created", cardInvoice()), { db: early, stripe }), null);
  assert.deepEqual(stripe.holds, []);
  assert.equal(early.store.invoices[0].client_id, null);
  assert.equal(early.store.invoices[0].amount_due, 1000);

  // By the client row's plan, when the subscription's metadata has been wiped.
  const db = cardDb({ clients: [{ id: "c-s", plan: "self_serve", status: "active", contact_email: "owner@brand.com",
                                  stripe_customer_id: "cus_new1", stripe_subscription_id: "sub_new1" }], invoices: [] });
  const bare = cardInvoice({ id: "in_dec",
    parent: { type: "subscription_details", subscription_details: { subscription: "sub_new1", metadata: {} } } });
  assert.equal(await handleStripeEvent(event("invoice.created", bare), { db, stripe }), null);
  assert.deepEqual(stripe.holds, []);
  assert.equal(db.store.invoices[0].client_id, "c-s");

  assert.equal(shouldHold(cardInvoice(), { clientId: "c-s" }), false);
  assert.equal(shouldHold(bare, { clientId: "c-s", plan: "self_serve" }), false);
  assert.equal(shouldHold(bare, { clientId: "c-s", plan: "retainer" }), true);
});

test("the first invoice can arrive before the session: it is tied to the client once there is one", async () => {
  const db = cardDb({ invoices: [] });
  const mail = fakeResend();
  const deps = { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl };
  await handleStripeEvent(event("invoice.paid", cardInvoice({ status: "paid", amount_paid: 100000 })), deps);
  assert.equal(db.store.invoices[0].client_id, null);
  assert.equal((db.store.clients ?? []).length, 0);       // an invoice never creates a client
  assert.equal(await handleStripeEvent(event("checkout.session.completed", paidSession()), deps), null);
  assert.equal(db.store.invoices[0].client_id, db.store.clients[0].id);
  assert.equal(db.store.invoices[0].status, "paid");
});

test("a card that fails on renewal marks the client past due, a later payment restores them, and the end of the subscription ends it", async () => {
  const db = cardDb({ invoices: [] });
  const mail = fakeResend();
  const deps = { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl };
  await handleStripeEvent(event("checkout.session.completed", paidSession()), deps);
  const started = db.store.clients[0].retainer_started_at;

  await handleStripeEvent(event("invoice.payment_failed", cardInvoice({ id: "in_jan", status: "open" })), deps);
  assert.equal(db.store.clients[0].status, "past_due");
  await handleStripeEvent(event("invoice.paid", cardInvoice({ id: "in_jan", status: "paid", amount_paid: 100000 })), deps);
  assert.equal(db.store.clients[0].status, "active");
  assert.equal(db.store.clients[0].retainer_started_at, started);

  // A second subscription bought by mistake ends without ending the client.
  await handleStripeEvent(event("customer.subscription.deleted", { id: "sub_other", customer: "cus_new1" }), deps);
  assert.equal(db.store.clients[0].status, "active");
  await handleStripeEvent(event("customer.subscription.deleted", { id: "sub_new1", customer: "cus_new1" }), deps);
  assert.equal(db.store.clients[0].status, "churned");
  assert.equal(mail.sent.length, 1);
});

test("a client who left and pays again by card is set up again on the new subscription", async () => {
  const db = cardDb({ clients: [{ id: "c-back", plan: "self_serve", status: "churned", contact_email: "owner@brand.com",
                                  stripe_customer_id: "cus_old", stripe_subscription_id: "sub_old", platform: "shopify" }] });
  const mail = fakeResend();
  const session = paidSession({ id: "cs_test_again0001", customer: "cus_new2", subscription: "sub_new2" });
  assert.equal(await handleStripeEvent(event("checkout.session.completed", session),
    { db, stripe: cardStripe(), env: ENV, fetchImpl: mail.fetchImpl }), null);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.clients[0].status, "active");
  assert.equal(db.store.clients[0].stripe_subscription_id, "sub_new2");
  assert.equal(mail.sent.length, 1);
});
