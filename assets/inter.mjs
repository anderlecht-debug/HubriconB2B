/* ============================================================================
   Inter's measurements, so text is placed by measurement, never by guessing.

   Advance widths per mille of the font size, for printable ASCII and a few
   more, read from the font files (2026-10-19):
   - the text cut (opsz 14): Inter 4, Regular and SemiBold;
   - the display cut (opsz 32): film/fonts/InterDisplay-*.ttf, Inter 4.1.
   The site loads Inter with its optical-size axis, so the browser draws text
   between 14px and 32px in a cut between the two; widths are interpolated the
   same way. A film is set in the display cut only (every film text is 40px+).
   Kerning is ignored: a few hundredths of an em, never enough to collide.
   ============================================================================ */

const TEXT = {
  400: [281,288,466,633,642,982,644,300,365,365,501,662,288,460,288,360,631,407,610,618,646,593,620,566,619,620,288,302,662,662,662,511,966,690,654,730,722,601,590,746,743,269,571,672,565,903,753,765,639,765,644,642,646,744,690,985,682,679,629,365,360,365,471,456,323,562,612,571,612,583,370,613,591,242,242,549,242,876,591,600,612,612,376,528,327,591,562,818,546,562,552,426,333,426,662],
  600: [252,321,523,644,650,1004,663,326,373,373,540,673,319,465,319,379,660,423,623,636,666,612,640,576,640,640,319,329,673,673,673,543,999,728,659,737,722,605,588,749,746,277,580,703,565,922,759,769,645,773,652,650,660,736,728,1020,720,713,652,373,379,373,481,469,351,574,624,583,624,591,389,625,612,262,262,569,262,900,612,609,624,624,397,549,353,612,587,839,569,588,566,455,359,455,673],
};
const DISPLAY = {
  400: [250,220,403,600,614,844,608,254,299,299,469,628,220,429,220,325,613,362,561,599,618,577,584,516,582,584,220,223,628,628,628,524,974,653,638,722,689,580,554,730,708,232,535,634,535,857,710,749,612,749,632,614,610,703,653,949,646,643,613,299,325,299,438,454,241,518,565,523,565,536,306,565,547,206,206,507,206,839,547,549,565,565,322,475,311,547,512,752,507,512,479,385,296,385,628],
  600: [226,238,449,617,640,906,634,266,321,321,513,646,236,439,236,351,638,380,586,613,644,592,606,539,604,606,236,239,646,646,646,553,996,693,643,725,697,599,572,734,715,250,553,668,550,882,720,748,625,748,644,640,627,704,688,981,680,674,627,321,351,321,455,468,277,541,587,544,587,553,349,587,573,232,233,536,232,869,573,570,587,587,356,505,350,573,540,796,527,540,508,421,330,421,646],
};
const EXTRA_TEXT = { 400: { "−": 662, "–": 500, "—": 1000, "·": 288, "×": 662, "£": 640, "€": 650, "…": 900 }, 600: { "−": 673, "–": 500, "—": 1000, "·": 319, "×": 673, "£": 650, "€": 660, "…": 920 } };
const EXTRA_DISPLAY = { 400: { "−": 628, "–": 500, "—": 1000, "·": 220, "×": 628, "£": 582, "€": 634, "…": 659 }, 600: { "−": 646, "–": 500, "—": 1000, "·": 236, "×": 646, "£": 601, "€": 652, "…": 709 } };
const TNUM = { text: 648, display: 645 };

/** Inter's capital height, as a share of the font size (both cuts). */
export const CAP = 1490 / 2048;

/** How far along the optical-size axis the browser draws text at this size: 0 text, 1 display. */
export const displayShare = (px) => Math.min(1, Math.max(0, (px - 14) / (32 - 14)));

/** One character's advance in px. `cut`: "auto" (by size, as the site does), "text" or "display". */
export function glyphWidth(ch, px, weight = 400, { tabular = false, cut = "auto" } = {}) {
  const w = weight >= 600 ? 600 : 400;
  const t = cut === "display" ? 1 : cut === "text" ? 0 : displayShare(px);
  const c = ch.codePointAt(0);
  const one = (table, extra, tn) => (tabular && c >= 48 && c <= 57 ? tn : c >= 32 && c <= 126 ? table[w][c - 32] : extra[w][ch] ?? 620);
  const a = one(TEXT, EXTRA_TEXT, TNUM.text), b = one(DISPLAY, EXTRA_DISPLAY, TNUM.display);
  return ((a + (b - a) * t) / 1000) * px;
}

/** The rendered width of a string in px. */
export function textWidth(s, px, weight = 400, tabular = false, cut = "auto") {
  let sum = 0;
  for (const ch of String(s)) sum += glyphWidth(ch, px, weight, { tabular, cut });
  return sum;
}
