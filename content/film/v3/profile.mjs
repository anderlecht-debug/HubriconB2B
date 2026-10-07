// What a v3 shot costs to paint, per frame: the number that decides whether a film renders in
// one hour or ten. Samples frames across the shot and times the seek and the capture.
//   FILM_LOOK=v3 node content/film/v3/profile.mjs <jobs.json> [--only id,id] [--css "<injected css>"]
// Target: a paper shot at 350 ms a frame or less on this PC (one worker), the world stills less.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { serve, cdp, chromeBin, STAGE, seekJS } from "../render.mjs";
import { filmFigures } from "./built.mjs";
import { shotHTML } from "./shots.mjs";

const ROOT = new URL("../../../", import.meta.url).pathname;
const json = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));
const [jobsPath, ...rest] = process.argv.slice(2);
const arg = (k) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : null);
const only = arg("--only")?.split(",");
const css = arg("--css") || "";
const jobs = JSON.parse(readFileSync(jobsPath, "utf8")).filter((j) => !only || only.includes(j.id));
const built = filmFigures();
const srv = await serve();
const page = await cdp(chromeBin());
try {
  await page.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await page.send("Page.enable"); await page.send("Runtime.enable");
  await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/${STAGE}` });
  await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
  for (const job of jobs) {
    await page.evaluate(`(async () => { const s = document.getElementById("stage"); s.innerHTML = ${JSON.stringify(shotHTML(job, built))};
      await document.fonts.ready; await Promise.all([...s.querySelectorAll("img")].map((i) => i.decode().catch(() => null)));
      document.getAnimations().forEach((a) => a.pause());
      let st = document.getElementById("profile-css"); if (!st) { st = document.createElement("style"); st.id = "profile-css"; document.head.appendChild(st); }
      st.textContent = ${JSON.stringify(css)}; })()`);
    let paint = 0; const n = 8;
    for (let i = 0; i < n; i++) {
      await page.evaluate(seekJS((job.seconds * (i + 0.5) / n) * 1000));
      const t = performance.now();
      await page.send("Page.captureScreenshot", { format: "jpeg", quality: 95, optimizeForSpeed: true });
      paint += performance.now() - t;
    }
    const ms = Math.round(paint / n);
    console.log(`${job.id}\t${job.kind}\t${ms} ms/frame\t≈ ${Math.round((ms * job.frames) / 1000)} s for its ${job.frames} frames`);
  }
} finally {
  page.close(); srv.close();
}
