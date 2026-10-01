// The pieces every public page shares, built from data so no page hand-copies them
// (scripts/build-pages.mjs bakes them in between <!-- build:NAME --> markers):
//
//   nav            the tabs, the Education and Trust flyouts, the phone menu
//   foot           the footer: every page, one version
//   library-home   the course library as the home page shows it
//   library-hub    the same library on /learn, with what each planned course will cover
//   film-case      the case-study film's slot on the home page
//   video-<id>     a lesson's video slot on its course page
//   wall           the results wall: clients' own words, or a reserved frame for each missing one
//   board          the scoreboard illustration, its receipts counted by the terms' rules
//
// Honesty, in code: a planned course links nowhere and names no date; an empty video
// slot says what will play there in the future tense; a testimonial needs the
// client's consent, its date and the Record month it speaks to; and the
// illustration's dollars are counted by the same rules the terms set.
import { readFileSync } from "node:fs";

const root = new URL("../", import.meta.url);
const json = (p) => JSON.parse(readFileSync(new URL(p, root), "utf8"));

const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
const usd = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const longDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };

export const MARK = '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" fill="none" stroke="currentColor" stroke-width="5"/><path d="M22.5 18h6.5v11h6V18h6.5v28H35V35.5h-6V46h-6.5z" fill="currentColor"/></svg>';
const ARROW = '<span class="arrow" aria-hidden="true">→</span>';
const CHEV = '<svg class="chev" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';

/** The tabs, in the order they sit on the bar. */
const TABS = [["Proof", "/#case-study"], ["How it works", "/#how"], ["The offer", "/#offer"], ["Results", "/#results"]];
/** Where every promise is written down. */
const TRUST = [
  ["How a dollar counts", "/terms#how-a-dollar-counts", "The rules your Record is kept by, agreed before any number is on it."],
  ["What is true today", "/honesty", "No client results yet, and every number we publish labelled for what it is."],
  ["Your data", "/your-data", "What we ask for, where it lives, and how you take it back."],
];
const WRITING = [["The terms", "/terms"], ["Privacy", "/privacy"], ["The guarantee", "/#offer"]];
const PROOF = [["The case study", "/#case-study"], ["The results wall", "/#results"], ["Check a Profit Record", "/verify"]];

// ------------------------------------------------------------------ the nav ----
/* The motion switch, first thing in the body: .motion only when scripts run and the
   visitor hasn't asked for less of it; if /assets/site.js never arrives, it comes off
   and every chart and section is simply there. */
const SWITCH = `<script>
(function (d) {
  d.classList.add("js");
  try {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    d.classList.add("motion");
    setTimeout(function () { if (!window.__hubriconMotion) d.classList.remove("motion"); }, 3000);
  } catch (e) {}
})(document.documentElement);
</script>`;

