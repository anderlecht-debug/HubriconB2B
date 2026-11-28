/**
 * Instant setup for a paid self-serve Checkout Session: the client row, the
 * upload link, the portal seat and the one welcome email, with nobody from
 * Hubricon in the loop.
 *
 * Two callers race each other and both must be safe to run any number of
 * times, in either order, at once:
 *
 *   the webhook   (checkout.session.completed)  provisions and sends the email
 *   the paid page (GET /api/checkout-session)   provisions and sends nothing
 *
 * What makes that safe:
 *   - the client is found by subscription, then customer, then email, and the
 *     unique constraints on those three columns turn a lost race into a
 *     re-read instead of a second row;
 *   - the upload token is derived from the session id (lib/checkout.js), so
 *     both callers mint the same one and a duplicate mint is a success;
 *   - the welcome email is deduped on client_emails (client, kind, session).
 *     It is sent first and recorded after: a webhook that dies between the
 *     two sends it twice on Stripe's retry, which is better than never,
 *     because the email is the only place the cancel link lives.
 *
 * A live client on another plan is never overwritten: that is a conflict a
 * person settles, and the webhook says so to Stripe. A client who pays twice
 * keeps the first subscription on the row; the second is logged for Hagen
 * (funnel_events, self_serve_duplicate_payment) and nothing is refunded or
 * cancelled by code.
 */
import {
  PLAN, MONTHLY_FEE_USD, isSelfServe, readPlatform, siteBase,
  uploadToken, tokenHash, uploadUrl, billingUrl,
} from "./checkout.js";
import { sendResend, EMAIL_FONT, EMAIL_INK, EMAIL_INK_2, EMAIL_RULE, EMAIL_P, EMAIL_SMALL, EMAIL_LIST, EMAIL_URL } from "./tool_email.js";

export const WELCOME_KIND = "self_serve_welcome";
export const WELCOME_SUBJECT = "Your Hubricon upload link, and what happens next";
export const TOKEN_LABEL = "self-serve checkout";
// The email says "Keep this email", so the link outlives the default 90 days.
export const TOKEN_DAYS = 365;

const CLIENT_COLS = "id, status, plan, contact_email, contact_name, stripe_customer_id, stripe_subscription_id, platform, retainer_started_at";
const LIVE = ["active", "past_due"];
const DEFAULT_FROM = "Hagen Simmons <hagen.simmons@hubricon.com>";
const DEFAULT_REPLY_TO = "hagen.simmons@hubricon.com";

const idOf = (v) => (v && typeof v === "object" ? v.id : v) || null;
const isDuplicate = (error) => error?.code === "23505" || /duplicate key/i.test(error?.message || "");
const isInternal = (email) => /@hubricon\.internal$/i.test(email || "");
const fail = (error, detail, extra = {}) => ({ ok: false, error, detail: detail ?? null, ...extra });

/** What a paid session says about its buyer. */
export function sessionFacts(session) {
  const email = String(session?.customer_details?.email ?? session?.customer_email ?? "").trim().toLowerCase();
  const name = String(session?.customer_details?.name ?? "").trim().slice(0, 120) || null;
  return {
    id: session?.id ?? null,
    email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= 254 ? email : null,
    name,
    customer: idOf(session?.customer),
    subscription: idOf(session?.subscription),
    platform: readPlatform(session),
  };
}

// ------------------------------------------------------------- the email --
const SHOPIFY_FILES = [
  "Your Products export. Products, Export, All products, Plain CSV file.",
  "Your Orders export for the last 6 months. Orders, clear any filters, Export, Orders by date, set the range, Plain CSV file, Export orders. Shopify emails that one to you.",
];
const AMAZON_FILES = [
  "Reports, Business Reports, Detail Page Sales and Traffic by Child Item.",
  "Reports, SKU Economics.",
];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/**
 * The email after payment, in the copy chief's wording (27 Nov 2026), with
 * only the platform block that applies. It promises no time for the first
 * Brief and no refund. `alone` is whether Hubricon has no other client: the
 * sentence that says so is printed only while it is true.
 */
