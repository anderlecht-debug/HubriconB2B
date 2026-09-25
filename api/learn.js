import { createHash } from "node:crypto";
import { SlidingWindow, clientIp } from "../lib/ratelimit.js";
import { renderHtml, renderText, sendResend } from "../lib/tool_email.js";

/**
 * The capture form on /learn/<course>: six fields in, the template by email, and
 * the route the answers imply back to the page.
 *
 *   POST /api/learn  {course, first_name, email, channel, rev, model, skus, website}
 *
 * The four questions are apply.html's GATE_QUESTIONS, same keys, same option
 * labels. The route is decided here from the answers, the way apply.html's fitTag
 * tags a booking, with one more door (docs/content/hubricon-learn-build-prompt.md §3):
 *
 *   core   $3M+ on an own brand: the template, then the Profit Teardown and the call
 *   below  under $3M, or wholesale / arbitrage: the template, then Capital Position
 *   none   mixed / other under $3M: the template and nothing offered
 *
 * No prospect row is written. A person who read a lesson asked for a spreadsheet,
 * not an upload page, and a wants_teardown prospect would be emailed one. The
 * address lands in funnel_events as `learn_capture` with the band, model and
 * catalog size in the payload, so the outbound engine segments without re-asking
 * and the recovered-amount follow-up (operator.learn_followups) finds it there a
 * week on.
 *
 * The template email goes through Resend when RESEND_API_KEY is set. Without a
 * key the capture still stands, the page unlocks on the response, and the download
 * button under the video slot is the delivery.
 *
 * Abuse controls mirror api/gate.js: a honeypot field, a per-instance sliding
 * window, a durable per-hashed-IP count over a day, and one row per address.
 */

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const KIND = "learn_capture";
const MAX_BODY_BYTES = 4 * 1024;
const DAILY_PER_IP = 5;
const SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";
const FROM = process.env.EMAIL_FROM || "Hagen Simmons <hagen.simmons@hubricon.com>";
const REPLY_TO = process.env.EMAIL_REPLY_TO || "hagen.simmons@hubricon.com";
// Capital Position has no page yet (docs/content/hubricon-capital-position-build-prompt.md).
// Until it ships, the `below` email delivers the template and offers nothing, so no
// email ever links to a page that does not exist. Set POSITION_URL when it does.
const POSITION_URL = process.env.POSITION_URL || null;

// apply.html's GATE_QUESTIONS: the keys and the option labels, so an answer is one
// of the chips the page renders and nothing else.
export const QUESTIONS = [
  { key: "channel", options: ["Amazon", "Shopify", "Both"] },
  { key: "rev", options: ["Under $3M", "$3M–$5M", "$5M–$20M", "$20M+"] },
  { key: "model", options: ["Private label", "Wholesale / reseller", "Arbitrage", "Mixed / other"] },
  { key: "skus", options: ["Under 10 SKUs", "10–50 SKUs", "50+ SKUs"] },
];

export const COURSES = {
  "reimbursement-playbook": {
    title: "The Reimbursement Playbook",
    template: "/learn/reimbursement-playbook-template.xlsx",
  },
};
const DEFAULT_COURSE = "reimbursement-playbook";

const writeWindow = new SlidingWindow({ limit: 6, windowMs: 10 * 60 * 1000 });

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extra },
  });
}

const tooMany = (retryAfterMs) =>
  json({ error: "Too many requests. Try again later." }, 429, { "Retry-After": String(Math.ceil(retryAfterMs / 1000)) });

// Same salt as api/quick.js and api/gate.js, so one connection hashes the same everywhere.
function ipHash(ip) {
  const salt = process.env.RATE_LIMIT_SALT || "hubricon-teardown";
  return createHash("sha256").update(`${salt}:${ip}`).digest("hex").slice(0, 32);
}

function missingEnv() {
  const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !process.env[k]);
  return missing.length ? json({ error: `missing ${missing.join(", ")}` }, 500) : null;
}

/** Where the answers send a reader. Anything short of four known answers offers nothing. */
export function routeFor(a = {}) {
  if (QUESTIONS.some((q) => !q.options.includes(a[q.key]))) return "none";
  if (a.model === "Mixed / other" && a.rev === "Under $3M") return "none";
  if (a.rev === "Under $3M") return "below";
  if (a.model === "Wholesale / reseller" || a.model === "Arbitrage") return "below";
  return "core";
}

