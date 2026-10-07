// The figures every film stage draws from: the site's own (scripts/build-pages.mjs `figures()`, called
// read-only, never changed here), plus the case-study listing's other staircases for the charts' small
// multiples (kinds/charts.mjs "staircases"): its fulfilment fee by the price band it charges and by
// size tier, at its own weight, on the card in force, from the same fee library and rate card the case
// study is priced with (lib/fees.js, ratecard.json). Only the listing's public facts are used: its
// weight, its tier and its price band, all in data/case-study.json.
import { readFileSync } from "node:fs";
import { figures } from "../../../scripts/build-pages.mjs";
import * as fees from "../../../lib/fees.js";

const ROOT = new URL("../../../", import.meta.url);
const json = (p) => JSON.parse(readFileSync(new URL(p, ROOT), "utf8"));

/** The site's figures with charts.price and charts.size added for the film. */
export function filmFigures() {
  const rc = json("ratecard.json"), mc = json("data/montecarlo.json"), cs = json("data/case-study.json");
  const built = figures(rc, mc, cs);
  const priced = cs.priced_on, nonPeak = fees.cardNamed(rc, "non_peak");
  const [plo, phi] = rc.fba.price_band_edges, oz = cs.listing.item_weight_oz, mid = (plo + phi) / 2;
  const price = {
    edges: [plo, phi],
    fees: [plo - 0.01, mid, phi + 0.01].map((p) => fees.fulfilmentFee(rc, cs.listing.tier, oz, p, priced, nonPeak)),
    band: cs.listing.price_band === `$${plo} to $${phi}` ? 1 : null,
  };
  const size = { tiers: ["small_standard", "large_standard"].map((t) => [t, fees.fulfilmentFee(rc, t, oz, mid, priced, nonPeak)]), tier: cs.listing.tier };
  // the listing sits on each panel at its own fee, the one the site's staircase draws: if the card or the
  // case study changes and they disagree, stop rather than draw a panel the case study does not support
  const own = built.charts.stairs.listing.fee;
  const onBand = price.band == null ? own : price.fees[price.band];
  const onTier = (size.tiers.find(([t]) => t === size.tier) || [])[1];
  if (Math.abs(onBand - own) > 1e-3 || Math.abs(onTier - own) > 1e-3) {
    throw new Error("the price and size panels do not agree with the case study's fee; re-run scripts/case-study.mjs");
  }
  return { ...built, charts: { ...built.charts, price, size } };
}
