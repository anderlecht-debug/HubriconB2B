// /learn, held to HUBRICON_SPEC.md's "Education hub" as the founder amended it on
// 2026-10-01: a tile per course, live ones linked and planned ones labelled and linked
// nowhere, one email to enter, three columns, the spreadsheet under every lesson, a
// standing invitation to the call and nothing for sale inside, an Education tab on every
// page. And the spreadsheet: built from the card the engine prices with, and re-verified
// whenever that card or the file moves.
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

const hub = read("learn/index.html");
const course = read("learn/fee-staircase.html");

test("the hub links every live course and only those; a planned one says so and goes nowhere", () => {
  const main = hub.slice(hub.indexOf("<main"), hub.indexOf("</main>"));
  const links = [...new Set([...main.matchAll(/<a\b[^>]*href="(\/learn\/[a-z-]+)"/g)].map(([, h]) => h))];
  assert.deepEqual(links.sort(), Object.values(COURSES).map((c) => c.path).sort());
  const planned = [...main.matchAll(/<article class="tile tile-planned"[\s\S]*?<\/article>/g)].map(([t]) => t);
  assert.ok(planned.length >= 1);
  for (const t of planned) {
    assert.doesNotMatch(t, /<a\b/, "a planned course links nowhere");
    assert.match(t, />Planned</);
    assert.doesNotMatch(text(t), /\b(19|20)\d\d\b|January|February|March|April|June|July|August|September|October|November|December|Q[1-4]\b/, "a plan names no date");
  }
  assert.doesNotMatch(text(hub), /coming soon|\bsoon\b|waitlist|launching/i);
  const own = main.replace(/<!-- build:library-hub -->[\s\S]*?<!-- \/build:library-hub -->/, "");
  assert.ok(text(own).split(" ").length < 80, "the hub's own copy stays short; the library speaks for itself");
});

test("no hype furniture anywhere in /learn", () => {
  for (const page of [hub, course]) {
    assert.doesNotMatch(text(page), /limited (spots|time)|only \d+ (left|spots)|countdown|hurry|act now|enrolled|students|unlock|game-changer|leverage/i);
  }
});

test("one email opens the course, and the form asks for nothing else", () => {
  const form = course.match(/<form[\s\S]*?<\/form>/)[0];
  const fields = [...form.matchAll(/<input\b[^>]*name="([^"]+)"/g)].map(([, n]) => n);
  assert.deepEqual(fields, ["email", "website"], "the address, and the hidden field bots fill");
  assert.match(form, /type="email"/);
  assert.match(form, /one click unsubscribes/);
  assert.match(form, /href="\/privacy#learn"/);
  assert.match(read("privacy.html"), /id="learn"/);
});

test("three columns: the lessons, the lesson with the spreadsheet under its head, the invitation", () => {
  assert.match(course, /<details class="toc"/);
  assert.match(course, /<main class="lesson-col"/);
  assert.match(course, /<aside class="invite"/);
  const lessons = [...course.matchAll(/<article class="lesson" id="([^"]+)"[\s\S]*?<\/article>/g)];
  const toc = [...course.matchAll(/<li><a href="#([^"]+)">/g)].map(([, id]) => id);
  assert.equal(lessons.length, 8);
  assert.deepEqual(lessons.map(([, id]) => id), toc, "the list on the left is the lessons, in order");
  for (const [whole, id] of lessons) {
    const afterHead = whole.slice(whole.indexOf("</header>"));
    assert.match(afterHead.slice(0, 400), /class="tpl"[\s\S]*href="\/learn\/files\/hubricon-fee-staircase\.xlsx"/, `${id}: the spreadsheet sits directly under the lesson's head`);
    assert.match(whole, /<div class="do">/, `${id}: ends with something to do`);
  }
});

test("the invitation is one quiet call to the call; nothing inside a lesson sells", () => {
  const invite = course.match(/<aside class="invite"[\s\S]*?<\/aside>/)[0];
  assert.equal([...invite.matchAll(/<a\b/g)].length, 1);
  assert.match(invite, /href="\/apply"/);
  const lessons = course.slice(course.indexOf('<article class="lesson"'), course.lastIndexOf("</article>"));
  assert.doesNotMatch(lessons, /href="\/apply"|\$6,000|Book your call|Managed Profit/, "no second ask inside the content");
});

test("every case-study figure in the course wears its label; every invented example says so", () => {
  const figures = [...course.matchAll(/<figure[\s\S]*?<\/figure>/g)].map(([f]) => f);
  assert.ok(figures.length >= 3);
  for (const f of figures) assert.match(f, /Modeled from public data · Not a client · Not a result/);
  const worked = [...course.matchAll(/<div class="worked">[\s\S]*?<\/div>/g)].map(([w]) => w);
  for (const w of worked) assert.match(w, /Modeled from public data · Not a client · Not a result|an invented listing/);
});

test("/learn is in every footer and the Education tab; on the home page it is never a button", () => {
  // The founder put the free training on the home page and in the bar on 2026-10-01; the call stays the only button.
  const home = read("index.html");
  for (const [tag] of home.matchAll(/<a\b[^>]*href="\/learn[^"]*"[^>]*>/g)) assert.doesNotMatch(tag, /class="btn/, tag);
  const learn = home.match(/<section[^>]*id="learn"[\s\S]*?<\/section>/)[0];
  assert.match(learn, /<h3><a href="\/learn\/fee-staircase">The Fee Staircase<\/a><\/h3>/, "the featured course links to its page");
  assert.match(learn, /<form class="join-tile" data-join="fee-staircase"/, "and opens from one email, where Acquisition.com asks for it");
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "terms.html", "privacy.html", "learn/index.html", "learn/fee-staircase.html"]) {
    const h = read(page);
    const foot = h.slice(h.lastIndexOf("<footer"));
    assert.match(foot, /href="\/learn"/, `${page}'s footer`);
  }
});

test("the spreadsheet was verified against the engine on today's card, and has not moved since", () => {
  const stamp = JSON.parse(read("scripts/learn/fee-staircase.stamp.json"));
  const rerun = "run: uv run --no-project --with openpyxl python scripts/learn/verify_fee_staircase.py --publish";
  assert.equal(stamp.ratecard_sha256, sha("ratecard.json"), `ratecard.json changed since the template was verified; ${rerun}`);
  assert.equal(stamp.file_sha256, sha(stamp.file), `the template changed without being re-verified; ${rerun}`);
  assert.ok(stamp.golden_cases >= 40);
  const gen = read("scripts/learn/fee_staircase_template.py");
  assert.match(gen, /ratecard\.json/, "the fees come from the engine's card, not typed in");
});
