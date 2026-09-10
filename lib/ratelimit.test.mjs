import { test } from "node:test";
import assert from "node:assert/strict";
import { SlidingWindow, clientIp } from "./ratelimit.js";

test("allows up to the limit inside the window, then refuses with a retry time", () => {
  const w = new SlidingWindow({ limit: 3, windowMs: 1000 });
  assert.equal(w.hit("a", 0).ok, true);
  assert.equal(w.hit("a", 100).ok, true);
  assert.equal(w.hit("a", 200).ok, true);
  const r = w.hit("a", 300);
  assert.equal(r.ok, false);
  assert.equal(r.retryAfterMs, 700);
  assert.equal(w.hit("b", 300).ok, true, "keys are independent");
});

test("the window slides: old hits expire", () => {
  const w = new SlidingWindow({ limit: 2, windowMs: 1000 });
  w.hit("a", 0); w.hit("a", 10);
  assert.equal(w.hit("a", 500).ok, false);
  assert.equal(w.hit("a", 1011).ok, true);
});

test("prunes idle keys so the map cannot grow without bound", () => {
  const w = new SlidingWindow({ limit: 1, windowMs: 10, maxKeys: 5 });
  for (let i = 0; i < 20; i++) w.hit(`k${i}`, i);
  w.prune(1000);
  assert.equal(w.hits.size, 0);
});

test("takes the first forwarded hop as the client", () => {
  const h = new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" });
  assert.equal(clientIp(h), "203.0.113.7");
  assert.equal(clientIp(new Headers()), "unknown");
});
