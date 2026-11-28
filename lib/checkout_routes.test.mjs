// The three routes of the card offer, every answer, on fakes
// (lib/checkout_fakes.mjs): no Stripe, no database, no email leaves.
import test from "node:test";
import assert from "node:assert/strict";
import { SlidingWindow } from "./ratelimit.js";
import { handleCheckout, handleCheckoutSession, handleBilling } from "./checkout_routes.js";
import { NOT_SWITCHED_ON, billingKey, uploadToken } from "./checkout.js";
import { ENV, fakeDb, fakeStripe, paidSession } from "./checkout_fakes.mjs";

const SITE = "https://www.hubricon.com";
const open = () => new SlidingWindow({ limit: 1000, windowMs: 60_000 });
const post = (path, body, headers = {}) => new Request(`${SITE}${path}`, {
  method: "POST",
  headers: typeof body === "string" ? { "content-type": "application/x-www-form-urlencoded", ...headers } : { "content-type": "application/json", ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body),
});
const get = (path) => new Request(`${SITE}${path}`);
const pay = (request, over = {}) => {
  const stripe = over.stripe ?? fakeStripe();
  return handleCheckout(request, { env: ENV, makeStripe: () => stripe, limiter: open(), ...over }).then((res) => ({ res, stripe }));
};

// ---------------------------------------------------------- POST /api/checkout
test("the button, pressed by the page, answers the card page's address and the session id", async () => {
  const { res, stripe } = await pay(post("/api/checkout", { platform: "amazon" }));
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("cache-control"), "no-store");
  assert.deepEqual(await res.json(), { url: "https://checkout.stripe.test/c/pay/cs_test_abc12345", session_id: "cs_test_abc12345" });
  const [, params] = stripe.calls[0];
  assert.equal(params.mode, "subscription");
  assert.equal(params.metadata.hubricon_platform, "amazon");
  assert.equal(params.success_url, `${SITE}/start?session_id={CHECKOUT_SESSION_ID}`);
  assert.equal(params.cancel_url, `${SITE}/start?cancelled=1`);
});

test("the button, pressed as a plain form, sends the browser to the card page", async () => {
  const { res, stripe } = await pay(post("/api/checkout", ""));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), "https://checkout.stripe.test/c/pay/cs_test_abc12345");
  assert.equal(stripe.calls[0][1].metadata.hubricon_platform, "shopify");

  const form = await pay(post("/api/checkout", "platform=amazon&from=%2Fstart"));
  assert.equal(form.res.status, 303);
  assert.equal(form.stripe.calls[0][1].metadata.hubricon_platform, "amazon");
});

test("a platform that is neither shopify nor amazon is refused before Stripe is asked", async () => {
  const { res, stripe } = await pay(post("/api/checkout", { platform: "etsy" }));
  assert.equal(res.status, 400);
  const body = await res.json();
  assert.equal(body.error, "bad_platform");
  assert.match(body.message, /Nothing was charged/);
  assert.equal(stripe.calls.length, 0);
});

test("with any part of the chain missing the button says so and takes no card", async () => {
  for (const missing of Object.keys(ENV)) {
    const env = { ...ENV, [missing]: "" };
    const { res, stripe } = await pay(post("/api/checkout", {}), { env });
    assert.equal(res.status, 503, missing);
    const body = await res.json();
    assert.deepEqual(body, { error: "not_configured", message: NOT_SWITCHED_ON });
    assert.equal(stripe.calls.length, 0);
    // The name of what is missing is for the log, never for the buyer.
    assert.ok(!JSON.stringify(body).includes(missing));
  }
  const form = await pay(post("/api/checkout", ""), { env: {} });
  assert.equal(form.res.status, 503);
  assert.match(form.res.headers.get("content-type"), /text\/html/);
  const html = await form.res.text();
  assert.ok(html.includes(NOT_SWITCHED_ON));
  assert.ok(html.includes('href="/start"'));
  assert.ok(!html.includes("STRIPE"));
});

test("when Stripe refuses, the answer is a 502 that says nothing was charged and leaks nothing", async () => {
  const stripe = fakeStripe({ fail: { "checkout.create": "No such price: price_secret123" } });
  const { res } = await pay(post("/api/checkout", {}), { stripe });
  assert.equal(res.status, 502);
  const body = await res.json();
  assert.equal(body.error, "stripe_error");
  assert.match(body.message, /Nothing was charged/);
  assert.ok(!JSON.stringify(body).includes("price_secret123"));
});

