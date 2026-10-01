/**
 * Set a prospect up by hand: the client row, a fresh upload link, and the
 * emails the machine would send at their stage.
 *
 *   npm install
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com [--platform shopify]
 *
 * --platform (amazon | shopify | both, default amazon) is recorded on the
 * client and decides which export list the emails carry and which cards the
 * upload page shows.
 *
 * Finds-or-creates the client by email (status 'pending'), revokes any
 * previous intake links, mints a fresh one, and prints the emails. Re-running
 * always rotates the link; old links stop working immediately.
 *
 * The emails follow the journey (engine/src/hubricon_engine/lifecycle.py):
 *   call_prep  before the call: what it is, what to have ready, and the
 *              upload link as an option, never a condition
 *   nudge      after the call: the upload page again
 *   files      after the call: the export list in full
 * The yes is recorded with `hubricon retainer`, which sends the letter that
 * dates the Proving Month; nothing here sends it.
 *
 * Add `--send call_prep` (or `nudge` / `files`) to deliver one through
 * Resend from Hagen Simmons <hagen.simmons@hubricon.com>. Needs
 * RESEND_API_KEY. It is refused when the client's stage does not allow it
 * (no nudge before the call, nothing after a no); `--force` overrides, for
 * the founder's own judgement. `--to` overrides the recipient (send yourself
 * a copy first).
 */
import { createHash, randomBytes } from "node:crypto";
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";
import { emailConfigured, renderHtml, renderText, sendEmail } from "./lib/email.mjs";
import { callAt, coreSet, CARD_NAME, maySend, stage } from "../lib/intake.js";

export const EMAIL_KINDS = ["call_prep", "nudge", "files"];
const TOKEN_LIFETIME_DAYS = 90;

const AMAZON_EXPORTS = [
  'Sales & traffic by product — Reports → Business Reports → "Detail Page Sales and Traffic by Child Item". ' +
    "One file PER MONTH for the last 6 months (this is what lets us model your trend, not just a snapshot).",
  "Fees & SKU economics — Reports → SKU Economics → one file per month, same 6 months.",
  "Advertising — Advertising Console → Measurement & Reporting → Sponsored ads reports → " +
    "Sponsored Products / Search term → last 60 days.",
  "Inventory — Reports → Fulfillment → FBA Inventory → today's snapshot.",
];
const SHOPIFY_EXPORTS = [
  "Orders — Shopify admin → Orders → clear any filters → Export → Orders by date, last 6 months → Plain CSV file.",
  "Products — Products → Export → All products → Plain CSV file (fill in Cost per item first if it is blank; on a single-location store the same file is your stock snapshot).",
  "Payouts — Finances → Payouts → View transactions → Export → last 90 days (Shopify Payments only).",
  "Advertising — Meta Ads Manager → Campaigns → breakdown by Day → Export CSV; and/or Google Ads → Campaigns (segment by Day) → Download CSV, plus Insights & reports → Search terms → Download CSV.",
];
const COSTS =
  "Your costs — the page has a one-row-per-SKU template (unit cost, freight, packaging, pick/pack/postage, lead time). " +
  "Estimates are fine.";
const SHOPIFY_NOTE =
  "Two things about Shopify exports: clear any filter or search first, because an export sends only what is on " +
  "screen; and expect the file by email rather than in your browser.";

export function exportsFor(platform) {
  if (platform === "shopify") return [...SHOPIFY_EXPORTS, COSTS];
  if (platform === "both") {
    return [...AMAZON_EXPORTS.map((e) => `Amazon — ${e}`), ...SHOPIFY_EXPORTS.map((e) => `Shopify — ${e}`), COSTS];
  }
  return [...AMAZON_EXPORTS, COSTS];
}

const OFFER =
  "Managed Profit is $6,000 a month, flat. The first month, the Proving Month, is free; after it, a month is " +
  "invoiced only if your Profit Record shows it cleared the fee.";

/** The emails, one definition each; lib/email.mjs renders each as HTML and as text. */
export function emailsFor({ firstName, platform = "amazon", link }) {
  const greeting = `Hi ${firstName || "there"},`;
  const exports = exportsFor(platform);
  const count = exports.length === 5 ? "Five" : String(exports.length);
  const core = coreSet(platform).map((t) => CARD_NAME[t]).join(", ");
  const shopify = platform === "shopify" || platform === "both";
  const amazon = platform !== "shopify";
  const ready = [
    amazon
      ? "On Amazon: Seller Central open, and two reports downloaded, Inventory Age (Reports → Fulfillment → Manage " +
        "Inventory Health) and Fee Preview (Reports → Fulfillment → Fee Preview). A campaign report by day is optional."
      : null,
    shopify ? "On Shopify: your admin open." : null,
    "And your landed cost per unit, roughly, as a share of price: unit cost, freight and packaging. A guess is fine.",
  ].filter(Boolean);
  return {
    call_prep: {
      when: "ON BOOKING (before the call), send what the call is:",
      subject: "Your call: what it is, and what to have ready",
      greeting,
      blocks: [
        { p: "Your call is booked. Twenty minutes, on your own numbers." },
        {
          p: amazon
            ? "We open two or three of your own Seller Central reports together and price, while we talk, the costs " +
              "only your data shows: aged stock heading for day 271, the low-inventory fee, units just past a fee " +
              "edge, ads spending past break-even. The reports are read in your browser; nothing is uploaded for that part."
            : "We go through your store's own numbers together: where the margin goes, SKU by SKU.",
        },
        { p: "To have ready:" },
        { ol: ready },
        {
          p:
            "Optional: if you'd like your first full read before we speak, your private upload page takes your " +
            "exports. Nothing waits on it.",
        },
        { button: "Open your upload page", url: link },
        { p: OFFER },
      ],
    },
    nudge: {
      when: "AFTER THE CALL, if their files have not come, send the nudge:",
      subject: "Your upload page, again",
      greeting,
      blocks: [
        { p: "Your upload page shows what has come in and what is still missing:" },
        { button: "Open your upload page", url: link },
        {
          p:
            `Your first full read publishes when the core files are in (${core}), or 24 hours after your last ` +
            "upload. If something's in the way, a report you can't find or a seat you'd rather grant, reply here and I'll sort it.",
        },
      ],
    },
    files: {
      when: "AFTER THE CALL, if they want the full export list, send it:",
      subject: "Your exports, in about fifteen minutes",
      greeting,
      blocks: [
        { p: `${count} exports through your private upload page (no account needed):` },
        { button: "Open your upload page", url: link },
        { ol: exports },
        ...(shopify ? [{ p: SHOPIFY_NOTE }] : []),
        {
          p:
            "The page checks each file as you pick it, and shows each one as Received, Read or Needs a fix. Your " +
            `first full read publishes when the core files are in (${core}), or 24 hours after your last upload.`,
        },
      ],
    },
  };
}

