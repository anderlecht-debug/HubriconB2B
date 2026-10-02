// The home page's three pictures, as SVG strings: the Monte Carlo, Amazon's fee
// staircase and the aged-inventory cliff. Pure functions of their data, so
// scripts/build-pages.mjs bakes each one into index.html as its finished still
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

/**
 * The readout a reader can scrub (assets/site.js): {f: font, t: top, b: bottom, p: [[x, [y…], [line…]], …]}
 * in the chart's own units. A progressive enhancement: the chart's <desc> already says what it shows.
 */
const scrubOf = (font, top, bottom, rows) => ({ f: font, t: r1(top), b: r1(bottom), p: rows.map(([x, ys, lines]) => [r1(x), ys.map(r1), lines]) });

function frame(w, h, cls, title, desc, body, scrub = null) {
  const data = scrub ? ` data-scrub="${esc(JSON.stringify(scrub))}"` : "";
  return `<svg class="chart ${cls}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="${title.id} ${desc.id}" preserveAspectRatio="xMidYMid meet"${data}>` +
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
  const scrub = full ? scrubOf(font, m.t, h - m.b, months.map((mo, i) => [X(mo), [Y(mc.percentiles.p90[i]), Y(mc.percentiles.p50[i]), Y(mc.percentiles.p10[i])],
    [mo === 0 ? "Today" : `Month ${mo}`, `P90 ${usd(mc.percentiles.p90[i], { step: 1000 })}`, `Median ${usd(mc.percentiles.p50[i], { step: 1000 })}`, `P10 ${usd(mc.percentiles.p10[i], { step: 1000 })}`]])) : null;
  return frame(w, h, `mc mc--${variant}`, { id: `${id}-t`, text: "Ten thousand simulated years of one listing's profit" }, { id: `${id}-d`, text: desc }, body, scrub);
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
  const feeAt = (rows, oz) => (rows.find(([e]) => oz <= e) || rows[rows.length - 1])[1];
  const ozs = Array.from({ length: Math.round(xMax * 2) }, (_, i) => (i + 1) / 2);
  const scrub = scrubOf(font, m.t, h - m.b, ozs.map((oz) => [X(oz), [Y(feeAt(treads, oz)), Y(feeAt(alt, oz))],
    [`${oz.toFixed(1)} oz`, `${perUnit(feeAt(treads, oz))}, ${st.label}`, `${perUnit(feeAt(alt, oz))}, ${st.altLabel}`]]));
  return frame(w, h, "stairs", { id: `${id}-t`, text: "Amazon's fee staircase, with one listing just past an edge" }, { id: `${id}-d`, text: desc }, body, scrub);
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

// ---------------------------------------------------------------- the aging strip

/**
 * The aging strip (HUBRICON_SPEC.md, "Displaying the case study", layer 2, third
 * visual): one unit's clock toward the 271-day cliff. A strip from the day a unit
 * reaches Amazon ("Today"), cut into the storage-cost bands it passes through, each
 * marked with what 1,000 of these units cost a month there; the bands from the cliff
 * on are the leak, so they alone take the accent. Each day tick carries data-days, so
 * the page can print the calendar date that day falls on for the person reading it;
 * the still frame shows day numbers.
 */
export function agingStripSVG(ag, opts) {
  const { id, w, h, m, font = 13, xMax = 420, ticks = ag.ticks } = opts;
  const X = scale(0, xMax, m.l, w - m.r);
  const y0 = m.t, bh = h - m.t - m.b;
  const end = (b) => Math.min(b.to == null ? xMax : b.to + 1, xMax);
  let body = "";
  ag.bands.forEach((b, i) => {
    const x0 = X(b.from), x1 = X(end(b)), leak = b.from >= ag.cliff;
    const tone = leak ? "seg-leak" : `seg-${Math.min(i, 3)}`;
    body += `<rect class="seg ${tone} fade" style="--after:${120 * i}ms" x="${r1(x0)}" y="${y0}" width="${r1(Math.max(0, x1 - x0 - 2))}" height="${bh}"/>`;
    if (x1 - x0 >= font * 3.4) {
      body += `<text class="${leak ? "seg-text-leak" : "seg-text"} fade" style="--after:${120 * i + 200}ms" x="${r1(x0 + 8)}" y="${r1(y0 + bh / 2)}" font-size="${font}" dominant-baseline="middle">$${Math.round(b.value)}</text>`;
    }
  });
  // Today, at day 0.
  body += `<line class="tick" x1="${r1(X(0))}" x2="${r1(X(0))}" y1="${y0 - 10}" y2="${y0 + bh + 6}"/>`;
  body += `<text class="ink strong" x="${r1(X(0))}" y="${y0 - 16}" font-size="${font}">Today</text>`;
  // The cliff: a riser in the accent, named.
  const cx = X(ag.cliff);
  const before = ag.bands.find((b) => b.to === ag.cliff - 1)?.value, after = ag.bands.find((b) => b.from === ag.cliff)?.value;
  body += `<line class="leak fade" style="--after:900ms" x1="${r1(cx - 1)}" x2="${r1(cx - 1)}" y1="${y0 - 10}" y2="${y0 + bh + 6}"/>`;
  if (before != null && after != null) {
    body += `<text class="leak-text fade" style="--after:900ms" x="${r1(cx - 8)}" y="${y0 - 16}" font-size="${font}" text-anchor="end">$${Math.round(before)} → $${Math.round(after)} a month</text>`;
  }
  // Day ticks, with an empty line for the visitor's calendar date.
  for (const d of ticks) {
    const x = r1(X(d)), anchor = d === 0 ? "start" : "middle";
    body += `<line class="tick" x1="${x}" x2="${x}" y1="${y0 + bh}" y2="${y0 + bh + 6}"/>`;
    body += `<text x="${x}" y="${y0 + bh + font + 12}" font-size="${font}" text-anchor="${anchor}"${d === ag.cliff ? ' class="ink strong"' : ""}>Day ${d}</text>`;
    body += `<text class="strip-date" data-days="${d}" x="${x}" y="${y0 + bh + 2 * font + 18}" font-size="${font - 1}" text-anchor="${anchor}"></text>`;
  }
  const desc = `A unit that reaches Amazon today is in the cheapest storage band until day 181, steps up each month after, and at day ${ag.cliff} goes from $${Math.round(before)} to $${Math.round(after)} a month for every 1,000 units.`;
  return frame(w, h, "strip", { id: `${id}-t`, text: "One unit's clock toward the 271-day cliff" }, { id: `${id}-d`, text: desc }, body);
}

// ---------------------------------------------------------------- the price curve

/**
 * The fit: one SKU's periods as dots (price against units a day) and the demand curve the
 * log-log fit draws through them, units = e^a · price^ε. fit: {points: [{price, perDay}],
 * intercept, elasticity, lo, hi}.
 */
export function fitSVG(fit, opts) {
  const { id, w, h, m, font = 13 } = opts;
  const prices = fit.points.map((p) => p.price), rates = fit.points.map((p) => p.perDay);
  const pLo = Math.min(...prices) * 0.97, pHi = Math.max(...prices) * 1.03;
  const curve = (p) => Math.exp(fit.intercept) * p ** fit.elasticity;
  const xt = niceTicks(pLo, pHi, 4), yt = niceTicks(Math.min(...rates) * 0.9, Math.max(...rates) * 1.08, 4);
  const X = scale(pLo, pHi, m.l, w - m.r);
  const y0 = Math.min(yt[0], Math.min(...rates) * 0.9), y1 = Math.max(yt[yt.length - 1], Math.max(...rates) * 1.08);
  const Y = scale(y0, y1, h - m.b, m.t);
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${t}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const t of xt.filter((t) => t >= pLo && t <= pHi)) {
    body += `<line class="tick" x1="${r1(X(t))}" x2="${r1(X(t))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(t))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">$${t}</text>`;
  }
  body += `<text x="0" y="${m.t - font}" font-size="${font}">Units a day</text>`;
  const n = 48, xs = [], ys = [];
  for (let i = 0; i <= n; i++) { const p = pLo + ((pHi - pLo) * i) / n; xs.push(X(p)); ys.push(Y(curve(p))); }
  body += `<path class="step draw" pathLength="1" d="${line(pts(xs, ys))}"/>`;
  const r = font < 13 ? 4 : 5;
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .6)">` +
    fit.points.map((p) => `<circle class="dot" cx="${r1(X(p.price))}" cy="${r1(Y(p.perDay))}" r="${r}"/>`).join("") + `</g>`;
  const lab = `Elasticity ${minus(fit.elasticity, 2)}, interval ${minus(fit.lo, 2)} to ${minus(fit.hi, 2)}`;
  body += `<text class="ink strong fade" style="--after:var(--mc-draw-ms)" x="${w - m.r}" y="${m.t - font}" font-size="${font}" text-anchor="end">${esc(lab)}</text>`;
  const desc = `Each dot is one period's average price and units sold a day. The line is the demand curve the log-log fit draws through them: ${lab}.`;
  const scrub = scrubOf(font, m.t, h - m.b, xs.map((x, i) => { const p = pLo + ((pHi - pLo) * i) / n; return [x, [ys[i]], [`At $${p.toFixed(2)}`, `${curve(p).toFixed(1)} units a day, on the fit`]]; }));
  return frame(w, h, "fit", { id: `${id}-t`, text: "One listing's sales history and the demand curve fitted to it" }, { id: `${id}-d`, text: desc }, body, scrub);
}

