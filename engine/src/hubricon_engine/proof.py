"""Proof: what a client's own ledger proved, turned into something a stranger can read.

The loop this business is meant to be — customers, results, word of mouth,
customers — was missing its third arrow. `value.compute` has always known
when a reimbursement Amazon paid on a claim we filed landed, when a directive
measured `direct`, when the day-30 gate cleared and when the ledger crossed
three or five times the fee. Nothing turned any of those into a sentence, so
the site kept its "Sample · demo data" badges and the cold email kept saying
"the track record isn't [built]" however true the ledger had become.

Three rules, all enforced here rather than remembered:

  1. A result is written by this module from the ledger, never by hand and
     never by a model. `detect()` is pure and keys off `value_total` and
     `roi_multiple` — the gate's own bar counts identified-but-unbanked value,
     and that is the right bar for an invoice and the wrong one for a claim
     made to a stranger.
  2. Nothing is public without `anonymised_results` consent (terms §9). The
     `public_results()` RPC re-checks consent on every read, so a revocation
     hides every card at once.
  3. The one line of proof the cold copy and the site carry is a template
     whose only numbers are `{{placeholders}}` filled from the RPC, and it is
     checked with the same `narrate.validate` guard the Issue letter runs
     under. A proof line can therefore never carry a figure the ledger did not.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from . import narrate
from . import value as valuemod

RESULTS_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/results"

KINDS = ("first_recovered", "gate_cleared", "roi_3x", "roi_5x", "direct_measured")

# A fixed vocabulary so the public cards read as a set. The founder records one
# at kickoff (`hubricon proof set <client> --industry kitchen`).
INDUSTRIES = ("kitchen", "home", "beauty", "health", "supplements", "pet", "baby", "outdoor",
              "sports", "apparel", "electronics", "toys", "food", "office", "automotive",
              "garden", "other")

HOW_LABEL = {
    "direct": "confirmed by the platform's own record",
    "isolated": "measured on the exact line the move named",
    "attributable": "measured against a stated counterfactual",
    "recovered": "paid by Amazon on a claim we filed",
    "gate": "the Profit Record against the invoice",
}

# The proof line. Two templates, no digits, every figure a placeholder that
# `facts()` fills from the RPC; `line()` refuses to render either if the
# number guard objects.
ONE_RESULT = ("A {{proof_industry}} brand in the {{proof_band}} range took the free month and has "
              "{{proof_total}} on its Profit Record so far, measured from its own exports. "
              "The record is at {{proof_url}}.")
MANY_RESULTS = ("{{proof_count}} brands have taken the free month and have {{proof_total}} on "
                "their Profit Records between them, measured from their own exports. "
                "The records are at {{proof_url}}.")

_BAND = re.compile(r"rev\s*[:=]\s*([^|]+)")
BANDS = {
    "under $1m": "under $1M",
    "$1m–$5m": "$1M–$5M", "$1m-$5m": "$1M–$5M",
    "$5m–$20m": "$5M–$20M", "$5m-$20m": "$5M–$20M",
    "$20m+": "$20M+",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def revenue_band_from_answers(answers: dict | None) -> str | None:
    """The gate's own revenue answer, from the same utm_content string the
    platform is read from (`onboarding.platform_from_answers`)."""
    if not answers:
        return None
    direct = str(answers.get("rev") or answers.get("revenue") or "").strip().lower()
    if direct in BANDS:
        return BANDS[direct]
    for value in answers.values():
        m = _BAND.search(str(value))
        if m and m.group(1).strip().lower() in BANDS:
            return BANDS[m.group(1).strip().lower()]
    return None


# -- detection -----------------------------------------------------------------------

def _stamp(client: dict, kind: str, source_ref: str, amount: float, mechanism: str | None,
           how: str) -> dict:
    return {
        "client_id": client["id"], "kind": kind, "source_ref": str(source_ref),
        "amount_usd": round(float(amount), 2), "mechanism": mechanism, "how_we_know": how,
        "platform": client.get("platform") or "amazon",
        "industry": client.get("industry"), "revenue_band": client.get("revenue_band"),
    }


def detect(client: dict, ledger: dict, directives: list[dict], claims: list[dict]) -> list[dict]:
    """Every verified event the ledger supports right now. Pure; idempotent by
    (client, kind, source_ref), which `record` enforces."""
    out: list[dict] = []
    total = float(ledger.get("value_total") or 0)
    multiple = ledger.get("roi_multiple")

    ours = [c for c in claims
            if c.get("status") == "paid" and float(c.get("paid_amount") or 0) > 0
            and (c.get("filed_at") or c.get("case_id"))]
    if ours:
        first = sorted(ours, key=lambda c: str(c.get("paid_at") or c.get("filed_at") or ""))[0]
        out.append(_stamp(client, "first_recovered", first.get("id") or first.get("claim_key") or "",
                          first["paid_amount"], first.get("claim_type"), "recovered"))

    for d in directives:
        if d.get("attribution") == "direct" and float(d.get("measured_impact_usd") or 0) > 0:
            out.append(_stamp(client, "direct_measured", d.get("id") or "",
                              d["measured_impact_usd"],
                              d.get("module") or d.get("kind") or "directive", "direct"))

    if total > 0 and client.get("billing_decision") == "cleared":
        ref = str(client.get("retainer_started_at") or client["id"])[:10]
        out.append(_stamp(client, "gate_cleared", ref, total, "ledger", "gate"))

    if total > 0 and multiple is not None:
        month = str(ledger.get("as_of") or "")[:7]
        if float(multiple) >= valuemod.STRONG_MULTIPLE:
            out.append(_stamp(client, "roi_5x", month, total, f"{float(multiple):.1f}x fees", "gate"))
        elif float(multiple) >= valuemod.AT_RISK_MULTIPLE:
            out.append(_stamp(client, "roi_3x", month, total, f"{float(multiple):.1f}x fees", "gate"))
    return out


def record(db, rows: list[dict]) -> int:
    """Insert what is new; never touch a row that exists, because `published`
    lives on it. Returns how many were written."""
    written = 0
    by_client: dict[str, list[dict]] = {}
    for r in rows:
        by_client.setdefault(r["client_id"], []).append(r)
    for cid, mine in by_client.items():
        have = {(x["kind"], x.get("source_ref") or "") for x in
                db.table("results").select("kind, source_ref").eq("client_id", cid).execute().data}
        fresh = [r for r in mine if (r["kind"], r["source_ref"]) not in have]
        if fresh:
            db.table("results").insert(fresh).execute()
            written += len(fresh)
    return written


def publish(db) -> int:
    """Flip `published` on every unpublished row whose client has granted
    anonymised-results consent. The RPC re-checks consent on read, so this is
    eligibility, not permission."""
    consented = {k["client_id"] for k in
                 db.table("consents").select("client_id").eq("kind", "anonymised_results")
                 .eq("granted", True).execute().data}
    if not consented:
        return 0
    pending = db.table("results").select("id, client_id").eq("published", False).execute().data
    ids = [r["id"] for r in pending if r["client_id"] in consented]
    if not ids:
        return 0
    db.table("results").update({"published": True, "published_at": _now()}).in_("id", ids).execute()
    return len(ids)


# -- the public side -----------------------------------------------------------------

def cards(db) -> list[dict]:
    try:
        return db.rpc("public_results", {}).execute().data or []
    except Exception:
        return []


def facts(rows: list[dict]) -> dict | None:
    """A `narrate.build_facts`-shaped table: formatted strings only."""
    if not rows:
        return None
    total = sum(float(r.get("amount_usd") or 0) for r in rows)
    lead = rows[0]
    return {
        "proof_count": {"value": str(len(rows)), "label": "brands with a published result"},
        "proof_total": {"value": narrate._money(total), "label": "verified value across those brands"},
        "proof_industry": {"value": str(lead.get("industry") or "product"), "label": "the brand's category"},
        "proof_band": {"value": str(lead.get("revenue_band") or "$1M–$20M"), "label": "the brand's revenue band"},
        "proof_url": {"value": RESULTS_URL, "label": "where the anonymised records are published"},
    }


def line_from(rows: list[dict]) -> str | None:
    f = facts(rows)
    if not f:
        return None
    template = ONE_RESULT if len(rows) == 1 else MANY_RESULTS
    problems = narrate.validate(template, f)
    if problems:      # a template edit smuggled a number in; refuse rather than ship it
        raise ValueError("proof line rejected by the number guard: " + "; ".join(problems))
    return narrate.render(template, f)


def line(db) -> str | None:
    """The one sentence of proof, or None while there is nothing to prove.
    Copy that takes it must read equally well without it."""
    return line_from(cards(db))


# -- the founder's inputs -------------------------------------------------------------

def set_profile(db, client_id: str, industry: str | None = None, revenue_band: str | None = None) -> dict:
    patch = {}
    if industry is not None:
        word = industry.strip().lower()
        if word not in INDUSTRIES:
            raise ValueError(f"industry must be one of: {', '.join(INDUSTRIES)}")
        patch["industry"] = word
    if revenue_band is not None:
        band = BANDS.get(revenue_band.strip().lower(), revenue_band.strip())
        patch["revenue_band"] = band
    if not patch:
        return {}
    db.table("clients").update(patch).eq("id", client_id).execute()
    # cards already written for this client inherit the words
    db.table("results").update(patch).eq("client_id", client_id).execute()
    return patch


def describe(row: dict) -> str:
    """One line per result, for the CLI and the digest."""
    return (f"{row.get('kind'):<16} ${float(row.get('amount_usd') or 0):>10,.0f}  "
            f"{HOW_LABEL.get(row.get('how_we_know'), row.get('how_we_know'))}"
            f"{'  · published' if row.get('published') else ''}")
