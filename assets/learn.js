// A /learn course page's behaviour. Every lesson is already in the HTML, in order, and open
// to anyone: no email, no account (the founder's call, 2026-10-01). A visitor without scripts
// reads them straight through. With scripts: the cover is the start, one lesson shows at a
// time, the list on the left marks where you are and what you have read, the cover offers to
// pick up where you left off, and the charts draw once. The optional email is /assets/site.js.
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

const lessons = [...document.querySelectorAll(".lesson")];
const links = [...document.querySelectorAll(".toc a[href^='#']")];
const toc = document.getElementById("toc");
const start = document.querySelector("[data-start]");

/* -- What you have read, kept in this browser only ----------------------------------- */
function seen() { return new Set(((store.read().seen || {})[COURSE]) || []); }
function markSeen(id) {
  const s = store.read();
  s.seen = s.seen || {};
  const list = new Set(s.seen[COURSE] || []);
  list.add(id);
  s.seen[COURSE] = [...list];
  s.last = { ...(s.last || {}), [COURSE]: id };
  store.write(s);
}

/* -- The cover's start: lesson 1, or where you left off ------------------------------- */
function paintStart() {
  if (!start) return;
  const last = (store.read().last || {})[COURSE];
  const i = lessons.findIndex((l) => l.id === last);
  if (i < 0) return;
  // Pick up at the lesson after the last one opened, or that one if it was the last.
  const j = Math.min(i + 1, lessons.length - 1);
  const title = links[j].textContent.replace(/^\d+/, "").trim();
  start.setAttribute("href", `#${lessons[j].id}`);
  start.firstChild.textContent = `Continue with lesson ${j + 1}, ${title} `;
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
  if (summary) summary.textContent = i >= 0 ? `Lesson ${i + 1} of ${lessons.length}: ${links[i].textContent.replace(/^\d+/, "").trim()}` : `Lessons (${lessons.length})`;
}

/* -- One view at a time: the cover, or one lesson ------------------------------------- */
function show(id, { scroll = true } = {}) {
  const lesson = lessons.find((l) => l.id === id);
  for (const l of lessons) l.classList.toggle("current", l === lesson);
  root.classList.toggle("reading", Boolean(lesson));
  paintToc(lesson ? lesson.id : null);
  if (lesson) {
    markSeen(lesson.id);
    track("lesson_view", { course: COURSE, lesson: lesson.id });
  } else {
    paintStart();
  }
  if (matchMedia("(max-width: 860px)").matches && toc) toc.open = false;
  if (scroll) document.getElementById("main").scrollIntoView({ block: "start" });
}
window.addEventListener("hashchange", () => show(location.hash.slice(1)));

if (toc) toc.open = !matchMedia("(max-width: 860px)").matches;
show(location.hash.slice(1), { scroll: Boolean(location.hash) });

document.querySelectorAll("[data-template]").forEach((a) => a.addEventListener("click", () => track("template_download", { course: COURSE })));
document.addEventListener("click", (ev) => { if (ev.target.closest?.("[data-cta]")) track("cta_click", { section: "learn", course: COURSE }); });

// The charts draw once as they arrive: /assets/site.js, which every page with the bar loads.
