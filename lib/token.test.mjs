// One link, one job: each page resolves a token only for its own purpose, and
// falls back to the old resolver only while the migration is not yet applied.
//   node --test lib/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolveTokenFor, isMissingFunction } from "./token.js";

const TOKEN = "x".repeat(32);
const row = { client_id: "c1", company_name: "Alpha" };

function db(handlers) {
  const calls = [];
  return { calls, rpc: async (name, params) => { calls.push([name, params]); return handlers[name](params); } };
}

test("a token resolves only for the purpose the page names", async () => {
  const d = db({ validate_token_for: ({ p_purpose }) => ({ data: p_purpose === "upload" ? [row] : [], error: null }) });
  assert.deepEqual(await resolveTokenFor(d, TOKEN, "upload"), row);
  assert.equal(await resolveTokenFor(d, TOKEN, "consent"), null);
  assert.deepEqual(d.calls.map(([n]) => n), ["validate_token_for", "validate_token_for"]);
});

test("before the migration, the old resolver answers as it always did", async () => {
  const d = db({
    validate_token_for: () => ({ data: null, error: { code: "PGRST202", message: "Could not find the function public.validate_token_for" } }),
    validate_intake_token: () => ({ data: [row], error: null }),
  });
  assert.deepEqual(await resolveTokenFor(d, TOKEN, "consent"), row);
});

test("any other database error resolves nothing, never the fallback", async () => {
  const d = db({ validate_token_for: () => ({ data: null, error: { code: "57014", message: "timeout" } }) });
  assert.equal(await resolveTokenFor(d, TOKEN, "upload"), null);
  assert.equal(d.calls.length, 1);
  assert.equal(isMissingFunction({ code: "42883" }), true);
});

test("malformed tokens never reach the database", async () => {
  const d = db({});
  assert.equal(await resolveTokenFor(d, "short", "upload"), null);
  assert.equal(d.calls.length, 0);
  await assert.rejects(resolveTokenFor(d, TOKEN, "anything"));
});

test("the upload page asks for upload links and the consent page for consent links", () => {
  const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
  assert.match(read("api/intake.js"), /resolveTokenFor\(db, [^,]+, "upload"\)/);
  assert.match(read("api/consent.js"), /resolveTokenFor\(db, [^,]+, "consent"\)/);
  for (const p of ["api/intake.js", "api/consent.js"]) assert.doesNotMatch(read(p), /validate_intake_token/, p);
  const sql = read("supabase/migrations/20261001000007_token_purpose.sql");
  assert.match(sql, /and purpose = 'upload'\s+and revoked_at is null/, "rotating upload links spares consent links");
  assert.match(sql, /label ilike 'consent%'/, "referral.py's 'consent link' label sets the purpose");
});
