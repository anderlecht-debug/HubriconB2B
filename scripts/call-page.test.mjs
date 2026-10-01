// /call, the page used on a sales call: the prospect's reports are read in their own
// browser and nothing leaves it. No analytics, no request that could carry a file, not
// indexed, not linked from the home page, on the one design system. "Keep this reading"
// is the browser's print dialog on this same page, so keeping it sends nothing either.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = read("call.html");
const js = read("assets/call.js");
const style = page.match(/<style>([\s\S]*?)<\/style>/)[1];
const print = style.slice(style.indexOf("@media print {"));
const results = page.match(/<section class="results"[\s\S]*?<\/section>\s*<\/main>/)[0];

test("nothing leaves the browser: no analytics, no upload, no beacon", () => {
  assert.doesNotMatch(page, /_vercel\/insights|googletagmanager|gtag\(/, "no analytics script on /call");
  assert.doesNotMatch(page, /<form\b[^>]*action=/i, "no form posts anywhere");
  assert.doesNotMatch(js, /XMLHttpRequest|sendBeacon|method:\s*["']POST|new WebSocket|navigator\.share|createObjectURL|FormData/);
  const fetches = [...js.matchAll(/fetch\(([^)]*)\)/g)].map(([, a]) => a.trim());
  assert.deepEqual(fetches, ['"/ratecard.json"'], "the only request is the public rate card");
  assert.match(page, /Nothing is uploaded/);
});

test("not indexed, not linked from the home page, on the design system", () => {
  assert.match(page, /<meta name="robots" content="noindex, nofollow">/);
  assert.doesNotMatch(read("index.html"), /href="\/call"/);
  assert.match(page, /href="\/assets\/hubricon\.css"/);
  assert.doesNotMatch(style, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, "colours belong in /assets/hubricon.css, the print styles' included");
  assert.match(page, /family=Inter:opsz,wght@14\.\.32/);
  assert.doesNotMatch(page, /class="(btn|tile)\b/, "the call is the only solid button, and the course tile is the library's");
  assert.doesNotMatch(page, /<header class="nav"/, "no tab bar on /call");
});

test("the page says what its figures are", () => {
  assert.match(page, /not a result and not a promise/);
  assert.match(page, /the same arithmetic Hubricon's engine runs/);
  assert.match(js, /estimate/);
  assert.match(js, /a plain multiplication, not a forecast/, "the year line says what it is");
});

test("keep this reading: the print dialog on this page, the controls away, the date and what was read in their place", () => {
  assert.match(js, /\$\("keep"\)\.addEventListener\("click", \(\) => \{ stampReading\(\); window\.print\(\); \}\);/);
  assert.match(js, /addEventListener\("beforeprint", stampReading\)/, "a print from the browser's own menu is dated too");
  assert.match(page, /<button class="keep" type="button" id="keep">Keep this reading<\/button>/);
  assert.match(style, /\.print-only \{ display: none; \}/);
  assert.match(print, /\.top, \.head, \.reports, \.keep-bar, \.foot \{ display: none; \}/, "on paper, no drops, no buttons");
  assert.match(print, /\.print-only \{ display: grid; \}/);
  // What prints is the results section: the mark, the date, the files, what was typed, and every label.
  assert.match(results, /class="print-only reading"[\s\S]*Hubricon · hubricon\.com[\s\S]*A reading of your own reports/);
  for (const id of ["reading-when", "reading-files", "reading-typed"]) assert.match(results, new RegExp(`id="${id}"`));
  assert.match(results, /not a result and not a promise/);
  assert.match(js, /`\$\{usd\(total\)\}<span class="est">estimate<\/span>`/);
});

test("Shopify sellers get a Shopify reading, and a SKU with its own cost says so", () => {
  assert.match(page, /id="file-shopify"/);
  assert.match(page, /On Shopify: prices sitting under their own compare-at, and parcels just past a pound line\./);
  assert.match(js, /call\.parseShopifyProducts/);
  assert.match(js, /call\.analyseShopify\(rc, state\.shopify, \{/);
  for (const label of ["est.", "estimate"]) assert.ok(js.split("drawShopify")[2].includes(label), `the Shopify figures carry "${label}"`);
  assert.match(page, /id="file-cost"/);
  assert.match(page, /href="\/cogs-template\.csv"/);
  assert.match(js, /costBySku: state\.cost \? state\.cost\.bySku : \{\}/);
  assert.match(js, /m\.cost_basis === "yours" \? "your cost" : "est\. from your %"/);
});

test("a Shopify booker is met as one: Shopify cards first, the Shopify lede, no ACoS box", () => {
  // the channel is the one /apply kept for this browser at booking, or ?p= on the link
  const apply = read("apply.html");
  assert.match(apply, /const BOOKED_KEY = "hubricon_booked";/);
  assert.match(apply, /localStorage\.setItem\(BOOKED_KEY, JSON\.stringify\(\{ channel: channelOf\(channel\), at: Date\.now\(\) \}\)\)/);
  assert.match(js, /localStorage\.getItem\("hubricon_booked"\)/);
  assert.match(js, /new URLSearchParams\(location\.search\)\.get\("p"\)/);
  assert.doesNotMatch(js, /localStorage\.(setItem|removeItem)/, "the call reads the booking's answer and never changes it");
  const order = js.match(/const ORDER = \{([\s\S]*?)\n\};/)[1];
  assert.match(order, /shopify: \[\["shopify", "orders", "cost"\], "Also selling on Amazon\?[^"]*", \["inventory", "fees", "ads"\]\]/);
  for (const id of ["shopify", "orders", "cost", "inventory", "fees", "ads"]) assert.match(page, new RegExp(`id="drop-${id}"`), `${id} is a card on the page`);
  assert.match(js, /\$\("knob-target"\)\.hidden = CHANNEL === "shopify" && !amazon;/, "target ACoS is Amazon's, shown to a Shopify seller only once an Amazon report is in");
  assert.match(page, /<div class="knob" id="knob-target">\s*<label for="target">Your target ACoS<\/label>/);
  const lede = js.match(/shopify: "(Drop in your Shopify[^"]*)"/)[1];
  assert.doesNotMatch(lede, /Amazon|Seller Central|ACoS|FBA/, "the Shopify lede names no Amazon report");
  assert.match(js, /if \(CHANNEL === "shopify"\) \$\("results"\)\.insertBefore\(\$\("shopify"\), \$\("amazon"\)\);/);
});

test("the Orders export makes the Shopify figures a month, read here, its customer columns never", () => {
  assert.match(page, /id="file-orders"/);
  assert.match(page, /Orders, Export, Orders by date, as CSV/);
  assert.match(page, /no name, email or address/);
  assert.match(js, /orders: \{ label: "Shopify Orders", parse: call\.parseShopifyOrders/);
  assert.match(js, /orders: state\.orders/);
  assert.doesNotMatch(js, /your own count/, "nothing points at an export the page cannot read");
  const body = js.split("function drawShopify")[1];
  assert.match(body, /Twelve months at this pace would be \$\{usd\(total \* 12\)\}, an estimate: a plain multiplication, not a forecast\./);
});

test("what each Shopify variant keeps, and its break-even ROAS, every figure an estimate, on paper too", () => {
  const body = js.split("function drawShopify")[1];
  assert.match(body, /Shopify Payments' standard online card fee of \$\{\(pay\.rate \* 100\)\.toFixed\(1\)\}% \+ \$\{Math\.round\(pay\.fixed \* 100\)\}¢/);
  assert.match(body, /The fee is an estimate/);
  assert.match(body, /Break-even ROAS is the return an ad must bring/);
  const keep = body.slice(body.indexOf("const BASIS"));
  assert.equal((keep.match(/<span class="basis">estimate<\/span>/g) || []).length, 4, "the fee, kept a unit, the ROAS and kept a month each say estimate");
  assert.match(keep, /cost_per_item: "Cost per item"/, "a cost says where it came from");
  assert.match(results, /id="leak-keep"[\s\S]*What each variant keeps, and the ROAS that breaks even/, "inside the results, so the printed reading carries it");
  assert.match(results, /Shopify Payments' standard 2\.9% \+ 30¢/);
});
