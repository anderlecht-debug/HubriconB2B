import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  CORE, ALLOWED, maySend, coreSet, callAt, stage, addMonths, provingMonth, nextSweep, plainProblem, presentUpload,
  summarizeCards, statusLine, intakeView, dispatchOperator,
} from "./intake.js";

const NOW = new Date("2026-10-01T15:00:00Z"); // a Thursday

// A Supabase client wide enough for intakeView: select/eq/in/not/order/limit/maybeSingle, awaited.
function fakeDb(tables = {}, { broken = [] } = {}) {
  return {
    from(name) {
      const rows = tables[name] ?? [];
      const filters = [];
      let one = false;
      const run = () => {
        if (broken.includes(name)) return { data: null, error: { message: `relation "${name}" does not exist` } };
        const hit = rows.filter((r) => filters.every((f) => f(r)));
        return { data: one ? hit[0] ?? null : hit, error: null };
      };
      const q = {
        select() { return q; },
        eq(k, v) { filters.push((r) => r[k] === v); return q; },
        in(k, vs) { filters.push((r) => vs.includes(r[k])); return q; },
        not(k, op, v) { filters.push((r) => (op === "is" && v === null ? r[k] != null : true)); return q; },
        order() { return q; },
        limit() { return q; },
        maybeSingle() { one = true; return q; },
        then(resolve, reject) { return Promise.resolve(run()).then(resolve, reject); },
      };
      return q;
    },
  };
}

// ── the lifecycle mirror ─────────────────────────────────────────────────────

test("the stage mirrors lifecycle.py: a yes, a no, a call that has or has not happened", () => {
  const past = new Date("2026-09-30T15:00:00Z"), soon = new Date("2026-10-02T15:00:00Z");
  assert.equal(stage({ status: "pending" }, soon, NOW), "booked");
  assert.equal(stage({ status: "pending" }, null, NOW), "booked");
  assert.equal(stage({ status: "pending" }, past, NOW), "called");
  assert.equal(stage({ status: "pending", retainer_started_at: "2026-10-01T00:00:00Z" }, soon, NOW), "agreed");
  assert.equal(stage({ status: "active" }, null, NOW), "agreed");
  assert.equal(stage({ status: "past_due" }, null, NOW), "agreed");
  assert.equal(stage({ status: "declined", retainer_started_at: "2026-10-01" }, past, NOW), "declined");
  assert.equal(stage({ status: "churned", retainer_started_at: "2026-10-01" }, past, NOW), "churned");
  // the engine's own table of stages is the one mirrored here
  const py = readFileSync(new URL("../engine/src/hubricon_engine/lifecycle.py", import.meta.url), "utf8");
  assert.match(py, /STAGES = \("booked", "called", "agreed", "declined", "churned"\)/);
  assert.match(py, /retainer_started_at"\) or status in \("active", "past_due"\)/);
});

test("what may be sent at each stage is lifecycle.py's table, word for word", () => {
  const py = readFileSync(new URL("../engine/src/hubricon_engine/lifecycle.py", import.meta.url), "utf8");
  const table = py.match(/ALLOWED: dict\[str, frozenset\[str\]\] = \{([\s\S]*?)\n\}/)[1];
  const parsed = {};
  for (const [, name, body] of table.matchAll(/"(\w+)": frozenset\((?:\{([^}]*)\})?\)/g)) {
    parsed[name] = [...(body || "").matchAll(/"(\w+)"/g)].map((m) => m[1]).sort();
  }
  assert.deepEqual(Object.fromEntries(Object.entries(ALLOWED).map(([k, v]) => [k, [...v].sort()])), parsed);
  assert.equal(maySend("booked", "call_prep"), true);
  assert.equal(maySend("booked", "nudge"), false, "no nudge before the call");
  assert.equal(maySend("declined", "files"), false, "nothing after a no");
});

test("the call is the latest booking that is not a kickoff", () => {
  const at = callAt([
    { starts_at: "2026-10-01T16:00:00Z", event_type: "Hubricon call", created_at: "2026-09-20T00:00:00Z" },
    { starts_at: "2026-10-08T16:00:00Z", event_type: "Kick-off", created_at: "2026-09-29T00:00:00Z" },
    { starts_at: "2026-10-03T16:00:00Z", event_type: "Hubricon call", created_at: "2026-09-25T00:00:00Z" }, // a reschedule
  ]);
  assert.equal(at.toISOString(), "2026-10-03T16:00:00.000Z");
  assert.equal(callAt([{ starts_at: null, event_type: "call", created_at: "x" }]), null);
  assert.equal(callAt([]), null);
});

