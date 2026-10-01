import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CHANGE, KINDS, REFERRAL, STYLE, form, saved } from "./consent_page.js";

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");
const words = (html) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
const IDENTITY = { client_id: "c1", company_name: "Cedar <&> Pine" };
const SITE = "https://www.hubricon.com";

test("the page is on the design system: the shared stylesheet, and no colour of its own", async () => {
  assert.doesNotMatch(STYLE, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, "colours belong in /assets/hubricon.css");
  const html = await form({ identity: IDENTITY, code: "abc12345", token: "t".repeat(32), site: SITE }).text();
  assert.match(html, /<link rel="stylesheet" href="\/assets\/hubricon\.css">/);
  assert.match(html, /family=Inter:opsz,wght@14\.\.32,400;14\.\.32,600/);
  for (const gone of ["Iowan", "Georgia", "amber", "serif"]) assert.ok(!html.includes(gone), `${gone} is still on the page`);
  const api = read("../api/consent.js");
  assert.doesNotMatch(api, /<style>/, "the handler keeps no style of its own");
  assert.match(api, /from "\.\.\/lib\/consent_page\.js"/);
});

test("the referral line says what terms §9 says, and nothing more generous", async () => {
  const terms = words(read("../terms.html"));
  for (const clause of [
    "one month of your fee",
    "against your next invoice",
    "or add a free month if you are not yet invoiced",
    "One credit per brand introduced, applied when that brand's first invoice is raised after its own thirtieth day, and never before.",
  ]) assert.ok(terms.includes(clause), `terms §9 no longer says "${clause}"`);
  assert.match(REFERRAL, /one month of your fee is credited against your next invoice, or a free month is added if you are not yet invoiced/);
  assert.match(REFERRAL, /applied when that brand's first invoice is raised after its own thirtieth day, and never before/);
  for (const html of [
    await form({ identity: IDENTITY, code: "abc12345", token: "t".repeat(32), site: SITE }).text(),
    await saved({ identity: IDENTITY, code: "abc12345", token: "t".repeat(32), site: SITE }).text(),
  ]) {
    assert.ok(words(html).includes(REFERRAL));
    assert.doesNotMatch(html, /next month is on us|day thirty/);
    assert.ok(html.includes(`${SITE}/?ref=abc12345`));
  }
});

test("'change your mind' stays true after the link expires, and nothing promises an hourly pass", async () => {
  assert.match(CHANGE, /at any time by replying to any email from us/);
  const formHtml = await form({ identity: IDENTITY, code: "x", token: "t".repeat(32), site: SITE }).text();
  const savedHtml = await saved({ identity: IDENTITY, code: "x", token: "t".repeat(32), site: SITE, granted: 2 }).text();
  for (const html of [formHtml, savedHtml]) {
    assert.ok(words(html).includes(CHANGE));
    assert.doesNotMatch(html, /hourly|any time at the same link|expires with your upload links/i);
  }
  assert.match(words(savedHtml), new RegExp(`2 of ${KINDS.length} permissions granted`));
});

test("the form shows each answer as it stands, and escapes what it prints", async () => {
  const html = await form({
    identity: IDENTITY, code: "x", token: "t".repeat(32), site: SITE,
    existing: [
      { kind: "anonymised_results", granted: true },
      { kind: "network", granted: false },
      { kind: "testimonial", granted: true, testimonial: "Fewer <b>surprises</b>.", testimonial_named_ok: true },
    ],
  }).text();
  assert.match(html, /name="anonymised_results" checked>/);
  assert.match(html, /name="network" >/);
  assert.match(html, /name="testimonial_named_ok" checked>/);
  assert.ok(html.includes("Fewer &lt;b&gt;surprises&lt;/b&gt;."));
  assert.ok(html.includes("Cedar &lt;&amp;&gt; Pine"));
  assert.ok(!html.includes("Cedar <&> Pine"));
  for (const kind of KINDS) assert.match(html, new RegExp(`name="${kind}"`));
});
