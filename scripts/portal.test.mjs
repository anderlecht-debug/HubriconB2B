// The client's Profit Record (portal.html), checked without a browser.
//
// The page keeps its arithmetic and its sentences in one block, between
// `/* portal:pure` and `/* /portal:pure */`: no DOM, no network, no clock but the
// one handed in. This file runs that block in node:vm against fixtures, so each
// number on the scoreboard and each sentence about money has a test saying why
// it is true. The rest is read as text: what the page must never say, the one
// printed page, and the migration the portal writes through.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const root = new URL("../", import.meta.url);
const read = (f) => readFileSync(new URL(f, root), "utf8");
const html = read("portal.html");
const script = html.slice(html.indexOf("<script>"), html.lastIndexOf("</script>"));
const migration = read("supabase/migrations/20261001000006_portal_consents.sql");

function pure() {
  const start = html.indexOf("/* portal:pure");
  const end = html.indexOf("/* /portal:pure */");
  assert.ok(start > 0 && end > start, "portal.html keeps its arithmetic between the portal:pure markers");
  return vm.runInNewContext(`${html.slice(start, end)}\n;P`, { PORTAL_LOCALE: "en-US" });
}
const P = pure();
const at = (y, m, d, h = 12) => new Date(y, m - 1, d, h);          // local noon: a calendar day, wherever the test runs
const strip = (s) => String(s).replace(/<[^>]+>/g, "");
// values made inside the vm carry its own Array and Object: compare them as data
const same = (actual, expected, message) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, message);

const row = (o) => ({ channel: "amazon", fee_usd: 6000, disputed_usd: 0, free: false, moves: [], ...o });
const JUN = { month_index: 0, month_start: "2026-06-03", month_end: "2026-07-02", free: true };
const JUL = { month_index: 1, month_start: "2026-07-03", month_end: "2026-08-02" };
const AUG = { month_index: 2, month_start: "2026-08-03", month_end: "2026-09-02" };
const agreed = { id: "c1", status: "pending", retainer_started_at: "2026-06-03T15:00:00Z" };
const mv = (directive_id, usd, attribution, kind, verdict = "measured") => ({ directive_id, usd, attribution, kind, verdict });

// ── proven since day one: one number, one basis at a time ────────────────────

test("proven is every month on the Record after disputes, all channels, once a month exists", () => {
  const months = P.monthsOf([
    row({ ...JUN, attributed_usd: 2900 }),
    row({ ...JUL, attributed_usd: 5000 }),
    row({ ...JUL, channel: "shopify", attributed_usd: 2000, disputed_usd: 500 }),
  ]);
  assert.equal(months.length, 2);
  assert.equal(months[1].total, 6500);
  const proven = P.provenOf(months, { value_total: 99999 }, []);
  same({ ...proven }, { basis: "record", value: 9400 });
  assert.equal(P.provenLabel(proven, agreed, "agreed", at(2026, 9, 1)), "Proven on your Profit Record since day one");
});

test("before the first month closes, the number is what is measured so far, and says when the month closes", () => {
  const proven = P.provenOf([], { value_total: 1234 }, []);
  same({ ...proven }, { basis: "measured", value: 1234 });
  assert.equal(P.provenLabel(proven, agreed, "agreed", at(2026, 6, 20)), "Measured so far · your first month closes Jul 2");
  assert.equal(P.provenLabel(proven, agreed, "agreed", at(2026, 7, 5)), "Measured so far · your first month closed Jul 2");
  // no chart pack yet: the measured moves themselves
  const fromMoves = P.provenOf([], null, [{ measured_at: "2026-07-01", measured_impact_usd: 400 }, { measured_impact_usd: 900 }]);
  assert.equal(fromMoves.value, 400);
});

