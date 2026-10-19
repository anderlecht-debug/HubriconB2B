// Writes the design tokens into /assets/hubricon.css from /assets/tokens.mjs.
//
//   node scripts/build-tokens.mjs
//
// The stylesheet's :root and .night rules sit between the tokens:begin and
// tokens:end comments and are only ever written by this script. Change a value in
// tokens.mjs, run this, commit both. scripts/tokens.test.mjs fails if they differ.

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { CSS, NIGHT } from "../assets/tokens.mjs";

const ROOT = new URL("../", import.meta.url);
export const STYLESHEET = fileURLToPath(new URL("assets/hubricon.css", ROOT));
const BEGIN = "/* tokens:begin.";
const END = "/* tokens:end */";

/** The generated block, markers included. */
export function tokenBlock() {
  const out = [
    `${BEGIN} Generated from /assets/tokens.mjs by \`node scripts/build-tokens.mjs\`.`,
    "   Edit the values there, never here: scripts/tokens.test.mjs fails if the two differ. */",
    ":root {",
  ];
  CSS.forEach(([group, rows], g) => {
    if (g) out.push("");
    out.push(`  /* ${group} */`);
    for (const row of rows) {
      if (!row) { out.push(""); continue; }
      const [name, value, note] = row;
      const decl = `  --${name}: ${value};`;
      out.push(note ? `${decl.padEnd(37)}/* ${note} */` : decl);
    }
  });
  out.push("}", "");
  out.push("/* A dark section is the same system with the ink and paper swapped, so every");
  out.push("   component and chart inside it needs no second style. */");
  out.push(".night {");
  for (const [name, from] of NIGHT) out.push(`  --${name}: var(--${from});`);
  out.push("  background: var(--paper);", "  color: var(--ink-2);", "}", END);
  return out.join("\n");
}

/** The stylesheet with its token block replaced. */
export function withTokens(css) {
  const b = css.indexOf(BEGIN), e = css.indexOf(END);
  if (b < 0 || e < 0 || e < b) throw new Error("hubricon.css has no tokens:begin … tokens:end block");
  return css.slice(0, b) + tokenBlock() + css.slice(e + END.length);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const before = readFileSync(STYLESHEET, "utf8");
  const after = withTokens(before);
  if (after === before) console.log("hubricon.css: tokens already current");
  else { writeFileSync(STYLESHEET, after); console.log("hubricon.css: tokens rewritten from assets/tokens.mjs"); }
}
