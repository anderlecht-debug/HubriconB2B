import { test } from "node:test";
import assert from "node:assert/strict";
import { pace } from "./pace.mjs";

const take = (lead, voiced, tail, sr = 8000) => {
  const s = new Float32Array(Math.round((lead + voiced + tail) * sr));
  for (let i = Math.round(lead * sr); i < Math.round((lead + voiced) * sr); i++) s[i] = 0.3 * Math.sin(i / 3);
  return s;
};

test("a take's pace counts only its voiced span, not the silence around it", () => {
  const p = pace(take(2, 30, 3), 8000, 80);          // 80 words in 30 s of voice: 160 wpm
  assert.equal(p.verdict, "good");
  assert.ok(Math.abs(p.wpm - 160) <= 2 && Math.abs(p.seconds - 30) <= 0.1);
});

test("a rushed take and a dragging one are named, with what to do", () => {
  assert.equal(pace(take(0.5, 20, 0.5), 8000, 80).verdict, "fast");     // 240 wpm
  assert.match(pace(take(0.5, 60, 0.5), 8000, 80).note, /slow/);        // 80 wpm
  assert.equal(pace(new Float32Array(8000), 8000, 10).verdict, "silent");
});