test("the number ticks up only from a number of the same kind; a basis switch or a dispute is set, never animated", () => {
  assert.equal(P.tickPlan(null, { basis: "record", value: 10 }).animate, false);
  assert.equal(P.tickPlan({ basis: "measured", value: 9000 }, { basis: "record", value: 4000 }).animate, false);
  assert.equal(P.tickPlan({ basis: "measured", value: 100 }, { basis: "record", value: 4000 }).animate, false);
  assert.equal(P.tickPlan({ basis: "record", value: 9000 }, { basis: "record", value: 8600 }).animate, false);
  same({ ...P.tickPlan({ basis: "record", value: 8000 }, { basis: "record", value: 9400 }) }, { animate: true, from: 8000 });
  assert.match(script, /P\.tickPlan\(prev, proven\)/, "showProven decides through tickPlan");
  assert.doesNotMatch(html, /<section[^>]*id="score"[^>]*aria-live/, "the count-up is not read out frame by frame");
  assert.match(html, /id="score-sr" aria-live="polite"/);
});

// ── the month table reads the invoice, never assumes one ─────────────────────

test("each month's outcome is what became of its invoice", () => {
  const [jun, jul, aug] = P.monthsOf([row({ ...JUN, attributed_usd: 2900 }), row({ ...JUL, attributed_usd: 7300 }),
    row({ ...AUG, attributed_usd: 5030 })]);
  const say = (m, inv) => P.outcomeText(m, P.outcomeOf(m, inv));
  assert.equal(say(jun, null), "Free: the Proving Month");
  assert.equal(say(jul, null), "Cleared · billing not switched on yet");
  assert.equal(say(jul, { status: "open", issued_at: "2026-08-10T15:00:00" }), "Cleared · sent Aug 10");
  assert.equal(say(jul, { status: "paid", paid_at: "2026-08-14T15:00:00" }), "Cleared · paid Aug 14");
  assert.equal(say(jul, { status: "draft" }), "Cleared · invoice not sent yet");
  assert.equal(say(aug, null), "Under the fee: free · no invoice");
  assert.equal(say(aug, { status: "void", voided_at: "2026-09-10" }), "Under the fee: free · voided unsent");
  assert.equal(say(aug, { status: "paid", refunded_usd: 6000 }), "Under the fee: free · refunded $6,000");
  const disputed = P.monthsOf([row({ ...AUG, attributed_usd: 7000, disputed_usd: 1500 })])[0];
  assert.equal(say(disputed, { status: "void" }), "Under the fee: free · voided", "a month a dispute took under may have been sent");
  assert.equal(say(disputed, { status: "open", issued_at: "2026-09-10T15:00:00" }), "Under the fee after a dispute · sent Sep 10");
});

test("the sentence under the number says 'our bill' only when a bill was sent", () => {
  const jul = P.monthsOf([row({ ...JUL, attributed_usd: 7300 })])[0];
  const none = P.monthSentence(jul, P.outcomeOf(jul, null));
  assert.doesNotMatch(none, /Our bill/);
  assert.match(none, /Billing is not switched on yet, so no invoice exists for it\./);
  const sent = strip(P.monthSentence(jul, P.outcomeOf(jul, { status: "open", issued_at: "2026-08-10T15:00:00" })));
  assert.equal(sent, "Jul 3 – Aug 2: your Record measured $7,300. Our bill for it: $6,000, sent Aug 10. You are $1,300 up on the month.");
  const jun = P.monthsOf([row({ ...JUN, attributed_usd: 2900 })])[0];
  assert.match(P.monthSentence(jun, P.outcomeOf(jun, null)), /That was your Proving Month: free, whatever it measured\./);
  assert.doesNotMatch(script, /this is your Proving Month/, "no 'this is your Proving Month' after it has ended");
});

