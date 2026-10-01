#!/usr/bin/env node
/**
 * Checks a Hubricon Profit Record export offline, with nothing but Node.
 *
 *   node verify-record.mjs <export.zip | record-seal.json> [--seal 3f9a1c0b2e7d]... [--head <64 hex>]... [--list] [--json]
 *
 * Every move on the Profit Record is sealed twice: a "called" entry written
 * before the email that announced it was sent (what was promised, the
 * expected dollars, a SHA-256 of the evidence), and a "measured" entry when
 * it was banked or closed (what it earned, and how we know). This script
 * recomputes all of it from the file:
 *
 *   - each entry's document, in RFC 8785 canonical JSON, hashes to its leaf
 *   - head_n = sha256(head_{n-1} || leaf_n), from 64 zeros, in the client's
 *     chain and in the global chain across every client
 *   - every measurement answers the called entry for the same move, and a
 *     correction names the measurement it replaces
 *   - the evidence in the file hashes to the digests that were sealed
 *   - the client's entries sit where they claim in the global chain, which
 *     leads to the global head Hubricon publishes
 *
 * --seal takes the short seal printed in a pre-move email (the first twelve
 * hex of the promise's leaf): your inbox dated it, so a Record rewritten
 * afterwards cannot contain it. --head takes a global head captured earlier
 * (the public head at some date); a rewritten chain does not pass through it.
 * A chain can be rewritten consistently by whoever holds the database; a
 * witness held by someone else is what makes that evident.
 *
 * Exit 0: intact (or nothing sealed yet). 1: broken — the first broken entry
 * is named. 2: the file could not be read. No dependencies: node:crypto,
 * node:zlib, node:fs. The same checks run in the engine as
 * `hubricon seal verify` (engine/src/hubricon_engine/seal.py).
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";
import { pathToFileURL } from "node:url";

export const FORMAT = "hubricon-record-seal/1";
export const GENESIS = "0".repeat(64);
const HEX64 = /^[0-9a-f]{64}$/;
const LONE_SURROGATE = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;

export class SealError extends Error {}

// RFC 8785. JSON.stringify already prints numbers the way the scheme wants
// (ECMAScript's Number::toString) and escapes strings the way it wants; what
// it does not do is sort keys, refuse what JSON cannot say, or refuse a lone
// surrogate (which has no UTF-8 form, and which the engine refuses too).
export function canonicalize(v) {
  if (v === null) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) throw new SealError(`${v} is not a finite number; JSON has no form for it`);
    return JSON.stringify(v);
  }
  if (typeof v === "string") {
    if (LONE_SURROGATE.test(v)) throw new SealError("a string holds a lone surrogate, which has no UTF-8 form");
    return JSON.stringify(v);
  }
  if (Array.isArray(v)) return "[" + v.map(canonicalize).join(",") + "]";
  if (typeof v === "object") {
    const keys = Object.keys(v).sort();          // UTF-16 code unit order, as the scheme requires
    return "{" + keys.map((k) => canonicalize(k) + ":" + canonicalize(v[k])).join(",") + "}";
  }
  throw new SealError(`${typeof v} has no canonical JSON form`);
}

export const sha256 = (data) => createHash("sha256").update(data).digest("hex");
export const leafOf = (doc) => sha256(Buffer.from(canonicalize(doc), "utf8"));
export const digest = (value) => sha256(Buffer.from(canonicalize(value), "utf8"));
export const short = (leaf) => (leaf ? leaf.slice(0, 12) : null);

export function link(prevHead, leaf) {
  if (typeof prevHead !== "string" || !HEX64.test(prevHead) || typeof leaf !== "string" || !HEX64.test(leaf)) {
    throw new SealError("a head or leaf is not a 64-character lowercase hex SHA-256");
  }
  return sha256(Buffer.concat([Buffer.from(prevHead, "hex"), Buffer.from(leaf, "hex")]));
}

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isInt = (v) => Number.isInteger(v);

/** The same checks, in the same order, as seal.verify_bundle. */
export function verifyBundle(b, witnesses = []) {
  const problems = [];
  const bad = (seq, check, detail) => problems.push({ seq, check, detail });
  if (!isObject(b) || b.format !== FORMAT) {
    return { status: "unreadable", problems: [{ seq: null, check: "format", detail: `not a ${FORMAT} file` }],
      first_broken_seq: null, entries: 0 };
  }
  // A file is data from outside: anything malformed is reported, never thrown on.
  const entries = (Array.isArray(b.entries) ? b.entries : []).map((e) => (isObject(e) ? e : {}));
  const client = b.client_id;
  let prev = GENESIS;
  const calledBy = new Map();
  const measuredBy = new Map();
  const lastMeasured = new Map();
  const keys = new Set();
  const counts = { called: 0, measured: 0, late: 0 };
  const heads = new Set();
  entries.forEach((e, idx) => {
    const i = idx + 1;
    let seq = e.seq;
    if (seq !== i) { bad(i, "sequence", `entry ${i} is numbered ${seq}`); seq = i; }
    const doc = e.document;
    if (!isObject(doc)) {
      bad(seq, "document", "no document: the entry cannot be recomputed");
      prev = e.head;
      return;
    }
    try {
      if (leafOf(doc) !== e.leaf) bad(seq, "leaf", "the document no longer hashes to its seal");
    } catch (err) {
      bad(seq, "leaf", `the document has no canonical form: ${err.message}`);
    }
    if (e.prev_head !== prev) bad(seq, "link", "does not follow the entry before it");
    for (const [p, h] of [["prev_head", "head"], ["global_prev_head", "global_head"]]) {
      try {
        if (link(e[p], e.leaf) !== e[h]) bad(seq, h, `${h} is not sha256(${p} || leaf)`);
      } catch (err) {
        bad(seq, h, err.message);
      }
    }
    heads.add(e.head);
    if (doc.client_id !== client) bad(seq, "client", "sealed for a different client");
    const entry = doc.entry;
    const did = doc.directive_id;
    if (e.entry !== entry) bad(seq, "entry", "the row and its document disagree on what kind of entry this is");
    const want = entry === "called" ? `called:${did}` : entry === "measured" ? `measured:${did}:${doc.measured_at}` : null;
    if (e.entry_key !== want) bad(seq, "entry_key", "the entry's key is not the one its document implies");
    if (keys.has(e.entry_key)) bad(seq, "duplicate", "sealed twice");
    keys.add(e.entry_key);
    if (doc.sealed === "late") counts.late += 1;
    if (entry === "called") {
      counts.called += 1;
      if (calledBy.has(did)) bad(seq, "duplicate", "a second called entry for the same move");
      calledBy.set(did, e.leaf);
    } else if (entry === "measured") {
      counts.measured += 1;
      if (doc.called_leaf == null || calledBy.get(did) !== doc.called_leaf) {
        bad(seq, "double_entry", "does not answer the called entry for this move");
      }
      if ((doc.supersedes ?? null) !== (measuredBy.get(did) ?? null)) {
        bad(seq, "supersedes", "does not name the measurement it replaces");
      }
      measuredBy.set(did, e.leaf);
      lastMeasured.set(did, { seq, doc });
    } else {
      bad(seq, "entry", `unknown entry ${JSON.stringify(entry)}`);
    }
    prev = e.head;
  });
  if (entries.length && b.head !== prev) bad(null, "head", "the Record's head is not its last entry's head");

  const evidence = isObject(b.evidence) ? b.evidence : {};
  entries.forEach((e, idx) => {
    const doc = e.document;
    if (!isObject(doc) || doc.entry !== "called") return;
    const ev = typeof doc.directive_id === "string" && Object.hasOwn(evidence, doc.directive_id)
      ? evidence[doc.directive_id] : null;
    if (!isObject(ev)) return;
    try {
      if (digest(ev.before || {}) !== doc.evidence_sha256) {
        bad(idx + 1, "evidence", "the evidence behind this promise is not the evidence it was sealed with");
      }
    } catch (err) {
      bad(idx + 1, "evidence", err.message);
    }
  });
  for (const [did, m] of lastMeasured) {
    const ev = typeof did === "string" && Object.hasOwn(evidence, did) ? evidence[did] : null;
    if (!isObject(ev)) continue;
    let got;
    try {
      got = ev.after == null ? null : digest(ev.after);
    } catch (err) {
      bad(m.seq, "evidence_after", err.message);
      continue;
    }
    if (got !== (m.doc.after_sha256 ?? null)) {
      bad(m.seq, "evidence_after", "the measurement's evidence is not the evidence it was sealed with");
    }
  }

  const g = b.global;
  const globalHeads = new Set();
  if (isObject(g) && entries.length) {
    const fromSeq = g.from_seq;
    const leaves = Array.isArray(g.leaves) ? g.leaves : [];
    if (!isInt(fromSeq)) {
      bad(null, "global", "the global section does not say where its leaves start");
    } else {
      const at = new Map(entries.map((e, idx) => [e.global_seq, [idx + 1, e]]).filter(([gs]) => isInt(gs)));
      let h = entries[0].global_prev_head;
      try {
        leaves.forEach((leaf, j) => {
          h = link(h, leaf);
          globalHeads.add(h);
          const hit = at.get(fromSeq + j);
          if (hit && (hit[1].leaf !== leaf || hit[1].global_head !== h)) {
            bad(hit[0], "global", `not at global entry ${fromSeq + j} of the chain in this file`);
          }
        });
      } catch (err) {
        bad(null, "global", err.message);
      }
      entries.forEach((e, idx) => {
        const gs = e.global_seq;
        if (!isInt(gs) || !(fromSeq <= gs && gs < fromSeq + leaves.length)) {
          bad(idx + 1, "global", "outside the global leaves in this file");
        }
      });
      if (h !== g.head) bad(null, "global_head", "the global leaves do not lead to the global head in this file");
      if (fromSeq + leaves.length - 1 !== g.entries) {
        bad(null, "global_count", "the global leaves do not cover the chain up to its head");
      }
    }
  }

  for (const raw of witnesses) {
    const w = String(raw).trim().toLowerCase();
    const found = w.length === 64
      ? heads.has(w) || globalHeads.has(w) || (isObject(g) && w === g.head)
      : w.length >= 8 && entries.some((e) => (e.leaf || "").startsWith(w) && e.document?.entry === "called");
    if (!found) bad(null, "witness", `nothing in this Record carries ${w}`);
  }

  const seqs = problems.filter((p) => p.seq !== null && p.seq !== undefined).map((p) => p.seq);
  let status = problems.length ? "broken" : "ok";
  if (!entries.length && !problems.length) status = "empty";
  return { status, entries: entries.length, ...counts, head: b.head,
    global_head: isObject(g) ? g.head : null, first_broken_seq: seqs.length ? Math.min(...seqs) : null, problems };
}

