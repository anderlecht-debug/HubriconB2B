// One link, one job: an upload link (/intake) and a consent link (/say) each
// resolve only for their own purpose (migration 20261001000007_token_purpose.sql,
// privacy.html §5: "upload links are single-purpose").
//
// Until that migration is applied the database has no validate_token_for, and
// the old resolver answers for every token as before; once it is applied the old
// resolver answers for upload links only, so neither order of deploy and
// migration lets an upload link open the consent page for longer than the gap.
import { createHash } from "node:crypto";

export const PURPOSES = ["upload", "consent"];

// PostgREST's "function not found" (PGRST202) or Postgres's undefined_function (42883).
export function isMissingFunction(error) {
  if (!error) return false;
  return error.code === "PGRST202" || error.code === "42883" || /could not find the function/i.test(error.message || "");
}

export async function resolveTokenFor(db, token, purpose) {
  if (!PURPOSES.includes(purpose)) throw new Error(`unknown token purpose: ${purpose}`);
  if (typeof token !== "string" || token.length < 20 || token.length > 200) return null;
  const hash = createHash("sha256").update(token).digest("hex");
  let { data, error } = await db.rpc("validate_token_for", { p_token_hash: hash, p_purpose: purpose });
  if (isMissingFunction(error)) {
    ({ data, error } = await db.rpc("validate_intake_token", { p_token_hash: hash }));
  }
  if (error || !data || data.length === 0) return null;
  return data[0]; // { client_id, company_name }
}