const minus = (v, d) => (v < 0 ? `−${Math.abs(v).toFixed(d)}` : v.toFixed(d));

/**
 * Profit a month against price, at the fitted elasticity and at both ends of its interval.
 * All three pass through today's price, where volume is what it is. pc: {p0, q0, cost, fee,
 * fixed, eps, lo, hi, best, step, range: [lo, hi]}.
 */
export function profitSVG(pc, opts) {
  const { id, w, h, m, font = 13, narrow = false } = opts;
  const prof = (e, p) => pc.q0 * (p / pc.p0) ** e * (p * (1 - pc.fee) - pc.cost - pc.fixed);
  const [pLo, pHi] = pc.range;
  const n = 64, curves = [pc.eps, pc.lo, pc.hi].map((e) => {
    const out = [];
    for (let i = 0; i <= n; i++) { const p = pLo + ((pHi - pLo) * i) / n; out.push([p, prof(e, p)]); }
    return out;
  });
  const vals = curves.flat().map(([, v]) => v);
  const yt = niceTicks(Math.min(...vals), Math.max(...vals), 4);
  const y0 = Math.min(yt[0], Math.min(...vals)), y1 = Math.max(yt[yt.length - 1], Math.max(...vals));
  const X = scale(pLo, pHi, m.l, w - m.r), Y = scale(y0, y1, h - m.b, m.t);
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${usd(t, { compact: true })}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const t of niceTicks(pLo, pHi, narrow ? 3 : 5).filter((t) => t >= pLo && t <= pHi)) {
    body += `<line class="tick" x1="${r1(X(t))}" x2="${r1(X(t))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(t))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">$${t}</text>`;
  }
  body += `<text x="0" y="${m.t - font}" font-size="${font}">Profit a month</text>`;
  const path = (c) => line(pts(c.map(([p]) => X(p)), c.map(([, v]) => Y(v))));
  body += `<path class="curve-alt fade" style="--after:0ms" d="${path(curves[1])}"/>`;
  body += `<path class="curve-alt fade" style="--after:0ms" d="${path(curves[2])}"/>`;
  body += `<path class="curve draw" pathLength="1" d="${path(curves[0])}"/>`;
  // the three curves' names, at the right edge, spread so none sits on another
  const ends = spread([
    { y: Y(curves[0][n][1]), t: `${minus(pc.eps, 2)}, the estimate`, cls: "leak-text" },
    { y: Y(curves[1][n][1]), t: `${minus(pc.lo, 2)}`, cls: "" },
    { y: Y(curves[2][n][1]), t: `${minus(pc.hi, 2)}`, cls: "" },
  ], font + 4, m.t, h - m.b);
  if (!narrow) body += `<g class="fade" style="--after:var(--mc-draw-ms)">` + ends.map((e) => `<text class="${e.cls}" x="${w - m.r + 8}" y="${r1(e.y)}" font-size="${font}" dominant-baseline="middle">${esc(e.t)}</text>`).join("") + `</g>`;
  const r = font < 13 ? 4.5 : 5.5;
  const today = [X(pc.p0), Y(prof(pc.eps, pc.p0))], step = [X(pc.step), Y(prof(pc.eps, pc.step))];
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<circle class="dot" cx="${r1(today[0])}" cy="${r1(today[1])}" r="${r}"/>`;
  body += `<text class="ink strong" x="${r1(today[0] - r - 4)}" y="${r1(today[1] + font + 8)}" font-size="${font}" text-anchor="end">Today $${pc.p0.toFixed(2)}</text>`;
  body += `<circle class="dot-hollow" cx="${r1(step[0])}" cy="${r1(step[1])}" r="${r}"/>`;
  // Next's label starts right of the best-price line when the two are close, never across it.
  const nextX = pc.best && pc.best > pc.step ? Math.max(step[0] + r + 4, X(pc.best) + 6) : step[0] + r + 4;
  body += `<text x="${r1(nextX)}" y="${r1(step[1] + font + 8)}" font-size="${font}">Next $${pc.step.toFixed(2)}</text>`;
  if (pc.best) {
    const best = [X(pc.best), Y(prof(pc.eps, pc.best))];
    body += `<line class="leak" x1="${r1(best[0])}" x2="${r1(best[0])}" y1="${r1(best[1])}" y2="${h - m.b}"/>`;
    body += `<text class="leak-text" x="${r1(best[0] + 8)}" y="${r1(h - m.b - font)}" font-size="${font}">Best $${pc.best.toFixed(2)}</text>`;
  }
  body += `</g>`;
  const desc = `Profit a month against price. The solid line uses the fitted elasticity, ${minus(pc.eps, 2)}; the dashed lines use the ends of its interval. ` +
    `All three pass through today's price. The solid line is flat across the top: a few percent either side of the best price costs little.`;
  const scrub = scrubOf(font, m.t, h - m.b, curves[0].map(([p, v], i) => [X(p), [Y(v), Y(curves[1][i][1]), Y(curves[2][i][1])],
    [`At $${p.toFixed(2)}`, `${usd(v)} a month at ${minus(pc.eps, 2)}`, `${usd(curves[1][i][1])} at ${minus(pc.lo, 2)}`, `${usd(curves[2][i][1])} at ${minus(pc.hi, 2)}`]]));
  return frame(w, h, "profit", { id: `${id}-t`, text: "Profit a month against price, at the fitted elasticity and at the ends of its interval" }, { id: `${id}-d`, text: desc }, body, scrub);
}

