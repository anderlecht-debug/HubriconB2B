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
 * is named. 2: the file could not be read. No dependencies: node:fs and
 * node:zlib for reading the file; everything else is the core below. The same
 * checks run in the engine as `hubricon seal verify`
 * (engine/src/hubricon_engine/seal.py).
 *
 * The core, between the two "core" lines, is plain JavaScript with no Node in
 * it, and hubricon.com/verify (assets/verify.js) runs the same bytes in a
 * browser; scripts/verify-record.test.mjs fails if the two copies differ.
 * SHA-256 is computed here, in the core, so both run one implementation; the
 * page then re-derives every leaf and link with the browser's own Web Crypto,
 * and the tests hold this one to Node's and Python's.
 */
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";
import { pathToFileURL } from "node:url";

// ---- core: begin (assets/verify.js carries these lines byte for byte) ----
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

// SHA-256 (FIPS 180-4), in full: the first 32 bits of the fractional parts of
// the cube roots of the first 64 primes, then of the square roots of the first 8.
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
const H0 = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
const rotr = (x, n) => (x >>> n) | (x << (32 - n));

/** SHA-256 of bytes, as 32 bytes. */
export function sha256Bytes(msg) {
  const n = msg.length;
  const blocks = new Uint8Array((((n + 8) >> 6) + 1) << 6);
  blocks.set(msg);
  blocks[n] = 0x80;
  const view = new DataView(blocks.buffer);
  view.setUint32(blocks.length - 8, Math.floor(n / 0x20000000));   // the length in bits, high word
  view.setUint32(blocks.length - 4, (n << 3) >>> 0);                // and low word
  const h = H0.slice();
  const w = new Uint32Array(64);
  for (let at = 0; at < blocks.length; at += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(at + 4 * i);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, k] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (k + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      k = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    [a, b, c, d, e, f, g, k].forEach((x, i) => { h[i] = (h[i] + x) | 0; });
  }
  const out = new Uint8Array(32);
  const ov = new DataView(out.buffer);
  h.forEach((x, i) => ov.setUint32(4 * i, x >>> 0));
  return out;
}

const UTF8 = new TextEncoder();
export const toHex = (bytes) => Array.from(bytes, (x) => x.toString(16).padStart(2, "0")).join("");
export const fromHex = (hex) => Uint8Array.from(hex.match(/../g) || [], (x) => parseInt(x, 16));
/** sha256 of bytes, or of a string's UTF-8, as lowercase hex. */
export const sha256 = (data) => toHex(sha256Bytes(typeof data === "string" ? UTF8.encode(data) : data));
export const leafOf = (doc) => sha256(canonicalize(doc));
export const digest = (value) => sha256(canonicalize(value));
export const short = (leaf) => (leaf ? leaf.slice(0, 12) : null);

export function link(prevHead, leaf) {
  if (typeof prevHead !== "string" || !HEX64.test(prevHead) || typeof leaf !== "string" || !HEX64.test(leaf)) {
    throw new SealError("a head or leaf is not a 64-character lowercase hex SHA-256");
  }
  const both = new Uint8Array(64);
  both.set(fromHex(prevHead), 0);
  both.set(fromHex(leaf), 32);
  return sha256(both);
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

/** A hash as people copy it: a printed head comes in groups of eight, maybe quoted. */
export const cleanHash = (raw) => String(raw ?? "").replace(/[\s"'`‘’“”]/g, "").toLowerCase();

/**
 * Every place a hash from elsewhere sits in this Record: a head printed on a
 * page of the Record (the client's chain, or the global one), a seal printed in
 * an email (the first twelve hex of a promise's leaf), or a whole leaf. It says
 * where the file carries the hash and nothing more; whether that means anything
 * depends on the file having verified first, which is the caller's to say.
 */
export function locate(b, raw) {
  const h = cleanHash(raw);
  if (!/^[0-9a-f]+$/.test(h) || h.length < 8 || h.length > 64) return { hash: h, readable: false, hits: [] };
  const entries = isObject(b) && Array.isArray(b.entries) ? b.entries.filter(isObject) : [];
  const hits = [];
  const add = (where, e, extra = {}) => hits.push({
    where, seq: e ? e.seq : null, global_seq: e ? e.global_seq : null, entry: e?.document?.entry ?? null,
    sealed_at: e?.document?.sealed_at ?? null, of: entries.length, ...extra,
  });
  const ours = new Set();
  for (const e of entries) {
    if (h.length === 64) {
      if (e.head === h) add("head", e);
      if (e.global_head === h) { add("global_head", e); ours.add(e.global_seq); }
      if (e.leaf === h) add("leaf", e);
    } else if (typeof e.leaf === "string" && e.leaf.startsWith(h) && e.document?.entry === "called") {
      add("seal", e);
    }
  }
  const g = isObject(b) ? b.global : null;
  if (h.length === 64 && isObject(g) && Array.isArray(g.leaves) && isInt(g.from_seq) && entries.length) {
    let chain = entries[0].global_prev_head;
    try {
      g.leaves.forEach((leaf, j) => {
        chain = link(chain, leaf);
        if (chain === h && !ours.has(g.from_seq + j)) add("global_chain", null, { global_seq: g.from_seq + j, of_global: g.entries });
      });
    } catch (err) { /* a malformed global section is verifyBundle's to report */ }
  }
  return { hash: h, readable: true, hits };
}

/** One file out of a zip, as { method, data }: stored (0) or deflated (8), still compressed. */
export function zipEntry(bytes, name) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const u16 = (i) => view.getUint16(i, true);
  const u32 = (i) => view.getUint32(i, true);
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 0xffff); i--) {
    if (u32(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a zip file");
  const count = u16(eocd + 10);
  let p = u32(eocd + 16);
  if (p === 0xffffffff) throw new Error("a zip64 archive: unzip it and pass record-seal.json");
  const names = new TextDecoder();
  for (let n = 0; n < count; n++) {
    if (p + 46 > bytes.length || u32(p) !== 0x02014b50) throw new Error("the zip's central directory is damaged");
    const method = u16(p + 10);
    const size = u32(p + 20);
    const nameLen = u16(p + 28);
    const extraLen = u16(p + 30);
    const commentLen = u16(p + 32);
    const local = u32(p + 42);
    if (names.decode(bytes.subarray(p + 46, p + 46 + nameLen)) === name) {
      if (size === 0xffffffff || local === 0xffffffff) throw new Error("a zip64 entry: unzip it and pass record-seal.json");
      const start = local + 30 + u16(local + 26) + u16(local + 28);
      if (method !== 0 && method !== 8) throw new Error(`${name} is compressed with method ${method}, which this script does not read`);
      return { method, data: bytes.subarray(start, start + size) };
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}
// ---- core: end ----

/** One file out of a zip, stored or deflated — enough for the export Python's zipfile writes. */
export function readZipEntry(buf, name) {
  const hit = zipEntry(buf, name);
  if (!hit) return null;
  return hit.method === 0 ? Buffer.from(hit.data) : inflateRawSync(hit.data);
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
