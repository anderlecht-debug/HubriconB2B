/**
 * The words and the look of /say/<token> (api/consent.js): the page where a
 * client answers the price of the free month. Kept apart from the handler so
 * what it promises is tested without a database (lib/consent_page.test.mjs).
 *
 * Since 2026-10-01 the page is on the design system (/assets/hubricon.css):
 * its own style holds layout and tokens, never a colour. Before, it kept an
 * amber button and an Iowan serif of its own. The referral line says what
 * terms.html §9 says, and the "change your mind" line stays true after the
 * link expires.
 */

export const KINDS = ["testimonial", "anonymised_results", "named_results", "calibration", "network"];

export const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Layout and tokens only: every colour comes from /assets/hubricon.css.
export const STYLE = `
/* The consent page. Every value is a token from /assets/hubricon.css. */
body { font-size: var(--t-16); }
.wrap { width: min(680px, 100% - 2 * var(--gutter)); margin-inline: auto; padding-block: var(--s-6) var(--s-9); }
.wordmark { display: flex; width: max-content; align-items: center; gap: var(--s-2); color: var(--ink); text-decoration: none; font-weight: var(--strong); font-size: var(--t-20); letter-spacing: -0.02em; margin-bottom: var(--s-6); }
.wordmark svg { width: 26px; height: 26px; }
h1 { font-size: var(--t-display-s); margin: var(--s-2) 0 var(--s-3); }
h2 { font-size: var(--t-20); letter-spacing: -0.015em; line-height: 1.3; margin-bottom: var(--s-2); }
p { max-width: 62ch; }
.sub { color: var(--ink-2); }
.panel { background: var(--paper-2); border-radius: var(--radius); padding: var(--s-5) var(--s-6); margin: var(--s-4) 0; }
label.row { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: var(--s-3); align-items: start; padding: var(--s-3) 0; border-top: 1px solid var(--rule); }
label.row:first-of-type { border-top: 0; }
label.row b { display: block; }
input[type=checkbox] { width: 18px; height: 18px; margin-top: 4px; accent-color: var(--ink); }
textarea { width: 100%; min-height: 96px; margin-top: var(--s-2); padding: var(--s-3); border: 1px solid var(--rule-2); border-radius: 8px; font: inherit; color: var(--ink); background: var(--paper); }
.before { margin-top: var(--s-4); }
.btn { margin-top: var(--s-2); }
.link { display: block; margin-top: var(--s-2); padding: var(--s-3); border: 1px solid var(--rule); border-radius: 8px; background: var(--paper); color: var(--ink); font-size: var(--t-14); word-break: break-all; }
.back { margin-top: var(--s-4); font-size: var(--t-16); }
.back a { color: var(--ink); text-underline-offset: 3px; }
footer { margin-top: var(--s-6); padding-top: var(--s-4); border-top: 1px solid var(--rule); font-size: var(--t-14); color: var(--ink-3); }
@media (max-width: 560px) { .panel { padding: var(--s-4); } }
`;

// terms.html §9, second paragraph, said to the person who holds the link.
export const REFERRAL =
  "Their first month is free, as yours was. If they stay past their own thirtieth day, one month of your " +
  "fee is credited against your next invoice, or a free month is added if you are not yet invoiced: one " +
  "credit per brand you introduce, applied when that brand's first invoice is raised after its own " +
  "thirtieth day, and never before (terms §9).";

// True after the link has expired too: the right to change an answer does not expire with it.
export const CHANGE =
  "You can change any answer later: here while this link works, or at any time by replying to any email from us.";

const MARK = `<a class="wordmark" href="/" aria-label="Hubricon, home"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>Hubricon</a>`;

/** A whole page: the site's fonts and stylesheet, then the body. */
export function page(title, body) {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<meta name="robots" content="noindex,nofollow"><title>${esc(title)}</title>` +
      `<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` +
      `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,600&display=swap">` +
      `<link rel="stylesheet" href="/assets/hubricon.css">` +
      `<style>${STYLE}</style></head><body><div class="wrap">${MARK}${body}</div></body></html>`,
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }
  );
}

