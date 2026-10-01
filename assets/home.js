// The home page's behaviour. Everything visible is already in the HTML; this file
// only plays the charts once, counts clicks, and shows a real client's result
// when one has been published with consent.
"use strict";
window.__hubriconMotion = true;

const root = document.documentElement;
const headline = root.getAttribute("data-headline") || "A";

/* -- Vercel Web Analytics --------------------------------------------------- */
window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
const track = (name, data) => { try { window.va("event", { name, data }); } catch (e) {} };
try {
  if (!sessionStorage.getItem("hubricon_h_seen")) {
    sessionStorage.setItem("hubricon_h_seen", "1");
    track("headline_shown", { v: headline });
  }
} catch (e) {}

/* A client's referral link (hubricon.com/?ref=<code>) rides the visit to /apply,
   which books it, so the sender can be credited. */
const REF_OK = /^[A-Za-z0-9_-]{4,32}$/;
try {
  const ref = new URLSearchParams(location.search).get("ref");
  if (ref && REF_OK.test(ref)) sessionStorage.setItem("hubricon_ref", ref);
} catch (e) {}

document.addEventListener("click", (ev) => {
  const a = ev.target.closest?.("[data-cta]");
  if (a) track("cta_click", { section: a.dataset.cta || "", h: headline });
});
document.querySelectorAll("details[data-q]").forEach((d) => {
  d.addEventListener("toggle", () => { if (d.open) track("faq_open", { q: d.dataset.q }); });
});
const method = document.querySelector("#case-study details");
method?.addEventListener("toggle", () => { if (method.open) track("method_open", {}); });

/* -- The charts: drawn once when they come into view, then still -------------- */
const ms = (name, fallback) => {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v.endsWith("ms") ? parseFloat(v) : v.endsWith("s") ? parseFloat(v) * 1000 : fallback;
};
if (root.classList.contains("motion")) {
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

/* -- The case-study film ------------------------------------------------------ */
// TODO(video): the five-beat case-study film (HUBRICON_SPEC.md, "Education: landing
// page vs the hub"). Set src and poster when it exists; until then nothing renders.
const VIDEO = { src: "", poster: "" };
if (VIDEO.src) {
  const slot = document.getElementById("case-video");
  const v = document.createElement("video");
  Object.assign(v, { src: VIDEO.src, poster: VIDEO.poster, controls: true, preload: "none", playsInline: true });
  v.addEventListener("play", () => track("video_play", {}), { once: true });
  slot.append(v);
  slot.hidden = false;
}

/* -- Real results, only once they exist ---------------------------------------- */
// The two anon-callable functions in the schema; both re-check consent on every read.
const PUBLISHABLE = "sb_publishable_byrEWlQDgM9fDW-2bwIA3w_XA0mrg5X";
async function rpc(name) {
  try {
    const res = await fetch(`https://cgqvdnhgbfxikzdqqaws.supabase.co/rest/v1/rpc/${name}`, {
      method: "POST", body: "{}",
      headers: { apikey: PUBLISHABLE, Authorization: `Bearer ${PUBLISHABLE}`, "content-type": "application/json" },
    });
    return res.ok ? await res.json() : null;
  } catch (e) { return null; }
}

(async () => {
  const pending = document.querySelector("[data-proof-pending]");
  if (!pending) return;
  const rows = await rpc("public_results");
  if (Array.isArray(rows) && rows.length) pending.hidden = true;
})();

/* One client's result, told in full, or nothing. public_case_study() returns a row only
   for a real client whose Proving Month closed, who wrote the before-state and the
   quote, and who said yes to publishing. No row, no section. */
(async () => {
  const sect = document.getElementById("result");
  const cs = sect ? await rpc("public_case_study") : null;
  if (!cs || !cs.before || !cs.quote || !Array.isArray(cs.numbers) || !cs.numbers.length) return;
  const $ = (k) => sect.querySelector(`[data-result="${k}"]`);
  const el = (tag, text) => { const x = document.createElement(tag); if (text != null) x.textContent = text; return x; };
  const usd = (v) => (v == null ? "—" : "$" + Math.round(Number(v)).toLocaleString("en-US"));
  const closed = cs.closed_on
    ? new Date(cs.closed_on + "T12:00:00Z").toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
    : "";
  $("eyebrow").textContent = `A client · ${cs.brand || `a ${cs.industry || "private-label"} brand`}${closed ? ` · Proving Month closed ${closed}` : ""}`;
  $("before").textContent = cs.before;
  $("numbers").replaceChildren(...cs.numbers.map((x) => {
    const d = el("div");
    d.append(el("span", x.label), el("b", usd(x.amount_usd)), el("p", x.method));
    return d;
  }));
  $("quote").textContent = cs.quote;
  sect.hidden = false;
  track("case_study_shown", { named: Boolean(cs.brand) });
})();
