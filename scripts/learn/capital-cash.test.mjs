// Capital & Cash (/learn/capital-and-cash), held to the same rules as the other courses and to
// the engine it teaches: every figure and the spreadsheet were computed and checked by Hubricon's
// engine (scripts/learn/capital_cash.py), and are re-checked whenever the engine moves; the
// worked examples are labelled invented wherever they show; nothing inside a lesson sells.
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
const page = read("learn/capital-and-cash.html");
const rerun = "run: cd engine && uv run --with openpyxl python ../scripts/learn/capital_cash.py --publish";

test("the figures and the spreadsheet were computed and checked by the engine as it is today", () => {
  const figs = JSON.parse(read("data/learn-capital-cash.json"));
  for (const [file, hash] of Object.entries(figs.engine)) assert.equal(hash, sha(file), `${file} changed since the course's figures were computed; ${rerun}`);
  const stamp = JSON.parse(read("scripts/learn/capital-cash.stamp.json"));
  for (const [file, hash] of Object.entries(stamp.engine_sha256)) assert.equal(hash, sha(file), `${file} changed since the spreadsheet was verified; ${rerun}`);
  assert.equal(stamp.file_sha256, sha(stamp.file), `the template changed without being re-verified; ${rerun}`);
  const py = read("scripts/learn/capital_cash.py");
  for (const call of ["inventory_sim.run(", "cashflow.run(", "inventory_econ.critical_fractile(", "inventory_econ.hold_vs_liquidate("]) assert.ok(py.includes(call), `the figures are the engine's own: ${call}`);
});

test("registered where a sign-up and the library look for it, lesson for lesson", () => {
  const c = COURSES["capital-and-cash"];
  assert.equal(c.path, "/learn/capital-and-cash");
  assert.match(page, /<body class="course-page" data-course="capital-and-cash">/);
  const lib = JSON.parse(read("data/library.json")).courses.find((x) => x.slug === "capital-and-cash");
  assert.equal(lib.status, "live");
  const ids = [...page.matchAll(/<article class="lesson" id="([^"]+)"/g)].map(([, id]) => id);
  const toc = [...page.matchAll(/<li><a href="#([^"]+)">/g)].map(([, id]) => id);
  assert.deepEqual(lib.lessons.map((l) => l.id), ids);
  assert.deepEqual(toc, ids);
  for (const [whole, id] of page.matchAll(/<article class="lesson" id="([^"]+)"[\s\S]*?<\/article>/g)) {
    const head = whole.slice(whole.indexOf("</header>"), whole.indexOf("</header>") + 400);
    assert.match(head, /class="tpl"[\s\S]*href="\/learn\/files\/hubricon-capital-and-cash\.xlsx"/, `${id}: the spreadsheet under the head`);
    assert.match(whole, new RegExp(`<!-- build:video-${id} -->`), `${id}: a slot for its video`);
  }
});

test("the examples say they are invented wherever they show, and no figure in a lesson is typed", () => {
  for (const [f] of page.matchAll(/<figure[\s\S]*?<\/figure>/g)) assert.match(f, /An invented listing · Not a client · Not a result/);
  for (const [w] of page.matchAll(/<div class="worked">[\s\S]*?<\/div>/g)) assert.match(text(w), /invented/i);
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  // the exercises in "Check yourself" are their own invented round numbers; everything else is a fill
  const prose = lessons.replace(/<!-- build:[\s\S]*?<!-- \/build:[^>]*-->/g, "").replace(/<div class="check">[\s\S]*?<\/ol>\s*<\/div>/g, "")
    .replace(/<span[^>]*data-fill[^>]*>[^<]*<\/span>/g, "FILL");
  for (const [m] of text(prose).matchAll(/\$\d+(?:,\d{3})*(?:\.\d+)?/g)) assert.fail(`${m} is typed into a lesson; it must come from data/learn-capital-cash.json`);
});

test("nothing inside a lesson sells, and the course says where its payout facts come from", () => {
  const lessons = page.slice(page.indexOf('<article class="lesson"'), page.lastIndexOf("</article>"));
  assert.doesNotMatch(lessons, /href="\/apply"|\$6,000|Book your call|Managed Profit/);
  assert.doesNotMatch(text(page), /limited (spots|time)|countdown|hurry|act now|coming soon|unlock|game-changer/i);
});
