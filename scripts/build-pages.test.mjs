// The baked pages, as built: current with their data, the home page short and inside the
// Hormozi standard with one action, every section it gave up on the page under its tab,
// the attribution rules identical wherever they appear, and every page honest about what
// its figures are.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { figures, build, mainWords, PAGES } from "./build-pages.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const html = read("index.html");
const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
const text = (h) => h.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
const section = (h, id) => (h.match(new RegExp(`<section[^>]*\\bid="${id}"[\\s\\S]*?</section>`)) || [""])[0];
// The pages behind the tabs (HUBRICON_SPEC.md, "A short first page", 2026-10-01 evening)
const TAB_PAGES = { "/case-study": "case-study.html", "/how-it-works": "how-it-works.html", "/offer": "offer.html" };
// The home page's own words, capped: the founder asked for a short first page. Set at the first
// build's count plus a tenth; raising it is a decision about the page, not a fix for a test.
const HOME_WORDS_MAX = 435;

for (const page of PAGES) {
  test(`${page.file} is current with its data (node scripts/build-pages.mjs)`, () => {
    const before = read(page.file);
    assert.equal(build(before, built, { requireAllFills: page.requireAllFills, name: page.file }), before);
  });
}

test("the short first page: five bands, and every other section on the page under its tab", () => {
  // The founder, 2026-10-01 evening: "a short first page, not a lot of scrolling … all the other
  // information about the business on the tabs." The spec's sections are kept, not cut: moved.
  assert.match(html, /<section class="hero"/, "1 · the hero");
  const order = [...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(([, id]) => id).filter((id) => id !== "result");
  assert.deepEqual(order, ["proof", "offer", "learn", "book"], "the promise, the proof, the offer, the library, the call");
  const words = mainWords(html);
  assert.ok(words <= HOME_WORDS_MAX, `the home page's own words: ${words}, capped at ${HOME_WORDS_MAX}`);
  assert.doesNotMatch(html, /<figure class="exhibit"/, "no exhibit on the home page: the proof's figures are on /case-study");
  assert.equal((html.match(/<svg class="chart /g) || []).length, 2, "one chart, the hero's mood, in its wide and narrow frames");
  const how = read("how-it-works.html"), offer = read("offer.html"), cs = read("case-study.html");
  for (const id of ["steps", "record", "who", "faq"]) assert.ok(section(how, id), `/how-it-works has #${id}`);
  assert.match(how, /"@type": "FAQPage"/, "the questions carry their structured data where they are");
  assert.equal((section(offer, "offer").match(/<div class="layer"/g) || []).length, 4, "/offer carries the guarantee's four layers");
  assert.match(offer, /id="guarantee"[^>]*>The guarantee, in four layers</);
  assert.ok(section(offer, "trust"), "/offer has where every promise is written down");
  for (const id of ["customers", "slipping", "demand", "method", "problem", "staircase", "case-study"]) assert.ok(section(cs, id), `/case-study has #${id}`);
  assert.doesNotMatch(html, /<div class="layer"/, "the four layers live one click away, never above the call (spec §6)");
  assert.match(section(html, "offer"), /href="\/offer"[^>]*>The guarantee, in four layers/, "and the offer links to them");
});

test("one action: every button says the same thing and goes to the same place", () => {
  const SOURCES = /^https:\/\/(archive\.ics\.uci\.edu\/dataset\/502\/online\+retail\+ii|doi\.org\/10\.24432\/C5CG6D)$/;   // the store study's data, cited
  for (const file of ["index.html", ...Object.values(TAB_PAGES)]) {
    const h = read(file);
    const ctas = [...h.matchAll(/<a\b[^>]*data-cta="[^"]+"[^>]*>([\s\S]*?)<\/a>/g)];
    assert.ok(ctas.length >= 2, `${file}: the call to action repeats`);
    for (const [tag, inner] of ctas) {
      assert.match(tag, /href="\/apply"/);
      assert.equal(inner.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim(), "Book your call →");
    }
    for (const [tag] of h.matchAll(/<a\b[^>]*class="btn[^"]*"[^>]*>/g)) assert.match(tag, /href="\/apply"/, `${file}: only the call is a button`);
    const otherLinks = [...h.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map(([, x]) => x).filter((x) => x !== "/apply");
    for (const x of otherLinks) {
      if (file === "case-study.html" && SOURCES.test(x)) continue;
      assert.match(x, /^\/(#[a-z-]+|learn(\/[a-z-]+(#[a-z-]+)?|\/files\/[a-z-]+\.xlsx)?|honesty|your-data|verify|manifesto|case-study(#[a-z-]+)?|how-it-works(#[a-z-]+)?|offer(#[a-z-]+)?|privacy(#[a-z-]+)?|terms(#[a-z-]+)?)?$/, `${file}: ${x}: every other link is the site's own page, a section of one, or a free course`);
    }
  }
  // The bar's tabs (the founder, 2026-10-01: "we are mimicking Apple's .com with the education tab"):
  // each one a page. No Results tab until a client's consent fills one (the founder, the same evening).
  const tabs = html.match(/<nav class="nav-tabs"[\s\S]*?<\/nav>/)[0];
  assert.deepEqual([...tabs.matchAll(/<a class="nav-tab" href="[^"]+"[^>]*>([^<]+)/g)].map(([, t]) => t), ["Proof", "How it works", "The offer", "Education", "Trust"]);
  assert.doesNotMatch(tabs, />Results</);
  assert.doesNotMatch(tabs, /class="btn/);
  for (const [path, file] of Object.entries(TAB_PAGES)) {
    assert.match(tabs, new RegExp(`<a class="nav-tab" href="${path}"`), `the tab for ${path}`);
    assert.ok(read(file).includes("<main>"), `${path} is a page`);
  }
  assert.match(tabs, /href="\/learn"[^>]*>Education/);
  // no redirect may stand in front of a page the build writes (Vercel runs redirects first)
  const sources = new Set(JSON.parse(read("vercel.json")).redirects.map((r) => r.source));
  for (const page of PAGES) {
    const url = "/" + page.file.replace(/(^|\/)index\.html$/, "").replace(/\.html$/, "");
    assert.ok(!sources.has(url.replace(/\/$/, "") || "/"), `${url}: a redirect would hide this page`);
  }
});

test("the call repeats after each proof block, the same words and the same colour", () => {
  // HUBRICON_SPEC.md, "Global rules for the page": after the proof, the offer and the Record, and at the close.
  const where = (file) => [...read(file).matchAll(/<a\b[^>]*data-cta="([^"]+)"/g)].map(([, w]) => w);
  for (const w of ["hero", "proof", "offer", "close"]) assert.ok(where("index.html").includes(w), `home: a call at ${w}`);
  for (const w of ["case-study", "listing"]) assert.ok(where("case-study.html").includes(w), `/case-study: a call at ${w}`);
  for (const w of ["record", "how"]) assert.ok(where("how-it-works.html").includes(w), `/how-it-works: a call at ${w}`);
  assert.ok(where("offer.html").includes("offer"), "/offer: a call after the guarantee");
  for (const [file, id] of [["index.html", "proof"], ["index.html", "offer"], ["how-it-works.html", "record"], ["offer.html", "offer"], ["case-study.html", "method"]]) {
    assert.match(section(read(file), id), /<a class="btn btn-lg" href="\/apply"/, `${file} #${id} ends on the call`);
  }
});

test("the home page has no form; the course's optional email lives on /learn, and looks like the field's, not the call's", () => {
  // Every lesson is open (the founder's call, 2026-10-01), and the home page is short (the same
  // evening): the opt-in is on /learn's featured course and on each course, never on the home page.
  assert.doesNotMatch(html, /<form\b/, "no form on the home page: the call is the only thing it asks for");
  const hub = read("learn/index.html");
  const forms = [...hub.matchAll(/<form\b[\s\S]*?<\/form>/g)].map(([f]) => f);
  assert.equal(forms.length, 1, "one form on /learn");
  const f = forms[0];
  assert.match(f, /data-join="fee-staircase"/);
  assert.deepEqual([...f.matchAll(/<input\b[^>]*name="([^"]+)"/g)].map(([, n]) => n), ["email", "website"], "the address, and the field bots fill");
  assert.doesNotMatch(f, /class="btn/, "the submit is not styled as the call");
  assert.match(f, /href="\/privacy#learn"/);
  assert.match(f, /One click unsubscribes/);
  assert.match(f, /No email is needed to read it/);
  assert.match(f, /Optional/);
  assert.match(hub, /<a class="go-to" href="\/learn\/fee-staircase#staircase">Start lesson 1, no email needed/, "the card opens lesson 1 itself");
  const js = read("assets/site.js");
  assert.match(js, /fetch\("\/api\/learn"/);
  assert.match(js, /email, course: form\.dataset\.join, website: form\.website\.value, source:/, "it sends what the course page sends, nothing more");
  assert.doesNotMatch(js, /location\.href\s*=/, "the reader stays where they are");
  assert.match(js, /body\.emailed\)/, "it says an email was sent only when the server says it was");
});

test("the proof has its own page, the home page states its calls as the page does; the sitemap and robots name the public site", () => {
  const home = read("index.html"), page = read("case-study.html");
  // every call the home page states is the same figure, worded the same, on /case-study
  for (const [, key, val] of section(home, "proof").matchAll(/data-fill="(store_[a-z_]+)"[^>]*>([^<]*)</g)) {
    assert.match(page, new RegExp(`data-fill="${key}"[^>]*>${val.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}<`), `${key} reads "${val}" on /case-study too`);
  }
  assert.match(section(home, "proof"), /href="\/case-study"/, "the proof links to the whole study");
  const map = read("sitemap.xml");
  for (const p of ["/", "/case-study", "/how-it-works", "/offer", "/learn", "/learn/capital-and-cash", "/verify", "/manifesto"]) assert.ok(map.includes(`<loc>https://www.hubricon.com${p}</loc>`), `sitemap: ${p}`);
  for (const p of ["/portal", "/apply", "/call", "/intake", "/welcome"]) assert.ok(!map.includes(`hubricon.com${p}<`), `sitemap leaves out ${p}`);
  const robots = read("robots.txt");
  assert.match(robots, /Sitemap: https:\/\/www\.hubricon\.com\/sitemap\.xml/);
  assert.match(robots, /Disallow: \/portal/);
  assert.match(read(".vercelignore"), /^hagen\.jpg$/m, "the founder is off camera");
});

test("every chart a reader studies can be scrubbed, and asking for less motion gets a dissolve, not nothing", () => {
  // The founder, 2026-10-01: "the animations still need to actually be animated … making the site more interactive"
  const charts = (page) => [...read(page).matchAll(/<svg class="chart ([a-z]+)[^"]*"[^>]*>/g)];
  for (const page of ["index.html", "case-study.html", "learn/fee-staircase.html", "learn/price-curve.html", "learn/capital-and-cash.html"]) {
    for (const [tag, kind] of charts(page)) {
      if (/mc--mood|aging|strip|chart order/.test(tag)) continue;   // the hero's mood, the age bands and the labelled bars carry no values to read
      const m = tag.match(/data-scrub="([^"]+)"/);
      assert.ok(m, `${page}: a ${kind} chart without a readout`);
      const data = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, "&"));
      assert.ok(data.p.length > 3 && data.p.every(([x, ys, lines]) => Number.isFinite(x) && ys.length && lines.length), `${page}: ${kind} readout`);
    }
  }
  const js = read("assets/site.js"), css = read("assets/hubricon.css");
  assert.match(js, /svg\.chart\[data-scrub\]/);
  assert.match(read("scripts/site-blocks.mjs"), /prefers-reduced-motion: reduce\)"\)\.matches\) \{ d\.classList\.add\("calm"\)/);
  assert.match(css, /\.calm \.armed\[data-reveal\] \{ opacity: 0; transform: none;/);
  assert.match(js, /if \(calm && !el\.hasAttribute\("data-reveal"\)\) return;/, "charts and numbers keep their finished frame when motion is reduced");
});

test("nothing is blank for want of a scroll: only an armed element or the hero's chart starts hidden", () => {
  // HUBRICON_SPEC.md, the Monte Carlo's contract: before it fires, show the finished still frame.
  const css = read("assets/hubricon.css");
  for (const rule of css.match(/[^{}]+\{[^}]*(opacity:\s*0(?![.\d])|stroke-dashoffset:\s*1(?![.\d])|scaleX\(0\))[^}]*\}/g) || []) {
    const sel = rule.slice(0, rule.indexOf("{"));
    if (/@keyframes|^\s*(from|to)\b/.test(sel) || /nav|fly|sheet|scrim|motion \.nav|drop input/.test(sel)) continue;
    assert.match(sel, /\.armed|data-play="load"/, `"${sel.trim()}" hides content without being armed`);
  }
  assert.match(html, /<figure class="figure" data-play="load">/, "the hero's chart draws as the page opens");
  assert.equal((html.match(/data-play="load"/g) || []).length, 1);
});

test("the case studies say what they are on their own screens", () => {
  assert.match(section(html, "proof"), /Modeled on published data · Not a client · Not a result/, "the home page's proof");
  const cs = read("case-study.html");
  assert.match(cs.slice(cs.indexOf("<main>"), cs.indexOf('id="customers"')), /Modeled on published data · Not a client · Not a result/, "the store study's head");
  for (const [f] of cs.matchAll(/<figure class="exhibit"[\s\S]*?<\/figure>/g)) assert.match(f, /class="label-box"/, "every exhibit carries its label");
  const listing = section(cs, "case-study");
  assert.match(listing, /Modeled from public data · Not a client · Not a result/);
  assert.match(listing, /class="est">estimate</);
  // the store study cites its source as the licence asks, and says what it cannot show
  assert.match(cs, /CC BY 4\.0/);
  assert.match(cs, /doi\.org\/10\.24432\/C5CG6D/);
  assert.match(text(section(cs, "method")), /What this cannot show: profit/);
  assert.match(text(section(cs, "demand")), /the ranges were too narrow, and we say so/, "a miss is said where it happened");
});

test("nothing from the retired funnel or the retired look", () => {
  for (const page of ["index.html", "case-study.html", "how-it-works.html", "offer.html", "apply.html", "honesty.html", "your-data.html", "portal.html", "intake.html", "welcome.html", "learn/index.html", "learn/fee-staircase.html", "learn/price-curve.html", "manifesto.html", "verify.html"]) {
    const h = read(page);
    for (const gone of ["Teardown", "Anton", "Fraunces", "Iowan", "#FFC000", "Demo data", "Start your free Proving Month"]) {
      assert.ok(!h.includes(gone), `"${gone}" is still on ${page}`);
    }
  }
});

test("no page on the design system keeps a palette of its own", () => {
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "portal.html", "terms.html", "privacy.html", "intake.html", "welcome.html", "learn/index.html", "learn/fee-staircase.html", "call.html", "learn/price-curve.html", "manifesto.html", "verify.html"]) {
    const style = read(page).match(/<style>([\s\S]*?)<\/style>/)[1];
    assert.doesNotMatch(style, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, `${page}: colours belong in /assets/hubricon.css`);
    assert.match(read(page), /href="\/assets\/hubricon\.css"/);
  }
});

test("the terms and /honesty carry the attribution rules word for word", () => {
  const block = text(read("scripts/blocks/attribution.html"));
  for (const page of ["terms.html", "honesty.html", "portal.html"]) assert.ok(text(read(page)).includes(block), `${page} has drifted`);
});

test("the rules claim only the guards the engine enforces", () => {
  const block = text(read("scripts/blocks/attribution.html"));
  // measurement.py enforces the cap, the $25 floor and one dollar, one move; monthly.py re-measures
  // every move on each month's own exports, which is what makes "it has to last" a rule.
  assert.match(block, /Four rules apply to every dollar/);
  assert.match(block, /Nothing under \$25/);
  assert.match(block, /It has to last/);
  const engine = read("engine/src/hubricon_engine/measurement.py");
  assert.match(engine, /^MEASURE_MIN_USD = 25\.0/m);
  assert.match(engine, /^MEASUREMENT_HORIZON_DAYS = 30/m);
  assert.match(read("engine/src/hubricon_engine/monthly.py"), /^def measure_month\(/m);
});

test("/honesty says there are no client results before it says anything else", () => {
  const h = read("honesty.html");
  const firstHeading = h.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)[1];
  assert.equal(firstHeading.trim(), "No client results yet.");
  const silent = json("data/case-study.json").selection;
  assert.ok(text(h).includes(`${silent.brands_silent.toLocaleString("en-US")} of ${silent.brands_modeled.toLocaleString("en-US")}`));
});
