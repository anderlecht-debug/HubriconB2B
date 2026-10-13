import { test } from "node:test";
import assert from "node:assert/strict";
import { beats, chapters } from "./record.mjs";

const SCRIPT = `SCRIPT
[0:00] COLD OPEN
  VO: In {{y}} a store opened.
[0:30] CHAPTER — ONE PRICE
  VO: One price.
[0:33] THE CLERK
  VO: He was a clerk.
[1:10] CHAPTER — THE CEILING
  VO: The ceiling.
[1:13] THE RULE
  VO: Then it held.
`;

test("a chapter is read in one take: the open, then each chapter card and the beats after it", () => {
  const list = beats(SCRIPT, { y: { value: "1879" } });
  const ch = chapters(list);
  assert.deepEqual(ch.map((c) => [c.id, c.name, c.beats]), [
    ["c1", "The open", ["b1"]], ["c2", "ONE PRICE", ["b2", "b3"]], ["c3", "THE CEILING", ["b4", "b5"]]]);
  assert.equal(ch[1].text, "One price.\n\nHe was a clerk.");
});