// ── dates the code keeps ─────────────────────────────────────────────────────

test("the Proving Month runs from the day of the yes to the day before the same date a month on", () => {
  assert.deepEqual(provingMonth("2026-10-01T09:30:00+00:00"), { start: "2026-10-01", end: "2026-10-31" });
  assert.deepEqual(provingMonth("2026-10-14"), { start: "2026-10-14", end: "2026-11-13" });
  // monthly.add_months clamps: a yes on 31 January runs to 27 February
  assert.equal(addMonths("2027-01-31", 1), "2027-02-28");
  assert.deepEqual(provingMonth("2027-01-31"), { start: "2027-01-31", end: "2027-02-27" });
  assert.equal(addMonths("2026-12-15", 1), "2027-01-15");
  assert.equal(provingMonth(null), null);
});

test("the next weekly pass is the next Monday at 11:00 UTC, as sweep.yml schedules it", () => {
  const yml = readFileSync(new URL("../.github/workflows/sweep.yml", import.meta.url), "utf8");
  assert.match(yml, /cron: "0 11 \* \* 1"/);
  assert.equal(nextSweep(NOW), "2026-10-05");
  assert.equal(nextSweep(new Date("2026-10-05T10:59:00Z")), "2026-10-05");
  assert.equal(nextSweep(new Date("2026-10-05T11:00:00Z")), "2026-10-12");
  assert.equal(nextSweep(new Date("2026-10-04T23:00:00Z")), "2026-10-05");
});

// ── the files ────────────────────────────────────────────────────────────────

test("every error the readers and parsers raise becomes a sentence that says what to fix", () => {
  const raised = [
    "File is not text in any supported encoding",
    "Could not find a header row in the first 20 lines",
    "CSV parse failed: Error tokenizing data. C error: Expected 3 fields in line 9, saw 5",
    "File contains a header but no data rows",
    "Unrecognized date '13/45/2026'",
    "Unrecognized time of day in '25:99'",
    "Missing required column(s) ['units_ordered']; file headers were: ['SKU', 'Title']",
    "The products export states no Cost per item and no Variant Inventory Qty. Fill in Cost per item in Shopify",
    "No usable data rows after parsing",
    "something nobody has seen before",
  ];
  const seen = new Set();
  for (const err of raised) {
    const said = plainProblem(err, "business_report");
    assert.doesNotMatch(said, /\[|\]|'\w+'|_|Error|parse failed|column\(s\)/, `the parser's words reached the client: ${said}`);
    assert.match(said, /\.$/);
    seen.add(said);
  }
  assert.equal(seen.size, raised.length - 1, "the two date errors share one fix; every other error has its own");
  assert.match(plainProblem("Missing required column(s) ['sku']", "ppc_campaign"), /“Advertising” card/);
  assert.match(plainProblem("Missing required column(s) ['unit_cost_usd']", "cogs"), /cost template/);
  // the messages mapped here are the ones the engine still raises
  const readers = readFileSync(new URL("../engine/src/hubricon_engine/ingest/readers.py", import.meta.url), "utf8");
  for (const m of ["not text in any supported encoding", "Could not find a header row", "CSV parse failed", "header but no data rows"]) {
    assert.ok(readers.includes(m), `readers.py no longer raises "${m}"`);
  }
  const cli = readFileSync(new URL("../engine/src/hubricon_engine/cli.py", import.meta.url), "utf8");
  assert.ok(cli.includes("No usable data rows after parsing"));
});

test("an upload is shown as received, read or failed; one never confirmed is not shown", () => {
  assert.equal(presentUpload({ status: "pending", report_type: "cogs" }), null);
  const read = presentUpload({ id: "u1", status: "parsed", report_type: "ppc_campaign", row_count: 412, original_filename: "c.csv",
    period_start: "2026-08-01", period_end: "2026-09-29", uploaded_at: "2026-09-30T10:00:00Z", parse_error: null });
  assert.deepEqual(read, { id: "u1", kind: "ppc_campaign", card: "ppc", filename: "c.csv", status: "parsed", rows: 412,
    period_start: "2026-08-01", period_end: "2026-09-29", uploaded_at: "2026-09-30T10:00:00Z", problem: null });
  const failed = presentUpload({ id: "u2", status: "failed", report_type: "cogs", parse_error: "File contains a header but no data rows" });
  assert.equal(failed.status, "failed");
  assert.equal(failed.rows, null);
  assert.match(failed.problem, /headings but no rows/);
  assert.equal(presentUpload({ id: "u3", status: "uploaded", report_type: "cogs", row_count: 9 }).rows, null, "no rows before it is read");
});

