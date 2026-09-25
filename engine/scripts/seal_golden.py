"""Golden values for the Seal, produced by the Python engine.

    cd engine && uv run python scripts/seal_golden.py

Writes ../scripts/record-seal.golden.json. `node --test scripts/verify-record.test.mjs`
pins the dependency-free verifier to it, and engine/tests/test_seal.py pins
seal.py to it, so a byte that canonicalises one way in Python and another in
JavaScript fails on both sides. Regenerate only when the canonical form or the
document format changes on purpose — and then bump seal.VERSION, because every
seal already written was computed under the old one.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hubricon_engine import seal  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "scripts" / "record-seal.golden.json"

# Values chosen to break a careless canonicaliser: key order by UTF-16 code
# unit (an astral character sorts before U+FF01), numbers at every ECMAScript
# layout boundary, -0, an integer past 2**53, and every escape JSON has.
CANONICAL_CASES = [
    {"b": 1, "a": 2, "A": 3, "é": 4, "€": 5, "\U0001F600": 6, "！": 7, "": 8, "10": 9, "9": 10},
    [0.1, 0.30000000000000004, 1e21, 1e20, 1e-7, 1e-6, 5e-324, 1.7976931348623157e308, -0.0, 100.0,
     2.5, -1.25e-8, 123456789012345680000.0, 0.000001, 1234.5678, -7, 9007199254740993, 2 ** 60],
    ["tab\there", "line\nbreak", "quote\" back\\slash", "\u0000\u0001\u001f\u007f", "  ", "é😀€",
     "/slash", "\b\f\r"],
    {"nested": {"z": [], "y": {}, "x": [None, True, False, {"k": [1, [2, [3]]]}]}},
    "",
    None,
    {"money": "1234.50", "when": "2026-09-28T11:04:12.123400Z"},
]

A = "a1a1a1a1-0000-4000-8000-000000000001"
B = "b2b2b2b2-0000-4000-8000-000000000002"
T0 = datetime(2026, 9, 28, 11, 0, 0, 250000, tzinfo=timezone.utc)


def _d(n: int, client: str, **kw) -> dict:
    base = {"id": f"d{n:07d}-0000-4000-8000-{n:012d}", "client_id": client, "channel": "amazon", "status": "issued",
            "mandate": "standing", "issued_at": (T0 + timedelta(minutes=n)).isoformat(), "dedupe_key": f"key{n:04d}"}
    base.update(kw)
    return base


def build() -> dict:
    d1 = _d(1, A, module="pricing", kind="price_step", action_text="Raise SKU-1 from $24.99 to $25.99 — a 4% step.",
            expected_impact_usd=412.37,
            evidence={"sku": "SKU-1", "p0": 24.99, "p_new": 25.99, "elasticity": -1.73, "ci95": [-2.2, -1.1],
                      "delta_p5": 120.004, "delta_p50": 412.37, "delta_p95": 690.5, "p_loss": 0.031,
                      "mc_inputs": {"draws": 4000, "seed": 20260911}, "score": 14.1237})
    d2 = _d(2, A, module="advertising", kind="ad_bleed_terms",
            action_text="Negative-match 2 search terms that spent with zero attributed sales — $1,204 of pure bleed.",
            expected_impact_usd=1290.0,
            evidence={"terms": [{"campaign_name": "SP — Kitchen", "search_term": "cheap tongs", "spend": 704.2,
                                 "clicks": 311},
                                {"campaign_name": "SP — Kitchen", "search_term": "tongs ünd grill", "spend": 500.0,
                                 "clicks": None}],
                      "baseline_spend": 1204.2, "horizon_days": 30, "delta_p5": 1100.0, "delta_p50": 1290.0,
                      "delta_p95": 1480.0, "score": 1204.2})
    d3 = _d(3, A, module="recovery", kind="recovery_filing", mandate="explicit",
            action_text="Authorize us to file 3 reimbursement claims with Amazon — $310 at face value.",
            expected_impact_usd=None,
            evidence={"claim_keys": ["lost:FBA1", "lost:FBA2", "damaged:FBA9"], "face_value": 310.0,
                      "expected_value": 248.0, "n_claims": 3})
    e1 = _d(11, B, module="pricing", kind="price_step", action_text="Raise SKU-B from $10.00 to $10.40.",
            expected_impact_usd=88.0, evidence={"sku": "SKU-B", "delta_p5": 10.0, "delta_p95": 150.0})
    e2 = _d(12, B, module="advertising", kind="campaign_trim", action_text="Trim Campaign B to break-even.",
            expected_impact_usd=55.5, evidence={"campaign_name": "Campaign B", "current_spend": 900.0})

    def when(minutes):
        return T0 + timedelta(minutes=minutes)

    def called(d, minutes):
        return seal.called_document(d, d["client_id"], when(minutes))

    rows_a, rows_b, global_rows = [], [], []

    def put(client, doc):
        key = (seal.called_key(doc["directive_id"]) if doc["entry"] == "called"
               else seal.measured_key(doc["directive_id"], doc["measured_at"]))
        item = seal._Item(key, doc["entry"], doc["directive_id"], doc, seal.leaf_of(doc))
        rows = rows_a if client == A else rows_b
        ctip = (rows[-1]["seq"], rows[-1]["head"]) if rows else (0, seal.GENESIS)
        gtip = (global_rows[-1]["global_seq"], global_rows[-1]["global_head"]) if global_rows else (0, seal.GENESIS)
        row = seal.chain_rows(client, [item], ctip, gtip)[0]
        rows.append(row)
        global_rows.append(row)
        return row

    r1 = put(A, called(d1, 1))
    put(B, called(e1, 2))
    r2 = put(A, called(d2, 3))
    put(A, called(d3, 4))
    put(B, called(e2, 5))
    m1 = {**d1, "status": "done", "measured_impact_usd": 380.25, "attribution": "attributable",
          "measured_at": "2026-10-26T00:00:00+00:00",
          "evidence": {**d1["evidence"], "after": {"measured_distribution": {"p5": 101.5, "p50": 380.25,
                                                                             "p95": 702.0}, "window": ["2026-09-29",
                                                                                                        "2026-10-25"]}}}
    rm1 = put(A, seal.measured_document(m1, A, r1["leaf"], None, when(60 * 24 * 28)))
    m1b = {**m1, "measured_impact_usd": 350.0, "attribution": "direct", "measured_at": "2026-10-27T15:30:00.5+00:00"}
    put(A, seal.measured_document(m1b, A, r1["leaf"], rm1["leaf"], when(60 * 24 * 29), seal.BY_HAND))
    m2 = {**d2, "status": "closed", "measured_impact_usd": None, "attribution": "none",
          "measured_at": "2026-10-26T00:00:00+00:00", "evidence": {**d2["evidence"], "after": {"reason": "paused"}}}
    put(A, seal.measured_document(m2, A, r2["leaf"], None, when(60 * 24 * 28 + 1)))
    me1 = {**e1, "status": "done", "measured_impact_usd": 91.0, "attribution": "isolated",
           "measured_at": "2026-10-26T00:00:00+00:00"}
    put(B, seal.measured_document(me1, B, rows_b[0]["leaf"], None, when(60 * 24 * 28 + 2)))

    export = seal.bundle(A, rows_a, [m1b, m2, d3], global_rows, generated_at=when(60 * 24 * 30))

    # The same Record rewritten by someone who recomputed everything: entry 2's
    # promise raised and every leaf and head after it redone. It verifies on its
    # own; only a witness — the short seal the client's inbox holds, or a head
    # captured before the rewrite — can tell.
    rewritten = copy.deepcopy(export)
    ents = rewritten["entries"]
    ents[1]["document"]["expected_usd"] = "1490.00"
    remap: dict[str, str] = {}
    for e in ents:                       # references only ever point back, so one pass follows them
        doc = e["document"]
        for ref in ("called_leaf", "supersedes"):
            if doc.get(ref) in remap:
                doc[ref] = remap[doc[ref]]
        new = seal.leaf_of(doc)
        if new != e["leaf"]:
            remap[e["leaf"]] = new
        e["leaf"] = new
    glob = rewritten["global"]
    for e in ents:
        glob["leaves"][e["global_seq"] - glob["from_seq"]] = e["leaf"]
    prev = seal.GENESIS
    for e in ents:
        e["prev_head"], e["head"] = prev, seal.link(prev, e["leaf"])
        prev = e["head"]
    rewritten["head"] = prev
    at = {e["global_seq"]: e for e in ents}
    g = ents[0]["global_prev_head"]
    for j, leaf in enumerate(glob["leaves"]):
        e = at.get(glob["from_seq"] + j)
        if e:
            e["global_prev_head"] = g
        g = seal.link(g, leaf)
        if e:
            e["global_head"] = g
    glob["head"] = g

    chain_docs = [r["document"] for r in rows_a[:3]]
    heads, h = [], seal.GENESIS
    for doc in chain_docs:
        h = seal.link(h, seal.leaf_of(doc))
        heads.append(h)

    first_called_short = seal.short(rows_a[1]["leaf"])
    return {
        "_note": "Generated by engine/scripts/seal_golden.py from seal.py. Pinned by engine/tests/test_seal.py "
                 "and scripts/verify-record.test.mjs; do not edit by hand.",
        "canonical": [{"value": v, "canonical": seal.canonical(v).decode("utf-8"),
                       "sha256": seal.sha256_hex(seal.canonical(v))} for v in CANONICAL_CASES],
        "chain": {"documents": chain_docs, "leaves": [seal.leaf_of(d) for d in chain_docs], "heads": heads},
        "export": export,
        "tampered": [
            {"name": "a sealed promise's expected dollars edited in the export",
             "set": [[["entries", 1, "document", "expected_usd"], "1490.00"]], "first_broken_seq": 2, "check": "leaf"},
            {"name": "the evidence behind a promise edited",
             "set": [[["evidence", d1["id"], "before", "delta_p50"], 999.0]], "first_broken_seq": 1,
             "check": "evidence"},
            {"name": "a measurement's evidence edited",
             "set": [[["evidence", d1["id"], "after", "measured_distribution", "p50"], 999.0]], "first_broken_seq": 5,
             "check": "evidence_after"},
            {"name": "a measurement pointed at another move's promise",
             "set": [[["entries", 3, "document", "called_leaf"], rows_a[1]["leaf"]]],
             "first_broken_seq": 4, "check": "double_entry"},
            {"name": "an entry taken out", "remove": ["entries", 3], "first_broken_seq": 4, "check": "sequence"},
            {"name": "the global head swapped", "set": [[["global", "head"], "0" * 63 + "1"]],
             "first_broken_seq": None, "check": "global_head"},
        ],
        "rewritten": {"bundle": rewritten, "witness_that_catches_it": [first_called_short, export["global"]["head"]],
                      "witness_it_still_has": [seal.short(rows_a[0]["leaf"])]},
    }


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