test("an invoice belongs to the month the gate judged, or to the month it bills in arrears", () => {
  const sched = P.schedule("2026-06-03T15:00:00Z", at(2026, 10, 1));
  same(sched.map((m) => m.index), [0, 1, 2, 3]);
  const jul = { index: 1 }, aug = { index: 2 };
  const judged = { gate_month_index: 1, status: "paid", issued_at: "2026-08-10" };
  const unjudged = { gate_month_index: null, status: "draft", period_start: "2026-09-03", issued_at: "2026-09-03" };
  assert.equal(P.invoiceFor(jul, [judged, unjudged], sched), judged);
  assert.equal(P.invoiceFor(aug, [judged, unjudged], sched), unjudged);
  assert.equal(P.invoiceFor({ index: 0 }, [judged, unjudged], sched), null);
  assert.equal(P.billedTotal([{ status: "paid", amount_due: 6000 }, { status: "open", amount_due: 6000, refunded_usd: 6000 },
    { status: "void", amount_due: 6000 }, { status: "draft", amount_due: 6000 }]), 6000);
});

// ── where the client stands: nothing assumes a yes before one is given ───────

test("the stage is read the way the engine reads it (lifecycle.stage)", () => {
  const now = at(2026, 10, 1);
  assert.equal(P.stageOf({ status: "pending" }, "2026-10-06T15:00:00Z", now), "booked");
  assert.equal(P.stageOf({ status: "pending" }, null, now), "booked");
  assert.equal(P.stageOf({ status: "pending" }, "2026-09-28T15:00:00Z", now), "called");
  assert.equal(P.stageOf({ status: "pending", retainer_started_at: "2026-09-29" }, null, now), "agreed");
  assert.equal(P.stageOf({ status: "active" }, null, now), "agreed");
  assert.equal(P.stageOf({ status: "past_due" }, null, now), "agreed");
  assert.equal(P.stageOf({ status: "declined", retainer_started_at: null }, null, now), "declined");
  assert.equal(P.stageOf({ status: "churned", retainer_started_at: "2026-06-03" }, null, now), "churned");
  assert.equal(P.provenLabel({ basis: "measured", value: 0 }, { status: "pending" }, "booked", now), "Your Profit Record");
  // the copy before a yes is about the call and the yes, never a month that has not begun
  assert.match(script, /Your call is \$\{P\.fwhen\(when\)\}\. Your Proving Month starts the day you say yes after the call/);
  assert.match(script, /"Client since"|Client since \$\{fmonth\(c\.client\.retainer_started_at\)\}/);
  assert.doesNotMatch(script, /fmonth\(client\.created_at\)/, "'Client since' is the yes, not the booking");
});

// ── the heartbeat ─────────────────────────────────────────────────────────────

