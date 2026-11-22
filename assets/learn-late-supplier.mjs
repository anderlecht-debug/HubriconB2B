// The Late Supplier's figures (/learn/late-supplier), as pure functions that return SVG.
// scripts/build-pages.mjs calls them in Node to bake each figure's still frame into the page,
// and the page's script (/assets/learn-late-supplier.js) calls the same functions as a reader
// moves a slider or types a number, so the still and the live figure are one drawing.
// Every simulated number comes from data/learn-late-supplier.json (scripts/learn/late_supplier.mjs).
// Blue is the leak: days late, and the money a late order costs. Everything else is ink.

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
const f1 = (v) => (Math.round(v * 10) / 10).toString();
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const usd = (v) => `${v < 0 ? "−" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
export const days = (v) => { const n = Math.round(v); return `${n} day${Math.abs(n) === 1 ? "" : "s"}`; };
const svg = (w, h, label, body) => `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}" preserveAspectRatio="xMidYMid meet">${body}</svg>`;

// ------------------------------------------------------------ lesson 1 ----
/** A year of orders at one typical supplier, each a dot by how many days late it was ready. */
export function promiseStats(orders, cushion) {
  const n = orders.length;
  const onTime = orders.filter((o) => o.late <= 0).length;
  const covered = orders.filter((o) => o.late <= cushion).length;
  return { n, onTime: onTime / n, covered: covered / n, late: n - onTime, missed: n - covered };
}

export function figPromise(data, cushion = 0, upto = Infinity) {
  const W = 720, H = 300, L = 24, R = 24, base = 236, lo = -12, hi = 28;
  const all = data.typical.orders, shown = all.slice(0, Math.max(1, Math.min(all.length, upto)));
  const playing = shown.length < all.length;
  const x = (v) => L + (Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo) * (W - L - R);
  const stack = new Map(), r = 3.6, step = 7.6;
  const dots = shown.map((o, i) => {
    const k = Math.round(o.late);
    const n = stack.get(k) || 0; stack.set(k, n + 1);
    const cls = o.late <= 0 ? "d-ok" : o.late <= cushion ? "d-cov" : "d-late";
    return `<circle class="${cls}${playing && i >= shown.length - 6 ? " d-new" : ""}" cx="${f1(x(k) + (n % 2 ? 2.2 : -2.2))}" cy="${f1(base - 6 - n * step / 2.1)}" r="${r}"/>`;
  }).join("");
  const s = promiseStats(shown, cushion);
  const clock = playing ? `<text class="lab strong" x="${W - R}" y="26" text-anchor="end">${MONTHS_LONG[Math.min(11, Math.floor(shown[shown.length - 1].day / (365 / 12)))]}</text><text class="lab" x="${W - R}" y="44" text-anchor="end">${shown.length} orders so far</text>` : "";
  const ticks = [-10, 0, 10, 20].map((t) => `<line class="tick" x1="${x(t)}" x2="${x(t)}" y1="${base}" y2="${base + 6}"/><text class="ax" x="${x(t)}" y="${base + 24}" text-anchor="middle">${t === 0 ? "Promised date" : t < 0 ? `${-t} days early` : `${t} days late`}</text>`).join("");
  const cx = x(cushion);
  const plan = cushion > 0 ? `<rect class="cushion" x="${x(0)}" y="22" width="${f1(cx - x(0))}" height="${base - 22}"/>
    <line class="plan" x1="${cx}" x2="${cx}" y1="14" y2="${base}"/>
    <text class="lab strong" x="${cx + 8}" y="26">You plan for ${days(cushion)} late</text>
    <text class="lab" x="${cx + 8}" y="44">covers ${Math.round(s.covered * 100)}% of orders</text>` : "";
  return svg(W, H, `${all.length} orders at one simulated supplier, ${Math.round(s.onTime * 100)}% ready by the promised date`, `
    <line class="axis" x1="${L}" x2="${W - R}" y1="${base}" y2="${base}"/>${ticks}
    ${plan}
    <line class="promise" x1="${x(0)}" x2="${x(0)}" y1="14" y2="${base}"/>
    ${cushion > 0 ? "" : `<text class="lab strong" x="${x(0) - 8}" y="26" text-anchor="end">Ready on time</text><text class="lab" x="${x(0) - 8}" y="44" text-anchor="end">${Math.round(s.onTime * 100)}% of orders</text><text class="lab leak" x="${x(0) + 8}" y="26">Late</text><text class="lab" x="${x(0) + 8}" y="44">${100 - Math.round(s.onTime * 100)}% of orders</text>`}
    ${clock}<g class="dots">${dots}</g>`);
}