// ---------------------------------------------------------------- the cash path

/**
 * c: Capital & Cash's cash figures (data/learn-capital-cash.json "cash"). The median path,
 * in steps, from today's balance; with opts.band, the 5th–95th percentile band and the 5th
 * percentile line under it. The wire and the low point are marked; the payouts are the steps.
 */
export function cashSVG(c, opts) {
  const { id, w, h, m, font = 13, band = false, narrow = false } = opts;
  // these labels repeat figures the lesson prints, rounded as the lesson rounds them
  const whole = (v) => `${v < 0 ? "−" : ""}$${Math.round(Math.abs(v)).toLocaleString("en-US")}`;
  const days = c.p50.length;
  const at = (arr) => [c.start, ...arr];                  // day 0 is today's balance
  const p50 = at(c.p50), p5 = at(c.p5), p95 = at(c.p95);
  const all = band ? [...p5, ...p95] : p50;
  const yt = niceTicks(Math.min(0, ...all), Math.max(...all), 4);
  const y0 = Math.min(yt[0], ...all), y1 = Math.max(yt[yt.length - 1], ...all);
  const X = scale(0, days, m.l, w - m.r), Y = scale(y0, y1, h - m.b, m.t);
  // steps: the balance holds through a day and moves at its end
  const stepped = (arr) => `M${r1(X(0))},${r1(Y(arr[0]))}` + arr.slice(1).map((v, i) => ` H${r1(X(i + 1))} V${r1(Y(v))}`).join("");
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${usd(t, { compact: true })}</text>`;
  }
  body += `<line class="cash-zero" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(0))}" y2="${r1(Y(0))}"/>`;
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  const xl = narrow ? [[0, "Today", "start"], [days, `${days} days`, "end"]] : [[0, "Today", "start"], [30, "30 days", "middle"], [60, "60 days", "middle"], [days, `${days} days`, "end"]];
  for (const [v, t, a] of xl) body += `<text x="${r1(X(v))}" y="${h - m.b + font + 12}" font-size="${font}" text-anchor="${a}">${t}</text>`;
  if (band) {
    const lo = p5.map((v, i) => [X(i), Y(v)]), hi = p95.map((v, i) => [X(i), Y(v)]);
    body += `<path class="cash-band fade" d="M${hi.map(([x, y]) => `${r1(x)},${r1(y)}`).join(" L")} L${lo.reverse().map(([x, y]) => `${r1(x)},${r1(y)}`).join(" L")}Z"/>`;
    body += `<path class="cash-p5 draw" pathLength="1" d="${stepped(p5)}"/>`;
  }
  body += `<path class="cash-p50 draw" pathLength="1" d="${stepped(p50)}"/>`;
  // the wire, and the low point the median reaches before the next payout
  const r = font < 13 ? 4.5 : 5.5;
  const wx = X(c.wire_day), wy0 = Y(p50[c.wire_day - 1]), wy1 = Y(p50[c.wire_day]);
  const tx = X(c.trough_day), ty = Y(band ? c.trough_p5 : c.trough_median);
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<line class="leak" x1="${r1(wx)}" x2="${r1(wx)}" y1="${r1(wy0)}" y2="${r1(wy1)}"/>`;
  // the wire's name sits right of the drop, at its top, clear of the path on either side
  body += `<text class="leak-text" x="${r1(wx + 8)}" y="${r1(wy0 + font * 0.4)}" font-size="${font}" dominant-baseline="middle">The wire ${whole(c.wire)}</text>`;
  body += `<circle class="${band ? "dot-blue" : "dot"}" cx="${r1(tx)}" cy="${r1(ty)}" r="${r}"/>`;
  const label = band ? `Bad case ${whole(c.trough_p5)}, day ${c.trough_day}` : `Low point ${whole(c.trough_median)}, day ${c.trough_day}`;
  body += `<text class="ink strong" x="${r1(tx + r + 6)}" y="${r1(ty + font + 6)}" font-size="${font}">${label}</text>`;
  body += `</g>`;
  const desc = band
    ? `Ten thousand simulated paths of the bank balance over ${days} days. The band holds nine paths in ten; its lower edge is the 5th percentile. ` +
      `After the wire of ${whole(c.wire)} on day ${c.wire_day}, the bad case bottoms at ${whole(c.trough_p5)} on day ${c.trough_day}, the day before a payout.`
    : `The median bank balance over ${days} days, starting at ${whole(c.start)}. Fixed costs drain it every day, payouts lift it every ${c.payout_days[1] - c.payout_days[0]} days, ` +
      `and the wire of ${whole(c.wire)} on day ${c.wire_day} takes it to its low point, ${whole(c.trough_median)} on day ${c.trough_day}, the day before the next payout.`;
  const scrub = scrubOf(font, m.t, h - m.b, p50.map((v, d) => [X(d), band ? [Y(p95[d]), Y(v), Y(p5[d])] : [Y(v)],
    band ? [d === 0 ? "Today" : `Day ${d}`, `1 in 20 above ${whole(p95[d])}`, `Median ${whole(v)}`, `1 in 20 below ${whole(p5[d])}`]
         : [d === 0 ? "Today" : `Day ${d}`, `Balance ${whole(v)}`]]));
  return frame(w, h, "cash", { id: `${id}-t`, text: band ? "The bank balance over 90 days, ten thousand ways" : "The bank balance over 90 days, the median path" }, { id: `${id}-d`, text: desc }, body, scrub);
}

// ---------------------------------------------------------------- two weeks late

/** late: Capital & Cash's "late" figures. The chance of running out, by days late. */
export function lateSVG(late, opts) {
  const { id, w, h, m, font = 13 } = opts;
  const curve = late.curve, n = curve[curve.length - 1].days_late;
  const top = Math.max(...curve.map((p) => p.p_out));
  const yt = niceTicks(0, top, 4);
  const X = scale(0, n, m.l, w - m.r), Y = scale(0, Math.max(yt[yt.length - 1], top), h - m.b, m.t);
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${Math.round(t * 100)}%</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const d of [0, 7, 14, 21, 28].filter((d) => d <= n)) {
    body += `<line class="tick" x1="${r1(X(d))}" x2="${r1(X(d))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(d))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">${d === 0 ? "On time" : `${d} days`}</text>`;
  }
  body += `<text x="0" y="${m.t - font}" font-size="${font}">Chance of running out before the order lands</text>`;
  body += `<path class="curve draw" pathLength="1" d="${line(pts(curve.map((p) => X(p.days_late)), curve.map((p) => Y(p.p_out))))}"/>`;
  const r = font < 13 ? 4.5 : 5.5;
  const a = late.on_time, b = late.two_weeks;
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<circle class="dot" cx="${r1(X(0))}" cy="${r1(Y(a.p_out))}" r="${r}"/>`;
  body += `<text class="ink strong" x="${r1(X(0) + r + 6)}" y="${r1(Y(a.p_out) - r - 4)}" font-size="${font}">${Math.round(a.p_out * 100)}%</text>`;
  body += `<circle class="dot-blue" cx="${r1(X(b.days_late))}" cy="${r1(Y(b.p_out))}" r="${r}"/>`;
  body += `<text class="leak-text" x="${r1(X(b.days_late) - r - 6)}" y="${r1(Y(b.p_out) - r - 4)}" font-size="${font}" text-anchor="end">${Math.round(b.p_out * 100)}%, two weeks late</text>`;
  body += `</g>`;
  const desc = `The chance the stock runs out before the order lands, by how many days after the reorder point the wire goes. ` +
    `On time it is ${Math.round(a.p_out * 100)}%; two weeks late it is ${Math.round(b.p_out * 100)}%.`;
  const scrub = scrubOf(font, m.t, h - m.b, curve.map((p) => [X(p.days_late), [Y(p.p_out)],
    [p.days_late === 0 ? "On time" : `${p.days_late} days late`, `${(p.p_out * 100).toFixed(1)}% chance of running out`, `${Math.round(p.units_short)} units short, on average`]]));
  return frame(w, h, "late", { id: `${id}-t`, text: "The chance of running out, by days late" }, { id: `${id}-d`, text: desc }, body, scrub);
}

