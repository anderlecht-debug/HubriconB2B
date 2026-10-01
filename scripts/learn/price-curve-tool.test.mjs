// The Price Curve's browser arithmetic (assets/price-curve.mjs) is the engine's, held to golden
// cases the engine itself computed (scripts/learn/price_curve.py: models/elasticity.py `_fit`,
// models/pricing_engine.py). A reader who types their own history into the course gets the
// numbers Hubricon's engine would give.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import * as pc from "../../assets/price-curve.mjs";

const root = new URL("../../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const golden = JSON.parse(read("scripts/learn/price-curve.golden.json"));
const near = (a, b, tol = 1.5e-4) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(b));

test("the golden cases are from the engine as it is today", () => {
  for (const [file, hash] of Object.entries(golden.engine_sha256)) {
    assert.equal(hash, createHash("sha256").update(readFileSync(new URL(file, root))).digest("hex"),
      `${file} changed; run: cd engine && uv run --with openpyxl python ../scripts/learn/price_curve.py --publish`);
  }
});

test("the t table is scipy's, to six places", () => {
  for (let d = 1; d < golden.t975.length; d++) assert.ok(Math.abs(pc.T975[d] - golden.t975[d]) < 1e-6, `dof ${d}: ${pc.T975[d]} vs ${golden.t975[d]}`);
});

test("the fit reads every history as the engine's _fit does", () => {
  for (const [i, { points, want }] of golden.fits.entries()) {
    const got = pc.fit(points);
    assert.equal(got.status, want.status, `case ${i}`);
    assert.equal(got.n, want.n, `case ${i}: periods used`);
    if (want.status !== "ok") continue;
    for (const [k, g] of [["elasticity", got.elasticity], ["std_err", got.stdErr], ["r_squared", got.rSquared], ["t", got.t], ["price_cv", got.priceCv], ["std_err_classical", got.stdErrClassical]]) {
      assert.ok(near(g, want[k]), `case ${i}: ${k} ${g} vs engine ${want[k]}`);
    }
    assert.ok(near(got.ci[0], want.ci[0]) && near(got.ci[1], want.ci[1]), `case ${i}: interval`);
    assert.equal(got.dof, want.dof);
    assert.equal(got.seEstimator, want.se_estimator);
    assert.equal(pc.nearUnitElastic(got.elasticity, got.stdErr, got.ci), want.guard, `case ${i}: the guard against −1`);
  }
});

test("the best price, the guard, the step and its worth are the engine's", () => {
  for (const [i, { row, want }] of golden.rows.entries()) {
    const g = pc.nearUnitElastic(row.eps, row.se, [row.lo, row.hi]);
    assert.equal(g, want.guard, `row ${i}: guard`);
    const best = g ? null : pc.bestPrice(row.eps, row.cost, row.referral, row.fixed);
    if (want.best === null) assert.equal(best, null, `row ${i}: no best price`);
    else assert.ok(near(best, want.best, 1e-9), `row ${i}: best ${best} vs ${want.best}`);
    const way = pc.direction(row.eps, row.price, best, g);
    assert.equal(way, want.way, `row ${i}: direction`);
    const next = pc.stepPrice(row.price, best, way);
    assert.ok(Math.abs(next - want.next) < 0.005, `row ${i}: next ${next} vs ${want.next}`);
    assert.ok(near(pc.profitDelta(row.eps, row.price, row.units, row.cost, row.referral, want.next, row.fixed), want.delta, 1e-9), `row ${i}: change a month`);
    assert.ok(near(pc.profit(row.eps, row.price, row.units, row.cost, row.referral, row.price, row.fixed), want.profit, 1e-9), `row ${i}: profit`);
    assert.equal(pc.crossesEdge(row.price, best ?? next), want.crosses, `row ${i}: fee edge`);
  }
});

test("the worked example reads the same in the browser as on the page", () => {
  const fig = JSON.parse(read("data/learn-price-curve.json"));
  const e = fig.economics;
  const r = pc.read(fig.history, { price: e.price, units: e.units_month, cost: e.landed_cost, referral: e.referral, fixed: e.fixed, discount: fig.discount.rate });
  assert.ok(near(r.fit.elasticity, fig.fit.elasticity));
  assert.ok(near(r.best, fig.best.price, 1e-3));
  assert.equal(r.next, fig.best.step_price);
  assert.ok(Math.abs(r.nextDelta - fig.best.step_delta) < 0.5);
  assert.ok(near(r.discount.needed, fig.discount.needed, 1e-9));
});

test("the reader's numbers stay in their browser, and the course reads without scripts", () => {
  const js = readFileSync(new URL("assets/learn-price-curve.js", root), "utf8");
  const page = readFileSync(new URL("learn/price-curve.html", root), "utf8");
  assert.doesNotMatch(js, /fetch\(|XMLHttpRequest|sendBeacon|WebSocket|navigator\.share|\bva\(|track\(/, "nothing the reader types is sent anywhere, or counted");
  assert.match(js, /localStorage/, "kept in their own browser");
  assert.match(page, /<section class="yours" id="yours" hidden/, "without scripts the panel never shows; the lessons and the spreadsheet stand alone");
  for (const k of ["fit", "best", "raise", "discount", "next"]) assert.match(page, new RegExp(`data-yours="${k}" hidden`), `lesson reading: ${k}`);
  assert.match(page, /<section class="memo" data-yours="memo" hidden/);
  assert.match(page, /Nothing you type leaves it\./);
  assert.match(readFileSync(new URL("privacy.html", root), "utf8"), /numbers you type into a course's own\s+calculator/);
  const css = readFileSync(new URL("assets/hubricon.css", root), "utf8");
  assert.match(css, /body\.course-page\.has-memo > :not\(\.memo\) \{ display: none !important; \}/, "the memo prints alone, and only once there is one");
});