// ------------------------------------------------------------ lesson 2 ----
export const atBusy = (data, busy) => data.loads.find((l) => l.busy === busy) || data.loads[data.loads.length - 1];

export function figBusy(data, busy = 85) {
  const W = 720, H = 320, L = 56, R = 24, T = 20, B = 260;
  const lo = 50, hi = 95, ymax = 60;
  const x = (b) => L + (b - lo) / (hi - lo) * (W - L - R);
  const y = (d) => B - (Math.max(-2, Math.min(ymax, d)) + 2) / (ymax + 2) * (B - T);
  const ls = data.loads;
  const band = `M${ls.map((l) => `${f1(x(l.busy))},${f1(y(l.p90_hi))}`).join(" L")} L${[...ls].reverse().map((l) => `${f1(x(l.busy))},${f1(y(l.p90_lo))}`).join(" L")} Z`;
  const line = `M${ls.map((l) => `${f1(x(l.busy))},${f1(y(l.p90))}`).join(" L")}`;
  const p = atBusy(data, busy);
  const grid = [0, 20, 40, 60].map((d) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(d)}" y2="${y(d)}"/><text class="ax" x="${L - 10}" y="${y(d) + 4}" text-anchor="end">${d}</text>`).join("");
  const xt = [50, 60, 70, 80, 90].map((b) => `<text class="ax" x="${x(b)}" y="${B + 24}" text-anchor="middle">${b}%</text>`).join("");
  const right = x(busy) > W - 220;
  return svg(W, H, `At ${busy}% busy, the typical simulated supplier's 1-in-10 order is ${days(p.p90)} late`, `
    ${grid}${xt}
    <text class="ax" x="${L}" y="${B + 48}">How busy the supplier is</text>
    <text class="ax" x="${L}" y="${T - 10}">Days late</text>
    <path class="band" d="${band}"/>
    <path class="curve" d="${line}"/>
    <line class="plan" x1="${x(busy)}" x2="${x(busy)}" y1="${T}" y2="${B}"/>
    <circle class="mark" cx="${x(busy)}" cy="${y(p.p90)}" r="6"/>
    <text class="lab strong" x="${x(busy) + (right ? -12 : 12)}" y="${y(p.p90) - 12}" text-anchor="${right ? "end" : "start"}">1 in 10 orders: ${days(p.p90)} late</text>`);
}

/** The line at one supplier, a day at a time: orders arrive at random (busy × a day), each takes a random
    time to make (one day on average), and one is made at a time. Yours are blue. */
export function lineSim(seed = 11) {
  let a = seed >>> 0;
  const r = () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const exp = () => -Math.log(1 - r());
  let id = 0, lastBlue = -99;
  const s = {
    t: 0, queue: [], cur: null, done: [], lastWait: null,
    step(dt, busy) {
      s.t += dt;
      if (r() < busy * dt) {
        const blue = !s.queue.some((o) => o.blue) && !(s.cur && s.cur.blue) && s.t - lastBlue > 12;
        if (blue) lastBlue = s.t;
        s.queue.push({ id: id++, at: s.t, blue, x: -20 });
      }
      if (s.cur) { s.cur.left -= dt; if (s.cur.left <= 0) { s.done.unshift({ ...s.cur, x: 600, out: 0 }); s.cur = null; } }
      if (!s.cur && s.queue.length) {
        const o = s.queue.shift();
        if (o.blue) s.lastWait = s.t - o.at;
        s.cur = { ...o, size: exp(), left: 0 }; s.cur.left = s.cur.size;
      }
      s.done = s.done.filter((o) => (o.out += dt) < 2.5);
      // ease every square toward its place, so the line slides rather than jumps
      s.queue.forEach((o, i) => { const tx = 500 - 22 * (i + 1); o.x += (tx - o.x) * Math.min(1, dt * 6); });
      if (s.cur) s.cur.x = 572;
      return s;
    },
    run(days, busy, dt = 0.1) { for (let i = 0; i < days / dt; i++) s.step(dt, busy); s.queue.forEach((o, i) => { o.x = 500 - 22 * (i + 1); }); return s; },
  };
  return s;
}

