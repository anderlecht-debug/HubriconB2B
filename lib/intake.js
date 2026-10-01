/**
 * What the upload page remembers, and the line that says what happens next.
 *
 * Until 2026-10-01 the page said "All set — N files received" once and forgot:
 * reopening the link showed nothing already sent, a file that failed to parse
 * was reported only to the founder, and nobody could see what came after the
 * upload. `intakeView` is everything GET /api/intake returns beyond the company
 * and platform: each upload in plain words, a summary per card, and a status
 * line whose every date is one the code actually keeps.
 *
 * Pure apart from the database reads in `intakeView`, so the page's promises
 * are tested here (lib/intake.test.mjs) rather than discovered by a client.
 */

// The core set: what Issue 001 (the first full read) waits for before it
// publishes, unless 24 hours pass after the last upload first. Kept in step
// with the engine's rule for Issue 001 (operator.teardowns).
export const CORE = {
  amazon: ["business_report", "sku_economics"],
  shopify: ["shopify_orders", "shopify_products"],
};

export function coreSet(platform) {
  const p = String(platform || "amazon").toLowerCase();
  if (p === "both") return [...CORE.amazon, ...CORE.shopify];
  return CORE[p] ? [...CORE[p]] : [...CORE.amazon];
}

// The card each report type is sent on. The advertising card takes either of
// two Amazon reports.
export const cardOf = (reportType) => (String(reportType).startsWith("ppc_") ? "ppc" : String(reportType));

export const CARD_NAME = {
  business_report: "Sales & traffic by product", sku_economics: "SKU economics", ppc: "Advertising",
  fba_inventory: "FBA inventory snapshot", cogs: "Your costs", fba_reimbursements: "Reimbursements",
  fba_returns: "Customer returns", inventory_ledger: "Inventory ledger", inventory_health: "Inventory age",
  transactions: "Payments transactions", shopify_orders: "Orders", shopify_products: "Products & costs",
  shopify_inventory: "Inventory", shopify_payouts: "Payouts", meta_ads: "Meta ads",
  google_ads_campaign: "Google ads — campaigns", google_ads_search_terms: "Google ads — search terms",
};

// ------------------------------------------------------------------ stages --
// A mirror of engine/src/hubricon_engine/lifecycle.py, which is the contract.
// A kickoff booking is a client's follow-up, never the application call
// (onboarding.KICKOFF_EVENT).
export const KICKOFF_EVENT = /kick\s*-?\s*off/i;