function nav(lib) {
  const live = lib.courses.filter((c) => c.status === "live");
  const planned = lib.courses.filter((c) => c.status === "planned");
  const big = ([t, h]) => `<a class="fly-big" href="${h}">${esc(t)}</a>`;
  const small = ([t, h]) => `<a class="fly-small" href="${h}">${esc(t)}</a>`;
  const education = `
        <div class="nav-fly" id="fly-education">
          <div class="fly-in">
            <div class="fly-col"><p class="fly-k">Education</p>${big(["All courses", "/learn"])}${live.map((c) => big([c.title, c.path])).join("")}</div>
            <div class="fly-col"><p class="fly-k">Planned</p>${planned.map((c) => `<span class="fly-planned">${esc(c.title)}</span>`).join("")}</div>
            <div class="fly-col"><p class="fly-k">Start tonight</p>${live.map((c) => small([c.start.text, c.start.href]) + small([`${c.title} spreadsheet (.xlsx)`, c.template])).join("")}</div>
          </div>
        </div>`;
  const trust = `
        <div class="nav-fly" id="fly-trust">
          <div class="fly-in">
            <div class="fly-col"><p class="fly-k">Trust</p>${TRUST.map(big).join("")}</div>
            <div class="fly-col"><p class="fly-k">In writing</p>${WRITING.map(small).join("")}</div>
            <div class="fly-col"><p class="fly-k">The proof</p>${PROOF.map(small).join("")}</div>
          </div>
        </div>`;
  const sheet = `
  <div class="nav-sheet" id="nav-sheet">
    <div class="sheet-in">
      <div class="sheet-group">${TABS.map(([t, h]) => `<a class="sheet-big" href="${h}">${esc(t)}</a>`).join("")}</div>
      <div class="sheet-group"><p class="sheet-k">Education</p><a class="sheet-mid" href="/learn">All courses</a>${live.map((c) => `<a class="sheet-mid" href="${c.path}">${esc(c.title)}</a>`).join("")}</div>
      <div class="sheet-group"><p class="sheet-k">Trust</p>${TRUST.map(([t, h]) => `<a class="sheet-mid" href="${h}">${esc(t)}</a>`).join("")}<a class="sheet-mid" href="/terms">The terms</a><a class="sheet-mid" href="/verify">Check a Profit Record</a></div>
    </div>
  </div>`;
  return `
<header class="nav" data-nav>
${SWITCH}
  <div class="nav-in">
    <a class="nav-mark" href="/" aria-label="Hubricon, home">${MARK}<span>Hubricon</span></a>
    <nav class="nav-tabs" aria-label="Main">
      ${TABS.map(([t, h]) => `<a class="nav-tab" href="${h}">${esc(t)}</a>`).join("\n      ")}
      <div class="nav-group">
        <a class="nav-tab" href="/learn" aria-controls="fly-education">Education${CHEV}</a>${education}
      </div>
      <div class="nav-group">
        <a class="nav-tab" href="/#trust" aria-controls="fly-trust">Trust${CHEV}</a>${trust}
      </div>
    </nav>
    <div class="nav-end">
      <a class="btn btn-nav" href="/apply" data-cta="nav">Book your call ${ARROW}</a>
      <button class="nav-menu" type="button" aria-expanded="false" aria-controls="nav-sheet" aria-label="Menu"><span></span><span></span></button>
    </div>
  </div>${sheet}
  <div class="nav-scrim" aria-hidden="true"></div>
</header>
`;
}

// --------------------------------------------------------------- the footer ----
function foot(lib) {
  const live = lib.courses.filter((c) => c.status === "live");
  const col = (k, links) => `<div class="foot-col"><p class="foot-k">${k}</p>${links.map(([t, h]) => `<a href="${h}">${esc(t)}</a>`).join("")}</div>`;
  return `
<footer class="site-foot night">
  <div class="foot-wrap">
    <div class="foot-brand">
      <a class="foot-mark" href="/" aria-label="Hubricon, home">${MARK}<span>Hubricon</span></a>
      <p class="foot-motto">Paid on proof.</p>
    </div>
    <div class="foot-cols">
      ${col("The work", [...TABS, ["The manifesto", "/manifesto"]])}
      ${col("Education", [["All courses", "/learn"], ...live.map((c) => [c.title, c.path])])}
      ${col("Trust", [...TRUST.map(([t, h]) => [t, h]), ["Check a Profit Record", "/verify"]])}
      ${col("Legal", [["Terms", "/terms"], ["Privacy", "/privacy"]])}
    </div>
    <p class="foot-legal"><span data-proof-pending>No client results are published yet; the first appears when a client agrees to publish theirs. </span>Case-study figures are estimates modeled from public pages and Amazon's published fee schedules. The scoreboard is an illustration. © 2026 Hubricon</p>
  </div>
</footer>
`;
}

// --------------------------------------------------------- the course covers ----
/* Each course's cover is a house visual in miniature, drawn once on scroll-in: ink for
   the structure, blue only on the money or the leak. 320 × 180, the shape of a video. */
