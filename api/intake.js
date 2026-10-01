import { createClient } from "@supabase/supabase-js";
import { dispatchOperator, intakeView } from "../lib/intake.js";
import { resolveTokenFor } from "../lib/token.js";

/**
 * Tokenized client intake.
 *
 *   GET  /api/intake?t=<token>                     -> { ok, company, platform, uploads, cards, status } | 403
 *   POST { t, action: "init", files: [...] }       -> { ok, files: [{ upload_id, signed_url }] }
 *   POST { t, action: "complete", upload_ids: [] } -> { ok, completed: [...] }
 *
 * Files never pass through this function: "init" registers them and returns
 * Supabase Storage signed upload URLs the browser PUTs to directly, which
 * sidesteps Vercel's request body limit.
 *
 * GET is what makes the page remember (lib/intake.js): every file already
 * sent, whether it has been read or needs a fix (in a sentence, never the
 * parser's own words), and the status line from the call to the first move
 * notices. "complete" wakes the operator through GitHub's workflow_dispatch
 * when GITHUB_DISPATCH_TOKEN and GITHUB_DISPATCH_REPO are set.
 */

const BUCKET = "intake";
const MAX_FILES_PER_REQUEST = 12;
const MAX_FILE_BYTES = 52428800; // keep in sync with the bucket's file_size_limit
const ALLOWED_EXTENSIONS = [".csv", ".txt", ".tsv"];
const REPORT_TYPES = new Set([
  "business_report",
  "sku_economics",
  "ppc_search_terms",
  "ppc_campaign",
  "fba_inventory",
  "cogs",
  // bleed reports
  "fba_reimbursements",
  "fba_returns",
  "inventory_ledger",
  "inventory_health",
  "transactions",
  // the Shopify route: the store's own exports and the two ad platforms a
  // Shopify brand actually buys (engine/src/hubricon_engine/ingest/shopify_*.py)
  "shopify_orders",
  "shopify_products",
  "shopify_inventory",
  "shopify_payouts",
  "meta_ads",
  "google_ads_campaign",
  "google_ads_search_terms",
]);
// business/economics/ppc exports and the row-level bleed reports cover a
// date range; the two inventory reports are snapshots (period_start only);
// cogs is timeless. Shopify orders, payouts and the ad exports cover a
// range; the products and inventory exports are snapshots (stock on hand at
// the moment of export, and — from the products file — cost per item).
const RANGE_SCOPED = new Set([
  "business_report",
  "sku_economics",
  "ppc_search_terms",
  "ppc_campaign",
  "transactions",
  "fba_reimbursements",
  "fba_returns",
  "inventory_ledger",
  "shopify_orders",
  "shopify_payouts",
  "meta_ads",
  "google_ads_campaign",
  "google_ads_search_terms",
]);
const SNAPSHOT_SCOPED = new Set([
  "fba_inventory",
  "inventory_health",
  "shopify_products",
  "shopify_inventory",
]);

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

// One link, one job: this page opens only upload links (lib/token.js).
async function resolveToken(db, token) {
  return resolveTokenFor(db, token, "upload");
}

function isIsoDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

function sanitizeFilename(name) {
  const base = String(name ?? "").split(/[\\/]/).pop() ?? "";
  const clean = base.replace(/[^\w.\- ]+/g, "_").trim().slice(0, 120);
  return clean || "upload.csv";
}

function validateFileSpec(spec) {
  if (!spec || typeof spec !== "object") return "each file must be an object";
  if (!REPORT_TYPES.has(spec.report_type)) return `unknown report_type: ${spec.report_type}`;
  const filename = sanitizeFilename(spec.filename);
  if (!ALLOWED_EXTENSIONS.some((ext) => filename.toLowerCase().endsWith(ext))) {
    return `"${filename}" must be a ${ALLOWED_EXTENSIONS.join("/")} export`;
  }
  const size = Number(spec.size);
  if (!Number.isFinite(size) || size <= 0 || size > MAX_FILE_BYTES) {
    return `"${filename}" exceeds the ${Math.floor(MAX_FILE_BYTES / 1048576)}MB limit`;
  }
  if (RANGE_SCOPED.has(spec.report_type)) {
    if (!isIsoDate(spec.period_start) || !isIsoDate(spec.period_end)) {
      return `"${filename}" needs period_start and period_end (YYYY-MM-DD)`;
    }
    if (spec.period_start > spec.period_end) return `"${filename}" has period_start after period_end`;
  } else if (SNAPSHOT_SCOPED.has(spec.report_type) && !isIsoDate(spec.period_start)) {
    return `"${filename}" needs a snapshot date (period_start, YYYY-MM-DD)`;
  }
  return null;
}

