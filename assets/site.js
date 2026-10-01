// Every public page's behaviour. Everything visible is already in the HTML; this file
// opens the phone menu, plays each chart and section once as it scrolls in, counts the
// true-today numbers up, opens a course from one email, and keeps the footer's one live
// line true.
"use strict";
window.__hubriconMotion = true;

const root = document.documentElement;
const motion = root.classList.contains("motion");

window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
export const track = (name, data) => { try { window.va("event", { name, data }); } catch (e) {} };

/* -- The nav ---------------------------------------------------------------------- */
const nav = document.querySelector("[data-nav]");
if (nav) {
  const button = nav.querySelector(".nav-menu");
  const setOpen = (open) => {
    nav.classList.toggle("open", open);
    button?.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("nav-locked", open);
  };
  button?.addEventListener("click", () => setOpen(!nav.classList.contains("open")));
  nav.querySelector(".nav-sheet")?.addEventListener("click", (e) => { if (e.target.closest("a")) setOpen(false); });
  matchMedia("(min-width: 1001px)").addEventListener?.("change", (e) => { if (e.matches) setOpen(false); });

  // A panel opened by hover stays open while the pointer rests on it, so after a click
  // (often a link on this same page) it is put away until the pointer leaves.
  const putAway = () => {
    nav.classList.add("fly-off");
    if (document.activeElement && nav.contains(document.activeElement)) document.activeElement.blur();
  };
  nav.querySelectorAll(".nav-fly a, .nav-tabs > a").forEach((a) => a.addEventListener("click", putAway));
  nav.querySelectorAll(".nav-group").forEach((g) => g.addEventListener("pointerleave", () => nav.classList.remove("fly-off")));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (nav.classList.contains("open")) { setOpen(false); button?.focus(); }
    else if (nav.contains(document.activeElement)) putAway();
  });

  const scrolled = () => nav.classList.toggle("scrolled", scrollY > 4);
  addEventListener("scroll", scrolled, { passive: true });
  scrolled();
}

/* -- Motion: everything plays once as it arrives, then stays still ------------------- */
// HUBRICON_SPEC.md, the Monte Carlo's contract, held for everything that moves: before it
// plays, an element shows its finished still frame, never a blank box. So an element is put
// back to its start (.armed) only while it is still below the screen, within a screen of
// it, and plays as it arrives. What is on screen at load, or what a visitor jumps past,
// stays as it is. The one exception is the hero's chart (data-play="load"), which the
// stylesheet holds at its start from the first paint and which draws as the page opens.
const ms = (name, fallback) => {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v.endsWith("ms") ? parseFloat(v) : v.endsWith("s") ? parseFloat(v) * 1000 : fallback;
};
const DIGITS = /\d[\d,]*/;
function countUp(el, final) {
  const m = final.match(DIGITS);
  if (!m) return;
  const target = Number(m[0].replace(/,/g, ""));
  const show = (v) => { el.textContent = final.replace(m[0], Math.round(v).toLocaleString("en-US")); };
  const t0 = performance.now(), dur = 1600;
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    show(target * (1 - Math.pow(1 - p, 4)));
    if (p < 1) requestAnimationFrame(tick); else el.textContent = final;
  };
  requestAnimationFrame(tick);
}
if (motion) {
  const chartMs = ms("--mc-draw-ms", 2000) + ms("--mc-band-ms", 400) + 1200;   // draw, band, the paths settling
  const playChart = (el) => {
    el.classList.add("playing");
    el.classList.remove("armed");
    setTimeout(() => { el.classList.add("played"); el.classList.remove("playing"); }, chartMs);
  };
  const arm = (el) => {
    if (el.classList.contains("armed")) return;
    el.classList.add("armed");
    if (el.hasAttribute("data-count")) {
      el.dataset.final = el.textContent;
      el.setAttribute("aria-label", el.textContent);
      el.textContent = el.textContent.replace(DIGITS, "0");
    }
  };
  const play = (el) => {
    if (!el.classList.contains("armed")) return;          // never put back: it is already its still frame
    if (el.hasAttribute("data-play")) return playChart(el);
    el.classList.remove("armed");
    if (el.hasAttribute("data-reveal")) el.classList.add("in");
    if (el.hasAttribute("data-count")) countUp(el, el.dataset.final);
  };
  const arriving = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      arriving.unobserve(e.target); nearing.unobserve(e.target);
      play(e.target);
    }
  }, { rootMargin: "0px 0px -6% 0px" });
  const nearing = new IntersectionObserver((entries) => {
    for (const e of entries) {
      // Within a screen of arriving, and still wholly below it: safe to put back to its start.
      if (e.isIntersecting && e.boundingClientRect.top > innerHeight) { arm(e.target); nearing.unobserve(e.target); }
    }
  }, { rootMargin: "0px 0px 100% 0px" });
  for (const el of document.querySelectorAll('[data-play="load"]')) playChart(el);
  for (const el of document.querySelectorAll('[data-play]:not([data-play="load"]), [data-reveal], [data-count]')) {
    nearing.observe(el);
    arriving.observe(el);
  }
}

