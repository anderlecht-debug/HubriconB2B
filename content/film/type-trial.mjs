// A type trial for the films: the same frames of the style reel, finished, in several
// typefaces and sizings, side by side, so the founder chooses by looking.
//
//   node content/film/type-trial.mjs [outdir]        default content/videos/type-trial
//
// Each variant is a Google Fonts link (the only font host the site's CSP allows, so the
// winner can go on the site as well) and a few overrides of the film's own sizes.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { figures } from "../../scripts/build-pages.mjs";
import { sceneHTML, STYLE_REEL } from "./scenes.mjs";
import { chromeBin, serve, cdp } from "./render.mjs";
import { readFileSync } from "node:fs";

const ROOT = new URL("../../", import.meta.url).pathname;
const json = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));

// Sizes a phone can read: published guidance for 1080p video watched on a phone is
// 40 to 60 px for running text, titles half again as large. A standalone figure takes
// proportional digits; tabular digits are for columns.
const PHONE = `
  .caption { font-size: 44px; max-width: 46ch; }
  .heading { font-size: 72px; }
  .number { font-variant-numeric: lining-nums proportional-nums; }
  .number-sub { font-size: 56px; }
  .corner .label-box { font-size: 28px; padding: 8px 18px; letter-spacing: 0.06em; }
  .mark { font-size: 34px; } .mark svg { width: 40px; height: 40px; }`;

export const VARIANTS = [
  { id: "a-today", name: "Today", note: "Inter as the site loads it now: the small-text cut at every size.", link: null, css: "" },
  { id: "b-inter-display", name: "Inter Display", note: "The same Inter, loaded with its optical-size axis, so big lines take the display cut. Phone-legible sizes.",
    link: "https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..700&display=block",
    css: `:root { --font: "Inter", ui-sans-serif, system-ui, sans-serif; } body { font-optical-sizing: auto; } .display, .heading, .number, .number-sub { letter-spacing: -0.03em; }${PHONE}` },
  { id: "c-geist", name: "Geist", note: "Vercel's grotesk: narrower, more technical. Phone-legible sizes.",
    link: "https://fonts.googleapis.com/css2?family=Geist:wght@400;600;700&display=block",
    css: `:root { --font: "Geist", ui-sans-serif, system-ui, sans-serif; } .display, .heading, .number { letter-spacing: -0.035em; }${PHONE}` },
  { id: "d-instrument-sans", name: "Instrument Sans", note: "A warmer neo-grotesk with a little more character. Phone-legible sizes.",
    link: "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600;700&display=block",
    css: `:root { --font: "Instrument Sans", ui-sans-serif, system-ui, sans-serif; } .display, .heading, .number { letter-spacing: -0.03em; }${PHONE}` },
];
const SCENES = ["s1", "s3", "s2"];

if (import.meta.url === `file://${process.argv[1]}`) {
  const out = process.argv[2] || join(ROOT, "content/videos/type-trial");
  const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
  const srv = await serve();
  const page = await cdp(chromeBin());
  try {
    await page.send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    for (const v of VARIANTS) {
      await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/content/film/stage.html` });
      await page.evaluate(`new Promise((r) => { const go = () => r(); document.readyState === "complete" ? go() : addEventListener("load", go); })`);
      await page.evaluate(`(async () => {
        ${v.link ? `const l = document.createElement("link"); l.rel = "stylesheet"; l.href = ${JSON.stringify(v.link)}; document.head.append(l); await new Promise((r) => { l.onload = r; l.onerror = r; });` : ""}
        const s = document.createElement("style"); s.textContent = ${JSON.stringify(v.css)}; document.head.append(s);
        await document.fonts.ready;
      })()`);
      mkdirSync(join(out, v.id), { recursive: true });
      for (const id of SCENES) {
        const scene = STYLE_REEL.scenes.find((s) => s.id === id);
        await page.evaluate(`(async () => {
          document.getElementById("stage").innerHTML = ${JSON.stringify(sceneHTML(scene, built))};
          await document.fonts.ready;
          document.querySelectorAll("[data-play]").forEach((f) => f.classList.add("playing"));
          for (const a of document.getAnimations()) { a.pause(); a.currentTime = a.effect.getComputedTiming().endTime; }
        })()`);
        const png = await page.send("Page.captureScreenshot", { format: "png" });
        writeFileSync(join(out, v.id, `${id}.png`), Buffer.from(png.result.data, "base64"));
      }
      const fam = await page.evaluate(`getComputedStyle(document.querySelector(".display, .heading, .number")).fontFamily`);
      console.log(`${v.id.padEnd(20)} ${fam}`);
    }
  } finally {
    page.close();
    srv.close();
  }
}