/** The template email. No figure appears in it; the template and the lessons carry those. */
export function composeLearnEmail({ firstName, course = DEFAULT_COURSE, route, site = SITE, positionUrl = POSITION_URL, postalAddress = null }) {
  const slug = COURSES[course] ? course : DEFAULT_COURSE;
  const c = COURSES[slug];
  const blocks = [
    { p: `Here's the spreadsheet from ${c.title}. It's the file the lessons walk through: the reports go in, the claims come out, and the filing log keeps what Amazon owes you and what it has paid side by side.` },
    { button: "Download the template", url: `${site}${c.template}` },
    { p: "The rest of the lessons are open on the course page, in the order the reports are worth reading." },
    { button: "Open the course", url: `${site}/learn/${slug}` },
  ];
  if (route === "core") {
    blocks.push({ p: "The Playbook covers what Amazon owes you on lost and damaged inventory. A brand your size usually has more than that sitting in its fee lines, its ad spend and its reorders. The Profit Teardown reads your own exports and shows where, and it's back within a day. The call that follows it is yours to take or leave." });
    blocks.push({ button: "Get the Profit Teardown", url: `${site}/apply` });
  } else if (route === "below" && positionUrl) {
    blocks.push({ p: "Managed Profit is built for own brands above a revenue bar, so the page I'd point you to is Capital Position: what your cash can carry this week, and what it has to hold back." });
    blocks.push({ button: "Read Capital Position", url: positionUrl });
  }
  blocks.push({ small: `You asked for this on hubricon.com/learn${postalAddress ? `. Hubricon · ${postalAddress}` : ""}. An email follows in about a week to ask what came back, and nothing else unless you reply.` });
  const greeting = firstName ? `Hi ${String(firstName).trim().slice(0, 80)},` : "Hello,";
  const msg = { greeting, blocks };
  return { subject: `${c.title}: your template`, text: renderText(msg), html: renderHtml(msg) };
}

/**
 * funnel_events behind three calls, so api/learn.test.mjs can stand in for Supabase.
 * The client is imported here rather than at the top so the module, and the tests
 * that inject a store, load in a checkout with no node_modules; Vercel traces the
 * static specifier all the same.
 */
async function supabaseStore() {
  const { createClient } = await import("@supabase/supabase-js");
  const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });
  return {
    async dailyCount(hash, since) {
      const { count } = await db.from("funnel_events").select("id", { count: "exact", head: true })
        .eq("kind", KIND).eq("payload->>ip_hash", hash).gte("occurred_at", since);
      return count ?? 0;
    },
    async seen(email) {
      const { data } = await db.from("funnel_events").select("id").eq("kind", KIND).eq("payload->>email", email).limit(1);
      return Boolean(data?.length);
    },
    async record(row) {
      const { error } = await db.from("funnel_events").insert(row);
      return { error };
    },
  };
}

/**
 * The handler proper. `deps` exists for the tests: a store in place of Supabase, a
 * sliding window of their own, an API key and a fetch in place of Resend.
 */
export async function handle(request, deps = {}) {
  const ip = clientIp(request.headers);
  const gate = (deps.window || writeWindow).hit(ip);
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
  if (String(body.website || "").trim()) return json({ ok: true, route: "none", emailed: false });

  const course = COURSES[body.course] ? String(body.course) : DEFAULT_COURSE;
  const email = String(body.email || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 200) return json({ error: "a real email address, please" }, 400);
  const firstName = String(body.first_name ?? body.firstName ?? "").trim().slice(0, 80);
  const answers = {};
  for (const q of QUESTIONS) {
    const v = String(body[q.key] || "").trim();
    if (q.options.includes(v)) answers[q.key] = v;
  }
  if (QUESTIONS.some((q) => !answers[q.key])) return json({ error: "answer every question, please" }, 400);
  const route = routeFor(answers);

  let store = deps.store;
  if (!store) {
    const bad = missingEnv();
    if (bad) return bad;
    store = await supabaseStore();
  }
  const hash = ipHash(ip);
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const [byIp, seen] = await Promise.all([store.dailyCount(hash, since), store.seen(email)]);
  if (byIp >= DAILY_PER_IP) return tooMany(3600 * 1000);
  // One row per address. A second submit from the same person (a cleared browser,
  // another device) still learns its route so the page unlocks, and sends nothing.
  if (seen) return json({ ok: true, route, emailed: false, repeat: true });

  // The email they asked for. Without a key on this deployment the capture still
  // stands and the download button on the page is what delivers the template.
  let emailed = false, emailError = null;
  const apiKey = deps.apiKey ?? process.env.RESEND_API_KEY;
  if (apiKey) {
    const msg = composeLearnEmail({ firstName, course, route, postalAddress: process.env.POSTAL_ADDRESS || null });
    const sent = await sendResend({ apiKey, from: FROM, to: email, replyTo: REPLY_TO, fetchImpl: deps.fetchImpl, ...msg });
    emailed = sent.ok;
    emailError = sent.ok ? null : sent.error;
  }

  const { error } = await store.record({
    kind: KIND,
    prospect_id: null,
    note: [answers.channel, answers.rev, answers.model].filter(Boolean).join(" · ") || null,
    payload: {
      email, first_name: firstName || null, course, ...answers, route, emailed,
      ...(emailError ? { email_error: String(emailError).slice(0, 200) } : {}),
      ip_hash: hash, referer: (request.headers.get("referer") || "").slice(0, 300) || null,
    },
  });
  if (error) return json({ error: "could not save that" }, 500);
  return json({ ok: true, route, emailed });
}

export const POST = (request) => handle(request);
