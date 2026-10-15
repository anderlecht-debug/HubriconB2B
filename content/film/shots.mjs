// One shot of a long film as HTML on the film stage (VISUAL_SPEC.md §8.1, §14). A pure
// function: a resolved shot job in (content/src/hubricon_content/render_shots.py fills
// every figure from facts.json, every time relative to the shot's first frame, every
// asset path), a string out. Every number a style uses comes from its `render` block
// in content/film/styles.json and reaches the CSS as a custom property; shots.css only
// lays things out. Paper kinds drift (§3.4) so nothing on screen is ever frozen.
import { sceneHTML } from "./scenes.mjs";

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const ms = (s) => `${Math.round((s || 0) * 1000)}ms`;
// Numbers go to CSS unitless; shots.css multiplies by 1px where it means pixels.
const vars = (o) => Object.entries(o).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => `--${k}:${v}`).join(";");
const money = (s) => /\$/.test(String(s));
const PROOF = "Modeled from public data · Not a client · Not a result";
const MARK = `<span class="mark"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>Hubricon</span>`;

/** The stage's corner: the honesty label when the shot carries one, and the mark. */
function corner(job) {
  const text = job.label === "proof" ? PROOF : job.label === "demo" ? job.demo_label : null;
  return `<div class="corner">${text ? `<span class="label label-box">${esc(text)}</span>` : ""}${MARK}</div>`;
}

/** Text that lands at `at` seconds with the stage's entrance (film.css .in). */
const lands = (at) => `class="in" style="--at:${ms(at)}"`;

/** What the world room may set over a picture (§3.3): a credit, a place and date, "Illustration". */
function overlays(job) {
  const o = job.overlay || {}, out = [];
  if (o.credit) out.push(`<p class="ov-credit">${esc(o.credit)}</p>`);
  if (o.place || o.date) out.push(`<div class="ov-place">${o.place ? `<p class="ov-place-name">${esc(o.place)}</p>` : ""}${o.date ? `<p class="ov-date">${esc(o.date)}</p>` : ""}</div>`);
  if (o.illustration) out.push(`<p class="ov-illustration label">Illustration</p>`);
  return out.join("");
}

function still(job) {
  const r = job.render, [fx, fy] = job.focus || [0.5, 0.5], motion = job.motion || "push";
  const long = job.seconds > (r.long_after_s ?? Infinity);
  const v = { fx, fy, dur: ms(job.seconds) };
  if (motion === "push") Object.assign(v, { from: r.from ?? 1, to: long ? r.long_to : r.to ?? 1.07 });
  if (motion === "pull") Object.assign(v, { from: r.to ?? 1.07, to: r.from ?? 1 });
  if (motion === "drift") Object.assign(v, { from: r.from ?? 1, to: r.to ?? 1.03 });
  if (motion.startsWith("pan")) Object.assign(v, { scale: r.scale, travel: r.travel });
  if (motion === "reveal") {
    const on = job.on ?? 0, pull = (job.seconds - on) * r.pull_share;
    Object.assign(v, { from: r.from, to: r.to, drift: r.drift_to, on: ms(on), pull: ms(pull), rest: ms(Math.max(0.1, job.seconds - on - pull)) });
  }
  return `<section class="scene world" style="${vars(v)}"><div class="still-frame"><img class="still-img m-${esc(motion)}" src="${esc(job.asset.url)}" alt=""></div>${overlays(job)}</section>`;
}

function documentShot(job) {
  const r = job.render, p = job.params || {}, lines = (p.lines || []).slice(0, r.max_lines || 8);
  const target = Math.min(lines.length, Math.max(1, p.line || 1)) - 1;
  const on = job.on ?? 1.5, hit = lines[target] || "";
  const origin = lines.length ? ((target + 0.5) / lines.length) * 100 : 50;
  const v = { "line": r.line_px, "source": r.source_px, "radius": r.radius_px, "start-scale": r.start_scale ?? 1, "push-scale": r.push_scale ?? r.push_to,
              "push-at": ms(r.push_from_s ?? 0), "push-dur": ms((r.push_to_s ?? job.seconds) - (r.push_from_s ?? 0)), "mark-at": ms(on),
              "mark-dur": `${r.mark_ms}ms`, "mark": money(hit) ? r.money_px : r.ink_px ?? r.mark_px, "dim-at": ms(on + (r.dim_after_ms || 0) / 1000),
              "dim-dur": `${r.dim_ms || 400}ms`, "dim": r.dim ?? 1, "origin": `${origin.toFixed(1)}%` };
  const body = lines.map((l, i) => `<p class="doc-line${i === target ? ` doc-target${money(hit) ? " doc-money" : ""}` : ""}">${esc(l)}${i === target ? `<span class="doc-mark"></span>` : ""}</p>`).join("");
  return `<section class="scene paper doc${p.clipping ? " doc-clip" : ""}" style="${vars(v)}"><div class="drift">` +
    `<div class="doc-page">${p.image ? `<img class="doc-image" src="${esc(p.image)}" alt="">` : ""}${body}</div>` +
    `${p.source ? `<p class="doc-source">${esc(p.source)}</p>` : ""}</div>${corner(job)}</section>`;
}