test("the next check is the next Monday 11:00 UTC, and only for clients the sweep visits", () => {
  const utc = (s) => new Date(s);
  assert.equal(P.nextCheck(utc("2026-10-01T09:00:00Z")).toISOString(), "2026-10-05T11:00:00.000Z");
  assert.equal(P.nextCheck(utc("2026-10-05T10:59:00Z")).toISOString(), "2026-10-05T11:00:00.000Z");
  assert.equal(P.nextCheck(utc("2026-10-05T11:00:00Z")).toISOString(), "2026-10-12T11:00:00.000Z");
  assert.equal(P.nextCheck(utc("2026-10-04T23:00:00Z")).toISOString(), "2026-10-05T11:00:00.000Z");
  const now = utc("2026-10-01T15:00:00Z");
  assert.match(P.heartbeat("2026-09-28T11:42:00Z", { status: "active" }, now), /^Last checked 3 days ago · next check \w+day, Oct \d+$/);
  assert.equal(P.heartbeat("2026-09-28T11:42:00Z", { status: "past_due" }, now), "Last checked 3 days ago");
  assert.equal(P.heartbeat(null, { status: "active" }, now), "");
  assert.doesNotMatch(script, /within the hour/i);
  assert.doesNotMatch(script, /id="asof"|#asof/, "no 'as of' the browser's own date");
  assert.match(script, /addEventListener\("visibilitychange"/);
  assert.match(script, /REFRESH_MS = 5 \* 60 \* 1000/);
});

// ── the save and the forward line ────────────────────────────────────────────

const july = () => P.monthsOf([row({ ...JUN, attributed_usd: 2900 }), row({ ...JUL, attributed_usd: 7342.5, moves: [
  mv("d1", 2400, "isolated", "ad_bleed_terms"), mv("d3", 980, "attributable", "price_step"),
  mv("d4", 1342.5, "direct", "recovery_filing"), mv("d5", 0, "none", "campaign_trim", "closed")] })]);

test("the save counts leaks still held shut in the latest month, never a one-off reimbursement", () => {
  assert.equal(strip(P.heldLine(july())), "2 leaks held shut · $3,380 held in Jul 3 – Aug 2");
  const disputed = P.monthsOf([row({ ...JUL, attributed_usd: 3380, disputed_usd: 3000, moves: [mv("d1", 2400, "isolated"), mv("d3", 980, "attributable")] })]);
  assert.equal(strip(P.heldLine(disputed)), "2 leaks held shut · $380 held in Jul 3 – Aug 2", "never above the month after disputes");
  assert.equal(P.heldLine([]), null);
});

test("one forward line, for a client who said yes, after a closed month, labelled as a straight line", () => {
  const months = july();
  const proven = P.provenOf(months, null, []);
  const now = at(2026, 10, 1);
  assert.equal(P.monthsLeftInYear(now), 3);
  const f = P.forwardLine("agreed", months, proven, now);
  assert.equal(f.rate, 3380);
  assert.equal(strip(f.html), "By December 31, 2026, at this rate: $20,383.A straight line through what is already measured. Not a forecast, not a promise.");
  assert.equal(P.FORWARD_NOTE, "A straight line through what is already measured. Not a forecast, not a promise.");
  for (const stage of ["booked", "called", "declined", "churned"]) assert.equal(P.forwardLine(stage, months, proven, now), null, stage);
  assert.equal(P.forwardLine("agreed", [], { basis: "measured", value: 5000 }, now), null);
});

// ── the scary moment ─────────────────────────────────────────────────────────

test("the alert under the score is the freshest warning from the latest sweep, or nothing", () => {
  const packs = [{ run_id: "r9", created_at: "2026-09-28T11:42:00Z" }, { run_id: "r9b", created_at: "2026-09-28T11:30:00Z" },
    { run_id: "r8", created_at: "2026-09-21T11:40:00Z" }];
  const alerts = [
    { id: "old", run_id: "r8", severity: "critical", created_at: "2026-09-21T11:39:00Z" },
    { id: "info", run_id: "r9", severity: "info", created_at: "2026-09-28T11:41:00Z" },
    { id: "warn", run_id: "r9", severity: "warning", created_at: "2026-09-28T11:40:00Z" },
    { id: "warn2", run_id: "r9b", severity: "warning", created_at: "2026-09-28T11:29:00Z" },
  ];
  assert.equal(P.freshAlert(alerts, packs).id, "warn");
  assert.equal(P.freshAlert([...alerts, { id: "crit", run_id: "r9b", severity: "critical", created_at: "2026-09-28T11:28:00Z" }], packs).id, "crit");
  assert.equal(P.freshAlert([...alerts, { id: "net", run_id: null, severity: "warning", created_at: "2026-09-30T08:00:00Z" }], packs).id, "net");
  assert.equal(P.freshAlert(alerts.filter((a) => a.id === "old" || a.id === "info"), packs), null);
  assert.equal(P.freshAlert(alerts, []), null);
  for (const gone of ["escalated — action issued", "flagged at last sweep", "already has a reorder waiting"]) {
    assert.ok(!html.includes(gone), `"${gone}" is back`);
  }
});

// ── every leak named, and sealed ─────────────────────────────────────────────

test("each leak is named on the product as the client names it", () => {
  const names = { "KT-17": "1.7L Gooseneck Kettle" };
  assert.equal(P.leakName({ kind: "fee_anomaly", evidence: { sku: "KT-17" } }, names), "A fee change on 1.7L Gooseneck Kettle");
  assert.equal(P.leakName({ kind: "price_step", evidence: { item_id: "PO-2" } }, names), "Price on PO-2");
  assert.equal(P.leakName({ kind: "ad_bleed_terms", evidence: { campaign_name: "Auto — Kettles" } }, names), "Search terms spending with no sales in Auto — Kettles");
  assert.equal(P.leakName({ kind: "fee_anomaly", evidence: { scope: "fee_type", item_id: "fba_fee_per_unit" } }, names), "A fee change on fba fee per unit");
  assert.equal(P.leakName({ kind: "something_new", action_text: "Do the thing." }, names), "Do the thing.");
});

test("moves fall into sealed and holding, paid once, called, stopped holding, missed and not made", () => {
  const months = P.monthsOf([row({ ...AUG, attributed_usd: 2400, moves: [mv("d1", 2400, "isolated"), mv("d2", 0, "isolated", "fee_anomaly", "closed")] })]);
  const d = (id, o) => ({ id, status: "done", issued_at: "2026-07-01", ...o });
  const { groups } = P.groupMoves([
    d("d1", { measured_at: "2026-07-20", measured_impact_usd: 2400, attribution: "isolated" }),
    d("d2", { measured_at: "2026-07-21", measured_impact_usd: 1650, attribution: "isolated" }),
    d("d4", { measured_at: "2026-07-22", measured_impact_usd: 1342.5, attribution: "direct", kind: "recovery_filing" }),
    d("d5", { measured_at: "2026-07-23", measured_impact_usd: 0, status: "closed" }),
    d("d6", { executed_at: "2026-09-24" }),
    d("d7", { status: "issued" }),
    d("d8", { status: "declined" }),
    d("d9", { status: "draft" }),
  ], months);
  const ids = Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.map((x) => x.id)]));
  same(ids, { holding: ["d1"], once: ["d4"], called: ["d6", "d7"], stopped: ["d2"], missed: ["d5"], notMade: ["d8"] });
  for (const label of ["Sealed and holding", "Called, not yet measured", "Missed, shown at what it earned"]) assert.ok(script.includes(`"${label}"`), label);
  assert.ok(!script.includes('["Measured", sealed'), "the old 'Measured' group label is gone");
});

