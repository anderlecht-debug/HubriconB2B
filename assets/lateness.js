// /lateness: Fig. 1 replays one simulated factory's year on a canvas; Fig. 2 runs the same
// model as a Monte Carlo over 200 factories. Everything is computed here, in the browser,
// from Hubricon's factory simulation (./lateness-sim.mjs). No number on the page is typed in.
import { simulate, summarize, PROMISE } from "./lateness-sim.mjs";

const $ = id => document.getElementById(id);
const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
const css = name => getComputedStyle($("sim")).getPropertyValue(name).trim();
const daysTxt = v => v <= 0 ? "On time" : `${Math.round(v)} day${Math.round(v) === 1 ? "" : "s"}`;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dateOf = d => { const dt = new Date(Date.UTC(2026, 0, 1) + Math.floor(d) * 864e5); return `${dt.getUTCDate()} ${MONTHS[dt.getUTCMonth()]}`; };

const SEED = 133;                       // a typical factory: its 1-in-10 lateness sits near the middle of the 200
const LOADS = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95];
const RUNS = 200;

// ---------------------------------------------------------------- Monte Carlo
const mc = (() => {                     // p90 lateness for every factory at every load: 2,000 simulated years
  const per = LOADS.map(() => []);
  for (let s = 1; s <= RUNS; s++) LOADS.forEach((L, k) => per[k].push(summarize(simulate(L / 100, s)).p90));
  const runs = Array.from({ length: RUNS }, (_, s) => LOADS.map((_, k) => per[k][s]));
  const q = (k, p) => { const a = [...per[k]].sort((x, y) => x - y); return a[Math.floor(p * (a.length - 1))]; };
  return { runs, p10: LOADS.map((_, k) => q(k, 0.1)), p50: LOADS.map((_, k) => q(k, 0.5)), p90: LOADS.map((_, k) => q(k, 0.9)) };
})();

// ---------------------------------------------------------------- Fig. 1, the stage
const cv = $("stage"), ctx = cv.getContext("2d");
let W = 0, H = 0, data = null, t0 = 0, raf = 0, tEnd = 430;
const DUR = 14000;                      // one year in fourteen seconds

