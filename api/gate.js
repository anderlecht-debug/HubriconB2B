import { createHash } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { SlidingWindow, clientIp } from "../lib/ratelimit.js";

/**
 * The two doors on the application's below-the-bar screen.
 *
 * The gate on index.html renders the calendar only for a brand doing $3M or
 * more on its own label: below that the Profit Record cannot cover $6,000 a
 * month, so every invoice would void. Those founders get the 60-second
 * Teardown and these:
 *
 *   POST /api/gate  {intent: "recovery", email, channel, rev, model, skus, website}
 *     Recovery Only, for Amazon sellers (terms §4): no retainer, a share of what
 *     Amazon actually pays on claims we file. The prospect is written at
 *     wants_teardown with a recovery note, so the hourly operator provisions
 *     them and sends `recovery_welcome` (the upload page and the plan) instead
 *     of the full-Teardown `files` email. The plan itself is still switched by
 *     `hubricon downsell`: a plan is a contract, and a person confirms it.
 *
 *   POST /api/gate  {intent: "position", email, ...}
 *     An address for Capital Position's weekly page. Nothing is sent and no
 *     prospect is created: a wants_teardown prospect is emailed an upload page
 *     for the full Teardown, which is not what this founder asked for. The
 *     address lands in funnel_events as `position_list` for the Capital
 *     Position build to import.
 *
 * Abuse controls mirror api/quick.js: a honeypot field, a per-instance sliding
 * window, a durable per-hashed-IP count over a day, and one row per address
 * per door.
 */

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const INTERNAL = /@(hubricon\.com|gethubricon\.com|tryhubricon\.com)$/i;
const ANSWER = /^[\w $+–\-/]{1,40}$/;       // the gate's own chip labels, nothing longer
const KINDS = { recovery: "recovery_requested", position: "position_list" };
// operator.teardown_requests keys on this prefix to send recovery_welcome.
const RECOVERY_NOTE = "recovery-only (site gate)";
const MAX_BODY_BYTES = 4 * 1024;
const DAILY_PER_IP = 5;

const writeWindow = new SlidingWindow({ limit: 6, windowMs: 10 * 60 * 1000 });

function getDb() {
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });
}

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra },
  });
}

const tooMany = (retryAfterMs) =>
  json({ error: "Too many requests. Try again later." }, 429, { "Retry-After": String(Math.ceil(retryAfterMs / 1000)) });

// Same salt as api/quick.js, so one connection hashes the same in both tables.
function ipHash(ip) {
  const salt = process.env.RATE_LIMIT_SALT || "hubricon-teardown";
  return createHash("sha256").update(`${salt}:${ip}`).digest("hex").slice(0, 32);
}

function missingEnv() {
  const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !process.env[k]);
  return missing.length ? json({ error: `missing ${missing.join(", ")}` }, 500) : null;
}

/** The prospect a Recovery Only request becomes. Never moves a prospect backwards. */
async function recoveryProspect(db, email, answers) {
  const note = `${RECOVERY_NOTE} · channel:${answers.channel} · rev:${answers.rev || "?"} · model:${answers.model || "?"}`;
  const now = new Date().toISOString();
  const { data: prior } = await db.from("prospects").select("id, status").eq("email", email).maybeSingle();
  if (prior) {
    const patch = { fit_notes: note, last_event_at: now };
    if (!["client", "booked", "wants_teardown", "unsubscribed"].includes(prior.status)) patch.status = "wants_teardown";
    await db.from("prospects").update(patch).eq("id", prior.id);
    return prior.id;
  }
  const { data: created } = await db
    .from("prospects")
    .insert({ email, source: "inbound", status: "wants_teardown", fit_notes: note, last_event_at: now })
    .select("id")
    .single();
  return created?.id ?? null;
}

export async function POST(request) {
  const bad = missingEnv();
  if (bad) return bad;
  const ip = clientIp(request.headers);
  const gate = writeWindow.hit(ip);
  if (!gate.ok) return tooMany(gate.retryAfterMs);

  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return json({ error: "request too large" }, 413);
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  if (!body || typeof body !== "object") return json({ error: "bad json" }, 400);
  // The honeypot: a human never sees the field, so a value means a script.
  if (String(body.website || "").trim()) return json({ ok: true });

  const intent = body.intent === "recovery" ? "recovery" : "position";
  const email = String(body.email || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 200) return json({ error: "a real email address, please" }, 400);
  const answers = {};
  for (const key of ["channel", "rev", "model", "skus"]) {
    const v = String(body[key] || "").trim();
    if (ANSWER.test(v)) answers[key] = v;
  }
  // Amazon reimburses lost FBA inventory. A Shopify store has no warehouse
  // losing units on its behalf, so there is nothing for Recovery Only to file.
  if (intent === "recovery" && !["Amazon", "Both"].includes(answers.channel)) {
    return json({ error: "Recovery Only files Amazon reimbursements, so it needs an Amazon account" }, 400);
  }

  const db = getDb();
  const hash = ipHash(ip);
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const [{ count: byIp }, { data: existing }] = await Promise.all([
    db.from("funnel_events").select("id", { count: "exact", head: true })
      .in("kind", Object.values(KINDS)).eq("payload->>ip_hash", hash).gte("occurred_at", since),
    db.from("funnel_events").select("id").eq("kind", KINDS[intent]).eq("payload->>email", email).limit(1),
  ]);
  if ((byIp ?? 0) >= DAILY_PER_IP) return tooMany(3600 * 1000);
  if (existing?.length) return json({ ok: true });

  const prospectId = intent === "recovery" && !INTERNAL.test(email) ? await recoveryProspect(db, email, answers) : null;
  const { error } = await db.from("funnel_events").insert({
    kind: KINDS[intent],
    prospect_id: prospectId,
    note: [answers.channel, answers.rev, answers.model].filter(Boolean).join(" · ") || null,
    payload: { email, ...answers, ip_hash: hash, referer: (request.headers.get("referer") || "").slice(0, 300) || null },
  });
  if (error) return json({ error: "could not save that" }, 500);
  return json({ ok: true });
}
