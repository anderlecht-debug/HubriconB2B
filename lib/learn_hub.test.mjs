import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * The hub at /learn, checked the way the copy critique and the learn build
 * prompt read it (docs/content/hubricon-learn-build-prompt.md §2, §7): one
 * card per course that exists in full, the position stated in the headline,
 * under two hundred visible words, and no hype furniture.
 */

const page = readFileSync(new URL("../learn/index.html", import.meta.url), "utf8");
const visible = page
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .replace(/<style[\s\S]*?<\/style>/g, "")
  .replace(/<!--[\s\S]*?-->/g, "")
  .replace(/<[^>]+>/g, " ")
  .replace(/&[a-z]+;/g, " ");
const words = visible.split(/\s+/).filter(Boolean);

test("one course card, for the course that exists, with its badges", () => {
  const cards = page.match(/class="card"/g) || [];
  assert.equal(cards.length, 1);
  assert.match(page, /<a class="card" href="\/learn\/reimbursement-playbook">/);
  assert.match(page, /<span class="tag new">New<\/span><span class="tag">Free<\/span>/);
});

test("the headline states the position", () => {
  assert.match(page, /<h1>The method is public\. The execution is the product\.<\/h1>/);
});

test("under two hundred visible words", () => {
  assert.ok(words.length < 200, `${words.length} words`);
});

test("no hype furniture, no exclamation mark, 'free' at most twice", () => {
  assert.doesNotMatch(visible, /!/);
  assert.doesNotMatch(visible, /coming soon|limited spots|countdown|in today's video|let's dive in|game-changer|\bsecret\b|\bhack\b|\bcrazy\b|\binsane\b|\bsimply\b|\bjust\b|\bobviously\b|of course|the truth is|\bimagine\b/i);
  assert.ok((visible.match(/\bfree\b/gi) || []).length <= 2);
});