function table(job) {
  const r = job.render, p = job.params || {}, rows = (p.rows || []).slice(0, r.rows_max || 10);
  const row = Math.max(1, Math.min(rows.length, p.row || 1)), cell = p.cell || 0, on = job.on ?? 1;
  const v = { "cell": r.cell_px, "header": r.header_px, "source": r.source_px, "band-at": ms(on), "band-dur": `${r.band_ms}ms`, "money-at": ms(on + r.money_after_ms / 1000), "row": row };
  const isNum = (c) => /^[−\-–$]?[\d,.]+[%a-z]*$/i.test(String(c).replace(/\s/g, ""));
  const head = (p.columns || []).map((c, i) => `<th${i && isNum(rows[0]?.[i] ?? "") ? ` class="num"` : ""}>${esc(c)}</th>`).join("");
  const body = rows.map((rw, i) => `<tr class="${i + 1 === row ? "tbl-hit" : ""}">` + rw.map((c, j) =>
    `<td class="${isNum(c) ? "num" : ""}${i + 1 === row && j + 1 === cell && money(c) ? " tbl-money" : ""}">${esc(c)}</td>`).join("") + "</tr>").join("");
  return `<section class="scene paper top tbl" style="${vars(v)}"><div class="drift">${p.heading ? `<h2 class="heading in">${esc(p.heading)}</h2>` : ""}` +
    `<div class="tbl-wrap"><div class="tbl-band"></div><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>` +
    `${p.source ? `<p class="doc-source">${esc(p.source)}</p>` : ""}</div>${corner(job)}</section>`;
}

function number(job) {
  const p = job.params || {}, on = job.on ?? 0, value = p.value ?? job.reveals?.[0]?.value ?? "";
  return `<section class="scene paper"><div class="drift"><p class="number${money(value) ? "" : " ink"} in" style="--at:${ms(on)}">${esc(value)}` +
    `${p.estimate ? `<span class="est">estimate</span>` : ""}</p>${p.sub ? `<p class="number-sub in" style="--at:${ms(on + job.render.sub_after_ms / 1000)}">${esc(p.sub)}</p>` : ""}</div>${corner(job)}</section>`;
}

function pair(job) {
  const r = job.render, p = job.params || {}, L = p.left || {}, R = p.right || {};
  const col = (c) => `<div class="pair-col in" style="--at:${ms(c.at ?? 0)}"><p class="pair-label">${esc(c.label)}</p><p class="pair-figure${money(c.value) ? " money" : ""}">${esc(c.value)}</p></div>`;
  return `<section class="scene paper" style="${vars({ q: r.question_px, l: r.label_px, f: r.figure_px, g: r.gap_line_px })}"><div class="drift">` +
    `${p.question ? `<p class="pair-q in">${esc(p.question)}</p>` : ""}<div class="pair-row">${col(L)}${col(R)}</div>` +
    `${p.gap ? `<p class="pair-gap in" style="--at:${ms((R.at ?? 0) + 0.6)}">${esc(p.gap)}</p>` : ""}</div>${corner(job)}</section>`;
}

function grid(job) {
  const r = job.render, p = job.params || {}, on = job.on ?? 0;
  const int = (s) => Number(String(s).replace(/[^\d.]/g, "")) || 0;
  let total = int(p.total), filled = int(p.filled), per = 1;
  if (total > r.per_dot_max) { per = 10; total = Math.ceil(total / 10); filled = Math.round(filled / 10); }
  // 14 px dots for a big count (§14, P7); a small count grows to fill the stage, never under 14 px
  const dot = Math.max(r.dot_px, Math.min(72, Math.floor(Math.sqrt((1600 * 520) / Math.max(total, 1))) - r.gap_px));
  const dots = Array.from({ length: total }, (_, i) => `<i class="${i < filled ? "dot-on" : ""}" style="--at:${ms(on + (filled ? (i / filled) * r.fill_ms / 1000 : 0))}"></i>`).join("");
  const caption = per > 1 ? `${p.caption || ""} One dot is ten.`.trim() : p.caption;
  return `<section class="scene paper top grid" style="${vars({ dot, gap: r.gap_px })}"><div class="drift">${p.heading ? `<h2 class="heading in">${esc(p.heading)}</h2>` : ""}` +
    `<div class="dots${money(p.filled) ? " dots-money" : ""}">${dots}</div>${caption ? `<p class="caption in" style="--at:${ms(on)}">${esc(caption)}</p>` : ""}</div>${corner(job)}</section>`;
}

