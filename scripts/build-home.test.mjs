// The home page as built: current with its data, inside the Hormozi standard,
// one action, and honest about what its figures are.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { figures, build, visibleWords } from "./build-home.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const html = read("index.html");
const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));

test("index.html is current with its data (node scripts/build-home.mjs)", () => {
  assert.equal(build(html, built), html);
});

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
  assert.deepEqual(otherLinks.sort(), ["/", "/privacy", "/terms"], "no navigation competes with the call");
});

test("the case study says what it is on its own screen", () => {
  const cs = html.match(/<section[^>]*id="case-study"[\s\S]*?<\/section>/)[0];
  assert.match(cs, /Modeled from public data · Not a client · Not a result/);
  assert.match(cs, /class="est">estimate</);
});

test("nothing from the retired funnel or the retired look", () => {
  for (const gone of ["Teardown", "Anton", "Fraunces", "Iowan", "#FFC000", "Demo data", "Start your free Proving Month"]) {
    assert.ok(!html.includes(gone), `"${gone}" is still on the page`);
  }
});

test("the page keeps no palette of its own", () => {
  const style = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  assert.doesNotMatch(style, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, "colours belong in /assets/hubricon.css");
});
