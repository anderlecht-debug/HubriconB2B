// Instant setup after a paid self-serve Checkout Session. Everything runs on
// fakes (lib/checkout_fakes.mjs): no Stripe, no database, no email leaves.
import test from "node:test";
import assert from "node:assert/strict";
import { uploadToken, tokenHash, verifyBillingKey } from "./checkout.js";
import {
  provisionSelfServe, welcomeEmail, sessionFacts, decide,
  WELCOME_KIND, WELCOME_SUBJECT, TOKEN_LABEL, TOKEN_DAYS,
} from "./provision.js";
import { ENV, fakeDb, fakeResend, paidSession } from "./checkout_fakes.mjs";

const NOW = new Date("2026-11-28T15:00:00Z");
const run = (db, over = {}) => {
  const mail = over.mail ?? fakeResend();
  return provisionSelfServe({ db, session: paidSession(), env: ENV, now: NOW, welcome: true, fetchImpl: mail.fetchImpl, ...over })
    .then((out) => ({ out, mail }));
};

test("a paid session becomes a paid client waiting for files, with a link, a seat and one email", async () => {
  const db = fakeDb();
  const { out, mail } = await run(db);
  assert.equal(out.ok, true);
  assert.equal(out.outcome, "create");
  assert.equal(out.email, "owner@brand.com");
  assert.equal(out.emailed, true);

  const [client] = db.store.clients;
  assert.deepEqual(
    { ...client, id: undefined },
    {
      id: undefined, contact_email: "owner@brand.com", contact_name: "Dana Owner",
      plan: "self_serve", status: "active", platform: "shopify",
      monthly_fee_usd: 1000, free_months: 0,
      stripe_customer_id: "cus_new1", stripe_subscription_id: "sub_new1",
      retainer_started_at: NOW.toISOString(), retainer_source: "first_invoice",
    },
  );

  const token = uploadToken(ENV.CHECKOUT_TOKEN_SECRET, "cs_test_a1b2c3d4e5f6");
  assert.equal(out.uploadUrl, `https://www.hubricon.com/intake?t=${token}`);
  const [stored] = db.store.intake_tokens;
  assert.equal(stored.client_id, client.id);
  assert.equal(stored.token_hash, tokenHash(token), "only the hash is stored");
  assert.equal(stored.label, TOKEN_LABEL);
  assert.ok(!/^consent/i.test(stored.label), "a label starting with consent would make it a consent link");
  assert.equal(stored.expires_at, new Date(NOW.getTime() + TOKEN_DAYS * 86400000).toISOString());

  const key = new URL(out.billingUrl).searchParams.get("k");
  assert.equal(new URL(out.billingUrl).searchParams.get("c"), client.id);
  assert.ok(verifyBillingKey(ENV.CHECKOUT_TOKEN_SECRET, client.id, key));

  assert.deepEqual(db.users.map((u) => u.email), ["owner@brand.com"]);
  assert.deepEqual(db.store.client_users.map((s) => [s.user_id, s.client_id, s.role]), [[db.users[0].id, client.id, "owner"]]);

  assert.equal(mail.sent.length, 1);
  assert.deepEqual(mail.sent[0].to, ["owner@brand.com"]);
  assert.equal(mail.sent[0].subject, WELCOME_SUBJECT);
  assert.ok(mail.sent[0].text.includes(out.uploadUrl));
  assert.ok(mail.sent[0].text.includes(out.billingUrl));
  assert.deepEqual(db.store.client_emails.map((e) => [e.client_id, e.kind, e.ref_id]), [[client.id, WELCOME_KIND, "cs_test_a1b2c3d4e5f6"]]);
  assert.deepEqual(db.store.funnel_events.map((e) => [e.kind, e.note]), [["self_serve_paid", "cs_test_a1b2c3d4e5f6"]]);
});

test("the webhook delivered twice changes nothing and sends nothing the second time", async () => {
  const db = fakeDb();
  const first = await run(db);
  const again = await run(db, { now: new Date("2026-11-29T09:00:00Z") });
  assert.equal(again.out.ok, true);
  assert.equal(again.out.outcome, "same");
  assert.equal(again.out.emailed, false);
  assert.equal(again.mail.sent.length, 0);
  assert.equal(again.out.uploadUrl, first.out.uploadUrl);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.clients[0].retainer_started_at, NOW.toISOString(), "the day they paid does not move");
  assert.equal(db.store.intake_tokens.length, 1);
  assert.equal(db.store.client_users.length, 1);
  assert.equal(db.store.client_emails.length, 1);
  assert.equal(db.store.funnel_events.length, 1);
});

