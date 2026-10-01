// Freeze the films' look once the founder has approved it (HUBRICON_SPEC.md: produce the
// first explainer, then freeze the style and reuse it across every one after). The look
// is four files; the lock is their fingerprints. check.mjs reports any film rendered
// after one of them moved.
//
//   node content/film/lock.mjs            write the lock (the founder's call, once)
//   node content/film/lock.mjs --verify   exit 1 if the look has moved since
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../../", import.meta.url).pathname;
export const LOOK = ["assets/hubricon.css", "assets/charts.mjs", "content/film/film.css", "content/film/scenes.mjs"];
export const LOCK = join(ROOT, "content/assets/film-style-lock.json");

export const fingerprints = () => Object.fromEntries(LOOK.map((p) => [p, createHash("sha256").update(readFileSync(join(ROOT, p))).digest("hex")]));

/** The files whose look moved since the lock, or null when there is no lock yet. */
export function drift() {
  if (!existsSync(LOCK)) return null;
  const lock = JSON.parse(readFileSync(LOCK, "utf8")), now = fingerprints();
  return LOOK.filter((p) => lock.files[p] !== now[p]);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv.includes("--verify")) {
    const d = drift();
    console.log(d === null ? "no lock yet: the look is not frozen" : d.length ? `the look moved since the lock: ${d.join(", ")}` : "the look is as locked");
    process.exit(d && d.length ? 1 : 0);
  }
  writeFileSync(LOCK, JSON.stringify({ locked_on: new Date().toISOString().slice(0, 10), from: "content/videos/style-reel", files: fingerprints() }, null, 2) + "\n");
  console.log(`locked: ${LOCK}`);
}
