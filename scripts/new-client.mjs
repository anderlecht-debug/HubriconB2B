/**
 * Onboard an audit prospect before any Stripe money moves.
 *
 *   npm install
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com
 *
 * Finds-or-creates the client by email (status 'pending' — the Stripe
 * webhook flips it to 'active' on conversion), revokes any previous intake
 * links, mints a fresh one, and prints the data-request email to send.
 * Re-running always rotates the link; old links stop working immediately.
 */
import { createHash, randomBytes } from "node:crypto";
import { parseArgs } from "node:util";
import { createClient } from "@supabase/supabase-js";

const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !process.env[k]);
if (missing.length) {
  console.error(`Set ${missing.join(", ")} before running.`);
  process.exit(1);
}

const { values: args } = parseArgs({
  options: {
    company: { type: "string" },
    name: { type: "string" },
    email: { type: "string" },
  },
});
if (!args.email) {
  console.error('Usage: npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com');
  process.exit(1);
}
const email = args.email.trim().toLowerCase();

const INTAKE_BASE_URL = process.env.INTAKE_BASE_URL ?? "https://www.hubricon.com";
const TOKEN_LIFETIME_DAYS = 90;

const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

let { data: client, error: findError } = await db
  .from("clients")
  .select("id, company_name, contact_name, status")
  .eq("contact_email", email)
  .maybeSingle();
if (findError) {
  console.error("Client lookup failed:", findError.message);
  process.exit(1);
}

if (client) {
  console.log(`Client already exists: ${client.company_name ?? email} (${client.id}, ${client.status})`);
} else {
  const insert = { contact_email: email, status: "pending" };
  if (args.company) insert.company_name = args.company;
  if (args.name) insert.contact_name = args.name;
  const { data, error } = await db.from("clients").insert(insert).select("id, company_name").single();
  if (error) {
    console.error("Client creation failed:", error.message);
    process.exit(1);
  }
  client = data;
  console.log(`Created client: ${client.company_name ?? email} (${client.id})`);
}

const { data: revoked, error: revokeError } = await db.rpc("revoke_intake_tokens", {
  p_client_id: client.id,
});
if (revokeError) {
  console.error("Token revocation failed:", revokeError.message);
  process.exit(1);
}
if (revoked > 0) console.log(`Revoked ${revoked} previous intake link(s).`);

const token = randomBytes(32).toString("base64url");
const tokenHash = createHash("sha256").update(token).digest("hex");
const expiresAt = new Date(Date.now() + TOKEN_LIFETIME_DAYS * 24 * 60 * 60 * 1000).toISOString();
const { error: tokenError } = await db.rpc("create_intake_token", {
  p_client_id: client.id,
  p_token_hash: tokenHash,
  p_label: "audit intake",
  p_expires_at: expiresAt,
});
if (tokenError) {
  console.error("Token creation failed:", tokenError.message);
  process.exit(1);
}

const link = `${INTAKE_BASE_URL}/intake?t=${token}`;
const welcome = `${INTAKE_BASE_URL}/welcome`;
const execEmail = process.env.EXECUTION_EMAIL ?? "hagen.simmons@hubricon.com";
const firstName = (args.name ?? client.contact_name ?? "").split(/\s+/)[0] || "there";

console.log(`
Fallback intake link (valid ${TOKEN_LIFETIME_DAYS} days, not stored anywhere — copy it now):

  ${link}

WHEN THEY SAY YES (free month or paid), send the welcome email:
──────────────────────────────────────────────────────────────────────
Subject: You're in — one 2-minute step and we take it from here

Hi ${firstName},

Welcome aboard. Everything you need is on one page:

  ${welcome}

The short version: add ${execEmail} as a user in your
Seller Central (Settings → User Permissions — the page shows the exact
four permissions), and book your kickoff on the same page. Within 24
hours of that seat going live you'll have your Profit Teardown on
video, and on the kickoff call I'll present your 90-day plan.

One five-minute homework: Amazon doesn't know your unit costs. Grab
the template on your secure upload page and fill one row per SKU
(estimates are fine):

  ${link}

Your first month is free. If we don't find you more than we cost,
walk away owing nothing.

Best,
Hagen — Hubricon
──────────────────────────────────────────────────────────────────────

IF THEY STALL ON THE SEAT after 2–3 days, send the nudge:
──────────────────────────────────────────────────────────────────────
Subject: 2 minutes and your Teardown starts

Quick nudge — your models are waiting on one thing: the seat.

Settings → User Permissions → Invite new user → ${execEmail}
Grant: Business Reports (view) · Fulfillment reports (view) ·
Pricing (view & edit) · Campaign Manager (view & edit). Nothing else.

The moment it's live, your 24-hour Teardown clock starts. Exact steps
with screenshots: ${welcome}
──────────────────────────────────────────────────────────────────────

IF THEY PREFER FILES over a seat, send the export fallback:
──────────────────────────────────────────────────────────────────────
Subject: Your Profit Teardown — 15 minutes of exports and you're done

Hi ${firstName},

No seat needed — five exports through your private upload page and
we're off (no account required):

  ${link}

1. Sales & traffic by product — Reports → Business Reports → "Detail
   Page Sales and Traffic by Child Item". One file PER MONTH for the
   last 6 months (this is what lets us model your trend, not just a
   snapshot).
2. Fees & SKU economics — Reports → SKU Economics → one file per month,
   same 6 months.
3. Advertising — Advertising Console → Measurement & Reporting →
   Sponsored ads reports → Sponsored Products / Search term → last 60 days.
4. Inventory — Reports → Fulfillment → FBA Inventory → today's snapshot.
5. Your costs — the page has a one-row-per-SKU template (unit cost,
   freight, packaging, lead time). Estimates are fine.

The models run the moment your last file lands — your Profit Teardown,
written and on video, is back within 24 hours.

Best,
Hagen — Hubricon
──────────────────────────────────────────────────────────────────────
`);
