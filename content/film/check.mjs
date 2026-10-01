// The spec's pre-publish checklist (HUBRICON_SPEC.md, "Content engine"), run every time:
// audio levels, spelling on every text frame, brand colours, spacing, every number
// labelled. The half a program can judge; the eye judges the rest.
//
//   node content/film/check.mjs <board.json> [<rendered.mp4>]
//
// Without a video it checks the words and the labels; with one it adds the colours,
// the margins and the loudness, read from the frames and the soundtrack themselves.
import { readFileSync, existsSync } from "node:fs";
import { execFileSync, spawnSync } from "node:child_process";
import { join } from "node:path";
import { figures } from "../../scripts/build-pages.mjs";
import { fill } from "./scenes.mjs";
import { drift } from "./lock.mjs";

const ROOT = new URL("../../", import.meta.url).pathname;
const read = (p) => readFileSync(join(ROOT, p), "utf8");
const json = (p) => JSON.parse(read(p));
const CASE = /public-data case study/i;
// Site figures that are case-study estimates (scripts/build-pages.mjs), for boards that use them directly.
const SITE_CASE = new Set(["leak_p10", "leak_p90", "units", "years", "months_total", "months_losing", "mc_p10", "mc_p50", "mc_p90", "sales_lo", "sales_hi", "weight", "who", "who_lower"]);
const PAGES = ["index.html", "honesty.html", "terms.html", "learn/index.html", "learn/fee-staircase.html"];