// ---------------------------------------------------------------- the parcel staircase

/**
 * pc: USPS Ground Advantage commercial rates by weight (the rate card's carrier rows), the
 * farthest zone solid and the nearest dashed, with one invented parcel just past the pound
 * line. Anything over a pound bills at the next whole pound, so the step at 16 oz is from the
 * under-a-pound rate to the 2 lb rate.
 */
export function parcelSVG(pc, opts) {
  const { id, w, h, m, font = 13 } = opts;
  const xMax = 48;
  const near = [[16, pc.rows["0"][0]], [32, pc.rows["32"][0]], [48, pc.rows["48"][0]]];
  const far = [[16, pc.rows["0"][7]], [32, pc.rows["32"][7]], [48, pc.rows["48"][7]]];
  const all = [...near, ...far].map(([, v]) => v);
  const yt = niceTicks(Math.min(...all) - 0.5, Math.max(...all) + 0.5, 4);
  const d0 = Math.min(yt[0], Math.min(...all) - 0.5), d1 = Math.max(yt[yt.length - 1], Math.max(...all) + 0.5);
  const X = scale(0, xMax, m.l, w - m.r), Y = scale(d0, d1, h - m.b, m.t);
  const stairs = (rows) => {
    let d = `M${r1(X(0))},${r1(Y(rows[0][1]))}`;
    rows.forEach(([edge], i) => { d += ` H${r1(X(edge))}`; if (i + 1 < rows.length) d += ` V${r1(Y(rows[i + 1][1]))}`; });
    return d;
  };
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">$${t.toFixed(2)}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const e of [0, 16, 32, 48]) {
    body += `<line class="tick" x1="${r1(X(e))}" x2="${r1(X(e))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(e))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">${e === xMax ? "48 oz" : e}</text>`;
  }
  body += `<path class="step-alt fade" style="--after:0ms" d="${stairs(near)}"/>`;
  body += `<path class="step draw" pathLength="1" d="${stairs(far)}"/>`;
  const kx = m.l, ky = font * 0.9, kl = font * 1.7;
  body += `<g class="fade" style="--after:0ms">` +
    `<line class="key-solid" x1="${kx}" x2="${kx + kl}" y1="${ky}" y2="${ky}"/>` +
    `<text class="ink" x="${kx + kl + 8}" y="${ky}" font-size="${font - 1}" dominant-baseline="middle">The farthest zone (8)</text>` +
    `<line class="step-alt" x1="${kx}" x2="${kx + kl}" y1="${ky + font * 1.6}" y2="${ky + font * 1.6}"/>` +
    `<text x="${kx + kl + 8}" y="${ky + font * 1.6}" font-size="${font - 1}" dominant-baseline="middle">The nearest zone (1)</text>` +
    `</g>`;
  // the invented parcel, just past the pound line, on the farthest zone; one step down, under a pound
  const r = font < 13 ? 4.5 : 5.5;
  const ex = X(16), yLo = Y(pc.rows["0"][7]), yHi = Y(pc.rows["32"][7]), px = X(pc.parcel_oz);
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  body += `<line class="leak" x1="${r1(ex)}" x2="${r1(ex)}" y1="${r1(yLo)}" y2="${r1(yHi)}"/>`;
  body += `<circle class="dot-hollow" cx="${r1(ex - 1.5)}" cy="${r1(yLo)}" r="${r}"/>`;
  body += `<circle class="dot" cx="${r1(px)}" cy="${r1(yHi)}" r="${r}"/>`;
  body += `<text class="leak-text" x="${r1(ex - 10)}" y="${r1((yLo + yHi) / 2)}" font-size="${font + 1}" text-anchor="end" dominant-baseline="middle">+${perUnit(pc.step[0])} to ${perUnit(pc.step[1])}</text>`;
  body += `<text class="leak-text" x="${r1(ex - 10)}" y="${r1((yLo + yHi) / 2 + font + 4)}" font-size="${font - 1}" text-anchor="end" dominant-baseline="middle">a parcel, by zone</text>`;
  body += `<text class="ink strong" x="${r1(px + r + 6)}" y="${r1(yHi - r - 6)}" font-size="${font}">${pc.parcel_oz} oz · an invented parcel</text>`;
  body += `</g>`;
  const desc = `USPS Ground Advantage's 2026 commercial rates climb a step at every pound, because anything over a pound bills at the next whole pound. ` +
    `A parcel at ${pc.parcel_oz} ounces pays the 2 lb rate: ${perUnit(pc.step[0])} to ${perUnit(pc.step[1])} more a parcel than one under a pound, depending on the zone.`;
  const rowAt = (oz) => pc.rows[oz < 16 ? "0" : oz === 16 ? "16" : String(Math.ceil(oz / 16) * 16)];
  const billed = (oz) => (oz < 16 ? "under a pound" : `${Math.ceil(oz / 16)} lb`);
  const ozs = Array.from({ length: xMax * 2 }, (_, i) => (i + 1) / 2);
  const scrub = scrubOf(font, m.t, h - m.b, ozs.map((oz) => [X(oz), [Y(rowAt(oz)[7]), Y(rowAt(oz)[0])],
    [`${oz.toFixed(1)} oz bills as ${billed(oz)}`, `Farthest zone ${perUnit(rowAt(oz)[7])}`, `Nearest zone ${perUnit(rowAt(oz)[0])}`]]));
  return frame(w, h, "stairs", { id: `${id}-t`, text: "The parcel staircase: USPS Ground Advantage by weight" }, { id: `${id}-d`, text: desc }, body, scrub);
}

