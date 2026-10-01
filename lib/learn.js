/**
 * /learn's server side, minus the network: which courses exist, what a sign-up
 * must look like, the one email it sends, and the page an unsubscribe lands on.
 * api/learn.js wires these to Supabase and Resend; lib/learn.test.mjs pins them.
 *
 * HUBRICON_SPEC.md ("Education hub"): one email registers you for a course, the
 * way Acquisition.com's free courses work, and everything inside is open. So the
 * sign-up asks for nothing else, the email that follows delivers the link and the
 * spreadsheet and says what else will ever arrive (a note when a new course is
 * out), and one click stops that.
 */
import { renderHtml, renderText } from "./tool_email.js";

export const SITE = "https://www.hubricon.com";

/** A course is listed here only once it exists in full (no "coming soon"). */
export const COURSES = {
  "fee-staircase": {
    title: "The Fee Staircase",
    path: "/learn/fee-staircase",
    template: "/learn/files/hubricon-fee-staircase.xlsx",
    first: "Start with lesson 2 if you want a number tonight: five figures from any product page, and the One listing sheet does the rest.",
  },
  "price-curve": {
    title: "The Price Curve",
    path: "/learn/price-curve",
    template: "/learn/files/hubricon-price-curve.xlsx",
    first: "Start with lesson 5 if you have a raise in mind: the table under Your price says how many units it can lose and still pay.",
  },
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const TOKEN = /^[a-f0-9]{32}$/;

/** The sign-up, cleaned. A bot that fills the hidden field gets { bot: true } and nothing is kept. */
export function parseSignup(body) {
  if (!body || typeof body !== "object") return { error: "bad request" };
  if (String(body.website || "").trim()) return { bot: true };
  const email = String(body.email || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 200) return { error: "That doesn't look like an email address. Check it and try again." };
  const course = String(body.course || "");
  if (!Object.hasOwn(COURSES, course)) return { error: "No such course." };
  const source = String(body.source || "").replace(/[^\w.:/-]/g, "").slice(0, 64) || null;
  return { email, course, source };
}

/** The one email a sign-up sends: the link back, the spreadsheet, and what else will ever come. */
export function composeLearnEmail({ course, unsubscribeUrl, postalAddress, site = SITE }) {
  const c = COURSES[course];
  if (!c) throw new Error(`no course ${course}`);
  const blocks = [
    { p: `Here is ${c.title}, every lesson, for whenever you want to come back to it.` },
    { button: "Open the course", url: `${site}${c.path}` },
    { p: "And the spreadsheet, to keep on your own machine:" },
    { button: "Download the template", url: `${site}${c.template}` },
    { p: c.first },
    { p: "Every fee in it comes from Amazon's published 2026 schedules. If you find one that is wrong, reply and tell me: I fix it and say so." },
    {
      small: `You asked for this on hubricon.com. We write again only when a new course is out${postalAddress ? `. Hubricon · ${postalAddress}` : ""}.`,
      link: { text: "Unsubscribe", url: unsubscribeUrl },
    },
  ];
  return {
    subject: `${c.title}: your link`,
    text: renderText({ greeting: null, blocks }),
    html: renderHtml({ greeting: null, blocks }),
    // RFC 8058 one-click unsubscribe, which the large inboxes ask bulk senders for.
    headers: { "List-Unsubscribe": `<${unsubscribeUrl}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  };
}

export const unsubscribeUrl = (token, site = SITE) => `${site}/api/learn?unsubscribe=${token}`;

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

/** The page an unsubscribe link opens: a sentence, in the house style, and the way back. */
export function unsubscribePage(ok) {
  const head = ok ? "You're off the list." : "That link didn't match anything.";
  const body = ok
    ? "No more emails about courses. Every course you opened stays open."
    : "It may already have been used. Reply to any email from us and we'll take you off by hand.";
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(head)} — Hubricon</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,600&display=swap">
<link rel="stylesheet" href="/assets/hubricon.css">
</head><body><main class="wrap section"><span class="label">Hubricon</span>
<h1 style="margin-top: var(--s-3); font-size: var(--t-display-s)">${esc(head)}</h1>
<p class="lede" style="margin-top: var(--s-4)">${esc(body)}</p>
<p style="margin-top: var(--s-6)"><a href="/learn">Back to the courses</a></p></main></body></html>`;
}
