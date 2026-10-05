// hubricon.com/verify: a Profit Record export, checked in the reader's own browser.
//
// The core below is scripts/verify-record.mjs's core, line for line (the checker every
// export carries as verify-record.mjs; scripts/verify-record.test.mjs fails if the two
// copies differ). Around it, this file only reads the dropped file, re-derives every hash
// with the browser's own Web Crypto as a second opinion, and draws the answer.
//
// Nothing leaves the page: the file is read where it was dropped, and the one request
// is for Hubricon's published head (public_record_seal(), body "{}"), which carries
// nothing of the reader's. There is no analytics script on /verify.

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

// -- reading the file in a browser --------------------------------------------------------

/** deflate-raw, by the browser's own DecompressionStream. */
async function inflateRaw(data) {
  if (typeof DecompressionStream !== "function") throw new Error("this browser cannot open a zip here: unzip the export and drop record-seal.json instead");
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** An export .zip or a record-seal.json, as bytes → the Record. */
export async function readRecord(bytes) {
  const text = new TextDecoder();
  if (bytes.length >= 4 && new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(0, true) === 0x04034b50) {
    const hit = zipEntry(bytes, "record-seal.json");
    if (!hit) throw new Error("this export has no record-seal.json (it predates the Seal)");
    return JSON.parse(text.decode(hit.method === 0 ? hit.data : await inflateRaw(hit.data)));
  }
  return JSON.parse(text.decode(bytes));
}

/**
 * The second opinion: every leaf and every link the core hashed, hashed again by the
 * browser's own SHA-256 (Web Crypto), so nobody has to trust the core's arithmetic.
 * → { agree: true, hashes } | { agree: false, seq } | null when the browser has no Web Crypto.
 */
export async function crossCheck(b) {
  const subtle = globalThis.crypto && globalThis.crypto.subtle;
  if (!subtle || !isObject(b) || !Array.isArray(b.entries)) return null;
  const theirs = async (bytes) => toHex(new Uint8Array(await subtle.digest("SHA-256", bytes)));
  const utf8 = new TextEncoder();
  let hashes = 0;
  const pair = (a, c) => { const both = new Uint8Array(64); both.set(fromHex(a), 0); both.set(fromHex(c), 32); return both; };
  for (const e of b.entries.filter(isObject)) {
    const inputs = [];
    try { if (isObject(e.document)) inputs.push(utf8.encode(canonicalize(e.document))); } catch (err) { /* reported by the check itself */ }
    for (const p of ["prev_head", "global_prev_head"]) if (HEX64.test(e[p] || "") && HEX64.test(e.leaf || "")) inputs.push(pair(e[p], e.leaf));
    for (const bytes of inputs) {
      if (await theirs(bytes) !== sha256(bytes)) return { agree: false, seq: e.seq };
      hashes += 1;
    }
  }
  const g = b.global;
  if (isObject(g) && Array.isArray(g.leaves) && b.entries.length && HEX64.test(b.entries[0].global_prev_head || "")) {
    let h = b.entries[0].global_prev_head;
    for (const leaf of g.leaves) {
      if (!HEX64.test(leaf || "")) break;
      const bytes = pair(h, leaf);
      const mine = sha256(bytes);
      if (await theirs(bytes) !== mine) return { agree: false, seq: null };
      hashes += 1;
      h = mine;
    }
  }
  return { agree: true, hashes };
}

// -- the page ------------------------------------------------------------------------------

export const groups = (hash) => (String(hash || "").match(/.{1,8}/g) || []).join(" ");
const day = (iso) => {
  const t = Date.parse(iso || "");
  return Number.isNaN(t) ? "–" : new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
};
const usd = (s) => (s == null ? "" : `$${Number(s).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const plural = (n, one, many) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
const CHECKS = {
  format: "the file", sequence: "the order", document: "the entry", leaf: "the seal", link: "the chain",
  head: "the chain", global_head: "the chain across clients", client: "the client", entry: "the entry", entry_key: "the entry",
  duplicate: "sealed once", double_entry: "the promise it answers", supersedes: "the correction", evidence: "the evidence",
  evidence_after: "the evidence", global: "the chain across clients", global_count: "the chain across clients", witness: "a witness",
};
const GRADE = { direct: "direct", isolated: "isolated", attributable: "attributable", unmeasurable: "unmeasurable" };

/** What a pasted hash means, in words, given the Record and whether it checked out. */
export function describeFind(state, raw) {
  if (!String(raw || "").trim()) return "Paste a head or a seal first.";
  if (!state.record) return "Load a Record export first. A hash on its own proves nothing: it means something only as a place in a chain this page has just recomputed.";
  if (state.result.status !== "ok") return "This export did not pass the check above, so finding a hash in it would prove nothing. Check it again from a fresh export first.";
  const where = locate(state.record, raw);
  if (!where.readable) return "That is not a head or a seal: a head is 64 characters and a seal is the first 12, each 0 to 9 and a to f.";
  const lead = state.sample ? "In the sample Record (invented, not a client): " : "";
  if (!where.hits.length) {
    return lead + "Not in this Record. Check the characters, and that the page or email came from this client's Record. If both are right, this is not the Record that page or email was made from: a Record rewritten at or before the entry it names cannot pass through it.";
  }
  const lines = where.hits.map((h) => {
    const after = h.of - h.seq;
    if (h.where === "head") {
      return `found. It is this Record's head after entry ${h.seq} of ${h.of}, sealed ${day(h.sealed_at)}. Every entry up to it is exactly what it was when that head was taken` +
        (after ? `; ${plural(after, "entry was", "entries were")} sealed after it.` : ", and nothing has been sealed since.");
    }
    if (h.where === "global_head") return `found in the chain across all clients: the head after global entry ${h.global_seq}, which is this Record's entry ${h.seq}, sealed ${day(h.sealed_at)}.`;
    if (h.where === "global_chain") return `found in the chain across all clients, after global entry ${h.global_seq} of ${h.of_global}: another client's entry, of which this export holds only the fingerprint.`;
    if (h.where === "leaf") return `found: the full seal of entry ${h.seq}, sealed ${day(h.sealed_at)}.`;
    const e = state.record.entries.find((x) => x.seq === h.seq) || {};
    const d = e.document || {};
    return `found: the seal of entry ${h.seq}, the promise called on ${day(d.issued_at || h.sealed_at)}${d.expected_usd != null ? `, expected ${usd(d.expected_usd)}` : ""}. The email that carried this seal and this Record agree.`;
  });
  const text = lines.join(" Also ");
  return lead + text.charAt(0).toUpperCase() + text.slice(1);
}

