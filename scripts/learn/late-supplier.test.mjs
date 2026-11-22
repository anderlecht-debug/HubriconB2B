// The Late Supplier (/learn/late-supplier): the arithmetic its figures teach, the labels its
// simulated figures carry, and the page agreeing with its data and its worksheet.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import * as F from "../../assets/learn-late-supplier.mjs";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const data = JSON.parse(read("data/learn-late-supplier.json"));
const page = read("learn/late-supplier.html");

test("the 1-in-10 figure is computed the way the worksheet's PERCENTILE computes it", () => {
  assert.equal(Math.round(F.p90([11, -1, 18, -1]) * 10) / 10, 15.9);
  assert.equal(F.p90([7]), 7);
  assert.equal(F.p90(Array.from({ length: 11 }, (_, i) => i)), 9);
});

test("lesson 4: a stockout loses margin on lost sales; cover costs only its carrying", () => {
  const c = F.cost({ sales: 30000, margin: 50, late: 10, carry: 20 });
  assert.equal(c.perDay, 1000);
  assert.equal(c.stockout, 5000);
  assert.equal(c.cash, 5000);
  assert.equal(c.carrying, 1000);
});

test("lesson 6: the reorder point is a day's sales × (promised + 1-in-10 late + shipping)", () => {
  const r = F.reorder({ daily: 10, onHand: 1000, promised: 30, late: 10, transit: 20 });
  assert.equal(r.point, 600);
  assert.equal(r.cover, 100);
  assert.equal(r.onReal, 40);
  assert.equal(r.onPromise, 50);
  assert.equal(r.extraUnits, 100);
});

test("lesson 5 reads pasted rows with a header in any order, and skips what it can't read", () => {
  const { rows, skipped } = F.parseOrders("actual ready,order date,supplier,promised\n2026-02-15,2026-01-01,Acme,2026-02-05\nnot,a,row,here");
  assert.equal(skipped, 1);
  assert.deepEqual(rows.map((r) => [r.sup, r.late]), [["Acme", 10]]);
  const s = F.score([...rows, { sup: "Acme", late: -2 }]);
  assert.equal(s[0].onTime, 0.5);
});

test("every simulated figure on the page is labelled as one, and its numbers come from the data file", () => {
  const figs = [...page.matchAll(/<figure class="ls-fig[^"]*" data-fig="([a-z]+)"[\s\S]*?<\/figure>/g)];
  assert.equal(figs.length, 6);
  for (const [f, name] of figs) {
    if (["promise", "busy", "calendar"].includes(name)) assert.match(f, /Simulated · Not a client · Not a result/, `${name} is simulated and says so`);
    else if (name !== "measure") assert.match(f, /Arithmetic/, `${name} is arithmetic on the reader's numbers and says so`);
  }
  assert.ok(page.includes(`>${data.typical.on_time}%</span>`), "lesson 1's on-time share is the data's");
  assert.ok(page.includes(data.about) === false && data.about.includes("Not a client"));
  assert.match(page, /none is published yet/, "the pooling result is a simulation, and the page says no real one is out");
});

test("the worksheet the page links to exists", () => {
  for (const [, href] of page.matchAll(/href="(\/learn\/files\/[^"]+)"/g)) assert.ok(existsSync(new URL(`.${href}`, root)), href);
});
