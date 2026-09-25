import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

/**
 * The course page at /learn/reimbursement-playbook, checked the way the copy
 * critique reads it (docs/content/hubricon-learn-build-prompt.md §7): the
 * inline script parses, every lesson is embedded, lesson one is open without
 * the form, the form has six fields and no phone, and the visible copy carries
 * no exclamation mark and "free" at most twice.
 */

const page = readFileSync(new URL("../learn/reimbursement-playbook.html", import.meta.url), "utf8");
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const visible = page
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .replace(/<style[\s\S]*?<\/style>/g, "")
  .replace(/<!--[\s\S]*?-->/g, "")
  .replace(/<[^>]+>/g, " ");

test("the inline script parses", () => {
  assert.equal(scripts.length, 1);
  assert.doesNotThrow(() => new vm.Script(scripts[0], { filename: "reimbursement-playbook.html" }));
});

test("six lessons are embedded, lesson one open and the rest gated", () => {
  for (const n of [1, 2, 3, 4, 5, 6]) {
    const sec = page.match(new RegExp(`<section class="prose" id="L${n}" data-lesson="L${n}"([^>]*)>([\\s\\S]*?)</section>`));
    assert.ok(sec, `section L${n}`);
    assert.match(sec[2], /<h2>.+<\/h2>/, `L${n} carries its heading`);
    if (n === 1) assert.doesNotMatch(sec[1], /hidden|data-gated/, "lesson one is readable without the form");
    else assert.match(sec[1], /\bhidden\b[^>]*data-gated|data-gated[^>]*\bhidden\b/, `L${n} is hidden and gated`);
    assert.match(page, new RegExp(`<a href="#L${n}" data-lesson="L${n}">`), `L${n} is in the lesson list`);
  }
});

test("the form has six fields, apply.html's four questions verbatim, and no phone number", () => {
  const form = page.match(/<form class="gate capture"[\s\S]*?<\/form>/)[0];
  assert.match(form, /name="first_name"/);
  assert.match(form, /name="email"/);
  const radios = [...form.matchAll(/name="(channel|rev|model|skus)"/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(radios)], ["channel", "rev", "model", "skus"]);
  assert.doesNotMatch(form, /phone|tel"/i);
  const honeypot = form.match(/class="hp"[\s\S]*?name="website"/);
  assert.ok(honeypot, "the honeypot is present and off-screen");
  for (const opt of ["Under $3M", "$3M–$5M", "$5M–$20M", "$20M+", "Private label", "Wholesale / reseller", "Arbitrage", "Mixed / other", "Under 10 SKUs", "10–50 SKUs", "50+ SKUs", "Amazon", "Shopify", "Both"]) {
    assert.match(form, new RegExp(`value="${opt.replace(/[$+]/g, "\\$&")}"`), `option ${opt}`);
  }
});

test("the template sits directly under the video slot and one amber button is the form's", () => {
  const slot = page.indexOf('id="slot"'), tpl = page.indexOf('id="tpl"'), first = page.indexOf('<section class="prose" id="L1"');
  assert.ok(slot > 0 && tpl > slot && first > tpl);
  assert.match(page, /id="tpl" href="\/learn\/reimbursement-playbook-template\.xlsx" download data-locked="true"/);
});

test("the visible copy has no exclamation mark, no hype furniture and 'free' at most twice", () => {
  assert.doesNotMatch(visible, /!/);
  assert.doesNotMatch(visible, /coming soon|limited spots|countdown|in today's video|let's dive in|game-changer|\bsecret\b|\bhack\b|\bcrazy\b|\binsane\b|\bsimply\b|\bjust\b|\bobviously\b|of course|the truth is|\bimagine\b/i);
  assert.ok((visible.match(/\bfree\b/gi) || []).length <= 2);
});