test("the seal beside each move is the promise's first twelve characters; the head reads in eight groups of eight", () => {
  const leaf = "3f9a1c0b2e7d" + "a".repeat(52);
  const seals = P.sealsByMove([
    { entry: "called", directive_id: "d1", leaf, sealed: "late" },
    { entry: "measured", directive_id: "d1", leaf: "f".repeat(64) },
    { entry: "called", directive_id: "d2", leaf: "8c01e4d27b55" + "b".repeat(52), sealed: "at_issue" },
  ]);
  same({ ...seals.d1 }, { short: "3f9a1c0b2e7d", late: true });
  assert.equal(strip(P.sealHtml(seals.d1)), " · seal 3f9a1c0b2e7d · sealed late");
  assert.equal(strip(P.sealHtml(seals.d2)), " · seal 8c01e4d27b55");
  assert.match(P.sealHtml(seals.d2), /class="hash"/);
  const head = "9d4e0c7a1b2f3e8d5c6a7b9e0f1d2c3b4a5e6f708192a3b4c5d6e7f8091a2b3c";
  assert.equal(P.grouped(head), "9d4e0c7a 1b2f3e8d 5c6a7b9e 0f1d2c3b 4a5e6f70 8192a3b4 c5d6e7f8 091a2b3c");
  assert.match(script, /Called \$\{fdate\(d\.issued_at\)\}\$\{P\.sealHtml\(seal\)\}/);
});

// ── the one page ─────────────────────────────────────────────────────────────