test("a card says Read only once a file is parsed, and a re-sent file clears its fix", () => {
  const up = (id, status, extra = {}) => presentUpload({ id, status, report_type: "business_report", original_filename: `${id}.csv`, ...extra });
  const cards = summarizeCards([
    up("aug", "parsed", { row_count: 40, period_start: "2026-08-01", period_end: "2026-08-31", uploaded_at: "2026-09-01T00:00:00Z" }),
    up("sep", "failed", { period_start: "2026-09-01", period_end: "2026-09-30", uploaded_at: "2026-09-02T00:00:00Z", parse_error: "Unrecognized date 'x'" }),
    up("jul", "parsed", { row_count: 38, period_start: "2026-07-01", period_end: "2026-07-31", uploaded_at: "2026-09-03T00:00:00Z" }),
  ]);
  assert.equal(cards.business_report.status, "failed");
  assert.equal(cards.business_report.read, 2);
  assert.equal(cards.business_report.rows, 78);
  assert.equal(cards.business_report.period_start, "2026-07-01");
  assert.equal(cards.business_report.period_end, "2026-08-31");
  assert.equal(cards.business_report.problems.length, 1);

  const again = summarizeCards([
    up("sep", "failed", { period_start: "2026-09-01", uploaded_at: "2026-09-02T00:00:00Z", parse_error: "x" }),
    up("sep2", "uploaded", { period_start: "2026-09-01", uploaded_at: "2026-09-04T00:00:00Z" }),
  ]);
  assert.equal(again.business_report.status, "received", "received, not read: nothing has parsed it yet");
  assert.equal(again.business_report.problems.length, 0);
});

// ── the status line ──────────────────────────────────────────────────────────

const booking = (starts_at) => ({ starts_at, event_type: "Hubricon call", created_at: "2026-09-25T00:00:00Z" });

test("before the call: the call, the files, and the rule for the first read; no Proving Month, no move notices", () => {
  const line = statusLine({ client: { platform: "amazon", status: "pending" }, bookings: [booking("2026-10-02T16:00:00Z")],
    uploads: [], firstReadAt: null, now: NOW });
  assert.equal(line.stage, "booked");
  assert.deepEqual(line.call, { at: "2026-10-02T16:00:00.000Z", past: false });
  assert.deepEqual(line.files, { core: CORE.amazon, in: [], count: 0, of: 2, last_upload_at: null });
  assert.deepEqual(line.first_read, { published_at: null });
  assert.equal(line.proving_month, null);
  assert.equal(line.move_notices, null);
});

test("after the yes: the Proving Month's dates and the next weekly pass", () => {
  const uploads = [
    presentUpload({ id: "a", status: "parsed", report_type: "shopify_orders", row_count: 9, uploaded_at: "2026-09-29T00:00:00Z" }),
    presentUpload({ id: "b", status: "failed", report_type: "shopify_products", parse_error: "x", uploaded_at: "2026-09-30T00:00:00Z" }),
  ];
  const line = statusLine({ client: { platform: "shopify", status: "pending", retainer_started_at: "2026-10-01T12:00:00Z" },
    bookings: [booking("2026-09-30T16:00:00Z")], uploads, firstReadAt: "2026-09-30T20:00:00Z", movesNotified: false, now: NOW });
  assert.equal(line.stage, "agreed");
  assert.equal(line.call.past, true);
  assert.deepEqual(line.files.in, ["shopify_orders"], "a file that failed is not in");
  assert.equal(line.files.last_upload_at, "2026-09-30T00:00:00Z");
  assert.equal(line.first_read.published_at, "2026-09-30T20:00:00.000Z");
  assert.deepEqual(line.proving_month, { start: "2026-10-01", end: "2026-10-31" });
  assert.deepEqual(line.move_notices, { first: true, next_pass: "2026-10-05" });
  const later = statusLine({ client: { platform: "shopify", status: "active", retainer_started_at: "2026-10-01" },
    bookings: [], uploads: [], movesNotified: true, now: NOW });
  assert.equal(later.move_notices.first, false);
});

