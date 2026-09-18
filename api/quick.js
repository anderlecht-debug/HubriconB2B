import { createHash } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import * as fees from "../lib/fees.js";
import { SlidingWindow, clientIp } from "../lib/ratelimit.js";
import { composeToolEmail, sendResend } from "../lib/tool_email.js";

/**
 * The 60-second Teardown's three server-side jobs. Everything else — the fee
 * stack, the cliff, the break-even, the ten thousand months — runs in the
 * visitor's browser off /ratecard.json and lib/fees.js, so a page view costs
 * nothing and no listing is ever fetched from a datacenter (Amazon soft-blocks
 * those; the harvest reads pages from the founder's Mac).
 *
 *   GET  /api/quick?asin=B0…                 prefill from harvest_products,
 *                                            public numbers the crawl already read
 *   GET  /api/quick?product=<url>             a Shopify product: first from the
 *                                            crawl's rows, then the store's own
 *                                            public JSON with a short timeout —
 *                                            a convenience that falls back to
 *                                            typing, never a requirement
 *   GET  /api/quick?bench=<category>&oz=&dims= the category benchmark: how far
 *                                            every listing we have weighed sits
 *                                            above its band edge, yours marked.
 *                                            Aggregates only; no row leaves.
 *   POST /api/quick  {email, first_name, asin, inputs, summary, website}
 *                                            keep the run, email the visitor
 *                                            their result (Resend), create the
 *                                            prospect at `wants_teardown`. The
 *                                            hourly operator provisions that
 *                                            prospect and emails the private
 *                                            upload page — the full Teardown
 *                                            path, already built.
 *
 * What keeps the POST honest and hard to abuse:
 *   - the email is composed from a server-side recomputation of the numeric
 *     inputs (lib/fees.js analyse), never from text the client sent, and the
 *     link in it is rebuilt from those inputs on this site's own origin;
 *   - a hidden `website` field: a bot that fills it gets a 200 and nothing saved;
 *   - two rate limits — a per-instance sliding window, and a durable count in
 *     tool_runs per hashed IP and per address over the last day;
 *   - the IP is stored as a salted hash, never raw.
 */

const ASIN = /^[A-Z0-9]{10}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const INTERNAL = /@(hubricon\.com|gethubricon\.com|tryhubricon\.com)$/i;
const SITE = process.env.INTAKE_BASE_URL || "https://www.hubricon.com";
const APPLY_URL = `${SITE}/apply`;
const FROM = process.env.EMAIL_FROM || "Hagen Simmons <hagen.simmons@hubricon.com>";
const REPLY_TO = process.env.EMAIL_REPLY_TO || "hagen.simmons@hubricon.com";
const MAX_BODY_BYTES = 16 * 1024;
const DAILY_PER_IP = 5;
const DAILY_PER_EMAIL = 3;

// Per instance. Reads are cheap and bounded; the capture is dearer, so it is tighter.
const readWindow = new SlidingWindow({ limit: 60, windowMs: 10 * 60 * 1000 });
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

const tooMany = (retryAfterMs, what) =>
  json({ error: `Too many ${what}. Try again in a few minutes.` }, 429, { "Retry-After": String(Math.ceil(retryAfterMs / 1000)) });

function ipHash(ip) {
  const salt = process.env.RATE_LIMIT_SALT || "hubricon-teardown";
  return createHash("sha256").update(`${salt}:${ip}`).digest("hex").slice(0, 32);
}

function missingEnv() {
  const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !process.env[k]);
  return missing.length ? json({ error: `missing ${missing.join(", ")}` }, 500) : null;
}

let cachedCard = null;
async function ratecard(request) {
  if (cachedCard) return cachedCard;
  const res = await fetch(new URL("/ratecard.json", request.url));
  if (!res.ok) throw new Error(`ratecard.json ${res.status}`);
  cachedCard = await res.json();
  return cachedCard;
}

async function prefill(db, asin) {
  const { data } = await db
    .from("harvest_products")
    .select("asin, title, brand, category, bsr, price, weight_oz, dims, reviews, seen_at")
    .eq("asin", asin)
    .maybeSingle();
  if (!data) return json({ found: false }, 404);
  return json({ found: true, ...data });
}

// -- a Shopify product, from the crawl or from the store itself ----------------------

const HOSTNAME = /^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$/i;
const NOT_A_STORE = /(^|\.)(localhost|local|internal|corp|home|lan|test|example|invalid)$/i;
const LIVE_TIMEOUT_MS = 4000;
const LIVE_MAX_BYTES = 2 * 1024 * 1024;
const BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";

