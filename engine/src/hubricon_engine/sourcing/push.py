"""Qualified leads into Instantly — into a holding pen, and no further.

The founder's instruction on this build was explicit: no teardown goes out
without his say-so. That is not a comment, it is a design constraint, and it
has to survive somebody later renaming a list in a web UI at eleven at night.

The hazard is specific and it is easy to walk into. `outbound.enroll_from_lists`
enrols **any Instantly lead list whose name contains `INSTANTLY_LIST_MATCH`**
(default `"hubricon"`) into the live campaign, and the hourly GitHub operator
runs it with `COLD_DRY_RUN: "false"`. So a list called "Hubricon sourcing"
would begin cold-emailing strangers within the hour, with nobody having
approved anything. Four fences, each with a test:

  1. The list is named `Sourcing holding pen (manual enroll only)` — no
     "hubricon" token anywhere in it, so `enroll_from_lists` cannot match it.
     It is a constant, not an environment knob, because a knob is a thing
     somebody can set wrong.
  2. `push` re-reads the list's name from Instantly and refuses to write to it
     if it now matches `outbound.LIST_MATCH`. A rename becomes an exception,
     not a send.
  3. Only `add_leads(list_id=...)`. `campaign_id` is never passed from this
     package, and `create_lead` — the per-prospect teardown dispatch path — is
     never called from here at all.
  4. Only `published`, non-role addresses are pushed (`contact.sendable`), so
     the list cannot fill with guesses even if somebody does enrol it by hand.

When the founder does want to start sending, the path is the one that already
exists and already has a human in it: `hubricon teardown review`, then
`approve`, and the hourly operator dispatches what he approved. Nothing here
shortcuts that.
"""

from __future__ import annotations

from .. import outbound
from ..instantly import Instantly
from .contact import sendable

# Deliberately free of the token `outbound.LIST_MATCH` looks for. Read fence 1
# in the module docstring before changing this string.
LIST_NAME = "Sourcing holding pen (manual enroll only)"
BATCH = 100


class WouldEnroll(RuntimeError):
    """The destination list would be auto-enrolled into the live campaign."""


def check_name(name: str) -> None:
    """Fence 2. Raises if `name` is one `enroll_from_lists` would pick up."""
    if outbound.LIST_MATCH and outbound.LIST_MATCH in (name or "").lower():
        raise WouldEnroll(
            f"the destination list is named {name!r}, which contains "
            f"{outbound.LIST_MATCH!r} — outbound.enroll_from_lists would enrol it into the live "
            f"campaign and the hourly operator would start sending. Rename it in Instantly to "
            f"something without that word (the engine expects {LIST_NAME!r}).")


def ensure_list(api: Instantly, name: str = LIST_NAME) -> str:
    """The holding pen's id, created if it is not there. Checks fence 2 on the
    name Instantly actually reports, not on the one we asked for."""
    check_name(name)
    for lst in api.lead_lists():
        if lst.get("name") == name:
            check_name(lst.get("name") or "")
            return lst["id"]
    created = api.create_lead_list(name)
    check_name(created.get("name") or name)
    return created["id"]


def lead_payload(row: dict) -> dict:
    """One prospect as an Instantly lead.

    The custom variables carry the qualification with the lead, so a sequence
    written later can branch on the finding and the founder can see why a row
    is in the list without going back to the database.
    """
    brand = row.get("brand") or row.get("domain") or ""
    stack = row.get("stack") or {}
    apps = stack.get("apps") if isinstance(stack, dict) else None
    return {
        "email": row["email"],
        "first_name": row.get("first_name") or f"{brand} team",
        "last_name": row.get("last_name") or "",
        "company_name": brand,
        "website": f"https://{row['domain']}/" if row.get("domain") else "",
        "custom_variables": {
            "source": "sourcing",
            "platform": "shopify",
            "domain": row.get("domain") or "",
            "score": row.get("score") or "",
            "tranco_rank": row.get("tranco_rank") or "",
            "est_annual": row.get("est_annual") or "",
            "stack": ", ".join(apps or []) if apps else "",
            "finding_kind": row.get("finding_kind") or "",
            "finding_dollars": row.get("finding_high") or "",
            "teardown_url": row.get("teardown_url") or "",
            "email_confidence": row.get("email_confidence") or "",
        },
    }


def eligible(prospects: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """-> (rows we may push, [(domain, why not)]). Fence 4."""
    keep, refused = [], []
    for row in prospects:
        ok, why = sendable(row)
        (keep if ok else refused).append(row if ok else (row.get("domain") or "?", why))
    return keep, refused


def push(db, api: Instantly | None, prospects: list[dict], dry: bool = False,
         limit: int = 200, log=print) -> dict:
    """Qualified, contactable prospects into the holding pen.

    Nothing is sent. Nothing is enrolled. A row that lands here is a row a
    person can look at in Instantly and choose to do something with.
    """
    keep, refused = eligible(prospects)
    for domain, why in refused:
        log(f"  skip {domain}: {why}")
    keep = keep[:limit]
    summary = {"eligible": len(keep), "refused": len(refused), "pushed": 0,
               "list": LIST_NAME, "sent": 0}
    if not keep:
        log("  nothing eligible to push")
        return summary
    if dry or api is None:
        log(f"  would push {len(keep)} lead(s) to {LIST_NAME!r}"
            + ("" if api else " (no INSTANTLY_API_KEY on this machine)"))
        summary["dry"] = True
        return summary

    list_id = ensure_list(api)
    pushed = 0
    for start in range(0, len(keep), BATCH):
        batch = keep[start:start + BATCH]
        api.add_leads(list_id=list_id, leads=[lead_payload(r) for r in batch])
        pushed += len(batch)
        for row in batch:
            db.table("sourcing_prospects").update(
                {"status": "promoted", "note": f"in Instantly list {LIST_NAME!r}"}
            ).eq("domain", row["domain"]).execute()
    log(f"  pushed {pushed} lead(s) into {LIST_NAME!r} — not enrolled, nothing sent")
    summary["pushed"] = pushed
    return summary
