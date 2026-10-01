// The baked pages, as built: current with their data, the home page inside the
// Hormozi standard with one action, the attribution rules identical wherever they
// appear, and every page honest about what its figures are.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { figures, build, visibleWords, PAGES } from "./build-pages.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const html = read("index.html");
const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
const text = (h) => h.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

for (const page of PAGES) {
  test(`${page.file} is current with its data (node scripts/build-pages.mjs)`, () => {
    const before = read(page.file);
    assert.equal(build(before, built, { requireAllFills: page.requireAllFills, name: page.file }), before);
  });
}

test("under about 900 words on load", () => {
  const n = visibleWords(html);
  assert.ok(n <= 900, `${n} visible words`);
});

test("one action: every button says the same thing and goes to the same place", () => {
  const ctas = [...html.matchAll(/<a\b[^>]*data-cta="[^"]+"[^>]*>([\s\S]*?)<\/a>/g)];
  assert.ok(ctas.length >= 3, "the call to action repeats after each proof block");
  for (const [tag, inner] of ctas) {
    assert.match(tag, /href="\/apply"/);
    assert.equal(inner.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim(), "Book your call →");
  }
  const otherLinks = [...html.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map(([, h]) => h).filter((h) => h !== "/apply");
  assert.deepEqual([...new Set(otherLinks)].sort(), ["/", "/honesty", "/privacy", "/terms", "/your-data"],
    "no navigation competes with the call: the wordmark, a data answer, and the footer");
});

test("the case study says what it is on its own screen", () => {
  const cs = html.match(/<section[^>]*id="case-study"[\s\S]*?<\/section>/)[0];
  assert.match(cs, /Modeled from public data · Not a client · Not a result/);
  assert.match(cs, /class="est">estimate</);
});

test("nothing from the retired funnel or the retired look", () => {
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "portal.html", "intake.html", "welcome.html"]) {
    const h = read(page);
    for (const gone of ["Teardown", "Anton", "Fraunces", "Iowan", "#FFC000", "Demo data", "Start your free Proving Month"]) {
      assert.ok(!h.includes(gone), `"${gone}" is still on ${page}`);
    }
  }
});

test("no page on the design system keeps a palette of its own", () => {
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "portal.html", "terms.html", "privacy.html", "intake.html", "welcome.html"]) {
    const style = read(page).match(/<style>([\s\S]*?)<\/style>/)[1];
    assert.doesNotMatch(style, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, `${page}: colours belong in /assets/hubricon.css`);
    assert.match(read(page), /href="\/assets\/hubricon\.css"/);
  }
});

test("the terms and /honesty carry the attribution rules word for word", () => {
  const block = text(read("scripts/blocks/attribution.html"));
  for (const page of ["terms.html", "honesty.html", "portal.html"]) assert.ok(text(read(page)).includes(block), `${page} has drifted`);
});

test("the rules claim only the guards the engine enforces", () => {
  const block = text(read("scripts/blocks/attribution.html"));
  // measurement.py enforces the cap, the $25 floor and one dollar, one move; persistence is not yet code.
  assert.match(block, /Three rules apply to every dollar/);
  assert.match(block, /Nothing under \$25/);
  assert.doesNotMatch(block, /it has to last|only if it lasts|still be there in your latest export/i);
  const engine = read("engine/src/hubricon_engine/measurement.py");
  assert.match(engine, /^MEASURE_MIN_USD = 25\.0/m);
  assert.match(engine, /^MEASUREMENT_HORIZON_DAYS = 30/m);
});

test("/honesty says there are no client results before it says anything else", () => {
  const h = read("honesty.html");
  const firstHeading = h.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)[1];
  assert.equal(firstHeading.trim(), "No client results yet.");
  const silent = json("data/case-study.json").selection;
  assert.ok(text(h).includes(`${silent.brands_silent.toLocaleString("en-US")} of ${silent.brands_modeled.toLocaleString("en-US")}`));
});