function cover(kind, id) {
  const draw = (d, cls = "cv-line", delay = 0) => `<path class="${cls} draw" pathLength="1" style="--delay:${delay}ms" d="${d}"/>`;
  const art = {
    staircase: () => `
      <path class="cv-grid" d="M20 160 H300"/>
      ${draw("M20 152 H84 V128 H148 V100 H212 V66 H276 V34 H300")}
      ${draw("M148 128 V100", "cv-leak", 900)}
      <circle class="cv-hollow fade" style="--after:1100ms" cx="140" cy="128" r="5"/>
      <circle class="cv-dot fade" style="--after:1100ms" cx="156" cy="100" r="5"/>`,
    waterfall: () => {
      const bars = [[24, 36, 124], [76, 36, 30], [128, 66, 26], [180, 92, 22], [232, 114, 14], [284, 128, 32]];
      return `<path class="cv-grid" d="M16 160 H310"/>` + bars.map(([x, y, h], i) => i === 4
        ? `<rect class="cv-blue fade" style="--after:${300 + i * 160}ms" x="${x - 14}" y="${y}" width="28" height="${h}"/>`
        : draw(`M${x - 14} ${y + h} V${y} H${x + 14} V${y + h}`, i === 5 ? "cv-line" : "cv-dim", i * 160)).join("")
        + draw("M38 36 H62 M90 66 H114 M142 92 H166 M194 114 H218 M246 128 H270", "cv-guide", 900);
    },
    trough: () => `
      <defs><clipPath id="${id}-below"><rect x="0" y="96" width="320" height="84"/></clipPath></defs>
      <path class="cv-zero" d="M20 96 H300"/>
      ${draw("M20 64 C 70 64, 92 150, 150 150 S 240 66, 300 38")}
      <g clip-path="url(#${id}-below)">${draw("M20 64 C 70 64, 92 150, 150 150 S 240 66, 300 38", "cv-leak", 0)}</g>`,
    curve: () => `
      <path class="cv-grid" d="M20 160 H300"/>
      ${draw("M24 156 C 90 30, 210 30, 296 156")}
      ${draw("M96 75 H152", "cv-guide", 1000)}
      <circle class="cv-hollow fade" style="--after:900ms" cx="96" cy="75" r="5"/>
      <circle class="cv-bluedot fade" style="--after:1200ms" cx="152" cy="62" r="6"/>`,
    fan: () => {
      const ends = [34, 52, 68, 82, 96, 110, 124, 140, 156];
      return `<path class="cv-wash fade" style="--after:1400ms" d="M24 98 Q 160 98, 300 52 L300 140 Q 160 98, 24 98 Z"/>`
        + ends.map((y, i) => draw(`M24 98 Q 160 98, 300 ${y}`, "cv-path", i * 60)).join("")
        + draw("M24 98 Q 160 98, 300 96", "cv-line", 600);
    },
    bars: () => `
      ${draw("M24 44 H296 V76 H24 Z", "cv-dim")}
      ${draw("M24 108 H196 V140 H24 Z", "cv-line", 300)}
      ${draw("M196 124 H296", "cv-leak", 900)}
      <path class="cv-guide" d="M296 76 V140"/>`,
  }[kind];
  if (!art) throw new Error(`no cover called ${kind}`);
  return `<svg class="cover-art" viewBox="0 0 320 180" aria-hidden="true">${art()}</svg>`;
}

// ------------------------------------------------------------- video slots ----
/** A video that exists. preload="none": nothing downloads until the visitor presses play. */
function video(v, label, track) {
  const poster = v.poster ? ` poster="${esc(v.poster)}"` : "";
  return `<video class="slot-video" src="${esc(v.src)}"${poster} controls preload="none" playsinline aria-label="${esc(label)}" data-track="${esc(track)}"></video>`;
}

function filmCase(lib) {
  const f = lib.films.case_study;
  if (f.src) return `\n<div class="film">${video(f, f.title, "case_film")}</div>\n`;
  // Until it exists, the slot names what will play, beat by beat. It does not redraw
  // Fig. 1, which the visitor has just read one screen up.
  const beats = f.beats.map((b, i) => `<li><span>${String(i + 1).padStart(2, "0")}</span>${esc(b)}</li>`).join("");
  return `
<div class="film film-waiting night">
  <p class="film-note"><span class="label">Film</span><span>${esc(f.waiting)}</span></p>
  <ol class="film-beats">${beats}</ol>
</div>
`;
}

