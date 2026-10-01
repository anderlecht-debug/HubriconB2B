// A /learn course page's behaviour. Every lesson is already in the HTML, in order; a
// visitor without scripts reads them straight through. With scripts: one email opens
// the course (POST /api/learn), then one lesson shows at a time, the list on the left
// marks where you are and what you have read, and the charts draw once.
"use strict";
window.__hubriconMotion = true;

const root = document.documentElement;
const COURSE = document.body.dataset.course;
const KEY = "hubricon.learn";

window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
const track = (name, data) => { try { window.va("event", { name, data }); } catch (e) {} };

const store = {
  read() { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} },
};
const isIn = () => Boolean((store.read().courses || {})[COURSE]) || root.classList.contains("learn-in");

const lessons = [...document.querySelectorAll(".lesson")];
const links = [...document.querySelectorAll(".toc a[href^='#']")];
const toc = document.getElementById("toc");

/* -- One lesson at a time ---------------------------------------------------------- */
function seen() { return new Set(((store.read().seen || {})[COURSE]) || []); }
function markSeen(id) {
  const s = store.read();
  s.seen = s.seen || {};
  const list = new Set(s.seen[COURSE] || []);
  list.add(id);
  s.seen[COURSE] = [...list];
  store.write(s);
}
function paintToc(current) {
  const done = seen();
  for (const a of links) {
    const id = a.getAttribute("href").slice(1);
    if (id === current) a.setAttribute("aria-current", "true");
    else a.removeAttribute("aria-current");
    a.classList.toggle("seen", done.has(id) && id !== current);
  }
  const i = lessons.findIndex((l) => l.id === current);
  const summary = toc?.querySelector("summary");
  if (summary && i >= 0) summary.textContent = `Lesson ${i + 1} of ${lessons.length}: ${links[i].textContent.replace(/^\d+/, "").trim()}`;
}
function show(id, { scroll = true } = {}) {
  if (!isIn()) return;
  const lesson = lessons.find((l) => l.id === id) || lessons[0];
  for (const l of lessons) l.classList.toggle("current", l === lesson);
  paintToc(lesson.id);
  markSeen(lesson.id);
  if (matchMedia("(max-width: 860px)").matches && toc) toc.open = false;
  if (scroll) document.getElementById("main").scrollIntoView({ block: "start" });
  track("lesson_view", { course: COURSE, lesson: lesson.id });
}
window.addEventListener("hashchange", () => show(location.hash.slice(1)));
// Before the email, a lesson link brings the visitor to the form, not to a blank page.
for (const a of links) {
  a.addEventListener("click", (ev) => {
    if (isIn()) return;
    ev.preventDefault();
    document.getElementById("email")?.focus();
  });
}

/* -- The email that opens the course ----------------------------------------------- */
const form = document.getElementById("join");
const err = document.getElementById("join-err");
function open(email) {
  const s = store.read();
  s.courses = { ...(s.courses || {}), [COURSE]: new Date().toISOString().slice(0, 10) };
  store.write(s);
  root.classList.add("learn-in");
  if (toc) toc.open = !matchMedia("(max-width: 860px)").matches;
  show(location.hash.slice(1) || lessons[0].id);
  track("learn_registered", { course: COURSE, known: Boolean(email) });
}
form?.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  err.hidden = true;
  const email = form.email.value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
    err.textContent = "That doesn't look like an email address. Check it and try again.";
    err.hidden = false;
    form.email.focus();
    return;
  }
  const button = form.querySelector("button");
  button.disabled = true;
  let res = null;
  try {
    const params = new URLSearchParams(location.search);
    res = await fetch("/api/learn", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, course: COURSE, website: form.website.value, source: params.get("utm_source") || params.get("ref") || "" }),
    });
  } catch (e) { res = null; }
  button.disabled = false;
  // A bad address is the visitor's to fix. Anything else is ours: the course opens anyway.
  if (res && res.status === 400) {
    const body = await res.json().catch(() => ({}));
    err.textContent = body.error || "That address was not accepted. Check it and try again.";
    err.hidden = false;
    return;
  }
  open(email);
});

if (isIn()) {
  if (toc) toc.open = !matchMedia("(max-width: 860px)").matches;
  show(location.hash.slice(1), { scroll: Boolean(location.hash) });
}
document.querySelectorAll("[data-template]").forEach((a) => a.addEventListener("click", () => track("template_download", { course: COURSE })));
document.addEventListener("click", (ev) => { if (ev.target.closest?.("[data-cta]")) track("cta_click", { section: "learn", course: COURSE }); });

// The charts draw once as they arrive: /assets/site.js, which every page with the bar loads.
