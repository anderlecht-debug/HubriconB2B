// The Shopify Margin (/learn/shopify-margin), held to the same rules as the other courses and to
// the cards it teaches: every figure and the spreadsheet were computed and checked against
// Hubricon's engine (scripts/learn/shopify_margin.py, cold/priors.py) and are re-checked whenever
// the cards move; the examples are labelled invented wherever they show; nothing inside a lesson
// sells; the Products export is read in the browser and never sent.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { COURSES } from "../../lib/learn.js";
import * as call from "../../lib/call.js";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const sha = (p) => createHash("sha256").update(readFileSync(new URL(p, root))).digest("hex");
const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const page = read("learn/shopify-margin.html");
const rerun = "run: cd engine && uv run --with openpyxl python ../scripts/learn/shopify_margin.py --publish";

test("the figures and the spreadsheet were checked against the engine's cards as they are today", () => {
  const figs = JSON.parse(read("data/learn-shopify-margin.json"));
  for (const [file, hash] of Object.entries(figs.sources)) assert.equal(hash, sha(file), `${file} changed since the course's figures were computed; ${rerun}`);
  const stamp = JSON.parse(read("scripts/learn/shopify-margin.stamp.json"));
  for (const [file, hash] of Object.entries(stamp.sources_sha256)) assert.equal(hash, sha(file), `${file} changed since the spreadsheet was verified; ${rerun}`);
  assert.equal(stamp.file_sha256, sha(stamp.file), `the template changed without being re-verified; ${rerun}`);
  assert.match(read("scripts/learn/shopify_margin.py"), /priors\.payments_fee\(/, "Shopify Payments is the engine's own");
});

test("registered where a sign-up and the library look for it, for Shopify sellers, lesson for lesson", () => {
  assert.equal(COURSES["shopify-margin"].path, "/learn/shopify-margin");
  assert.match(page, /<body class="course-page" data-course="shopify-margin">/);
  const lib = JSON.parse(read("data/library.json")).courses.find((x) => x.slug === "shopify-margin");
  assert.equal(lib.status, "live");
  assert.equal(lib.audience, "For Shopify sellers");
  const ids = [...page.matchAll(/<article class="lesson" id="([^"]+)"/g)].map(([, id]) => id);
  assert.deepEqual(lib.lessons.map((l) => l.id), ids);
  assert.deepEqual([...page.matchAll(/<li><a href="#([^"]+)">/g)].map(([, id]) => id), ids);
});

test("the examples say they are invented, no figure in a lesson is typed, and the FTC rule is quoted from its source", () => {
  for (const [f] of page.matchAll(/<figure[\s\S]*?<\/figure>/g)) assert.match(f, /An invented (listing|parcel)|USPS's published rates · An invented parcel/);
  for (const [w] of page.matchAll(/<div class="worked">[\s\S]*?<\/div>/g)) assert.match(text(w), /invented/i);
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  const prose = lessons.replace(/<!-- build:[\s\S]*?<!-- \/build:[^>]*-->/g, "").replace(/<div class="check">[\s\S]*?<\/ol>\s*<\/div>/g, "")
    .replace(/<span[^>]*data-fill[^>]*>[^<]*<\/span>/g, "FILL");
  // "$50" is the free-shipping line's own name in its lesson's opening example, not a computed figure
  for (const [m] of text(prose).matchAll(/\$\d+(?:,\d{3})*(?:\.\d+)?/g)) assert.ok(["$50"].includes(m), `${m} is typed into a lesson; it must come from data/learn-shopify-margin.json`);
  assert.match(page, /href="https:\/\/www\.ecfr\.gov\/current\/title-16\/chapter-I\/subchapter-B\/part-233\/section-233\.1"/);
  assert.match(text(page), /openly and actively offered for sale, for a reasonably substantial period of time/);
});

test("the Products export is read in the browser by /call's own reading, and nothing is sent", () => {
  const js = read("assets/learn-shopify-margin.js");
  assert.match(js, /import \* as call from "\/lib\/call\.js"/);
  assert.match(js, /call\.parseShopifyProducts\(/);
  assert.match(js, /call\.analyseShopify\(rc, read\)/);
  assert.match(js, /new FileReader\(\)/);
  assert.deepEqual([...js.matchAll(/fetch\("([^"]+)"/g)].map(([, u]) => u), ["/ratecard.json"], "the one request is the published rate card");
  // a two-variant export: one parcel just past a pound, one under its compare-at
  const csv = "Handle,Title,Variant SKU,Variant Grams,Variant Price,Variant Compare At Price,Status\npress,Garlic Press,GP-1,470.6,42.00,56.00,active\nmug,Mug,MG-1,300,18.00,,active\n";
  const a = call.analyseShopify(JSON.parse(read("ratecard.json")), call.parseShopifyProducts(csv));
  assert.equal(a.priced, 2);
  assert.equal(a.parcels.length, 1, "470.6 g is 16.6 oz, just past a pound");
});

test("nothing inside a lesson sells", () => {
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  assert.doesNotMatch(lessons, /href="\/apply"|\$6,000|Book your call|Managed Profit/);
});
