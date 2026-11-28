/**
 * The three routes of the card offer, written against what they are handed
 * (the environment, a Stripe client, a database client, a rate limiter) so
 * lib/checkout_routes.test.mjs runs every answer with fakes. The files in
 * api/ hand them the real ones and hold nothing else.
 *
 *   POST /api/checkout                  the pay button: open Stripe's card page
 *   GET  /api/checkout-session          what /start asks when the buyer comes back
 *   GET  /api/billing?c=&k=             the cancel link in the welcome email
 *   POST /api/billing                   the cancel itself, when Stripe's own page cannot be opened
 *
 * Nothing here says when a first Brief arrives and nothing here promises a
 * refund: the page promises neither, so the API cannot.
 */
import { SlidingWindow, clientIp } from "./ratelimit.js";
import {
  PLAN, MONTHLY_FEE_USD, SESSION_ID, START_PATH, createCheckout, isSelfServe, siteBase, verifyBillingKey,
} from "./checkout.js";
import { provisionSelfServe } from "./provision.js";
import { notice, backLink, esc } from "./checkout_page.js";

const MAX_BODY_BYTES = 4 * 1024;
const TEN_MINUTES = 10 * 60 * 1000;

// Per instance, like every other route here: enough to stop a script, no more.
const payWindow = new SlidingWindow({ limit: 20, windowMs: TEN_MINUTES });
// /start asks every 3 seconds for a minute, then every 15: about 60 in ten minutes.
const statusWindow = new SlidingWindow({ limit: 240, windowMs: TEN_MINUTES });
const billingWindow = new SlidingWindow({ limit: 30, windowMs: TEN_MINUTES });

const CHECK_LATER = "Payment status cannot be checked right now. Do not pay again.";
const REPLY = "Reply to the email this link came in and it reaches Hagen.";

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra },
  });
}

const retryAfter = (ms) => ({ "Retry-After": String(Math.ceil(ms / 1000)) });
const tooMany = (ms) => json({ error: "too_many_requests", message: "Too many requests. Try again later." }, 429, retryAfter(ms));
const isJson = (request) => /application\/json/i.test(request.headers.get("content-type") || "");
const wantsJson = (request) => isJson(request) || /application\/json/i.test(request.headers.get("accept") || "");

/** The fields of a small JSON or form body, or a Response saying why not. */
async function readFields(request) {
  if (Number(request.headers.get("content-length") || 0) > MAX_BODY_BYTES) {
    return { refused: json({ error: "request_too_large" }, 413) };
  }
  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) return { refused: json({ error: "request_too_large" }, 413) };
  if (isJson(request)) {
    if (!text.trim()) return { fields: {} };
    try {
      const body = JSON.parse(text);
      if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("not an object");
      return { fields: body };
    } catch {
      return { refused: json({ error: "bad_request", message: "The request was not valid JSON. Nothing was charged." }, 400) };
    }
  }
  return { fields: Object.fromEntries(new URLSearchParams(text)) };
}

// ------------------------------------------------------------ the button --
/**
 * POST /api/checkout  { platform?: "shopify" | "amazon", from?: "/start" }
 *   JSON request  -> 200 { url, session_id }
 *   form post     -> 303 to Stripe's card page
 *   400 bad_platform · 503 not_configured · 502 stripe_error, each { error, message }
 */
export async function handleCheckout(request, { env, makeStripe, limiter = payWindow }) {
  const gate = limiter.hit(clientIp(request.headers));
  if (!gate.ok) return tooMany(gate.retryAfterMs);
  const asJson = wantsJson(request);
  const { fields, refused } = await readFields(request);
  if (refused) return refused;

  const made = await createCheckout({
    env, makeStripe,
    platform: fields.platform,
    from: typeof fields.from === "string" ? fields.from : undefined,
    referer: request.headers.get("referer"),
  });
  if (made.ok) {
    return asJson
      ? json({ url: made.url, session_id: made.id })
      : new Response(null, { status: 303, headers: { Location: made.url, "Cache-Control": "no-store" } });
  }
  // The names of what is missing are for the log, never for the page.
  if (made.missing) console.error(`checkout: not switched on, missing ${made.missing.join(", ")}`);
  if (made.detail) console.error(`checkout: ${made.error}: ${made.detail}`);
  if (asJson) return json({ error: made.error, message: made.message }, made.status);
  return notice(made.status, "No payment was taken", [made.message], backLink(START_PATH, "Back to the page"));
}

