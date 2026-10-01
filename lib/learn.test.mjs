// /learn's server side: a sign-up is an email and a course and nothing else, the one
// email it sends carries the link, the spreadsheet and a working unsubscribe, and the
// unsubscribe page says what happened.
//   node --test lib/
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { COURSES, parseSignup, composeLearnEmail, unsubscribePage, unsubscribeUrl, TOKEN } from "./learn.js";

const root = new URL("../", import.meta.url);

test("a sign-up is an address and a course, cleaned", () => {
  assert.deepEqual(parseSignup({ email: "  Ada@Brand.COM ", course: "fee-staircase", source: "youtube" }),
    { email: "ada@brand.com", course: "fee-staircase", source: "youtube" });
  assert.equal(parseSignup({ email: "ada@brand.com", course: "fee-staircase", source: "<script>x" }).source, "scriptx");
  assert.equal(parseSignup({ email: "ada@brand.com", course: "fee-staircase" }).source, null);
});

test("a bad address or an unknown course is refused; a bot is quietly ignored", () => {
  assert.ok(parseSignup({ email: "not-an-email", course: "fee-staircase" }).error);
  assert.ok(parseSignup({ email: "a@b.c", course: "fee-staircase" }).error, "a one-letter top-level domain is not real");
  assert.ok(parseSignup({ email: `${"a".repeat(200)}@b.com`, course: "fee-staircase" }).error);
  assert.ok(parseSignup({ email: "ada@brand.com", course: "teardown" }).error, "only courses that exist");
  assert.ok(parseSignup({ email: "ada@brand.com", course: "__proto__" }).error);
  assert.deepEqual(parseSignup({ email: "ada@brand.com", course: "fee-staircase", website: "http://spam" }), { bot: true });
  assert.ok(parseSignup(null).error);
});

test("every course listed exists in full: its page and its spreadsheet are on the site", () => {
  for (const [slug, c] of Object.entries(COURSES)) {
    assert.equal(c.path, `/learn/${slug}`);
    assert.ok(existsSync(new URL(`.${c.path}.html`, root)), `${c.path}.html`);
    assert.ok(existsSync(new URL(`.${c.template}`, root)), c.template);
  }
});

test("the one email: the link back, the spreadsheet, what else will come, and the way out", () => {
  const token = "0123456789abcdef0123456789abcdef";
  const url = unsubscribeUrl(token);
  const m = composeLearnEmail({ course: "fee-staircase", unsubscribeUrl: url, postalAddress: "1 Test St, Dallas TX" });
  assert.equal(m.subject, "The Fee Staircase: your link");
  for (const part of [m.text, m.html]) {
    assert.ok(part.includes("https://www.hubricon.com/learn/fee-staircase"));
    assert.ok(part.includes("https://www.hubricon.com/learn/files/hubricon-fee-staircase.xlsx"));
    assert.ok(part.includes(url), "a working unsubscribe link");
    assert.match(part, /only when a new course is out/);
    assert.match(part, /1 Test St, Dallas TX/);
  }
  assert.deepEqual(m.headers, { "List-Unsubscribe": `<${url}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" });
  assert.doesNotMatch(m.text, /\$\d|price|offer|call/i, "nothing is for sale in the course email");
  assert.ok(TOKEN.test(token));
});

test("the unsubscribe page says what happened, in plain words", () => {
  assert.match(unsubscribePage(true), /You(&#39;|')re off the list\./);
  assert.match(unsubscribePage(true), /stays open/);
  assert.match(unsubscribePage(false), /didn(&#39;|')t match/);
  assert.match(unsubscribePage(true), /noindex/);
});
