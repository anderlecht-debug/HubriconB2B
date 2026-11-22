// /learn/late-supplier: the course player and its figures.
// Every lesson is in the HTML and open to anyone; without this script the page reads straight
// through, every answer and every still figure in place. With it: one lesson at a time; each
// "Guess first" waits for a guess; a quick check from the lesson before opens each lesson; the
// figures move and answer the reader's sliders and numbers; the numbers a reader enters carry from
// lesson to lesson into their own supplier plan at the end. Progress, guesses and numbers stay in
// this browser's own storage. Nothing a reader types or pastes leaves the page.
import * as F from "./learn-late-supplier.mjs";
import { simulate, PROMISE } from "./lateness-sim.mjs";

window.__hubriconMotion = true;
const root = document.documentElement;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const COURSE = document.body.dataset.course;
const KEY = `hubricon:learn:${COURSE}`;
const DATA = JSON.parse($("#ls-data").textContent);
const CALM = matchMedia("(prefers-reduced-motion: reduce)").matches;

window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
const track = (name, data) => { try { window.va("event", { name, data }); } catch (e) {} };

const store = {
  read() { try { const v = JSON.parse(localStorage.getItem(KEY) || "{}"); return { done: [], guesses: {}, recalls: {}, mine: {}, ...v }; } catch (e) { return { done: [], guesses: {}, recalls: {}, mine: {} }; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} },
  patch(fn) { const v = store.read(); fn(v); store.write(v); return v; },
};

// --------------------------------------------------- your numbers, carried along ----
// One set of numbers for the whole course: change "days late" in lesson 4 and lesson 6 has it.
const START = { ...DATA.start.curve, ...DATA.start.reorder };
const mine = { ...START, ...store.read().mine };
const LABELS = { late: ["Worst 1 in 10", (v) => F.days(v) + " late"], sales: ["Sales a month", (v) => F.usd(v)], margin: ["Gross margin", (v) => `${v}%`], daily: ["Units a day", (v) => v.toLocaleString("en-US")], promised: ["Promised", (v) => F.days(v)], transit: ["Shipping", (v) => F.days(v)] };
const listeners = [];
function setMine(k, v, from) {
  mine[k] = v;
  store.patch((s) => { s.mine[k] = v; });
  for (const i of $$(`[data-in="${k}"]`)) if (i !== from) i.value = v;
  listeners.forEach((fn) => fn(k));
}
function paintMine() {
  const s = store.read().mine, keys = Object.keys(LABELS).filter((k) => k in s);
  $("[data-mine]").hidden = !keys.length;
  $("[data-mine-list]").innerHTML = keys.map((k) => `<div><dt>${LABELS[k][0]}</dt><dd>${LABELS[k][1](s[k])}</dd></div>`).join("");
}
listeners.push(paintMine);
paintMine();

// ---------------------------------------------------------------- the player ----
const lessons = $$("[data-lesson]");
const counted = lessons.filter((l) => l.id !== "one-page");
const tocLinks = $$(".ls-toc a");