test("the paid page provisions without the webhook and sends no email; the webhook then sends exactly one", async () => {
  const db = fakeDb();
  const page = await run(db, { welcome: false });
  assert.equal(page.out.ok, true);
  assert.equal(page.out.emailed, false);
  assert.equal(page.mail.sent.length, 0);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.intake_tokens.length, 1);
  assert.equal((db.store.client_emails ?? []).length, 0);

  const hook = await run(db);
  assert.equal(hook.out.outcome, "same");
  assert.equal(hook.out.emailed, true);
  assert.equal(hook.mail.sent.length, 1);
  assert.equal(hook.out.uploadUrl, page.out.uploadUrl, "both callers hand out the same link");
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.intake_tokens.length, 1);
  assert.equal(db.store.client_users.length, 1);

  const pageAgain = await run(db, { welcome: false });
  assert.equal(pageAgain.out.uploadUrl, page.out.uploadUrl);
  assert.equal(pageAgain.mail.sent.length, 0);
});

test("both callers at once still make one client and one link", async () => {
  const db = fakeDb();
  const mail = fakeResend();
  const [a, b] = await Promise.all([run(db, { mail }), run(db, { mail, welcome: false })]);
  assert.equal(a.out.ok && b.out.ok, true);
  assert.equal(a.out.clientId, b.out.clientId);
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.intake_tokens.length, 1);
  assert.equal(mail.sent.length, 1);
});

test("a lost insert race is a re-read, not a second client", async () => {
  const db = fakeDb();
  // The other caller's row appears between this caller's lookup and its insert.
  const from = db.from;
  let planted = false;
  db.from = (name) => {
    const q = from(name);
    if (name === "clients" && !planted) {
      const insert = q.insert;
      q.insert = (row) => {
        planted = true;
        db.store.clients = [{ id: "c-raced", ...row }];
        return insert(row);
      };
    }
    return q;
  };
  const { out } = await run(db);
  assert.equal(out.ok, true);
  assert.equal(out.clientId, "c-raced");
  assert.equal(out.outcome, "same");
  assert.equal(db.store.clients.length, 1);
});

test("where they sell comes from the session and lands on the client row", async () => {
  const db = fakeDb();
  const session = paidSession({ metadata: { hubricon_plan: "self_serve", hubricon_platform: "amazon" } });
  const { out, mail } = await run(db, { session });
  assert.equal(out.platform, "amazon");
  assert.equal(db.store.clients[0].platform, "amazon");
  assert.match(mail.sent[0].text, /if you sell on Amazon/);
  assert.doesNotMatch(mail.sent[0].text, /if you sell on Shopify/);
});

test("nothing is provisioned for a session that is unpaid, not ours, or has no email", async () => {
  for (const [session, error] of [
    [paidSession({ payment_status: "unpaid" }), "not_paid"],
    [paidSession({ payment_status: "no_payment_required" }), "not_paid"],
    [paidSession({ metadata: {} }), "not_self_serve"],
    [paidSession({ mode: "payment" }), "not_self_serve"],
    [paidSession({ customer_details: { email: "not an email" } }), "no_email"],
    [paidSession({ subscription: null }), "not_paid"],
  ]) {
    const db = fakeDb();
    const { out, mail } = await run(db, { session });
    assert.equal(out.ok, false);
    assert.equal(out.error, error);
    assert.equal(db.store.clients, undefined);
    assert.equal(db.store.intake_tokens.length, 0);
    assert.equal(mail.sent.length, 0);
  }
  const { out } = await run(fakeDb(), { env: { ...ENV, CHECKOUT_TOKEN_SECRET: "" } });
  assert.equal(out.error, "not_configured");
});

test("a prospect or a client who left is converted on their own row, keeping their earlier links", async () => {
  for (const status of ["pending", "churned", "declined"]) {
    const db = fakeDb({
      clients: [{
        id: "c-old", contact_email: "owner@brand.com", contact_name: "D. Owner", status, plan: "retainer",
        platform: "amazon", monthly_fee_usd: 6000, free_months: 1, stripe_customer_id: null, stripe_subscription_id: null,
        retainer_started_at: null, declined_at: status === "declined" ? "2026-10-01T00:00:00Z" : null,
      }],
      intake_tokens: [{ id: "t-old", client_id: "c-old", token_hash: "feed", label: "audit intake", revoked_at: null }],
    });
    const { out } = await run(db);
    assert.equal(out.ok, true);
    assert.equal(out.outcome, "convert");
    assert.equal(out.clientId, "c-old");
    assert.equal(db.store.clients.length, 1);
    const c = db.store.clients[0];
    assert.deepEqual(
      [c.plan, c.status, c.monthly_fee_usd, c.free_months, c.platform, c.stripe_subscription_id, c.declined_at, c.contact_name],
      ["self_serve", "active", 1000, 0, "shopify", "sub_new1", null, "D. Owner"],
    );
    assert.equal(db.store.intake_tokens.length, 2);
    assert.equal(db.store.intake_tokens[0].revoked_at, null, "an earlier upload link is never revoked by paying");
  }
});