// ------------------------------------------------- the buyer comes back --
/**
 * GET /api/checkout-session?session_id=cs_...
 *   200 { status: "open" }        not paid, the card page still works
 *   200 { status: "processing" }  paid or completing, setup not finished: do not pay again
 *   200 { status: "paid", email, upload_url, upload_token, platform, cancel_url }
 *   200 { status: "expired" }
 *   404 { error: "not_found" }    unknown or malformed id, or a session that is not this offer's
 * An email or an upload link is only ever returned for a paid, set-up session.
 */
export async function handleCheckoutSession(request, { env, makeStripe, makeDb, limiter = statusWindow }) {
  const gate = limiter.hit(clientIp(request.headers));
  if (!gate.ok) return tooMany(gate.retryAfterMs);
  const id = new URL(request.url).searchParams.get("session_id") || "";
  if (!SESSION_ID.test(id)) return json({ error: "not_found" }, 404);
  if (!env.STRIPE_SECRET_KEY) return json({ error: "not_configured", message: CHECK_LATER }, 503);

  let session;
  try {
    session = await makeStripe().checkout.sessions.retrieve(id);
  } catch (err) {
    if (err?.code === "resource_missing" || err?.statusCode === 404) return json({ error: "not_found" }, 404);
    console.error(`checkout-session: ${err?.message ?? err}`);
    return json({ error: "stripe_error", message: CHECK_LATER }, 502);
  }
  if (!isSelfServe(session)) return json({ error: "not_found" }, 404);
  if (session.status === "expired") return json({ status: "expired" });
  if (session.status === "open") return json({ status: "open" });
  if (session.payment_status !== "paid") return json({ status: "processing" });

  const missing = ["CHECKOUT_TOKEN_SECRET", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !env[k]);
  if (missing.length > 0) {
    console.error(`checkout-session: paid session ${id} but missing ${missing.join(", ")}`);
    return json({ error: "not_configured", message: CHECK_LATER }, 503);
  }
  // The webhook may not have landed yet. Setting up here too is safe (it is
  // the same idempotent step) and means the buyer's upload link never waits
  // on Stripe's delivery. The welcome email stays the webhook's to send.
  let made;
  try {
    made = await provisionSelfServe({ db: makeDb(), session, env, welcome: false });
  } catch (err) {
    made = { ok: false, error: "exception", detail: err?.message ?? String(err) };
  }
  if (!made.ok) {
    console.error(`checkout-session: ${id} paid, setup not finished: ${made.error}${made.detail ? ` (${made.detail})` : ""}`);
    return json({ status: "processing" });
  }
  return json({
    status: "paid",
    email: made.email,
    upload_url: made.uploadUrl,
    upload_token: made.token,
    platform: made.platform,
    cancel_url: made.billingUrl,
  });
}

