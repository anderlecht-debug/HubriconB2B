// The Shopify Margin, lesson 6, on the reader's own store: drop Shopify's Products export and
// read every variant just past a pound line (priced on USPS Ground Advantage, by zone) and every
// variant priced under its own compare-at. The arithmetic is /lib/call.js's Shopify reading,
// the same /call uses, on /lib/fees.js's cards, which lib/fees.golden.json holds to the engine.
// The file is read in this browser with FileReader and never uploaded; the one request is the
// published rate card, /ratecard.json.
"use strict";
import * as call from "/lib/call.js";

const $ = (s, el = document) => el.querySelector(s);
const panel = document.getElementById("yours-variants");
const cents = (v) => `$${v.toFixed(2)}`;
const pct = (v) => `${Math.round(v * 100)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
let rc = null;

function render(read) {
  const out = $("#variants-out", panel);
  const a = call.analyseShopify(rc, read);
  const parts = [];
  parts.push(`<p><b>${a.priced.toLocaleString("en-US")}</b> priced variant${a.priced === 1 ? "" : "s"} read${a.no_weight ? `, ${a.no_weight} with no weight in the export` : ""}.</p>`);
  if (a.parcels.length) {
    const priced = a.parcels.filter((p) => p.priced);
    parts.push(`<h4>Just past a pound line: ${a.parcels.length}</h4>`);
    parts.push(`<p>Trimming each under its line saves ${priced.length ? `${cents(a.parcel_low)} to ${cents(a.parcel_high)} a parcel, by zone` : "a step the loaded card does not price"}. The weight here is Variant Grams: if it is the product alone, add your box and fill before you trust a line.</p>`);
    parts.push(`<div class="table-scroll" role="region" aria-label="Variants just past a pound line" tabindex="0"><table class="data"><thead><tr><th scope="col">Variant</th><th scope="col">Ounces</th><th scope="col">Past the line</th><th scope="col">Bills as</th><th scope="col">Saved a parcel</th></tr></thead><tbody>` +
      a.parcels.slice(0, 25).map((p) => `<tr><th scope="row">${esc(p.name || p.sku)}</th><td class="num">${p.weight_oz.toFixed(1)}</td><td class="num">${p.over_by.toFixed(1)} oz</td><td>${esc(p.band_above)}</td><td class="num">${p.priced ? `${cents(p.low)}–${cents(p.high)}` : "not on the card"}</td></tr>`).join("") +
      `</tbody></table></div>`);
  } else {
    parts.push(`<p>No variant sits within three ounces past a pound line.</p>`);
  }
  if (a.catalogue_share != null) {
    parts.push(`<h4>Under their own compare-at: ${a.below} of ${a.priced} (${pct(a.catalogue_share)})</h4>`);
    parts.push(a.policy
      ? `<p>Half or more of the catalogue is "on sale", so the sale is your price. Lesson 4 says what that costs and what to do.</p>`
      : `<p>Under half the catalogue is marked down: that reads as a promotion, not a policy.</p>`);
    if (a.anchors.length) {
      parts.push(`<div class="table-scroll" role="region" aria-label="Variants under their compare-at" tabindex="0"><table class="data"><thead><tr><th scope="col">Variant</th><th scope="col">Price</th><th scope="col">Compare-at</th><th scope="col">Shown off</th></tr></thead><tbody>` +
        a.anchors.slice(0, 25).map((v) => `<tr><th scope="row">${esc(v.name || v.sku)}</th><td class="num">${cents(v.price)}</td><td class="num">${cents(v.compare_at)}</td><td class="num">${cents(v.per_unit)} (${pct(v.share)})</td></tr>`).join("") +
        `</tbody></table></div>`);
    }
  }
  out.innerHTML = parts.join("");
  out.hidden = false;
}

function init() {
  panel.hidden = false;
  const drop = $(".yours-drop", panel), input = $("input[type=file]", drop), msg = $(".yours-drop-state", drop);
  const take = (file) => {
    if (!file) return;
    const fr = new FileReader();
    fr.onload = () => {
      try {
        const read = call.parseShopifyProducts(String(fr.result));
        drop.classList.remove("bad");
        msg.textContent = `${file.name}: ${read.length} variant${read.length === 1 ? "" : "s"} read, here in your browser.`;
        render(read);
      } catch (e) {
        drop.classList.add("bad");
        msg.textContent = `${e.message || "This file could not be read."} Shopify Admin, Products, Export, CSV for Excel or plain CSV.`;
      }
    };
    fr.onerror = () => { drop.classList.add("bad"); msg.textContent = "This file could not be opened. Export it again and drop the new copy."; };
    fr.readAsText(file);
  };
  input.addEventListener("change", () => take(input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); take(e.dataTransfer.files[0]); });
}

if (panel) {
  fetch("/ratecard.json").then((r) => r.json()).then((card) => { rc = card; init(); }).catch(() => {});
}