/** A store host we are willing to fetch from: a public DNS name, never an address, never a private suffix. */
function storeHost(hostname) {
  const h = String(hostname || "").toLowerCase().replace(/\.$/, "");
  if (!HOSTNAME.test(h) || NOT_A_STORE.test(h) || /^\d+\.\d+\.\d+\.\d+$/.test(h) || h.includes(":")) return null;
  return h;
}

function parseProductUrl(raw) {
  let u;
  try { u = new URL(String(raw).trim()); } catch { return null; }
  if (!/^https?:$/.test(u.protocol)) return null;
  const host = storeHost(u.hostname);
  const m = u.pathname.match(/\/products\/([a-z0-9][a-z0-9._-]{0,254})/i);
  if (!host || !m) return null;
  return { host, handle: m[1].toLowerCase(), ref: `${host.replace(/^www\./, "")}/products/${m[1].toLowerCase()}` };
}

/** GET a store's public JSON with a browser identity and a hard timeout; null on any refusal. */
async function liveJson(host, path) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), LIVE_TIMEOUT_MS);
  try {
    const res = await fetch(`https://${host}${path}`, { headers: { "user-agent": BROWSER_UA, accept: "application/json" }, redirect: "follow", signal: ctl.signal });
    if (!res.ok) return null;
    if (!storeHost(new URL(res.url).hostname)) return null;            // a redirect somewhere we would not have fetched
    const len = Number(res.headers.get("content-length") || 0);
    if (len > LIVE_MAX_BYTES) return null;
    const text = await res.text();
    if (text.length > LIVE_MAX_BYTES) return null;
    return JSON.parse(text);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

const cheapest = (variants) => (variants || []).map((v) => ({ v, p: Number(v?.price) })).filter((x) => x.p > 0).sort((a, b) => a.p - b.p)[0]?.v || null;
const gramsToOz = (g) => { const n = Number(g); return n > 0 ? Math.round((n / 28.3495) * 1000) / 1000 : null; };

async function product(db, url) {
  const parsed = parseProductUrl(url.searchParams.get("product"));
  if (!parsed) return json({ found: false, reason: "Paste the product's own URL — it ends in /products/<handle>." }, 400);
  const { host, handle, ref } = parsed;
  const out = { found: false, source: null, ref };
  // 1. the crawl, if it has read this product
  const { data: row } = await db.from("harvest_products").select("asin, title, brand, price, weight_oz, seen_at").eq("asin", ref).maybeSingle();
  if (row) Object.assign(out, { found: true, source: "crawl", title: row.title, vendor: row.brand, price: Number(row.price) || null, weight_oz: Number(row.weight_oz) || null, seen_at: row.seen_at });
  // 2. the store itself, briefly: the product for its numbers, the catalogue for the anchor share
  const [prod, cat] = await Promise.all([liveJson(host, `/products/${handle}.json`), liveJson(host, "/products.json?limit=250")]);
  const p = prod && prod.product && typeof prod.product === "object" ? prod.product : null;
  if (p) {
    const v = cheapest(p.variants);
    Object.assign(out, {
      found: true, source: "live", title: String(p.title || "").slice(0, 200) || out.title || null,
      vendor: String(p.vendor || "").slice(0, 120) || out.vendor || null,
      price: v ? Number(v.price) : out.price || null,
      compare_at_price: v && Number(v.compare_at_price) > 0 ? Number(v.compare_at_price) : null,
      weight_oz: v ? gramsToOz(v.grams) ?? out.weight_oz ?? null : out.weight_oz || null,
    });
  }
  const list = cat && Array.isArray(cat.products) ? cat.products : null;
  if (list && list.length) {
    const priced = list.map((x) => cheapest(x?.variants)).filter((v) => v && Number(v.price) > 0);
    const marked = priced.filter((v) => Number(v.compare_at_price) > Number(v.price));
    if (priced.length) Object.assign(out, { catalogue_size: list.length, catalogue_discount_share: Math.round((marked.length / priced.length) * 1000) / 1000 });
  }
  if (!out.found) return json({ ...out, reason: "The store did not answer from here, and our crawl has not read it. Type the numbers from the variant in your admin; the result is the same." }, 404);
  return json(out);
}

async function bench(db, request, url) {
  const category = (url.searchParams.get("bench") || "").trim().slice(0, 80);
  const oz = Number(url.searchParams.get("oz")) || null;
  const dims = (url.searchParams.get("dims") || "").slice(0, 60) || null;
  if (!category) return json({ error: "category required" }, 400);
  const rc = await ratecard(request);
  if (category.toLowerCase() === "shopify") {
    const { data } = await db.from("harvest_products").select("seller_id, weight_oz, platform").eq("platform", "shopify").not("weight_oz", "is", null).limit(3000);
    const b = fees.benchmarkShopify(rc, data || [], oz);
    return json(b || { measured: (data || []).length, reason: "fewer than 30 weighed Shopify products over a pound" });
  }
  const card = fees.cardFor(rc);
  if (!card) return json({ measured: 0, reason: fees.stale(rc) });
  const { data } = await db
    .from("harvest_products")
    .select("category, weight_oz, dims, platform")
    .ilike("category", category)
    .not("weight_oz", "is", null)
    .limit(3000);
  const b = fees.benchmark(rc, card, data || [], category, oz, dims);
  if (!b) return json({ measured: (data || []).length, reason: "fewer than 30 measured listings in this category" });
  return json(b);
}

export async function GET(request) {
  const bad = missingEnv();
  if (bad) return bad;
  const gate = readWindow.hit(clientIp(request.headers));
  if (!gate.ok) return tooMany(gate.retryAfterMs, "lookups");
  const url = new URL(request.url);
  const db = getDb();
  const asin = (url.searchParams.get("asin") || "").trim().toUpperCase();
  if (asin) return ASIN.test(asin) ? prefill(db, asin) : json({ error: "not an ASIN" }, 400);
  if (url.searchParams.get("product")) return product(db, url);
  if (url.searchParams.get("bench")) return bench(db, request, url);
  return json({ error: "asin or bench required" }, 400);
}

/** The numeric inputs, and nothing else, as the page sends them. */
function cleanInputs(raw) {
  const i = raw && typeof raw === "object" ? raw : {};
  const n = (v, lo, hi) => { const x = Number(v); return Number.isFinite(x) && x >= lo && x <= hi ? x : null; };
  const dims = Array.isArray(i.dims) && i.dims.length === 3 ? i.dims.map((v) => n(v, 0.05, 200)) : null;
  return {
    asin: ASIN.test(String(i.asin || "").toUpperCase()) ? String(i.asin).toUpperCase() : null,
    price: n(i.price, 0.5, 100000),
    itemWeightOz: n(i.itemWeightOz, 0.05, 5000),
    dims: dims && dims.every((v) => v != null) ? dims : null,
    category: String(i.category || "").trim().toLowerCase().slice(0, 60) || null,
    bsr: n(i.bsr, 1, 50000000),
    cogs: n(i.cogs, 0, 100000),
  };
}

function cleanShopifyInputs(raw) {
  const i = raw && typeof raw === "object" ? raw : {};
  const n = (v, lo, hi) => { const x = Number(v); return Number.isFinite(x) && x >= lo && x <= hi ? x : null; };
  const handle = parseProductUrl(i.handle || "")?.ref || null;
  return {
    handle, price: n(i.price, 0.5, 100000), compareAtPrice: n(i.compareAtPrice, 0, 100000),
    weightOz: n(i.weightOz, 0.05, 5000), units: Math.max(1, Math.round(n(i.units, 1, 1000) || 1)),
    shipCharge: n(i.shipCharge, 0, 1000) || 0, plan: String(i.plan || "basic").toLowerCase().slice(0, 12),
    thirdParty: Boolean(i.thirdParty), orders: n(i.orders, 1, 10000000), cogs: n(i.cogs, 0, 100000),
    catalogueShare: n(i.catalogueShare, 0, 1),
  };
}

export async function POST(request) {
  const bad = missingEnv();
  if (bad) return bad;
  const ip = clientIp(request.headers);
  const gate = writeWindow.hit(ip);
  if (!gate.ok) return tooMany(gate.retryAfterMs, "requests");

  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return json({ error: "request too large" }, 413);
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ error: "bad json" }, 400);
  }
  // The honeypot: a human never sees the field, so a value means a script.
  if (String(body.website || "").trim()) return json({ ok: true, run_id: null, emailed: false });

  const email = String(body.email || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 200) return json({ error: "a real email address, please" }, 400);
  const firstName = String(body.first_name || "").trim().slice(0, 80) || null;
  const platform = body.platform === "shopify" ? "shopify" : "amazon";
  const inputs = platform === "shopify" ? cleanShopifyInputs(body.inputs) : cleanInputs(body.inputs);
  if (!inputs.price || !(platform === "shopify" ? inputs.weightOz : inputs.itemWeightOz)) return json({ error: "a price and a weight are needed to send a result" }, 400);
  const asin = platform === "amazon" ? inputs.asin : null;
  const summary = body.summary && typeof body.summary === "object" ? body.summary : {};
  const db = getDb();
  const hash = ipHash(ip);

  // The durable limits: a day of captures per address and per hashed IP.
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const [{ count: byIp }, { count: byEmail }] = await Promise.all([
    db.from("tool_runs").select("id", { count: "exact", head: true }).eq("ip_hash", hash).gte("created_at", since),
    db.from("tool_runs").select("id", { count: "exact", head: true }).eq("email", email).gte("created_at", since),
  ]);
  if ((byIp ?? 0) >= DAILY_PER_IP) return tooMany(3600 * 1000, "results from this connection today");
  if ((byEmail ?? 0) >= DAILY_PER_EMAIL) return json({ error: "That address already has today's results. Check your inbox, or reply to one of them." }, 429);

  // The result, recomputed here; the email is built from this and nothing else.
  const rc = await ratecard(request);
  const result = platform === "shopify" ? fees.analyseShopify(rc, inputs) : fees.analyse(rc, inputs, new Date());
  const link = `${SITE}/teardown${platform === "shopify" ? fees.resultHashShopify(inputs) : fees.resultHash(inputs)}`;
  const lead = result.found[0];
  const headline = lead ? `${lead.kind} ${lead.perUnitLow}–${lead.perUnitHigh}/unit`
    : platform === "shopify" ? (result.econ?.keepLow != null ? `keeps ${result.econ.keepLow}–${result.econ.keepHigh} of ${result.econ.charged} an order` : "unpriced")
    : result.u?.keep != null ? `keeps ${result.u.keep} of ${result.u.price}` : "unpriced";

  // The prospect. An address the cold lane already holds keeps its source and
  // moves to wants_teardown unless it is further along than that already.
  let prospectId = null;
  if (!INTERNAL.test(email)) {
    const { data: existing } = await db.from("prospects").select("id, status").eq("email", email).maybeSingle();
    const company = String(summary.brand || "").trim().slice(0, 120) || null;
    const note = `60-second Teardown (${platform})${asin ? ` on ${asin}` : inputs.handle ? ` on ${inputs.handle}` : ""}: ${headline}`;
    if (existing) {
      prospectId = existing.id;
      const patch = { fit_notes: note, last_event_at: new Date().toISOString() };
      if (!["client", "booked", "wants_teardown", "unsubscribed"].includes(existing.status)) patch.status = "wants_teardown";
      if (firstName) patch.first_name = firstName;
      await db.from("prospects").update(patch).eq("id", existing.id);
    } else {
      const { data: created } = await db
        .from("prospects")
        .insert({ email, first_name: firstName, company_name: company, source: "tool", status: "wants_teardown", fit_notes: note, last_event_at: new Date().toISOString() })
        .select("id")
        .single();
      prospectId = created?.id ?? null;
    }
  }

  const { data: run, error } = await db
    .from("tool_runs")
    .insert({
      email, first_name: firstName, platform, asin,
      inputs: { ...inputs, link }, summary, prospect_id: prospectId, ip_hash: hash,
      referer: (request.headers.get("referer") || "").slice(0, 300) || null,
      ua: (request.headers.get("user-agent") || "").slice(0, 200) || null,
    })
    .select("id")
    .single();
  if (error) return json({ error: "could not save the run" }, 500);

  // The email they asked for. Without a key on this deployment the capture
  // still stands and the operator's upload-page email is what arrives.
  let emailed = false, emailError = null;
  if (process.env.RESEND_API_KEY) {
    const msg = composeToolEmail({ firstName, asin: platform === "shopify" ? inputs.handle : asin, result, link, applyUrl: APPLY_URL, postalAddress: process.env.POSTAL_ADDRESS || null });
    const sent = await sendResend({ apiKey: process.env.RESEND_API_KEY, from: FROM, to: email, replyTo: REPLY_TO, ...msg });
    emailed = sent.ok;
    emailError = sent.ok ? null : sent.error;
    if (sent.ok) await db.from("tool_runs").update({ email_sent_at: new Date().toISOString(), email_id: sent.id }).eq("id", run.id);
  }

  await db.from("funnel_events").insert({
    kind: "tool_capture", prospect_id: prospectId,
    payload: { run_id: run.id, asin, platform, headline, emailed, ...(emailError ? { email_error: String(emailError).slice(0, 200) } : {}) },
  });
  return json({ ok: true, run_id: run.id, emailed, provisioned: Boolean(prospectId) });
}