function timeline(job) {
  const r = job.render, events = (job.params?.events || []).filter((e) => typeof e === "object");
  const n = events.length;
  const items = events.map((e, i) => {
    // the plan's position on a 0.06–0.94 track, inset so an event's full-width label clears the frame's edge
    const raw = e.pos ?? (n === 1 ? 0.5 : 0.06 + (0.88 * i) / (n - 1)), low = i % 2 === 1 && n > 3;
    const x = 0.12 + 0.76 * Math.min(1, Math.max(0, (raw - 0.06) / 0.88));
    return `<div class="tl-event${low ? " tl-low" : ""} in" style="--at:${ms(e.at ?? 0.4 + i * 0.8)};--x:${(x * 100).toFixed(2)}%">` +
      `<p class="tl-date">${esc(e.date)}</p><i class="tl-tick"></i><p class="tl-label${money(e.label) ? " money" : ""}">${esc(e.label)}</p></div>`;
  }).join("");
  return `<section class="scene paper top tl" style="${vars({ date: r.date_px, label: r.label_px, tickh: r.tick_h_px, axis: r.axis_px })}"><div class="drift">` +
    `${job.params?.heading ? `<h2 class="heading in">${esc(job.params.heading)}</h2>` : ""}<div class="tl-track"><i class="tl-axis"></i>${items}</div></div>${corner(job)}</section>`;
}

function formula(job) {
  const r = job.render, p = job.params || {}, terms = (p.terms || []).slice(0, r.max_terms || 5), ops = p.ops || [];
  const parts = terms.map((t, i) => `<span class="f-term${i === terms.length - 1 && money(t.text) ? " money" : ""} in" style="--at:${ms(t.at ?? i * 0.9)}">${esc(t.text)}</span>` +
    (i < terms.length - 1 ? `<span class="f-op in" style="--at:${ms(terms[i + 1].at ?? (i + 1) * 0.9)}">${esc(ops[i] ?? "+")}</span>` : "")).join("");
  return `<section class="scene paper" style="${vars({ term: r.term_px, cap: r.caption_px, radius: r.radius_px })}"><div class="drift">` +
    `<div class="f-panel">${parts}</div>${p.caption ? `<p class="caption in" style="--at:${ms((terms.at(-1)?.at ?? 0) + 0.6)}">${esc(p.caption)}</p>` : ""}</div>${corner(job)}</section>`;
}

function kinetic(job) {
  const lines = job.params?.lines || [job.says];
  const at = job.params?.at || [0, 0.9];
  return `<section class="scene paper"><div class="drift">${lines.map((l, i) => `<p class="display in" style="--at:${ms(at[i] ?? i * 0.9)}">${esc(l)}</p>`).join("")}</div>${corner(job)}</section>`;
}

function quote(job) {
  const r = job.render, p = job.params || {};
  return `<section class="scene paper" style="${vars({ q: r.size_px, a: r.attribution_px })}"><div class="drift"><blockquote class="quote in">${esc(p.text)}</blockquote>` +
    `${p.attribution ? `<p class="quote-by in" style="--at:400ms">${esc(p.attribution)}</p>` : ""}</div>${corner(job)}</section>`;
}

function chapter(job) {
  const r = job.render;
  return `<section class="scene paper chapter" style="${vars({ size: r.size_px, hair: r.hairline_px })}"><div class="drift"><i class="ch-hair"></i>` +
    `<p class="ch-title in" style="--at:150ms">${esc(job.params?.title || "")}</p></div>${corner({ ...job, label: null })}</section>`;
}

function archive(job) {
  const r = job.render, a = job.asset || {};
  const scale = Math.min(r.box_w / (a.w || r.box_w), r.box_h / (a.h || r.box_h));
  const w = Math.round((a.w || r.box_w) * scale), h = Math.round((a.h || r.box_h) * scale);
  return `<section class="scene paper archive" style="${vars({ gap: r.gap_px, cap: r.caption_px, to: r.drift_to })}"><div class="drift arch-drift">` +
    `<figure class="arch in"><img src="${esc(a.url)}" width="${w}" height="${h}" alt=""><figcaption><span>${esc([a.place, a.date].filter(Boolean).join(", "))}</span>` +
    `<span>${esc(a.credit)}</span></figcaption></figure></div>${corner(job)}</section>`;
}

