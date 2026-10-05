/**
 * The email a visitor asked for on the retired 60-second calculator: their
 * result, restated from the numbers, and the door that exists today, the
 * 20-minute call, with the free course for their store beside it.
 *
 * Dormant since September: /teardown redirects home and no page on the site
 * posts to api/quick.js, which still composes this email for a request that
 * reaches it. Until 2026-10-01 it offered "the full Profit Teardown… back in
 * 24 hours, free", an upload page "within about an hour", a link back to the
 * retired page, and (on Shopify) labels, apps and 3PL charges and Meta "bleed
 * by ad set" that nothing reads (Meta is read at campaign level). None of that
 * is true now, so none of it is said.
 *
 * Nothing the visitor typed as prose reaches this email. The route recomputes
 * the result server-side from the numeric inputs (lib/fees.js) and this file
 * turns that into sentences, so a stranger cannot use Hubricon's sender to
 * deliver their own text to someone else's inbox. The only free text is the
 * first name, escaped and capped.
 *
 * Hubricon's one email look, defined here once for the JavaScript senders
 * (scripts/lib/email.mjs reads it from this file; the engine's
 * onboarding.render_html and supabase/templates/magic-link.html write the same
 * values): one sans, ink #0a0e17 on white, #3b4250 for what is secondary, one
 * hairline rule #e4e7ec before the sign-off, the button in ink with the one
 * radius, 520px, Hagen's signature. Blue (#0b5fff) is for money alone, so a
 * letter of prose carries none.
 */

export const EMAIL_FONT = "Inter,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
export const EMAIL_INK = "#0a0e17";
export const EMAIL_INK_2 = "#3b4250";
export const EMAIL_RULE = "#e4e7ec";
export const EMAIL_P = `style="font-size:16px;color:${EMAIL_INK};margin:0 0 20px"`;
export const EMAIL_SMALL = `style="font-size:14px;color:${EMAIL_INK_2};margin:0 0 20px"`;
export const EMAIL_LIST = `style="font-size:15px;color:${EMAIL_INK};padding-left:22px;margin:0 0 20px"`;
export const EMAIL_PANEL = `style="font-size:14px;color:${EMAIL_INK};background:#f5f6f8;border-radius:10px;padding:10px 14px;margin:0 0 20px"`;
export const EMAIL_BUTTON = `style="display:inline-block;background:${EMAIL_INK};color:#ffffff;text-decoration:none;padding:14px 24px;border-radius:10px;font-size:15px;font-weight:600"`;
export const EMAIL_URL = `style="color:${EMAIL_INK_2};word-break:break-all"`;