test("an oversized or broken body is refused, and a script is slowed down", async () => {
  const big = await pay(post("/api/checkout", { platform: "x".repeat(5000) }));
  assert.equal(big.res.status, 413);
  assert.equal(big.stripe.calls.length, 0);

  const broken = await pay(new Request(`${SITE}/api/checkout`, { method: "POST", headers: { "content-type": "application/json" }, body: "{not json" }));
  assert.equal(broken.res.status, 400);
  assert.equal((await broken.res.json()).error, "bad_request");

  const limiter = new SlidingWindow({ limit: 2, windowMs: 60_000 });
  const stripe = fakeStripe();
  const hit = () => handleCheckout(post("/api/checkout", {}, { "x-forwarded-for": "203.0.113.9" }), { env: ENV, makeStripe: () => stripe, limiter });
  assert.equal((await hit()).status, 200);
  assert.equal((await hit()).status, 200);
  const third = await hit();
  assert.equal(third.status, 429);
  assert.ok(Number(third.headers.get("retry-after")) >= 1);
  assert.equal(stripe.calls.length, 2);
});

// -------------------------------------------------- GET /api/checkout-session
const ID = "cs_test_a1b2c3d4e5f6";
const ask = (id, { session, db = fakeDb(), env = ENV, stripe } = {}) => {
  const s = stripe ?? fakeStripe({ sessions: session ? { [session.id]: session } : {} });
  return handleCheckoutSession(get(`/api/checkout-session?session_id=${id}`), {
    env, makeStripe: () => s, makeDb: () => db, limiter: open(),
  }).then(async (res) => ({ res, body: await res.json(), db, stripe: s }));
};

test("a paid session answers paid, with the email and the upload link the intake page reads", async () => {
  const { res, body, db } = await ask(ID, { session: paidSession() });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("cache-control"), "no-store");
  const token = uploadToken(ENV.CHECKOUT_TOKEN_SECRET, ID);
  const [client] = db.store.clients;
  assert.deepEqual(body, {
    status: "paid",
    email: "owner@brand.com",
    upload_url: `${SITE}/intake?t=${token}`,
    upload_token: token,
    platform: "shopify",
    cancel_url: `${SITE}/api/billing?c=${client.id}&k=${billingKey(ENV.CHECKOUT_TOKEN_SECRET, client.id)}`,
  });
  assert.equal(client.plan, "self_serve");
  assert.equal(db.store.intake_tokens.length, 1);
  // The page setting a client up never sends the email: that is the webhook's.
  assert.equal((db.store.client_emails ?? []).length, 0);
});

test("asking again, or after the webhook, answers the same link and makes nothing twice", async () => {
  const db = fakeDb();
  const first = await ask(ID, { session: paidSession(), db });
  const second = await ask(ID, { session: paidSession(), db });
  assert.deepEqual(second.body, first.body);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.intake_tokens.length, 1);
});

test("open, expired and still-completing sessions say so, and never carry an email or a link", async () => {
  const cases = [
    [paidSession({ status: "open", payment_status: "unpaid" }), "open"],
    [paidSession({ status: "expired", payment_status: "unpaid" }), "expired"],
    [paidSession({ status: "complete", payment_status: "unpaid" }), "processing"],
  ];
  for (const [session, status] of cases) {
    const { res, body, db } = await ask(ID, { session });
    assert.equal(res.status, 200);
    assert.deepEqual(body, { status });
    assert.equal((db.store.clients ?? []).length, 0);
  }
});

test("a paid session whose setup cannot finish says processing, never paid", async () => {
  const down = fakeDb();
  down.fail["clients.insert"] = "database is down";
  const a = await ask(ID, { session: paidSession(), db: down });
  assert.deepEqual(a.body, { status: "processing" });

  const noEmail = await ask(ID, { session: paidSession({ customer_details: {} }) });
  assert.deepEqual(noEmail.body, { status: "processing" });

  // A live client on another plan paid by card: a person settles it.
  const taken = fakeDb({ clients: [{ id: "11111111-1111-4111-8111-111111111111", contact_email: "owner@brand.com", plan: "retainer", status: "active" }] });
  const c = await ask(ID, { session: paidSession(), db: taken });
  assert.deepEqual(c.body, { status: "processing" });
  assert.equal(taken.store.clients[0].plan, "retainer");
});

