// /verify, the page anyone uses to check a Profit Record without trusting us: the file is
// read in the reader's browser and nothing of theirs leaves it, the sample is labelled a
// sample wherever it shows, a hash is never vouched for on its own, the page says plainly
// what the Seal cannot prove yet, and it is on the one design system in the one face.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { verifyBundle, GENESIS } from "./verify-record.mjs";
import * as page from "../assets/verify.js";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const html = read("verify.html");
const js = read("assets/verify.js");
const style = html.match(/<style>([\s\S]*?)<\/style>/)[1];
const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const sample = JSON.parse(html.match(/<script type="application\/json" id="sample-record">([\s\S]*?)<\/script>/)[1]);

test("nothing of the reader's leaves the browser: one request, for the public head, carrying nothing", () => {
  assert.doesNotMatch(html, /_vercel\/insights|googletagmanager|gtag\(/, "no analytics on /verify");
  assert.doesNotMatch(html, /<form\b[^>]*action=/i, "no form posts anywhere");
  assert.doesNotMatch(js, /XMLHttpRequest|sendBeacon|new WebSocket|navigator\.share|FormData/);
  const fetches = [...js.matchAll(/fetch\(([^,)]*)/g)].map(([, a]) => a.trim());
  assert.deepEqual(fetches, ["RPC_URL"], "the only request is the published head");
  assert.match(js, /const RPC_URL = "https:\/\/cgqvdnhgbfxikzdqqaws\.supabase\.co\/rest\/v1\/rpc\/public_record_seal";/);
  assert.match(js, /fetch\(RPC_URL, \{\s*method: "POST", body: "\{\}",/, "and it carries an empty body");
  assert.match(text(html), /Read in this browser\. Nothing is uploaded\./);
  assert.match(html, /<script type="module" src="\/assets\/verify\.js"><\/script>/);
});

test("on the one design system, in the one face: no palette, no monospace, hashes in Inter in eights", () => {
  assert.match(html, /href="\/assets\/hubricon\.css"/);
  assert.match(html, /family=Inter:opsz,wght@14\.\.32/);
  assert.doesNotMatch(style, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, "colours belong in /assets/hubricon.css");
  for (const src of [html, js]) assert.doesNotMatch(src, /monospace|Menlo|Consolas|Courier|SF Mono|<code\b|<pre\b|<kbd\b|<tt\b/i, "one face: no monospace anywhere");
  const rule = style.match(/\.hash \{([^}]*)\}/)[1];
  assert.match(rule, /font-family: var\(--font\)/);
  assert.match(rule, /font-feature-settings: "zero"/);
  assert.match(rule, /font-variant-numeric: tabular-nums/);
  assert.equal(page.groups("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"), "01234567 89abcdef 01234567 89abcdef 01234567 89abcdef 01234567 89abcdef");
  assert.doesNotMatch(html, /class="btn\b/, "the call is the only solid button on the site, and this page books nothing");
  assert.doesNotMatch(html, /<!-- build:/, "the shared nav and footer are built in by the site's own build, not here");
});

test("it says plainly what the Seal cannot prove yet", () => {
  const t = text(html);
  assert.match(t, /There is no outside timestamp\./);
  assert.match(t, /Whoever owns the database could rewrite the table consistently/);
  assert.match(t, /the seals in clients' inboxes, the heads on pages already printed, and the exports already downloaded/);
  assert.match(t, /That is evidence of a rewrite, not prevention of one\./);
  assert.match(t, /is the next step, and it is not built\./, "the anchor is future, and labelled so");
  assert.match(t, /every export carries the same checker as a file, verify-record\.mjs/);
});

test("the sample is a sample wherever it shows, and it checks out until one figure is changed", () => {
  assert.match(sample.sample, /^Invented for hubricon\.com\/verify .* Not a client, not a result\.$/);
  assert.equal(verifyBundle(sample).status, "ok");
  for (const e of sample.entries) assert.ok(Date.parse(e.document.sealed_at) < Date.parse("2026-10-01"), "nothing in the sample is dated in the future");
  const t = text(html);
  assert.match(t, /Try it on a sample Record \(invented, not a client\)/);
  assert.match(t, /Change one figure in the sample, then check again/);
  assert.match(t, /Sample Record · invented for this page · not a client · not a result/);
  assert.match(js, /\$\("sample-tag"\)\.hidden = !sample;/, "the label shows whenever the sample does");
  assert.match(js, /"Intact \(sample\)\."/);
  const state = { record: sample, result: verifyBundle(sample), sample: true };
  assert.match(page.describeFind(state, sample.head), /^In the sample Record \(invented, not a client\): Found\./);
  assert.match(page.describePublished({ head: GENESIS, entries: 0 }, state), /sample is invented/);
  const tampered = structuredClone(sample);
  tampered.entries[1].document.expected_usd = "1490.00";
  const r = verifyBundle(tampered);
  assert.equal(r.first_broken_seq, 2);
  assert.ok(r.problems.some((p) => p.check === "leaf" && p.seq === 2));
  assert.match(js, /b\.entries\[1\]\.document\.expected_usd = "1490\.00";/, "the page's tamper is the one tested here");
});

test("a pasted hash means something only after the export checks out", () => {
  assert.match(page.describeFind({ record: null }, "e70027c2 7e914d6e"), /^Load a Record export first\./);
  const state = { record: sample, result: verifyBundle(sample), sample: false };
  const grouped = sample.entries[2].head.match(/.{8}/g).join(" ");
  assert.match(page.describeFind(state, `  ${grouped}\n`), /head after entry 3 of 6, sealed Aug 24, 2026/);
  assert.match(page.describeFind(state, "zz"), /not a head or a seal/);
});

test("the published head, read the way the site's other pages read public functions", () => {
  assert.match(js, /const PUBLISHABLE = "sb_publishable_byrEWlQDgM9fDW-2bwIA3w_XA0mrg5X";/);
  assert.equal(js.match(/sb_publishable_[A-Za-z0-9_-]+/)[0], read("assets/site.js").match(/sb_publishable_[A-Za-z0-9_-]+/)[0], "the same public key as every other page");
  assert.match(js, /Nothing has been sealed on Hubricon's chain yet/, "an empty chain is said to be empty");
  assert.match(js, /could not be read just now/, "and an unreachable one is said to be unreachable");
});