// ----------------------------------------------------------------- cancel --
const BILLING_ENV = ["STRIPE_SECRET_KEY", "CHECKOUT_TOKEN_SECRET", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"];
const fee = `$${MONTHLY_FEE_USD.toLocaleString("en-US")}`;

const notValid = (asJson) => (asJson
  ? json({ error: "not_found" }, 404)
  : notice(404, "This link is not valid", ["Nothing changed.", `To cancel, reply to the email your upload link came in and it reaches Hagen.`]));

const notNow = (asJson) => (asJson
  ? json({ error: "not_configured", message: `Cancelling online is not available right now. Nothing changed. ${REPLY}` }, 503)
  : notice(503, "Cancelling online is not available right now", ["Nothing changed.", REPLY]));

async function billingClient(db, clientId) {
  const { data, error } = await db.from("clients")
    .select("id, plan, status, stripe_customer_id, stripe_subscription_id").eq("id", clientId).maybeSingle();
  if (error) return { error: error.message };
  if (!data || data.plan !== PLAN || !data.stripe_customer_id) return { client: null };
  return { client: data };
}

function confirmPage(clientId, key) {
  return notice(200, "Cancel your Profit Record", [
    `Cancelling stops the next ${fee} charge. The month already paid for runs to its end.`,
    "Your Record is yours to export, free, including the day you cancel.",
  ],
  `<form method="post" action="/api/billing">` +
    `<input type="hidden" name="c" value="${esc(clientId)}"><input type="hidden" name="k" value="${esc(key)}">` +
    `<input type="hidden" name="action" value="cancel">` +
    `<button class="btn" type="submit">Cancel my subscription</button></form>`);
}

const longDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

/**
 * GET /api/billing?c=<client id>&k=<key>   the link in the welcome email.
 *   303 to Stripe's customer portal, opened on "cancel this subscription".
 *   If Stripe will not open a portal, 200 with a page holding one button that
 *   POSTs back here. A GET never changes anything, so a mail scanner that
 *   follows the link cancels nothing.
 *
 * POST /api/billing  { c, k, action: "cancel" }  (form or JSON)
 *   Sets the subscription to end with the paid month (cancel_at_period_end):
 *   no further charge. 200 page, or { ok, cancel_at_period_end, ends_at } for JSON.
 *
 * 404 for a link that does not verify · 503 when not configured · 502 when Stripe refuses.
 */
export async function handleBilling(request, { env, makeStripe, makeDb, limiter = billingWindow }) {
  const gate = limiter.hit(clientIp(request.headers));
  if (!gate.ok) return tooMany(gate.retryAfterMs);
  const posting = request.method === "POST";
  const asJson = posting && wantsJson(request);

  let fields;
  if (posting) {
    const read = await readFields(request);
    if (read.refused) return read.refused;
    fields = read.fields;
  } else {
    fields = Object.fromEntries(new URL(request.url).searchParams);
  }
  const clientId = typeof fields.c === "string" ? fields.c : "";
  const key = typeof fields.k === "string" ? fields.k : "";

  if (BILLING_ENV.some((k) => !env[k])) {
    console.error(`billing: missing ${BILLING_ENV.filter((k) => !env[k]).join(", ")}`);
    return notNow(asJson);
  }
  if (!verifyBillingKey(env.CHECKOUT_TOKEN_SECRET, clientId, key)) return notValid(asJson);

  const db = makeDb();
  const found = await billingClient(db, clientId);
  if (found.error) {
    console.error(`billing: ${found.error}`);
    return notNow(asJson);
  }
  if (!found.client) return notValid(asJson);
  const client = found.client;
  const stripe = makeStripe();
  const base = siteBase(env);

  if (!posting) {
    const open = { customer: client.stripe_customer_id, return_url: `${base}/portal` };
    const tries = client.stripe_subscription_id
      ? [{ ...open, flow_data: { type: "subscription_cancel", subscription_cancel: { subscription: client.stripe_subscription_id } } }, open]
      : [open];
    for (const params of tries) {
      try {
        const portal = await stripe.billingPortal.sessions.create(params);
        if (portal?.url) return new Response(null, { status: 303, headers: { Location: portal.url, "Cache-Control": "no-store" } });
      } catch (err) {
        console.error(`billing: portal refused: ${err?.message ?? err}`);
      }
    }
    // Stripe's page could not be opened (no portal configuration saved, or
    // the subscription has already ended there). Offer our own one button.
    if (!client.stripe_subscription_id) return notNow(false);
    return confirmPage(client.id, key);
  }

  if (fields.action !== "cancel") {
    return asJson ? json({ error: "bad_request", message: "Nothing changed." }, 400) : confirmPage(client.id, key);
  }
  if (!client.stripe_subscription_id) return notValid(asJson);
  let sub;
  try {
    sub = await stripe.subscriptions.update(client.stripe_subscription_id, { cancel_at_period_end: true });
  } catch (err) {
    console.error(`billing: cancel refused for ${client.id}: ${err?.message ?? err}`);
    const message = `The cancellation did not go through. Nothing changed. ${REPLY}`;
    return asJson
      ? json({ error: "stripe_error", message }, 502)
      : notice(502, "The cancellation did not go through", ["Nothing changed.", REPLY]);
  }
  try {
    await db.from("funnel_events").insert({
      kind: "self_serve_cancel_requested", client_id: client.id, note: client.stripe_subscription_id,
      payload: { plan: PLAN, via: "cancel_link" },
    });
  } catch {
    // A log line never fails a cancellation.
  }
  const unix = sub?.cancel_at ?? sub?.items?.data?.[0]?.current_period_end ?? sub?.current_period_end ?? null;
  const endsAt = unix ? new Date(unix * 1000).toISOString() : null;
  if (asJson) return json({ ok: true, cancel_at_period_end: true, ends_at: endsAt });
  return notice(200, "Your subscription is cancelled", [
    "No further charge will be made.",
    endsAt ? `The month already paid for runs until ${longDate(endsAt)}.` : "The month already paid for runs to its end.",
    "Your Record is yours to export, free, including today.",
    `Cancelled by mistake? ${REPLY}`,
  ]);
}