function lessonVideos(lib) {
  const out = {};
  for (const c of lib.courses.filter((x) => x.status === "live")) {
    for (const l of c.lessons) {
      // Until a lesson's video exists, its slot says what will play there (the spec's amendment:
      // "every course and lesson has a slot that says what will play there until it does").
      // Nothing pretends to play: no frame, no button.
      out[`video-${l.id}`] = l.video
        ? `\n<div class="lesson-video">${video(l.video, `${c.title}: ${l.title}`, `lesson:${l.id}`)}</div>\n`
        : `\n<p class="lesson-video-waiting"><span class="label">Video</span><span>This lesson, taught on screen on its own charts, will play here.</span></p>\n`;
    }
  }
  return out;
}

// ---------------------------------------------------------------- the library ----
const lessonCount = (c) => (Array.isArray(c.lessons) ? c.lessons.length : c.lessons);

/* The email, as the founder set it on 2026-10-01: every lesson and spreadsheet is open to
   anyone, and an email is the opt-in for a little extra: the link and the spreadsheet in your
   inbox, then a short note only when a fee card the courses use changes or a new course opens. One
   form, wherever it shows (the featured card, a course's cover and its last lesson); it posts
   the address, the course and the link's campaign tag to /api/learn (/assets/site.js). Its
   button is the field's own outline, never the call's. `where` keeps the ids unique. */
export function joinForm(c, where = "card") {
  const id = `join-${c.slug}${where === "card" ? "" : `-${where}`}`;
  return `
      <form class="join-tile" data-join="${c.slug}" novalidate>
        <label for="${id}">Want it in your inbox? <span>Optional</span></label>
        <div class="join-row">
          <input id="${id}" name="email" type="email" required autocomplete="email" inputmode="email" placeholder="you@yourbrand.com">
          <button type="submit">Send it to me ${ARROW}</button>
        </div>
        <div class="hp" aria-hidden="true"><label for="${id}-website">Leave this empty</label><input id="${id}-website" name="website" tabindex="-1" autocomplete="off"></div>
        <p class="join-fine">No email is needed to read it. Leave one and we send the link and the spreadsheet, then a short note only when a fee card the courses use changes or a new course opens. One click unsubscribes. <a href="/privacy#learn">How we handle your email</a>.</p>
        <p class="join-err" role="alert" hidden></p>
      </form>`;
}

function liveTile(c, i, { feature, wide = false }) {
  // The featured course carries the opt-in form, and a tile with a trailer carries a
  // video, so neither can be one link: the cover, the title and "Start" carry it instead.
  const trailer = Boolean(c.trailer && c.trailer.src);
  const whole = !trailer && !feature;
  // Who it is for, first after "Free": an Amazon-only course says so, so a Shopify seller moves on to one that runs on theirs
  const badges = ["Free", ...(c.audience ? [c.audience] : []), `${lessonCount(c)} lessons`, ...(c.extras || [])].map((b) => `<span class="go-badge">${esc(b)}</span>`).join("");
  const title = whole ? esc(c.title) : `<a href="${c.path}">${esc(c.title)}</a>`;
  const go = feature
    ? `<a class="go-to" href="${c.path}#${c.lessons[0].id}">Start lesson 1, no email needed ${ARROW}</a>`
    : whole ? `<span class="go-to">Take the course ${ARROW}</span>` : `<a class="go-to" href="${c.path}">Take the course ${ARROW}</a>`;
  const art = trailer
    ? video(c.trailer, `${c.title}: trailer`, `trailer:${c.slug}`)
    : `<span class="cover-k">Course ${i + 1}</span>${cover(c.cover, `cv-${c.slug}`)}<span class="cover-title">${esc(c.title)}</span>`;
  const cls = `tile tile-live${feature ? " tile-feature" : ""}${wide ? " tile-wide" : ""}`;
  const coverEl = trailer || whole
    ? `<div class="tile-cover night">${art}</div>`
    : `<a class="tile-cover night" href="${c.path}" tabindex="-1" aria-hidden="true">${art}</a>`;
  const [open, close] = whole
    ? [`<a class="${cls}" href="${c.path}" data-play>`, "</a>"]
    : [`<article class="${cls}"${trailer ? "" : " data-play"}>`, "</article>"];
  return `
  ${open}
    ${coverEl}
    <div class="tile-body">
      <div class="go-badges">${badges}</div>
      <h3>${title}</h3>
      <p>${esc(c.summary)}</p>${feature || wide ? `\n      <p class="tile-detail">${esc(c.detail)}</p>` : ""}
      ${go}${feature ? joinForm(c) : ""}
    </div>
  ${close}`;
}

