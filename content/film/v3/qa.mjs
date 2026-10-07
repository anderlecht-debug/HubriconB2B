// Film QA for the v3 stage, with no AI in the loop: what five critic agents checked by eye on G01,
// as code, so a film a day is checked for free (docs/content/FILM_LINE.md).
//   FILM_LOOK=v3 node content/film/v3/qa.mjs <jobs.json> [--only id,id]
// Prints one JSON line per problem ({shot, kind, t, check, msg}), then a summary line. Checks:
//   early-figure  a figure readable before the voice says it (digits or a spelled number), unless the
//                 film said it before (job.said_before / said_phrases), or it is known (job.known);
//                 axis rulers and the label slot (citations) are exempt, as decided on G01
//   bare-opening  the shot's first frame is an empty desk: almost no lit area, no held picture, and at most one line
//   label-on-lit  the label slot sits over a lit picture or page (it must read on dark)
//   under-print   a line of text runs under a companion print
//   title-safe    a line outside title-safe; overlap: two landed lines on top of each other
import { readFileSync } from "node:fs";
import { serve, cdp, chromeBin, STAGE, seekJS } from "../render.mjs";
import { filmFigures } from "./built.mjs";
import { shotHTML } from "./shots.mjs";

const [jobsPath, ...rest] = process.argv.slice(2);
const only = rest.includes("--only") ? rest[rest.indexOf("--only") + 1].split(",") : null;
const jobs = JSON.parse(readFileSync(jobsPath, "utf8")).filter((j) => !only || only.includes(j.id));
const built = filmFigures();
const WORLD = new Set(["still", "texture", "footage"]);
const SAFE = { x0: 140, x1: 1780, y0: 70, y1: 1010 };
const STEP = 0.5;                      // the honesty sweep's spacing, seconds
const LEAD = 0.15;                     // a figure may start landing this long before its word

// numbers as the voice says them: digits, or spelled ("seventy-two" → 72); "one" is too often a pronoun
const ONES = Object.fromEntries("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ").map((w, i) => [w, i]));
const TENS = Object.fromEntries("twenty thirty forty fifty sixty seventy eighty ninety".split(" ").map((w, i) => [w, 20 + 10 * i]));
const digits = (s) => String(s).replace(/,/g, "").replace(/\.$/, "");
function numbersIn(text, spoken = false) {
  const out = (String(text).match(/\d[\d,]*(?:\.\d+)?/g) || []).map(digits);
  for (const m of String(text).toLowerCase().matchAll(/\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](one|two|three|four|five|six|seven|eight|nine))?\b|\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b/g))
    out.push(String(m[3] ? ONES[m[3]] : TENS[m[1]] + (m[2] ? ONES[m[2]] : 0)));
  if (spoken) for (const m of String(text).toLowerCase().matchAll(/\bone\b/g)) out.push("1");
  return out;
}

const srv = await serve();
const page = await cdp(chromeBin());
let problems = 0;
const report = (job, t, check, msg) => { problems++; console.log(JSON.stringify({ shot: job.id, kind: job.kind, t: +t.toFixed(2), check, msg })); };

