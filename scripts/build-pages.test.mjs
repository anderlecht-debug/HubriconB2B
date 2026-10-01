// The baked pages, as built: current with their data, the home page inside the
// Hormozi standard with one action, the attribution rules identical wherever they
// appear, and every page honest about what its figures are.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { figures, build, visibleWords, PAGES } from "./build-pages.mjs";

const root = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, root), "utf8");
const json = (p) => JSON.parse(read(p));
const html = read("index.html");
const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
const text = (h) => h.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

for (const page of PAGES) {
  test(`${page.file} is current with its data (node scripts/build-pages.mjs)`, () => {
    const before = read(page.file);
    assert.equal(build(before, built, { requireAllFills: page.requireAllFills, name: page.file }), before);
  });
}

test("the spec's ten sections in the spec's order, with the founder's additions in theirs", () => {
  // HUBRICON_SPEC.md, "Landing page, section by section", and its amendments of 2026-10-01:
  // the founder added the trust section, the results wall and the education library
  // ("everything needs to be on that landing page") and retired the 900-word cap.
  assert.match(html, /<section class="hero"/, "1 · the hero");
  const order = [...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(([, id]) => id).filter((id) => id !== "result");
  assert.deepEqual(order, ["problem", "staircase", "case-study", "how", "offer", "trust", "scoreboard", "results", "learn", "who", "faq", "book"]);
  const spec = ["problem", "staircase", "case-study", "how", "offer", "scoreboard", "who", "faq", "book"];
  assert.deepEqual(order.filter((id) => spec.includes(id)), spec, "the spec's own sections never move");
  assert.ok(html.indexOf("The guarantee, in four layers") > html.indexOf('id="offer"'), "the four guarantee layers live in the offer, never above it (spec §6)");
  assert.ok(visibleWords(html) > 0);
});

test("one action: every button says the same thing and goes to the same place", () => {
  const ctas = [...html.matchAll(/<a\b[^>]*data-cta="[^"]+"[^>]*>([\s\S]*?)<\/a>/g)];
  assert.ok(ctas.length >= 3, "the call to action repeats after each proof block");
  for (const [tag, inner] of ctas) {
    assert.match(tag, /href="\/apply"/);
    assert.equal(inner.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim(), "Book your call →");
  }
  for (const [tag] of html.matchAll(/<a\b[^>]*class="btn[^"]*"[^>]*>/g)) assert.match(tag, /href="\/apply"/, "only the call is a button");
  const otherLinks = [...html.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map(([, h]) => h).filter((h) => h !== "/apply");
  for (const h of otherLinks) assert.match(h, /^\/(#[a-z-]+|learn(\/[a-z-]+(#[a-z-]+)?|\/files\/[a-z-]+\.xlsx)?|honesty|your-data|verify|manifesto|case-study|privacy(#[a-z-]+)?|terms(#[a-z-]+)?)?$/, `${h}: every other link is the site's own page, a section of this one, or a free course`);
  // Since 2026-10-01 the bar has tabs (the founder: "we are mimicking Apple's .com with the
  // education tab"); none of them is a button, and none of them sells anything but the call.
  const tabs = html.match(/<nav class="nav-tabs"[\s\S]*?<\/nav>/)[0];
  for (const t of ["Proof", "How it works", "The offer", "Results", "Education", "Trust"]) assert.match(tabs, new RegExp(`>${t}<`), `the ${t} tab`);
  assert.match(tabs, /href="\/learn"[^>]*>Education/);
  assert.doesNotMatch(tabs, /class="btn/);
  for (const id of ["case-study", "how", "offer", "results", "trust"]) assert.match(html, new RegExp(`<section[^>]*id="${id}"`), `the #${id} tab has a section to land on`);
});

test("the call repeats after each proof block, the same words and the same colour", () => {
  // HUBRICON_SPEC.md, "Global rules for the page": after the case study, the offer and the Record, and at the close.
  const where = [...html.matchAll(/<a\b[^>]*data-cta="([^"]+)"/g)].map(([, w]) => w);
  for (const w of ["hero", "case-study", "offer", "record", "close"]) assert.ok(where.includes(w), `a call at ${w}`);
  for (const id of ["case-study", "offer", "scoreboard"]) {
    const sect = html.match(new RegExp(`<section[^>]*id="${id}"[\\s\\S]*?</section>`))[0];
    assert.match(sect, /<a class="btn btn-lg" href="\/apply"/, `#${id} ends on the call`);
  }
});

test("the only other control is the course's optional email, and it looks like the field's, not the call's", () => {
  // Every lesson is open (the founder's call, 2026-10-01): the card opens lesson 1 with no email,
  // and the email is the opt-in for the link, the spreadsheet and the fee-change notes.
  const forms = [...html.matchAll(/<form\b[\s\S]*?<\/form>/g)].map(([f]) => f);
  assert.equal(forms.length, 1, "one form on the page");
  const f = forms[0];
  assert.match(f, /data-join="fee-staircase"/);
  assert.deepEqual([...f.matchAll(/<input\b[^>]*name="([^"]+)"/g)].map(([, n]) => n), ["email", "website"], "the address, and the field bots fill");
  assert.doesNotMatch(f, /class="btn/, "the submit is not styled as the call");
  assert.match(f, /href="\/privacy#learn"/);
  assert.match(f, /One click unsubscribes/);
  assert.match(f, /No email is needed to read it/);
  assert.match(f, /Optional/);
  const learnSection = html.match(/<section[^>]*id="learn"[\s\S]*?<\/section>/)[0];
  assert.ok(learnSection.includes(f), "it sits in the Education section, on the featured course");
  assert.match(learnSection, /<a class="go-to" href="\/learn\/fee-staircase#staircase">Start lesson 1, no email needed/, "the card opens lesson 1 itself");
  assert.doesNotMatch(text(learnSection), /one email (opens|to enter)|email opens|for an email/i);
  const js = read("assets/site.js");
  assert.match(js, /fetch\("\/api\/learn"/);
  assert.match(js, /email, course: form\.dataset\.join, website: form\.website\.value, source:/, "it sends what the course page sends, nothing more");
  assert.doesNotMatch(js, /location\.href\s*=/, "the reader stays where they are");
  assert.match(js, /body\.emailed\)/, "it says an email was sent only when the server says it was");
});

test("the case study has its own page, the home page's own sections; the sitemap and robots name the public site", () => {
  const home = read("index.html"), page = read("case-study.html");
  for (const id of ["staircase", "case-study"]) {
    const sec = (h) => h.match(new RegExp(`<section class="section" id="${id}">[\\s\\S]*?\\n</section>`))[0];
    assert.equal(sec(page), sec(home), `/case-study's #${id} is the home page's, as built`);
  }
  const map = read("sitemap.xml");
  for (const p of ["/", "/case-study", "/learn", "/learn/capital-and-cash", "/verify", "/manifesto"]) assert.ok(map.includes(`<loc>https://www.hubricon.com${p}</loc>`), `sitemap: ${p}`);
  for (const p of ["/portal", "/apply", "/call", "/intake", "/welcome"]) assert.ok(!map.includes(`hubricon.com${p}<`), `sitemap leaves out ${p}`);
  const robots = read("robots.txt");
  assert.match(robots, /Sitemap: https:\/\/www\.hubricon\.com\/sitemap\.xml/);
  assert.match(robots, /Disallow: \/portal/);
  assert.match(read(".vercelignore"), /^hagen\.jpg$/m, "the founder is off camera");
});

test("every chart a reader studies can be scrubbed, and asking for less motion gets a dissolve, not nothing", () => {
  // The founder, 2026-10-01: "the animations still need to actually be animated … making the site more interactive"
  const charts = (page) => [...read(page).matchAll(/<svg class="chart ([a-z]+)[^"]*"[^>]*>/g)];
  for (const page of ["index.html", "learn/fee-staircase.html", "learn/price-curve.html", "learn/capital-and-cash.html"]) {
    for (const [tag, kind] of charts(page)) {
      if (/mc--mood|aging|strip/.test(tag)) continue;   // the hero's mood and the age bands carry no values to read
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

test("the case study says what it is on its own screen", () => {
  const cs = html.match(/<section[^>]*id="case-study"[\s\S]*?<\/section>/)[0];
  assert.match(cs, /Modeled from public data · Not a client · Not a result/);
  assert.match(cs, /class="est">estimate</);
});

test("nothing from the retired funnel or the retired look", () => {
  for (const page of ["index.html", "apply.html", "honesty.html", "your-data.html", "portal.html", "intake.html", "welcome.html", "learn/index.html", "learn/fee-staircase.html", "learn/price-curve.html", "manifesto.html", "verify.html"]) {
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