// ---------------------------------------------------------------- one order's money

/**
 * o: The Shopify Margin's order figures. One bar per zone (the nearest and the farthest), the
 * price split left to right into Shopify Payments, the label, packing, landed cost and what is
 * kept before ads; only what is kept is in the money colour.
 */
export function orderSVG(o, opts) {
  const { id, w, h, m, font = 13 } = opts;
  const bars = o.zones.map((z, i) => ({ z, parts: [
    ["Shopify Payments", o.fee], ["The label", o.labels[i]], ["Packing", o.packing], ["Landed cost", o.landed], ["Kept before ads", o.price - o.fee - o.labels[i] - o.packing - o.landed],
  ] }));
  const X = scale(0, o.price, m.l, w - m.r);
  const bh = Math.min(56, (h - m.t - m.b) / (bars.length * 1.9));
  let body = "";
  bars.forEach((b, i) => {
    const y = m.t + i * bh * 1.9;
    body += `<text class="ink strong" x="${m.l}" y="${r1(y - 8)}" font-size="${font}">Zone ${b.z}</text>`;
    let x0 = 0;
    b.parts.forEach(([name, v], k) => {
      const kept = k === b.parts.length - 1;
      const x = X(x0), wd = X(x0 + v) - X(x0);
      body += `<rect class="${kept ? "seg seg-kept" : "seg"} fade" style="--after:${k * 120}ms" x="${r1(x)}" y="${r1(y)}" width="${r1(Math.max(0, wd))}" height="${r1(bh)}"/>`;
      if (wd > font * 3.4) body += `<text class="${kept ? "seg-text-kept" : "seg-text"} fade" style="--after:${k * 120 + 200}ms" x="${r1(x + wd / 2)}" y="${r1(y + bh / 2)}" font-size="${font}" text-anchor="middle" dominant-baseline="middle">$${v.toFixed(2)}</text>`;
      x0 += v;
    });
  });
  // the names once, under the last bar, each at its own segment's middle where it fits
  const last = bars[bars.length - 1], yl = m.t + (bars.length - 1) * bh * 1.9 + bh + font + 10;
  let x0 = 0;
  const names = [];
  last.parts.forEach(([name, v]) => { names.push({ x: X(x0 + v / 2), name }); x0 += v; });
  names.forEach((nm, k) => {
    const anchor = k === 0 ? "start" : k === names.length - 1 ? "end" : "middle";
    const x = k === 0 ? m.l : k === names.length - 1 ? w - m.r : nm.x;
    body += `<text x="${r1(x)}" y="${r1(yl + (k % 2) * (font + 4))}" font-size="${font - 1}" text-anchor="${anchor}">${esc(nm.name)}</text>`;
  });
  body += `<text x="${w - m.r}" y="${m.t - font - 8}" font-size="${font}" text-anchor="end">Price $${o.price.toFixed(2)}</text>`;
  const desc = `One order at $${o.price.toFixed(2)}: Shopify Payments $${o.fee.toFixed(2)}, the label $${o.labels[0].toFixed(2)} to the nearest zone and $${o.labels[1].toFixed(2)} to the farthest, packing $${o.packing.toFixed(2)}, landed cost $${o.landed.toFixed(2)}; ` +
    `kept before ads $${(o.price - o.fee - o.labels[1] - o.packing - o.landed).toFixed(2)} to $${(o.price - o.fee - o.labels[0] - o.packing - o.landed).toFixed(2)}.`;
  return frame(w, h, "order", { id: `${id}-t`, text: "Where one order's money goes, nearest zone and farthest" }, { id: `${id}-d`, text: desc }, body);
}

