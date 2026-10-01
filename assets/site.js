// Every public page's behaviour. Everything visible is already in the HTML; this file
// opens the phone menu, plays each chart and section once as it scrolls in, counts
// the true-today numbers up, and keeps the footer's one live line true.
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

/* -- Charts: drawn once when they come into view, then still ------------------------ */
const ms = (name, fallback) => {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v.endsWith("ms") ? parseFloat(v) : v.endsWith("s") ? parseFloat(v) * 1000 : fallback;
};
if (motion) {
  const total = ms("--mc-draw-ms", 2000) + ms("--mc-band-ms", 400) + 1200;   // draw, band, the paths settling
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const fig = e.target;
      io.unobserve(fig);
      fig.classList.add("playing");
      setTimeout(() => { fig.classList.add("played"); fig.classList.remove("playing"); }, total);
    }
  }, { threshold: 0.3 });
  document.querySelectorAll("[data-play]").forEach((f) => io.observe(f));
}

/* -- Sections arrive once; true-today numbers count up to what they already say ------ */
function countUp(el) {
  const final = el.textContent;
  const m = final.match(/\d[\d,]*/);
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
  const counting = [...document.querySelectorAll("[data-count]")];
  for (const el of counting) {
    el.setAttribute("aria-label", el.textContent);
    el.dataset.final = el.textContent;
    el.textContent = el.textContent.replace(/\d[\d,]*/, "0");
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      io.unobserve(e.target);
      if (e.target.hasAttribute("data-count")) { e.target.textContent = e.target.dataset.final; countUp(e.target); }
      else e.target.classList.add("in");
    }
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0.1 });
  document.querySelectorAll("[data-reveal], [data-count]").forEach((el) => io.observe(el));
}

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
