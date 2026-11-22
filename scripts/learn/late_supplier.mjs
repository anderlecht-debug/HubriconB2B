// The Late Supplier's figures (/learn/late-supplier), from Hubricon's supplier simulation
// (assets/lateness-sim.mjs, the same model /lateness runs in the browser). Writes
// data/learn-late-supplier.json; scripts/build-pages.mjs bakes the course's still frames from it
// and the page's script reads the same numbers, so what a visitor sees before and after the
// script runs is one set of figures. Every number here is simulated: not a client, not a result.
//
//   node scripts/learn/late_supplier.mjs
import { writeFileSync } from "node:fs";
import { simulate, summarize, PROMISE, MIN_PT } from "../../assets/lateness-sim.mjs";

const SEEDS = 200;                         // suppliers per load, as in /lateness's Fig. 2
const FOCUS = 0.85;                        // "busy": the load the lessons start from
const r1 = (v) => Math.round(v * 10) / 10;
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };

// Lesson 2: lateness by how busy the supplier is, the typical supplier and the middle 80%
const loads = [];
for (let L = 50; L <= 95; L += 1) {
  const S = Array.from({ length: SEEDS }, (_, i) => summarize(simulate(L / 100, i + 1)));
  loads.push({
    busy: L,
    on_time: Math.round(q(S.map((s) => s.onTime), 0.5) * 100),
    p90: r1(q(S.map((s) => s.p90), 0.5)),
    p90_lo: r1(q(S.map((s) => s.p90), 0.1)),
    p90_hi: r1(q(S.map((s) => s.p90), 0.9)),
    // waiting in line, as a multiple of a half-busy supplier's: rho / (1 - rho), the textbook queue
    wait_x: r1((L / 100) / (1 - L / 100)),
  });
}

// Lesson 1: one typical supplier at 85% busy, every order it took in one year: the supplier
// whose year sits closest to the median of the 200 on both its on-time share and its 1-in-10 lateness
const yearOf = (seed) => { const l = simulate(FOCUS, seed); return [...l].map((v, i) => ({ day: l.when[i], late: r1(v) })).filter((o) => o.day < 365); };
const years = Array.from({ length: SEEDS }, (_, i) => { const o = yearOf(i + 1); return { seed: i + 1, o, s: summarize(o.map((x) => x.late)) }; });
const midOn = q(years.map((y) => y.s.onTime), 0.5), midP90 = q(years.map((y) => y.s.p90), 0.5);
const dist = (y) => Math.abs(y.s.onTime - midOn) / 0.1 + Math.abs(y.s.p90 - midP90) / 5;
const typical = years.reduce((b, y) => (dist(y) < dist(b) ? y : b));
const orders = typical.o;
const ys = typical.s;

// Lesson 3: by the month the order is placed, pooled over every supplier at 85%
const months = Array.from({ length: 12 }, () => []);
for (let i = 1; i <= SEEDS; i++) {
  const l = simulate(FOCUS, i);
  l.forEach((v, j) => { const d = l.when[j]; if (d < 365) months[Math.min(11, Math.floor(d / (365 / 12)))].push(v); });
}
const byMonth = months.map((a) => ({ p90: r1(q(a, 0.9)), p50: r1(q(a, 0.5)), on_time: Math.round(a.filter((v) => v <= 0).length / a.length * 100) }));

const out = {
  about: "Simulated by assets/lateness-sim.mjs: one factory, first in first out, Lunar New Year shutdown from day 30 for 18 days. Not a client, not a result.",
  generated_by: "scripts/learn/late_supplier.mjs",
  promise_days: PROMISE,
  production_days: MIN_PT,
  suppliers_per_load: SEEDS,
  focus_busy: Math.round(FOCUS * 100),
  loads,
  typical: { seed: typical.seed, on_time: Math.round(ys.onTime * 100), p50: r1(ys.p50), p90: r1(ys.p90), worst: Math.max(...orders.map((o) => o.late)), orders },
  months: byMonth,
};
writeFileSync(new URL("../../data/learn-late-supplier.json", import.meta.url), JSON.stringify(out, null, 1) + "\n");
console.log(`typical seed ${typical.seed}: ${out.typical.on_time}% on time, 1 in 10 ${out.typical.p90} d late, worst ${out.typical.worst}; ${orders.length} orders`);
console.log("months p90:", byMonth.map((m) => m.p90).join(" "));
console.log("at 50/70/85/90/95:", [50, 70, 85, 90, 95].map((b) => { const x = loads.find((l) => l.busy === b); return `${b}%: ${x.on_time}% on time, p90 ${x.p90}`; }).join("; "));