// ---------------------------------------------------------------- The Operator's Math

/**
 * One order's money, top to bottom: the price, each cost taken off where it falls, what the order
 * keeps before ads, the ads, and what it keeps after. wf: {price, costs: [[name, $]…], ads}.
 * The two "kept" bars are the money, so they alone are blue.
 */
export function waterfallSVG(wf, opts) {
  const { id, w, h, m, font = 13, labelW = 150 } = opts;
  const before = wf.price - wf.costs.reduce((a, [, v]) => a + v, 0), after = before - wf.ads;
  const rows = [["Price", 0, wf.price, "seg"]];
  let run = wf.price;
  for (const [name, v] of wf.costs) { rows.push([name, run - v, run, "seg"]); run -= v; }
  rows.push(["Kept before ads", 0, before, "seg seg-kept"], ["Ads per order", after, before, "seg"], ["Kept after ads", 0, after, "seg seg-kept"]);
  const X = scale(0, wf.price, m.l + labelW, w - m.r);
  const pitch = (h - m.t - m.b) / rows.length, bh = Math.min(30, pitch * 0.66);
  let body = "";
  rows.forEach(([name, lo, hi, cls], i) => {
    const y = m.t + i * pitch, kept = cls.includes("kept"), v = hi - lo;
    const delay = `style="--after:${i * 110}ms"`;
    body += `<text class="${kept ? "ink strong" : ""}" x="${m.l}" y="${r1(y + bh / 2)}" font-size="${font}" dominant-baseline="middle">${esc(name)}</text>`;
    body += `<rect class="${cls} fade" ${delay} x="${r1(X(lo))}" y="${r1(y)}" width="${r1(Math.max(1, X(hi) - X(lo)))}" height="${r1(bh)}"/>`;
    const txt = `${i === 0 || kept ? "" : "−"}$${v.toFixed(2)}`;
    // too narrow to hold its figure: the figure goes beside the bar, on the side away from the row's name
    const inside = X(hi) - X(lo) > font * 4.6, right = !inside && lo === 0;
    const tx = inside ? X(lo) + (X(hi) - X(lo)) / 2 : right ? X(hi) + 6 : X(lo) - 6;
    body += `<text class="${inside && kept ? "seg-text-kept" : "seg-text"} fade" ${delay} x="${r1(tx)}" y="${r1(y + bh / 2)}" font-size="${font}" text-anchor="${inside ? "middle" : right ? "start" : "end"}" dominant-baseline="middle">${txt}</text>`;
  });
  const desc = `One order at $${wf.price.toFixed(2)}: ` + wf.costs.map(([n, v]) => `${n.toLowerCase()} $${v.toFixed(2)}`).join(", ") +
    `; it keeps $${before.toFixed(2)} before ads, and $${after.toFixed(2)} after $${wf.ads.toFixed(2)} of ads an order.`;
  return frame(w, h, "order waterfall", { id: `${id}-t`, text: "Where one order's money goes, and what it keeps" }, { id: `${id}-d`, text: desc }, body);
}