// visible, readable text at this moment: effective opacity, blur filters, and the documents' depth of
// field (a soft line is drawn as a text-shadow under a nearly transparent colour)
const TEXT_JS = `(() => {
  const out = [];
  const eff = (el) => { let o = 1, blur = 0; for (let e = el; e && e.id !== "stage"; e = e.parentElement) { const cs = getComputedStyle(e);
    if (cs.visibility === "hidden" || cs.display === "none") return { o: 0, blur: 99 };
    o *= +cs.opacity; const m = /blur\\(([\\d.]+)px\\)/.exec(cs.filter); if (m) blur = Math.max(blur, +m[1]); } return { o, blur }; };
  const walker = document.createTreeWalker(document.getElementById("stage"), NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode());) {
    const txt = n.textContent.replace(/\\s+/g, " ").trim(); if (!txt) continue;
    const el = n.parentElement; if (el.closest("svg defs, style, script")) continue;
    const { o, blur } = eff(el); if (o < 0.5 || blur >= 3) continue;
    const cs = getComputedStyle(el), a = /rgba?\\([^)]*?,\\s*([\\d.]+)\\)$/.exec(cs.color), alpha = a ? +a[1] : (/ \\/ ([\\d.]+)\\)$/.exec(cs.color) || [0, 1])[1];
    if (+alpha * o < 0.35) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    for (const b of r.getClientRects()) {
      if (b.width < 4 || b.height < 4 || b.right < 0 || b.left > 1920 || b.bottom < 0 || b.top > 1080) continue;
      out.push({ txt, x0: b.left, y0: b.top, x1: b.right, y1: b.bottom, o,
        label: !!el.closest(".labels"), ruler: !!el.closest(".ch-tick, .ch-axis, .ch-axisname"),
        paper: !!el.closest(".v3-document, .v3-table, .v3-receipt"), id: el.dataset.qa || (el.dataset.qa = Math.random().toString(36).slice(2)) });
    }
  }
  const pr = [...document.querySelectorAll(".ph-comp img")].filter((i) => eff(i).o > 0.3).map((i) => i.getBoundingClientRect()).filter((b) => b.width > 20)
    .map((b) => ({ x0: b.left, y0: b.top, x1: b.right, y1: b.bottom }));
  const lab = [...document.querySelectorAll(".labels p")].filter((p) => +getComputedStyle(p).opacity > 0.5)
    .map((p) => p.getBoundingClientRect()).filter((b) => b.width > 4);
  const held = [...document.querySelectorAll(".v3-backdrop")].some((b) => +getComputedStyle(b).opacity > 0.1);
  return { text: out, prints: pr, held, label: lab.length ? { x0: Math.min(...lab.map((b) => b.left)), y0: Math.min(...lab.map((b) => b.top)),
    x1: Math.max(...lab.map((b) => b.right)), y1: Math.max(...lab.map((b) => b.bottom)) } : null };
})()`;

// mean luma of a screenshot region, measured in the page (no image library on this side)
async function luma(clip, hideLabels = false) {
  if (hideLabels) await page.evaluate(`document.querySelectorAll(".labels").forEach((l) => l.style.visibility = "hidden")`);
  const shot = await page.send("Page.captureScreenshot", { format: "jpeg", quality: 70, clip: { ...clip, scale: 0.25 } });
  if (hideLabels) await page.evaluate(`document.querySelectorAll(".labels").forEach((l) => l.style.visibility = "")`);
  return page.evaluate(`new Promise((ok) => { const i = new Image(); i.onload = () => { const c = document.createElement("canvas");
    c.width = i.width; c.height = i.height; const x = c.getContext("2d"); x.drawImage(i, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data;
    let s = 0, lit = 0; for (let k = 0; k < d.length; k += 4) { const y = 0.2126 * d[k] + 0.7152 * d[k + 1] + 0.0722 * d[k + 2]; s += y; if (y > 70) lit++; }
    ok({ mean: s / (d.length / 4), lit: lit / (d.length / 4) }); }; i.src = "data:image/jpeg;base64,` + shot.result.data + `"; })`);
}