test("the printed page carries the Record, its method and the head, and nothing unproven", () => {
  const months = july();
  const head = "9d4e0c7a1b2f3e8d5c6a7b9e0f1d2c3b4a5e6f708192a3b4c5d6e7f8091a2b3c";
  const out = P.printHtml({
    company: "Northwind Kitchen", now: at(2026, 10, 1), lastAt: "2026-09-28T11:42:00Z",
    label: "Proven on your Profit Record since day one", proven: P.provenOf(months, null, []), months,
    outcome: (m) => P.outcomeText(m, P.outcomeOf(m, null)),
    sealed: [{ id: "d1", kind: "ad_bleed_terms", evidence: {}, attribution: "isolated", measured_impact_usd: 2400 }],
    seals: { d1: { short: "3f9a1c0b2e7d", late: false } }, names: {}, head,
  });
  const text = strip(out);
  assert.ok(text.includes("Northwind Kitchen"));
  assert.ok(text.includes("Proven on your Profit Record since day one"));
  assert.ok(text.includes("$10,243"));
  assert.ok(text.includes("Cleared · billing not switched on yet"));
  assert.ok(text.includes("Search terms spending with no sales") && text.includes("isolated") && text.includes("3f9a1c0b2e7d"));
  assert.ok(text.endsWith("Kept by Hubricon · Paid on proof · Record head 9d4e0c7a 1b2f3e8d 5c6a7b9e 0f1d2c3b 4a5e6f70 8192a3b4 c5d6e7f8 091a2b3c · Check this Record's export at hubricon.com/verify"));
  assert.equal((out.match(/<li>/g) || []).length, 3, "a three-line method");
  for (const never of [P.FORWARD_NOTE, "at this rate", "found, not yet measured", "forecast", "expected"]) {
    assert.ok(!text.includes(never), `the printed page says "${never}"`);
  }
  assert.match(html, /id="print"[^>]*>Print one page</);
  assert.match(html, /@media print \{[\s\S]*#app > \*:not\(#print-page\) \{ display: none !important; \}/);
});

test("a hash is set in Inter: slashed zero, tabular, no monospace anywhere", () => {
  assert.doesNotMatch(html, /monospace/i);
  const rule = html.match(/\.hash \{[^}]*\}/)[0];
  assert.match(rule, /font-family: var\(--font\)/);
  assert.match(rule, /font-size: var\(--t-12\)/);
  assert.match(rule, /font-feature-settings: "zero"/);
  assert.match(rule, /font-variant-numeric: tabular-nums/);
});

// ── yours ────────────────────────────────────────────────────────────────────

test("each permission the terms name, with its state; withdrawal is one click where the RPC exists", () => {
  const caps = { consent_kinds: ["anonymised_results", "testimonial", "calibration", "network"], withdraw_only: ["named_results"] };
  const rows = P.consentRows([
    { kind: "anonymised_results", granted: true, answered_at: "2026-08-11T09:00:00" },
    { kind: "testimonial", granted: null },
    { kind: "calibration", granted: false, answered_at: "2026-08-11T09:00:00" },
  ], caps);
  same(rows.map((r) => r.kind), ["anonymised_results", "testimonial", "calibration", "network"]);
  same(rows.map((r) => r.state), ["Given Aug 11", "Asked, not answered", "Not given · Aug 11", "Not asked yet"]);
  same(rows.map((r) => r.canWithdraw), [true, false, false, false]);
  assert.ok(P.consentRows([{ kind: "named_results", granted: true }], caps).find((r) => r.kind === "named_results").canWithdraw);
  assert.ok(P.consentRows([{ kind: "anonymised_results", granted: true }], null).every((r) => !r.canWithdraw), "no RPC, no button");
  assert.equal(P.CHANGE_BY_EMAIL, "Reply to any email from us to change this.");
  assert.equal(P.referralUrl("nk7Qx2aB"), "https://www.hubricon.com/?ref=nk7Qx2aB");
  assert.equal(P.referralUrl("<script>"), null);
  assert.match(script, /rpc\("my_portal", \{ p_client_id: client\.id \}\)/);
  assert.match(script, /\/rest\/v1\/rpc\/set_my_consent/);
});

test("the migration lets a member withdraw only what the terms name, and give back only what was asked", () => {
  assert.match(migration, /create or replace function public\.set_my_consent\(p_client_id uuid, p_kind text, p_granted boolean\)/);
  assert.match(migration, /security definer\s+set search_path = ''/);
  assert.match(migration, /from public\.client_users u\s+where u\.user_id = \(select auth\.uid\(\)\) and u\.client_id = p_client_id/);
  assert.match(migration, /p_kind in \('anonymised_results', 'testimonial', 'calibration', 'network'\)/);
  assert.match(migration, /p_kind = 'named_results' and p_granted is false/);
  assert.match(migration, /revoke execute on function public\.set_my_consent\(uuid, text, boolean\) from public, anon;/);
  assert.match(migration, /revoke execute on function public\.my_portal\(uuid\) from public, anon;/);
  // the kinds the RPC accepts are the /say page's, less the one the terms do not name
  const say = read("api/consent.js").match(/const KINDS = \[([^\]]+)\]/)[1].match(/"([a-z_]+)"/g).map((s) => s.slice(1, -1));
  same(say.filter((k) => k !== "named_results").sort(), ["anonymised_results", "calibration", "network", "testimonial"]);
});