export function figLine(s, busy) {
  const W = 720, Y = 50, Q = 16;
  const wait = s.queue.length + (s.cur ? Math.max(0, s.cur.left) : 0);
  const shown = s.queue.filter((o) => o.x > 4);
  const more = s.queue.length - shown.length;
  const sq = (o, cls, x, y, op = 1) => `<rect class="${cls}${o.blue ? " q-blue" : ""}" x="${f1(x)}" y="${f1(y)}" width="${Q}" height="${Q}" rx="3"${op < 1 ? ` opacity="${f1(op)}"` : ""}/>`;
  const line = shown.map((o) => sq(o, "q-wait", o.x, Y - Q / 2)).join("");
  const cur = s.cur ? sq(s.cur, "q-make", 572, Y - Q / 2) + `<rect class="q-prog" x="548" y="${Y + 18}" width="${f1(64 * (1 - Math.max(0, s.cur.left) / s.cur.size))}" height="3" rx="1.5"/>` : "";
  const done = s.done.map((o) => sq(o, "q-done", 640 + o.out * 28, Y - Q / 2, Math.max(0, 1 - o.out / 2.5))).join("");
  const hud = `<div class="q-hud"><p><b>Day ${Math.floor(s.t)}</b><span>${s.queue.length} order${s.queue.length === 1 ? "" : "s"} in line${more > 0 ? `, ${more} off screen` : ""}</span></p>`
    + `<p class="r"><b>A new order waits about ${days(wait)}</b><span class="leak">${s.lastWait === null ? "&nbsp;" : `Your last order waited ${days(s.lastWait)} in line`}</span></p></div>`;
  return hud + svg(W, 130, `At ${busy}% busy, ${s.queue.length} orders are waiting; a new order would wait about ${days(wait)}`, `
    <line class="q-floor" x1="0" x2="${W}" y1="${Y + 30}" y2="${Y + 30}"/>
    <rect class="q-factory" x="536" y="${Y - 34}" width="88" height="64" rx="8"/>
    <text class="ax" x="580" y="${Y + 52}" text-anchor="middle">Being made</text>
    <text class="ax" x="300" y="${Y + 52}" text-anchor="middle">Waiting in line</text>
    ${line}${cur}${done}`);
}

// ------------------------------------------------------------ lesson 3 ----
export function figCalendar(data, month = 1) {
  const W = 720, H = 300, L = 40, R = 16, T = 34, B = 240;
  const ms = data.months, max = Math.ceil(Math.max(...ms.map((m) => m.p90)) / 10) * 10;
  const bw = (W - L - R) / 12;
  const y = (d) => B - Math.max(0, d) / max * (B - T);
  const worst = ms.reduce((b, m, i) => (m.p90 > ms[b].p90 ? i : b), 0);
  const bars = ms.map((m, i) => {
    const cls = i === month ? "mbar sel" : "mbar";
    return `<g class="mo" data-month="${i}"><rect class="hit" x="${f1(L + i * bw)}" y="${T - 30}" width="${f1(bw)}" height="${B - T + 60}"/>
      <rect class="${cls}" x="${f1(L + i * bw + 8)}" y="${f1(y(m.p90))}" width="${f1(bw - 16)}" height="${f1(B - y(m.p90))}" rx="3"/>
      <text class="ax${i === month ? " strong" : ""}" x="${f1(L + i * bw + bw / 2)}" y="${B + 22}" text-anchor="middle">${MONTHS[i]}</text>
      ${i === month ? `<text class="lab strong" x="${f1(L + i * bw + bw / 2)}" y="${f1(y(m.p90) - 10)}" text-anchor="middle">${Math.round(m.p90)} d</text>` : ""}</g>`;
  }).join("");
  // Lunar New Year in the simulation: every factory stops from day 30 for 18 days
  const d2x = (d) => L + d / 365 * (W - L - R);
  return svg(W, H, `Orders placed in ${MONTHS_LONG[month]}: 1 in 10 ready ${days(ms[month].p90)} after the promised date. Worst month: ${MONTHS_LONG[worst]}.`, `
    <rect class="lny" x="${f1(d2x(30))}" y="${T - 30}" width="${f1(d2x(48) - d2x(30))}" height="${B - T + 30}"/>
    <text class="ax" x="${f1(d2x(48) + 6)}" y="${T - 16}">Factories closed for Lunar New Year</text>
    <line class="axis" x1="${L}" x2="${W - R}" y1="${B}" y2="${B}"/>
    ${bars}`);
}

