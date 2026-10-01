// The shared pieces, held to the honesty rules: the nav and footer on every public page,
// a planned course never presented as one that exists, an empty video slot that says so
// in the future tense, a testimonial only with consent, and a scoreboard illustration
// counted by the same rules as the terms.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { siteBlocks, counts, board, checkTestimonial } from "./site-blocks.mjs";
import { COURSES } from "../lib/learn.js";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const text = (h) => h.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<style[\s\S]*?<\/style>/g, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const lib = json("data/library.json");
const PUBLIC = ["index.html", "case-study.html", "honesty.html", "your-data.html", "terms.html", "privacy.html", "verify.html", "manifesto.html", "learn/index.html", "learn/fee-staircase.html", "learn/price-curve.html", "learn/fee-staircase-card.html", "learn/price-curve-card.html", "learn/capital-and-cash.html", "learn/capital-and-cash-card.html", "learn/shopify-margin.html", "learn/shopify-margin-card.html"];

test("every public page carries the one nav and the one footer, and the script that runs them", () => {
  const blocks = siteBlocks();
  for (const page of PUBLIC) {
    const h = read(page);
    assert.ok(h.includes(`<!-- build:nav -->${blocks.nav}<!-- /build:nav -->`), `${page}: the nav, as built`);
    assert.ok(h.includes(`<!-- build:foot -->${blocks.foot}<!-- /build:foot -->`), `${page}: the footer, as built`);
    assert.match(h, /src="\/assets\/(site|home)\.js"/, `${page}: loads the nav's script`);
    assert.equal((h.match(/<header class="nav"/g) || []).length, 1, `${page}: one bar`);
  }
  assert.match(read("assets/home.js"), /from "\.\/site\.js"/);
});

test("the library: live courses are the ones that exist; planned ones link nowhere, anywhere", () => {
  const live = lib.courses.filter((c) => c.status === "live");
  const planned = lib.courses.filter((c) => c.status === "planned");
  assert.deepEqual(live.map((c) => c.slug).sort(), Object.keys(COURSES).sort(), "live means signed up for in lib/learn.js");
  for (const c of live) assert.equal(c.path, COURSES[c.slug].path);
  for (const c of lib.courses) assert.ok(["live", "planned"].includes(c.status), `${c.slug}: live or planned, nothing in between`);
  for (const c of planned) {
    assert.equal(c.path, undefined, `${c.slug}: a planned course has no page to link to`);
    assert.ok(c.lessons.length > 0, `${c.slug}: a plan names its lessons`);
    for (const page of PUBLIC) {
      for (const [, inner] of read(page).matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
        assert.ok(!text(inner).includes(c.title), `${page}: "${c.title}" is planned, so no link carries it`);
      }
    }
  }
  for (const page of PUBLIC) assert.doesNotMatch(text(read(page)), /coming soon/i, page);
});

test("each live course's lessons are its page's lessons, each with its video slot", () => {
  const seen = new Set();
  for (const live of lib.courses.filter((c) => c.status === "live")) {
    const course = read(`${live.path.slice(1)}.html`);
    const ids = [...course.matchAll(/<article class="lesson" id="([^"]+)"/g)].map(([, id]) => id);
    assert.deepEqual(live.lessons.map((l) => l.id), ids, live.slug);
    for (const id of ids) {
      assert.match(course, new RegExp(`<!-- build:video-${id} -->`), `${live.slug}/${id}: a slot for its video`);
      assert.ok(!seen.has(id), `lesson id ${id} is used by two courses; video slots are keyed by it`);
      seen.add(id);
    }
  }
});

