import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * The Managed Profit page's visible word count, as the learn build prompt's
 * acceptance check reads it (docs/content/hubricon-learn-build-prompt.md §7.13):
 * /learn is linked from the nav and the footer only, and the body copy between
 * them is unchanged by the learn project.
 */

const page = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const strip = (html) => html
  .replace(/<script[\s\S]*?<\/script>/g, "")
  .replace(/<style[\s\S]*?<\/style>/g, "")
  .replace(/<!--[\s\S]*?-->/g, "")
  .replace(/<[^>]+>/g, " ")
  .replace(/&[a-z#0-9]+;/g, " ");
const words = (html) => strip(html).split(/\s+/).filter(Boolean).length;

const nav = page.match(/<nav class="nav"[\s\S]*?<\/nav>/)[0];
const footer = page.match(/<footer class="footer">[\s\S]*?<\/footer>/)[0];
const body = page.slice(page.indexOf("<body>")).replace(nav, "").replace(footer, "");

// Measured on 2026-09-18 before the learn links were added; the learn project may not change it.
const BODY_WORDS_BEFORE_LEARN_LINKS = 507;

test("the body copy's word count is unchanged by the learn project", (t) => {
  t.diagnostic(`visible words on the page: ${words(page)}; body copy without nav and footer: ${words(body)}`);
  assert.equal(words(body), BODY_WORDS_BEFORE_LEARN_LINKS);
});

test("/learn is linked from the nav and the footer only", () => {
  assert.match(nav, /<a href="\/learn">Learn<\/a>/);
  assert.match(footer, /<h4>Product<\/h4><ul><li><a href="\/learn">Free training<\/a><\/li>/);
  assert.doesNotMatch(body, /href="\/learn"/, "no learn link inside the body copy");
});