test("an unknown or malformed session id, or a Checkout that is not this offer's, is a 404", async () => {
  for (const id of ["", "nope", "cs_test_short", "cs_test_a1b2c3d4e5f6%27%20or%201=1", "../etc/passwd"]) {
    const { res, body, stripe } = await ask(id);
    assert.equal(res.status, 404, id);
    assert.deepEqual(body, { error: "not_found" });
    assert.equal(stripe.calls.length, 0);
  }
  const unknown = await ask("cs_test_zzzzzzzz9999");
  assert.equal(unknown.res.status, 404);
  assert.deepEqual(unknown.body, { error: "not_found" });

  const other = paidSession({ metadata: {} });
  const notOurs = await ask(ID, { session: other });
  assert.equal(notOurs.res.status, 404);
  assert.equal((notOurs.db.store.clients ?? []).length, 0);
});

test("when the status cannot be checked the answer tells the buyer not to pay again", async () => {
  const noKey = await ask(ID, { session: paidSession(), env: { ...ENV, STRIPE_SECRET_KEY: "" } });
  assert.equal(noKey.res.status, 503);
  assert.match(noKey.body.message, /Do not pay again/);

  const noSecret = await ask(ID, { session: paidSession(), env: { ...ENV, CHECKOUT_TOKEN_SECRET: "" } });
  assert.equal(noSecret.res.status, 503);
  assert.equal(noSecret.body.error, "not_configured");
  assert.ok(!("email" in noSecret.body));

  const stripe = fakeStripe({ fail: { "checkout.retrieve": "Stripe is unreachable" } });
  const down = await ask(ID, { stripe });
  assert.equal(down.res.status, 502);
  assert.match(down.body.message, /Do not pay again/);
  assert.ok(!JSON.stringify(down.body).includes("unreachable"));
});

// ------------------------------------------------------------ /api/billing
const CLIENT = "22222222-2222-4222-8222-222222222222";
const KEY = billingKey(ENV.CHECKOUT_TOKEN_SECRET, CLIENT);
const card = (over = {}) => ({
  id: CLIENT, contact_email: "owner@brand.com", plan: "self_serve", status: "active",
  stripe_customer_id: "cus_new1", stripe_subscription_id: "sub_new1", ...over,
});
const bill = (request, { db = fakeDb({ clients: [card()] }), stripe = fakeStripe(), env = ENV } = {}) =>
  handleBilling(request, { env, makeStripe: () => stripe, makeDb: () => db, limiter: open() })
    .then((res) => ({ res, db, stripe }));

test("the cancel link opens Stripe's own page on cancelling this subscription, and changes nothing itself", async () => {
  const { res, stripe } = await bill(get(`/api/billing?c=${CLIENT}&k=${KEY}`));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get("location"), "https://billing.stripe.test/p/session/bps_test_1");
  assert.deepEqual(stripe.calls, [["portal.create", {
    customer: "cus_new1",
    return_url: `${SITE}/portal`,
    flow_data: { type: "subscription_cancel", subscription_cancel: { subscription: "sub_new1" } },
  }]]);
});

test("if Stripe refuses the deep link the plain portal opens; if it refuses both, our own one button", async () => {
  const flow = await bill(get(`/api/billing?c=${CLIENT}&k=${KEY}`), { stripe: fakeStripe({ fail: { "portal.flow": "flow not allowed" } }) });
  assert.equal(flow.res.status, 303);
  assert.equal(flow.stripe.calls.length, 2);
  assert.equal(flow.stripe.calls[1][1].flow_data, undefined);

  const none = await bill(get(`/api/billing?c=${CLIENT}&k=${KEY}`), { stripe: fakeStripe({ fail: { "portal.create": "No configuration provided" } }) });
  assert.equal(none.res.status, 200);
  const html = await none.res.text();
  assert.ok(html.includes('<form method="post" action="/api/billing">'));
  assert.ok(html.includes(`name="c" value="${CLIENT}"`));
  assert.ok(html.includes(`name="k" value="${KEY}"`));
  assert.ok(html.includes("Cancel my subscription"));
  assert.ok(html.includes("stops the next $1,000 charge"));
  assert.ok(!/refund/i.test(html));
  assert.ok(!html.includes("No configuration provided"));
  // A GET never cancels: a mail scanner following the link changes nothing.
  assert.ok(!none.stripe.calls.some(([name]) => name === "subscriptions.update"));
});