/** The letter around the blocks: the wordmark, the greeting, the one rule, the signature. */
export function emailLetter(greetingHtml, blockHtml) {
  return [
    `<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:${EMAIL_FONT};color:${EMAIL_INK};font-size:16px;line-height:1.6">`,
    `  <p style="font-size:17px;font-weight:600;letter-spacing:-0.01em;color:${EMAIL_INK};margin:0 0 28px">Hubricon</p>`,
    greetingHtml ? `  <p ${EMAIL_P}>${greetingHtml}</p>` : "",
    ...blockHtml,
    `  <hr style="border:0;border-top:1px solid ${EMAIL_RULE};margin:8px 0 20px">`,
    `  <p ${EMAIL_P}>Best,</p>`,
    `  <p style="font-size:14px;color:${EMAIL_INK};margin:0">Hagen Simmons<br><span style="color:${EMAIL_INK_2}">Hubricon</span></p>`,
    `</div>`,
  ].filter(Boolean).join("\n");
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (v, d = 2) => (v == null || Number.isNaN(v)) ? "—" : (v < 0 ? "−" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const cents = (v) => v == null ? "—" : (v < 1 ? `${Math.round(v * 100)}c` : money(v));
const pct = (v, d = 0) => v == null ? "—" : `${(v * 100).toFixed(d)}%`;

function htmlBlock(b) {
  if (b.p) return `  <p ${EMAIL_P}>${esc(b.p)}</p>`;
  if (b.li) return `  <ul ${EMAIL_LIST}>\n${b.li.map((i) => `    <li style="margin:0 0 8px">${esc(i)}</li>`).join("\n")}\n  </ul>`;
  if (b.button) return [
    `  <p style="margin:0 0 10px"><a href="${esc(b.url)}" ${EMAIL_BUTTON}>${esc(b.button)}</a></p>`,
    `  <p ${EMAIL_SMALL}><a href="${esc(b.url)}" ${EMAIL_URL}>${esc(b.url)}</a></p>`,
  ].join("\n");
  if (b.small) return `  <p ${EMAIL_SMALL}>${esc(b.small)}${b.link ? ` <a href="${esc(b.link.url)}" style="color:${EMAIL_INK_2}">${esc(b.link.text)}</a>` : ""}</p>`;
  throw new Error(`Unknown email block: ${JSON.stringify(b)}`);
}
const textBlock = (b) => b.p ?? (b.small != null ? b.small + (b.link ? ` ${b.link.text}: ${b.link.url}` : "") : null) ?? (b.li ? b.li.map((i) => `- ${i}`).join("\n") : `  ${b.url}`);

export function renderHtml({ greeting, blocks }) {
  return emailLetter(greeting ? esc(greeting) : "", blocks.map(htmlBlock));
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
    case "carrier_band_edge": return `The pound: your product ships at ${e.yourWeightOz} oz, ${e.overByOz} oz over the ${e.edge} oz boundary, so every parcel bills at the ${e.bandAbove} rate where ${e.bandBelow} would have paid less — ${per} a parcel, nearest zone to farthest${f.monthlyTypedHigh > 0 ? ` (${money(f.monthlyTypedLow, 0)}–${money(f.monthlyTypedHigh, 0)} a month at the orders you typed)` : ""}.`;
    case "permanent_discount": return `The anchor: the product page says ${money(e.compareAt)} and sells at ${money(e.price)}, ${Math.round(e.discountShare * 100)}% off — ${money(f.perUnitLow)} a unit given to an anchor${f.monthlyTypedHigh > 0 ? ` (${money(f.monthlyTypedLow, 0)} a month at the orders you typed)` : ""}. Whether that is a promotion or a policy shows across the whole catalogue, which the call reads from your Products export.`;
    default: return `${f.kind}: ${per} a unit${monthly}.`;
  }
}

// The free course that starts with the visitor's own store (engine triage.LEARN_URLS).
export const LEARN_URLS = {
  amazon: "https://www.hubricon.com/learn/fee-staircase",
  shopify: "https://www.hubricon.com/learn/price-curve",
};
const SMALL_PRINT = (postalAddress) => `You asked for this email on hubricon.com${postalAddress ? `. Hubricon · ${postalAddress}` : ""}. Nothing else follows unless you reply.`;

/** Subject and body from a server-side analysis (lib/fees.js analyse()). `link`, the
 *  retired calculator's address, is accepted and not printed: that page now redirects home. */
export function composeToolEmail({ firstName, asin, result, link, applyUrl, postalAddress }) {
  if (result.econ !== undefined) return composeShopifyEmail({ firstName, handle: asin, result, link, applyUrl, postalAddress });
  const { item, u, found, sim } = result;
  const lead = found[0];
  const what = asin ? `listing ${asin}` : "your listing";
  const short = lead ? (lead.kind === "price_band_edge" ? `${money(lead.evidence.yourPrice)} nets less than ${money(lead.evidence.targetPrice)}` : lead.kind === "fee_band_edge" ? `${lead.evidence.overByOz} oz over a fee band` : lead.kind === "size_tier_edge" ? "one dimension into a dearer tier" : "paying fulfilment on the box")
    : (u?.keep != null ? `you keep ${money(u.keep)} of ${money(u.price)}` : "one listing, priced");
  const blocks = [];
  blocks.push({ p: `Here is the result you ran on ${what}, restated from the numbers you typed. Every dollar is arithmetic on a published rate, and every estimate says so.` });
  const li = [];
  if (u?.keep != null) li.push(`After Amazon's referral (${pct(u.referralRate)}) and fulfilment (${money(u.fee)}) fees you keep ${money(u.keep)} of ${money(u.price)} — Amazon's take is ${pct(u.amazonTakePct)}.`);
  else if (u) li.push(`Referral fee ${money(u.referral)} at ${pct(u.referralRate)}; the fulfilment fee stayed unpriced because the size tier needs package dimensions.`);
  for (const f of found.slice(0, 2)) li.push(findingLine(f));
  if (!found.length && u?.keep != null) li.push("No cliff: the unit sits clear of every band edge within reach and the price is clear of Amazon's $10 and $50 fee columns.");
  if (u?.contribution != null) li.push(`Break-even ACoS ${pct(Math.max(u.breakEvenAcos, 0), 1)}: each unit contributes ${money(u.contribution)} after your landed cost, so any campaign above that ACoS loses money on it. The price floor is ${money(u.priceFloor)}.`);
  if (u?.peakDelta != null && u.peakDelta > 0) li.push(`From 15 October the holiday peak card adds ${cents(u.peakDelta)} a unit (${money(u.fee)} → ${money(u.feePeak)})${u.peakWindowHigh ? `, ${money(u.peakWindowLow, 0)}–${money(u.peakWindowHigh, 0)} across the window` : ""}; ${money(u.priceToHoldMargin)} holds your margin flat.`);
  if (sim) li.push(`Ten thousand simulated months: median ${money(sim.p50, 0)}, with 80% of months between ${money(sim.p10, 0)} and ${money(sim.p90, 0)}${sim.pLoss > 0 ? `; ${pct(sim.pLoss, 1)} of months lose money` : ""}.`);
  blocks.push({ li });
  blocks.push({ p: "That is what one public listing can tell us. The way in for the rest is a 20-minute call: we open your own Seller Central reports together and price, in your browser, what public pages can't show: aged stock, low-inventory fees, an ad target set wrong. Nothing is uploaded, and there is no card." });
  blocks.push({ button: "Book your call", url: applyUrl });
  blocks.push({ p: `Or learn the method yourself, free and in full: ${LEARN_URLS.amazon}. Reply to this email if you would rather ask me something first.` });
  blocks.push({ small: SMALL_PRINT(postalAddress) });
  const greeting = firstName ? `Hi ${String(firstName).trim().slice(0, 80)},` : "Hello,";
  const msg = { greeting, blocks };
  return { subject: `Your listing, priced: ${short}`, text: renderText(msg), html: renderHtml(msg) };
}

/** One email through Resend's REST API. Resolves to { ok, id, status, error }; never throws. */
export async function sendResend({ apiKey, from, to, replyTo, subject, text, html, headers, fetchImpl = fetch }) {
  if (!apiKey) return { ok: false, status: 0, error: "RESEND_API_KEY not set" };
  try {
    const res = await fetchImpl("https://api.resend.com/emails", {
      method: "POST",
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json", "user-agent": "Hubricon-site/1.0 (+https://www.hubricon.com)" },
      body: JSON.stringify({ from, to: [to], subject, text, html, ...(replyTo ? { reply_to: replyTo } : {}), ...(headers ? { headers } : {}) }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, status: res.status, error: body?.message || body?.error || `HTTP ${res.status}` };
    return { ok: true, status: res.status, id: body?.id || null };
  } catch (err) {
    return { ok: false, status: 0, error: String(err?.message || err) };
  }
}


const range = (a, b, d = 2) => a === b ? money(a, d) : `${money(a, d)}–${money(b, d)}`;

/** The Shopify side: one order through Shopify Payments and the carrier, by zone. */
export function composeShopifyEmail({ firstName, handle, result, link, applyUrl, postalAddress }) {
  const { item, econ, found } = result;
  const cliff = found.find((f) => f.kind === "carrier_band_edge");
  const what = handle ? `your product at ${String(handle).replace(/^https?:\/\//, "").slice(0, 80)}` : "your product";
  const short = cliff ? `${cliff.evidence.overByOz} oz over a pound` : econ?.keepLow != null ? `you keep ${range(econ.keepLow, econ.keepHigh)} of ${money(econ.charged)} an order` : "one product, priced";
  const li = [];
  if (econ?.keepLow != null) li.push(`One order charged at ${money(econ.charged)} (${item.unitsPerOrder} × ${money(econ.price)}${econ.shipCharge ? ` + ${money(econ.shipCharge)} shipping` : ", free shipping"}): Shopify Payments takes ${money(econ.payments)}, the carrier ${range(econ.shipLow, econ.shipHigh)} by zone, and you keep ${range(econ.keepLow, econ.keepHigh)} before ads and cost.`);
  else if (econ) li.push(`Shopify Payments takes ${money(econ.payments)} on the ${money(econ.charged)} charge; the carrier stayed unpriced because this weight is past the rows we hold.`);
  if (econ?.subsidyByZone) li.push(econ.shipCharge > 0 ? `Your ${money(econ.shipCharge)} shipping charge loses money in ${econ.zonesSubsidised} of 8 zones against the carrier's ${range(econ.shipLow, econ.shipHigh)}.` : `Free shipping costs you ${range(econ.shipLow, econ.shipHigh)} an order, by zone.`);
  for (const f of found.slice(0, 2)) li.push(findingLine(f));
  if (!cliff && item.billableWeightOz) li.push(item.billableWeightOz <= 16 ? "No pound cliff: under a pound the USPS commercial rate is flat." : "No pound cliff within 3 oz of this parcel.");
  if (econ?.contributionLow != null) li.push(`Break-even ROAS ${econ.breakEvenRoasLow ? `${econ.breakEvenRoasLow.toFixed(2)}–${econ.breakEvenRoasHigh ? econ.breakEvenRoasHigh.toFixed(2) : "∞"}` : "—"} across zones: an order contributes ${range(econ.contributionLow, econ.contributionHigh)} after your landed cost. The price floor is ${range(econ.priceFloorLow, econ.priceFloorHigh)} a unit.`);
  const blocks = [
    { p: `Here is the result you ran on ${what}, restated from the numbers you typed. Every dollar is arithmetic on a published rate — Shopify Payments' plan rates and USPS Ground Advantage commercial prices by zone — and your orders a month are your own figure, not an estimate.` },
    { li },
    { p: "That is what one public product page can tell us. The way in for the rest is a 20-minute call: we open your Shopify Products export together and price, in your browser, what it shows across your whole catalogue: prices sitting under their own compare-at, and parcels just past a USPS pound line. Nothing is uploaded, and there is no card." },
    { button: "Book your call", url: applyUrl },
    { p: `Or learn the method yourself, free and in full: ${LEARN_URLS.shopify}. Reply to this email if you would rather ask me something first.` },
    { small: SMALL_PRINT(postalAddress) },
  ];
  const greeting = firstName ? `Hi ${String(firstName).trim().slice(0, 80)},` : "Hello,";
  const msg = { greeting, blocks };
  return { subject: `Your product, priced: ${short}`, text: renderText(msg), html: renderHtml(msg) };
}
