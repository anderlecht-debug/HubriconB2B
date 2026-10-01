#!/usr/bin/env node
/**
 * What /learn's optional email promises, kept. Nothing is sent without --send or --test.
 *
 *   node scripts/learn/note.mjs scripts/learn/notes/<id>.json                      who would get it, and its text
 *   node scripts/learn/note.mjs scripts/learn/notes/<id>.json --test you@example.com   one copy, to you
 *   node scripts/learn/note.mjs scripts/learn/notes/<id>.json --send               everyone it may go to, once
 *   node scripts/learn/note.mjs --backfill [--send]   the first email, to sign-ups it never reached
 *
 * Who: a "course" note goes to every address with no unsubscribed row; every form has promised
 * it. A "fee-cards" note goes only to addresses whose sign-up recorded lib/learn.js's PROMISE in
 * funnel_events (api/learn.js writes it beside the learner's id). One note per address, whatever
 * its courses. A note goes once: --send refuses an id already recorded (funnel_events "learn_note").
 *
 * Figures: a note types no number the course computes. "{fill:<course>:<key>}" in its text is
 * read from the built page's data-fill (learn/<course>.html); a missing key stops the run.
 * Reads SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, RESEND_API_KEY and POSTAL_ADDRESS from .env.
 */
import { existsSync, readFileSync } from "node:fs";
import { createClient } from "@supabase/supabase-js";
import { sendResend } from "../../lib/tool_email.js";
import { composeLearnEmail, composeLearnNote, unsubscribeUrl, NOTE_KINDS, PROMISE } from "../../lib/learn.js";

const root = new URL("../../", import.meta.url);
const ENV = new URL(".env", root);
let SITE, FROM, REPLY_TO;
const PAUSE_MS = 600; // Resend's default limit is two requests a second

const args = process.argv.slice(2);
const flag = (f) => args.includes(f);
const after = (f) => (args.includes(f) ? args[args.indexOf(f) + 1] : null);
const SEND = flag("--send");
const TEST = after("--test");
const mask = (e) => e.replace(/^(.).*(@.*)$/, "$1***$2");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const unescape = (s) => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");

/** "{fill:fee-staircase:learn_peak_min}" → the figure the built page prints. */
export function resolveFills(value, read = (p) => readFileSync(new URL(p, root), "utf8")) {
  const pages = new Map();
  const one = (s) => s.replace(/\{fill:([a-z-]+):([a-z0-9_]+)\}/g, (_, course, key) => {
    if (!pages.has(course)) pages.set(course, read(`learn/${course}.html`));
    const m = pages.get(course).match(new RegExp(`data-fill="${key}"[^>]*>([^<]*)<`));
    if (!m) throw new Error(`no figure ${key} on learn/${course}.html`);
    return unescape(m[1]);
  });
  const walk = (v) => (typeof v === "string" ? one(v) : Array.isArray(v) ? v.map(walk) : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x)])) : v);
  return walk(value);
}

function db() {
  if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_ROLE_KEY) throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are needed (.env)");
  return createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
}

async function learners(sb) {
  const { data, error } = await sb.from("learners").select("id, email, course, unsubscribe_token, unsubscribed_at, email_sent_at, created_at").order("created_at");
  if (error) throw new Error(`learners: ${error.message}`);
  const off = new Set(data.filter((r) => r.unsubscribed_at).map((r) => r.email));
  return { rows: data, live: data.filter((r) => !off.has(r.email)) };
}

/** The learner ids whose sign-up was told PROMISE. */
async function toldIds(sb) {
  const { data, error } = await sb.from("funnel_events").select("payload").eq("kind", "learn_registered").eq("payload->>promise", PROMISE);
  if (error) throw new Error(`funnel_events: ${error.message}`);
  return new Set(data.map((e) => e.payload?.learner).filter(Boolean));
}

async function send(to, msg) {
  return sendResend({ apiKey: process.env.RESEND_API_KEY, from: FROM, to, replyTo: REPLY_TO, ...msg });
}

