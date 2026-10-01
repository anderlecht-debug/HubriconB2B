// The Price Curve (/learn/price-curve), held to the same rules as the first course and to
// the engine it teaches: the spreadsheet and every figure were checked against Hubricon's
// engine (scripts/learn/price_curve.py), and are re-checked whenever the engine moves; the
// worked example is labelled invented wherever it shows; nothing inside a lesson sells.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { COURSES } from "../../lib/learn.js";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const sha = (p) => createHash("sha256").update(readFileSync(new URL(p, root))).digest("hex");
const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const page = read("learn/price-curve.html");
const rerun = "run: cd engine && uv run --with openpyxl python ../scripts/learn/price_curve.py --publish";

test("the spreadsheet and the figures were checked against the engine as it is today", () => {
  const stamp = JSON.parse(read("scripts/learn/price-curve.stamp.json"));
  const figs = JSON.parse(read("data/learn-price-curve.json"));
  for (const [file, hash] of Object.entries(stamp.engine_sha256)) assert.equal(hash, sha(file), `${file} changed since the spreadsheet was verified; ${rerun}`);
  for (const [file, hash] of Object.entries(figs.engine_sha256)) assert.equal(hash, sha(file), `${file} changed since the course's figures were computed; ${rerun}`);
  assert.equal(stamp.file_sha256, sha(stamp.file), `the template changed without being re-verified; ${rerun}`);
  assert.ok(stamp.golden_cases >= 80);
  assert.match(read("scripts/learn/price_curve.py"), /from hubricon_engine\.models\.elasticity import[^\n]*_fit/, "the figures are the engine's own fit");
});

test("registered where a sign-up and the library look for it", () => {
  assert.equal(COURSES["price-curve"].path, "/learn/price-curve");
  assert.equal(COURSES["price-curve"].template, "/learn/files/hubricon-price-curve.xlsx");
  assert.match(page, /<body class="course-page" data-course="price-curve">/);
  const lib = JSON.parse(read("data/library.json"));
  const c = lib.courses.find((x) => x.slug === "price-curve");
  assert.equal(c.status, "live");
  const ids = [...page.matchAll(/<article class="lesson" id="([^"]+)"/g)].map(([, id]) => id);
  assert.deepEqual(c.lessons.map((l) => l.id), ids);
});

test("eight lessons in the list's order, the spreadsheet directly under each head, something to do at the end of each", () => {
  const lessons = [...page.matchAll(/<article class="lesson" id="([^"]+)"[\s\S]*?<\/article>/g)];
  const toc = [...page.matchAll(/<li><a href="#([^"]+)">/g)].map(([, id]) => id);
  assert.equal(lessons.length, 8);
  assert.deepEqual(lessons.map(([, id]) => id), toc);
  for (const [whole, id] of lessons) {
    assert.match(whole.slice(whole.indexOf("</header>"), whole.indexOf("</header>") + 400), /class="tpl"[\s\S]*href="\/learn\/files\/hubricon-price-curve\.xlsx"/, `${id}: the spreadsheet under the head`);
    assert.match(whole, /<div class="do">/, `${id}: ends with something to do`);
    assert.match(whole, new RegExp(`<!-- build:video-${id} -->`), `${id}: a slot for its video`);
  }
});

test("the invented listing says so wherever it shows, and no figure in the page is typed", () => {
  for (const [f] of page.matchAll(/<figure[\s\S]*?<\/figure>/g)) assert.match(f, /An invented listing · Not a client · Not a result/);
  for (const [w] of page.matchAll(/<div class="worked">[\s\S]*?<\/div>/g)) assert.match(w, /invented listing/i);
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  const prose = lessons.replace(/<!-- build:[\s\S]*?<!-- \/build:[^>]*-->/g, "").replace(/<span[^>]*data-fill[^>]*>[^<]*<\/span>/g, "FILL");
  for (const [money] of text(prose).matchAll(/\$\d[\d,]*(?:\.\d\d)?/g)) assert.ok(["$10", "$50"].includes(money), `${money} is typed into a lesson; it must come from data/learn-price-curve.json`);
});

test("one email opens it, and nothing inside a lesson sells", () => {
  const form = page.match(/<form[\s\S]*?<\/form>/)[0];
  assert.deepEqual([...form.matchAll(/<input\b[^>]*name="([^"]+)"/g)].map(([, n]) => n), ["email", "website"]);
  assert.match(form, /href="\/privacy#learn"/);
  const invite = page.match(/<aside class="invite"[\s\S]*?<\/aside>/)[0];
  assert.equal([...invite.matchAll(/<a\b/g)].length, 1);
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  assert.doesNotMatch(lessons, /href="\/apply"|\$6,000|Book your call|Managed Profit/);
  assert.doesNotMatch(text(page), /limited (spots|time)|countdown|hurry|act now|coming soon|unlock|game-changer/i);
});
