// The home page's three pictures, as SVG strings: the Monte Carlo, Amazon's fee
// staircase and the aged-inventory cliff. Pure functions of their data, so
// scripts/build-home.mjs bakes each one into index.html as its finished still
// frame: a visitor without scripts, or who never scrolls to it, sees the result.
// The browser only animates what is already drawn (assets/home.js, and the
// .draw / .fade classes in assets/hubricon.css). Colours, weights and timings
// come from the stylesheet's tokens; nothing here names a colour.

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const r1 = (v) => Math.round(v * 10) / 10;
const pts = (xs, ys) => xs.map((x, i) => `${r1(x)},${r1(ys[i])}`);
// <path>, not <polyline>: pathLength, which the draw-in animation needs, is only dependable on paths.
const line = (p) => `M${p.join(" L")}`;

/** "$687,000" or, compact, "$687k" / "$1.2M". Floors: a range on this page is never rounded up. */
export function usd(v, { compact = false, step = 1 } = {}) {
  const sign = v < 0 ? "−" : "";
  const a = Math.floor(Math.abs(v) / step) * step;
  const trim = (x) => String(Math.floor(x * 10) / 10);
  if (compact && a >= 1e6) return `${sign}$${trim(a / 1e6)}M`;
  if (compact && a >= 1000) {
    const k = a / 1000;
    return `${sign}$${k >= 100 ? Math.floor(k) : trim(k)}k`;
  }
  return `${sign}$${a.toLocaleString("en-US")}`;
}

/** A per-unit fee, the way the page's prose prints it: "$0.26". */
export const perUnit = (v) => `$${v.toFixed(2)}`;

/** Three to five round ticks across [lo, hi]. */
export function niceTicks(lo, hi, target = 4) {
  const span = hi - lo || 1;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= target + 0.5) || 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

const scale = (d0, d1, r0, r1_) => (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1_ - r0);

/** Spread labels at least `gap` apart vertically, keeping their order. */
function spread(items, gap, lo, hi) {
  const s = [...items].sort((a, b) => a.y - b.y);
  for (let i = 1; i < s.length; i++) if (s[i].y - s[i - 1].y < gap) s[i].y = s[i - 1].y + gap;
  const over = s.length ? s[s.length - 1].y - hi : 0;
  if (over > 0) for (const it of s) it.y -= over;
  if (s.length && s[0].y < lo) { const d = lo - s[0].y; for (const it of s) it.y += d; }
  return s;
}

function frame(w, h, cls, title, desc, body) {
  return `<svg class="chart ${cls}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="${title.id} ${desc.id}" preserveAspectRatio="xMidYMid meet">` +
    `<title id="${title.id}">${esc(title.text)}</title><desc id="${desc.id}">${esc(desc.text)}</desc>${body}</svg>`;
}

// ---------------------------------------------------------------- Monte Carlo

/**
 * mc: the montecarlo.json contract. opts.variant "full" draws axes and the three
 * labelled lines; "mood" is the same picture with no words, for the hero.
 * Paths are taken at even steps through the file's (rank-ordered) paths.
 */