test("a live client on another plan is not overwritten: a conflict, logged once, nothing sent", async () => {
  const live = {
    id: "c-ret", contact_email: "owner@brand.com", status: "active", plan: "retainer", platform: "amazon",
    monthly_fee_usd: 6000, free_months: 1, stripe_customer_id: "cus_old", stripe_subscription_id: "sub_old",
  };
  const db = fakeDb({ clients: [live] });
  const { out, mail } = await run(db);
  assert.equal(out.ok, false);
  assert.equal(out.error, "conflict");
  assert.deepEqual(db.store.clients, [live]);
  assert.equal(db.store.intake_tokens.length, 0);
  assert.equal(mail.sent.length, 0);
  await run(db);
  assert.deepEqual(db.store.funnel_events.map((e) => e.kind), ["self_serve_conflict"]);
});

test("paying twice keeps the first subscription, still hands over a working link, and is logged for a person", async () => {
  const db = fakeDb();
  await run(db);
  const second = paidSession({ id: "cs_test_secondpayment1", customer: "cus_new2", subscription: "sub_new2" });
  const { out, mail } = await run(db, { session: second });
  assert.equal(out.ok, true);
  assert.equal(out.outcome, "duplicate");
  assert.equal(db.store.clients.length, 1);
  assert.equal(db.store.clients[0].stripe_subscription_id, "sub_new1");
  assert.equal(db.store.intake_tokens.length, 2);
  assert.equal(mail.sent.length, 1);
  const logged = db.store.funnel_events.find((e) => e.kind === "self_serve_duplicate_payment");
  assert.equal(logged.note, "cs_test_secondpayment1");
  assert.equal(logged.payload.kept_subscription, "sub_new1");
  assert.equal(logged.payload.subscription, "sub_new2");
});

test("a failed email is an error so Stripe retries, and the retry sends it once", async () => {
  const db = fakeDb();
  const down = await run(db, { mail: fakeResend({ status: 500 }) });
  assert.equal(down.out.ok, false);
  assert.equal(down.out.error, "email");
  assert.equal((db.store.client_emails ?? []).length, 0, "an unsent email is not recorded as sent");
  assert.equal(db.store.clients.length, 1, "the client is already real, and the paid page can already hand over the link");

  const retry = await run(db);
  assert.equal(retry.out.ok, true);
  assert.equal(retry.out.emailed, true);
  assert.equal(retry.mail.sent.length, 1);
});

test("the email is not sent before the buyer can sign in: a seat failure stops it", async () => {
  const db = fakeDb();
  db.fail["client_users.upsert"] = "permission denied";
  const { out, mail } = await run(db);
  assert.equal(out.ok, false);
  assert.equal(out.error, "seat");
  assert.equal(mail.sent.length, 0);

  // The paid page does not wait on the seat.
  const page = await run(db, { welcome: false });
  assert.equal(page.out.ok, true);
});

test("a buyer who already has a sign-in keeps it and gains the seat", async () => {
  const db = fakeDb({}, { users: [{ id: "u-existing", email: "owner@brand.com" }] });
  const { out } = await run(db);
  assert.equal(out.ok, true);
  assert.equal(db.users.length, 1);
  assert.deepEqual(db.store.client_users.map((s) => s.user_id), ["u-existing"]);
});

test("a database or token failure is reported, never papered over", async () => {
  let db = fakeDb();
  db.fail["clients.select"] = "connection refused";
  assert.deepEqual((await run(db)).out, { ok: false, error: "database", detail: "connection refused" });

  db = fakeDb();
  db.fail["rpc.create_intake_token"] = "function is down";
  const { out, mail } = await run(db);
  assert.equal(out.error, "token");
  assert.equal(mail.sent.length, 0);
});

test("sessionFacts lowercases the email and reads ids whether Stripe expanded them or not", () => {
  assert.deepEqual(
    sessionFacts(paidSession({ customer: { id: "cus_x" }, subscription: { id: "sub_x" }, customer_details: null, customer_email: " A@B.co " })),
    { id: "cs_test_a1b2c3d4e5f6", email: "a@b.co", name: null, customer: "cus_x", subscription: "sub_x", platform: "shopify" },
  );
  assert.equal(decide(null, {}), "create");
});

