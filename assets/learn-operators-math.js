// The Operator's Math, lesson 4, on the reader's own store: drop Shopify's Orders export and read
// how often a new customer comes back, month by month, and the month they pay back what they cost.
// The orders are read with /lib/call.js's own Shopify reading plus the Email column, and counted by
// /assets/cohorts.mjs, which scripts/learn/operators_math.py holds to its reference. The file is read
// in this browser with FileReader; nothing is uploaded and nothing is requested.
"use strict";
import * as call from "/lib/call.js";
import { ordersFromRows, customerCurve, paybackMonth } from "/assets/cohorts.mjs";

const $ = (s, el = document) => el.querySelector(s);
const panel = document.getElementById("yours-customers");
const money = (v) => `$${v.toFixed(2)}`;
const pct = (v) => `${Math.round(v * 100)}%`;
const ORDERS = { ...call.SHOPIFY_ORDERS, email: [["email", "customeremail"], call.cleanStr] };
let cv = null;

function num(id) {
  const v = parseFloat($(id, panel).value);
  return Number.isFinite(v) && v > 0 ? v : null;
}

function render() {
  const out = $("#customers-out", panel);
  if (!cv) return;
  const margin = num("#yc-margin"), cac = num("#yc-cac");
  const rate = margin != null ? margin / 100 : null;
  const parts = [];
  parts.push(`<p><b>${cv.customers.toLocaleString("en-US")}</b> customers, of whom ${pct(cv.came_back_share)} came back at least once. ` +
    `A first order averages ${money(cv.first_value)}${cv.repeat_value != null ? `; a repeat order ${money(cv.repeat_value)}` : ""}. The export runs to ${cv.last}.</p>`);
  const rows = cv.curve.filter((r) => r.customers > 0);
  if (!rows.length) {
    parts.push(`<p>No customer's first order is a full month before the export's last day. Export a longer range.</p>`);
  } else {
    const head = `<th scope="col">Months since the first order</th><th scope="col">Customers counted</th><th scope="col">Repeat orders so far</th><th scope="col">Repeat revenue so far</th>` +
      (rate != null ? `<th scope="col">Margin back so far</th>` : "");
    parts.push(`<div class="table-scroll" role="region" aria-label="Repeat orders by month since the first order" tabindex="0"><table class="data"><thead><tr>${head}</tr></thead><tbody>` +
      rows.map((r) => `<tr><th scope="row">${r.month}</th><td class="num">${r.customers.toLocaleString("en-US")}</td><td class="num">${r.repeats.toFixed(2)}</td><td class="num">${money(r.repeat_revenue)}</td>` +
        (rate != null ? `<td class="num">${money(rate * (cv.first_value + r.repeat_revenue))}</td>` : "") + `</tr>`).join("") +
      `</tbody></table></div>`);
    parts.push(`<p class="source">Each month counts only the customers whose first order is at least that long before the export's last day, so the later months rest on fewer customers.</p>`);
  }
  if (rate != null && cac != null) {
    const m = paybackMonth(cv, rate, cac);
    parts.push(m != null
      ? `<h4>Paid back in month ${m}</h4><p>At a ${margin}% margin rate, a new customer's margin passes the ${money(cac)} they cost in month ${m}. Until then, each one is cash out.</p>`
      : `<h4>Not paid back within the export</h4><p>At a ${margin}% margin rate, no month in this export brings a new customer's margin to the ${money(cac)} they cost.</p>`);
  } else {
    parts.push(`<p>Add your margin rate and what a new customer costs, above, for the margin back and the payback month.</p>`);
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
        const rows = call.mapColumns(call.readTable(String(fr.result)), ORDERS);
        const read = customerCurve(ordersFromRows(rows, call.isoDate));
        if (!read.customers) throw new Error("No paid order in this export carries an email, so no customer can be counted.");
        cv = read;
        drop.classList.remove("bad");
        msg.textContent = `${file.name}: ${cv.customers.toLocaleString("en-US")} customers read, here in your browser.`;
        render();
      } catch (e) {
        drop.classList.add("bad");
        msg.textContent = `${e.message || "This file could not be read."} Shopify Admin, Orders, Export, all orders, CSV.`;
      }
    };
    fr.onerror = () => { drop.classList.add("bad"); msg.textContent = "This file could not be opened. Export it again and drop the new copy."; };
    fr.readAsText(file);
  };
  input.addEventListener("change", () => take(input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); take(e.dataTransfer.files[0]); });
  for (const id of ["#yc-margin", "#yc-cac"]) $(id, panel).addEventListener("input", render);
}

if (panel) init();
