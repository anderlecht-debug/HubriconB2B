// Pins scripts/verify-record.mjs to values the Python engine produced
// (scripts/record-seal.golden.json, written by engine/scripts/seal_golden.py;
// engine/tests/test_seal.py pins seal.py to the same file). If a byte
// canonicalises one way in Python and another here, one side fails.
//   node --test scripts/verify-record.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { deflateRawSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import {
  FORMAT, GENESIS, SealError, canonicalize, sha256, leafOf, link, verifyBundle, readZipEntry, loadBundle,
} from "./verify-record.mjs";

const golden = JSON.parse(readFileSync(new URL("./record-seal.golden.json", import.meta.url)));
const SCRIPT = fileURLToPath(new URL("./verify-record.mjs", import.meta.url));
const clone = (v) => JSON.parse(JSON.stringify(v));

function mutate(bundle, t) {
  const b = clone(bundle);
  for (const [path, value] of t.set ?? []) {
    let o = b;
    for (const p of path.slice(0, -1)) o = o[p];
    o[path.at(-1)] = value;
  }
  if (t.remove) {
    let o = b;
    for (const p of t.remove.slice(0, -1)) o = o[p];
    o.splice(t.remove.at(-1), 1);
  }
  return b;
}

// A zip the way Python's zipfile writes one (local headers, a central
// directory, the end record), stored or deflated. CRCs are left at zero: the
// reader under test trusts the hashes inside the file, not the archive's.
function zip(files) {
  const parts = [];
  const central = [];
  let offset = 0;
  for (const f of files) {
    const body = f.method === 8 ? deflateRawSync(f.data) : f.data;
    const name = Buffer.from(f.name, "utf8");
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(f.method, 8);
    local.writeUInt32LE(body.length, 18);
    local.writeUInt32LE(f.data.length, 22);
    local.writeUInt16LE(name.length, 26);
    const dir = Buffer.alloc(46);
    dir.writeUInt32LE(0x02014b50, 0);
    dir.writeUInt16LE(20, 4);
    dir.writeUInt16LE(20, 6);
    dir.writeUInt16LE(f.method, 10);
    dir.writeUInt32LE(body.length, 20);
    dir.writeUInt32LE(f.data.length, 24);
    dir.writeUInt16LE(name.length, 28);
    dir.writeUInt32LE(offset, 42);
    parts.push(local, name, body);
    central.push(dir, name);
    offset += 30 + name.length + body.length;
  }
  const cd = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(cd.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, cd, end]);
}

test("canonical JSON is byte-for-byte what the engine hashed", () => {
  for (const c of golden.canonical) {
    assert.equal(canonicalize(c.value), c.canonical);
    assert.equal(sha256(Buffer.from(c.canonical, "utf8")), c.sha256);
  }
});

test("key order is by UTF-16 code unit, and numbers print as ECMAScript prints them", () => {
  // an astral character (U+1F600, a surrogate pair from 0xD83D) sorts before U+FF01
  assert.equal(canonicalize({ "！": 1, "\u{1F600}": 2, b: 3, A: 4 }), '{"A":4,"b":3,"\u{1F600}":2,"！":1}');
  assert.equal(canonicalize([1e21, 1e-7, 1e-6, -0, 100, 5e-324]), "[1e+21,1e-7,0.000001,0,100,5e-324]");
  assert.throws(() => canonicalize(NaN), SealError);
  assert.throws(() => canonicalize(Infinity), SealError);
  assert.throws(() => canonicalize("\ud800"), SealError, "a lone surrogate has no UTF-8 form");
  assert.throws(() => canonicalize({ a: undefined }), SealError);
});

test("the leaves and heads of the golden chain", () => {
  const { documents, leaves, heads } = golden.chain;
  let h = GENESIS;
  documents.forEach((doc, i) => {
    assert.equal(leafOf(doc), leaves[i]);
    h = link(h, leaves[i]);
    assert.equal(h, heads[i]);
  });
  assert.throws(() => link(GENESIS, "abc"), SealError, "a truncated leaf never chains silently");
});