/* Each live course's opt-in, twice: under its cover's start, and at the end of its last
   lesson, where a reader who finished it is the one most likely to want it kept current. */
function optins(lib) {
  const out = {};
  for (const c of lib.courses.filter((x) => x.status === "live")) {
    out[`optin-${c.slug}-cover`] = joinForm(c, "cover");
    out[`optin-${c.slug}-end`] = `
      <section class="keep" aria-labelledby="keep-${c.slug}-h">
        <h3 id="keep-${c.slug}-h">Keep it current</h3>
        <p>The fee cards these courses use change about once a year, and Amazon adds a holiday card every autumn. Leave an email and you hear when that happens, and when the next course opens. Nothing else.</p>${joinForm(c, "end")}
      </section>`;
  }
  return out;
}

function plannedTile(c, { hub }) {
  const covers = hub ? `
      <details class="tile-more"><summary>What it will cover</summary><ol>${c.lessons.map((l) => `<li>${esc(l.title)}</li>`).join("")}</ol></details>` : "";
  return `
  <article class="tile tile-planned" data-play>
    <div class="tile-cover night"><span class="cover-k">Planned</span>${cover(c.cover, `cv-${c.slug}${hub ? "-hub" : ""}`)}<span class="cover-title">${esc(c.title)}</span></div>
    <div class="tile-body">
      <div class="go-badges"><span class="go-badge">${lessonCount(c)} lessons planned</span></div>
      <h3>${esc(c.title)}</h3>
      <p>${esc(c.summary)}</p>${covers}
    </div>
  </article>`;
}

function library(lib, { hub }) {
  const live = lib.courses.filter((c) => c.status === "live");
  const planned = lib.courses.filter((c) => c.status === "planned");
  // One featured course, the way Acquisition.com features one, with the opt-in under it; every
  // other live course is a tile that opens its own page. Every lesson is open, no email asked.
  const [first, ...more] = live;
  const others = more.length ? `
  <div class="lib-live">
    <p class="lib-k">Also free, complete now</p>
    <div class="lib-live-list">${more.map((c, i) => liveTile(c, i + 1, { feature: false, wide: true })).join("")}
    </div>
  </div>` : "";
  return `
<div class="lib">${liveTile(first, 0, { feature: true })}${others}
  <div class="lib-planned">
    <p class="lib-k">Planned for the library <span>· free and open when each is complete</span></p>
    <div class="${hub ? "lib-grid" : "rail"}">${planned.map((c) => plannedTile(c, { hub })).join("")}
    </div>
  </div>
</div>
`;
}

// ---------------------------------------------------------- the results wall ----
export function checkTestimonial(t) {
  for (const k of ["client", "quote", "consent_on", "record_month"]) {
    if (!t[k] || !String(t[k]).trim()) throw new Error(`a testimonial without ${k}: the wall takes a client's own words, with consent, or nothing`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t.consent_on)) throw new Error(`consent_on is a date (YYYY-MM-DD), not "${t.consent_on}"`);
  if (!/^\d{4}-\d{2}$/.test(t.record_month)) throw new Error(`record_month is a month (YYYY-MM), not "${t.record_month}"`);
}

function wall(list) {
  list.forEach(checkTestimonial);
  const said = list.map((t) => `
    <figure class="frame frame-said">
      ${t.video && t.video.src ? `<div class="frame-media">${video(t.video, `${t.client}, in their own words`, "testimonial")}</div>` : ""}
      <blockquote>${esc(t.quote)}</blockquote>
      <figcaption><b>${esc(t.client)}</b>${t.role ? `, ${esc(t.role)}` : ""}${t.brand ? ` · ${esc(t.brand)}` : ""}<span>Their words, published with consent on ${longDate(t.consent_on)} · Record month ${esc(t.record_month)}</span></figcaption>
    </figure>`);
  const reserved = Array.from({ length: Math.max(0, 3 - list.length) }, (_, i) => `
    <div class="frame frame-reserved">
      <span class="frame-n">${String(list.length + i + 1).padStart(2, "0")}</span>
      <span class="label">Reserved</span>
    </div>`);
  return `
<div class="wall-frames" data-wall>${[...said, ...reserved].join("")}
</div>
<div class="wall-results" id="wall-results" hidden></div>
`;
}

