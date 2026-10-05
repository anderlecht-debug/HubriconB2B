// Where a visitor first came from (assets/site.js sourceFrom): the code a film's link carries
// rides the booking, so the spec's phase-2 gate, booked calls from published content, can be
// counted. Only a short code is ever kept.
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// site.js touches the page at import; its pure function is read out of the file and run alone.
const js = readFileSync(new URL("../assets/site.js", import.meta.url), "utf8");
const body = js.slice(js.indexOf("export const SOURCE_OK"), js.indexOf("export function sourceCode"));
const { sourceFrom, SOURCE_OK } = new Function(`${body.replace(/export /g, "")}; return { sourceFrom, SOURCE_OK };`)();

test("a film's own link code is kept as it is, lower-cased", () => {
  assert.equal(sourceFrom("?src=YT-F02", "", "hubricon.com"), "yt-f02");
  assert.equal(sourceFrom("?src=li-v01&utm_source=linkedin", "", "hubricon.com"), "li-v01", "src wins over utm tags");
});

test("without a code, utm tags or another site's referral stand in; our own pages never do", () => {
  assert.equal(sourceFrom("?utm_source=YouTube&utm_campaign=Holiday Fees", "", "hubricon.com"), "youtube.holiday-fees");
  assert.equal(sourceFrom("", "https://www.youtube.com/watch?v=abc", "hubricon.com"), "ref.youtube.com");
  assert.equal(sourceFrom("", "https://www.hubricon.com/learn", "hubricon.com"), "");
  assert.equal(sourceFrom("?utm_source=hubricon&utm_medium=gate", "", "hubricon.com"), "", "the site's own booking tag is not a source");
});

test("nothing but a short, plain code is ever kept", () => {
  for (const code of [sourceFrom("?src=" + "x".repeat(200), "", "hubricon.com"), sourceFrom("?src=<script>", "", "hubricon.com"), sourceFrom("?src=a b%40c.com", "", "hubricon.com")]) {
    assert.ok(code === "" || SOURCE_OK.test(code), code);
    assert.ok(code.length <= 48);
    assert.doesNotMatch(code, /[<>@\s]/);
  }
  assert.match(js, /localStorage\.setItem\(SOURCE_KEY/, "kept in this browser only");
  assert.match(js, /src: sourceCode\(\) \|\| "direct"/, "the call's clicks say where the visitor came from");
});

test("the booking carries the source, and the engine reads it back", () => {
  const apply = readFileSync(new URL("../apply.html", import.meta.url), "utf8");
  assert.match(apply, /localStorage\.getItem\("hubricon_src"\)/, "/apply reads the code site.js keeps");
  assert.match(apply, /\(src \? `\|src:\$\{src\}` : ""\)/, "and appends it to the booking's utm_content");
  assert.ok(apply.includes(SOURCE_OK.source), "with the same rule for what a code may be");
  const py = readFileSync(new URL("../engine/src/hubricon_engine/referral.py", import.meta.url), "utf8");
  assert.match(py, /def source_from_answers/);
  assert.match(py, /src\\s\*\[:=\]/, "the engine parses the same src: token");
});
