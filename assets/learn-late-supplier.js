// /learn/late-supplier: the course player and its figures.
// Every lesson is in the HTML and open to anyone; without this script the page reads straight
// through, every answer and every still figure in place. With it: one lesson at a time, each
// "Guess first" waits for a guess before it shows the answer, the figures answer the reader's
// sliders and numbers, and the rail keeps what's been finished in this browser's own storage.
// Nothing a reader types or pastes leaves the page.
import * as F from "./learn-late-supplier.mjs";
import { simulate, PROMISE } from "./lateness-sim.mjs";

window.__hubriconMotion = true;
const root = document.documentElement;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const COURSE = document.body.dataset.course;
const KEY = `hubricon:learn:${COURSE}`;
const DATA = JSON.parse($("#ls-data").textContent);

window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
const track = (name, data) => { try { window.va("event", { name, data }); } catch (e) {} };

const store = {
  read() { try { const v = JSON.parse(localStorage.getItem(KEY) || "{}"); return { done: [], guesses: {}, ...v }; } catch (e) { return { done: [], guesses: {} }; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} },
};

// ---------------------------------------------------------------- the player ----
const lessons = $$("[data-lesson]");
const counted = lessons.filter((l) => l.id !== "one-page");
const tocLinks = $$(".ls-toc a");

function paintRail(current) {
  const s = store.read();
  const done = new Set(s.done);
  for (const a of tocLinks) {
    const id = a.getAttribute("href").slice(1);
    a.toggleAttribute("data-done", done.has(id));
    if (id === current) a.setAttribute("aria-current", "step"); else a.removeAttribute("aria-current");
  }
  const n = counted.filter((l) => done.has(l.id)).length;
  $("[data-meter]").style.width = `${(n / counted.length) * 100}%`;
  $("[data-count-done]").textContent = n ? `${n} of ${counted.length} lessons done` : `${counted.length} lessons · about 35 minutes`;
  const start = $("[data-start]");
  const next = counted.find((l) => !done.has(l.id));
  if (n && next) { start.setAttribute("href", `#${next.id}`); start.firstChild.textContent = `Continue with lesson ${counted.indexOf(next) + 1} `; }
  else if (n) { start.setAttribute("href", "#one-page"); start.firstChild.textContent = "See the six rules "; }
}

function markDone(id) {
  const s = store.read();
  if (!s.done.includes(id)) { s.done.push(id); store.write(s); track("lesson_done", { course: COURSE, lesson: id }); }
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
// Reaching the end of a lesson counts as finishing it, for a reader who scrolls rather than clicks.
const seen = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { markDone(e.target.closest("[data-lesson]").id); paintRail(location.hash.slice(1)); seen.unobserve(e.target); } }), { threshold: 1 });
$$(".ls-lesson:not(.ls-end) .ls-pager").forEach((p) => seen.observe(p));
for (const h of $$(".ls-lesson h2")) h.setAttribute("tabindex", "-1");
show();

// --------------------------------------------------------------- guess first ----
for (const g of $$("[data-guess]")) {
  const id = g.closest("[data-lesson]").id;
  const answer = +g.dataset.answer;
  const opts = $$(".ls-opt", g);
  const reveal = $(".ls-reveal", g);
  const verdict = document.createElement("p");
  verdict.className = "ls-verdict";
  reveal.prepend(verdict);
  const settle = (i, fresh) => {
    g.classList.add("answered");
    opts.forEach((o, j) => { o.disabled = true; o.classList.toggle("right", j === answer); o.classList.toggle("picked", j === i); o.setAttribute("aria-pressed", String(j === i)); });
    verdict.textContent = i === answer ? "You called it." : i === -1 ? "" : "Not quite. Here is why.";
    verdict.hidden = i === -1;
    if (fresh) { const s = store.read(); s.guesses[id] = i; store.write(s); track("lesson_guess", { course: COURSE, lesson: id, right: i === answer }); }
  };
  g.classList.add("pending");
  const skip = document.createElement("button");
  skip.type = "button"; skip.className = "ls-skip"; skip.textContent = "Skip, show me the answer";
  skip.addEventListener("click", () => settle(-1, false));
  $(".ls-opts", g).after(skip);
  opts.forEach((o, i) => o.addEventListener("click", () => settle(i, true)));
  const prior = store.read().guesses[id];
  if (prior !== undefined) settle(prior, false);
}

// ----------------------------------------------------------------- the figures ----
const body = (name) => $(`[data-fig="${name}"] .ls-fig-body`);
const out = (k) => $(`[data-out="${k}"]`);
const pct = (v) => `${Math.round(v)}%`;

// Fig. 1: plan for some lateness, see how many orders it covers
const cushion = $('[data-ctl="cushion"]');
cushion.addEventListener("input", () => {
  const v = +cushion.value;
  body("promise").innerHTML = F.figPromise(DATA, v);
  out("cushion").textContent = F.days(v);
});