// ------------------------------------------------------------ lesson 4 ----
/** One late order against holding cover for it all year. Plain arithmetic, labelled as such. */
export function cost({ sales = 50000, margin = 55, late = 14, carry = 25 } = {}) {
  const perDay = sales / 30;
  const stockout = perDay * late * (margin / 100);           // the profit on sales you can't make
  const cash = perDay * late * (1 - margin / 100);           // product cost of the extra stock
  const carrying = cash * (carry / 100);                     // what holding it costs for a year
  return { perDay, stockout, cash, carrying, ratio: carrying > 0 ? stockout / carrying : 0 };
}

export function figCost(inp = {}) {
  const c = cost(inp);
  const W = 720, H = 220, L = 16, R = 16, max = Math.max(c.stockout, c.cash, 1);
  const w = (v) => Math.max(2, v / max * (W - L - R - 150));
  const row = (yy, k, v, cls, note) => `<text class="lab strong" x="${L}" y="${yy - 10}">${k}</text>
    <rect class="${cls}" x="${L}" y="${yy}" width="${f1(w(v))}" height="26" rx="3"/>
    <text class="lab strong${cls === "cb-leak" ? " leak" : ""}" x="${f1(L + w(v) + 10)}" y="${yy + 18}">${usd(v)}</text>
    ${note ? `<text class="ax" x="${L}" y="${yy + 46}">${note}</text>` : ""}`;
  return svg(W, H, `A ${days(inp.late ?? 14)} stockout costs about ${usd(c.stockout)} in profit; holding that cover all year costs about ${usd(c.carrying)}`, `
    ${row(32, "One stockout: profit on the sales you can't make", c.stockout, "cb-leak", "")}
    ${row(102, "Holding the same days of cover for a year: carrying cost", c.carrying, "cb-ink", "")}
    ${row(172, "The cash that cover ties up (you get it back when it sells)", c.cash, "cb-ghost", "")}`);
}

/** How many days of cover to hold. The lateness of a year of orders at the typical simulated supplier,
    scaled so its worst 1 in 10 matches yours; for each number of days of cover, what running short costs
    in a year (orders a year × the average days each one runs past your cover × a day's profit) against what
    holding the cover costs (days × a day's product cost × the yearly holding rate). The total bottoms out
    where one more day of cover costs as much as it saves. */
export function coverCurve(data, { sales = 50000, margin = 55, late = 12, carry = 25, orders = 6 } = {}) {
  const perDay = sales / 30, m = Math.min(0.95, margin / 100), k = late > 0 ? late / (data.typical.p90 || 1) : 0;
  const L = data.typical.orders.map((o) => Math.max(0, o.late * k));
  const maxC = Math.max(10, Math.ceil(Math.max(...L) * 1.1));
  const pts = [];
  for (let c = 0; c <= maxC; c++) {
    const short = L.reduce((t, l) => t + Math.max(0, l - c), 0) / L.length;
    const stockout = orders * short * perDay * m, hold = c * perDay * (1 - m) * (carry / 100);
    pts.push({ c, stockout, hold, total: stockout + hold });
  }
  const best = pts.reduce((b, p) => (p.total < b.total ? p : b));
  return { pts, best, maxC, perDay };
}