export function monteCarloSVG(mc, opts) {
  const { id, w, h, m, paths: nPaths = mc.paths.length, variant = "full", font = 13 } = opts;
  const full = variant === "full";
  const months = mc.months;
  const all = [...mc.paths.flat(), ...mc.percentiles.p10, ...mc.percentiles.p90];
  const yLo = Math.min(0, ...all), yHi = Math.max(...all);
  const ticks = niceTicks(yLo, yHi, full ? 4 : 3);
  const d0 = Math.min(yLo, ticks[0]), d1 = Math.max(yHi, ticks[ticks.length - 1]);
  const X = scale(months[0], months[months.length - 1], m.l, w - m.r);
  const Y = scale(d0, d1, h - m.b, m.t);
  const xs = months.map(X);

  const pick = nPaths >= mc.paths.length ? mc.paths.map((_, i) => i)
    : Array.from({ length: nPaths }, (_, i) => Math.round((i * (mc.paths.length - 1)) / (nPaths - 1)));
  let body = "";

  if (full) {
    for (const t of ticks) {
      body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
      body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${usd(t, { compact: true })}</text>`;
    }
    if (d0 < 0) body += `<line class="mc-zero" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(0))}" y2="${r1(Y(0))}"/>`;
    const last = months[months.length - 1];
    const xl = [[months[0], "Today", "start"], [last / 2, `${last / 2} months`, "middle"], [last, `${last} months`, "end"]];
    for (const [v, t, a] of xl) body += `<text x="${r1(X(v))}" y="${h - m.b + font + 12}" font-size="${font}" text-anchor="${a}">${t}</text>`;
  }

  // The band first, under everything; it fades in once the lines have settled.
  const p10 = mc.percentiles.p10.map(Y), p90 = mc.percentiles.p90.map(Y);
  body += `<path class="mc-band fade" d="${line([...pts(xs, p90), ...pts(xs, p10).reverse()])}Z"/>`;

  pick.forEach((k, i) => {
    const delay = (i * 53) % 260;
    body += `<path class="mc-path draw" pathLength="1" style="--delay:${delay}ms" d="${line(pts(xs, mc.paths[k].map(Y)))}"/>`;
  });
  for (const q of ["p10", "p90", "p50"]) {
    body += `<path class="mc-pct draw ${q}" pathLength="1" d="${line(pts(xs, mc.percentiles[q].map(Y)))}"/>`;
  }

  if (full) {
    const end = months.length - 1;
    const names = { p90: "P90", p50: "Median", p10: "P10" };
    const placed = spread(["p90", "p50", "p10"].map((q) => ({ q, y: Y(mc.percentiles[q][end]) })), font * 2.6, m.t + font, h - m.b);
    for (const { q, y } of placed) {
      const x = w - m.r + 14;
      body += `<g class="fade">` +
        `<text x="${x}" y="${r1(y - font * 0.55)}" font-size="${font - 1}">${names[q]}</text>` +
        `<text class="mc-value ${q}" x="${x}" y="${r1(y + font * 0.75)}" font-size="${font + 1}">${usd(mc.percentiles[q][end], { step: 1000, compact: w < 500 })}</text>` +
        `</g>`;
    }
  }

  const end = months.length - 1;
  const desc = `Each faint line is one simulated year of one listing's cumulative profit, starting today. ` +
    `After ${months[end]} months, one year in ten ends below ${usd(mc.percentiles.p10[end], { step: 1000 })}, the median year at ${usd(mc.percentiles.p50[end], { step: 1000 })}, ` +
    `and one in ten above ${usd(mc.percentiles.p90[end], { step: 1000 })}. Share of simulated months at a loss: ${(mc.share_losing * 100).toFixed(1)}%.`;
  return frame(w, h, `mc mc--${variant}`, { id: `${id}-t`, text: "Ten thousand simulated years of one listing's profit" }, { id: `${id}-d`, text: desc }, body);
}

// ---------------------------------------------------------------- the staircase

/**
 * st.treads: [[edge_oz, fee], ...] for the card in force; st.alt: the same for the
 * other card (dashed); st.listing / st.edge: the solid and hollow dots.
 */
