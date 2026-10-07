// The photographs kind (v3): the layout promises a designer can break without seeing it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { archive, still, split, companion } from "./photos.mjs";

const num = (html, re) => +(html.match(re) || [])[1];
const printBox = (html) => ({
  w: num(html, /class="ph-print[^"]*" style="width:([\d.]+)px/),
  h: num(html, /class="ph-print[^"]*" style="width:[\d.]+px;height:([\d.]+)px/),
  left: num(html, /class="ph-place" style="left:([\d.-]+)px/),
});
const GUIDEBOOK = "Sears, Roebuck and Co., A Visit to Sears, Roebuck and Co. (1914)";

test("a long credit never shrinks a print into a corner (c24b)", () => {
  const job = { id: "c24b", kind: "archive", seconds: 4.2, words: [], params: {},
    asset: { url: "x.jpg", w: 1700, h: 1680, date: "1914", place: "Chicago", credit: GUIDEBOOK } };
  const b = printBox(archive(job));
  assert.ok(b.h >= 640, `print ${b.h} px tall`);
  assert.ok(Math.abs(b.left + b.w / 2 - 990) < 80, `print centred at ${b.left + b.w / 2}`);
});

test("a portrait print is never left at under 60% of the frame, and opens in close", () => {
  const job = { id: "e22b", kind: "archive", seconds: 4.5, words: [], params: {},
    asset: { url: "x.jpg", w: 1027, h: 1640, date: "1920" } };
  const html = archive(job);
  assert.ok(printBox(html).h >= 0.6 * 1080);
  assert.match(html, /@keyframes ph-in-e22b\{0%\{transform:translate\([^)]*\) rotateX\([^)]*\) scale\(1\.[3-9]/);
});

test("a print cut after a page opens at a second scale; a printed page never opens in close", () => {
  const base = { kind: "archive", seconds: 6, words: [], params: {}, prev_kind: "document" };
  const photo = archive({ ...base, id: "b21", asset: { url: "x.jpg", w: 2400, h: 1800, date: "1906" } });
  const page = archive({ ...base, id: "e04b", asset: { url: "x.jpg", w: 2400, h: 1800, date: "1917", title: "Electrical goods, catalogue 134, page 766" } });
  assert.match(photo, /0%\{transform:translate\([^)]*\) rotateX\([^)]*\) scale\(1\.[2-9]/);
  assert.match(page, /0%\{transform:translate\(0px,0px\) rotateX\([^)]*\) scale\(1\)/);
});

test("a world still says when it was made, and a modern photograph keeps saying it", () => {
  const job = (asset, params = {}) => ({ id: "w", kind: "still", seconds: 5.6, words: [], params, asset: { url: "x.jpg", w: 3840, h: 2600, ...asset } });
  const modern = still(job({ date: "2000", credit: "Wikimedia Commons" }, { enter: "dive" }));
  assert.match(modern, /<p class="source">Photographed in 2000<\/p>/);
  assert.match(modern, /--out:99s/);                                 // held to the cut
  const old = still(job({ date: "c. 1914", place: "United States of America", credit: "Smithsonian Institution, National Postal Museum" }));
  assert.match(old, /<p class="source">c\. 1914 — Smithsonian National Postal Museum<\/p>/);
  const fromTitle = still(job({ date: null, title: "Sears, Roebuck and Company, Merchandise Packers, circa 1920 - Advertising Postcard" }));
  assert.match(fromTitle, /<p class="source">c\. 1920<\/p>/);
  assert.doesNotMatch(still(job({ date: null, title: "Long Lake Farmers Ship Live Poultry" })), /class="labels"/);   // no year is ever guessed
});

test("then and now: two prints of one size, filling the frame, captions inside title-safe", () => {
  const job = { id: "a07", kind: "split", seconds: 6, words: [{ w: "descendants", t: 1.1 }], params: { right: {} },
    asset: { url: "x.jpg", w: 2711, h: 2033, date: "c. 1914" } };
  const html = split(job);
  const then = printBox(html);
  const now = { w: num(html, /class="ph-now" style="left:[\d.]+px;top:[\d.]+px;width:([\d.]+)px/), h: num(html, /class="ph-now" style="[^"]*height:([\d.]+)px/) };
  assert.equal(then.w, now.w); assert.equal(then.h, now.h);
  assert.ok(then.h >= 560, `prints ${then.h} px tall`);
  assert.match(html, /<p>c\. 1914<\/p>/);
  for (const m of html.matchAll(/class="ph-cap" style="left:([\d.]+)px;top:([\d.]+)px/g)) assert.ok(+m[1] >= 160 && +m[2] >= 90);
});

test("a panorama companion print is a crop of itself, never a thin strip", () => {
  const html = companion({ id: "a06", seconds: 10, print: { url: "x.jpg", w: 1878, h: 664, focus: [0.5, 0.62] } });
  const b = printBox(html);
  assert.ok(b.w / b.h <= 1.75 && b.h >= 400, `print ${b.w}×${b.h}`);
});

test("a museum object on black lies on the desk itself: no print, its ground lightened away, large", () => {
  const job = { id: "e18", kind: "archive", seconds: 4.1, words: [], params: {},
    asset: { url: "x.jpg", w: 1941, h: 1770, date: "c. 1914", credit: "Smithsonian Institution, National Postal Museum",
      title: "Parcel post rate indicator", ground: { luma: 0, sd: 0, box: [0.21, 0.365, 0.79, 0.628] } } };
  const html = archive(job);
  assert.doesNotMatch(html, /ph-print/);
  assert.match(html, /ph-ob-lighten/);
  const w = num(html, /class="ph-ob-img[^"]*" src="x.jpg" style="left:[\d.-]+px;top:[\d.-]+px;width:([\d.]+)px/);
  assert.ok(w * 0.58 >= 0.6 * 1920 || w * (1770 / 1941) * 0.263 >= 0.5 * 1080, `object ${Math.round(w * 0.58)} px wide`);
  // a photograph of a scene on a dark ground stays a print; `treat: "print"` keeps one too
  assert.match(archive({ ...job, asset: { ...job.asset, title: "Photograph of a carrier", credit: "Wikimedia Commons", ground: { luma: 35, sd: 8, box: [0.3, 0.1, 0.7, 0.6] } } }), /ph-print/);
  assert.match(archive({ ...job, params: { treat: "print" } }), /ph-print/);
});

test("a white seamless object is darkened into the lamp's pool; an unspoken figure on it is soft", () => {
  const html = companion({ id: "d11b", seconds: 8, print: { url: "x.jpg", w: 2000, h: 2872, credit: "Smithsonian Institution, National Postal Museum",
    title: "Triner postal scale", ground: { luma: 237, sd: 6, box: [0.06, 0.11, 0.9, 0.95] }, at: 3.5, soft: [[0.3, 0.3, 0.5, 0.4]] } });
  assert.match(html, /ph-ob-darken/);
  assert.match(html, /ph-ob-lit/);
  assert.match(html, /class="ph-ob-soft"/);
  assert.match(html, /ph-ob-in 0\.7s cubic-bezier\([^)]*\) 3\.25s/);   // lands on its word
});

test("a print ends pushed into its focus, and a catalogue page is lit only on its line", () => {
  const job = { id: "e05", kind: "archive", seconds: 3.9, prev_kind: "archive", params: { band: [0.735, 0.775] }, focus: [0.4, 0.74],
    words: [["And", 0.22], ["next", 0.42], ["every", 0.82], ["item", 1.08], ["catalogue,", 1.76], ["shipping", 2.9], ["weight.", 3.24]].map(([w, t]) => ({ w, t })),
    asset: { url: "x.jpg", w: 869, h: 720, date: "1917", title: "Electrical goods, catalogue 134: an item" } };
  const html = archive(job);
  const last = [...html.matchAll(/scale\(([\d.]+)\)/g)].map((m) => +m[1]).at(-1);
  assert.ok(last >= 1.8, `ends at ${last}`);
  assert.match(html, /class="ph-lamp-soft"/);
  assert.match(html, /class="ph-lamp" style="--b0:/);
});

test("a label never prints over a lit map; the trim may isolate one panel of a collage", () => {
  const map = still({ id: "d05b", kind: "still", seconds: 4.5, words: [], params: { enter: "dive", exit: "surface" },
    asset: { url: "x.jpg", w: 2846, h: 1876, date: "1913", title: "Official Parcel Post map", credit: "Smithsonian Institution, National Postal Museum" } });
  assert.match(map, /ph-scrim" style="background:linear-gradient\(to top, color-mix\(in srgb, var\(--ground\) 96%/);
  const c11 = still({ id: "c11", kind: "still", seconds: 5.8, words: [], params: { trim: [0.08, 0.38, 0.43, 0] }, asset: { url: "x.jpg", w: 2164, h: 1302 } });
  assert.match(c11, /object-view-box:inset\(8% 38% 43% 0%\)/);
});