/** Sales a day on a fitted ad curve (models/ad_efficiency.py's forms), and its slope. */
function adCurve(model, p) {
  if (model === "hill") return (s) => (p.a * s ** p.h) / (p.k ** p.h + s ** p.h);
  if (model === "linear") return (s) => p.roas * s;
  return (s) => p.a * Math.log1p(p.b * s);
}

/**
 * One campaign's days (spend against the sales the platform credits), the curve the engine fitted
 * through them, the average return (the straight line from nothing to today) and the last dollar's
 * (the curve's slope at today's spend), and the spend where the last dollar stops paying for a
 * first order. rs: Operator's Math "ads" figures.
 */
export function responseSVG(rs, opts) {
  const { id, w, h, m, font = 13, narrow = false } = opts;
  const f = adCurve(rs.model, rs.params);
  const slope = (s) => (f(s * 1.0001) - f(s * 0.9999)) / (s * 0.0002);
  const xMax = Math.ceil((rs.max_seen * 1.08) / 50) * 50;
  const ys = rs.points.map(([, v]) => v);
  const yt = niceTicks(0, Math.max(...ys, f(xMax)) * 1.05, 4);
  const X = scale(0, xMax, m.l, w - m.r), Y = scale(0, yt[yt.length - 1], h - m.b, m.t);
  const money = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">${usd(t, { compact: true })}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const t of niceTicks(0, xMax, narrow ? 3 : 5).filter((t) => t <= xMax)) {
    body += `<line class="tick" x1="${r1(X(t))}" x2="${r1(X(t))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(t))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">$${t}</text>`;
  }
  body += `<text x="0" y="${m.t - font}" font-size="${font}">Sales a day the platform credits</text>`;
  body += `<text x="${w - m.r}" y="${h - m.b + 2 * font + 14}" font-size="${font}" text-anchor="end">Ad spend a day</text>`;
  const r = font < 13 ? 3 : 3.5;
  body += `<g class="fade" style="--after:0ms">` + rs.points.map(([s, v]) => `<circle class="dot-faint" cx="${r1(X(s))}" cy="${r1(Y(v))}" r="${r}"/>`).join("") + `</g>`;
  const n = 64, cx = [], cy = [];
  for (let i = 0; i <= n; i++) { const s = (xMax * i) / n; cx.push(X(s)); cy.push(Y(f(s))); }
  body += `<path class="fit-line draw" pathLength="1" d="${line(pts(cx, cy))}"/>`;
  const s0 = rs.spend, v0 = f(s0), be = rs.breakeven;
  body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
  // the average: a straight line from nothing to today; the last dollar: the curve's slope at today
  body += `<path class="curve-alt" d="M${r1(X(0))},${r1(Y(0))} L${r1(X(s0))},${r1(Y(v0))}"/>`;
  const dx = xMax * 0.16, k = slope(s0);
  body += `<path class="step" d="M${r1(X(s0 - dx))},${r1(Y(v0 - k * dx))} L${r1(X(Math.min(xMax, s0 + dx)))},${r1(Y(v0 + k * Math.min(dx, xMax - s0)))}"/>`;
  body += `<circle class="dot" cx="${r1(X(s0))}" cy="${r1(Y(v0))}" r="${r + 2}"/>`;
  body += `<text class="ink strong halo" x="${r1(X(s0) + 10)}" y="${r1(Y(v0) + font + 12)}" font-size="${font}">Today ${money(s0)} a day</text>`;
  if (!narrow) {
    // the average's name under its own dashed line, where no day falls; the last dollar's at the end of its slope
    body += `<text class="halo" x="${r1(X(s0 * 0.6) + 8)}" y="${r1(Y(v0 * 0.6) + font + 8)}" font-size="${font}">Average ${rs.average.toFixed(2)}</text>`;
    const ex = Math.min(xMax, s0 + dx);
    body += `<text class="ink strong halo" x="${r1(X(ex) + 6)}" y="${r1(Y(v0 + k * (ex - s0)))}" font-size="${font}" dominant-baseline="middle">Last dollar ${rs.marginal.toFixed(2)}</text>`;
  }
  if (be != null) {
    body += `<line class="leak" x1="${r1(X(be))}" x2="${r1(X(be))}" y1="${r1(Y(f(be)))}" y2="${h - m.b}"/>`;
    body += `<text class="leak-text" x="${r1(X(be) + 6)}" y="${r1(h - m.b - font)}" font-size="${font}">${narrow ? money(be) : `Break-even, first order: ${money(be)}`}</text>`;
  }
  body += `</g>`;
  const desc = `${rs.points.length} days of one campaign: spend against the sales the platform credits to it, and the curve fitted through them. ` +
    `At today's ${money(s0)} a day the average return is ${rs.average.toFixed(2)} and the last dollar returns ${rs.marginal.toFixed(2)}. ` +
    (be != null ? `On a first order alone, the last dollar stops paying at ${money(be)} a day.` : "");
  const scrub = scrubOf(font, m.t, h - m.b, cx.map((x, i) => { const s = (xMax * i) / n; return [x, [cy[i]],
    [`At ${money(s)} a day`, `${money(f(s))} of sales, on the curve`, s > 0 ? `The last dollar returns ${slope(s).toFixed(2)}` : ""].filter(Boolean)]; }));
  return frame(w, h, "response", { id: `${id}-t`, text: "One campaign's spend against its sales: the average dollar and the last dollar" }, { id: `${id}-d`, text: desc }, body, scrub);
}