test("after a no, nothing is promised: no first read to wait for, no Proving Month", () => {
  for (const status of ["declined", "churned"]) {
    const line = statusLine({ client: { platform: "both", status, retainer_started_at: "2026-10-01" },
      bookings: [booking("2026-09-30T16:00:00Z")], uploads: [], now: NOW });
    assert.equal(line.first_read, null);
    assert.equal(line.proving_month, null);
    assert.equal(line.move_notices, null);
    assert.equal(line.files.of, 4, "a two-platform client's core set is both platforms'");
  }
  assert.deepEqual(coreSet("both"), [...CORE.amazon, ...CORE.shopify]);
  assert.deepEqual(coreSet(undefined), CORE.amazon);
});

test("intakeView reads one client, and a table that is missing degrades to nothing known", async () => {
  const db = fakeDb({
    clients: [{ id: "c1", platform: "amazon", status: "pending" }, { id: "c2", platform: "shopify", status: "active" }],
    uploads: [
      { id: "u1", client_id: "c1", report_type: "sku_economics", status: "parsed", row_count: 120, original_filename: "s.csv",
        period_start: "2026-09-01", period_end: "2026-09-30", uploaded_at: "2026-09-30T10:00:00Z" },
      { id: "u2", client_id: "c1", report_type: "cogs", status: "pending" },
      { id: "u3", client_id: "c2", report_type: "shopify_orders", status: "parsed", row_count: 5 },
    ],
    bookings: [{ client_id: "c1", ...booking("2026-10-02T16:00:00Z") }],
    briefings: [{ client_id: "c2", issue_number: 1, created_at: "2026-09-20T00:00:00Z" }],
    directives: [],
  });
  const view = await intakeView(db, "c1", NOW);
  assert.equal(view.platform, "amazon");
  assert.deepEqual(view.uploads.map((u) => u.id), ["u1"], "only this client's files, and none never confirmed");
  assert.equal(view.cards.sku_economics.status, "parsed");
  assert.equal(view.status.files.count, 1);
  assert.equal(view.status.first_read.published_at, null, "another client's Issue 001 is not this client's");

  const broken = fakeDb({ clients: [{ id: "c1", platform: "shopify", status: "pending" }] }, { broken: ["uploads", "bookings", "briefings", "directives"] });
  const bare = await intakeView(broken, "c1", NOW);
  assert.equal(bare.platform, "shopify");
  assert.deepEqual(bare.uploads, []);
  assert.equal(bare.status.call, null);
});

// ── the dispatch ─────────────────────────────────────────────────────────────

test("files landing wake the operator only when the token and repo are set, and never throw", async () => {
  const calls = [];
  const ok = async (url, init) => { calls.push({ url, init }); return { status: 204 }; };
  assert.deepEqual(await dispatchOperator({}, ok), { dispatched: false, reason: "not configured" });
  assert.deepEqual(await dispatchOperator({ GITHUB_DISPATCH_TOKEN: "t" }, ok), { dispatched: false, reason: "not configured" });
  assert.equal(calls.length, 0, "nothing is called when it is not configured");

  const env = { GITHUB_DISPATCH_TOKEN: "ghp_x", GITHUB_DISPATCH_REPO: "anderlecht-debug/HubriconB2B" };
  assert.deepEqual(await dispatchOperator(env, ok), { dispatched: true });
  assert.equal(calls[0].url, "https://api.github.com/repos/anderlecht-debug/HubriconB2B/actions/workflows/operator.yml/dispatches");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers.authorization, "Bearer ghp_x");
  assert.deepEqual(JSON.parse(calls[0].init.body), { ref: "main" });

  assert.deepEqual(await dispatchOperator(env, async () => ({ status: 403 })), { dispatched: false, reason: "GitHub 403" });
  assert.deepEqual(await dispatchOperator(env, async () => { throw new Error("timeout"); }), { dispatched: false, reason: "timeout" });
  assert.equal((await dispatchOperator({ ...env, GITHUB_DISPATCH_REPO: "x/y/../z" }, ok)).dispatched, false);

  // the workflow it names can be dispatched
  const yml = readFileSync(new URL("../.github/workflows/operator.yml", import.meta.url), "utf8");
  assert.match(yml, /^\s+workflow_dispatch:/m);
});

test("the API serves the view and dispatches only after files are confirmed", () => {
  const api = readFileSync(new URL("../api/intake.js", import.meta.url), "utf8");
  assert.match(api, /import \{ dispatchOperator, intakeView \} from "\.\.\/lib\/intake\.js"/);
  const complete = api.slice(api.indexOf('body.action === "complete"'));
  assert.ok(complete.indexOf("dispatchOperator(") > complete.indexOf("completed.push"), "dispatch follows the storage check");
  assert.match(complete, /if \(completed\.length\)/);
});
