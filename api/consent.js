import { randomBytes } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { KINDS, form, saved } from "../lib/consent_page.js";
import { resolveTokenFor } from "../lib/token.js";

/**
 * The page where a client answers the price of the free month.
 *
 *   GET  /say/<token>   -> the form: three consents, two lines, their referral link
 *   POST /say/<token>   -> records the answers, shows the link again
 *
 * terms.html §9 prices the free month in a testimonial and anonymised results.
 * The engine asks for them once, in the Profit Brief email that follows the first
 * measured or recovered dollars (engine/src/hubricon_engine/referral.py), and
 * this is the only place the answer is written. The token is minted by the
 * same private-link machinery as the upload page and validated the same way
 * (so, until tokens carry a purpose, an upload link also opens this page).
 *
 * No consent is inferred. An unticked box is "no", written as false, and a
 * client can come back and change any answer while the link lives, or at any
 * time by replying to an email, which the founder records by hand. The page
 * says both, because the link expires and the right to change one's mind does
 * not. The page's words and look live in lib/consent_page.js.
 *
 * `network` (terms.html §10, the third exception) lets aggregates from the
 * client's account warn other clients of a fee change on the platform's side
 * and count toward the book of what each kind of move delivers. The engine's
 * network pass (engine/src/hubricon_engine/fleet.py) reads nobody without it,
 * and an unticked box withdraws it on the next weekly pass.
 */

const SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";

function getDb() {
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });
}

function missingEnv() {
  const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((name) => !process.env[name]);
  return missing.length > 0
    ? new Response(`Server not configured: missing ${missing.join(", ")}`, { status: 500 })
    : null;
}

// One link, one job: this page opens only consent links (lib/token.js).
async function resolveToken(db, token) {
  return resolveTokenFor(db, token, "consent");
}

function newCode() {
  return randomBytes(6).toString("base64url").replace(/-/g, "x").replace(/_/g, "y").slice(0, 8);
}

async function referralCode(db, clientId) {
  const { data: c } = await db.from("clients").select("referral_code").eq("id", clientId).single();
  if (c?.referral_code) return c.referral_code;
  const code = newCode();
  await db.from("clients").update({ referral_code: code }).eq("id", clientId);
  return code;
}

export async function GET(request) {
  const notConfigured = missingEnv();
  if (notConfigured) return notConfigured;
  const token = new URL(request.url).searchParams.get("t");
  const db = getDb();
  const identity = await resolveToken(db, token);
  if (!identity) return new Response("Not found", { status: 404 });
  const { data: existing } = await db.from("consents").select("*").eq("client_id", identity.client_id);
  const code = await referralCode(db, identity.client_id);
  return form({ identity, existing: existing ?? [], code, token, site: SITE });
}

export async function POST(request) {
  const notConfigured = missingEnv();
  if (notConfigured) return notConfigured;
  const url = new URL(request.url);
  const db = getDb();
  const identity = await resolveToken(db, url.searchParams.get("t"));
  if (!identity) return new Response("Not found", { status: 404 });

  let body;
  try {
    body = await request.formData();
  } catch {
    return new Response("Bad request", { status: 400 });
  }
  const yes = (k) => body.get(k) === "on" || body.get(k) === "true";
  const now = new Date().toISOString();
  const text = String(body.get("testimonial_text") ?? "").trim().slice(0, 1200);
  const before = String(body.get("before_text") ?? "").trim().slice(0, 800);
  const rows = KINDS.map((kind) => ({
    client_id: identity.client_id,
    kind,
    granted: yes(kind),
    answered_at: now,
    ...(kind === "testimonial"
      ? { testimonial: text || null, testimonial_named_ok: yes("testimonial_named_ok"), before_text: before || null }
      : {}),
  }));
  // `network` is written on its own. Until its migration
  // (supabase/migrations/20260925000003_network.sql) is applied the consents
  // check constraint refuses the kind, and one refused row must not take the
  // testimonial and every other answer down with it. The page says when it
  // happens; nothing is silently dropped.
  const core = rows.filter((r) => r.kind !== "network");
  const { error } = await db.from("consents").upsert(core, { onConflict: "client_id,kind" });
  if (error) return new Response("Could not save your answers", { status: 500 });
  const { error: networkError } = await db
    .from("consents")
    .upsert(rows.filter((r) => r.kind === "network"), { onConflict: "client_id,kind" });
  const written = networkError ? core : rows;
  const networkNote = !networkError
    ? ""
    : yes("network")
      ? `<p class="sub"><b>One answer is not saved yet:</b> your yes to warning other
brands. Nothing of yours is used for it until it is. Everything else is saved.</p>`
      : `<p class="sub"><b>One answer could not be saved:</b> warning other brands.
Everything else is saved. Please save again, or reply to any Hubricon email and it will be recorded by hand.</p>`;

  const events = [{ kind: "consent_answered", client_id: identity.client_id, payload: { granted: written.filter((r) => r.granted).map((r) => r.kind) } }];
  if (written.some((r) => r.granted)) events.push({ kind: "consent_granted", client_id: identity.client_id, payload: {} });
  if (yes("testimonial") && text) events.push({ kind: "testimonial_given", client_id: identity.client_id, payload: { chars: text.length } });
  await db.from("funnel_events").insert(events);

  const code = await referralCode(db, identity.client_id);
  await db.from("funnel_events").insert({ kind: "referral_link_issued", client_id: identity.client_id, payload: { code } });
  const { data: existing } = await db.from("consents").select("*").eq("client_id", identity.client_id);
  return saved({
    identity, code, token: url.searchParams.get("t"), site: SITE, networkNote,
    granted: (existing ?? []).filter((r) => r.granted).length,
  });
}