async function main() {
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
      platform: { type: "string" },
      force: { type: "boolean", default: false },
    },
  });
  if (!args.email) {
    console.error('Usage: npm run new-client -- --company "Acme Goods" --name "Jane Doe" --email jane@acme.com [--platform amazon|shopify|both] [--send call_prep|nudge|files] [--force] [--to you@example.com]');
    process.exit(1);
  }
  const PLATFORMS = ["amazon", "shopify", "both"];
  if (args.platform && !PLATFORMS.includes(args.platform)) {
    console.error(`--platform must be one of ${PLATFORMS.join(", ")}`);
    process.exit(1);
  }
  if (args.send === "welcome") {
    console.error("The welcome email is retired. The yes is recorded with `hubricon retainer`, which sends the letter that dates the Proving Month.");
    process.exit(1);
  }
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

  const { createClient } = await import("@supabase/supabase-js");
  const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });

  let { data: client, error: findError } = await db
    .from("clients")
    .select("id, company_name, contact_name, status, platform, retainer_started_at")
    .eq("contact_email", email)
    .maybeSingle();
  if (findError) {
    console.error("Client lookup failed:", findError.message);
    process.exit(1);
  }

  if (client) {
    console.log(`Client already exists: ${client.company_name ?? email} (${client.id}, ${client.status}, ${client.platform ?? "amazon"})`);
    if (args.platform && args.platform !== client.platform) {
      const { error } = await db.from("clients").update({ platform: args.platform }).eq("id", client.id);
      if (error) {
        console.error("Platform update failed:", error.message);
        process.exit(1);
      }
      client.platform = args.platform;
      console.log(`Platform set to ${args.platform}.`);
    }
  } else {
    const insert = { contact_email: email, status: "pending", platform: args.platform ?? "amazon" };
    if (args.company) insert.company_name = args.company;
    if (args.name) insert.contact_name = args.name;
    const { data, error } = await db.from("clients").insert(insert).select("id, company_name, platform, status").single();
    if (error) {
      console.error("Client creation failed:", error.message);
      process.exit(1);
    }
    client = data;
    console.log(`Created client: ${client.company_name ?? email} (${client.id})`);
  }

  // Where they stand, the way lifecycle.py reads it: what may be sent depends on it.
  const { data: bookings } = await db.from("bookings").select("starts_at, event_type, created_at").eq("client_id", client.id);
  const where = stage(client, callAt(bookings ?? []));
  console.log(`Stage: ${where}.`);
  if (args.send && !maySend(where, args.send) && !args.force) {
    console.error(`A ${args.send} email is not sent at the ${where} stage (lifecycle.py). Add --force if you mean to.`);
    process.exit(1);
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
  const platform = args.platform ?? client.platform ?? "amazon";
  const EMAILS = emailsFor({ firstName, platform, link });
  const RULE = "─".repeat(70);

  console.log(`
Upload link (valid ${TOKEN_LIFETIME_DAYS} days, not stored anywhere — copy it now):

  ${link}
`);

  if (args.send) {
    const spec = EMAILS[args.send];
    const to = (args.to ?? email).trim().toLowerCase();
    try {
      const id = await sendEmail({ to, subject: spec.subject, html: renderHtml(spec), text: renderText(spec) });
      console.log(`Sent the ${args.send} email to ${to} — "${spec.subject}" (Resend id ${id}).`);
    } catch (err) {
      console.error(`Sending the ${args.send} email failed: ${err.message}`);
      console.error("The upload link above is still valid — send the draft below by hand.");
      console.log(`\n${RULE}\nSubject: ${spec.subject}\n\n${renderText(spec)}\n${RULE}`);
      process.exit(1);
    }
  } else {
    for (const [kind, spec] of Object.entries(EMAILS)) {
      const note = maySend(where, kind) ? "" : `  (not for the ${where} stage)`;
      console.log(`${spec.when}${note}\n${RULE}\nSubject: ${spec.subject}\n\n${renderText(spec)}\n${RULE}\n`);
    }
    console.log("Add `--send call_prep` (or nudge / files) to deliver one through Resend instead.");
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
