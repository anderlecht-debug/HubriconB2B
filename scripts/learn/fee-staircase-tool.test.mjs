// The Fee Staircase on the reader's own listing and reports (assets/learn-fee-staircase.js):
// the arithmetic is /lib/fees.js and /lib/call.js, which lib/fees.test.mjs and lib/call.test.mjs
// hold to the engine; reports are read in the browser and never sent; the course reads the
// same without scripts; one printed page, only once there is something to print.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const js = read("assets/learn-fee-staircase.js");
const page = read("learn/fee-staircase.html");

test("the arithmetic is the engine-pinned library, not a second copy", () => {
  assert.match(js, /import \* as fees from "\/lib\/fees\.js";/);
  assert.match(js, /import \* as call from "\/lib\/call\.js";/);
  for (const fn of ["describeItem", "unitEconomics", "detect"]) assert.match(js, new RegExp(`fees\\.${fn}\\(`));
  for (const fn of ["parseFeePreview", "parseInventoryHealth", "analyse"]) assert.match(js, new RegExp(`call\\.${fn}\\b`));
  assert.doesNotMatch(js, /fulfilmentFee\(|\b0\.035\b|\b5\.45\b/, "no fee or rate is typed into the tool");
});

test("a report is read in the browser and nothing the reader types or drops is sent", () => {
  const fetches = [...js.matchAll(/fetch\(([^)]*)\)/g)].map(([, a]) => a.trim());
  assert.deepEqual(fetches, ['"/ratecard.json"'], "the one request is Amazon's published card");
  assert.doesNotMatch(js, /XMLHttpRequest|sendBeacon|WebSocket|FormData|\bva\(|track\(/);
  assert.match(js, /new FileReader\(\)/);
  assert.match(js, /fr\.onerror/, "a file that cannot be opened says so");
  assert.match(read("privacy.html"), /A report you drop into a course \(Fee Preview,\s+Inventory Age\) is read there and then, in your browser, and never uploaded or kept\./);
});

test("three panels where the lessons put them, hidden until the script that runs them arrives", () => {
  const lesson = (id) => page.match(new RegExp(`<article class="lesson" id="${id}"[\\s\\S]*?</article>`))[0];
  assert.match(lesson("find-the-step"), /<section class="yours" id="yours-listing" hidden/);
  assert.match(lesson("the-cliff"), /<section class="yours" id="yours-stock" hidden/);
  assert.match(lesson("every-sku"), /<section class="yours" id="yours-catalogue" hidden/);
  assert.match(page, /<section class="memo" data-yours="memo" hidden/);
  assert.match(page, /<script type="module" src="\/assets\/learn-fee-staircase\.js"><\/script>/);
  assert.match(page, /<script type="application\/json" id="fs-example">/, "the example comes from the build, the same listing lesson 3 prices");
});

test("the holiday card is named as a dated fact, never as a countdown", () => {
  assert.match(js, /Amazon's holiday card starts \$\{longDate\(peak\.effective\)\}/);
  assert.doesNotMatch(js, /days left|hurry|countdown|act now|only \d+/i);
});
