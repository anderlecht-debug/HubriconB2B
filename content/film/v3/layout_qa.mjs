// Layout QA for the v3 stage: every visible line of text, at three moments of every shot, must sit
// inside title-safe and must not overlap another line. A film a day cannot be checked by eye.
//   FILM_LOOK=v3 node content/film/v3/layout_qa.mjs <jobs.json> [--only id,id]  → one line per problem
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { serve, cdp, chromeBin, STAGE, seekJS } from "../render.mjs";
import { filmFigures } from "./built.mjs";
import { shotHTML } from "./shots.mjs";

const ROOT = new URL("../../../", import.meta.url).pathname;
const json = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));
const [jobsPath, ...rest] = process.argv.slice(2);
const only = rest.includes("--only") ? rest[rest.indexOf("--only") + 1].split(",") : null;
const jobs = JSON.parse(readFileSync(jobsPath, "utf8")).filter((j) => !only || only.includes(j.id));
const built = filmFigures();
const SAFE = { x0: 140, x1: 1780, y0: 70, y1: 1010 };   // title-safe, with a 20 px tolerance
const srv = await serve();
const page = await cdp(chromeBin());
let problems = 0;
try {
  await page.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await page.send("Page.enable"); await page.send("Runtime.enable");
  await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/${STAGE}` });
  await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
  for (const job of jobs) {
    if (["still", "texture", "footage"].includes(job.kind)) continue;
    await page.evaluate(`(async () => { const s = document.getElementById("stage"); s.innerHTML = ${JSON.stringify(shotHTML(job, built))};
      await document.fonts.ready; await Promise.all([...s.querySelectorAll("img")].map((i) => i.decode().catch(() => null)));
      document.getAnimations().forEach((a) => a.pause()); })()`);
    const seen = new Set();
    for (const f of [0.35, 0.7, 0.98]) {
      const t = job.seconds * f;
      await page.evaluate(seekJS(t * 1000));
      const found = await page.evaluate(`(() => {
        const S = ${JSON.stringify(SAFE)}, out = [], boxes = [];
        const vis = (el) => { let o = 1; for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e);
          if (cs.visibility === "hidden" || cs.display === "none") return 0; o *= +cs.opacity; } return o; };
        const walker = document.createTreeWalker(document.getElementById("stage"), NodeFilter.SHOW_TEXT);
        for (let n; (n = walker.nextNode());) {
          const txt = n.textContent.trim(); if (txt.length < 2) continue;
          const el = n.parentElement; if (el.closest(".labels, svg defs")) continue;
          const o = vis(el); if (o < 0.5) continue;
          const r = document.createRange(); r.selectNodeContents(n);
          for (const b of r.getClientRects()) {
            if (b.width < 4 || b.height < 4) continue;
            const box = { x0: b.left, y0: b.top, x1: b.right, y1: b.bottom, txt: txt.slice(0, 40), o, el };
            if (box.x1 < 0 || box.x0 > 1920 || box.y1 < 0 || box.y0 > 1080) continue;   // off frame: not seen
            const paper = !!el.closest(".v3-document, .v3-table, .v3-receipt");     // a pushed-in page runs past the frame by design
            if (!paper && (box.x0 < S.x0 || box.x1 > S.x1 || box.y0 < S.y0 || box.y1 > S.y1)) out.push("outside title-safe: \\"" + box.txt + "\\" at " + [box.x0, box.y0, box.x1, box.y1].map(Math.round).join(","));
            boxes.push(box);
          }
        }
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
          const a = boxes[i], b = boxes[j];
          const ox = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0), oy = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
          // landed text only (an entrance passes over its neighbours), more than a third of a line's height,
          // and never two runs of one element (a line's own words)
          if (a.o < 0.9 || b.o < 0.9 || a.el === b.el) continue;
          if (ox > 6 && oy > 0.35 * Math.min(a.y1 - a.y0, b.y1 - b.y0) && a.txt !== b.txt) out.push("overlap: \\"" + a.txt + "\\" × \\"" + b.txt + "\\"");
        }
        return out;
      })()`);
      for (const p of found) if (!seen.has(p)) { seen.add(p); console.log(`${job.id}\t${job.kind}\t${t.toFixed(1)}s\t${p}`); problems++; }
    }
  }
} finally {
  page.close(); srv.close();
}
console.log(`${problems} layout problem(s)`);
