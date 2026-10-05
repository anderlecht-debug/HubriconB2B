// The store study (/case-study, and the home page's proof): Hubricon's engine on a real retailer's
// published orders, called before and measured after. Held to the engine as it is today, to the
// data's licence, and to the rule that nothing published identifies a customer.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const sha = (p) => createHash("sha256").update(readFileSync(new URL(p, root))).digest("hex");
const ss = JSON.parse(read("data/store-study.json"));
const rerun = "run: cd engine && uv run --with openpyxl python scripts/store_case_study.py && cd .. && node scripts/build-pages.mjs";

test("every call was made by the engine as it is today", () => {
  for (const [file, hash] of Object.entries(ss.engine)) assert.equal(hash, sha(file), `${file} changed since the store study was run; ${rerun}`);
  const py = read("engine/scripts/store_case_study.py");
  for (const call of ["clv.run(", "clv.bgnbd_fit(", "clv.expected_repeats(", "forecast.run(", "seasonality.indices("]) assert.ok(py.includes(call), `the study calls ${call}`);
  assert.match(py, /clv\.CALIBRATION_SHARE/, "the cut-off is the engine's own rule, not a date picked after the fact");
});

test("the calls are what the data says: the engine's own verdict, and the misses kept", () => {
  const c = ss.customers;
  assert.equal(c.engine_verdict.status, "ok");
  assert.ok(Math.abs(c.engine_verdict.calibration.actual_over_predicted - c.ratio) < 1e-3, "the page's ratio is the engine's own calibration");
  assert.ok(Math.abs(c.measured / c.called - c.ratio) < 1e-3);
  assert.equal(c.path.called.length, c.path.weeks.length);
  const s = ss.slipping;
  assert.equal(s.named, s.named_came_back + s.named_did_not);
  assert.equal(s.regulars, s.named + s.steady);
  const d = ss.demand;
  assert.equal(d.quarter.called, d.calls.reduce((t, x) => t + x.called, 0));
  assert.equal(d.quarter.measured, d.calls.reduce((t, x) => t + x.measured, 0));
  for (const x of d.calls) assert.ok(x.called_on < `${x.month}-01`, `${x.month} was called before it began`);
  assert.match(ss.not_published, /elasticity/, "what was not published, and why, is on file");
});

test("the source is cited as its licence asks, and nothing names a customer", () => {
  assert.equal(ss.source.licence, "CC BY 4.0");
  assert.match(ss.source.doi, /10\.24432\/C5CG6D/);
  assert.equal(ss.label, "Modeled on published data. Not a client. Not a result.");
  const raw = read("data/store-study.json");
  assert.doesNotMatch(raw, /Customer ID|customer_key|"cust"|\b1[2-8]\d{3}\.0\b/, "no customer number reaches a published file");
  const page = read("case-study.html");
  assert.match(page, /CC BY 4\.0/);
  assert.match(page, /Chen, D\., 2012/);
});