function size() {
  const r = cv.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
  W = r.width; H = r.height; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function load(loadPct) {
  const late = simulate(loadPct / 100, SEED);
  const orders = late.map((v, i) => ({ when: late.when[i], late: v, ready: late.when[i] + PROMISE + v })).filter(o => o.when < 365);
  orders.forEach((o, i) => { o.row = i; });
  const s = summarize(orders.map(o => o.late));
  tEnd = Math.max(400, Math.ceil(Math.max(...orders.map(o => o.ready)) + 4));
  data = { orders, queue: late.queue, s, max: Math.max(...orders.map(o => o.late)) };
  $("r-ontime").textContent = `${Math.round(s.onTime * 100)}%`;
  $("r-p90").textContent = daysTxt(s.p90);
  $("r-max").textContent = daysTxt(data.max);
  $("r-mc").textContent = daysTxt(mc.p50[LOADS.indexOf(loadPct)]);
}

function frame(now) {
  const ink = css("--ink"), ink3 = css("--ink-3"), ink4 = css("--ink-4"), rule = css("--rule"), blue = css("--blue");
  const p = calm ? 1 : Math.min(1, (now - t0) / DUR);
  const day = p * tEnd;
  ctx.clearRect(0, 0, W, H);

  const narrow = W < 700;
  const padL = 20, padR = 20, padT = 92;
  const histW = narrow ? 0 : Math.min(300, W * 0.27);
  const gx0 = padL, gx1 = W - padR - (histW ? histW + 32 : 0);
  const gy0 = padT, gy1 = H * (narrow ? 0.62 : 0.68);
  const qy0 = gy1 + 18, qy1 = H - 34;
  const X = d => gx0 + d / tEnd * (gx1 - gx0);

  // month grid
  ctx.font = "11px Inter, system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  for (let m = 0; m <= 13; m++) {
    const d = Math.round(m * 30.42); if (d > tEnd) break;
    ctx.strokeStyle = rule; ctx.globalAlpha = 0.7; ctx.beginPath(); ctx.moveTo(X(d), gy0 - 8); ctx.lineTo(X(d), qy1); ctx.stroke(); ctx.globalAlpha = 1;
    if (m < 12) { ctx.fillStyle = ink3; ctx.fillText(MONTHS[m], X(d + 15), H - 14); }
  }

  // the orders: each a line from placed to ready, blue past its promise
  const { orders } = data, rows = 64, rh = (gy1 - gy0) / rows;
  ctx.lineCap = "round";
  for (const o of orders) {
    if (o.when > day) break;
    const y = gy0 + (o.row % rows + 0.5) * rh;
    const end = Math.min(day, o.ready), prom = o.when + PROMISE;
    const okEnd = Math.min(end, prom);
    const done = day >= o.ready;
    ctx.lineWidth = Math.max(1.2, rh * 0.42);
    ctx.strokeStyle = ink4; ctx.globalAlpha = done ? 0.55 : 0.95;
    ctx.beginPath(); ctx.moveTo(X(o.when), y); ctx.lineTo(X(okEnd), y); ctx.stroke();
    if (end > prom) {
      ctx.globalAlpha = 1; ctx.strokeStyle = blue;
      ctx.shadowColor = blue; ctx.shadowBlur = done ? 0 : 10;
      ctx.beginPath(); ctx.moveTo(X(prom), y); ctx.lineTo(X(end), y); ctx.stroke();
      ctx.shadowBlur = 0;
    }
    if (!done) { ctx.globalAlpha = 1; ctx.fillStyle = end > prom ? blue : ink; ctx.beginPath(); ctx.arc(X(end), y, Math.max(1.6, rh * 0.38), 0, 7); ctx.fill(); }
  }
  ctx.globalAlpha = 1;

  // the line at the factory: days of work waiting, through the year
  const q = data.queue, qMax = 30;
  const QY = v => qy1 - Math.min(v, qMax) / qMax * (qy1 - qy0);
  const grad = ctx.createLinearGradient(0, qy0, 0, qy1);
  grad.addColorStop(0, blue); grad.addColorStop(1, "rgba(91,148,255,0)");
  const qEnd = Math.min(day, 364);
  ctx.beginPath(); ctx.moveTo(X(0), qy1);
  for (let d = 0; d <= qEnd; d++) ctx.lineTo(X(d), QY(q[d]));
  ctx.lineTo(X(qEnd), qy1); ctx.closePath();
  ctx.globalAlpha = 0.35; ctx.fillStyle = grad; ctx.fill(); ctx.globalAlpha = 1;
  ctx.beginPath(); for (let d = 0; d <= qEnd; d++) d ? ctx.lineTo(X(d), QY(q[d])) : ctx.moveTo(X(d), QY(q[d]));
  ctx.strokeStyle = blue; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.fillStyle = ink3; ctx.textAlign = "left";
  ctx.fillText("Work waiting in line at the factory", gx0 + 2, qy0 + 2);
  ctx.fillText("Each line: one order, placed → ready", gx0 + 2, gy0 - 12);

  // the playhead
  if (p < 1) {
    ctx.strokeStyle = ink; ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(X(day), gy0 - 8); ctx.lineTo(X(day), qy1); ctx.stroke(); ctx.globalAlpha = 1;
  }
  $("clock").textContent = day < 365 ? dateOf(day) : (p < 1 ? "Year end: last orders finishing" : "The year, done");
  $("queue-now").textContent = day < 365 ? `${Math.round(q[Math.floor(day)])} days of work in line` : "";

  // the tally: every finished order drops into its column of days late
  if (histW) {
    const hx0 = gx1 + 32, hx1 = W - padR, hy1 = gy1, hy0 = gy0;
    const LO = -8, HI = 40, cw = (hx1 - hx0) / (HI - LO + 1);
    const HX = v => hx0 + (Math.max(LO, Math.min(HI, Math.round(v))) - LO + 0.5) * cw;
    ctx.fillStyle = ink3; ctx.textAlign = "left"; ctx.fillText("Days late, every order", hx0, gy0 - 12);
    ctx.strokeStyle = ink; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(HX(0) + cw / 2, hy0); ctx.lineTo(HX(0) + cw / 2, hy1 + 4); ctx.stroke(); ctx.setLineDash([]);
    ctx.textAlign = "center"; ctx.fillStyle = ink3;
    ctx.fillText("promised", HX(0) + cw / 2, hy1 + 18);
    for (const v of [10, 20, 30, 40]) ctx.fillText(`+${v}`, HX(v), hy1 + 18);
    const stack = new Map(), r = Math.max(1.5, Math.min(cw * 0.45, 3));
    const sorted = orders.filter(o => o.ready <= day).sort((a, b) => a.ready - b.ready);
    for (const o of sorted) {
      const c = Math.max(LO, Math.min(HI, Math.round(o.late))); const n = stack.get(c) || 0; stack.set(c, n + 1);
      const ty = hy1 - r - n * r * 2.1; if (ty < hy0) continue;
      const e = calm ? 1 : Math.min(1, (day - o.ready) / 6); const k = 1 - Math.pow(1 - e, 3);
      const y = hy0 + (ty - hy0) * k;
      ctx.fillStyle = o.late > 0 ? blue : ink4; ctx.globalAlpha = 0.4 + 0.6 * k;
      if (o.late > 0 && e < 1) { ctx.shadowColor = blue; ctx.shadowBlur = 8; }
      ctx.beginPath(); ctx.arc(HX(o.late), y, r, 0, 7); ctx.fill(); ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;
  }

  raf = p < 1 ? requestAnimationFrame(frame) : 0;
}

function play() { cancelAnimationFrame(raf); t0 = performance.now(); raf = requestAnimationFrame(frame); }
const still = () => { cancelAnimationFrame(raf); t0 = performance.now() - DUR; frame(performance.now()); };

// the finished still frame first, never a blank box; play once when it scrolls into view
size(); load(+$("load").value); still();
if (!calm && "IntersectionObserver" in window) {
  new IntersectionObserver((es, ob) => { if (es[0].isIntersecting) { ob.disconnect(); play(); } }, { threshold: 0.35 }).observe(cv);
}
$("load").addEventListener("input", e => { $("load-out").textContent = `${e.target.value}%`; load(+e.target.value); calm ? still() : play(); fanMark(); });
$("replay").addEventListener("click", () => calm ? still() : play());
addEventListener("resize", () => { size(); if (!raf) still(); });

// ---------------------------------------------------------------- Fig. 2, the fan
const NS = "http://www.w3.org/2000/svg", fan = $("fan");
const el = (tag, a, parent = fan) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); parent.appendChild(e); return e; };
const FL = 40, FR = 16, FT = 16, FB = 34, FW = 560, FH = 300, YMAX = 60;
const fx = L => FL + (L - 50) / 45 * (FW - FL - FR);
const fy = v => FT + (1 - Math.max(0, Math.min(YMAX, v)) / YMAX) * (FH - FT - FB);
const line = arr => arr.map((v, k) => `${k ? "L" : "M"}${fx(LOADS[k]).toFixed(1)},${fy(v).toFixed(1)}`).join("");
for (let v = 0; v <= YMAX; v += 10) { el("line", { x1: FL, x2: FW - FR, y1: fy(v), y2: fy(v), class: "grid" }); el("text", { x: FL - 8, y: fy(v) + 4, "text-anchor": "end" }).textContent = v ? `+${v}` : "0"; }
for (const L of [50, 60, 70, 80, 90]) el("text", { x: fx(L), y: FH - 12, "text-anchor": "middle" }).textContent = `${L}%`;
el("text", { x: FW - FR, y: FH - 12, "text-anchor": "end" }).textContent = "busy →";
el("text", { x: FL, y: FT - 6 }).textContent = "Days late, worst 1 in 10 orders";
const runsG = el("g", {});
mc.runs.forEach(r => el("path", { d: line(r), class: "run" }, runsG));
el("path", { d: line(mc.p90) + LOADS.map((L, k) => LOADS.length - 1 - k).map(k => `L${fx(LOADS[k]).toFixed(1)},${fy(mc.p10[k]).toFixed(1)}`).join("") + "Z", class: "band" });
const mid = el("path", { d: line(mc.p50), class: "mid" });
const markL = el("line", { class: "mark", y1: FT, y2: FH - FB }), markD = el("circle", { class: "mark-dot", r: 6 });
const markT = el("text", { "text-anchor": "middle", style: "font-weight:600;fill:var(--ink)" });
function fanMark() {
  const L = +$("load").value, v = mc.p50[LOADS.indexOf(L)];
  markL.setAttribute("x1", fx(L)); markL.setAttribute("x2", fx(L));
  markD.setAttribute("cx", fx(L)); markD.setAttribute("cy", fy(v));
  markT.setAttribute("x", Math.max(FL + 30, Math.min(FW - FR - 30, fx(L)))); markT.setAttribute("y", fy(v) - 14); markT.textContent = `${Math.round(v)} days`;
}
fanMark();
if (!calm && "IntersectionObserver" in window) {
  const len = mid.getTotalLength(); mid.style.strokeDasharray = len;
  new IntersectionObserver((es, ob) => {
    if (!es[0].isIntersecting) return; ob.disconnect();
    mid.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 1800, easing: "cubic-bezier(0.16,1,0.3,1)" });
    [...runsG.children].forEach((p, i) => p.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 600, delay: i * 6, fill: "backwards" }));
  }, { threshold: 0.4 }).observe(fan);
}

