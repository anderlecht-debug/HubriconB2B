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
import { readFileSync, readdirSync } from "node:fs";
import { COURSES, composeLearnNote, NOTE_KINDS } from "../../lib/learn.js";
import { resolveFills } from "./note.mjs";

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

test("every lesson is open to anyone; the email is an opt-in that asks for nothing else", () => {
  // The founder, 2026-10-01: "I want the lessons to be open to everybody as that is the free
  // content that I am giving. Of course, if they want a little bit of extra, they can opt in the email."
  const css = read("assets/hubricon.css"), js = read("assets/learn.js");
  for (const src of [css, js]) assert.doesNotMatch(src, /learn-in/, "no state where a lesson waits for an email");
  assert.doesNotMatch(js, /api\/learn|\.courses\b/, "the course page asks for nothing before it shows a lesson");
  assert.match(css, /\.js \.course-page \.lesson\.current \{ display: block; \}/);
  for (const c of Object.values(COURSES)) {
    const page = read(`${c.path.slice(1)}.html`);
    const first = page.match(/<article class="lesson" id="([^"]+)"/)[1];
    assert.match(page, new RegExp(`<a class="btn" href="#${first}" data-start>Start lesson 1 `), `${c.path}: the cover starts lesson 1`);
    assert.match(text(page), /Every lesson and the spreadsheet are open\. No email, no account\./);
    assert.doesNotMatch(page, /learn-in|id="join"/);
    const forms = [...page.matchAll(/<form\b[\s\S]*?<\/form>/g)].map(([f]) => f);
    assert.equal(forms.length, 2, `${c.path}: the opt-in under the cover and at the end of the last lesson`);
    for (const form of forms) {
      assert.deepEqual([...form.matchAll(/<input\b[^>]*name="([^"]+)"/g)].map(([, n]) => n), ["email", "website"], "the address, and the hidden field bots fill");
      assert.match(form, /type="email"/);
      assert.doesNotMatch(form, /class="btn/, "the opt-in is never styled as the call");
      assert.match(form, /No email is needed to read it/);
      assert.match(form, /One click unsubscribes/);
      assert.match(form, /href="\/privacy#learn"/);
    }
    const lessons = [...page.matchAll(/<article class="lesson"[\s\S]*?<\/article>/g)].map(([a]) => a);
    assert.ok(lessons.at(-1).includes(forms[1]), `${c.path}: the second sits in the last lesson`);
  }
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

test("every lesson in every live course asks two questions before its task, each answer behind a click", () => {
  // Retrieval practice: trying to answer before reading the answer is what makes a lesson stay.
  for (const c of Object.values(COURSES)) {
    const page = read(`${c.path.slice(1)}.html`);
    const lessons = [...page.matchAll(/<article class="lesson" id="([^"]+)"[\s\S]*?<\/article>/g)];
    assert.ok(lessons.length >= 1, c.path);
    for (const [whole, id] of lessons) {
      const check = whole.match(/<div class="check">[\s\S]*?<\/ol>\s*<\/div>/)?.[0];
      assert.ok(check, `${c.path}#${id}: Check yourself`);
      assert.ok(whole.indexOf(check) < whole.indexOf('<div class="do">'), `${c.path}#${id}: the questions come before the task`);
      const items = [...check.matchAll(/<li>([\s\S]*?)<\/li>/g)].map(([, li]) => li);
      assert.equal(items.length, 2, `${c.path}#${id}: two questions`);
      for (const li of items) assert.match(li, /^<p>[\s\S]+?\?<\/p><details><summary>The answer<\/summary><p>[\s\S]+<\/p><\/details>$/, `${c.path}#${id}: a question, then its answer behind a click`);
    }
  }
});

test("on a phone nothing scrolls the page sideways, and a panel with nothing to say shows nothing", () => {
  // A table of six columns does not fit 390 pixels: it scrolls inside its own box.
  for (const c of Object.values(COURSES)) {
    const page = read(`${c.path.slice(1)}.html`);
    for (const m of page.matchAll(/<table class="data">[\s\S]*?<\/thead>/g)) {
      if ((m[0].match(/<th scope="col">/g) || []).length < 6) continue;
      const before = page.slice(0, m.index);
      assert.match(before.slice(before.lastIndexOf("<div")), /^<div class="(table-scroll|card-table)" role="region" aria-label="[^"]+" tabindex="0">\s*$/, `${c.path}: a wide table scrolls in its own box`);
    }
  }
  // The [hidden] attribute beats a panel's own display, so an empty reading is never an empty box.
  assert.match(read("assets/hubricon.css"), /\.course-page \[hidden\] \{ display: none !important; \}/);
});

test("every note drafted for the list composes, types no figure the course computes, and never sells", () => {
  const dir = new URL("scripts/learn/notes/", root);
  const drafts = readdirSync(dir).filter((f) => f.endsWith(".json"));
  assert.ok(drafts.length >= 1);
  for (const f of drafts) {
    const raw = JSON.parse(readFileSync(new URL(f, dir), "utf8"));
    assert.equal(`${raw.id}.json`, f, "a note's file is named for its id");
    assert.ok(Object.hasOwn(NOTE_KINDS, raw.kind));
    const typed = JSON.stringify(raw).replace(/\{fill:[^}]+\}/g, "").match(/\$\d[\d.,]*|\d+(\.\d+)?%/g) || [];
    for (const t of typed) assert.ok(["$10", "$50"].includes(t), `${f}: ${t} is typed; it must be a {fill:…} from the course page`);
    const note = resolveFills(raw);
    assert.doesNotMatch(JSON.stringify(note), /\{fill:/);
    const m = composeLearnNote({ note, unsubscribeUrl: "https://www.hubricon.com/api/learn?unsubscribe=" + "0".repeat(32) });
    assert.match(m.text, /Unsubscribe/);
  }
  assert.throws(() => resolveFills("{fill:fee-staircase:no_such_key}"), /no figure no_such_key/);
});

test("each course on one page: eight cells, each pointing at a lesson that teaches it, no figure typed, one printed page", () => {
  const css = read("assets/hubricon.css");
  assert.match(css, /body\.sheet-page > :not\(main\)[^{]*\{ display: none !important; \}/, "printed, the bar and the footer go");
  assert.match(css, /@media print \{[\s\S]*?\.sheet \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/, "two columns on paper, whatever the width");
  for (const c of Object.values(COURSES)) {
    const card = read(`${c.card.slice(1)}.html`), page = read(`${c.path.slice(1)}.html`);
    assert.ok(page.includes(`href="${c.card}"`), `${c.path} links its one page`);
    const cells = [...card.matchAll(/<section class="sheet-cell"[\s\S]*?<\/section>/g)].map(([s]) => s);
    assert.equal(cells.length, 8, c.card);
    for (const cell of cells) {
      const [, path, id] = cell.match(/class="sheet-more" href="([^"#]+)#([^"]+)"/);
      assert.equal(path, c.path);
      assert.match(page, new RegExp(`<article class="lesson" id="${id}"`), `${c.card} points at a lesson that exists: ${id}`);
    }
    const prose = text(card.replace(/<!-- build:[\s\S]*?<!-- \/build:[^>]*-->/g, "").replace(/<span[^>]*data-fill[^>]*>[^<]*<\/span>/g, "FILL"));
    for (const [m] of prose.matchAll(/\$\d+(?:,\d{3})*(?:\.\d+)?/g)) assert.ok(["$10", "$50", "$0.01"].includes(m), `${c.card}: ${m} is typed; it must be a fill`);
    for (const [, key, shown] of card.matchAll(/data-fill="([a-z0-9_]+)">([^<]*)</g)) {
      const onCourse = page.match(new RegExp(`data-fill="${key}"[^>]*>([^<]*)<`));
      assert.ok(onCourse, `${key} is a figure the course itself prints`);
      assert.equal(shown, onCourse[1], `${c.card} and ${c.path} print the same ${key}`);
    }
    assert.match(text(card), /Every lesson is open; no email needed\./);
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
