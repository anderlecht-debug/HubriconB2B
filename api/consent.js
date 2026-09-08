import { createHash, randomBytes } from "node:crypto";
import { createClient } from "@supabase/supabase-js";

/**
 * The page where a client answers the price of the free month.
 *
 *   GET  /say/<token>   -> the form: three consents, two lines, their referral link
 *   POST /say/<token>   -> records the answers, shows the link again
 *
 * terms.html §9 prices the free month in a testimonial and anonymised results.
 * The engine asks for them once, in the Issue email that follows the first
 * measured or recovered dollars (engine/src/hubricon_engine/referral.py), and
 * this is the only place the answer is written. The token is minted by the
 * same private-link machinery as the upload page and validated the same way.
 *
 * No consent is inferred. An unticked box is "no", written as false, and a
 * client can come back and change either answer while the link lives.
 */

const SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";
const KINDS = ["testimonial", "anonymised_results", "named_results", "calibration"];

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

async function resolveToken(db, token) {
  if (typeof token !== "string" || token.length < 20 || token.length > 200) return null;
  const hash = createHash("sha256").update(token).digest("hex");
  const { data, error } = await db.rpc("validate_intake_token", { p_token_hash: hash });
  if (error || !data || data.length === 0) return null;
  return data[0]; // { client_id, company_name }
}

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

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