// ---------------------------------------------------------------- What to expect at your size
// Modeled, not measured: the 1-in-10 lateness comes from the Monte Carlo above; the forecast
// misses are the simulation's (Fig. 3): 6.5 days knowing only the season, 4.5 with 5 brands pooled.
// Extra stock covers the miss 9 times in 10: 1.28 standard deviations, and a standard deviation is
// about 1.25 average misses, so 1.6 average misses.
const COVER = 1.28 * 1.25, MISS_SEASON = 6.5, MISS_POOLED = 4.5;
const REV_MIN = 250e3, REV_SPAN = 200;                  // $250k to $50M on a log slider
const revOf = v => REV_MIN * Math.pow(REV_SPAN, v / 1000);
const money = v => v >= 1e6 ? `$${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M` : v >= 1e3 ? `$${Math.round(v / 1e3)}k` : `$${Math.round(v)}`;
function expect(rev, share, cogs, busy) {
  const day = rev / 365 * share;
  const risk = mc.p50[LOADS.indexOf(busy)] * day;
  const park = COVER * MISS_SEASON * day * cogs;
  const free = COVER * (MISS_SEASON - MISS_POOLED) * day * cogs;
  return { risk, park, free };
}
const lad = $("ladder");
const LX0 = 56, LX1 = 600, LY0 = 20, LY1 = 262, VMIN = 300, VMAX = 3e6;
const lx = r => LX0 + Math.log(r / REV_MIN) / Math.log(REV_SPAN) * (LX1 - LX0);
const ly = v => LY1 - Math.log(Math.max(VMIN, Math.min(VMAX, v)) / VMIN) / Math.log(VMAX / VMIN) * (LY1 - LY0);
function ladder() {
  const share = +$("share").value / 100, cogs = +$("cogs").value / 100, busy = +$("busy").value, rev = revOf(+$("rev").value);
  lad.replaceChildren();
  const E = (t, a) => el(t, a, lad);
  for (const v of [1e3, 1e4, 1e5, 1e6]) { E("line", { x1: LX0, x2: LX1, y1: ly(v), y2: ly(v), class: "grid" }); E("text", { x: LX0 - 8, y: ly(v) + 4, "text-anchor": "end" }).textContent = money(v); }
  for (const r of [250e3, 1e6, 3e6, 10e6, 50e6]) E("text", { x: lx(r), y: LY1 + 22, "text-anchor": "middle" }).textContent = money(r);
  E("text", { x: LX1, y: LY1 + 38, "text-anchor": "end" }).textContent = "yearly revenue →";
  const xs = Array.from({ length: 41 }, (_, i) => REV_MIN * Math.pow(REV_SPAN, i / 40));
  const path = f => xs.map((r, i) => `${i ? "L" : "M"}${lx(r).toFixed(1)},${ly(f(r)).toFixed(1)}`).join("");
  const f = k => r => expect(r, share, cogs, busy)[k];
  E("path", { d: path(f("free")) + `L${lx(xs.at(-1))},${LY1}L${lx(xs[0])},${LY1}Z`, class: "a-free" });
  E("path", { d: path(f("risk")), class: "l-risk" });
  E("path", { d: path(f("park")), class: "l-park" });
  E("path", { d: path(f("free")), class: "l-free" });
  const x = lx(rev), o = expect(rev, share, cogs, busy);
  E("line", { x1: x, x2: x, y1: LY0, y2: LY1, class: "you" });
  E("text", { x, y: LY0 - 6, "text-anchor": "middle", class: "key" }).textContent = `You: ${money(rev)}`;
  const right = x < LX1 - 140, anchor = right ? "start" : "end", dx = right ? 12 : -12;
  [["risk", "dot-risk", "at risk"], ["park", "dot-park", "parked"], ["free", "dot-free", "freed"]].forEach(([k, c, w]) => {
    E("circle", { cx: x, cy: ly(o[k]), r: k === "free" ? 6 : 4.5, class: c });
    E("text", { x: x + dx, y: ly(o[k]) + 4, "text-anchor": anchor, class: "key" }).textContent = `${money(o[k])} ${w}`;
  });
  $("rev-out").textContent = money(rev); $("share-out").textContent = `${$("share").value}%`;
  $("cogs-out").textContent = `${$("cogs").value}%`; $("busy-out").textContent = `${busy}%`;
  $("o-risk").textContent = money(o.risk); $("o-park").textContent = money(o.park); $("o-free").textContent = money(o.free);
}
["rev", "share", "cogs"].forEach(id => $(id).addEventListener("input", ladder));
$("busy").addEventListener("input", e => { $("load").value = e.target.value; $("load").dispatchEvent(new Event("input")); });
$("load").addEventListener("input", e => { $("busy").value = e.target.value; ladder(); });
$("busy").value = $("load").value; ladder();