export function welcomeEmail({ platform, uploadUrl: upload, cancelUrl, portalUrl, alone }) {
  const amazon = platform === "amazon";
  const heading = amazon
    ? "What to send, if you sell on Amazon, one file per month for the last 6 months:"
    : "What to send, if you sell on Shopify:";
  const files = amazon ? AMAZON_FILES : SHOPIFY_FILES;
  const portal = String(portalUrl).replace(/^https?:\/\/(www\.)?/i, "");
  const next = [
    "Each file shows Received, then Read, or says what to fix.",
    `Profit Brief No. 001 is written once both ${amazon ? "reports" : "files"} are in.`,
    `It opens at ${portal}. Sign in there with the email you paid with. I email you the day it is there.`,
  ];
  const stands = [
    "What I said on the phone stands. Hubricon is new.",
    ...(alone ? ["There are no other clients yet and no result measured on a real brand."] : []),
    "Every move I call is written down with its expected dollars before you make it, and graded on your own later reports. Misses stay on.",
  ].join(" ");
  const cancelAfter = "It stops the next charge. Your Record is yours to export, free, including the day you cancel.";

  const text = [
    "Hi,",
    `Your payment went through. The Profit Record is $${MONTHLY_FEE_USD.toLocaleString("en-US")} a month.`,
    `Your upload page is here:\n${upload}`,
    "Keep this email. The link is yours alone.",
    `${heading}\n${files.map((f, i) => `${i + 1}. ${f}`).join("\n")}`,
    `What happens next:\n${next.join("\n")}`,
    stands,
    `To cancel, open this link and confirm:\n${cancelUrl}\n${cancelAfter}`,
    "Reply to this email and it reaches me.",
    "Hagen Simmons\nHubricon",
  ].join("\n\n");

  const html = [
    `<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:${EMAIL_FONT};color:${EMAIL_INK};font-size:16px;line-height:1.6">`,
    `  <p style="font-size:17px;font-weight:600;letter-spacing:-0.01em;color:${EMAIL_INK};margin:0 0 28px">Hubricon</p>`,
    `  <p ${EMAIL_P}>Hi,</p>`,
    `  <p ${EMAIL_P}>Your payment went through. The Profit Record is $${MONTHLY_FEE_USD.toLocaleString("en-US")} a month.</p>`,
    `  <p ${EMAIL_P}>Your upload page is here:<br><a href="${esc(upload)}" ${EMAIL_URL}>${esc(upload)}</a></p>`,
    `  <p ${EMAIL_P}>Keep this email. The link is yours alone.</p>`,
    `  <p ${EMAIL_P}>${esc(heading)}</p>`,
    `  <ol ${EMAIL_LIST}>\n${files.map((f) => `    <li style="margin:0 0 8px">${esc(f)}</li>`).join("\n")}\n  </ol>`,
    `  <p ${EMAIL_P}>What happens next:<br>${next.map(esc).join("<br>")}</p>`,
    `  <p ${EMAIL_P}>${esc(stands)}</p>`,
    `  <p ${EMAIL_P}>To cancel, open this link and confirm:<br><a href="${esc(cancelUrl)}" ${EMAIL_URL}>${esc(cancelUrl)}</a><br>${esc(cancelAfter)}</p>`,
    `  <p ${EMAIL_SMALL}>Reply to this email and it reaches me.</p>`,
    `  <hr style="border:0;border-top:1px solid ${EMAIL_RULE};margin:8px 0 20px">`,
    `  <p style="font-size:14px;color:${EMAIL_INK};margin:0">Hagen Simmons<br><span style="color:${EMAIL_INK_2}">Hubricon</span></p>`,
    `</div>`,
  ].join("\n");

  return { subject: WELCOME_SUBJECT, text, html };
}

// ---------------------------------------------------------- the database --
async function findClient(db, { subscription, customer, email }) {
  for (const [column, value] of [["stripe_subscription_id", subscription], ["stripe_customer_id", customer], ["contact_email", email]]) {
    if (!value) continue;
    const { data, error } = await db.from("clients").select(CLIENT_COLS).eq(column, value).maybeSingle();
    if (error) return { error: error.message };
    if (data) return { client: data };
  }
  return { client: null };
}

