// Every public page's behaviour. Everything visible is already in the HTML; this file
// opens the phone menu, plays each chart and section once as it scrolls in, counts the
// true-today numbers up, opens a course from one email, and keeps the footer's one live
// line true.
"use strict";
window.__hubriconMotion = true;

const root = document.documentElement;
const motion = root.classList.contains("motion");
const calm = root.classList.contains("calm");   // asked for less motion: a dissolve, nothing else

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
if (motion || calm) {
  const chartMs = ms("--mc-draw-ms", 2000) + ms("--mc-band-ms", 400) + 1200;   // draw, band, the paths settling
  const playChart = (el) => {
    el.classList.add("playing");
    el.classList.remove("armed");
    setTimeout(() => { el.classList.add("played"); el.classList.remove("playing"); }, chartMs);
  };
  const arm = (el) => {
    if (el.classList.contains("armed")) return;
    if (calm && !el.hasAttribute("data-reveal")) return;   // charts and numbers keep their finished frame
    el.classList.add("armed");
    if (motion && el.hasAttribute("data-count")) {
      el.dataset.final = el.textContent;
      el.setAttribute("aria-label", el.textContent);
      el.textContent = el.textContent.replace(DIGITS, "0");
    }
  };
  const play = (el) => {
    if (!el.classList.contains("armed")) return;          // never put back: it is already its still frame
    if (motion && el.hasAttribute("data-play")) return playChart(el);
    el.classList.remove("armed");
    if (el.hasAttribute("data-reveal")) el.classList.add("in");
    if (motion && el.hasAttribute("data-count")) countUp(el, el.dataset.final);
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
  if (motion) for (const el of document.querySelectorAll('[data-play="load"]')) playChart(el);
  for (const el of document.querySelectorAll('[data-play]:not([data-play="load"]), [data-reveal], [data-count]')) {
    nearing.observe(el);
    arriving.observe(el);
  }
}

/* -- Charts a reader can scrub ------------------------------------------------------ */
// Every chart with data-scrub (assets/charts.mjs) reads out its values where the pointer or a
// finger rests: a hairline, a dot on each line, and the figures beside them. The chart itself
// does not move; the readout is the reader's. Off the chart, or with Escape, it goes away.
const SVGNS = "http://www.w3.org/2000/svg";
const mk = (tag, attrs, parent) => { const n = document.createElementNS(SVGNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); parent?.append(n); return n; };
for (const svg of document.querySelectorAll("svg.chart[data-scrub]")) {
  let data;
  try { data = JSON.parse(svg.dataset.scrub); } catch (e) { continue; }
  if (!data.p?.length) continue;
  const vb = svg.viewBox.baseVal;
  const g = mk("g", { class: "scrub", "aria-hidden": "true" }, svg);
  const rule = mk("line", { class: "scrub-rule", y1: data.t, y2: data.b }, g);
  const dots = data.p[0][1].map(() => mk("circle", { class: "scrub-dot", r: data.f < 13 ? 3.5 : 4.5 }, g));
  const box = mk("rect", { class: "scrub-box", rx: 6 }, g);
  const lines = Math.max(...data.p.map((p) => p[2].length));
  const texts = Array.from({ length: lines }, (_, i) => mk("text", { class: i ? "scrub-text" : "scrub-text scrub-head", "font-size": data.f }, g));
  g.style.display = "none";
  let shown = -1;
  const show = (i) => {
    if (i === shown) return;
    shown = i;
    const [x, ys, label] = data.p[i];
    rule.setAttribute("x1", x); rule.setAttribute("x2", x);
    dots.forEach((d, k) => { d.setAttribute("cx", x); d.setAttribute("cy", ys[k] ?? -99); });
    const lh = data.f * 1.45, pad = data.f * 0.7;
    texts.forEach((t, k) => { t.textContent = label[k] || ""; });
    g.style.display = "";
    const w = Math.max(...texts.map((t) => t.getComputedTextLength())) + pad * 2;
    const h = label.length * lh + pad * 1.2;
    const right = x + 12 + w <= vb.x + vb.width;
    const bx = right ? x + 12 : x - 12 - w, by = Math.max(data.t, Math.min(data.b - h, Math.min(...ys) - h / 2));
    box.setAttribute("x", bx); box.setAttribute("y", by); box.setAttribute("width", w); box.setAttribute("height", h);
    texts.forEach((t, k) => { t.setAttribute("x", bx + pad); t.setAttribute("y", by + pad + lh * (k + 0.75)); });
  };
  const hide = () => { g.style.display = "none"; shown = -1; };
  const at = (ev) => {
    const m = svg.getScreenCTM();
    if (!m) return;
    const x = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(m.inverse()).x;
    let best = 0;
    for (let i = 1; i < data.p.length; i++) if (Math.abs(data.p[i][0] - x) < Math.abs(data.p[best][0] - x)) best = i;
    show(best);
  };
  svg.classList.add("scrubbable");
  svg.addEventListener("pointermove", at);
  svg.addEventListener("pointerdown", at);
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("pointercancel", hide);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  let tracked = false;
  svg.addEventListener("pointerenter", () => { if (!tracked) { tracked = true; track("chart_scrub", { chart: svg.classList[1] || "chart", page: location.pathname }); } });
}

/* -- The opt-in: the course in your inbox ----------------------------------------- */
// Every lesson is open to anyone (the founder's call, 2026-10-01). This form is the extra:
// it posts the address, the course and the link's campaign tag to /api/learn, which keeps
// the address and sends the link and the spreadsheet. The reader stays where they are.
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
    let body = {};
    try {
      const params = new URLSearchParams(location.search);
      res = await fetch("/api/learn", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, course: form.dataset.join, website: form.website.value, source: params.get("utm_source") || params.get("ref") || "" }),
      });
      body = await res.json().catch(() => ({}));
    } catch (e) { res = null; }
    button.disabled = false;
    if (res && res.status === 400) {
      err.textContent = body.error || "That address was not accepted. Check it and try again.";
      err.hidden = false;
      return;
    }
    // Say exactly what happened: nothing here may claim an email that was not sent.
    let said;
    if (!res || !res.ok) said = "That didn't go through on our side. Nothing is lost: every lesson and the spreadsheet are open right here. Try again later if you want the email.";
    else if (body.new === false) said = "You're already on the list for this course. Nothing more to do.";
    else if (body.emailed) said = `Sent to ${email}: the link and the spreadsheet. Nothing else arrives unless a fee card the courses use changes or a new course opens.`;
    else said = "Your address is saved, but the email didn't go out just now; we'll send it once it can. Every lesson and the spreadsheet are open right here.";
    track("learn_registered", { course: form.dataset.join, from: location.pathname, emailed: Boolean(body.emailed) });
    const done = document.createElement("p");
    done.className = "join-done";
    done.setAttribute("role", "status");
    done.textContent = said;
    form.replaceChildren(done);
  });
});

/* -- A page meant for paper: the one-page course cards ------------------------------- */
document.querySelectorAll("[data-print]").forEach((b) => b.addEventListener("click", () => { track("card_print", { page: location.pathname }); window.print(); }));

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