// ── never two workspaces on one page; never a dead link ──────────────────────

test("every table the page reads is scoped to the workspace on screen", () => {
  const load = script.slice(script.indexOf("async function loadNow"), script.indexOf("/* ── freshness"));
  const reads = [...load.matchAll(/\/rest\/v1\/(?!rpc\/)([a-z_]+)\?([^`]*)`/g)].filter(([, t]) => t !== "clients");
  assert.ok(reads.length >= 12, `found ${reads.length} reads`);
  for (const [, table, query] of reads) assert.match(query, /\$\{f\}/, `${table} is read without the workspace filter`);
  assert.doesNotMatch(script, /clients\[0\];\s*\n\s*\$\("#company"\)/);
  assert.doesNotMatch(html, /id="export-link"[^>]*href="#"/);
  assert.match(html, /<button class="link" id="export-link" type="button">/);
  assert.match(script, /mailto:\$\{EXPORT_EMAIL\}/);
});

// ── the words ────────────────────────────────────────────────────────────────

test("no retired word and no untrue line in what the client reads", () => {
  const visible = html.replace(/<script>[\s\S]*?<\/script>/g, "").replace(/<style>[\s\S]*?<\/style>/g, "")
    .replace(/<!--[\s\S]*?-->/g, "").replace(/<[^>]+>/g, " ");
  const months = july();
  const rendered = [
    ...months.map((m) => P.monthSentence(m, P.outcomeOf(m, null))),
    ...months.map((m) => P.outcomeText(m, P.outcomeOf(m, null))),
    P.heldLine(months), P.forwardLine("agreed", months, P.provenOf(months, null, []), at(2026, 10, 1)).html,
    ...P.consentRows([], null).flatMap((r) => [r.name, r.note, r.state]),
    ...["ad_bleed_terms", "campaign_trim", "price_step", "markdown", "sku_exit", "recovery_filing", "inventory_reorder"]
      .map((kind) => P.leakName({ kind, evidence: { sku: "X" } }, {})),
  ].map(strip).join("\n");
  for (const word of ["desk", "ledger", "quantitative", "retainer", "engagement", "directive", "Teardown", "three-minute brief"]) {
    const re = new RegExp(`\\b${word}\\b`, "i");
    assert.doesNotMatch(visible, re, `"${word}" in the page's text`);
    assert.doesNotMatch(rendered, re, `"${word}" in a sentence the page writes`);
  }
  for (const untrue of ["Cleared: invoiced", "negative-matched by us", "we pause it as a tracked test", "wire schedule under management", "We file, Amazon pays"]) {
    assert.ok(!html.includes(untrue), `"${untrue}" is back`);
  }
});