export function figCurve(data, inp = {}, cover = 0) {
  const cc = coverCurve(data, inp);
  const W = 720, H = 320, Lm = 64, R = 24, T = 24, B = 256;
  const ymax = Math.max(1, cc.pts[0].total, cc.pts[cc.pts.length - 1].total) * 1.08;
  const x = (c) => Lm + c / cc.maxC * (W - Lm - R);
  const y = (v) => B - Math.min(v, ymax) / ymax * (B - T);
  const path = (k) => "M" + cc.pts.map((p) => f1(x(p.c)) + "," + f1(y(p[k]))).join(" L");
  const at = cc.pts[Math.max(0, Math.min(cc.pts.length - 1, Math.round(cover)))];
  const nice = [500, 1000, 2000, 4000, 5000, 10000, 20000, 50000, 100000, 200000, 500000];
  const step = nice.find((n) => ymax / n <= 5) || 1000000;
  const money = (v) => (v >= 1000 ? "$" + (v / 1000) + "k" : "$" + v);
  const grid = [];
  for (let v = 0; v <= ymax; v += step) grid.push(`<line class="grid" x1="${Lm}" x2="${W - R}" y1="${f1(y(v))}" y2="${f1(y(v))}"/><text class="ax" x="${Lm - 10}" y="${f1(y(v) + 4)}" text-anchor="end">${money(v)}</text>`);
  const xs = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(cc.maxC * f)).map((c) => `<text class="ax" x="${f1(x(c))}" y="${B + 22}" text-anchor="middle">${c} d</text>`).join("");
  const right = x(at.c) > W - 230;
  return svg(W, H, `Holding ${days(at.c)} of cover costs about ${usd(at.total)} a year in stockouts and holding; the least is ${usd(cc.best.total)} at ${days(cc.best.c)}`, `
    ${grid.join("")}${xs}
    <text class="ax" x="${Lm}" y="${B + 46}">Days of extra stock you hold</text>
    <path class="c-hold" d="${path("hold")}"/>
    <path class="c-out" d="${path("stockout")}"/>
    <path class="c-total" d="${path("total")}"/>
    <text class="lab leak" x="${f1(x(cc.maxC * 0.22) - 10)}" y="${f1(y(cc.pts[Math.round(cc.maxC * 0.22)].stockout) + 20)}" text-anchor="end">Running out</text>
    <text class="lab" x="${W - R}" y="${f1(y(cc.pts[cc.pts.length - 1].hold) + 22)}" text-anchor="end">Holding extra</text>
    <circle class="c-best" cx="${f1(x(cc.best.c))}" cy="${f1(y(cc.best.total))}" r="5"/>
    <line class="plan" x1="${f1(x(at.c))}" x2="${f1(x(at.c))}" y1="${T}" y2="${B}"/>
    <circle class="mark-ink" cx="${f1(x(at.c))}" cy="${f1(y(at.total))}" r="6"/>
    <text class="lab strong" x="${f1(x(at.c) + (right ? -12 : 12))}" y="${f1(Math.max(T + 12, y(at.total) - 14))}" text-anchor="${right ? "end" : "start"}">${usd(at.total)} a year</text>`);
}

// ------------------------------------------------------------ lesson 6 ----
/** When the next PO has to go out, on the promise and on the real date. */
export function reorder({ daily = 40, onHand = 4000, promised = 30, late = 12, transit = 35 } = {}) {
  const cover = daily > 0 ? onHand / daily : 0;                // days until the shelf is empty
  const onPromise = cover - (promised + transit);              // order by this day if the promise holds
  const onReal = cover - (promised + late + transit);          // order by this day to cover the 1-in-10
  const point = daily * (promised + late + transit);           // the reorder point, in units
  return { cover, onPromise, onReal, point, extraUnits: daily * late };
}

export function figReorder(inp = {}) {
  const r = reorder(inp);
  const { promised = 30, late = 12, transit = 35 } = inp;
  const W = 720, H = 210, L = 16, R = 16;
  const span = Math.max(r.cover, promised + late + transit, 1) * 1.04;
  const x = (d) => L + Math.max(0, d) / span * (W - L - R);
  const o = r.onReal;
  const seg = (a, b, yy, cls, label) => `<rect class="${cls}" x="${f1(x(a))}" y="${yy}" width="${f1(Math.max(1, x(b) - x(a)))}" height="22" rx="3"/>${label ? `<text class="ax" x="${f1(x(a) + 6)}" y="${yy + 15}">${label}</text>` : ""}`;
  const start = Math.max(0, o);
  return svg(W, H, `Order by day ${Math.round(o)} to cover a 1-in-10 late order; the promise alone says day ${Math.round(r.onPromise)}`, `
    <line class="axis" x1="${L}" x2="${W - R}" y1="150" y2="150"/>
    <text class="ax" x="${L}" y="172">Today</text>
    <line class="promise" x1="${f1(x(r.cover))}" x2="${f1(x(r.cover))}" y1="12" y2="150"/>
    <text class="lab strong" x="${f1(x(r.cover) - 6)}" y="196" text-anchor="end">Shelf empty, day ${Math.round(r.cover)}</text>
    ${seg(start, start + promised, 40, "sg-ink", "Production, as promised")}
    ${seg(start + promised, start + promised + late, 40, "sg-leak", late >= 6 ? "Late" : "")}
    ${seg(start + promised + late, start + promised + late + transit, 40, "sg-ghost", "Shipping")}
    <line class="plan" x1="${f1(x(start))}" x2="${f1(x(start))}" y1="12" y2="150"/>
    <text class="lab strong${o < 0 ? " leak" : ""}" x="${f1(x(start) + 6)}" y="26">${o < 0 ? `Already ${days(-o)} too late to order` : `Order by day ${Math.round(o)}`}</text>
    <text class="ax" x="${f1(x(start) + 6)}" y="96">${o < 0 ? "" : `On the promise alone you'd wait until day ${Math.round(r.onPromise)}`}</text>`);
}

// ------------------------------------------------------------ lesson 5 ----
function parseDate(t) {
  t = String(t || "").trim().replace(/^"|"$/g, "");
  let m;
  if ((m = t.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/))) return Date.UTC(+m[1], m[2] - 1, +m[3]);
  if ((m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/))) { const y = +m[3] < 100 ? 2000 + +m[3] : +m[3]; return Date.UTC(y, m[1] - 1, +m[2]); }
  const d = Date.parse(t); return isNaN(d) ? null : d;
}

