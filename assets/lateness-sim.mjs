// One factory, one queue: how load turns into lateness.
// A port of the project's simulation (sim/simcore.py) small enough to run in a browser.
// Orders arrive in 1,000-unit lots, wait first-in first-out behind everyone else's,
// then take a fixed production time plus material and QC noise. The same random
// draws are used at every load, so moving the slider changes only how busy the factory is.

export const PROMISE = 20;   // days the factory promised: order to ready
export const MIN_PT = 12;    // days of actual production with no queue

function rng(seed) {          // mulberry32
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function normal(r) { let u = 0; while (!u) u = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r()); }
function poissonFromU(lam, us) { // inverse-CDF so a fixed uniform maps monotonically across loads
  let k = 0, p = Math.exp(-lam), c = p; const u = us;
  while (u > c && k < 200) { k++; p *= lam / k; c += p; }
  return k;
}

const DAYS = 365 * 3;
let base = null;
function draws(seed) {
  const r = rng(seed); const x = new Float64Array(DAYS), u = new Float64Array(DAYS), g = new Float64Array(DAYS);
  for (let i = 1; i < DAYS; i++) x[i] = 0.995 * x[i - 1] + 0.012 * normal(r);   // the factory's other customers come and go
  for (let i = 0; i < DAYS; i++) { u[i] = r(); g[i] = 1.5 * (-Math.log(1 - r()) - Math.log(1 - r())); } // gamma(2, 1.5)
  return { x, u, g };
}

// Returns days late (ready date minus promised date) for every order placed in years two and three.
export function simulate(load, seed = 7) {
  if (!base || base.seed !== seed) base = { seed, ...draws(seed) };
  const { x, u, g } = base; const mu = 2000;
  const arr = new Float64Array(DAYS), cap = new Float64Array(DAYS).fill(mu);
  for (let y = 0; y < 3; y++) { const c = 30 + 365 * y;                 // Lunar New Year: every factory stops at once
    for (let i = c; i < c + 18 && i < DAYS; i++) cap[i] = 0;
    for (let i = c + 18; i < c + 28 && i < DAYS; i++) cap[i] = mu * 0.6; }
  for (let i = 0; i < DAYS; i++) {
    const season = 1 + 0.12 * Math.sin(2 * Math.PI * (i - 200) / 365);
    arr[i] = poissonFromU(mu * load * season * Math.exp(x[i] - 0.0072) / 1000, u[i]) * 1000;
  }
  // first in, first out: an order is done when cumulative output reaches cumulative arrivals up to it
  const ca = new Float64Array(DAYS), co = new Float64Array(DAYS); let B = 0, sa = 0, so = 0; const queue = new Float64Array(DAYS);
  for (let i = 0; i < DAYS; i++) { const avail = B + arr[i]; const o = Math.min(avail, cap[i]); B = avail - o; queue[i] = B / mu; sa += arr[i]; so += o; ca[i] = sa; co[i] = so; }
  const late = [], when = []; let j = 0;
  for (let i = 365; i < DAYS - 120; i++) {
    if (!arr[i]) continue;
    while (j < DAYS && co[j] < ca[i]) j++;
    const wait = Math.max(0, (j < DAYS ? j : DAYS + 60) - i);
    late.push(MIN_PT + wait + g[i] - PROMISE); when.push(i - 365);
  }
  late.when = when;
  late.queue = queue.slice(365, 730);   // days of work waiting in line, through year two   // day of the year the order was placed (0 = 1 January of year two)
  return late;
}

export function summarize(late) {
  const s = [...late].sort((a, b) => a - b); const q = p => s[Math.min(s.length - 1, Math.floor(p * s.length))];
  return { n: s.length, onTime: s.filter(v => v <= 0).length / s.length, p10: q(0.1), p50: q(0.5), p90: q(0.9) };
}