function ts(v) {
  if (!v) return null;
  const d = v instanceof Date ? v : new Date(String(v).replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? null : d;
}

/** The time of the application call: the latest booking that is not a kickoff. */
export function callAt(bookings) {
  const rows = [...(bookings || [])].sort((a, b) => String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")));
  for (const b of rows) {
    if (!KICKOFF_EVENT.test(b.event_type || "") && b.starts_at) return ts(b.starts_at);
  }
  return null;
}

/** lifecycle.ALLOWED: what may be emailed, unasked, at each stage. */
export const ALLOWED = {
  booked: ["call_prep", "first_read"],
  called: ["first_read", "nudge", "files", "downsell"],
  agreed: ["agreed", "first_read", "nudge", "files", "moves", "brief", "weekly_note", "alerts"],
  declined: [],
  churned: [],
};
export const maySend = (stageName, kind) => (ALLOWED[stageName] || []).includes(kind);

/** lifecycle.stage: booked, called, agreed, declined or churned. */
export function stage(client, call, now = new Date()) {
  const status = String(client?.status || "pending").toLowerCase();
  if (status === "churned") return "churned";
  if (status === "declined") return "declined";
  if (client?.retainer_started_at || status === "active" || status === "past_due") return "agreed";
  const when = ts(call);
  if (when && when <= now) return "called";
  return "booked";
}

// -------------------------------------------------------------- the dates --
const isoDay = (d) => d.toISOString().slice(0, 10);

/** monthly.add_months: the same day n months on, clamped to the month's last day. */
export function addMonths(day, n) {
  const [y, m, d] = String(day).slice(0, 10).split("-").map(Number);
  const total = m - 1 + n;
  const year = y + Math.floor(total / 12);
  const month = ((total % 12) + 12) % 12;
  const last = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return isoDay(new Date(Date.UTC(year, month, Math.min(d, last))));
}

/** Month 0 of monthly.billing_months: from the day of the yes to the day before the same date a month on. */
export function provingMonth(retainerStartedAt) {
  const start = ts(retainerStartedAt);
  if (!start) return null;
  const first = String(retainerStartedAt).slice(0, 10);
  const next = new Date(`${addMonths(first, 1)}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() - 1);
  return { start: first, end: isoDay(next) };
}

/** The next weekly pass: .github/workflows/sweep.yml runs Mondays 11:00 UTC. */
export function nextSweep(now = new Date()) {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 11));
  d.setUTCDate(d.getUTCDate() + ((1 - d.getUTCDay() + 7) % 7));
  if (d <= now) d.setUTCDate(d.getUTCDate() + 7);
  return isoDay(d);
}

// ------------------------------------------------------------- the uploads --
const STATUS = { uploaded: "received", parsed: "parsed", failed: "failed" };

/**
 * The parser's error, as a sentence that says what to do. The engine writes
 * `uploads.parse_error` for the founder (column lists, Python reprs); a client
 * gets the fix. Every pattern here is an error the readers or parsers raise
 * (engine/src/hubricon_engine/ingest/, cli._ingest_client).
 */
export function plainProblem(parseError, reportType) {
  const e = String(parseError || "");
  const name = CARD_NAME[cardOf(reportType)] || "this";
  if (/not text in any supported encoding/i.test(e))
    return "This file isn't plain text: it may be an Excel file or a .zip. Download the export again as a CSV (unzip it first if it came zipped) and send the .csv.";
  if (/could not find a header row/i.test(e))
    return "We couldn't find the column headings near the top of the file. Send the export exactly as it downloaded, with nothing added above the headings.";
  if (/header but no data rows/i.test(e))
    return "The file has headings but no rows. Usually a filter was on or the date range was empty: clear any filters, check the dates, and export again.";
  if (/csv parse failed/i.test(e))
    return "The file is damaged or isn't a CSV. Download the export again and send it as it arrived, without opening and re-saving it.";
  if (/unrecognized (date|time of day)/i.test(e))
    return "A date in the file is in a format we don't read, which usually means it was opened and re-saved in a spreadsheet. Download the export again and send it untouched.";
  if (/no cost per item and no variant inventory qty/i.test(e))
    return "The products export has no Cost per item and no stock quantities. Fill in Cost per item in Shopify before you export; with more than one location, send the Inventory export as well.";
  if (/missing required column/i.test(e) && cardOf(reportType) === "cogs")
    return "This isn't the cost template, or one of its columns was renamed or removed. Download the template from the card, fill it in without changing its headings, and send it again.";
  if (/missing required column/i.test(e))
    return `This doesn't match the “${name}” card: a column that export always carries is missing. Check you picked the report the card names, with no columns hidden, and send it again.`;
  if (/no usable data rows/i.test(e))
    return "Nothing in the file could be used. It may cover dates outside the ones on its card, or be a different report. Check both and send it again.";
  return "We couldn't read this file. Send it again exactly as it downloaded; if it fails twice, reply to any email from us and we'll sort it out.";
}

/** One upload as the page shows it. A row still 'pending' never reached storage and is left out. */
export function presentUpload(row) {
  const status = STATUS[row.status];
  if (!status) return null;
  return {
    id: row.id,
    kind: row.report_type,
    card: cardOf(row.report_type),
    filename: row.original_filename || "upload.csv",
    status,
    rows: status === "parsed" && Number.isFinite(row.row_count) ? row.row_count : null,
    period_start: row.period_start || null,
    period_end: row.period_end || null,
    uploaded_at: row.uploaded_at || null,
    problem: status === "failed" ? plainProblem(row.parse_error, row.report_type) : null,
  };
}

/**
 * Per card: what is in, what we have read, and what still needs a fix. A
 * failed file stops needing a fix once a later file for the same card and the
 * same period has arrived, so re-sending a month clears it.
 */
export function summarizeCards(uploads) {
  const out = {};
  const byTime = [...uploads].sort((a, b) => String(a.uploaded_at ?? "").localeCompare(String(b.uploaded_at ?? "")));
  for (const u of byTime) {
    const c = (out[u.card] ??= { status: null, read: 0, received: 0, rows: 0, period_start: null, period_end: null, problems: [] });
    if (u.status === "parsed") {
      c.read += 1;
      c.rows += u.rows || 0;
      if (u.period_start && (!c.period_start || u.period_start < c.period_start)) c.period_start = u.period_start;
      const end = u.period_end || u.period_start;
      if (end && (!c.period_end || end > c.period_end)) c.period_end = end;
    } else if (u.status === "received") {
      c.received += 1;
    }
    if (u.status === "failed") {
      c.problems.push({ filename: u.filename, problem: u.problem, period_start: u.period_start, uploaded_at: u.uploaded_at });
    } else {
      c.problems = c.problems.filter((p) => (p.period_start || null) !== (u.period_start || null));
    }
  }
  for (const c of Object.values(out)) {
    c.status = c.problems.length ? "failed" : c.read ? "parsed" : c.received ? "received" : null;
  }
  return out;
}

// ------------------------------------------------------------ status line --
/**
 * The line across the top of the page: Call → Files → First full read →
 * Proving Month → First move notices. A stage the client has not reached is
 * left out, not shown greyed, and every date is one the code keeps: the call
 * from their booking, the Proving Month from the day of the yes, the move
 * notices from the weekly pass. The first read's timing is a rule, not a date.
 */
export function statusLine({ client, bookings, uploads, firstReadAt, movesNotified, now = new Date() }) {
  const call = callAt(bookings);
  const s = stage(client, call, now);
  const core = coreSet(client?.platform);
  const cards = summarizeCards(uploads || []);
  const inCore = core.filter((t) => cards[t] && (cards[t].read || cards[t].received));
  const last = (uploads || []).map((u) => u.uploaded_at).filter(Boolean).sort().pop() || null;
  const agreed = s === "agreed";
  const gone = s === "declined" || s === "churned";
  return {
    stage: s,
    call: call ? { at: call.toISOString(), past: call <= now } : null,
    files: { core, in: inCore, count: inCore.length, of: core.length, last_upload_at: last },
    first_read: firstReadAt ? { published_at: ts(firstReadAt).toISOString() } : gone ? null : { published_at: null },
    proving_month: agreed ? provingMonth(client.retainer_started_at) : null,
    move_notices: agreed ? { first: !movesNotified, next_pass: nextSweep(now) } : null,
  };
}

// ---------------------------------------------------------- the database --
async function settle(promise) {
  try {
    const { data, error } = await promise;
    return error ? null : data;
  } catch {
    return null;
  }
}

/**
 * Everything the page shows beyond the company name, read for one client.
 * Every read degrades to "nothing known" rather than failing the page: a
 * client must always be able to send files, whatever else is down.
 */
export async function intakeView(db, clientId, now = new Date()) {
  const [client, uploads, bookings, issue, notified] = await Promise.all([
    settle(db.from("clients").select("platform, status, retainer_started_at").eq("id", clientId).maybeSingle()),
    settle(db.from("uploads")
      .select("id, report_type, original_filename, status, row_count, period_start, period_end, uploaded_at, parse_error")
      .eq("client_id", clientId).in("status", ["uploaded", "parsed", "failed"])
      .order("uploaded_at", { ascending: false }).limit(500)),
    settle(db.from("bookings").select("starts_at, event_type, created_at").eq("client_id", clientId)
      .order("created_at", { ascending: false }).limit(20)),
    settle(db.from("briefings").select("created_at").eq("client_id", clientId).eq("issue_number", 1).limit(1)),
    settle(db.from("directives").select("id").eq("client_id", clientId).not("notified_at", "is", null).limit(1)),
  ]);
  const row = client || {};
  const shown = (uploads || []).map(presentUpload).filter(Boolean);
  return {
    platform: row.platform ?? "amazon",
    uploads: shown,
    cards: summarizeCards(shown),
    status: statusLine({
      client: row, bookings: bookings || [], uploads: shown,
      firstReadAt: issue?.[0]?.created_at || null, movesNotified: Boolean(notified?.length), now,
    }),
  };
}

// ---------------------------------------------------------- the dispatch --
/**
 * Wake the operator when files land, instead of waiting for its hourly run
 * (which GitHub delays by hours). Only when GITHUB_DISPATCH_TOKEN and
 * GITHUB_DISPATCH_REPO ("owner/repo") are set; otherwise nothing happens and
 * the hourly run reads the files as before. Never throws: an upload is never
 * failed because GitHub was slow. The page promises no speed either way.
 */
export async function dispatchOperator(env = {}, fetchImpl = globalThis.fetch) {
  const token = env.GITHUB_DISPATCH_TOKEN;
  const repo = env.GITHUB_DISPATCH_REPO;
  if (!token || !repo) return { dispatched: false, reason: "not configured" };
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) return { dispatched: false, reason: "GITHUB_DISPATCH_REPO must be owner/repo" };
  const url = `https://api.github.com/repos/${repo}/actions/workflows/operator.yml/dispatches`;
  try {
    const res = await fetchImpl(url, {
      method: "POST",
      headers: {
        accept: "application/vnd.github+json",
        authorization: `Bearer ${token}`,
        "x-github-api-version": "2022-11-28",
        "content-type": "application/json",
        "user-agent": "hubricon-intake",
      },
      body: JSON.stringify({ ref: env.GITHUB_DISPATCH_REF || "main" }),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(5000) : undefined,
    });
    return res.status === 204 ? { dispatched: true } : { dispatched: false, reason: `GitHub ${res.status}` };
  } catch (err) {
    return { dispatched: false, reason: String(err?.message || err) };
  }
}