export function staircaseSVG(st, opts) {
  const { id, w, h, m, font = 13, xMax } = opts;
  const treads = st.treads.filter(([e]) => e <= xMax);
  const alt = st.alt.filter(([e]) => e <= xMax);
  const fees = [...treads, ...alt].map(([, f]) => f);
  const yt = niceTicks(Math.min(...fees) - 0.15, Math.max(...fees) + 0.1, 4);
  const d0 = Math.min(yt[0], Math.min(...fees) - 0.15), d1 = Math.max(yt[yt.length - 1], Math.max(...fees) + 0.1);
  const X = scale(0, xMax, m.l, w - m.r), Y = scale(d0, d1, h - m.b, m.t);

  const stairs = (rows) => {
    let d = `M${r1(X(0))},${r1(Y(rows[0][1]))}`;
    rows.forEach(([edge, fee], i) => {
      d += ` H${r1(X(edge))}`;
      if (i + 1 < rows.length) d += ` V${r1(Y(rows[i + 1][1]))}`;
    });
    return d;
  };

  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">$${t.toFixed(2)}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const [edge] of [[0], ...treads]) {
    body += `<line class="tick" x1="${r1(X(edge))}" x2="${r1(X(edge))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(edge))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">${edge === xMax ? `${edge} oz` : edge}</text>`;
  }

  // The holiday card dashed (a dash pattern cannot share pathLength="1", so it fades in);
  // the card in force solid, drawn.
  body += `<path class="step-alt fade" style="--after:0ms" d="${stairs(alt)}"/>`;
  body += `<path class="step draw" pathLength="1" d="${stairs(treads)}"/>`;

  // The key, above the plot, so it never sits on a gridline.
  const kx = m.l, ky = font * 0.9, kl = font * 1.7;
  body += `<g class="fade" style="--after:0ms">` +
    `<line class="key-solid" x1="${kx}" x2="${kx + kl}" y1="${ky}" y2="${ky}"/>` +
    `<text class="ink" x="${kx + kl + 8}" y="${ky}" font-size="${font - 1}" dominant-baseline="middle">${esc(st.label)}</text>` +
    `<line class="step-alt" x1="${kx}" x2="${kx + kl}" y1="${ky + font * 1.6}" y2="${ky + font * 1.6}"/>` +
    `<text x="${kx + kl + 8}" y="${ky + font * 1.6}" font-size="${font - 1}" dominant-baseline="middle">${esc(st.altLabel)}</text>` +
    `</g>`;

  // The finding: one riser, in the accent, between the two dots. Both dots are
  // labelled in the clear space under the tread they sit on.
  const ex = X(st.edge.oz), yLo = Y(st.edge.fee), yHi = Y(st.listing.fee), lx = X(st.listing.oz);
  const r = font < 13 ? 4.5 : 5.5;
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<line class="leak" x1="${r1(ex)}" x2="${r1(ex)}" y1="${r1(yLo)}" y2="${r1(yHi)}"/>`;
  body += `<circle class="dot-hollow" cx="${r1(ex)}" cy="${r1(yLo)}" r="${r}"/>`;
  body += `<circle class="dot" cx="${r1(lx)}" cy="${r1(yHi)}" r="${r}"/>`;
  body += `<text class="leak-text" x="${r1(ex - 10)}" y="${r1((yLo + yHi) / 2)}" font-size="${font + 1}" text-anchor="end" dominant-baseline="middle">+${perUnit(st.step)} a unit</text>`;
  body += `<text class="ink strong" x="${r1(lx + r + 6)}" y="${r1(yHi + font + 6)}" font-size="${font}">${st.listing.oz.toFixed(1)} oz · this listing</text>`;
  body += `<text x="${r1(ex + r + 6)}" y="${r1(yLo + font + 8)}" font-size="${font}">${st.edge.oz.toFixed(1)} oz · one step down</text>`;
  body += `</g>`;

  const desc = `Amazon's fulfilment fee climbs in steps as shipping weight crosses each band edge. ` +
    `This listing ships at ${st.listing.oz.toFixed(1)} ounces, just past the ${st.edge.oz}-ounce edge, so every unit pays ${perUnit(st.step)} more than it would one step down.`;
  return frame(w, h, "stairs", { id: `${id}-t`, text: "Amazon's fee staircase, with one listing just past an edge" }, { id: `${id}-d`, text: desc }, body);
}

// ---------------------------------------------------------------- the aging cliff

/** ag.bands: [{from, to, value}] by age in days; ag.cliff: the day the step is drawn in the accent. */
export function agingSVG(ag, opts) {
  const { id, w, h, m, font = 13, xMax = 400 } = opts;
  const vals = ag.bands.map((b) => b.value);
  const yt = niceTicks(0, Math.max(...vals) * 1.08, 3);
  const d1 = Math.max(yt[yt.length - 1], Math.max(...vals) * 1.08);
  const X = scale(0, xMax, m.l, w - m.r), Y = scale(0, d1, h - m.b, m.t);

  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">$${t}</text>`;
  }
  for (const d of ag.ticks) {
    body += `<line class="tick" x1="${r1(X(d))}" x2="${r1(X(d))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(d))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle"${d === ag.cliff ? ' class="ink strong"' : ""}>${d === 0 ? "Day 0" : d}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;

  let d = `M${r1(X(0))},${r1(Y(ag.bands[0].value))}`;
  ag.bands.forEach((b, i) => {
    const to = b.to == null ? xMax : b.to + 1;
    d += ` H${r1(X(Math.min(to, xMax)))}`;
    if (i + 1 < ag.bands.length) d += ` V${r1(Y(ag.bands[i + 1].value))}`;
  });
  body += `<path class="step draw" pathLength="1" d="${d}"/>`;

  const i = ag.bands.findIndex((b) => b.from === ag.cliff);
  const before = ag.bands[i - 1].value, after = ag.bands[i].value, cx = X(ag.cliff);
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<line class="leak" x1="${r1(cx)}" x2="${r1(cx)}" y1="${r1(Y(before))}" y2="${r1(Y(after))}"/>`;
  body += `<text class="leak-text" x="${r1(cx - 12)}" y="${r1(Y(after) - 4)}" font-size="${font + 1}" text-anchor="end">$${Math.round(before)} → $${Math.round(after)} a month</text>`;
  body += `</g>`;

  const desc = `Monthly storage plus Amazon's aged-inventory surcharge on 1,000 units of this listing, by how long they have sat. ` +
    `At day ${ag.cliff} it steps from $${Math.round(before)} to $${Math.round(after)} a month.`;
  return frame(w, h, "aging", { id: `${id}-t`, text: "What 1,000 units cost to store, by age" }, { id: `${id}-d`, text: desc }, body);
}