/** Rows of supplier, order date, promised ready date, actual ready date: pasted, or a CSV. */
export function parseOrders(text) {
  const lines = String(text || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return { rows: [], skipped: 0 };
  const split = (l) => l.split(/\t|;|,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map((c) => c.trim().replace(/^"|"$/g, ""));
  let cols = { sup: 0, order: 1, promised: 2, actual: 3 };
  const head = split(lines[0]).map((h) => h.toLowerCase());
  if (head.every((h) => parseDate(h) === null)) {
    const taken = new Set();
    const find = (...ks) => { for (const k of ks) { const i = head.findIndex((h, j) => !taken.has(j) && h.includes(k)); if (i >= 0) { taken.add(i); return i; } } return -1; };
    const c = { sup: find("supplier", "factory", "vendor", "manufacturer"), promised: find("promis", "expected", "eta", "due"), actual: find("actual", "completed", "done", "ready"), order: find("order", "po", "placed") };
    if (c.order >= 0 && c.promised >= 0 && c.actual >= 0) cols = { ...c, sup: c.sup >= 0 ? c.sup : -1 };
    lines.shift();
  }
  const rows = []; let skipped = 0;
  for (const l of lines) {
    const c = split(l);
    const o = parseDate(c[cols.order]), p = parseDate(c[cols.promised]), a = parseDate(c[cols.actual]);
    if (o === null || p === null || a === null || p < o) { skipped++; continue; }
    rows.push({ sup: (cols.sup >= 0 && c[cols.sup]) || "Your supplier", order: o, late: Math.round((a - p) / 864e5) });
  }
  return { rows, skipped };
}

/** The 1-in-10 figure: the lateness nine orders in ten come in at or under, computed the way the
    worksheet's PERCENTILE does (linear between the two nearest orders), so page and file agree. */
export const p90 = (a) => {
  const s = [...a].sort((x, y) => x - y);
  if (!s.length) return 0;
  const pos = (s.length - 1) * 0.9, i = Math.floor(pos);
  return i + 1 < s.length ? s[i] + (s[i + 1] - s[i]) * (pos - i) : s[i];
};

export function score(rows) {
  const by = new Map();
  rows.forEach((r) => { if (!by.has(r.sup)) by.set(r.sup, []); by.get(r.sup).push(r.late); });
  return [...by].map(([sup, l]) => ({ sup, n: l.length, onTime: l.filter((v) => v <= 0).length / l.length, avg: l.reduce((t, v) => t + v, 0) / l.length, p90: p90(l), worst: Math.max(...l) }))
    .sort((a, b) => b.p90 - a.p90);
}

/** Two suppliers drawn from the simulation, a busy one and a quiet one, as a reader's rows would look. */
export function sampleRows(simulate, PROMISE) {
  const out = ["supplier,order_date,promised_ready_date,actual_ready_date"];
  const iso = (d) => new Date(Date.UTC(2025, 0, 1) + Math.round(d) * 864e5).toISOString().slice(0, 10);
  for (const [name, load, seed, every] of [["Sample supplier A (busy)", 0.9, 133, 23], ["Sample supplier B (quiet)", 0.6, 55, 29]]) {
    const l = simulate(load, seed); let next = 4;
    for (let i = 0; i < l.length; i++) { const d = l.when[i]; if (d < next || d >= 365) continue; next = d + every;
      out.push(`${name},${iso(d)},${iso(d + PROMISE)},${iso(d + PROMISE + l[i])}`); }
  }
  return out.join("\n");
}