/** create | same | convert | duplicate | conflict */
export function decide(client, facts) {
  if (!client) return "create";
  if (client.plan === PLAN && client.stripe_subscription_id === facts.subscription) return "same";
  if (LIVE.includes(client.status)) return client.plan === PLAN ? "duplicate" : "conflict";
  return "convert";
}

function paidRow(facts, now) {
  return {
    plan: PLAN,
    status: "active",
    platform: facts.platform,
    monthly_fee_usd: MONTHLY_FEE_USD,
    free_months: 0,
    stripe_customer_id: facts.customer,
    stripe_subscription_id: facts.subscription,
    retainer_started_at: now.toISOString(),
    retainer_source: "first_invoice",
  };
}

/** One row per (kind, session): a note for Hagen's digest, never a second time. */
async function logOnce(db, kind, clientId, facts, extra = {}) {
  try {
    const seen = await db.from("funnel_events").select("id").eq("kind", kind).eq("note", facts.id).limit(1);
    if (seen.error || seen.data?.length) return;
    await db.from("funnel_events").insert({
      kind, client_id: clientId, note: facts.id,
      payload: { plan: PLAN, platform: facts.platform, customer: facts.customer, subscription: facts.subscription, ...extra },
    });
  } catch {
    // A log line never fails a payment.
  }
}

async function ensureClient(db, facts, now) {
  let found = await findClient(db, facts);
  if (found.error) return fail("database", found.error);
  let what = decide(found.client, facts);

  if (what === "create") {
    const { data, error } = await db.from("clients")
      .insert({ contact_email: facts.email, contact_name: facts.name, ...paidRow(facts, now) })
      .select(CLIENT_COLS).single();
    if (!error) return { ok: true, client: data, what };
    if (!isDuplicate(error)) return fail("database", error.message);
    // The other caller got there first: read what it wrote.
    found = await findClient(db, facts);
    if (found.error || !found.client) return fail("database", found.error ?? "client vanished after a duplicate insert");
    what = decide(found.client, facts);
  }

  const client = found.client;
  if (what === "conflict") {
    return fail("conflict", `client ${client.id} is ${client.status} on the ${client.plan} plan`, { clientId: client.id });
  }
  if (what === "convert") {
    const patch = { ...paidRow(facts, now), declined_at: null, ...(client.contact_name ? {} : { contact_name: facts.name }) };
    const { error } = await db.from("clients").update(patch).eq("id", client.id);
    if (error) return fail("database", error.message);
    return { ok: true, client: { ...client, ...patch }, what };
  }
  return { ok: true, client, what };
}

async function mintToken(db, clientId, token, now) {
  const { error } = await db.rpc("create_intake_token", {
    p_client_id: clientId,
    p_token_hash: tokenHash(token),
    p_label: TOKEN_LABEL,
    p_expires_at: new Date(now.getTime() + TOKEN_DAYS * 86400000).toISOString(),
  });
  return !error || isDuplicate(error) ? null : error.message;
}

/** The portal signs in with `create_user: false`, so the buyer's user and seat must exist before the email says "sign in". */
export async function ensureSeat(db, clientId, email) {
  let userId = null;
  const created = await db.auth.admin.createUser({ email, email_confirm: true });
  if (!created.error && created.data?.user?.id) {
    userId = created.data.user.id;
  } else {
    for (let page = 1; page <= 20 && !userId; page += 1) {
      const { data, error } = await db.auth.admin.listUsers({ page, perPage: 1000 });
      if (error) return error.message;
      const users = data?.users ?? [];
      userId = users.find((u) => (u.email || "").toLowerCase() === email)?.id ?? null;
      if (users.length < 1000) break;
    }
    if (!userId) return created.error?.message ?? "could not create the portal user";
  }
  const { error } = await db.from("client_users")
    .upsert({ user_id: userId, client_id: clientId, role: "owner" }, { onConflict: "user_id,client_id" });
  return error ? error.message : null;
}

/** True only when the count came back and it is zero. */
async function hasNoOtherClient(db, clientId) {
  try {
    const { data, error } = await db.from("clients").select("id, contact_email")
      .in("status", ["active", "past_due", "churned"]).neq("id", clientId).limit(200);
    if (error || !Array.isArray(data)) return false;
    return data.filter((c) => !isInternal(c.contact_email)).length === 0;
  } catch {
    return false;
  }
}

