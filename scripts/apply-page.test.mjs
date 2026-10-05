// /apply after the booking: the prospect is told what the call is and what to have ready
// for where they sell, nobody is promised a reading /call cannot do (a Shopify-only seller
// hears nothing about Seller Central), and the fit tag in the booking URL is a code, not a
// verdict a prospect can read in their address bar.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = read("apply.html");
const call = read("call.html");
const script = page.match(/<script>\s*"use strict";([\s\S]*?)<\/script>/)[1];
const prep = JSON.parse(page.match(/<script type="application\/json" id="prep-copy">([\s\S]*?)<\/script>/)[1]);
const words = (channel) => [prep.facts[channel], prep.call[channel], ...prep.steps[channel].flatMap((s) => [s.do, s.how])].join(" ");
const AMAZON_ONLY = /Amazon|Seller Central|Fee Preview|Inventory Age|Inventory Health|ACoS|FBA|day 271|low-inventory|Sponsored Products/;

test("every channel gets the call in one sentence, two to four things to do, and the privacy line", () => {
  for (const c of ["Amazon", "Shopify", "Both"]) {
    assert.ok(prep.call[c] && prep.facts[c], c);
    assert.ok(prep.steps[c].length >= 2 && prep.steps[c].length <= 4, `${c}: ${prep.steps[c].length} steps`);
    for (const s of prep.steps[c]) assert.ok(s.do.endsWith(".") && s.how.length > 20, `${c}: "${s.do}" says how`);
  }
  assert.equal(prep.private, "Nothing is uploaded on the call; it is priced in your browser.");
  assert.match(script, /`\$\{PREP\.private\} \$\{PREP\.when\}`/, "the privacy line is on every panel");
});

test("Amazon: request Fee Preview and Inventory Age now, the ads report, landed cost and target ACoS", () => {
  const a = words("Amazon");
  assert.match(prep.steps.Amazon[0].do, /Request Fee Preview and Inventory Age in Seller Central now\./);
  assert.match(a, /Amazon builds both on request/);
  assert.match(a, /Manage Inventory Health/);
  assert.match(a, /campaign or search-term report/);
  assert.match(a, /landed cost as a % of price/);
  assert.match(a, /the ACoS you aim for/);
});

test("Shopify: Shopify admin and its Products export, landed cost, and not one word of Amazon", () => {
  const s = words("Shopify");
  assert.doesNotMatch(s, AMAZON_ONLY, "a Shopify-only seller is never promised an Amazon reading");
  assert.match(s, /signed in to Shopify admin/);
  assert.match(s, /Products, Export, All products, as CSV/);
  assert.match(s, /landed cost as a % of price/);
});

test("Both: the Amazon reports and the Shopify export", () => {
  const b = words("Both");
  for (const must of [/Fee Preview and Inventory Age/, /Shopify admin/, /campaign or search-term report/, /the ACoS you aim for/]) assert.match(b, must);
});

test("the panel asks only for what /call can read", () => {
  for (const name of ["Inventory Age", "Fee Preview", "Manage Inventory Health", "Campaign report", "Products export", "cost-template", "landed cost"]) {
    assert.ok(call.toLowerCase().includes(name.toLowerCase().replace("cost-template", "cogs-template")), `/call reads ${name}`);
  }
});

test("the facts beside the form promise nothing channel-specific until the seller says where they sell", () => {
  const li = page.match(/<li id="fact-reports">([^<]*)<\/li>/)[1];
  assert.doesNotMatch(li, /aged stock|low-inventory|compare-at|pound/, "the default line names no platform's leak");
  assert.match(li, /Seller Central or Shopify/);
  assert.doesNotMatch(prep.facts.Shopify, AMAZON_ONLY);
  assert.match(script, /if \(PREP\.facts\[ch\]\) factReports\.textContent = PREP\.facts\[ch\];/);
});

test("the panel shows when Calendly says a time was booked, and says 'if' to someone coming back", () => {
  assert.match(script, /e\.origin === "https:\/\/calendly\.com" && e\.data\?\.event === "calendly\.event_scheduled"\) \{\s*track\("calendly_scheduled", \{ h: headline \}\);\s*showPrep\(booked\);/);
  assert.match(script, /remember\(a\.channel\);\s*\/\/[^\n]*\n\s*location\.href = url;/, "the blocked-widget path remembers where they sell before it leaves");
  assert.match(script, /const back = recall\(\);\s*if \(back\) document\.getElementById\("gate-title"\)\.after\(prepPanel\(back\.channel, true\)\);/);
  assert.equal(prep.returning, "If you picked a time on Calendly:", "the page cannot see a booking it did not host, so it says if");
  assert.match(script, /textContent = s\.how|createTextNode\(s\.how\)/, "copy is set as text, never as HTML");
});

test("the fit tag is a code in the URL, documented beside it, never the word", () => {
  const codes = JSON.parse(script.match(/const FIT_CODE = (\{[^}]*\});/)[1].replace(/(\w+):/g, '"$1":'));
  assert.deepEqual(Object.keys(codes).sort(), ["below", "core"]);
  for (const v of Object.values(codes)) assert.match(v, /^[a-z]\d$/, "two characters a prospect cannot read as a verdict");
  assert.match(script, /\|fit:\$\{FIT_CODE\[fitTag\(a\)\]\}\|/);
  for (const [k, v] of Object.entries(codes)) assert.match(script, new RegExp(`fit:${v}\\s+[^\\n]*\\(was fit:${k}\\)`), `fit:${v} is documented`);
  assert.doesNotMatch(script.replace(/\/\*[\s\S]*?\*\//g, ""), /fit:(below|core)/, "the words appear only in the comment that decodes them");
});

test("no tab bar on /apply, the booking is the one solid button, and no retired word", () => {
  assert.doesNotMatch(page, /<header class="nav"/);
  assert.equal((page.match(/class="btn\b/g) || []).length, 1);
  const visible = page.replace(/<!--[\s\S]*?-->/g, "").replace(/\/\*[\s\S]*?\*\//g, "");
  for (const w of [/\bdesk\b/i, /\bledger\b/i, /\bretainer\b/i, /\bengagement\b/i, /\bdirective\b/i, /Teardown/, /three-minute brief/i, /quantitative/i]) {
    assert.doesNotMatch(visible, w);
  }
});
