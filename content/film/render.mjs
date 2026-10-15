// Render a film from scenes on the site's design system, frame by frame.
//
//   node content/film/render.mjs style-reel content/videos/style-reel/style-reel.mp4
//   node content/film/render.mjs <storyboard.json> <out.mp4> [--audio <dir>] [--stills <dir>]
//
// Each scene is a page on /assets/hubricon.css (content/film/scenes.mjs). Headless
// Chrome holds every animation still and steps it to each frame's time, so a frame is
// the same every run; when a scene's motion ends, its last frame is held, not
// re-captured. Frames go to ffmpeg as JPEG. With --audio, a scene lasts as long as
// <dir>/<scene id>.wav (the founder's own take) plus a breath, and the takes are laid
// under the picture in order. --stills writes one PNG per scene at its last frame.
//
// Needs Chrome or Chromium (CHROME_BIN, else Playwright's) and ffmpeg on PATH.
import { createServer } from "node:http";
import { spawn, spawnSync, execFileSync } from "node:child_process";
import { readFileSync, existsSync, mkdirSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { extname, join, dirname } from "node:path";
import { tmpdir, homedir } from "node:os";
import { filmFigures } from "./v3/built.mjs";
import { sceneHTML, STYLE_REEL } from "./scenes.mjs";
import { write as writeTokens } from "./tokens.mjs";
// The look a long film renders in: FILM_LOOK=v3 is the dark archive (content/film/v3/), the
// founder's call of 2026-10-06; anything else is the paper look the visual trial locked.
export const LOOK = process.env.FILM_LOOK === "v3" ? "v3" : "paper";
const { shotHTML } = await import(LOOK === "v3" ? "./v3/shots.mjs" : "./shots.mjs");
export const STAGE = LOOK === "v3" ? "content/film/v3/stage.html" : "content/film/stage.html";
// Each frame: every CSS animation to its time, then the page's own clock (count-ups, type, light).
export const seekJS = (ms) => `document.getAnimations().forEach((a) => { a.currentTime = ${ms}; }); window.__seek && window.__seek(${ms / 1000});`;

const ROOT = new URL("../../", import.meta.url).pathname;
const FPS = 30, W = 1920, H = 1080, BREATH = 0.45;
const json = (p) => JSON.parse(readFileSync(join(ROOT, p), "utf8"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function chromeBin() {
  if (process.env.CHROME_BIN) return process.env.CHROME_BIN;
  const pw = join(homedir(), ".cache/ms-playwright");
  if (existsSync(pw)) {
    const dir = execFileSync("ls", [pw]).toString().split("\n").filter((d) => d.startsWith("chromium-")).sort().pop();
    if (dir) return join(pw, dir, "chrome-linux64/chrome");
  }
  for (const b of ["chromium", "google-chrome", "chrome"]) { try { return execFileSync("which", [b]).toString().trim(); } catch {} }
  throw new Error("no Chrome: set CHROME_BIN");
}

const TYPES = { ".html": "text/html", ".css": "text/css", ".mjs": "text/javascript", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".png": "image/png", ".jpg": "image/jpeg" };
export function serve() {
  return new Promise((resolve) => {
    const srv = createServer((req, res) => {
      const path = join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
      if (!path.startsWith(ROOT) || !existsSync(path)) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" });
      res.end(readFileSync(path));
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

export async function cdp(chrome) {
  // Port 0: Chrome picks a free port and writes it to DevToolsActivePort in its own profile, so
  // parallel renders can never drive each other's browser (a random port once collided).
  const prof = mkdtempSync(join(tmpdir(), "hubricon-film-"));
  // FILM_CHROME_GPU=1 renders on the GPU (filters, 3D and blending are the slow part on a CPU).
  const gpu = process.env.FILM_CHROME_FLAGS ? process.env.FILM_CHROME_FLAGS.split(" ")
    : process.env.FILM_CHROME_GPU === "1"
    ? ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--use-angle=vulkan", "--enable-features=Vulkan,UseSkiaRenderer", "--disable-vulkan-surface"]
    : ["--disable-gpu"];
  const proc = spawn(chrome, ["--headless=new", "--no-sandbox", ...gpu, "--hide-scrollbars", "--force-color-profile=srgb",
    "--remote-debugging-port=0", `--user-data-dir=${prof}`, "about:blank"], { stdio: "ignore" });
  let ws, port;
  for (let i = 0; i < 60 && !ws; i++) {
    try {
      if (!port) port = Number(readFileSync(join(prof, "DevToolsActivePort"), "utf8").split("\n")[0]) || undefined;
      if (!port) throw new Error("not yet");
      const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page");
      if (page) ws = new WebSocket(page.webSocketDebuggerUrl);
    } catch {}
    if (!ws) await sleep(200);
  }
  await new Promise((r, j) => { ws.addEventListener("open", r); ws.addEventListener("error", j); });
  let id = 0; const pending = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async (expression) => {
    const m = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (m.result?.exceptionDetails) throw new Error(m.result.exceptionDetails.exception?.description || "page error");
    return m.result?.result?.value;
  };
  // The profile goes with the browser: a render left one in /tmp every time (136 of them, 2.2 GB).
  return { send, evaluate, close: () => { try { ws.close(); } catch {} proc.kill("SIGKILL");
    setTimeout(() => { try { rmSync(prof, { recursive: true, force: true }); } catch {} }, 300); } };
}

const seconds = (wav) => Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]).toString().trim());

export async function render(board, out, { audio = null, stills = null } = {}) {
  writeTokens();   // the films' tokens follow the site's CSS (VISUAL_SPEC.md §3.1)
  const built = filmFigures();
  // A film's own facts (content/film/facts.mjs) fill its placeholders alongside the site's figures.
  const facts = board.facts ? Object.fromEntries(Object.entries(json(board.facts)).map(([k, v]) => [k, v.value])) : {};
  const scenes = board.scenes.map((s) => {
    const take = audio ? join(audio, `${s.id}.wav`) : null;
    if (take && !existsSync(take)) throw new Error(`no take for scene ${s.id}: ${take}`);
    return { ...s, html: sceneHTML(s, built, facts), take, seconds: take ? seconds(take) + BREATH : s.seconds };
  });
  mkdirSync(dirname(out), { recursive: true });
  if (stills) mkdirSync(stills, { recursive: true });

  const srv = await serve();
  const page = await cdp(chromeBin());
  const silent = out.replace(/\.mp4$/, ".video.mp4");
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", String(FPS), "-i", "-",
    // JPEG frames are full-range; phones expect broadcast-range BT.709, so convert and say so.
    "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-crf", "16", "-preset", "slow",
    "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", audio ? silent : out], { stdio: ["pipe", "inherit", "inherit"] });
  const write = (buf) => new Promise((r) => (ff.stdin.write(buf) ? r() : ff.stdin.once("drain", r)));

  try {
    await page.send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/content/film/stage.html` });
    await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
    let frames = 0;
    for (const s of scenes) {
      // Mount the scene with every animation held at zero, then read when its motion ends.
      const end = await page.evaluate(`(async () => {
        const stage = document.getElementById("stage");
        stage.innerHTML = ${JSON.stringify(s.html)};
        await document.fonts.ready;
        stage.querySelectorAll("[data-play]").forEach((f) => f.classList.add("playing"));
        const anims = document.getAnimations();
        anims.forEach((a) => { a.pause(); a.currentTime = 0; });
        return Math.max(0, ...anims.map((a) => a.effect.getComputedTiming().endTime));
      })()`);
      const total = Math.round(s.seconds * FPS);
      const moving = Math.min(total, Math.ceil((end / 1000) * FPS) + 1);
      let last = null;
      for (let i = 0; i < moving; i++) {
        await page.evaluate(`document.getAnimations().forEach((a) => { a.currentTime = ${(i * 1000) / FPS}; })`);
        const shot = await page.send("Page.captureScreenshot", { format: "jpeg", quality: 94, optimizeForSpeed: true });
        last = Buffer.from(shot.result.data, "base64");
        await write(last);
      }
      if (!last) {
        const shot = await page.send("Page.captureScreenshot", { format: "jpeg", quality: 94, optimizeForSpeed: true });
        last = Buffer.from(shot.result.data, "base64");
        await write(last);
      }
      for (let i = Math.max(moving, 1); i < total; i++) await write(last);
      if (stills) {
        await page.evaluate(`document.getAnimations().forEach((a) => { a.currentTime = ${end}; })`);
        const png = await page.send("Page.captureScreenshot", { format: "png" });
        writeFileSync(join(stills, `${s.id}.png`), Buffer.from(png.result.data, "base64"));
      }
      frames += total;
      console.log(`  ${s.id} ${s.kind.padEnd(10)} ${s.seconds.toFixed(1)}s, ${moving} frames drawn, ${total - moving} held`);
    }
    ff.stdin.end();
    await new Promise((r, j) => ff.on("close", (c) => (c === 0 ? r() : j(new Error(`ffmpeg exited ${c}`)))));
    if (audio) {
      // Each take padded to exactly its scene's length, so the voice never drifts from the
      // picture; then the whole film's loudness measured once and set to -16 LUFS in a
      // second, linear pass (the target content/src/hubricon_content/qa.py holds).
      const work = mkdtempSync(join(tmpdir(), "hubricon-takes-"));
      const padded = scenes.map((s, i) => {
        const p = join(work, `${String(i).padStart(3, "0")}.wav`);
        execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", s.take, "-af", "apad", "-t", (Math.round(s.seconds * FPS) / FPS).toFixed(4), "-ac", "1", "-ar", "48000", p]);
        return p;
      });
      const list = join(work, "takes.txt");
      writeFileSync(list, padded.map((p) => `file '${p}'`).join("\n") + "\n");
      const joined = join(work, "joined.wav");
      execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", joined]);
      const target = "I=-16:TP=-1.5:LRA=11";
      const probe = spawnSync("ffmpeg", ["-hide_banner", "-i", joined, "-af", `loudnorm=${target}:print_format=json`, "-f", "null", "-"], { encoding: "utf8" }).stderr;
      const m = JSON.parse(probe.slice(probe.lastIndexOf("{"), probe.lastIndexOf("}") + 1));
      const second = `loudnorm=${target}:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true`;
      execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", silent, "-i", joined, "-af", `${second},aresample=48000`,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out]);
    }
    console.log(`${out}: ${scenes.length} scenes, ${(frames / FPS).toFixed(1)} s`);
  } finally {
    page.close();
    srv.close();
  }
}

/**
 * A long film's shots, one clip each (VISUAL_SPEC.md §8.3): every frame of every shot is
 * captured, because something always moves (a still's push, a paper shot's drift), so
 * nothing is held frozen. `jobs` come resolved from render_shots.py: figures filled, times
 * relative to the shot's first frame, `out`, `frames`, the grain filter `vf` and the
 * encoder arguments `encode`. Runs on `workers` Chrome pages in parallel.
 */
export async function renderShots(jobs, { workers = 4 } = {}) {
  writeTokens();
  const built = filmFigures();
  const srv = await serve();
  const queue = [...jobs], results = {};
  const worker = async () => {
    const page = await cdp(chromeBin());
    try {
      await page.send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
      await page.send("Page.enable");
      await page.send("Runtime.enable");
      await page.send("Page.navigate", { url: `http://127.0.0.1:${srv.address().port}/${STAGE}` });
      await page.evaluate("new Promise((r) => { const ok = () => document.fonts.ready.then(r); document.readyState === 'complete' ? ok() : addEventListener('load', ok); })");
      while (queue.length) {
        const job = queue.shift();
        results[job.id] = await renderShot(page, job, built);
      }
    } finally {
      page.close();
    }
  };
  try {
    await Promise.all(Array.from({ length: Math.max(1, Math.min(workers, jobs.length)) }, worker));
  } finally {
    srv.close();
  }
  return results;
}

async function renderShot(page, job, built) {
  const html = shotHTML(job, built);
  const info = await page.evaluate(`(async () => {
    const stage = document.getElementById("stage");
    stage.innerHTML = ${JSON.stringify(html)};
    await document.fonts.ready;
    await Promise.all([...stage.querySelectorAll("img")].map((i) => i.decode().catch(() => null)));
    stage.querySelectorAll("[data-play]").forEach((f) => f.classList.add("playing"));
    document.getAnimations().forEach((a) => { a.pause(); a.currentTime = 0; });
    window.__seek && window.__seek(0);
    const sr = stage.querySelector(".split-right"), r = sr?.getBoundingClientRect();
    return { rect: r ? { x: r.x, y: r.y, w: r.width, h: r.height, at: sr.dataset.at ? +sr.dataset.at : null,
                         rot: sr.dataset.rot ? +sr.dataset.rot : 0, grade: sr.dataset.grade || "" } : null,
             broken: [...stage.querySelectorAll("img")].filter((i) => !i.naturalWidth).map((i) => i.getAttribute("src")) };
  })()`);
  if (info.broken.length) throw new Error(`${job.id}: images did not load: ${info.broken.join(", ")}`);
  mkdirSync(dirname(job.out), { recursive: true });
  const vf = ["scale=in_range=pc:out_range=tv", job.vf, "format=yuv420p"].filter(Boolean).join(",");
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", String(FPS), "-i", "-",
    "-vf", vf, "-frames:v", String(job.frames), "-r", String(FPS), ...job.encode, "-movflags", "+faststart", job.out], { stdio: ["pipe", "inherit", "inherit"] });
  const write = (buf) => new Promise((r) => (ff.stdin.write(buf) ? r() : ff.stdin.once("drain", r)));
  const done = new Promise((r, j) => ff.on("close", (c) => (c === 0 ? r() : j(new Error(`ffmpeg exited ${c} on ${job.id}`)))));
  for (let i = 0; i < job.frames; i++) {
    await page.evaluate(seekJS((i * 1000) / FPS));
    const shot = await page.send("Page.captureScreenshot", { format: "jpeg", quality: 95, optimizeForSpeed: true });
    await write(Buffer.from(shot.result.data, "base64"));
  }
  ff.stdin.end();
  await done;
  if (job.still) {
    await page.evaluate(seekJS((job.still_at ?? job.seconds / 2) * 1000));
    const png = await page.send("Page.captureScreenshot", { format: "png" });
    writeFileSync(job.still, Buffer.from(png.result.data, "base64"));
  }
  return { frames: job.frames, rect: info.rect };
}

if (import.meta.url === `file://${process.argv[1]}` && process.argv[2] === "--shots") {
  const jobs = JSON.parse(readFileSync(process.argv[3], "utf8"));
  const wi = process.argv.indexOf("--workers");
  const results = await renderShots(jobs, { workers: wi > 0 ? Number(process.argv[wi + 1]) : 4 });
  process.stdout.write(JSON.stringify(results) + "\n");
} else if (import.meta.url === `file://${process.argv[1]}`) {
  const [what, out, ...rest] = process.argv.slice(2);
  const opt = (k) => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : null; };
  const board = what === "style-reel" ? STYLE_REEL : JSON.parse(readFileSync(what, "utf8"));
  await render(board, out, { audio: opt("--audio"), stills: opt("--stills") });
}
