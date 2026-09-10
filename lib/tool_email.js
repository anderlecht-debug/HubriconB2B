/**
 * The email a visitor asked for on /teardown: their result, restated from the
 * numbers, with the link back and the door to the full Teardown.
 *
 * Nothing the visitor typed as prose reaches this email. The route recomputes
 * the result server-side from the numeric inputs (lib/fees.js) and this file
 * turns that into sentences, so a stranger cannot use Hubricon's sender to
 * deliver their own text to someone else's inbox. The only free text is the
 * first name, escaped and capped.
 *
 * Same look as the onboarding emails (scripts/lib/email.mjs, which Vercel does
 * not ship): Georgia, 520px, the Hubricon label, Hagen's signature.
 */

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (v, d = 2) => (v == null || Number.isNaN(v)) ? "—" : (v < 0 ? "−" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const cents = (v) => v == null ? "—" : (v < 1 ? `${Math.round(v * 100)}c` : money(v));
const pct = (v, d = 0) => v == null ? "—" : `${(v * 100).toFixed(d)}%`;

const P = 'style="font-size:16px;margin:0 0 20px"';
const SMALL = 'style="font-size:14px;color:#555;margin:0 0 20px"';

function htmlBlock(b) {
  if (b.p) return `  <p ${P}>${esc(b.p)}</p>`;
  if (b.li) return `  <ul style="font-size:15px;padding-left:22px;margin:0 0 20px">\n${b.li.map((i) => `    <li style="margin:0 0 8px">${esc(i)}</li>`).join("\n")}\n  </ul>`;
  if (b.button) return [
    `  <p style="margin:0 0 10px"><a href="${esc(b.url)}" style="display:inline-block;background:#1a1a1a;color:#ffffff;text-decoration:none;padding:12px 24px;font-size:15px">${esc(b.button)}</a></p>`,
    `  <p ${SMALL}><a href="${esc(b.url)}" style="color:#555;word-break:break-all">${esc(b.url)}</a></p>`,
  ].join("\n");
  if (b.small) return `  <p ${SMALL}>${esc(b.small)}</p>`;
  throw new Error(`Unknown email block: ${JSON.stringify(b)}`);
}
const textBlock = (b) => b.p ?? b.small ?? (b.li ? b.li.map((i) => `- ${i}`).join("\n") : `  ${b.url}`);

export function renderHtml({ greeting, blocks }) {
  return [
    `<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:Georgia,'Times New Roman',serif;color:#1a1a1a;line-height:1.6">`,
    `  <p style="font-size:15px;letter-spacing:0.08em;text-transform:uppercase;color:#8a8a8a;margin:0 0 28px">Hubricon</p>`,
    greeting ? `  <p ${P}>${esc(greeting)}</p>` : "",
    ...blocks.map(htmlBlock),
    `  <p ${P}>Best,</p>`,
    `  <p style="font-size:14px;margin:0">Hagen Simmons<br><span style="color:#8a8a8a">Hubricon</span></p>`,
    `</div>`,
  ].filter(Boolean).join("\n");
}
export const renderText = ({ greeting, blocks }) => [greeting, ...blocks.map(textBlock), "Best,\nHagen — Hubricon"].filter(Boolean).join("\n\n");

/** One sentence per finding kind, from its evidence only. */
export function findingLine(f) {
  const e = f.evidence || {};
  const monthly = f.dollarsHigh > 0 ? (f.dollarsLow > 0 ? ` — ${money(f.dollarsLow, 0)}–${money(f.dollarsHigh, 0)} a month at the estimated volume` : ` — up to ${money(f.dollarsHigh, 0)} a month`) : "";
  const per = f.perUnitHigh > f.perUnitLow ? `${cents(f.perUnitLow)}–${cents(f.perUnitHigh)}` : cents(f.perUnitLow);
  switch (f.kind) {
    case "price_band_edge": return `The price-band trap: ${money(e.yourPrice)} nets less per unit than ${money(e.targetPrice)} does, because crossing Amazon's $${e.edge} fee column adds ${cents(e.feeJumpLow)}${e.feeJumpHigh > e.feeJumpLow ? `–${cents(e.feeJumpHigh)}` : ""} in fulfilment. Break-even is ${money(e.breakEvenPrice)}. Worth ${per} a unit${monthly}.`;
    case "fee_band_edge": return `The fee cliff: your published weight of ${e.yourWeightOz} oz is ${e.overByOz} oz over the ${e.edge} oz band edge, and that step is ${per} a unit on the published schedule${monthly}.`;
    case "dim_weight_overage": return `The box: ${e.dims.join(" × ")} in past a cubic foot is billed on dimensional weight (${(e.dimWeightOz / 16).toFixed(1)} lb), ${per} a unit more than the real weight${monthly}.`;
    case "size_tier_edge": return `The size tier: the ${e.axis} at ${e.actualIn} in against a ${e.limitIn} in limit puts the unit in large standard, ${per} a unit more than small standard${monthly}.`;
    default: return `${f.kind}: ${per} a unit${monthly}.`;
  }
}

/** Subject and body from a server-side analysis (lib/fees.js analyse()). */
export function composeToolEmail({ firstName, asin, result, link, applyUrl, postalAddress }) {
  const { item, u, found, sim } = result;
  const lead = found[0];
  const what = asin ? `listing ${asin}` : "your listing";
  const short = lead ? (lead.kind === "price_band_edge" ? `${money(lead.evidence.yourPrice)} nets less than ${money(lead.evidence.targetPrice)}` : lead.kind === "fee_band_edge" ? `${lead.evidence.overByOz} oz over a fee band` : lead.kind === "size_tier_edge" ? "one dimension into a dearer tier" : "paying fulfilment on the box")
    : (u?.keep != null ? `you keep ${money(u.keep)} of ${money(u.price)}` : "one listing, priced");
  const blocks = [];
  blocks.push({ p: `Here is the 60-second Teardown you ran on ${what}, restated from the numbers you typed. Every dollar is arithmetic on a published rate; every estimate says so on the page.` });
  const li = [];
  if (u?.keep != null) li.push(`After Amazon's referral (${pct(u.referralRate)}) and fulfilment (${money(u.fee)}) fees you keep ${money(u.keep)} of ${money(u.price)} — Amazon's take is ${pct(u.amazonTakePct)}.`);
  else if (u) li.push(`Referral fee ${money(u.referral)} at ${pct(u.referralRate)}; the fulfilment fee stayed unpriced because the size tier needs package dimensions.`);
  for (const f of found.slice(0, 2)) li.push(findingLine(f));
  if (!found.length && u?.keep != null) li.push("No cliff: the unit sits clear of every band edge within reach and the price is clear of Amazon's $10 and $50 fee columns.");
  if (u?.contribution != null) li.push(`Break-even ACoS ${pct(Math.max(u.breakEvenAcos, 0), 1)}: each unit contributes ${money(u.contribution)} after your landed cost, so any campaign above that ACoS loses money on it. The price floor is ${money(u.priceFloor)}.`);
  if (u?.peakDelta != null && u.peakDelta > 0) li.push(`From 15 October the holiday peak card adds ${cents(u.peakDelta)} a unit (${money(u.fee)} → ${money(u.feePeak)})${u.peakWindowHigh ? `, ${money(u.peakWindowLow, 0)}–${money(u.peakWindowHigh, 0)} across the window` : ""}; ${money(u.priceToHoldMargin)} holds your margin flat.`);
  if (sim) li.push(`Ten thousand simulated months: median ${money(sim.p50, 0)}, with 80% of months between ${money(sim.p10, 0)} and ${money(sim.p90, 0)}${sim.pLoss > 0 ? `; ${pct(sim.pLoss, 1)} of months lose money` : ""}.`);
  blocks.push({ li });
  blocks.push({ button: "Open your result", url: link });
  blocks.push({ p: "That is what a public page can tell us. Your own exports tell us the rest: true net margin per SKU after every fee line and honestly allocated ads, ad bleed by search term in dollars, stockout probability per SKU, and the reimbursements Amazon owes you. The full Profit Teardown reads them and is back in 24 hours, free." });
  blocks.push({ button: "Get the full Teardown", url: applyUrl });
  blocks.push({ p: "Your private upload page for it follows from me in a separate email within about an hour. Reply to this one if you would rather talk first." });
  blocks.push({ small: `You asked for this email on hubricon.com/teardown${postalAddress ? `. Hubricon · ${postalAddress}` : ""}. Nothing else follows unless you reply.` });
  const greeting = firstName ? `Hi ${String(firstName).trim().slice(0, 80)},` : "Hello,";
  const msg = { greeting, blocks };
  return { subject: `Your 60-second Teardown: ${short}`, text: renderText(msg), html: renderHtml(msg) };
}

/** One email through Resend's REST API. Resolves to { ok, id, status, error }; never throws. */
export async function sendResend({ apiKey, from, to, replyTo, subject, text, html, fetchImpl = fetch }) {
  if (!apiKey) return { ok: false, status: 0, error: "RESEND_API_KEY not set" };
  try {
    const res = await fetchImpl("https://api.resend.com/emails", {
      method: "POST",
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json", "user-agent": "Hubricon-site/1.0 (+https://www.hubricon.com)" },
      body: JSON.stringify({ from, to: [to], subject, text, html, ...(replyTo ? { reply_to: replyTo } : {}) }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, status: res.status, error: body?.message || body?.error || `HTTP ${res.status}` };
    return { ok: true, status: res.status, id: body?.id || null };
  } catch (err) {
    return { ok: false, status: 0, error: String(err?.message || err) };
  }
}