// Fig. 2: how busy the supplier is
const busy = $('[data-ctl="busy"]');
const half = F.atBusy(DATA, 50);
const paintBusy = () => {
  const b = +busy.value, p = F.atBusy(DATA, b);
  body("busy").innerHTML = F.figBusy(DATA, b);
  out("busy").textContent = `${b}%`;
  out("busy-on").textContent = pct(p.on_time);
  out("busy-p90").textContent = F.days(Math.max(0, p.p90));
  out("busy-x").textContent = `${Math.max(1, Math.round(p.wait_x / half.wait_x))}×`;
};
busy.addEventListener("input", paintBusy);
paintBusy();

// Fig. 3: pick a month
const cal = body("calendar");
const paintMonth = (m) => {
  cal.innerHTML = F.figCalendar(DATA, m);
  const d = DATA.months[m];
  out("month").innerHTML = `Orders placed in <b>${F.MONTHS_LONG[m]}</b>: ${d.on_time}% ready on time, and the worst 1 in 10 ready <b class="leak">${F.days(d.p90)}</b> after the promised date.`;
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

// Fig. 4 and Fig. 6: numbers in, figure out
function form(name, draw) {
  const fig = $(`[data-fig="${name}"]`);
  const inputs = $$("[data-in]", fig);
  const read = () => Object.fromEntries(inputs.map((i) => [i.dataset.in, Math.max(0, +i.value || 0)]));
  const paint = () => draw(read());
  inputs.forEach((i) => i.addEventListener("input", paint));
  paint();
}
form("cost", (v) => { body("cost").innerHTML = F.figCost(v); });
form("reorder", (v) => {
  body("reorder").innerHTML = F.figReorder(v);
  const r = F.reorder(v);
  out("ro-real").textContent = r.onReal < 0 ? `${F.days(-r.onReal)} ago` : `Day ${Math.round(r.onReal)}`;
  out("ro-point").textContent = Math.round(r.point).toLocaleString("en-US");
  out("ro-extra").textContent = Math.round(r.extraUnits).toLocaleString("en-US");
});

// Fig. 5: your own orders, scored in the browser
const text = $("#ls-rows"), score = $("[data-score]");
function paintScore() {
  const { rows, skipped } = F.parseOrders(text.value);
  if (!rows.length) {
    score.innerHTML = text.value.trim()
      ? `<p class="ls-score-empty">No rows I could read yet. Each needs an order date, a promised ready date and an actual ready date${skipped ? ` (${skipped} skipped)` : ""}.</p>`
      : `<p class="ls-score-empty">Your scores appear here as soon as there's a row to read. This runs in your browser: nothing is sent or saved.</p>`;
    return;
  }
  const sc = F.score(rows);
  const max = Math.max(5, ...sc.map((s) => s.p90));
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  score.innerHTML = `
    <p class="ls-score-k">${rows.length} orders read${skipped ? `, ${skipped} skipped` : ""} · ${sc.length} supplier${sc.length === 1 ? "" : "s"}</p>
    <div class="ls-score-table" role="table">
      <div class="st-row st-head" role="row"><span role="columnheader">Supplier</span><span role="columnheader">Orders</span><span role="columnheader">On time</span><span role="columnheader">Worst 1 in 10</span><span role="columnheader" class="st-bar-h"></span></div>
      ${sc.map((s) => `<div class="st-row" role="row"><span role="cell" class="st-sup">${esc(s.sup)}</span><span role="cell">${s.n}${s.n < 10 ? `<small>few</small>` : ""}</span><span role="cell">${pct(s.onTime * 100)}</span><span role="cell" class="leak">${s.p90 > 0 ? `${F.days(s.p90)} late` : "on time"}</span><span role="cell" class="st-bar" aria-hidden="true"><i style="width:${Math.max(0, s.p90) / max * 100}%"></i></span></div>`).join("")}
    </div>
    <p class="ls-score-note">Use the worst-1-in-10 figure for each supplier in lesson 6. ${sc.some((s) => s.n < 10) ? "A supplier marked few has under 10 orders: its figure is mostly its single worst order." : ""}</p>`;
  const top = sc[0];
  const late = $('[data-fig="reorder"] [data-in="late"]');
  if (top && top.p90 > 0 && late) { late.value = Math.round(top.p90); late.dispatchEvent(new Event("input")); }
}
text.addEventListener("input", paintScore);
$("[data-sample]").addEventListener("click", () => { text.value = F.sampleRows(simulate, PROMISE); paintScore(); track("lesson_sample", { course: COURSE }); });
$("[data-file]").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) f.text().then((t) => { text.value = t; paintScore(); }); });