function stack(job) {
  const r = job.render, p = job.params || {}, list = (job.assets || []).slice(0, 5);
  const every = (r.every_s[0] + r.every_s[1]) / 2;
  // equal heights, as tall as the stage's 1600 px width allows (3 to 5 photographs in a row)
  const aspects = list.reduce((sum, a) => sum + (a.w && a.h ? a.w / a.h : 1.5), 0);
  const height = Math.min(r.height_px, Math.floor((1600 - (list.length - 1) * r.gutter_px) / Math.max(aspects, 0.1)));
  const imgs = list.map((a, i) => `<img class="stk in${i === p.focus_index ? " stk-focus" : " stk-other"}" src="${esc(a.url)}" style="--at:${ms(a.at ?? 0.4 + i * every)}" alt="">`).join("");
  return `<section class="scene paper stack" style="${vars({ gut: r.gutter_px, h: height, rise: r.rise_px, dim: r.dim, ol: r.outline_px, olgap: r.outline_gap_px, to: r.push_to, "on-at": ms(job.on ?? job.seconds) })}">` +
    `<div class="drift stk-drift"><div class="stk-row">${imgs}</div></div>${corner(job)}</section>`;
}

function split(job) {
  const r = job.render, left = job.asset || {}, rightAt = job.on ?? r.right_at_s;
  // the label is the year from the provenance, never the archive's whole date note (§14, W11)
  const year = (String(left.date || "").match(/\b(1[5-9]\d\d|20\d\d)\b/) || [])[0] || "";
  return `<section class="scene paper split" style="${vars({ pw: r.panel_w, ph: r.panel_h, gut: r.gutter_px, lab: r.label_px })}"><div class="split-row">` +
    `<figure class="split-panel in"><p class="split-label">${esc(year)}</p><img src="${esc(left.url)}" alt=""></figure>` +
    `<figure class="split-panel in" style="--at:${ms(rightAt)}"><p class="split-label">Today</p><div class="split-right" data-at="${rightAt}"></div></figure>` +
    `</div>${corner(job)}</section>`;
}

function stageChart(job, built) {
  // The house charts as they appear on the home page (scenes.mjs), drifting.
  const html = sceneHTML({ id: job.id, kind: job.chart.scene, heading: job.params?.heading || "", caption: job.params?.caption }, built);
  return html.replace(/^<section class="scene top">/, `<section class="scene top"><div class="drift">`).replace(/(<div class="corner">)/, "</div>$1");
}

function receipt(job) {
  // The site's own receipt (how-it-works.html, assets/hubricon.css .rcpt) at film size: the move,
  // how we know, called before, measured after, what counts. Demo data only, and labelled so.
  const r = job.render, p = job.params || {}, rows = p.rows || [];
  const head = ["Move", "How we know", "Called before", "Measured after", "Counts"];
  const tr = (x, i) => `<tr class="in" style="--at:${ms(x.at ?? 0.3 + i * r.line_every_s)}"><td>${esc(x.move)}${x.why ? `<span class="rcpt-why">${esc(x.why)}</span>` : ""}</td>` +
    `<td>${esc(x.how)}</td><td class="num">${esc(x.before)}</td><td class="num">${esc(x.after)}</td><td class="num money">${esc(x.counts)}</td></tr>`;
  const total = p.total ? `<tfoot><tr class="in" style="--at:${ms(0.3 + rows.length * r.line_every_s)}"><td colspan="4">${esc(p.total_label || "This month, counted once")}</td><td class="num money">${esc(p.total)}</td></tr></tfoot>` : "";
  return `<section class="scene paper top film-rcpt" style="${vars({ cell: r.cell_px, why: r.why_px })}"><div class="drift">` +
    `${p.heading ? `<h2 class="heading in">${esc(p.heading)}</h2>` : ""}<table class="rcpt"><thead><tr>${head.map((h, i) => `<th${i > 1 ? ` class="num"` : ""}>${h}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map(tr).join("")}</tbody>${total}</table></div>${corner({ ...job, label: "demo" })}</section>`;
}

export const KINDS = { still, texture: still, document: documentShot, table, number, pair, grid, timeline, formula, kinetic, quote, chapter, archive, stack, split, receipt };

/** The HTML of one resolved shot job. `built` is the site's figures, for the house charts. */
export function shotHTML(job, built) {
  if (job.kind === "chart") return wrap(job, stageChart(job, built));
  if (job.kind === "end") return wrap(job, sceneHTML({ id: job.id, kind: "end", ...job.params }, built).replace(/^<section class="scene">/, `<section class="scene"><div class="drift">`).replace(/(<div class="corner">)/, "</div>$1"));
  const kind = KINDS[job.kind];
  if (!kind) throw new Error(`the stage has no kind ${job.kind}`);
  return wrap(job, kind(job));
}

// Every shot sits in one wrapper carrying its length and its drift (§3.4: paper drifts
// 1.000 → 1.015 over the whole shot, so nothing on screen is ever frozen).
const wrap = (job, html) => `<div class="shot" style="--shot:${ms(job.seconds)};--drift-to:${job.drift_to ?? 1.015}">${html}</div>`;