test("an empty video slot says, in the future tense, what will play there; a full one plays it", () => {
  const blocks = siteBlocks();
  const film = lib.films.case_study;
  if (film.src) assert.match(blocks["film-case"], new RegExp(`<video[^>]*src="${film.src}"`));
  else {
    assert.match(blocks["film-case"], /will play here/);
    assert.doesNotMatch(blocks["film-case"], /<video|play-button|▶/, "nothing pretends to play");
  }
  for (const c of lib.courses.filter((x) => x.status === "live")) {
    const trailer = blocks[`trailer-${c.slug}`];
    if (c.trailer && c.trailer.src) assert.match(trailer, /<video/);
    else assert.match(trailer, /will play here/, `${c.slug}: an empty trailer slot says what will play there`);
    assert.match(read(`${c.path.slice(1)}.html`), new RegExp(`<!-- build:trailer-${c.slug} -->`), `${c.slug}: the trailer slot sits on the cover`);
    for (const l of c.lessons) {
      const slot = blocks[`video-${l.id}`];
      if (l.video) assert.match(slot, /<video/);
      else {
        assert.match(slot, /will play here/, `${c.slug}#${l.id}: an empty lesson slot says what will play there`);
        assert.doesNotMatch(slot, /<video|play-button|▶/, "nothing pretends to play");
      }
    }
  }
  for (const c of lib.courses) {
    for (const v of [c.trailer, ...(c.lessons || []).map((l) => l.video)]) {
      assert.ok(v == null || (typeof v.src === "string" && /^(\/media\/|https:\/\/)/.test(v.src)), `${c.slug}: a video is null or a real src`);
    }
  }
});

test("the results wall: a client's own words with consent, a date and a Record month, or a reserved frame", () => {
  const list = json("data/testimonials.json").testimonials;
  list.forEach(checkTestimonial);
  const wall = siteBlocks().wall;
  assert.equal((wall.match(/frame-said/g) || []).length, list.length);
  assert.equal((wall.match(/frame-reserved/g) || []).length, Math.max(0, 3 - list.length));
  assert.throws(() => checkTestimonial({ client: "A", quote: "Great.", record_month: "2026-11" }), /consent_on/);
  assert.throws(() => checkTestimonial({ client: "A", quote: "Great.", consent_on: "yes", record_month: "2026-11" }), /date/);
  const home = read("index.html");
  assert.match(home, /id="wall-count">0</, "the wall reads zero until a result exists (spec, honesty rails)");
  assert.doesNotMatch(text(home), /\b(\d+\+? (happy )?clients|trusted by|as seen (in|on))\b/i, "no client count or logo bar");
});

test("the scoreboard illustration is counted by the terms' rules and labelled as an illustration", () => {
  assert.equal(counts({ grade: "isolated", expected: 1200, measured: 1340 }), 1200, "never above the promise");
  assert.equal(counts({ grade: "attributable", expected: 800, measured: 610 }), 610, "a miss stays at what it earned");
  assert.equal(counts({ grade: "direct", expected: 310, measured: 350 }), 350, "a direct dollar counts what was paid");
  assert.equal(counts({ grade: "isolated", expected: 90, measured: 18 }), 0, "nothing under $25");
  assert.equal(counts({ grade: "unmeasurable", expected: 500, measured: 500 }), 0, "unmeasurable banks nothing");
  const il = json("data/scoreboard-illustration.json");
  const month = il.moves.reduce((t, m) => t + counts(m), 0);
  const b = board(il);
  assert.ok(b.includes(`$${month.toLocaleString("en-US")}`));
  assert.ok(b.includes(`$${(il.proven_before_this_month + month).toLocaleString("en-US")}`));
  const rules = text(read("scripts/blocks/attribution.html"));
  for (const r of ["Never above the promise", "Nothing under $25", "Misses stay"]) assert.ok(rules.includes(r), `the terms still say "${r}"`);
  const sb = read("index.html").match(/<section[^>]*id="scoreboard"[\s\S]*?<\/section>/)[0];
  assert.match(sb, /Illustration · not a client's numbers/);
});

test("every trust tile points at the paragraph that says it", () => {
  const terms = read("terms.html");
  const trust = read("index.html").match(/<section[^>]*id="trust"[\s\S]*?<\/section>/)[0];
  for (const [, page, anchor] of trust.matchAll(/href="\/(terms|your-data|honesty)(?:#([a-z-]+))?"/g)) {
    if (anchor) assert.match(page === "terms" ? terms : read(`${page}.html`), new RegExp(`id="${anchor}"`), `/${page}#${anchor}`);
  }
  assert.match(terms, /<h2 id="invoicing">[\s\S]*?We keep no card on file/);
  assert.match(terms, /<h2 id="proving-month">[\s\S]*?never a percentage of your\s+ad spend/);
  assert.match(read("your-data.html"), /Never used to advise another client/);
});
