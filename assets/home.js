// The home page's behaviour on top of /assets/site.js (the nav, the motion, clicks, the
// footer's live line). Everything visible is already in the HTML; this file counts which
// headline a visitor saw, keeps a referral code for /apply, sends a link to one of the old
// home-page sections to the page it now lives on, and fills a real client's story only
// from rows a client consented to publish. (The results wall's code stays for the day a
// client fills one; no page carries the wall until then.)
"use strict";
import { track, rpc, results } from "./site.js";

const root = document.documentElement;
const headline = root.getAttribute("data-headline") || "A";

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

/* A link to a section that used to be on the home page lands where it lives now
   (HUBRICON_SPEC.md, "A short first page", 2026-10-01): shared links keep working. After
   the referral code is kept, so a shared link loses nothing. */
const MOVED = {
  "#case-study": "/case-study", "#staircase": "/case-study#staircase", "#problem": "/case-study#problem",
  "#how": "/how-it-works", "#scoreboard": "/how-it-works#record", "#who": "/how-it-works#who", "#faq": "/how-it-works#faq",
  "#trust": "/offer#trust", "#results": "/honesty",
};
if (MOVED[location.hash]) location.replace(MOVED[location.hash]);

/* -- The results wall --------------------------------------------------------------- */
// public_results() returns only rows a client consented to publish, re-checked on every
// read: category and revenue band, rounded down, no brand named. At zero the wall reads
// zero and keeps its reserved frames, which is the point of it.
const HOW = {
  direct: "confirmed by the platform's own record",
  isolated: "measured on the exact line the move named",
  attributable: "measured against a stated counterfactual",
  recovered: "paid by Amazon on a claim we filed",
  gate: "the Profit Record against the invoice",
};
const KIND = {
  first_recovered: "First reimbursement recovered",
  gate_cleared: "A month cleared the fee",
  roi_3x: "Record above three times the fee",
  roi_5x: "Record above five times the fee",
  direct_measured: "A correction, measured",
};
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const money = (v) => "$" + Math.floor(Number(v) || 0).toLocaleString("en-US");
results.then((rows) => {
  if (!Array.isArray(rows) || !rows.length) return;
  const count = document.getElementById("wall-count");
  if (count) count.textContent = String(rows.length);
  const box = document.getElementById("wall-results");
  if (!box) return;
  box.replaceChildren(...rows.map((r) => {
    const a = el("article");
    a.append(el("span", "label", `${r.month || ""} · ${r.platform || "amazon"}`), el("span", "amt", money(r.amount_usd)),
      el("p", null, `A ${r.industry || "private-label"} brand${r.revenue_band ? `, ${r.revenue_band}` : ""}. ${KIND[r.kind] || r.kind || ""}.`),
      el("p", null, `How we know: ${HOW[r.how_we_know] || r.how_we_know || "graded on the Record"}.`));
    return a;
  }));
  box.hidden = false;
  track("results_shown", { n: rows.length });
});

/* One client's result, told in full, or nothing. public_case_study() returns a row only
   for a real client whose Proving Month closed, who wrote the before-state and the
   quote, and who said yes to publishing. No row, no section. */
(async () => {
  const sect = document.getElementById("result");
  const cs = sect ? await rpc("public_case_study") : null;
  if (!cs || !cs.before || !cs.quote || !Array.isArray(cs.numbers) || !cs.numbers.length) return;
  const $ = (k) => sect.querySelector(`[data-result="${k}"]`);
  const usd = (v) => (v == null ? "—" : "$" + Math.round(Number(v)).toLocaleString("en-US"));
  const closed = cs.closed_on
    ? new Date(cs.closed_on + "T12:00:00Z").toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
    : "";
  $("eyebrow").textContent = `A client · ${cs.brand || `a ${cs.industry || "private-label"} brand`}${closed ? ` · Proving Month closed ${closed}` : ""}`;
  $("before").textContent = cs.before;
  $("numbers").replaceChildren(...cs.numbers.map((x) => {
    const d = el("div");
    d.append(el("span", null, x.label), el("b", null, usd(x.amount_usd)), el("p", null, x.method));
    return d;
  }));
  $("quote").textContent = cs.quote;
  sect.hidden = false;
  track("case_study_shown", { named: Boolean(cs.brand) });
})();
