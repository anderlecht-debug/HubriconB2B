// Every key the project reads is in .env.example, so the founder can fill them
// all in one sitting and the list cannot quietly fall behind the code again
// (2026-10-04: INSTANTLY_API_KEY, CALENDLY_URL and the review email were read by
// code that no example mentioned).
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const example = readFileSync(join(root, ".env.example"), "utf8");
const named = new Set([...example.matchAll(/^#?\s*([A-Z][A-Z0-9_]{2,})=/gm)].map(([, n]) => n));

// Read by the runtime or the machine, never set by hand.
const NOT_SETTINGS = new Set(["GITHUB_ACTIONS", "TMPDIR", "HOME", "PATH", "NODE_ENV", "VERCEL_ENV", "PORT"]);

// The Amazon harvest's knobs. Its steps are off (Amazon refuses automated reads,
// 2026-10-01), so they keep their defaults in code and are not put to the founder.
const AMAZON_OFF = new Set(["HARVEST_AMAZON_CLIENT", "HARVEST_CATEGORIES_PER_RUN", "HARVEST_DEPTH",
  "HARVEST_ENRICH_LIMIT", "HARVEST_LISTINGS_LIMIT", "HARVEST_LISTINGS_MAX_ASINS", "HARVEST_LISTINGS_PER_SELLER",
  "HARVEST_MAX_ASIN_MONTHLY_REVENUE", "HARVEST_MAX_PRODUCTS", "HARVEST_MAX_RATINGS_12MO",
  "HARVEST_MAX_RATINGS_LIFETIME", "HARVEST_MIN_MONTHLY_REVENUE", "HARVEST_MIN_RATINGS_12MO",
  "HARVEST_OWNER_LOOKUPS_DAILY", "HARVEST_PROFILES_LIMIT", "HARVEST_PUSH_LIMIT", "HARVEST_REQUALIFY_LIMIT",
  "HARVEST_REVENUE_PER_RATING", "HARVEST_RUN_ALL_LISTINGS", "HARVEST_SUBCATS", "HARVEST_WAYBACK_INTERVAL",
  "HARVEST_WAYBACK_LIMIT", "HARVEST_WAYBACK_WORKERS"]);

function walk(dir, exts, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".") || name === "__pycache__" || name === "archive") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, exts, out);
    else if (exts.some((e) => name.endsWith(e))) out.push(p);
  }
  return out;
}

function readNames() {
  const names = new Set();
  const js = [...walk(join(root, "api"), [".js"]), ...walk(join(root, "lib"), [".js"]),
              ...walk(join(root, "scripts"), [".mjs", ".js"])].filter((p) => !p.endsWith(".test.mjs"));
  for (const p of js) for (const m of readFileSync(p, "utf8").matchAll(/process\.env\.([A-Z][A-Z0-9_]+)|\benv\.([A-Z][A-Z0-9_]{3,})/g)) names.add(m[1] ?? m[2]);
  for (const p of walk(join(root, "engine/src"), [".py"])) {
    for (const [, n] of readFileSync(p, "utf8").matchAll(/(?:environ\.get|getenv|environ\[)\(?\s*["']([A-Z][A-Z0-9_]+)["']/g)) names.add(n);
  }
  return names;
}

// Read on the content branch (HubriconB2B-content), which loads this same .env.
const CONTENT = ["PEXELS_API_KEY", "PIXABAY_API_KEY", "SMITHSONIAN_API_KEY", "CONTENT_CONTACT_EMAIL",
  "CONTENT_REVIEW_EMAIL", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL",
  "ELEVENLABS_STABILITY", "ELEVENLABS_SIMILARITY", "ELEVENLABS_STYLE", "CONTENT_WHISPER_MODEL", "CONTENT_WHISPER_DEVICE"];

// The keys the founder was asked for on 2026-10-03/04, used by Claude to finish the setup.
const SETUP = ["STRIPE_SECRET_KEY", "VERCEL_TOKEN", "SUPABASE_ACCESS_TOKEN", "GITHUB_DISPATCH_TOKEN",
  "GITHUB_DISPATCH_REPO", "CALENDLY_TOKEN"];

test("every variable the main code reads is named in .env.example", () => {
  const missing = [...readNames()].filter((n) => !NOT_SETTINGS.has(n) && !AMAZON_OFF.has(n) && !named.has(n)).sort();
  assert.deepEqual(missing, [], `read by code but not in .env.example: ${missing.join(", ")}`);
});

test("the content pipeline's keys and the setup keys are named too", () => {
  for (const n of [...CONTENT, ...SETUP]) assert.ok(named.has(n), `${n} is missing from .env.example`);
});

test("the example holds no secret value, and no Mac-only wording", () => {
  for (const line of example.split("\n").filter((l) => /^[A-Z][A-Z0-9_]+=/.test(l))) {
    const [name, ...rest] = line.split("=");
    const value = rest.join("=");
    if (/(KEY|TOKEN|SECRET)$/.test(name)) assert.equal(value, "", `${name} must be blank in the example`);
  }
  assert.doesNotMatch(example, /\bthe Mac\b|founder's Mac|launchd/i);
  assert.match(example, /client_secret\.json/, "the YouTube OAuth file is part of the one sitting");
});