/** The published head against the export's global section, in words. */
export function describePublished(pub, state) {
  if (!pub || typeof pub.head !== "string") return null;
  if (!state.record || state.result.status !== "ok") return null;
  if (state.sample) return "The sample is invented, so it is not on Hubricon's chain and its global head is not meant to match the published one.";
  const g = state.record.global;
  if (!isObject(g) || !isInt(g.entries)) return "This export carries no chain across clients to compare with the published head.";
  if (g.entries === pub.entries) {
    return g.head === pub.head
      ? `The published head matches the global head in this export, at entry ${g.entries}.`
      : `At entry ${g.entries}, the published head and the global head in this export differ: this export was not made from the chain Hubricon publishes now.`;
  }
  if (g.entries < pub.entries) {
    return `This export covers the chain to entry ${g.entries}; the published head is at entry ${pub.entries}. Joining the two needs the fingerprints in between, which a later export carries: its check shows whether the chain still passes through this one's head.`;
  }
  return `This export claims a chain of ${g.entries} entries, longer than the ${pub.entries} Hubricon publishes. That should not happen; ask Hubricon why.`;
}

const PUBLISHABLE = "sb_publishable_byrEWlQDgM9fDW-2bwIA3w_XA0mrg5X";
const RPC_URL = "https://cgqvdnhgbfxikzdqqaws.supabase.co/rest/v1/rpc/public_record_seal";