/* -- The email that opens a course --------------------------------------------------- */
// HUBRICON_SPEC.md, "Email to enter, the Acquisition.com model": one address registers you
// for a course and everything inside is open. This is the featured card's form; it posts
// what the course page's form posts, remembers the course as opened in this browser the
// way the course page does, and takes the visitor straight into its first lesson.
const LEARN_KEY = "hubricon.learn";
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
document.querySelectorAll("form[data-join]").forEach((form) => {
  const err = form.querySelector(".join-err");
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    err.hidden = true;
    const email = form.email.value.trim();
    if (!EMAIL.test(email)) {
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
        body: JSON.stringify({ email, course: form.dataset.join, website: form.website.value, source: params.get("utm_source") || params.get("ref") || "" }),
      });
    } catch (e) { res = null; }
    // A bad address is the visitor's to fix. Anything else is ours: the course opens anyway.
    if (res && res.status === 400) {
      const body = await res.json().catch(() => ({}));
      err.textContent = body.error || "That address was not accepted. Check it and try again.";
      err.hidden = false;
      button.disabled = false;
      return;
    }
    try {
      const s = JSON.parse(localStorage.getItem(LEARN_KEY) || "{}");
      s.courses = { ...(s.courses || {}), [form.dataset.join]: new Date().toISOString().slice(0, 10) };
      localStorage.setItem(LEARN_KEY, JSON.stringify(s));
    } catch (e) {}
    track("learn_registered", { course: form.dataset.join, from: location.pathname });
    const done = document.createElement("p");
    done.className = "join-done";
    done.textContent = "You're in. Opening lesson 1…";
    form.replaceChildren(done);
    location.href = `${form.dataset.path}#${form.dataset.first}`;
  });
});

/* -- Videos: counted when someone presses play ------------------------------------ */
document.querySelectorAll("video[data-track]").forEach((v) => {
  v.addEventListener("play", () => track("video_play", { v: v.dataset.track }), { once: true });
});

/* -- The footer's one live line ---------------------------------------------------- */
// The two anon-callable functions in the schema; both re-check consent on every read.
const PUBLISHABLE = "sb_publishable_byrEWlQDgM9fDW-2bwIA3w_XA0mrg5X";
export async function rpc(name) {
  try {
    const res = await fetch(`https://cgqvdnhgbfxikzdqqaws.supabase.co/rest/v1/rpc/${name}`, {
      method: "POST", body: "{}",
      headers: { apikey: PUBLISHABLE, Authorization: `Bearer ${PUBLISHABLE}`, "content-type": "application/json" },
    });
    return res.ok ? await res.json() : null;
  } catch (e) { return null; }
}
export const results = document.querySelector("[data-proof-pending], [data-wall]") ? rpc("public_results") : Promise.resolve(null);
results.then((rows) => {
  if (Array.isArray(rows) && rows.length) document.querySelectorAll("[data-proof-pending]").forEach((n) => { n.hidden = true; });
});