test("the golden export is intact: every entry, the double entry, the evidence, the global chain", () => {
  const r = verifyBundle(golden.export);
  assert.deepEqual(r.problems, []);
  assert.equal(r.status, "ok");
  assert.equal(r.entries, 6);
  assert.equal(r.called, 3);
  assert.equal(r.measured, 3);
  assert.equal(r.global_head, golden.export.global.head);
  assert.equal(golden.export.format, FORMAT);
});

test("each tampering fails at the entry it touched, with the check that caught it", () => {
  for (const t of golden.tampered) {
    const r = verifyBundle(mutate(golden.export, t));
    assert.equal(r.status, "broken", t.name);
    assert.equal(r.first_broken_seq, t.first_broken_seq, t.name);
    assert.ok(r.problems.some((p) => p.check === t.check && p.seq === t.first_broken_seq),
      `${t.name}: expected ${t.check} at ${t.first_broken_seq}, got ${JSON.stringify(r.problems)}`);
  }
});

test("a consistent rewrite verifies on its own and is caught by any witness it could not rewrite", () => {
  const { bundle, witness_that_catches_it, witness_it_still_has } = golden.rewritten;
  assert.equal(verifyBundle(bundle).status, "ok");
  for (const w of witness_that_catches_it) {
    const r = verifyBundle(bundle, [w]);
    assert.equal(r.status, "broken");
    assert.deepEqual(r.problems.map((p) => p.check), ["witness"]);
  }
  assert.equal(verifyBundle(bundle, witness_it_still_has).status, "ok");
  assert.equal(verifyBundle(golden.export, witness_that_catches_it).status, "ok", "the untouched Record holds them");
});

test("the export zip is read directly, stored or deflated", () => {
  const data = Buffer.from(JSON.stringify(golden.export), "utf8");
  for (const method of [0, 8]) {
    const buf = zip([{ name: "MANIFEST.txt", data: Buffer.from("x"), method }, { name: "record-seal.json", data, method }]);
    assert.deepEqual(JSON.parse(readZipEntry(buf, "record-seal.json").toString("utf8")), golden.export);
    assert.equal(readZipEntry(buf, "absent.json"), null);
  }
  assert.throws(() => readZipEntry(Buffer.from("not a zip at all, just text"), "record-seal.json"));
});

test("the command: exit 0 when intact, 1 at the first broken entry, 2 when unreadable", () => {
  const dir = mkdtempSync(join(tmpdir(), "record-seal-"));
  const ok = join(dir, "export.zip");
  writeFileSync(ok, zip([{ name: "record-seal.json", data: Buffer.from(JSON.stringify(golden.export)), method: 8 }]));
  assert.deepEqual(loadBundle(ok), golden.export);
  let run = spawnSync(process.execPath, [SCRIPT, ok, "--list"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.match(run.stdout, /OK — every entry matches its seal/);
  assert.match(run.stdout, /6 entries: 3 called, 3 measured/);

  const broken = join(dir, "record-seal.json");
  writeFileSync(broken, JSON.stringify(mutate(golden.export, golden.tampered[0])));
  run = spawnSync(process.execPath, [SCRIPT, broken], { encoding: "utf8" });
  assert.equal(run.status, 1);
  assert.match(run.stdout, /BROKEN at entry 2/);

  run = spawnSync(process.execPath, [SCRIPT, ok, "--seal", "deadbeefdead"], { encoding: "utf8" });
  assert.equal(run.status, 1, "a seal the Record does not carry is a failure, not a shrug");

  const junk = join(dir, "junk.json");
  writeFileSync(junk, "{\"format\": \"something-else\"}");
  run = spawnSync(process.execPath, [SCRIPT, junk], { encoding: "utf8" });
  assert.equal(run.status, 2);
});
