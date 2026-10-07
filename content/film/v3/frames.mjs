// Style frames for the v3 look: render chosen moments of resolved jobs as PNGs, or a short
// motion test as MP4, without touching a film's clips.
//   FILM_LOOK=v3 node content/film/v3/frames.mjs <jobs.json> <outdir> [--video] [--jpeg] [--only id,id]
// A job's `stills` (seconds) set the moments; --video writes <id>.mp4 at 30 fps instead.
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";
import { serve, cdp, chromeBin, STAGE, seekJS } from "../render.mjs";
import { filmFigures } from "./built.mjs";
import { shotHTML } from "./shots.mjs";

const ROOT = new URL("../../../", import.meta.url).pathname;
const json = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));
const [jobsPath, outDir, ...rest] = process.argv.slice(2);
const only = rest.includes("--only") ? rest[rest.indexOf("--only") + 1].split(",") : null;
const video = rest.includes("--video");
const jobs = JSON.parse(readFileSync(jobsPath, "utf8")).filter((j) => !only || only.includes(j.id));
mkdirSync(outDir, { recursive: true });
const built = filmFigures();
const srv = await serve();
const page = await cdp(chromeBin());
try {
  await page.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await page.send("Page.enable"); await page.send("Runtime.enable");
  await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/${STAGE}` });
  await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
  for (const job of jobs) {
    const html = shotHTML(job, built);
    const broken = await page.evaluate(`(async () => {
      const stage = document.getElementById("stage"); stage.innerHTML = ${JSON.stringify(html)};
      await document.fonts.ready;
      await Promise.all([...stage.querySelectorAll("img")].map((i) => i.decode().catch(() => null)));
      document.getAnimations().forEach((a) => a.pause());
      return [...stage.querySelectorAll("img")].filter((i) => !i.naturalWidth).map((i) => i.getAttribute("src"));
    })()`);
    if (broken.length) console.error(`${job.id}: images did not load: ${broken.join(", ")}`);
    if (video) {
      const out = join(outDir, `${job.id}.mp4`);
      const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", "30", "-i", "-",
        "-frames:v", String(job.frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out], { stdio: ["pipe", "inherit", "inherit"] });
      for (let i = 0; i < job.frames; i++) {
        await page.evaluate(seekJS((i * 1000) / 30));
        const shot = await page.send("Page.captureScreenshot", { format: "jpeg", quality: 92, optimizeForSpeed: true });
        if (!ff.stdin.write(Buffer.from(shot.result.data, "base64"))) await new Promise((r) => ff.stdin.once("drain", r));
      }
      ff.stdin.end(); await new Promise((r) => ff.on("close", r));
      console.log(out);
    } else {
      for (const t of job.stills || [job.seconds / 2]) {
        await page.evaluate(seekJS(t * 1000));
        // --jpeg: a review frame at a tenth of a PNG's size (the scratch disk is shared, in memory)
        const jpeg = rest.includes("--jpeg");
        const png = await page.send("Page.captureScreenshot", jpeg ? { format: "jpeg", quality: 88 } : { format: "png" });
        const out = join(outDir, `${job.id}-${String(t.toFixed(2)).padStart(5, "0")}.${jpeg ? "jpg" : "png"}`);
        writeFileSync(out, Buffer.from(png.result.data, "base64"));
        console.log(out);
      }
    }
  }
} finally {
  page.close(); srv.close();
}