function paintRail(current) {
  const s = store.read(), done = new Set(s.done);
  for (const a of tocLinks) {
    const id = a.getAttribute("href").slice(1);
    a.toggleAttribute("data-done", done.has(id));
    if (id === current) a.setAttribute("aria-current", "step"); else a.removeAttribute("aria-current");
  }
  const n = counted.filter((l) => done.has(l.id)).length;
  $("[data-meter]").style.width = `${(n / counted.length) * 100}%`;
  $("[data-count-done]").textContent = n ? `${n} of ${counted.length} lessons done` : `${counted.length} lessons · about 35 minutes`;
  const start = $("[data-start]"), next = counted.find((l) => !done.has(l.id));
  if (n && next) { start.setAttribute("href", `#${next.id}`); start.firstChild.textContent = `Continue with lesson ${counted.indexOf(next) + 1} `; }
  else if (n) { start.setAttribute("href", "#one-page"); start.firstChild.textContent = "Open your supplier plan "; }
}
function markDone(id) {
  if (store.read().done.includes(id)) return;
  store.patch((s) => s.done.push(id));
  track("lesson_done", { course: COURSE, lesson: id });
}
function show() {
  const id = location.hash.slice(1);
  const lesson = lessons.find((l) => l.id === id);
  for (const l of lessons) l.classList.toggle("current", l === lesson);
  root.classList.toggle("reading", Boolean(lesson));
  paintRail(lesson ? lesson.id : null);
  if (lesson) {
    track("lesson_view", { course: COURSE, lesson: lesson.id });
    const top = $(".ls-body").getBoundingClientRect().top + scrollY - 72;
    scrollTo({ top: Math.max(0, top), behavior: "instant" });
    $("h2", lesson)?.focus?.({ preventScroll: true });
  }
}
addEventListener("hashchange", show);
for (const a of $$("[data-next]")) a.addEventListener("click", () => markDone(a.closest("[data-lesson]").id));
const seen = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { markDone(e.target.closest("[data-lesson]").id); paintRail(location.hash.slice(1)); seen.unobserve(e.target); } }), { threshold: 1 });
$$(".ls-lesson:not(.ls-end) .ls-pager").forEach((p) => seen.observe(p));
for (const h of $$(".ls-lesson h2")) h.setAttribute("tabindex", "-1");

// ------------------------------------------------- guess first, and quick checks ----
const afterGuess = {};
for (const g of $$("[data-guess]")) {
  const id = g.closest("[data-lesson]").id, answer = +g.dataset.answer;
  const opts = $$(".ls-opt", g), reveal = $(".ls-reveal", g);
  const verdict = document.createElement("p");
  verdict.className = "ls-verdict";
  reveal.prepend(verdict);
  const settle = (i, fresh) => {
    g.classList.add("answered");
    opts.forEach((o, j) => { o.disabled = true; o.classList.toggle("right", j === answer); o.classList.toggle("picked", j === i); o.setAttribute("aria-pressed", String(j === i)); });
    verdict.textContent = i === answer ? "You called it." : "Not quite. Here's why.";
    verdict.hidden = i === -1;
    if (fresh) { store.patch((s) => { s.guesses[id] = i; }); track("lesson_guess", { course: COURSE, lesson: id, right: i === answer }); (afterGuess[id] || (() => {}))(); }
  };
  g.classList.add("pending");
  const skip = document.createElement("button");
  skip.type = "button"; skip.className = "ls-skip"; skip.textContent = "Skip, show me the answer";
  skip.addEventListener("click", () => { settle(-1, false); (afterGuess[id] || (() => {}))(); });
  $(".ls-opts", g).after(skip);
  opts.forEach((o, i) => o.addEventListener("click", () => settle(i, true)));
  const prior = store.read().guesses[id];
  if (prior !== undefined) settle(prior, false);
}
for (const q of $$("[data-recall]")) {
  const id = q.closest("[data-lesson]").id, answer = +q.dataset.answer, opts = $$("button", q);
  const settle = (i, fresh) => {
    q.classList.add("answered");
    q.classList.toggle("right", i === answer);
    opts.forEach((o, j) => { o.disabled = true; o.classList.toggle("is-answer", j === answer); o.classList.toggle("picked", j === i); });
    if (fresh) { store.patch((s) => { s.recalls[id] = i; }); track("lesson_recall", { course: COURSE, lesson: id, right: i === answer }); }
  };
  q.classList.add("pending");
  opts.forEach((o, i) => o.addEventListener("click", () => settle(i, true)));
  const prior = store.read().recalls[id];
  if (prior !== undefined) settle(prior, false);
}

// ----------------------------------------------------------------- the figures ----
const body = (name) => $(`[data-fig="${name}"] .ls-fig-body`);
const out = (k) => $(`[data-out="${k}"]`);
const pct = (v) => `${Math.round(v)}%`;
const fmt = (d) => d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