/**
 * A new customer's margin back, week by week (models/clv.py: the first order's margin plus the
 * expected repeat orders at the repeat order's margin), against what that customer cost.
 * pb: {weekly: [$ at week 0…52], cac, weeks}.
 */
export function paybackSVG(pb, opts) {
  const { id, w, h, m, font = 13 } = opts;
  const N = pb.weekly.length - 1;
  const top = Math.max(...pb.weekly, pb.cac);
  const yt = niceTicks(0, top * 1.05, 4);
  const X = scale(0, N, m.l, w - m.r), Y = scale(0, yt[yt.length - 1], h - m.b, m.t);
  const money = (v) => `$${v.toFixed(2)}`;
  let body = "";
  for (const t of yt) {
    body += `<line class="grid" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(t))}" y2="${r1(Y(t))}"/>`;
    body += `<text x="${m.l - 10}" y="${r1(Y(t))}" font-size="${font}" text-anchor="end" dominant-baseline="middle">$${t}</text>`;
  }
  body += `<line class="axis" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>`;
  for (const t of [0, 13, 26, 39, 52].filter((t) => t <= N)) {
    body += `<line class="tick" x1="${r1(X(t))}" x2="${r1(X(t))}" y1="${h - m.b}" y2="${h - m.b + 5}"/>`;
    body += `<text x="${r1(X(t))}" y="${h - m.b + font + 10}" font-size="${font}" text-anchor="middle">${t === 0 ? "First order" : `Week ${t}`}</text>`;
  }
  body += `<text x="0" y="${m.t - font}" font-size="${font}">Margin back from one new customer</text>`;
  body += `<line class="step-alt" x1="${m.l}" x2="${w - m.r}" y1="${r1(Y(pb.cac))}" y2="${r1(Y(pb.cac))}"/>`;
  body += `<text x="${w - m.r}" y="${r1(Y(pb.cac) - 8)}" font-size="${font}" text-anchor="end">What they cost ${money(pb.cac)}</text>`;
  body += `<path class="curve draw" pathLength="1" d="${line(pts(pb.weekly.map((_, i) => X(i)), pb.weekly.map((v) => Y(v))))}"/>`;
  if (pb.weeks != null) {
    const x = X(pb.weeks), y = Y(pb.weekly[pb.weeks]);
    body += `<g class="fade" style="--after:calc(var(--mc-draw-ms) * .7)">`;
    body += `<line class="leak" x1="${r1(x)}" x2="${r1(x)}" y1="${r1(y)}" y2="${h - m.b}"/>`;
    body += `<circle class="dot-blue" cx="${r1(x)}" cy="${r1(y)}" r="${font < 13 ? 4.5 : 5.5}"/>`;
    body += `<text class="leak-text" x="${r1(x + 8)}" y="${r1(y + font + 10)}" font-size="${font}">Paid back, week ${pb.weeks}</text>`;
    body += `</g>`;
  }
  const desc = `A new customer's margin back, from the first order through week ${N}, against the ${money(pb.cac)} it cost to win them. ` +
    (pb.weeks != null ? `It crosses in week ${pb.weeks}.` : `It does not cross within a year.`);
  const scrub = scrubOf(font, m.t, h - m.b, pb.weekly.map((v, i) => [X(i), [Y(v)],
    [i === 0 ? "The first order" : `Week ${i}`, `${money(v)} of margin back`, v >= pb.cac ? "Paid back" : `${money(pb.cac - v)} still out`]]));
  return frame(w, h, "payback", { id: `${id}-t`, text: "A new customer's margin back, week by week, against what they cost" }, { id: `${id}-d`, text: desc }, body, scrub);
}
