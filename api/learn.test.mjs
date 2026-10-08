import { test } from "node:test";
import assert from "node:assert/strict";
import { handle, routeFor, composeLearnEmail } from "./learn.js";
import { SlidingWindow } from "../lib/ratelimit.js";

const answers = { channel: "Amazon", rev: "$5M–$20M", model: "Private label", skus: "10–50 SKUs" };

function req(body, headers = {}) {
  return new Request("https://www.hubricon.com/api/learn", {
    method: "POST",
    headers: { "content-type": "application/json", "x-forwarded-for": "203.0.113.9", ...headers },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function fakeStore({ seen = false, byIp = 0 } = {}) {
  const rows = [];
  return {
    rows,
    dailyCount: async () => byIp,
    seen: async () => seen,
    record: async (row) => { rows.push(row); return { error: null }; },
  };
}

// A fresh window and no Resend key per test, so nothing leaks between them or out to the network.
const deps = (extra = {}) => ({ store: fakeStore(), window: new SlidingWindow({ limit: 6, windowMs: 60_000 }), apiKey: "", ...extra });

const resendStub = (calls, body = { id: "re_1" }) => async (url, init) => {
  calls.push({ url, body: JSON.parse(init.body) });
  return new Response(JSON.stringify(body), { status: 200 });
};

test("the route follows apply.html's fitTag, with the mixed/other door added", () => {
  assert.equal(routeFor(answers), "core");
  assert.equal(routeFor({ ...answers, rev: "Under $3M" }), "below");
  assert.equal(routeFor({ ...answers, model: "Wholesale / reseller" }), "below");
  assert.equal(routeFor({ ...answers, model: "Arbitrage", rev: "$20M+" }), "below");
  assert.equal(routeFor({ ...answers, model: "Mixed / other", rev: "Under $3M" }), "none");
  assert.equal(routeFor({ ...answers, model: "Mixed / other" }), "core");
  assert.equal(routeFor({ ...answers, rev: "" }), "none", "an unanswered form offers nothing");
});

test("a bad address, an unknown answer and broken JSON are refused before anything is stored", async () => {
  const d = deps();
  assert.equal((await handle(req({ ...answers, email: "not-an-address" }), d)).status, 400);
  assert.equal((await handle(req({ ...answers, email: "a@b.co", rev: "Loads" }), d)).status, 400);
  assert.equal((await handle(req("{not json"), d)).status, 400);
  assert.equal(d.store.rows.length, 0);
});

test("the honeypot swallows a script's submit and stores nothing", async () => {
  const d = deps();
  const res = await handle(req({ ...answers, email: "bot@example.com", website: "http://spam" }), d);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).ok, true);
  assert.equal(d.store.rows.length, 0);
});

test("core: recorded as learn_capture with its route and no prospect, and the template email carries the Teardown", async () => {
  const calls = [];
  const d = deps({ apiKey: "re_test", fetchImpl: resendStub(calls) });
  const res = await handle(req({ ...answers, email: "Ada@Example.com", first_name: "Ada" }), d);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { ok: true, route: "core", emailed: true });
  assert.equal(d.store.rows.length, 1);
  const row = d.store.rows[0];
  assert.equal(row.kind, "learn_capture");
  assert.equal(row.prospect_id, null);
  assert.equal(row.payload.email, "ada@example.com");
  assert.equal(row.payload.first_name, "Ada");
  assert.equal(row.payload.route, "core");
  assert.equal(row.payload.rev, "$5M–$20M");
  assert.equal(row.payload.emailed, true);
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].body.to, ["ada@example.com"]);
  assert.match(calls[0].body.text, /reimbursement-playbook-template\.xlsx/);
  assert.match(calls[0].body.text, /Profit Teardown/);
  assert.match(calls[0].body.text, /\/apply/);
});

test("below: the template arrives and, until Capital Position has a page, nothing is offered", async () => {
  const calls = [];
  const d = deps({ apiKey: "re_test", fetchImpl: resendStub(calls, {}) });
  const res = await handle(req({ ...answers, rev: "Under $3M", email: "b@example.com" }), d);
  assert.deepEqual(await res.json(), { ok: true, route: "below", emailed: true });
  assert.equal(d.store.rows[0].payload.route, "below");
  assert.match(calls[0].body.text, /reimbursement-playbook-template\.xlsx/);
  assert.doesNotMatch(calls[0].body.text, /Profit Teardown/);
  assert.doesNotMatch(calls[0].body.text, /\/position/);
  const withPage = composeLearnEmail({ firstName: "Bo", route: "below", positionUrl: "https://www.hubricon.com/position" });
  assert.match(withPage.text, /Capital Position/);
  assert.match(withPage.text, /hubricon\.com\/position/);
});

test("none: the template and nothing else, and without a Resend key nothing is sent", async () => {
  const d = deps();
  const res = await handle(req({ ...answers, rev: "Under $3M", model: "Mixed / other", email: "c@example.com" }), d);
  assert.deepEqual(await res.json(), { ok: true, route: "none", emailed: false });
  assert.equal(d.store.rows[0].payload.route, "none");
  assert.equal(d.store.rows[0].payload.emailed, false);
  const m = composeLearnEmail({ firstName: "Cy", route: "none" });
  assert.doesNotMatch(m.text, /Teardown|Capital Position/);
  assert.match(m.text, /reimbursement-playbook-template\.xlsx/);
});

test("a repeat address learns its route again and is neither stored nor emailed twice", async () => {
  const d = deps({ store: fakeStore({ seen: true }), apiKey: "re_test", fetchImpl: async () => { throw new Error("must not send"); } });
  const res = await handle(req({ ...answers, email: "ada@example.com" }), d);
  assert.deepEqual(await res.json(), { ok: true, route: "core", emailed: false, repeat: true });
  assert.equal(d.store.rows.length, 0);
});

test("a failed send is recorded on the row and the capture still stands", async () => {
  const d = deps({ apiKey: "re_test", fetchImpl: async () => new Response(JSON.stringify({ message: "nope" }), { status: 422 }) });
  const res = await handle(req({ ...answers, email: "d@example.com" }), d);
  assert.deepEqual(await res.json(), { ok: true, route: "core", emailed: false });
  assert.equal(d.store.rows[0].payload.email_error, "nope");
});

test("the email carries no digit: every figure lives in the template and the lessons", () => {
  for (const route of ["core", "below", "none"]) {
    const m = composeLearnEmail({ firstName: "Ada", route, positionUrl: "https://www.hubricon.com/position" });
    const prose = (m.subject + "\n" + m.text).replace(/https?:\/\/\S+/g, "");
    assert.doesNotMatch(prose, /\d/, `${route}: ${prose}`);
    assert.doesNotMatch(prose, /!/);
  }
});