// Fig. 1: a year of orders lands, one at a time, then the slider plans for some lateness
const cushion = $('[data-ctl="cushion"]');
let playing = 0, yearPlayed = false;
function playYear() {
  yearPlayed = true;
  const n = DATA.typical.orders.length, t0 = performance.now(), dur = 3200, run = ++playing;
  if (CALM) { body("promise").innerHTML = F.figPromise(DATA, +cushion.value); return; }
  const frame = (t) => {
    if (run !== playing) return;
    const k = Math.min(1, (t - t0) / dur);
    body("promise").innerHTML = F.figPromise(DATA, +cushion.value, k < 1 ? Math.ceil(n * k) : Infinity);
    if (k < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
cushion.addEventListener("input", () => { playing++; body("promise").innerHTML = F.figPromise(DATA, +cushion.value); out("cushion").textContent = F.days(+cushion.value); });
$('[data-replay="promise"]').addEventListener("click", playYear);
afterGuess.promise = () => { if (!yearPlayed) playYear(); };

// Fig. 2 and 3: the line at the supplier, and what it does to lateness
const busy = $('[data-ctl="busy"]');
const half = F.atBusy(DATA, 50);
const line = F.lineSim(46).run(150, +busy.value / 100);
let lineOn = false, linePaused = false, lastT = 0;
const lineBody = body("line");
const paintBusy = () => {
  const b = +busy.value, p = F.atBusy(DATA, b);
  body("busy").innerHTML = F.figBusy(DATA, b);
  out("busy").textContent = `${b}%`;
  out("busy-on").textContent = pct(p.on_time);
  out("busy-p90").textContent = F.days(Math.max(0, p.p90));
  out("busy-x").textContent = `${Math.max(1, Math.round(p.wait_x / half.wait_x))}×`;
  if (CALM || !lineOn) lineBody.innerHTML = F.figLine(line.run(30, b / 100), b);
};
busy.addEventListener("input", paintBusy);
paintBusy();
function tick(t) {
  if (!lineOn) return;
  const dt = Math.min(0.1, ((t - lastT) / 1000) * 2.2);   // about two simulated days a second
  lastT = t;
  if (!linePaused) { line.step(dt, +busy.value / 100); lineBody.innerHTML = F.figLine(line, +busy.value); }
  requestAnimationFrame(tick);
}
if (!CALM) {
  new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting && !lineOn) { lineOn = true; lastT = performance.now(); requestAnimationFrame(tick); }
    else if (!e.isIntersecting) lineOn = false;
  }), { threshold: 0.2 }).observe(lineBody);
}
$("[data-pause]").addEventListener("click", (e) => { linePaused = !linePaused; e.currentTarget.textContent = linePaused ? "Play" : "Pause"; });
if (CALM) $("[data-pause]").hidden = true;

// Fig. 4: pick a month, see the dates
const cal = body("calendar");
const paintMonth = (m) => {
  cal.innerHTML = F.figCalendar(DATA, m);
  const d = DATA.months[m], placed = new Date(Date.UTC(2027, m, 1));
  const promised = new Date(placed.getTime() + 20 * 864e5);
  const real = new Date(promised.getTime() + Math.round(d.p90) * 864e5);
  out("month").innerHTML = `
    <div class="trip-step"><span>You order</span><b>${fmt(placed)}</b></div>
    <div class="trip-step"><span>Promised ready</span><b>${fmt(promised)}</b></div>
    <div class="trip-step leak"><span>Worst 1 in 10 ready</span><b>${fmt(real)}</b></div>
    <div class="trip-step"><span>Ready on time</span><b>${d.on_time < 5 ? "almost none" : `${d.on_time}%`}</b></div>`;
};
cal.addEventListener("click", (e) => { const g = e.target.closest("[data-month]"); if (g) paintMonth(+g.dataset.month); });
cal.addEventListener("keydown", (e) => {
  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  const cur = +($(".mbar.sel", cal)?.closest("[data-month]")?.dataset.month || 0);
  paintMonth((cur + (e.key === "ArrowRight" ? 1 : 11)) % 12); e.preventDefault();
});
cal.tabIndex = 0;
cal.setAttribute("aria-label", "Months: use the arrow keys to move between them");
paintMonth(DATA.months.reduce((b, m, i) => (m.p90 > DATA.months[b].p90 ? i : b), 0));

