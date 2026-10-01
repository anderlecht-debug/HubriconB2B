// /learn, held to HUBRICON_SPEC.md's "Education hub": one card per course that exists
// in full, one email to enter, three columns, the spreadsheet under every lesson, a
// standing invitation to the call and nothing for sale inside, in every footer and one
// quiet card on the home page. And the spreadsheet: built from the card the engine prices with, and
// re-verified whenever that card or the file moves.
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

test("the hub shows one card per course that exists, and no card for anything else", () => {
  const cards = [...hub.matchAll(/<a class="card" href="([^"]+)"/g)].map(([, h]) => h);
  assert.deepEqual(cards.sort(), Object.values(COURSES).map((c) => c.path).sort());
  assert.doesNotMatch(text(hub), /coming soon|soon|waitlist/i);
  const main = hub.slice(hub.indexOf("<main"), hub.indexOf("</main>"));
  assert.ok(text(main).split(" ").length < 200, "under two hundred words of page copy");
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

test("/learn is in every footer, and on the home page as one quiet card, never a button", () => {
  // The founder put the free training on the home page on 2026-10-01; the call stays the only button.
  const home = read("index.html");
  const body = home.slice(home.indexOf("<body"), home.indexOf('<footer class="foot">'));
  const links = [...body.matchAll(/<a\b([^>]*)href="(\/learn[^"]*)"/g)];
  assert.equal(links.length, 1, "one course card in the home page's body");
  assert.match(links[0][1], /class="go-card course"/);
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "terms.html", "privacy.html"]) {
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