try {
  await page.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await page.send("Page.enable"); await page.send("Runtime.enable");
  await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/${STAGE}` });
  await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
  for (const job of jobs) {
    if (WORLD.has(job.kind)) continue;
    await page.evaluate(`(async () => { const s = document.getElementById("stage"); s.innerHTML = ${JSON.stringify(shotHTML(job, built))};
      await document.fonts.ready; await Promise.all([...s.querySelectorAll("img")].map((i) => i.decode().catch(() => null)));
      document.getAnimations().forEach((a) => a.pause()); })()`);
    const before = new Set([...(job.said_before || []).map(digits), ...Object.values(job.known || {}).flatMap((v) => numbersIn(v))]);
    for (const ph of job.said_phrases || []) for (const n of numbersIn(ph)) if (n.length >= 2) before.add(n);
    const said = (t) => new Set((job.words || []).filter((w) => +w.t <= t + LEAD).flatMap((w) => numbersIn(w.w ?? w.word ?? "", true)));
    const seen = new Set();
    const once = (key, fn) => { if (!seen.has(key)) { seen.add(key); fn(); } };
    const T = job.seconds;
    const moments = [0.1]; for (let t = STEP; t < T - 0.05; t += STEP) moments.push(t); moments.push(Math.max(0, T - 0.05));
    for (const t of moments) {
      await page.evaluate(seekJS(t * 1000));
      const { text, prints, held, label } = await page.evaluate(TEXT_JS);
      const now = said(t);
      for (const b of text) {
        if (b.label || b.ruler) continue;
        for (const n of numbersIn(b.txt)) {
          if (n === "1" || n === "0" || before.has(n) || now.has(n)) continue;
          once(`fig:${n}:${b.txt}`, () => report(job, t, "early-figure", `"${n}" readable in "${b.txt.slice(0, 60)}" before it is said`));
        }
        for (const p of prints) {
          const ox = Math.min(b.x1, p.x1) - Math.max(b.x0, p.x0), oy = Math.min(b.y1, p.y1) - Math.max(b.y0, p.y0);
          if (ox > 0.15 * (b.x1 - b.x0) && oy > 0.3 * (b.y1 - b.y0)) once(`print:${b.txt}`, () => report(job, t, "under-print", `"${b.txt.slice(0, 50)}" runs under the companion print`));
        }
      }
      // the layout checks at three moments, as layout_qa.mjs did
      if ([0.35, 0.7, 0.98].some((f) => Math.abs(t - f * T) < STEP / 2)) {
        const boxes = text.filter((b) => !b.label);
        for (const b of boxes) if (!b.paper && !b.ruler && (b.x0 < SAFE.x0 || b.x1 > SAFE.x1 || b.y0 < SAFE.y0 || b.y1 > SAFE.y1))
          once(`safe:${b.txt}`, () => report(job, t, "title-safe", `"${b.txt.slice(0, 40)}" outside title-safe`));
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
          const a = boxes[i], b = boxes[j];
          if (a.o < 0.9 || b.o < 0.9 || a.id === b.id || a.txt === b.txt) continue;
          const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
          if (ox > 6 && oy > 0.35 * Math.min(a.y1 - a.y0, b.y1 - b.y0)) once(`ov:${a.txt}|${b.txt}`, () => report(job, t, "overlap", `"${a.txt.slice(0, 30)}" × "${b.txt.slice(0, 30)}"`));
        }
      }
      // pictures of the frame: the opening, and the label's ground at three moments
      if (t === 0.1) {
        const f = await luma({ x: 0, y: 0, width: 1920, height: 1080 }, true);
        const lines = new Set(text.filter((b) => !b.label).map((b) => b.y0 >> 4)).size;
        if (f.lit < 0.03 && lines <= 1 && !held) report(job, t, "bare-opening", `opens on an empty desk (${(100 * f.lit).toFixed(1)}% lit, ${lines} line)`);
      }
      if (label && (t === 0.1 || [0.5, 0.95].some((f) => Math.abs(t - f * T) < STEP / 2))) {
        const g = await luma({ x: Math.max(0, label.x0 - 8), y: Math.max(0, label.y0 - 6), width: Math.min(1900, label.x1 - label.x0 + 16), height: label.y1 - label.y0 + 12 }, true);
        if (g.mean > 95) once("label", () => report(job, t, "label-on-lit", `the label sits on a lit area (mean luma ${g.mean.toFixed(0)})`));
      }
    }
  }
} finally {
  page.close(); srv.close();
}
console.log(JSON.stringify({ summary: true, shots: jobs.filter((j) => !WORLD.has(j.kind)).length, problems }));