function boot() {
  const $ = (id) => document.getElementById(id);
  const state = { record: null, result: null, sample: false, pub: null };
  const sampleText = $("sample-record").textContent;

  const fact = (k, v, isHash) => {
    const dt = document.createElement("dt"); dt.textContent = k;
    const dd = document.createElement("dd"); dd.textContent = isHash ? groups(v) : v;
    if (isHash) dd.className = "hash";
    return [dt, dd];
  };
  const cell = (text, cls) => { const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; return td; };
  const rowOf = (cells) => { const tr = document.createElement("tr"); tr.append(...cells); return tr; };

  function comparePublished() {
    const line = describePublished(state.pub, state);
    $("pub-compare").hidden = !line;
    $("pub-compare").textContent = line || "";
  }

  async function show(record, { sample = false, name = "" } = {}) {
    state.record = record;
    state.sample = sample;
    state.result = verifyBundle(record);
    const r = state.result;
    $("result").hidden = false;
    $("sample-tag").hidden = !sample;
    $("tamper").hidden = !sample;
    $("drop").classList.toggle("loaded", !sample);
    $("drop-title").textContent = sample ? "Drop the Record export here, or tap to choose it." : `${name}: read.`;
    const v = $("verdict"), note = $("verdict-note");
    if (r.status === "unreadable") {
      v.textContent = "Not a Record file.";
      note.textContent = `This file is not a Hubricon Record seal file (${FORMAT}). Drop the export .zip, or the record-seal.json inside it.`;
    } else if (r.status === "empty") {
      v.textContent = "Nothing sealed yet.";
      note.textContent = `This Record has no sealed entries${record.reason ? `: ${record.reason}` : "."}`;
    } else if (r.status === "ok") {
      v.textContent = sample ? "Intact (sample)." : "Intact.";
      note.textContent = `${plural(r.entries, "entry", "entries")}: ${r.called} ${r.called === 1 ? "promise" : "promises"} called${r.late ? ` (${r.late} sealed late, and labelled so)` : ""}, ${r.measured} measured. ` +
        "Every entry hashes to its seal, each follows the one before it, every measurement answers its promise, the evidence is the evidence each was sealed with, and these entries sit where they claim in the chain across all clients.";
    } else {
      const first = r.problems.find((p) => p.seq === r.first_broken_seq) || r.problems[0];
      v.textContent = r.first_broken_seq != null ? `Broken at entry ${r.first_broken_seq}.` : "Broken.";
      note.textContent = `${first.detail.charAt(0).toUpperCase() + first.detail.slice(1)} (${CHECKS[first.check] || first.check}). ` +
        (r.problems.length > 1 ? `${plural(r.problems.length - 1, "other check", "other checks")} failed too, listed below.` : "");
    }

    const facts = [];
    if (r.status !== "unreadable") {
      if (record.client_id) facts.push(fact("Client", record.client_id));
      if (record.generated_at) facts.push(fact("Exported", day(record.generated_at)));
      if (record.head) facts.push(fact("This Record's head", record.head, true));
      if (isObject(record.global) && record.global.head) facts.push(fact(`Global head in this file, entry ${record.global.entries}`, record.global.head, true));
    }
    $("facts").replaceChildren(...facts.flat());

    $("problems-wrap").hidden = !(r.problems && r.problems.length);
    $("problems").replaceChildren(...(r.problems || []).slice(0, 50).map((p) => rowOf([cell(p.seq ?? "the file", "num"), cell(CHECKS[p.check] || p.check), cell(p.detail)])));

    const entries = Array.isArray(record.entries) ? record.entries.filter(isObject) : [];
    $("entries-wrap").hidden = !entries.length;
    $("entries").replaceChildren(...entries.map((e) => {
      const d = isObject(e.document) ? e.document : {};
      const what = d.entry === "called"
        ? `Called: ${d.action_text || d.kind || "a move"}`
        : d.entry === "measured" ? `Measured: ${GRADE[d.grade] || d.grade || "–"}${d.supersedes ? ", a correction" : ""}` : "–";
      const dollars = d.entry === "called" ? (d.expected_usd != null ? `${usd(d.expected_usd)} expected` : "") : (d.measured_usd != null ? usd(d.measured_usd) : "");
      const when = day(d.sealed_at) + (d.sealed === "late" ? " (late)" : "");
      const seal = cell(groups(short(e.leaf) || ""), "hash");
      return rowOf([cell(e.seq ?? "–", "num"), cell(when, "when"), cell(what), cell(dollars, "num"), seal]);
    }));

    const agree = $("agree");
    agree.textContent = "";
    if (r.status === "ok" || r.status === "broken") {
      const second = await crossCheck(record).catch(() => null);
      if (state.record !== record) return;          // another file arrived meanwhile
      if (second == null) agree.textContent = "This browser has no Web Crypto, so the hashes were not computed a second way.";
      else if (second.agree) agree.textContent = `Your browser's own SHA-256 (Web Crypto) computed all ${second.hashes.toLocaleString("en-US")} leaves and links a second time and agrees with this check on every one.`;
      else agree.textContent = `Your browser's own SHA-256 disagrees with this page's at entry ${second.seq ?? "in the chain across clients"}. Do not rely on this page's answer; run verify-record.mjs from the export instead.`;
    }
    comparePublished();
    const pasted = $("hash").value;
    $("found").textContent = pasted.trim() ? describeFind(state, pasted) : "";
  }

  async function loadFile(file) {
    let record;
    try {
      record = await readRecord(new Uint8Array(await file.arrayBuffer()));
    } catch (err) {
      state.record = null; state.result = null; state.sample = false;
      $("result").hidden = false;
      $("sample-tag").hidden = true; $("tamper").hidden = true;
      $("verdict").textContent = "This file could not be read.";
      $("verdict-note").textContent = err.message || "It is not a Record export.";
      $("agree").textContent = "";
      $("facts").replaceChildren(); $("problems-wrap").hidden = true; $("entries-wrap").hidden = true;
      comparePublished();
      return;
    }
    await show(record, { name: file.name });
  }

  const input = $("file"), drop = $("drop");
  input.addEventListener("change", () => input.files[0] && loadFile(input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); const f = e.dataTransfer.files[0]; if (f) loadFile(f); });

  $("try-sample").addEventListener("click", () => show(JSON.parse(sampleText), { sample: true }));
  $("tamper").addEventListener("click", () => {
    // One figure changed in the sample: the second promise's expected dollars, the way an
    // edit after the fact would change them. The seal no longer matches, and the check says where.
    const b = JSON.parse(sampleText);
    b.entries[1].document.expected_usd = "1490.00";
    show(b, { sample: true });
  });

  $("find").addEventListener("submit", (ev) => {
    ev.preventDefault();
    $("found").textContent = describeFind(state, $("hash").value);
  });

  $("pub-cmd").textContent = `curl -s -X POST ${RPC_URL} -H "apikey: ${PUBLISHABLE}" -H "content-type: application/json" -d '{}'`;
  fetch(RPC_URL, {
    method: "POST", body: "{}",
    headers: { apikey: PUBLISHABLE, Authorization: `Bearer ${PUBLISHABLE}`, "content-type": "application/json" },
  }).then((res) => (res.ok ? res.json() : null)).catch(() => null).then((pub) => {
    const el = $("pub");
    if (!pub || typeof pub.head !== "string") {
      el.textContent = "The published head could not be read just now. Anyone can read it the way shown below.";
      return;
    }
    state.pub = pub;
    if (!pub.entries) {
      el.textContent = "Nothing has been sealed on Hubricon's chain yet, so its head is 64 zeros, the point every chain starts from.";
      return;
    }
    el.replaceChildren(
      document.createTextNode(`Entry ${Number(pub.entries).toLocaleString("en-US")}, last sealed ${day(pub.last_sealed_at)}: `),
      Object.assign(document.createElement("span"), { className: "hash", textContent: groups(pub.head) }),
    );
    comparePublished();
  });
}

if (typeof document !== "undefined" && document.getElementById("verify")) boot();