test("pressing the button ends the subscription with the paid month, and says the date", async () => {
  const { res, stripe, db } = await bill(post("/api/billing", `c=${CLIENT}&k=${encodeURIComponent(KEY)}&action=cancel`));
  assert.equal(res.status, 200);
  assert.deepEqual(stripe.calls, [["subscriptions.update", "sub_new1", { cancel_at_period_end: true }]]);
  const html = await res.text();
  assert.ok(html.includes("Your subscription is cancelled"));
  assert.ok(html.includes("No further charge will be made."));
  assert.ok(html.includes("runs until 1 December 2026"));
  assert.ok(!/refund/i.test(html));
  assert.equal(db.store.funnel_events.length, 1);
  assert.equal(db.store.funnel_events[0].kind, "self_serve_cancel_requested");
  // The row is left as it is: Stripe's subscription.deleted ends it when the month does.
  assert.equal(db.store.clients[0].status, "active");

  const asJson = await bill(post("/api/billing", { c: CLIENT, k: KEY, action: "cancel" }));
  assert.equal(asJson.res.status, 200);
  assert.deepEqual(await asJson.res.json(), { ok: true, cancel_at_period_end: true, ends_at: "2026-12-01T00:00:00.000Z" });
});

test("a POST without the cancel action cancels nothing", async () => {
  const { res, stripe } = await bill(post("/api/billing", `c=${CLIENT}&k=${encodeURIComponent(KEY)}`));
  assert.equal(res.status, 200);
  assert.ok((await res.text()).includes("Cancel my subscription"));
  assert.equal(stripe.calls.length, 0);
  const asJson = await bill(post("/api/billing", { c: CLIENT, k: KEY }));
  assert.equal(asJson.res.status, 400);
  assert.equal(asJson.stripe.calls.length, 0);
});

test("a link that does not verify, or names a client who is not a card client, is a 404 and touches nothing", async () => {
  const other = "33333333-3333-4333-8333-333333333333";
  const tries = [
    get(`/api/billing?c=${CLIENT}&k=wrong`),
    get(`/api/billing?c=${CLIENT}`),
    get(`/api/billing?k=${KEY}`),
    get(`/api/billing?c=${other}&k=${KEY}`),
    get(`/api/billing?c=not-a-uuid&k=${KEY}`),
    post("/api/billing", `c=${CLIENT}&k=wrong&action=cancel`),
  ];
  for (const request of tries) {
    const { res, stripe } = await bill(request);
    assert.equal(res.status, 404);
    assert.equal(stripe.calls.length, 0);
  }
  // A good key for a client on another plan: this route is the card offer's only.
  const retainer = fakeDb({ clients: [card({ plan: "retainer" })] });
  const a = await bill(post("/api/billing", `c=${CLIENT}&k=${encodeURIComponent(KEY)}&action=cancel`), { db: retainer });
  assert.equal(a.res.status, 404);
  assert.equal(a.stripe.calls.length, 0);
  // A good key for a row that has since gone.
  const gone = await bill(get(`/api/billing?c=${CLIENT}&k=${KEY}`), { db: fakeDb() });
  assert.equal(gone.res.status, 404);
});

test("when cancelling cannot be done online the page says nothing changed and how to reach a person", async () => {
  const off = await bill(get(`/api/billing?c=${CLIENT}&k=${KEY}`), { env: { ...ENV, STRIPE_SECRET_KEY: "" } });
  assert.equal(off.res.status, 503);
  const offHtml = await off.res.text();
  assert.ok(offHtml.includes("Nothing changed."));
  assert.ok(offHtml.includes("Reply to the email this link came in"));
  assert.ok(!offHtml.includes("STRIPE"));

  const refused = await bill(post("/api/billing", `c=${CLIENT}&k=${encodeURIComponent(KEY)}&action=cancel`),
    { stripe: fakeStripe({ fail: { "subscriptions.update": "No such subscription: sub_new1" } }) });
  assert.equal(refused.res.status, 502);
  const html = await refused.res.text();
  assert.ok(html.includes("The cancellation did not go through"));
  assert.ok(html.includes("Nothing changed."));
  assert.ok(!html.includes("No such subscription"));
  assert.equal((refused.db.store.funnel_events ?? []).length, 0);

  const asJson = await bill(post("/api/billing", { c: CLIENT, k: KEY, action: "cancel" }),
    { stripe: fakeStripe({ fail: { "subscriptions.update": "boom" } }) });
  assert.equal(asJson.res.status, 502);
  assert.equal((await asJson.res.json()).error, "stripe_error");
});