function page(title, body) {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<meta name="robots" content="noindex,nofollow"><title>${esc(title)}</title>` +
      `<style>
:root{--bg:hsl(222 28% 96%);--ink:hsl(228 44% 11%);--soft:hsl(228 26% 26%);--faint:hsl(228 16% 42%);
--amber:hsl(40 96% 33%);--hair:hsl(228 30% 20% / .14)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--soft);font:15.5px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:34px 20px 90px}
.wrap{max-width:640px;margin:0 auto}
h1{font:500 clamp(24px,4.4vw,32px)/1.15 "Iowan Old Style",Georgia,serif;color:var(--ink);margin:6px 0 10px}
h2{font:500 19px/1.2 "Iowan Old Style",Georgia,serif;color:var(--ink);margin:0 0 8px}
.label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;color:var(--faint)}
.panel{background:#fff;border:1px solid var(--hair);border-radius:14px;padding:26px 30px;margin:18px 0}
.sub{color:var(--faint);font-size:14px}
label.row{display:grid;grid-template-columns:24px 1fr;gap:12px;align-items:start;padding:12px 0;border-top:1px solid var(--hair)}
label.row:first-of-type{border-top:0}
label.row b{color:var(--ink);display:block}
input[type=checkbox]{width:18px;height:18px;margin-top:4px}
textarea{width:100%;min-height:96px;border:1px solid var(--hair);border-radius:10px;padding:12px;font:inherit;margin-top:8px}
.btn{display:inline-block;margin-top:18px;background:var(--amber);color:#1a1205;font-weight:650;padding:13px 24px;border-radius:9px;text-decoration:none;font-size:15px;border:0;cursor:pointer}
.link{font-family:ui-monospace,Menlo,monospace;font-size:14px;background:hsl(222 26% 94%);padding:10px 12px;border-radius:8px;word-break:break-all;display:block;margin-top:8px}
footer{margin-top:28px;font-size:12.5px;color:var(--faint)}
@media (max-width:560px){.panel{padding:20px 18px}body{padding:22px 14px 70px}}
</style></head><body><div class="wrap">${body}</div></body></html>`,
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }
  );
}

function form(identity, existing, code, token) {
  const has = (k) => existing.find((r) => r.kind === k);
  const on = (k) => (has(k)?.granted ? "checked" : "");
  const testimonial = has("testimonial")?.testimonial || "";
  const named = has("testimonial")?.testimonial_named_ok ? "checked" : "";
  return page(
    `The price of the free month — ${identity.company_name || "Hubricon"}`,
    `<span class="label">Hubricon · ${esc(identity.company_name || "your desk")}</span>
<h1>The whole price of your free month, in a minute.</h1>
<p class="sub">We said we would ask for two things if the ledger earned it. Each box is a separate
yes; an unticked box is a no, and either is fine. You can come back and change any of them
while this link lives.</p>
<form method="post" action="/api/consent?t=${esc(token)}">
<div class="panel">
  <h2>What we may publish</h2>
  <label class="row"><input type="checkbox" name="anonymised_results" ${on("anonymised_results")}>
    <span><b>Publish my results, anonymised.</b> No company name, storefront, brand, ASIN or SKU.
    Figures rounded and shown by category and revenue band, on the public results page.</span></label>
  <label class="row"><input type="checkbox" name="named_results" ${on("named_results")}>
    <span><b>You may name my brand beside those results.</b> Optional, and off unless you tick it.</span></label>
  <label class="row"><input type="checkbox" name="calibration" ${on("calibration")}>
    <span><b>Use aggregate statistics from my account to calibrate your public estimates.</b>
    A slope, a rate, a ratio — never a figure of mine, never to advise another client on my
    business, and every estimate that uses it says how many accounts stand behind it.</span></label>
</div>
<div class="panel">
  <h2>A short testimonial</h2>
  <label class="row"><input type="checkbox" name="testimonial" ${on("testimonial")}>
    <span><b>Yes, you may quote me.</b> Two honest lines are plenty. Attributed by first name and
    category unless you tick the box below.</span></label>
  <textarea name="testimonial_text" placeholder="What changed, in your words.">${esc(testimonial)}</textarea>
  <label class="row"><input type="checkbox" name="testimonial_named_ok" ${named}>
    <span><b>You may attribute it to my name and brand.</b></span></label>
</div>
<button class="btn" type="submit">Save my answers</button>
</form>
<div class="panel">
  <h2>Your link</h2>
  <p>If another founder should see their own numbers the way you have, send them this. Their first
  month is free exactly as yours was, and if they stay past their day thirty, your next month is
  on us.</p>
  <span class="link">${esc(SITE)}/?ref=${esc(code)}</span>
</div>
<footer>This page is private to ${esc(identity.company_name || "your workspace")}. The link is
not shared, not indexed, and expires with your upload links. Reply to any Hubricon email to
reach the founder.</footer>`
  );
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
  return form(identity, existing ?? [], code, token);
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
  const rows = KINDS.map((kind) => ({
    client_id: identity.client_id,
    kind,
    granted: yes(kind),
    answered_at: now,
    ...(kind === "testimonial"
      ? { testimonial: text || null, testimonial_named_ok: yes("testimonial_named_ok") }
      : {}),
  }));
  const { error } = await db.from("consents").upsert(rows, { onConflict: "client_id,kind" });
  if (error) return new Response("Could not save your answers", { status: 500 });

  const events = [{ kind: "consent_answered", client_id: identity.client_id, payload: { granted: rows.filter((r) => r.granted).map((r) => r.kind) } }];
  if (rows.some((r) => r.granted)) events.push({ kind: "consent_granted", client_id: identity.client_id, payload: {} });
  if (yes("testimonial") && text) events.push({ kind: "testimonial_given", client_id: identity.client_id, payload: { chars: text.length } });
  await db.from("funnel_events").insert(events);

  const code = await referralCode(db, identity.client_id);
  await db.from("funnel_events").insert({ kind: "referral_link_issued", client_id: identity.client_id, payload: { code } });
  const { data: existing } = await db.from("consents").select("*").eq("client_id", identity.client_id);
  return page(
    "Saved — thank you",
    `<span class="label">Hubricon · ${esc(identity.company_name || "your desk")}</span>
<h1>Saved. Thank you.</h1>
<p class="sub">Your answers are recorded exactly as ticked. Anything you allowed appears on the public
results page on the next hourly pass; anything you did not stays private. Change your mind any
time at the same link.</p>
<div class="panel">
  <h2>Your link</h2>
  <p>Send it to a founder who should see their own numbers. Their first month is free exactly as
  yours was, and if they stay past their day thirty, your next month is on us.</p>
  <span class="link">${esc(SITE)}/?ref=${esc(code)}</span>
</div>
<p><a href="/api/consent?t=${esc(url.searchParams.get("t"))}">Back to your answers</a> ·
<a href="${esc(SITE)}/portal">Open your desk</a></p>
<footer>${(existing ?? []).filter((r) => r.granted).length} of ${KINDS.length} permissions granted.</footer>`
  );
}
