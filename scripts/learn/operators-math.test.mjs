// The Operator's Math (/learn/operators-math), held to the same rules as the other courses: every
// figure and the spreadsheet were computed and checked by Hubricon's engine (scripts/learn/
// operators_math.py: models/clv.py, models/ad_efficiency.py, cold/priors.py) and are re-checked
// whenever those move; the examples are labelled invented wherever they show; the reader's own
// Orders export is counted in the browser exactly as the Python reference counts it, and never
// sent; nothing inside a lesson sells.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { COURSES } from "../../lib/learn.js";
import * as call from "../../lib/call.js";
import { ordersFromRows, customerCurve, paybackMonth } from "../../assets/cohorts.mjs";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const sha = (p) => createHash("sha256").update(readFileSync(new URL(p, root))).digest("hex");
const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const page = read("learn/operators-math.html");
const rerun = "run: cd engine && uv run --with openpyxl python ../scripts/learn/operators_math.py --publish";

test("the figures and the spreadsheet were computed and checked by the engine as it is today", () => {
  const figs = JSON.parse(read("data/learn-operators-math.json"));
  for (const [file, hash] of Object.entries(figs.sources)) assert.equal(hash, sha(file), `${file} changed since the course's figures were computed; ${rerun}`);
  const stamp = JSON.parse(read("scripts/learn/operators-math.stamp.json"));
  for (const [file, hash] of Object.entries(stamp.sources_sha256)) assert.equal(hash, sha(file), `${file} changed since the spreadsheet was verified; ${rerun}`);
  assert.equal(stamp.file_sha256, sha(stamp.file), `the template changed without being re-verified; ${rerun}`);
  const py = read("scripts/learn/operators_math.py");
  for (const call_ of ["clv.run(", "ad_efficiency.run(", "priors.payments_fee(", "clv.expected_repeats("]) assert.ok(py.includes(call_), `the figures come from ${call_}`);
});

test("registered where a sign-up and the library look for it, lesson for lesson", () => {
  assert.equal(COURSES["operators-math"].path, "/learn/operators-math");
  assert.match(page, /<body class="course-page" data-course="operators-math">/);
  const lib = JSON.parse(read("data/library.json")).courses.find((x) => x.slug === "operators-math");
  assert.equal(lib.status, "live");
  const ids = [...page.matchAll(/<article class="lesson" id="([^"]+)"/g)].map(([, id]) => id);
  assert.deepEqual(lib.lessons.map((l) => l.id), ids);
  assert.deepEqual([...page.matchAll(/<li><a href="#([^"]+)">/g)].map(([, id]) => id), ids);
});

test("the examples say they are invented, the engine's estimate stands beside the truth, and no figure in a lesson is typed", () => {
  for (const [f] of page.matchAll(/<figure[\s\S]*?<\/figure>/g)) assert.match(f, /An invented (store|campaign) · Not a client · Not a result/);
  for (const [w] of page.matchAll(/<div class="worked">[\s\S]*?<\/div>/g)) assert.match(text(w), /invented/i);
  assert.match(page, /data-fill="learn_om_repeats_truth"/, "the simulation's truth is printed beside the engine's estimate");
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  const prose = lessons.replace(/<!-- build:[\s\S]*?<!-- \/build:[^>]*-->/g, "").replace(/<div class="check">[\s\S]*?<\/ol>\s*<\/div>/g, "")
    .replace(/<span[^>]*data-fill[^>]*>[^<]*<\/span>/g, "FILL");
  for (const [m] of text(prose).matchAll(/\$\d+(?:,\d{3})*(?:\.\d+)?/g)) assert.fail(`${m} is typed into a lesson; it must come from data/learn-operators-math.json`);
});

test("the browser counts a reader's customers exactly as the Python reference does", () => {
  const golden = JSON.parse(read("scripts/learn/operators-math.golden.json"));
  const rows = call.mapColumns(call.readTable(golden.csv), { ...call.SHOPIFY_ORDERS, email: [["email", "customeremail"], call.cleanStr] });
  const got = customerCurve(ordersFromRows(rows, call.isoDate));
  const want = golden.expect;
  for (const k of ["customers", "came_back", "last"]) assert.equal(got[k], want[k], k);
  for (const k of ["came_back_share", "first_value", "repeat_value"]) assert.ok(Math.abs(got[k] - want[k]) < 1e-6, `${k}: ${got[k]} vs ${want[k]}`);
  assert.equal(got.curve.length, want.curve.length);
  got.curve.forEach((r, i) => {
    const w = want.curve[i];
    assert.equal(r.customers, w.customers, `month ${r.month} customers`);
    assert.ok(Math.abs(r.repeats - w.repeats) < 1e-6 && Math.abs(r.repeat_revenue - w.repeat_revenue) < 1e-6, `month ${r.month}`);
  });
  assert.equal(paybackMonth(got, golden.margin_rate, golden.cac), golden.payback_month);
});

test("the Orders export is read in the browser by /call's own reading, and nothing is sent", () => {
  const js = read("assets/learn-operators-math.js");
  assert.match(js, /import \* as call from "\/lib\/call\.js"/);
  assert.match(js, /from "\/assets\/cohorts\.mjs"/);
  assert.match(js, /new FileReader\(\)/);
  assert.doesNotMatch(js + read("assets/cohorts.mjs"), /fetch\(|XMLHttpRequest|sendBeacon|navigator\.sendBeacon/, "nothing leaves the page");
  assert.match(page, /Nothing is uploaded/);
});

test("nothing inside a lesson sells", () => {
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  assert.doesNotMatch(lessons, /href="\/apply"|\$6,000|Book your call|Managed Profit/);
});
