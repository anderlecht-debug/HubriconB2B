/**
 * Onboard an audit prospect before any Stripe money moves.
 *
 *   npm install
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com
 *
 * Finds-or-creates the client by email (status 'pending' — the Stripe
 * webhook flips it to 'active' on conversion), revokes any previous intake
 * links, mints a fresh one, and prints the onboarding emails to send.
 * Re-running always rotates the link; old links stop working immediately.
 *
 * Add `--send welcome` (or `nudge` / `files`) to deliver that email through
 * Resend, branded like the portal's sign-in link, from
 * Hagen Simmons <hagen.simmons@hubricon.com>. Needs RESEND_API_KEY. `--to`
 * overrides the recipient (send yourself a copy first).
 */
import { createHash, randomBytes } from "node:crypto";
import { parseArgs } from "node:util";
import { createClient } from "@supabase/supabase-js";
import { emailConfigured, renderHtml, renderText, sendEmail } from "./lib/email.mjs";

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
    send: { type: "string" },
    to: { type: "string" },
  },
});
if (!args.email) {
  console.error('Usage: npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com [--send welcome|nudge|files] [--to you@example.com]');
  process.exit(1);
}
const EMAIL_KINDS = ["welcome", "nudge", "files"];
if (args.send && !EMAIL_KINDS.includes(args.send)) {
  console.error(`--send must be one of ${EMAIL_KINDS.join(", ")}`);
  process.exit(1);
}
if (args.send && !emailConfigured()) {
  console.error("--send needs RESEND_API_KEY (a key from the Resend team that owns hubricon.com).");
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
const greeting = `Hi ${firstName},`;

// One definition per email; lib/email.mjs renders it as HTML and as text.
const EMAILS = {
  welcome: {
    when: "WHEN THEY SAY YES (free month or paid), send the welcome email:",
    subject: "You're in — one 2-minute step and we take it from here",
    greeting,
    blocks: [
      { p: "Welcome aboard. Everything you need is on one page:" },
      { button: "Open your welcome page", url: welcome },
      {
        p:
          `The short version: add ${execEmail} as a user in your Seller Central (Settings → User Permissions — ` +
          "the page shows the exact four permissions), and book your kickoff on the same page. Within 24 hours " +
          "of that seat going live you'll have your Profit Teardown on video, and on the kickoff call I'll " +
          "present your 90-day plan.",
      },
      {
        p:
          "One five-minute homework: Amazon doesn't know your unit costs. Grab the template on your secure " +
          "upload page and fill one row per SKU (estimates are fine):",
      },
      { button: "Open your secure upload page", url: link },
      { p: "Your first month is free. If we don't find you more than we cost, walk away owing nothing." },
    ],
  },
  nudge: {
    when: "IF THEY STALL ON THE SEAT after 2–3 days, send the nudge:",
    subject: "2 minutes and your Teardown starts",
    greeting,
    blocks: [
      { p: "Quick nudge — your models are waiting on one thing: the seat." },
      { path: `Settings → User Permissions → Invite new user → ${execEmail}` },
      {
        p:
          "Grant: Business Reports (view) · Fulfillment reports (view) · Pricing (view & edit) · " +
          "Campaign Manager (view & edit). Nothing else.",
      },
      { p: "The moment it's live, your 24-hour Teardown clock starts. Exact steps with screenshots:" },
      { button: "See the exact steps", url: welcome },
    ],
  },
  files: {
    when: "IF THEY PREFER FILES over a seat, send the export fallback:",
    subject: "Your Profit Teardown — 15 minutes of exports and you're done",
    greeting,
    blocks: [
      { p: "No seat needed — five exports through your private upload page and we're off (no account required):" },
      { button: "Open your private upload page", url: link },
      {
        ol: [
          'Sales & traffic by product — Reports → Business Reports → "Detail Page Sales and Traffic by Child Item". ' +
            "One file PER MONTH for the last 6 months (this is what lets us model your trend, not just a snapshot).",
          "Fees & SKU economics — Reports → SKU Economics → one file per month, same 6 months.",
          "Advertising — Advertising Console → Measurement & Reporting → Sponsored ads reports → " +
            "Sponsored Products / Search term → last 60 days.",
          "Inventory — Reports → Fulfillment → FBA Inventory → today's snapshot.",
          "Your costs — the page has a one-row-per-SKU template (unit cost, freight, packaging, lead time). " +
            "Estimates are fine.",
        ],
      },
      {
        p:
          "The models run the moment your last file lands — your Profit Teardown, written and on video, " +
          "is back within 24 hours.",
      },
    ],
  },
};

const RULE = "─".repeat(70);

console.log(`
Fallback intake link (valid ${TOKEN_LIFETIME_DAYS} days, not stored anywhere — copy it now):

  ${link}
`);

if (args.send) {
  const spec = EMAILS[args.send];
  const to = (args.to ?? email).trim().toLowerCase();
  try {
    const id = await sendEmail({
      to,
      subject: spec.subject,
      html: renderHtml(spec),
      text: renderText(spec),
    });
    console.log(`Sent the ${args.send} email to ${to} — "${spec.subject}" (Resend id ${id}).`);
  } catch (err) {
    console.error(`Sending the ${args.send} email failed: ${err.message}`);
    console.error("The intake link above is still valid — send the draft below by hand.");
    console.log(`\n${RULE}\nSubject: ${spec.subject}\n\n${renderText(spec)}\n${RULE}`);
    process.exit(1);
  }
} else {
  for (const spec of Object.values(EMAILS)) {
    console.log(`${spec.when}\n${RULE}\nSubject: ${spec.subject}\n\n${renderText(spec)}\n${RULE}\n`);
  }
  console.log("Add `--send welcome` (or nudge / files) to deliver it branded through Resend instead.");
}
