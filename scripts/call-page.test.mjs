// /call, the page used on a sales call: the prospect's reports are read in their own
// browser and nothing leaves it. No analytics, no request that could carry a file, not
// indexed, not linked from the home page, on the one design system.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = read("call.html");
const js = read("assets/call.js");

test("nothing leaves the browser: no analytics, no upload, no beacon", () => {
  assert.doesNotMatch(page, /_vercel\/insights|googletagmanager|gtag\(/, "no analytics script on /call");
  assert.doesNotMatch(page, /<form\b[^>]*action=/i, "no form posts anywhere");
  assert.doesNotMatch(js, /XMLHttpRequest|sendBeacon|method:\s*["']POST|new WebSocket|navigator\.share/);
  const fetches = [...js.matchAll(/fetch\(([^)]*)\)/g)].map(([, a]) => a.trim());
  assert.deepEqual(fetches, ['"/ratecard.json"'], "the only request is the public rate card");
  assert.match(page, /Nothing is uploaded/);
});

test("not indexed, not linked from the home page, on the design system", () => {
  assert.match(page, /<meta name="robots" content="noindex, nofollow">/);
  assert.doesNotMatch(read("index.html"), /href="\/call"/);
  assert.match(page, /href="\/assets\/hubricon\.css"/);
  assert.doesNotMatch(page.match(/<style>([\s\S]*?)<\/style>/)[1], /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, "colours belong in /assets/hubricon.css");
  assert.match(page, /family=Inter:opsz,wght@14\.\.32/);
});

test("the page says what its figures are", () => {
  assert.match(page, /not a result and not a promise/);
  assert.match(page, /the same arithmetic Hubricon's engine runs/);
  assert.match(js, /estimate/);
});