async function note(path) {
  const n = resolveFills(JSON.parse(readFileSync(path, "utf8")));
  const postal = process.env.POSTAL_ADDRESS || null;
  const sample = composeLearnNote({ note: n, unsubscribeUrl: unsubscribeUrl("0".repeat(32), SITE), postalAddress: postal });
  if (TEST) {
    const r = await send(TEST, { ...sample, subject: `[test] ${sample.subject}` });
    console.log(r.ok ? `test copy sent to ${TEST} (${r.id})` : `test copy failed: ${r.error}`);
    return;
  }
  const sb = db();
  const { live } = await learners(sb);
  const told = NOTE_KINDS[n.kind] ? await toldIds(sb) : null;
  const byEmail = new Map();
  for (const r of live) if ((!told || told.has(r.id)) && !byEmail.has(r.email)) byEmail.set(r.email, r);
  const { data: sentBefore } = await sb.from("funnel_events").select("id").eq("kind", "learn_note").eq("payload->>note", n.id).limit(1);
  console.log(`${n.id} (${n.kind}): ${byEmail.size} address${byEmail.size === 1 ? "" : "es"} may get it${told ? `, of ${new Set(live.map((r) => r.email)).size} subscribed (the rest were not told fee-card notes would come)` : ""}.`);
  for (const r of [...byEmail.values()].slice(0, 10)) console.log(`  ${mask(r.email)}  ${r.course}  since ${r.created_at.slice(0, 10)}`);
  if (sentBefore?.length) { console.log("Already sent once. Nothing to do."); return; }
  if (!SEND) { console.log(`\n--- ${sample.subject}\n\n${sample.text}\n\nDry run. Add --test you@example.com for one copy, --send to send.`); return; }
  let sent = 0, failed = 0;
  for (const r of byEmail.values()) {
    const res = await send(r.email, composeLearnNote({ note: n, unsubscribeUrl: unsubscribeUrl(r.unsubscribe_token, SITE), postalAddress: postal }));
    if (res.ok) sent++; else { failed++; console.log(`  failed ${mask(r.email)}: ${res.error}`); }
    await sleep(PAUSE_MS);
  }
  await sb.from("funnel_events").insert({ kind: "learn_note", payload: { note: n.id, kind: n.kind, sent, failed } });
  console.log(`Sent ${sent}, failed ${failed}.`);
}

async function backfill() {
  const sb = db();
  const { live } = await learners(sb);
  const told = await toldIds(sb);
  const owed = live.filter((r) => !r.email_sent_at);
  console.log(`${owed.length} sign-up${owed.length === 1 ? "" : "s"} never got the first email.`);
  for (const r of owed.slice(0, 10)) console.log(`  ${mask(r.email)}  ${r.course}  since ${r.created_at.slice(0, 10)}${told.has(r.id) ? "" : "  (told: course notes only)"}`);
  if (!SEND || !owed.length) { if (owed.length) console.log("Dry run. Add --send to send them."); return; }
  for (const r of owed) {
    const msg = composeLearnEmail({ course: r.course, unsubscribeUrl: unsubscribeUrl(r.unsubscribe_token, SITE), postalAddress: process.env.POSTAL_ADDRESS || null, site: SITE, told: told.has(r.id) ? PROMISE : "courses" });
    const res = await send(r.email, msg);
    if (res.ok) await sb.from("learners").update({ email_sent_at: new Date().toISOString(), email_id: res.id }).eq("id", r.id);
    else console.log(`  failed ${mask(r.email)}: ${res.error}`);
    await sleep(PAUSE_MS);
  }
  console.log("Done.");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (existsSync(ENV)) process.loadEnvFile(ENV.pathname);
  SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";
  FROM = process.env.EMAIL_FROM || "Hagen Simmons <hagen.simmons@hubricon.com>";
  REPLY_TO = process.env.EMAIL_REPLY_TO || "hagen.simmons@hubricon.com";
  const path = args.find((a) => a.endsWith(".json"));
  (flag("--backfill") ? backfill() : path ? note(path) : Promise.reject(new Error("usage: note.mjs <note.json> [--test you@example.com | --send] · note.mjs --backfill [--send]")))
    .catch((e) => { console.error(e.message); process.exit(1); });
}
