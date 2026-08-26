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
const firstName = (args.name ?? client.contact_name ?? "").split(/\s+/)[0] || "there";

console.log(`
Intake link (valid ${TOKEN_LIFETIME_DAYS} days, not stored anywhere — copy it now):

  ${link}

──────────────────────────────────────────────────────────────────────
Subject: Your Margin Audit — 15 minutes of exports and you're done

Hi ${firstName},

Great speaking with you today. To run your audit I need four exports
from Seller Central and one short spreadsheet, uploaded through your
private intake page (no account needed):

  ${link}

1. Sales & traffic by product — Reports → Business Reports → "Detail
   Page Sales and Traffic by Child Item". Export one file PER MONTH for
   the last 6 months (set the date range to each month, download, repeat
   — this is what lets us model your trend, not just a snapshot).

2. Fees & SKU economics — Reports → SKU Economics → one file per month,
   same 6 months.

3. Advertising — Advertising Console → Measurement & Reporting →
   Sponsored ads reports → Create report → Sponsored Products / Search
   term → last 60 days.

4. Inventory — Reports → Fulfillment → Inventory → FBA Inventory →
   Download (today's snapshot is fine).

5. Your costs — the intake page has a small template (one row per SKU:
   unit cost, freight, packaging, supplier lead time). Amazon doesn't
   know what you pay for your product, and margin math is impossible
   without it. Estimates are fine — flag anything uncertain in notes.

The upload page checks everything in as it arrives, and the models run
the moment your last file lands. Your audit — a written report plus a
recorded walkthrough of your numbers — is back within 24 hours.

Best,
Hubricon
──────────────────────────────────────────────────────────────────────
`);