/**
 * Provision one paid session. Resolves to
 *   { ok: true, clientId, email, platform, token, uploadUrl, billingUrl, outcome, emailed }
 *   { ok: false, error, detail }   error: not_self_serve | not_paid | not_configured | no_email |
 *                                         database | conflict | token | seat | email
 * `welcome: true` (the webhook) also guarantees the seat and sends the email;
 * without it (the paid page) the seat is tried once and nothing is sent.
 */
export async function provisionSelfServe({ db, session, env = {}, now = new Date(), welcome = false, fetchImpl }) {
  if (!isSelfServe(session)) return fail("not_self_serve");
  if (session.payment_status !== "paid") return fail("not_paid", session.payment_status);
  const secret = env.CHECKOUT_TOKEN_SECRET;
  if (!secret) return fail("not_configured", "CHECKOUT_TOKEN_SECRET not set");
  const facts = sessionFacts(session);
  if (!facts.id || !facts.email) return fail("no_email", "the paid session carries no usable email");
  if (!facts.subscription) return fail("not_paid", "the session has no subscription yet");

  const made = await ensureClient(db, facts, now);
  if (!made.ok) {
    if (made.error === "conflict") await logOnce(db, "self_serve_conflict", made.clientId, facts, { detail: made.detail });
    return made;
  }
  const client = made.client;
  if (made.what === "create" || made.what === "convert") await logOnce(db, "self_serve_paid", client.id, facts);
  if (made.what === "duplicate") {
    await logOnce(db, "self_serve_duplicate_payment", client.id, facts, { kept_subscription: client.stripe_subscription_id });
  }

  const token = uploadToken(secret, facts.id);
  const tokenError = await mintToken(db, client.id, token, now);
  if (tokenError) return fail("token", tokenError, { clientId: client.id });

  const base = siteBase(env);
  const result = {
    ok: true,
    clientId: client.id,
    email: client.contact_email || facts.email,
    platform: made.what === "duplicate" || made.what === "same" ? client.platform || facts.platform : facts.platform,
    token,
    uploadUrl: uploadUrl(base, token),
    billingUrl: billingUrl(base, secret, client.id),
    outcome: made.what,
    emailed: false,
  };

  if (!welcome) {
    // The page beat the webhook: give the buyer their seat now if it is quick, and let the webhook insist on it.
    if (made.what === "create" || made.what === "convert") await ensureSeat(db, client.id, result.email).catch(() => null);
    return result;
  }

  const prior = await db.from("client_emails").select("id")
    .eq("client_id", client.id).eq("kind", WELCOME_KIND).eq("ref_id", facts.id).maybeSingle();
  if (prior.error) return fail("database", prior.error.message, { clientId: client.id });
  if (prior.data) return result;

  let seatError;
  try { seatError = await ensureSeat(db, client.id, result.email); } catch (err) { seatError = String(err?.message || err); }
  if (seatError) return fail("seat", seatError, { clientId: client.id });

  if (!isInternal(result.email)) {
    const mail = welcomeEmail({
      platform: result.platform,
      uploadUrl: result.uploadUrl,
      cancelUrl: result.billingUrl,
      portalUrl: `${base}/portal`,
      alone: await hasNoOtherClient(db, client.id),
    });
    const sent = await sendResend({
      apiKey: env.RESEND_API_KEY,
      from: env.EMAIL_FROM || DEFAULT_FROM,
      to: result.email,
      replyTo: env.EMAIL_REPLY_TO || DEFAULT_REPLY_TO,
      ...mail,
      ...(fetchImpl ? { fetchImpl } : {}),
    });
    if (!sent.ok) return fail("email", sent.error, { clientId: client.id });
    result.emailed = true;
  }
  const noted = await db.from("client_emails")
    .insert({ client_id: client.id, kind: WELCOME_KIND, ref_id: facts.id, subject: WELCOME_SUBJECT });
  if (noted.error && !isDuplicate(noted.error)) return fail("database", noted.error.message, { clientId: client.id });
  return result;
}
