// The pages and emails a client meets after booking, held to what is true (HUBRICON.md, "What is true
// today") and to the retired vocabulary. The audit of 2026-10-01 found each of these on a client surface.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const words = (html) => html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<!--[\s\S]*?-->/g, " ")
  .replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/\s+/g, " ").replace(/ ([,.;:)])/g, "$1");
const RETIRED = [/\bdesk\b/i, /\bledger\b/i, /\bretainer\b/i, /\bengagement\b/i, /\bdirective/i, /teardown/i, /quantitative/i];

test("the sign-in email: no retired word, no serif, one purpose", () => {
  const html = read("supabase/templates/magic-link.html");
  for (const w of RETIRED) assert.doesNotMatch(words(html), w);
  assert.doesNotMatch(html, /Georgia|Times New Roman|[^-]serif/);
  assert.match(html, /font-family:Inter,/);
  assert.equal((html.match(/<hr /g) || []).length, 1, "one rule");
  assert.match(html, /\{\{ \.ConfirmationURL \}\}/);
});

test("the page after the yes tells one story the rest of the machine keeps", () => {
  const page = words(read("welcome.html"));
  for (const w of RETIRED) assert.doesNotMatch(page, w);
  for (const untrue of [
    /No report exports/i,                       // it asks for exports
    /set you up with a secure upload link/i,    // they already have one
    /welcome email includes/i,                  // the template is on the upload page
    /lets our models read/i,                    // no code reads the seat
    /within 24 hours|Weeks 1–2/i,               // no clock the code does not keep
    /next month is on us/i,                     // terms §9 credits a month, on a condition
  ]) assert.doesNotMatch(page, untrue);
  assert.match(page, /when your core files are in, or 24 hours after your last upload/);
  assert.match(page, /we download them through the seat ourselves, by hand/);
  assert.match(page, /Received, Read or Needs a fix/);
  assert.match(page, /comes back to your bank\./, "kept, with no deadline");
  assert.match(page, /applied when their first invoice is raised after that day and never before/);
});
