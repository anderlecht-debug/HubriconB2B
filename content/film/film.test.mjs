// The films: one scene per approved beat, every figure the site's own, every case-study
// figure labelled, every word on screen one the site or the script already uses, and
// the recorder's teleprompter reading exactly what the script says.
//   node --test content/film/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkBoard } from "./check.mjs";
import { beats } from "./record.mjs";
import { sceneHTML, STYLE_REEL, fill, FILM_CHART } from "./scenes.mjs";
import { figures } from "../../scripts/build-pages.mjs";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
const FILMS = ["case-study-film", "october-15"];

for (const slug of FILMS) {
  const board = json(`content/videos/${slug}/board.json`);
  const script = read(`content/videos/${slug}/script.md`);
  const facts = json(`content/videos/${slug}/facts.json`);

  test(`${slug}: one scene for every beat of the script, in order`, () => {
    const b = beats(script, facts);
    assert.deepEqual(board.scenes.map((s) => s.id), b.map((x) => x.id));
  });

  test(`${slug}: the pre-publish checklist passes on the board`, () => {
    assert.deepEqual(checkBoard(board, { scriptText: script }), []);
  });

  test(`${slug}: the teleprompter reads the script with every figure filled`, () => {
    for (const b of beats(script, facts)) assert.doesNotMatch(b.text, /\{\{|\}\}/);
  });
}

test("the style reel says only what the home page already says, with the site's figures", () => {
  assert.deepEqual(checkBoard(STYLE_REEL), []);
  for (const s of STYLE_REEL.scenes) assert.ok(sceneHTML(s, built).length > 100);
});

test("a chart scene is the site's own chart code, drawn at film size, under its label", () => {
  const html = sceneHTML({ id: "x", kind: "staircase", heading: "h" }, built);
  assert.ok(html.includes(FILM_CHART.staircase(built.charts)), "the home page's staircase function, not a redrawing");
  assert.match(FILM_CHART.staircase(built.charts), /font-size="30"/, "labels a phone can read");
  assert.match(html, /Modeled from public data · Not a client · Not a result/);
});

test("a figure that is not money is drawn in ink; blue stays for money and the leak", () => {
  assert.match(sceneHTML({ id: "x", kind: "number", value: "{{weight}}", ink: true }, built), /class="number ink in"/);
});

test("an unknown figure is an error, never a guess", () => {
  assert.throws(() => fill("{{no_such_figure}}", built.fill));
  assert.throws(() => beats("[0:00] HOOK\n  VO: {{nope}}\n", {}));
});
