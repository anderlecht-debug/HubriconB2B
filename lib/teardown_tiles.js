/**
 * The three headline tiles of the 60-second Teardown, as HTML.
 *
 * Two pages show them: teardown.html above its six sections, and index.html
 * on their own, directly under the hero, where a founder prices one listing
 * before reading anything else. Both pages call these builders, so the same
 * listing can never read one way on the home page and another on the full page.
 *
 * Pure: a result from lib/fees.js in, a string out. No DOM, no fetch.
 */

import * as fees from "./fees.js";

export const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
export const money = (v, d = 2) => (v == null || Number.isNaN(v)) ? "—" : (v < 0 ? "−" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const cents = (v) => v == null ? "—" : (v < 1 ? `${Math.round(v * 100)}c` : money(v));
export const pct = (v, d = 0) => v == null ? "—" : `${(v * 100).toFixed(d)}%`;
export const oz = (v) => v == null ? "—" : `${Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })} oz`;
export const num = (v) => v == null ? "—" : Math.round(v).toLocaleString("en-US");
export const range = (a, b, d = 2) => a === b ? money(a, d) : `${money(a, d)}–${money(b, d)}`;
export const monthly = (f) => f.dollarsHigh > 0 ? (f.dollarsLow > 0 ? `${money(f.dollarsLow, 0)}–${money(f.dollarsHigh, 0)} a month` : `up to ${money(f.dollarsHigh, 0)} a month`) : null;

/** An Amazon listing: what Amazon keeps on one unit, the cliff, and what 15 October adds. */
export function amazonTiles(rc, { item, u, found }, today = new Date()) {
  const card = fees.cardFor(rc, today);
  const lead = found[0];
  const tierKnown = item.tier === "small_standard" || item.tier === "large_standard";
  const tiles = [];
  if (u && u.keep != null) tiles.push(`<div class="tile glass"><span class="k">Amazon keeps, on one unit</span><div class="v bad">${pct(u.amazonTakePct)}</div><p>${money(u.referral + u.fee)} of ${money(u.price)}: referral plus fulfilment on the ${card?.name === "peak" ? "holiday peak" : "current"} card.</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">Amazon keeps, on one unit</span><div class="v">${pct(u?.referralRate)}+</div><p>The referral fee. Add package dimensions to price the fulfilment fee — we will not guess a size tier.</p></div>`);
  if (lead) tiles.push(`<div class="tile glass"><span class="k">The cliff, per unit</span><div class="v amber">${cents(lead.perUnitLow)}${lead.perUnitHigh > lead.perUnitLow ? `–${cents(lead.perUnitHigh)}` : ""}</div><p>${monthly(lead) ? `${monthly(lead)} at this listing's estimated volume.` : "Per unit; add a rank for the monthly bracket."}</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">The cliff</span><div class="v good">None</div><p>${tierKnown && item.itemWeightOz ? `This unit sits ${oz(fees.overBy(rc, card, item.itemWeightOz, item.dims))} inside its band — no shaveable edge, no price-band trap.` : "Nothing we can price without more of the listing."}</p></div>`);
  if (u && u.peakDelta != null) tiles.push(`<div class="tile glass"><span class="k">From 15 October</span><div class="v ${u.peakDelta > 0 ? "bad" : "good"}">${u.peakDelta > 0 ? "+" : ""}${cents(u.peakDelta)}</div><p>per unit on the holiday peak card${u.peakWindowHigh ? `; ${money(u.peakWindowLow, 0)}–${money(u.peakWindowHigh, 0)} over the three-month window` : ""}.</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">From 15 October</span><div class="v">?</div><p>Dimensions needed to price the peak card on this unit.</p></div>`);
  return tiles.join("");
}

/** A Shopify product: what one order keeps, the pound, and the zones where shipping loses money. */
export function shopifyTiles({ item, econ, found }) {
  const cliff = found.find((f) => f.kind === "carrier_band_edge");
  const perParcel = (f) => f.perUnitHigh > f.perUnitLow ? `${cents(f.perUnitLow)}–${cents(f.perUnitHigh)}` : cents(f.perUnitLow);
  const typedMonthly = (f) => f.monthlyTypedHigh > 0 ? `${range(f.monthlyTypedLow, f.monthlyTypedHigh, 0)} a month at the ${num(item.orders)} orders you typed` : null;
  const tiles = [];
  if (econ?.keepLow != null) tiles.push(`<div class="tile glass"><span class="k">Kept per order, before cost</span><div class="v amber">${range(econ.keepLow, econ.keepHigh)}</div><p>of ${money(econ.charged)} charged, after Shopify Payments and the carrier; the range is zone 1 to zone 8.</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">Kept per order</span><div class="v">?</div><p>${econ ? "This weight is past the carrier rows we hold, so shipping stays unpriced." : "A price and a shipping weight are needed."}</p></div>`);
  if (cliff) tiles.push(`<div class="tile glass"><span class="k">The pound, per parcel</span><div class="v amber">${perParcel(cliff)}</div><p>${typedMonthly(cliff) || "Per parcel; add your orders for the monthly figure."}</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">The pound</span><div class="v good">None</div><p>${item.billableWeightOz && item.billableWeightOz <= 16 ? "Under a pound the rate is flat: nothing to drop into." : "Not within 3 oz of a pound boundary."}</p></div>`);
  if (econ?.subsidyByZone) tiles.push(`<div class="tile glass"><span class="k">Zones where shipping loses money</span><div class="v ${econ.zonesSubsidised > 4 ? "bad" : econ.zonesSubsidised ? "amber" : "good"}">${econ.zonesSubsidised} of 8</div><p>${econ.shipCharge > 0 ? `You charge ${money(econ.shipCharge)}; the carrier charges ${range(econ.shipLow, econ.shipHigh)}.` : `Free shipping costs you ${range(econ.shipLow, econ.shipHigh)} an order, by zone.`}</p></div>`);
  else tiles.push(`<div class="tile glass"><span class="k">Zones where shipping loses money</span><div class="v">?</div><p>Unpriced past the loaded carrier rows.</p></div>`);
  return tiles.join("");
}