// Your numbers in, figures out: every [data-in] reads and writes the shared numbers
for (const i of $$("[data-in]")) {
  if (i.dataset.in in mine) i.value = mine[i.dataset.in];
  i.addEventListener("input", () => setMine(i.dataset.in, Math.max(0, +i.value || 0), i));
}

// Fig. 5: the cover that costs least
const cover = $('[data-ctl="cover"]');
let coverTouched = false;
function paintCurve() {
  const cc = F.coverCurve(DATA, mine);
  cover.max = cc.maxC;
  const c = Math.min(+cover.value, cc.maxC), at = cc.pts[c];
  body("curve").innerHTML = F.figCurve(DATA, mine, c);
  out("cover").textContent = F.days(c);
  out("cv-out").textContent = F.usd(at.stockout);
  out("cv-hold").textContent = F.usd(at.hold);
  out("cv-best").textContent = F.days(cc.best.c);
  out("cv-best-d").textContent = `the cover that costs least: ${F.usd(cc.best.total)} a year`;
}
cover.addEventListener("input", () => { coverTouched = true; paintCurve(); });
listeners.push(paintCurve);
paintCurve();
// Once the guess is in, the slider walks along the curve and settles at its bottom
afterGuess.cost = () => {
  if (coverTouched || CALM) return;
  const best = F.coverCurve(DATA, mine).best.c, max = +cover.max;
  let c = 0;
  const back = () => { if (!coverTouched && +cover.value > best) { cover.value = +cover.value - 1; paintCurve(); setTimeout(back, 40); } };
  const go = () => { if (coverTouched) return; cover.value = c; paintCurve(); if (c < max * 0.85) { c++; setTimeout(go, 40); } else setTimeout(back, 400); };
  go();
};

// Fig. 7: when the next order goes out
const today = new Date();
function paintReorder() {
  body("reorder").innerHTML = F.figReorder(mine);
  const r = F.reorder(mine);
  const by = new Date(today.getTime() + Math.round(r.onReal) * 864e5);
  out("ro-real").textContent = r.onReal < 0 ? "Order now" : fmt(by);
  out("ro-date").textContent = r.onReal < 0 ? `you're ${F.days(-r.onReal)} past the last safe day to order` : `in ${F.days(r.onReal)}: the last day to order and still beat a 1-in-10 late order`;
  out("ro-point").textContent = Math.round(r.point).toLocaleString("en-US");
  out("ro-extra").textContent = Math.round(r.extraUnits).toLocaleString("en-US");
}
listeners.push(paintReorder);
paintReorder();

