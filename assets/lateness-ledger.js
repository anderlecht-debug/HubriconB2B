// /lateness hero: the ledger. Real rows from Hubricon's supplier simulation (a busy supplier),
// five orders at a time: each bar fills to its promised date in ink, then keeps going in blue
// if the order ran late. A new set of five every few seconds; it stops when the tab is hidden,
// on hover, and for anyone who asked for less motion.
import { simulate, PROMISE } from "./lateness-sim.mjs";

const rows = document.getElementById("ledger-rows");
const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = d => { const t = new Date(Date.UTC(2026, 0, 1) + Math.round(d) * 864e5); return `${t.getUTCDate()} ${MONTHS[t.getUTCMonth()]}`; };

const sim = simulate(0.88, 133);
const orders = [];
for (let i = 0, next = 0; i < sim.length; i++) {
  const d = sim.when[i]; if (d < next || d >= 365) continue; next = d + 9;
  orders.push({ when: d, late: sim[i] });
}
const SPAN = PROMISE + 26;                  // the bar's full width, in days from the order
const pct = d => `${Math.max(0, Math.min(100, d / SPAN * 100)).toFixed(2)}%`;

let at = Math.max(0, orders.findIndex(o => o.when >= 40));
function show() {
  const set = Array.from({ length: 5 }, (_, k) => orders[(at + k) % orders.length]);
  rows.innerHTML = set.map(o => {
    const total = PROMISE + o.late, late = o.late > 0.5;
    return `<li class="lr"><span class="d">${day(o.when)}</span>
      <span class="track"><span class="ok" style="width:0"></span><span class="over" style="left:${pct(PROMISE)};width:0"></span><span class="pin" style="left:${pct(PROMISE)}"></span></span>
      <span class="v ${late ? "late" : ""}">${late ? `+${Math.round(o.late)} days` : "on time"}</span></li>`;
  }).join("");
  [...rows.children].forEach((li, k) => {
    const o = set[k], total = PROMISE + o.late;
    const ok = li.querySelector(".ok"), over = li.querySelector(".over"), v = li.querySelector(".v");
    const okW = pct(Math.min(total, PROMISE)), overW = pct(Math.max(0, total - PROMISE));
    if (calm) { ok.style.width = okW; over.style.width = overW; return; }
    v.style.opacity = 0;
    const delay = k * 140;
    ok.animate([{ width: "0%" }, { width: okW }], { duration: 900, delay, easing: "cubic-bezier(0.16,1,0.3,1)", fill: "forwards" });
    over.animate([{ width: "0%" }, { width: overW }], { duration: 700, delay: delay + 850, easing: "cubic-bezier(0.16,1,0.3,1)", fill: "forwards" });
    v.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { duration: 400, delay: delay + (total > PROMISE ? 1400 : 800), fill: "forwards" });
  });
  at = (at + 5) % orders.length;
}
show();
if (!calm) {
  let paused = false;
  const box = document.getElementById("ledger");
  box.addEventListener("mouseenter", () => { paused = true; });
  box.addEventListener("mouseleave", () => { paused = false; });
  setInterval(() => { if (!paused && !document.hidden) show(); }, 6000);
}
