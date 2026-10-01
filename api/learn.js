import { createHash } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { SlidingWindow, clientIp } from "../lib/ratelimit.js";
import { sendResend } from "../lib/tool_email.js";
import { composeLearnEmail, parseSignup, unsubscribePage, unsubscribeUrl, TOKEN } from "../lib/learn.js";

/**
 * /learn's two server-side jobs.
 *
 *   POST /api/learn  {email, course, website, source}
 *        One email registers you for a course (HUBRICON_SPEC.md, "Education hub").
 *        Keeps the address in `learners`, once per course, and sends the one email
 *        lib/learn.js composes: the link back and the spreadsheet. A repeat sign-up
 *        sends nothing. The page opens the course whatever happens here, unless
 *        the address itself is bad (400): a fault of ours never locks a reader out.
 *
 *   GET  /api/learn?unsubscribe=<token>   the link in the email: a page
 *   POST /api/learn?unsubscribe=<token>   the inbox's one-click (RFC 8058)
 *        Marks every row for that address unsubscribed. No more notes; the
 *        courses stay open.
 *
 * Abuse: a hidden `website` field (a bot that fills it gets a 200 and nothing is
 * kept), a per-instance sliding window, and a durable count of new sign-ups per
 * hashed connection address per day. The address itself is never stored.
 */

const SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";
const FROM = process.env.EMAIL_FROM || "Hagen Simmons <hagen.simmons@hubricon.com>";
const REPLY_TO = process.env.EMAIL_REPLY_TO || "hagen.simmons@hubricon.com";
const MAX_BODY_BYTES = 4 * 1024;
const DAILY_PER_IP = 10;
const burst = new SlidingWindow({ limit: 8, windowMs: 10 * 60 * 1000 });

const db = () => createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});
const html = (body, status = 200) => new Response(body, {
  status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
});
const ipHash = (ip) => createHash("sha256").update(`${process.env.RATE_LIMIT_SALT || "hubricon-learn"}:${ip}`).digest("hex").slice(0, 32);
const configured = () => Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);

async function unsubscribe(token) {
  if (!TOKEN.test(token || "") || !configured()) return false;
  const sb = db();
  const { data: row } = await sb.from("learners").select("email").eq("unsubscribe_token", token).maybeSingle();
  if (!row) return false;
  const { error } = await sb.from("learners").update({ unsubscribed_at: new Date().toISOString() }).eq("email", row.email).is("unsubscribed_at", null);
  return !error;
}

export async function GET(request) {
  const token = new URL(request.url).searchParams.get("unsubscribe");
  if (!token) return json({ error: "not found" }, 404);
  const ok = await unsubscribe(token);
  return html(unsubscribePage(ok), ok ? 200 : 404);
}

export async function POST(request) {
  const token = new URL(request.url).searchParams.get("unsubscribe");
  if (token) {
    const ok = await unsubscribe(token);
    return json({ ok }, ok ? 200 : 404);
  }

  const ip = clientIp(request.headers);
  const gate = burst.hit(ip);
  if (!gate.ok) return json({ error: "Too many requests. Try again in a few minutes." }, 429);
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return json({ error: "request too large" }, 413);
  let body;
  try { body = JSON.parse(raw); } catch { return json({ error: "bad json" }, 400); }

  const s = parseSignup(body);
  if (s.bot) return json({ ok: true });
  if (s.error) return json({ error: s.error }, 400);
  if (!configured()) return json({ error: "not configured" }, 503);

  const sb = db();
  const hash = ipHash(ip);
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const { count } = await sb.from("learners").select("id", { count: "exact", head: true }).eq("ip_hash", hash).gte("created_at", since);
  if ((count ?? 0) >= DAILY_PER_IP) return json({ error: "Too many sign-ups from this connection today." }, 429);

  // Once per address per course. A repeat is a visit, not a new reader.
  const { data: created, error } = await sb.from("learners")
    .upsert({ email: s.email, course: s.course, ip_hash: hash, source: s.source }, { onConflict: "email,course", ignoreDuplicates: true })
    .select("id, unsubscribe_token");
  if (error) return json({ error: "could not save" }, 500);
  const fresh = Array.isArray(created) && created.length === 1 ? created[0] : null;
  if (!fresh) {
    await sb.from("learners").update({ last_seen_at: new Date().toISOString() }).eq("email", s.email).eq("course", s.course);
    return json({ ok: true, new: false });
  }

  const msg = composeLearnEmail({ course: s.course, unsubscribeUrl: unsubscribeUrl(fresh.unsubscribe_token, SITE), postalAddress: process.env.POSTAL_ADDRESS || null, site: SITE });
  const sent = await sendResend({ apiKey: process.env.RESEND_API_KEY, from: FROM, to: s.email, replyTo: REPLY_TO, ...msg });
  if (sent.ok) await sb.from("learners").update({ email_sent_at: new Date().toISOString(), email_id: sent.id }).eq("id", fresh.id);
  await sb.from("funnel_events").insert({
    kind: "learn_registered",
    payload: { course: s.course, source: s.source, emailed: sent.ok, ...(sent.ok ? {} : { email_error: String(sent.error).slice(0, 200) }) },
  });
  return json({ ok: true, new: true, emailed: sent.ok });
}