/** One file out of a zip, stored or deflated — enough for the export Python's zipfile writes. */
export function readZipEntry(buf, name) {
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 0xffff); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a zip file");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  if (p === 0xffffffff) throw new Error("a zip64 archive: unzip it and pass record-seal.json");
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Error("the zip's central directory is damaged");
    const method = buf.readUInt16LE(p + 10);
    const size = buf.readUInt32LE(p + 20);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    if (buf.toString("utf8", p + 46, p + 46 + nameLen) === name) {
      if (size === 0xffffffff || local === 0xffffffff) throw new Error("a zip64 entry: unzip it and pass record-seal.json");
      const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
      const data = buf.subarray(start, start + size);
      if (method === 0) return data;
      if (method === 8) return inflateRawSync(data);
      throw new Error(`${name} is compressed with method ${method}, which this script does not read`);
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

export function loadBundle(path) {
  const raw = readFileSync(path);
  if (raw.length >= 4 && raw.readUInt32LE(0) === 0x04034b50) {
    const inner = readZipEntry(raw, "record-seal.json");
    if (!inner) throw new Error("this export has no record-seal.json (it predates the Seal)");
    return JSON.parse(inner.toString("utf8"));
  }
  return JSON.parse(raw.toString("utf8"));
}

function money(s) {
  return s == null ? "—" : `$${Number(s).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function main(argv) {
  const files = [];
  const witnesses = [];
  let list = false;
  let asJson = false;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--seal" || a === "--head") witnesses.push(argv[++i] ?? "");
    else if (a === "--list") list = true;
    else if (a === "--json") asJson = true;
    else if (a === "-h" || a === "--help") { console.log("node verify-record.mjs <export.zip | record-seal.json> [--seal HEX]... [--head HEX]... [--list] [--json]"); return 0; }
    else files.push(a);
  }
  if (files.length !== 1) {
    console.error("usage: node verify-record.mjs <export.zip | record-seal.json> [--seal HEX]... [--head HEX]... [--list] [--json]");
    return 2;
  }
  let b;
  try {
    b = loadBundle(files[0]);
  } catch (err) {
    console.error(`Could not read ${files[0]}: ${err.message}`);
    return 2;
  }
  const r = verifyBundle(b, witnesses);
  if (asJson) {
    console.log(JSON.stringify(r, null, 1));
    return r.status === "ok" || r.status === "empty" ? 0 : r.status === "unreadable" ? 2 : 1;
  }
  if (r.status === "unreadable") {
    console.error(`${files[0]} is not a Hubricon Record seal file (${FORMAT}).`);
    return 2;
  }
  console.log(`Hubricon Profit Record — client ${b.client_id}`);
  if (r.status === "empty") {
    console.log(`Nothing sealed yet${b.reason ? `: ${b.reason}` : "."}`);
    return 0;
  }
  console.log(`  ${r.entries} entries: ${r.called} called${r.late ? ` (${r.late} sealed late)` : ""}, ${r.measured} measured`);
  console.log(`  client head  ${r.head}`);
  if (r.global_head) console.log(`  global head  ${r.global_head} (entry ${b.global.entries}) — compare it with the head Hubricon publishes`);
  if (list) {
    for (const e of b.entries) {
      const d = e.document || {};
      const what = d.entry === "called"
        ? `called   ${d.issued_at?.slice(0, 10) ?? ""}  ${d.kind ?? ""}  expected ${money(d.expected_usd)}  seal ${short(e.leaf)}`
        : `measured ${d.measured_at?.slice(0, 10) ?? ""}  ${d.grade ?? ""}  ${money(d.measured_usd)}  answers ${short(d.called_leaf)}`;
      console.log(`  ${String(e.seq).padStart(4)}  ${what}${d.sealed === "late" ? "  (sealed late)" : ""}`);
    }
  }
  if (r.status === "ok") {
    console.log("OK — every entry matches its seal, the chain is unbroken, every measurement answers its promise"
      + (witnesses.length ? ", and every witness you gave is in it." : "."));
    return 0;
  }
  const first = r.first_broken_seq;
  console.log(`BROKEN ${first != null ? `at entry ${first}` : "(the file as a whole)"}:`);
  for (const p of r.problems.slice(0, 20)) console.log(`  ${String(p.seq ?? "—").padStart(5)}  ${p.check.padEnd(16)} ${p.detail}`);
  if (r.problems.length > 20) console.log(`  … and ${r.problems.length - 20} more`);
  return 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main(process.argv.slice(2));
}