const words = (text) => (String(text).toLowerCase().replace(/<[^>]+>/g, " ").match(/[a-z][a-z'’-]*[a-z]|[a-z]/g) || [])
  .map((w) => w.replace(/[’]/g, "'").replace(/'s$/, ""));

/** Every text a scene puts on screen, before and after its placeholders are filled. */
function texts(scene) {
  return ["kicker", "heading", "caption", "value", "sub", "headline", "primary", "secondary"].map((k) => scene[k]).concat(scene.lines || []).filter(Boolean);
}

export function checkBoard(board, { scriptText = "" } = {}) {
  const built = figures(json("ratecard.json"), json("data/montecarlo.json"), json("data/case-study.json"));
  const facts = board.facts ? json(board.facts) : {};
  const values = { ...built.fill, ...Object.fromEntries(Object.entries(facts).map(([k, v]) => [k, v.value])) };
  const isCase = (k) => (facts[k] ? CASE.test(facts[k].source) : SITE_CASE.has(k));
  const corpus = new Set([...PAGES.flatMap((p) => words(read(p))), ...words(scriptText),
    "hubricon", "com", "learn", "ounce", "ounces", "oz", "p10", "p90", "estimate"]);
  const problems = [];
  for (const s of board.scenes) {
    const keys = texts(s).flatMap((t) => [...String(t).matchAll(/\{\{\s*([a-z0-9_]+)\s*\}\}/g)].map((m) => m[1]));
    for (const k of keys) if (!(k in values)) problems.push(`${s.id}: no figure {{${k}}}`);
    if (problems.length) continue;
    // Spelling: every word on screen is one the site or the approved script already uses.
    for (const t of texts(s)) {
      const unknown = words(fill(t, values)).filter((w) => !corpus.has(w));
      if (unknown.length) problems.push(`${s.id}: words found nowhere on the site or in the script: ${[...new Set(unknown)].join(", ")}`);
    }
    // Numbers typed by hand: on screen, a digit comes from a figure or not at all.
    for (const t of texts(s)) {
      const bare = String(t).replace(/\{\{[^}]+\}\}/g, "").replace(/day 271/gi, "");
      if (/\d/.test(bare)) problems.push(`${s.id}: a number typed into "${t}"; use a figure`);
    }
    // Labels: a case-study figure is shown under its label, and on its own it says "estimate".
    const chart = ["staircase", "montecarlo", "aging"].includes(s.kind);
    if ((keys.some(isCase) || chart) && !(s.proof || chart)) problems.push(`${s.id}: shows a case-study figure without "Modeled from public data · Not a client · Not a result"`);
    if (s.kind === "number" && [...String(s.value).matchAll(/\{\{\s*([a-z0-9_]+)\s*\}\}/g)].some((m) => isCase(m[1]) && !/^(who|who_lower|weight)$/.test(m[1])) && !s.estimate) {
      problems.push(`${s.id}: a case-study number on its own must say "estimate"`);
    }
  }
  return problems;
}

/** Colours, margins and loudness, read from the rendered film. */
export function checkVideo(mp4, board) {
  const problems = [];
  const W = 480, H = 270, margin = { x: Math.round(W * 0.05), y: Math.round(H * 0.05) };
  let t = 0;
  for (const s of board.scenes) {
    t += s.seconds;
    const at = Math.max(0, t - 0.2).toFixed(2);
    const raw = execFileSync("ffmpeg", ["-loglevel", "error", "-ss", at, "-i", mp4, "-frames:v", "1", "-vf", `scale=${W}:${H}`, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], { maxBuffer: 1 << 24 });
    let offHue = 0, inMargin = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 3, r = raw[i] / 255, g = raw[i + 1] / 255, b = raw[i + 2] / 255;
      const max = Math.max(r, g, b), min = Math.min(r, g, b), sat = max ? (max - min) / max : 0;
      if (sat > 0.3 && max > 0.2) {
        let h = max === r ? 60 * (((g - b) / (max - min)) % 6) : max === g ? 60 * ((b - r) / (max - min) + 2) : 60 * ((r - g) / (max - min) + 4);
        if (h < 0) h += 360;
        if (h < 195 || h > 245) offHue++;   // the blue family: compression fringes of #0b5fff land near 200
      }
      const edge = x < margin.x || x >= W - margin.x || y < margin.y || y >= H - margin.y;
      if (edge && 1 - min > 0.1) inMargin++;
    }
    if (offHue > 20) problems.push(`${s.id}: ${offHue} pixels in a colour that is not the one blue`);
    if (inMargin > 4) problems.push(`${s.id}: ${inMargin} pixels of content inside the 5% safe margin`);
  }
  const streams = execFileSync("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", mp4]).toString();
  if (streams.includes("audio")) {
    const log = spawnSync("ffmpeg", ["-nostats", "-i", mp4, "-af", "ebur128=peak=true", "-f", "null", "-"], { encoding: "utf8" }).stderr;
    const I = Number((log.match(/I:\s*(-?[\d.]+) LUFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
    const peak = Number((log.match(/Peak:\s*(-?[\d.]+) dBFS/g) || []).pop()?.match(/-?[\d.]+/)[0]);
    if (!(Math.abs(I + 16) <= 1)) problems.push(`loudness ${I} LUFS; the target is -16 ±1`);
    if (!(peak <= -1)) problems.push(`peak ${peak} dBFS; keep it under -1`);
  }
  return problems;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [boardPath, mp4] = process.argv.slice(2);
  const board = JSON.parse(readFileSync(boardPath, "utf8"));
  const scriptPath = join(ROOT, "content", "videos", board.name, "script.md");
  const moved = drift();
  const problems = [...checkBoard(board, { scriptText: existsSync(scriptPath) ? readFileSync(scriptPath, "utf8") : "" }),
    ...(mp4 ? checkVideo(mp4, board) : []),
    ...(moved && moved.length ? [`the look moved since it was locked: ${moved.join(", ")}`] : [])];
  for (const p of problems) console.log(`- ${p}`);
  const sound = mp4 && execFileSync("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", mp4]).toString().includes("audio");
  console.log(problems.length ? `${problems.length} problem(s)` : "clean: spelling, numbers, labels" + (mp4 ? ", colours, margins" : "") + (sound ? ", loudness" : (mp4 ? " (silent: no loudness to check)" : "")));
  process.exit(problems.length ? 1 : 0);
}
