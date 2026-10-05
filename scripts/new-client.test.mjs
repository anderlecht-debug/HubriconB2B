import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emailsFor, exportsFor, EMAIL_KINDS } from "./new-client.mjs";
import { renderText } from "./lib/email.mjs";
import { maySend } from "../lib/intake.js";

const LINK = "https://www.hubricon.com/intake?t=abc";
const RETIRED = [/teardown/i, /\bdesk\b/i, /\bledger\b/i, /\bretainer\b/i, /\bengagement\b/i, /\bdirective/i, /three-minute brief/i];

test("the manual emails are the journey's: call prep before the call, the upload page after it", () => {
  assert.deepEqual(EMAIL_KINDS, ["call_prep", "nudge", "files"]);
  assert.equal(maySend("booked", "call_prep"), true);
  for (const kind of ["nudge", "files"]) {
    assert.equal(maySend("booked", kind), false, `${kind} waits for the call`);
    assert.equal(maySend("called", kind), true);
  }
});

test("nothing retired, no Teardown and no speed promise in any of them, on any platform", () => {
  for (const platform of ["amazon", "shopify", "both"]) {
    const emails = emailsFor({ firstName: "Jane", platform, link: LINK });
    for (const [kind, spec] of Object.entries(emails)) {
      const text = `${spec.subject}\n${renderText(spec)}`;
      for (const word of RETIRED) assert.doesNotMatch(text, word, `${platform} ${kind}: ${word}`);
      assert.doesNotMatch(text, /within 24 hours|within the hour|the moment your|as soon as/i, `${platform} ${kind} promises speed`);
      assert.ok(text.includes(LINK), `${platform} ${kind} carries the upload link`);
    }
  }
  const src = readFileSync(new URL("./new-client.mjs", import.meta.url), "utf8");
  assert.doesNotMatch(src, /Teardown/);
});

test("the call email asks for what the call reads, and the upload stays optional", () => {
  const amazon = renderText(emailsFor({ firstName: "Jane", platform: "amazon", link: LINK }).call_prep);
  assert.match(amazon, /Inventory Age/);
  assert.match(amazon, /Fee Preview/);
  assert.match(amazon, /Optional/);
  const call = readFileSync(new URL("../call.html", import.meta.url), "utf8");
  assert.match(call, /Inventory Age/);
  assert.match(call, /Fee Preview/);
  const shopify = renderText(emailsFor({ firstName: "Jane", platform: "shopify", link: LINK }).call_prep);
  assert.doesNotMatch(shopify, /Seller Central/, "a Shopify store is never sent Seller Central steps");
});

test("the first read's timing is the rule, named with the client's own core files", () => {
  const files = renderText(emailsFor({ firstName: "Jane", platform: "shopify", link: LINK }).files);
  assert.match(files, /core files are in \(Orders, Products & costs\), or 24 hours after your last upload/);
  assert.equal(exportsFor("both").filter((e) => e.startsWith("Amazon — ")).length, 4);
});