// ------------------------------------------------------------- the email --
const mailFor = (over = {}) => welcomeEmail({
  platform: "shopify",
  uploadUrl: "https://www.hubricon.com/intake?t=TOKEN",
  cancelUrl: "https://www.hubricon.com/api/billing?c=ID&k=KEY",
  portalUrl: "https://www.hubricon.com/portal",
  alone: true,
  ...over,
});

test("the welcome email is the copy chief's: the subject, the two links, the files for their platform", () => {
  const { subject, text, html } = mailFor();
  assert.equal(subject, "Your Hubricon upload link, and what happens next");
  for (const body of [text, html]) {
    assert.ok(body.includes("Your payment went through. The Profit Record is $1,000 a month."));
    assert.ok(body.includes("https://www.hubricon.com/intake?t=TOKEN"));
    assert.ok(body.includes("https://www.hubricon.com/api/billing?c=ID&amp;k=KEY") || body.includes("https://www.hubricon.com/api/billing?c=ID&k=KEY"));
    assert.ok(body.includes("Keep this email. The link is yours alone."));
    assert.ok(body.includes("What to send, if you sell on Shopify:"));
    assert.ok(body.includes("Your Products export."));
    assert.ok(body.includes("Profit Brief No. 001 is written once both files are in."));
    assert.ok(body.includes("hubricon.com/portal"));
    assert.ok(body.includes("Sign in there with the email you paid with."));
    assert.ok(body.includes("Reply to this email and it reaches me."));
    assert.ok(body.includes("It stops the next charge."));
    assert.ok(!body.includes("Amazon"));
  }
  assert.ok(text.endsWith("Hagen Simmons\nHubricon"));
  const amazon = mailFor({ platform: "amazon" });
  assert.ok(amazon.text.includes("What to send, if you sell on Amazon, one file per month for the last 6 months:"));
  assert.ok(amazon.text.includes("1. Reports, Business Reports, Detail Page Sales and Traffic by Child Item.\n2. Reports, SKU Economics."));
  assert.ok(amazon.text.includes("once both reports are in"));
  assert.ok(!amazon.text.includes("Shopify"));
});

test("the email promises no time, no refund, no call, no free month and no old price", () => {
  for (const platform of ["shopify", "amazon"]) {
    for (const alone of [true, false]) {
      const { text, html } = mailFor({ platform, alone });
      for (const body of [text, html]) {
        assert.doesNotMatch(body, /refund|money back|guarantee/i);
        assert.doesNotMatch(body, /\b(within|in under|hours?|minutes?|tomorrow|today|24)\b/i);
        assert.doesNotMatch(body, /free month|proving month|\$6,000|6000|calendly|book a call|kickoff|walkthrough/i);
        assert.doesNotMatch(body, /one click/i, "the cancel link opens Stripe's page, where the buyer confirms");
      }
    }
  }
});

test("'no other clients yet' is printed only while it is true", async () => {
  assert.ok(mailFor({ alone: true }).text.includes("Hubricon is new. There are no other clients yet and no result measured on a real brand."));
  const later = mailFor({ alone: false }).text;
  assert.ok(later.includes("Hubricon is new."));
  assert.doesNotMatch(later, /no other clients|no result measured/);

  // The first buyer is alone; internal test rows and prospects do not count as clients.
  const first = fakeDb({
    clients: [
      { id: "c-test", contact_email: "demo@hubricon.internal", status: "active", plan: "retainer" },
      { id: "c-lead", contact_email: "lead@else.com", status: "pending", plan: "retainer" },
    ],
  });
  assert.match((await run(first)).mail.sent[0].text, /There are no other clients yet/);

  // The second buyer is not.
  const second = fakeDb({ clients: [{ id: "c-1", contact_email: "first@buyer.com", status: "active", plan: "self_serve", stripe_subscription_id: "sub_a" }] });
  assert.doesNotMatch((await run(second)).mail.sent[0].text, /no other clients/);

  // If the count cannot be read, the sentence is left out rather than risked.
  const blind = fakeDb();
  const from = blind.from;
  blind.from = (name) => {
    const q = from(name);
    const within = q.in;
    q.in = (...args) => { if (name === "clients") throw new Error("down"); return within(...args); };
    return q;
  };
  assert.doesNotMatch((await run(blind)).mail.sent[0].text, /no other clients/);
});

test("an internal test address is provisioned but never emailed", async () => {
  const db = fakeDb();
  const { out, mail } = await run(db, { session: paidSession({ customer_details: { email: "qa@hubricon.internal" } }) });
  assert.equal(out.ok, true);
  assert.equal(mail.sent.length, 0);
  assert.equal(db.store.client_emails.length, 1);
});