// Fig. 6: your own orders, scored in the browser
const text = $("#ls-rows"), score = $("[data-score]");
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function paintScore() {
  const { rows, skipped } = F.parseOrders(text.value);
  if (!rows.length) {
    score.innerHTML = text.value.trim()
      ? `<p class="ls-score-empty">No rows I could read yet. Each needs an order date, a promised ready date and an actual ready date${skipped ? ` (${skipped} skipped)` : ""}.</p>`
      : `<p class="ls-score-empty">Your scores appear here. This runs in your browser: nothing is sent or saved.</p>`;
    return;
  }
  const sc = F.score(rows), max = Math.max(5, ...sc.map((s) => s.p90));
  score.innerHTML = `
    <p class="ls-score-k">${rows.length} orders read${skipped ? `, ${skipped} skipped` : ""} · ${sc.length} supplier${sc.length === 1 ? "" : "s"}</p>
    <div class="ls-score-table" role="table">
      <div class="st-row st-head" role="row"><span role="columnheader">Supplier</span><span role="columnheader">Orders</span><span role="columnheader">On time</span><span role="columnheader">Worst 1 in 10</span><span role="columnheader" class="st-bar-h"></span></div>
      ${sc.map((s, i) => `<div class="st-row" role="row" style="--i:${i}"><span role="cell" class="st-sup">${esc(s.sup)}</span><span role="cell">${s.n}${s.n < 10 ? "<small>few</small>" : ""}</span><span role="cell">${pct(s.onTime * 100)}</span><span role="cell" class="leak">${s.p90 > 0 ? `${F.days(s.p90)} late` : "on time"}</span><span role="cell" class="st-bar" aria-hidden="true"><i style="--w:${(Math.max(0, s.p90) / max) * 100}%"></i></span></div>`).join("")}
    </div>
    <p class="ls-score-note">${sc[0].p90 > 0 ? `<b>${esc(sc[0].sup)}</b> needs the most cover: ${F.days(sc[0].p90)}. That number now fills lessons 4 and 6 and your plan.` : "Every supplier came in on time at the worst 1 in 10."}${sc.some((s) => s.n < 10) ? " A supplier marked few has under 10 orders: its figure is mostly its single worst order." : ""}</p>`;
  if (sc[0].p90 > 0) setMine("late", Math.round(sc[0].p90));
}
text.addEventListener("input", paintScore);
$("[data-sample]").addEventListener("click", () => { text.value = F.sampleRows(simulate, PROMISE); paintScore(); track("lesson_sample", { course: COURSE }); });
$("[data-file]").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) f.text().then((t) => { text.value = t; paintScore(); }); });

// The plan: everything the reader entered, on one page
const LNY = Date.UTC(2027, 1, 6);
function paintPlan() {
  const r = F.reorder(mine), cc = F.coverCurve(DATA, mine);
  const set = (k, v) => { const el = $(`[data-plan="${k}"]`); if (el) el.textContent = v; };
  const by = new Date(today.getTime() + Math.round(r.onReal) * 864e5);
  set("late", F.days(mine.late));
  set("point", `${Math.round(r.point).toLocaleString("en-US")} units`);
  set("date", r.onReal < 0 ? "Now" : fmt(by) + (by.getUTCFullYear() !== today.getUTCFullYear() ? `, ${by.getUTCFullYear()}` : ""));
  set("date-k", r.onReal < 0 ? `You're ${F.days(-r.onReal)} past it (lesson 6)` : "Lesson 6");
  set("cover", F.days(cc.best.c));
  set("cover-k", `${F.usd(cc.best.total)} a year in all (lesson 4)`);
  set("nocover", F.usd(cc.pts[0].total));
  set("lny", new Date(LNY - (mine.promised + 7) * 864e5).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }));
  const any = Object.keys(store.read().mine).length;
  $("[data-plan-lede]").textContent = any ? "Built from the numbers you entered. Change any of them in lessons 4 to 6 and it updates." : "Built from the example numbers. Put your own in lessons 4 to 6 and it becomes yours.";
}
listeners.push(paintPlan);
paintPlan();
$("[data-print]").addEventListener("click", () => window.print());
$("[data-copy]").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  const rows = $$(".ls-plan-cell").map((c) => `${$(".k", c).textContent}: ${$("b", c).textContent}`);
  const rules = $$(".ls-rules li").map((l, i) => `${i + 1}. ${l.textContent.trim()}`);
  try { await navigator.clipboard.writeText(["My supplier plan (hubricon.com/learn/late-supplier)", "", ...rows, "", ...rules].join("\n")); btn.textContent = "Copied"; }
  catch (err) { btn.textContent = "Couldn't copy: select the text instead"; }
});

show();
