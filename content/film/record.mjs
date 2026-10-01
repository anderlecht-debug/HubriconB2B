// The founder's own voice, one beat at a time (HUBRICON_SPEC.md: record in my own voice
// now, the clone later). A teleprompter in the browser on this machine: it shows the
// approved script beat by beat with every figure filled in, records a take, plays it
// back, and keeps it as content/videos/<slug>/takes/<beat>.wav, which is what
// `render.mjs <board> --audio <takes>` times each scene to.
//
//   node content/film/record.mjs <slug>        then open the address it prints
//
// It opens only for a script whose review gate is approved: nothing is recorded, like
// nothing is rendered, before the founder has said yes to the words.
import { createServer } from "node:http";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../../", import.meta.url).pathname;
const CONTENT = join(ROOT, "content");

/** The beats of a script.md, each with its narration and every {{key}} filled from facts. */
export function beats(scriptText, facts) {
  const out = [];
  let cur = null;
  for (const line of scriptText.split("\n")) {
    const head = line.match(/^\[(\d+):(\d\d)\]\s*(.*)$/);
    if (head) { cur = { id: `b${out.length + 1}`, at: Number(head[1]) * 60 + Number(head[2]), name: head[3].trim(), text: "" }; out.push(cur); continue; }
    const vo = line.match(/^\s+VO:\s*(.*)$/);
    if (vo && cur) cur.text = vo[1].replace(/\{\{\s*([a-z0-9_]+)\s*\}\}/g, (_, k) => {
      if (!facts[k]) throw new Error(`no fact ${k}`);
      return facts[k].value;
    });
    if (/^(RE-HOOK AUDIT|DERIVED ASSETS):/.test(line)) cur = null;
  }
  return out.filter((b) => b.text);
}

function approved(slug) {
  const q = JSON.parse(readFileSync(join(CONTENT, "queue.json"), "utf8"));
  const u = q.units.find((x) => x.slug === slug || x.id === slug);
  return u && u.steps && u.steps.review === "approved";
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const slug = process.argv[2];
  const dir = join(CONTENT, "videos", slug || "");
  if (!slug || !existsSync(join(dir, "script.md"))) { console.error("usage: node content/film/record.mjs <slug>"); process.exit(2); }
  if (!approved(slug) && !process.argv.includes("--rehearse")) {
    console.error(`${slug}: the script is not approved yet. Approve it first: hubricon-content approve ${slug}`);
    process.exit(1);
  }
  const facts = JSON.parse(readFileSync(join(dir, "facts.json"), "utf8"));
  const list = beats(readFileSync(join(dir, "script.md"), "utf8"), facts);
  const takes = join(dir, "takes");
  mkdirSync(takes, { recursive: true });
  const kept = () => readdirSync(takes).filter((f) => f.endsWith(".wav")).map((f) => f.replace(/\.wav$/, ""));

  const srv = createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    const send = (code, type, body) => { res.writeHead(code, { "content-type": type, "cache-control": "no-store" }); res.end(body); };
    if (req.method === "GET" && url.pathname === "/") return send(200, "text/html", readFileSync(join(CONTENT, "film", "record.html")));
    if (req.method === "GET" && url.pathname.startsWith("/assets/")) return send(200, "text/css", readFileSync(join(ROOT, url.pathname)));
    if (req.method === "GET" && url.pathname === "/beats.json") return send(200, "application/json", JSON.stringify({ slug, rehearsal: !approved(slug), beats: list, kept: kept() }));
    const take = url.pathname.match(/^\/take\/(b\d+)$/);
    if (req.method === "POST" && take && !approved(slug)) return send(403, "application/json", JSON.stringify({ error: "the script is not approved; takes are not kept" }));
    if (req.method === "POST" && take && list.some((b) => b.id === take[1])) {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        const raw = join(takes, `${take[1]}.webm`);
        writeFileSync(raw, Buffer.concat(chunks));
        // Mono, 48 kHz, the room left in: loudness is set once, on the whole film, at assembly.
        execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", raw, "-ac", "1", "-ar", "48000", join(takes, `${take[1]}.wav`)]);
        send(200, "application/json", JSON.stringify({ ok: true, kept: kept() }));
      });
      return;
    }
    send(404, "text/plain", "not found");
  });
  srv.listen(Number(process.env.PORT || 8790), "127.0.0.1", () => {
    console.log(`Recording ${slug}: ${list.length} beats. Open http://127.0.0.1:${srv.address().port}/ in Chrome.`);
    console.log(`Takes land in ${takes}. Then: node content/film/render.mjs content/videos/${slug}/board.json content/videos/${slug}/media/master.mp4 --audio ${takes}`);
  });
}