// ------------------------------------------------- the scoreboard illustration ----
/** What a move's dollars count for on the Record (scripts/blocks/attribution.html). */
export function counts({ grade, expected, measured }) {
  if (measured < 25) return 0;                       // nothing under $25
  if (grade === "direct") return measured;           // what the platform actually paid
  if (grade === "isolated" || grade === "attributable") return Math.min(measured, expected);   // never above the promise; a miss stays
  return 0;                                          // unmeasurable banks nothing
}
const why = (m) => m.measured < 25 ? "Under $25 counts nothing"
  : m.grade === "direct" ? "What Amazon paid"
  : m.measured > m.expected ? `Never above the promise: ${usd(m.measured - m.expected)} more shown, not added`
  : m.measured < m.expected ? "A miss stays at what it earned"
  : "";

export function board(il) {
  const rows = il.moves.map((m) => ({ ...m, counts: counts(m) }));
  const month = rows.reduce((t, r) => t + r.counts, 0);
  const proven = il.proven_before_this_month + month;
  const up = month - il.fee;
  const bill = Math.min(100, (il.fee / Math.max(month, il.fee)) * 100).toFixed(1);
  const fill = Math.min(100, (month / Math.max(month, il.fee)) * 100).toFixed(1);
  const grade = (g) => g.charAt(0).toUpperCase() + g.slice(1);
  const sentence = up > 0
    ? `This month your Record counted <b class="money">${usd(month)}</b>. Our bill was <b>${usd(il.fee)}</b>. You're up <b class="money">${usd(up)}</b>.`
    : `This month your Record counted <b class="money">${usd(month)}</b>, under our <b>${usd(il.fee)}</b> bill. So this month is free.`;
  return `
<div class="board">
  <p class="board-k">Proven since day one</p>
  <p class="board-big money" data-count>${usd(proven)}</p>
  <p class="board-line">${sentence}</p>
  <div class="bar" role="img" aria-label="Counted ${usd(month)} against a ${usd(il.fee)} bill" data-reveal><span class="bar-fill" style="width: ${fill}%"></span><span class="bar-bill" style="left: ${bill}%"></span></div>
  <div class="bar-keys"><span class="k-bill" style="left: ${bill}%">Our bill</span><span class="k-measured">Counted</span></div>
  <details class="fold receipts">
    <summary><span>This month's receipts <span class="tone">· ${rows.length} moves, each called before it went live</span></span></summary>
    <div class="fold-body">
      <table class="rcpt">
        <thead><tr><th>Move</th><th>How we know</th><th class="num">Called before</th><th class="num">Measured after</th><th class="num">Counts</th></tr></thead>
        <tbody>${rows.map((r) => `
          <tr><td>${esc(r.move)}${why(r) ? `<span class="rcpt-why">${esc(why(r))}</span>` : ""}</td><td data-k="How we know">${grade(r.grade)}</td><td class="num" data-k="Called before">${usd(r.expected)}</td><td class="num" data-k="Measured after">${usd(r.measured)}</td><td class="num money" data-k="Counts">${usd(r.counts)}</td></tr>`).join("")}
        </tbody>
        <tfoot><tr><td colspan="4">This month, counted once</td><td class="num money" data-k="This month">${usd(month)}</td></tr></tfoot>
      </table>
    </div>
  </details>
</div>
`;
}

/** Every shared block, from the data files. */
export function siteBlocks() {
  const lib = json("data/library.json");
  return {
    nav: nav(lib),
    foot: foot(lib),
    "library-home": library(lib, { hub: false }),
    "library-hub": library(lib, { hub: true }),
    "film-case": filmCase(lib),
    ...lessonVideos(lib),
    ...optins(lib),
    wall: wall(json("data/testimonials.json").testimonials),
    board: board(json("data/scoreboard-illustration.json")),
  };
}