export async function GET(request) {
  const notConfigured = missingEnv();
  if (notConfigured) return notConfigured;

  const token = new URL(request.url).searchParams.get("t");
  const db = getDb();
  const identity = await resolveToken(db, token);
  if (!identity) return Response.json({ ok: false }, { status: 403 });
  // `platform` decides which export cards the page shows: 'amazon', 'shopify' or 'both'.
  const view = await intakeView(db, identity.client_id);
  return Response.json(
    { ok: true, company: identity.company_name, ...view },
    { headers: { "cache-control": "no-store" } }
  );
}

export async function POST(request) {
  const notConfigured = missingEnv();
  if (notConfigured) return notConfigured;

  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const db = getDb();
  const identity = await resolveToken(db, body?.t);
  if (!identity) return Response.json({ ok: false }, { status: 403 });

  if (body.action === "init") {
    const specs = body.files;
    if (!Array.isArray(specs) || specs.length === 0 || specs.length > MAX_FILES_PER_REQUEST) {
      return Response.json(
        { ok: false, error: `Send 1-${MAX_FILES_PER_REQUEST} files per request` },
        { status: 400 }
      );
    }
    for (const spec of specs) {
      const problem = validateFileSpec(spec);
      if (problem) return Response.json({ ok: false, error: problem }, { status: 400 });
    }

    const results = [];
    for (const spec of specs) {
      const filename = sanitizeFilename(spec.filename);
      const row = {
        client_id: identity.client_id,
        report_type: spec.report_type,
        original_filename: filename,
        content_type: typeof spec.content_type === "string" ? spec.content_type.slice(0, 100) : null,
        declared_size_bytes: Number(spec.size),
        period_start: spec.period_start ?? null,
        period_end: RANGE_SCOPED.has(spec.report_type) ? spec.period_end : null,
        storage_path: "pending",
      };
      const { data: upload, error } = await db.from("uploads").insert(row).select("id").single();
      if (error) return Response.json({ ok: false, error: "Could not register upload" }, { status: 500 });

      const path = `${identity.client_id}/${upload.id}/${filename}`;
      const [{ error: pathError }, { data: signed, error: signError }] = await Promise.all([
        db.from("uploads").update({ storage_path: path }).eq("id", upload.id),
        db.storage.from(BUCKET).createSignedUploadUrl(path),
      ]);
      if (pathError || signError || !signed?.signedUrl) {
        return Response.json({ ok: false, error: "Could not create upload URL" }, { status: 500 });
      }
      results.push({ upload_id: upload.id, signed_url: signed.signedUrl });
    }
    return Response.json({ ok: true, files: results });
  }

  if (body.action === "complete") {
    const ids = body.upload_ids;
    if (!Array.isArray(ids) || ids.length === 0 || ids.length > MAX_FILES_PER_REQUEST) {
      return Response.json({ ok: false, error: "Send the upload_ids to finalize" }, { status: 400 });
    }
    const { data: rows, error } = await db
      .from("uploads")
      .select("id, storage_path, status")
      .eq("client_id", identity.client_id)
      .in("id", ids.map(String).slice(0, MAX_FILES_PER_REQUEST));
    if (error) return Response.json({ ok: false, error: "Lookup failed" }, { status: 500 });

    const completed = [];
    for (const row of rows ?? []) {
      if (row.status !== "pending") continue;
      // Trust nothing from the browser: confirm the object actually landed.
      const dir = row.storage_path.split("/").slice(0, -1).join("/");
      const name = row.storage_path.split("/").pop();
      const { data: objects } = await db.storage.from(BUCKET).list(dir);
      if (!objects?.some((o) => o.name === name)) continue;
      const { error: updateError } = await db
        .from("uploads")
        .update({ status: "uploaded", uploaded_at: new Date().toISOString() })
        .eq("id", row.id);
      if (!updateError) completed.push(row.id);
    }
    // Files are in: ask the operator to read them now rather than on its next
    // hourly run. Awaited (a serverless function may stop once it responds),
    // bounded by a timeout, and never allowed to fail the upload.
    if (completed.length) {
      const woke = await dispatchOperator(process.env);
      if (!woke.dispatched && woke.reason !== "not configured") console.warn(`operator dispatch: ${woke.reason}`);
    }
    return Response.json({ ok: true, completed });
  }

  return Response.json({ ok: false, error: "Unknown action" }, { status: 400 });
}