/** The form: the three consents, the testimonial and its "before", and the client's own link. */
export function form({ identity, existing = [], code, token, site }) {
  const has = (k) => existing.find((r) => r.kind === k);
  const on = (k) => (has(k)?.granted ? "checked" : "");
  const testimonial = has("testimonial")?.testimonial || "";
  const named = has("testimonial")?.testimonial_named_ok ? "checked" : "";
  return page(
    `The price of the free month — ${identity.company_name || "Hubricon"}`,
    `<span class="label">${esc(identity.company_name || "Your account")} · private</span>
<h1>The whole price of your free month, in a minute.</h1>
<p class="sub">We said we would ask for two things if your Profit Record earned it. Each box is a separate
yes; an unticked box is a no, and either is fine. ${CHANGE} Withdraw a permission to publish and the
result comes down at once.</p>
<form method="post" action="/api/consent?t=${esc(token)}">
<div class="panel">
  <h2>What we may publish</h2>
  <label class="row"><input type="checkbox" name="anonymised_results" ${on("anonymised_results")}>
    <span><b>Publish my results, anonymised.</b> No company name, storefront, brand, ASIN or SKU.
    Figures rounded and shown by category and revenue band, on the public results page.</span></label>
  <label class="row"><input type="checkbox" name="named_results" ${on("named_results")}>
    <span><b>You may name my brand beside those results.</b> Optional, and off unless you tick it.</span></label>
  <label class="row"><input type="checkbox" name="calibration" ${on("calibration")}>
    <span><b>Use aggregate statistics from my account to calibrate your public estimates.</b>
    A slope, a rate, a ratio — never a figure of mine, never to advise another client on my
    business, and every estimate that uses it says how many accounts stand behind it.</span></label>
</div>
<div class="panel">
  <h2>Warning other brands</h2>
  <label class="row"><input type="checkbox" name="network" ${on("network")}>
    <span><b>Let my account help warn other brands when Amazon or Shopify changes a fee.</b>
    Only the change leaves my account — which fee, which way, roughly when, and by what
    percentage — never a figure of mine, never my name, a SKU or an ASIN. An alert goes out only
    when several accounts show the same change, and it says how many stand behind it. My
    account also counts toward your measure of what each kind of move really delivers.</span></label>
</div>
<div class="panel">
  <h2>A short testimonial</h2>
  <label class="row"><input type="checkbox" name="testimonial" ${on("testimonial")}>
    <span><b>Yes, you may quote me.</b> Two honest lines are plenty. Attributed by first name and
    category unless you tick the box below.</span></label>
  <textarea name="testimonial_text" placeholder="What changed in how you run the business, in your words. Thirty words is plenty.">${esc(testimonial)}</textarea>
  <label class="row"><input type="checkbox" name="testimonial_named_ok" ${named}>
    <span><b>You may attribute it to my name and brand.</b></span></label>
  <p class="sub before"><b>Before, in your words.</b> Optional. One or two
  sentences about what this looked like before: a Sunday night with five reports, a question from your
  accountant you could not answer, a decision you kept putting off. If we ever tell your story, it starts
  here, and only with what you wrote.</p>
  <textarea name="before_text" placeholder="Before Hubricon, I…">${esc(has("testimonial")?.before_text || "")}</textarea>
</div>
<button class="btn" type="submit">Save my answers</button>
</form>
<div class="panel">
  <h2>Your link</h2>
  <p>If another founder should see their own numbers the way you have, send them this. ${REFERRAL}</p>
  <span class="link">${esc(site)}/?ref=${esc(code)}</span>
</div>
<footer>This page is private to ${esc(identity.company_name || "your workspace")}. Its link is not
indexed and stops working within 90 days of when we sent it; your answers stay as you left them.
Reply to any Hubricon email to reach the founder.</footer>`
  );
}

/** The page after a save. */
export function saved({ identity, code, token, site, networkNote = "", granted = 0 }) {
  return page(
    "Saved — thank you",
    `<span class="label">${esc(identity.company_name || "Your account")} · private</span>
<h1>Saved. Thank you.</h1>
<p class="sub">Your answers are recorded exactly as ticked. Nothing is published that your Profit Record has
not proven, and nothing you did not allow. ${CHANGE}</p>
${networkNote}
<div class="panel">
  <h2>Your link</h2>
  <p>Send it to a founder who should see their own numbers. ${REFERRAL}</p>
  <span class="link">${esc(site)}/?ref=${esc(code)}</span>
</div>
<p class="back"><a href="/api/consent?t=${esc(token)}">Back to your answers</a> ·
<a href="${esc(site)}/portal">Open Hubricon</a></p>
<footer>${granted} of ${KINDS.length} permissions granted.</footer>`
  );
}
