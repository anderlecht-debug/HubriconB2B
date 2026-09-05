"""The orchestration: prospects in, a review queue of teardowns out.

Designed around one habit rather than a pipeline. `hubricon teardown` builds
whatever is buildable and prints what is waiting; `hubricon teardown review`
walks the queue one at a time. Everything else is a shortcut into those two.

Nothing here sends an email. Phase 3 of COLD_ENGINE.md is deliberate about
that: the founder sends the first fifty by hand from his own mailbox and reads
every reply, because that is where the copy gets fixed. `mark_sent` records
what he sent, which is what makes the 90-day and three-touch rules real —
a hand-sent email nobody wrote down is a prospect the automated lane will mail
again next week.
"""

from __future__ import annotations

import secrets
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

from .. import icp, outbound
from . import compliance, copy as copymod, page, priors, select, settings
from .findings import Finding, detect
from .sources.harvest import HarvestSource
from .snapshot import ProspectSnapshot
from . import ENGINE_VERSION

REBUILD_AFTER_DAYS = 21          # a draft nobody sent goes stale; the listing moves


# -- persistence helpers -----------------------------------------------------------

def _finding_json(f: Finding) -> dict:
    return {k: v for k, v in asdict(f).items()}


def _snapshot_json(snap: ProspectSnapshot) -> dict:
    """Enough to reproduce the run without keeping the whole payload."""
    return {
        "key": snap.key, "platform": snap.platform, "provider": snap.provider,
        "brand": snap.brand, "website": snap.website, "country": snap.country,
        "est_monthly_revenue": snap.est_monthly_revenue,
        "captured_at": snap.captured_at.isoformat() if snap.captured_at else None,
        "items": [{"ref": i.ref, "price": i.price, "rank": i.rank, "category": i.category,
                   "item_weight_oz": i.item_weight_oz, "dims_in": list(i.dims_in or ()),
                   "tier": i.tier, "billable_weight_oz": i.billable_weight_oz,
                   "est_monthly_units": i.est_monthly_units} for i in snap.items],
    }


def _existing(db, prospect_key: str) -> dict | None:
    rows = (db.table("teardowns").select("*").eq("prospect_key", prospect_key)
            .order("created_at", desc=True).limit(1).execute().data)
    return rows[0] if rows else None


def _is_fresh(row: dict) -> bool:
    if row["status"] in ("sent", "approved", "rejected"):
        return True                                  # already decided; leave it alone
    made = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - made).days < REBUILD_AFTER_DAYS


# -- observations ------------------------------------------------------------------

def record_observations(db, products: list[dict], log=print) -> int:
    """Keep what the crawl just read, instead of overwriting it.

    Called wherever the harvest upserts harvest_products. That table holds one
    row per listing and the crawl updates it in place, so last week's price and
    rank are gone — which is the whole reason COLD_ENGINE.md §2 reaches for a
    paid history provider. The crawl already passes the same best sellers twice
    a day; keeping each reading turns those passes into the price and rank
    series Keepa would have sold us, for nothing, about a fortnight from now.

    Upserted on (asin, seen_on), so twice a day leaves one row and a re-run of
    the same day is idempotent. Never raises: a failure here must not lose the
    crawl's real work, which is the harvest_products write beside it.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    rows, seen = [], set()
    for p in products:
        asin = p.get("asin")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        rows.append({
            "asin": asin,
            "platform": p.get("platform") or "amazon",
            "seller_id": p.get("seller_id"),
            "price": p.get("price"),
            "bsr": p.get("bsr"),
            "reviews": p.get("reviews"),
            "weight_oz": p.get("weight_oz"),
            "seen_on": today,
        })
    if not rows:
        return 0
    try:
        db.table("harvest_product_observations").upsert(rows, on_conflict="asin,seen_on").execute()
    except Exception as err:
        log(f"  (price history not kept this pass: {err})")
        return 0
    return len(rows)


def _history(db, refs: list[str]) -> dict[str, list]:
    from .snapshot import Observation
    if not refs:
        return {}
    rows = (db.table("harvest_product_observations")
            .select("asin, price, bsr, seen_on").in_("asin", refs)
            .order("seen_on").execute().data)
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r["asin"], []).append(Observation(
            seen_on=date.fromisoformat(str(r["seen_on"])[:10]),
            price=float(r["price"]) if r.get("price") is not None else None,
            rank=r.get("bsr")))
    return out


def with_history(db, snap: ProspectSnapshot) -> ProspectSnapshot:
    """Attach whatever price/rank history the crawl has accumulated."""
    import dataclasses
    hist = _history(db, [i.ref for i in snap.items])
    if not hist:
        return snap
    items = tuple(dataclasses.replace(i, history=tuple(hist.get(i.ref, ()))) for i in snap.items)
    return dataclasses.replace(snap, items=items)


# -- build -------------------------------------------------------------------------

def build(db, limit: int = 40, log=print, force: bool = False,
          only: str | None = None, today: date | None = None) -> dict:
    """Model every buildable prospect and leave a draft teardown for each winner.

    Returns a summary the caller prints. The two numbers that matter are how
    many produced nothing and why — if 'nothing cleared the bar' is near zero,
    the confidence model is broken (COLD_ENGINE.md §2.2).
    """
    today = today or date.today()
    warning = priors.stale(today)
    if warning:
        log(f"! The FBA rate card is out of its window: {warning}")
        log("  Nothing will be priced until priors.py is updated. Stopping.")
        return {"stale": warning}

    source = HarvestSource(db)
    keys = [only] if only else source.keys(limit * 3)
    spent, budget = 0.0, settings.daily_budget_usd()
    counts = {"looked": 0, "built": 0, "no_finding": 0, "skipped": 0, "blocked": 0}
    reasons: dict[str, int] = {}

    for key in keys:
        if counts["built"] >= limit:
            break
        counts["looked"] += 1
        if spent + source.estimated_cost_usd() > budget:
            log(f"! COLD_DAILY_BUDGET_USD (${budget:,.2f}) would be exceeded; stopping here.")
            break

        prior = _existing(db, key)
        if prior and _is_fresh(prior) and not force:
            counts["skipped"] += 1
            continue

        snap = source.snapshot(key)
        if snap is None:
            counts["skipped"] += 1
            continue

        # The compliance gate runs before a draft is even written. A suppressed
        # or out-of-jurisdiction company should not have a page about it sitting
        # in a queue waiting for someone to click send by accident.
        clearance = compliance.authorise(db, snap, allow_dry_run=True)
        if not clearance.ok:
            counts["blocked"] += 1
            reasons[clearance.reason.split(":")[0][:48]] = \
                reasons.get(clearance.reason.split(":")[0][:48], 0) + 1
            continue
        bucket, why = compliance.off_icp(snap)
        if bucket:
            counts["blocked"] += 1
            reasons[f"off ICP ({bucket})"] = reasons.get(f"off ICP ({bucket})", 0) + 1
            continue

        snap = with_history(db, snap)
        found = detect(snap, today=today)
        verdict = select.review(found, snap)
        spent += snap.cost_usd

        run = db.table("cold_runs").insert({
            "prospect_key": key,
            "findings": [_finding_json(f) for f in found],
            "selected_finding": _finding_json(verdict.chosen) if verdict.chosen else None,
            "rejected": [{"kind": r.finding.kind, "reason": r.reason} for r in verdict.rejected],
            "confidence": verdict.chosen.confidence if verdict.chosen else None,
            "dollars_low": verdict.chosen.dollars_low if verdict.chosen else None,
            "dollars_high": verdict.chosen.dollars_high if verdict.chosen else None,
            "engine_version": ENGINE_VERSION,
            "snapshot": _snapshot_json(snap),
            "cost_usd": snap.cost_usd,
        }).execute().data[0]

        if not verdict.chosen:
            counts["no_finding"] += 1
            top = verdict.rejected[0].reason if verdict.rejected else "no finding at all"
            reasons[top[:48]] = reasons.get(top[:48], 0) + 1
            continue

        _write_teardown(db, snap, verdict.chosen, run["id"], today)
        counts["built"] += 1

    counts["spent_usd"] = round(spent, 4)
    counts["reasons"] = reasons
    counts["next"] = next_steps(reasons)
    return counts


# The point of a silent prospect is not that it is silent, it is which command
# would make it speak. Anything not on this list is a company whose public
# pages genuinely do not support a claim, and no command fixes that.
UNBLOCKERS = (
    ("no contact address", "hubricon harvest enrich",
     "reads the brand site for a published address"),
    ("no finding at all", "hubricon harvest listings",
     "re-reads the seller's storefront for listings with a published weight"),
    ("off ICP", None, "not customers; nothing to do"),
    ("GDPR", None, "suppressed on purpose"),
)


def next_steps(reasons: dict[str, int]) -> list[tuple[int, str, str]]:
    """(how many prospects, the command that would unblock them, why)."""
    out = []
    for needle, command, why in UNBLOCKERS:
        n = sum(v for k, v in reasons.items() if needle.lower() in k.lower())
        if n and command:
            out.append((n, command, why))
    return sorted(out, reverse=True)


def _write_teardown(db, snap: ProspectSnapshot, finding: Finding, run_id: str,
                    today: date) -> dict:
    token = secrets.token_urlsafe(24)
    expires = today + timedelta(days=settings.teardown_ttl_days())
    url = copymod.teardown_url(token)
    message = copymod.email(finding, snap, snap.first_name, url, outbound.CALENDLY_URL)
    html = page.render(finding, snap, token=token, cta_url=f"{url}?cta=1",
                       expires_on=expires, generated_on=today)
    return db.table("teardowns").insert({
        "prospect_key": snap.key,
        "cold_run_id": run_id,
        "token": token,
        "html": html,
        "subject": message["subject"],
        "body": message["body"],
        "script": copymod.script(finding, snap),
        "expires_at": datetime.combine(expires, datetime.min.time(),
                                       tzinfo=timezone.utc).isoformat(),
    }).execute().data[0]


# -- the queue ---------------------------------------------------------------------

def blocker(seller: dict) -> str | None:
    """What stands between this teardown and the founder pressing send.

    The founder's standing call on 2026-09-03: a role inbox is never cold
    emailed. `info@` reaches a customer-service queue, and a teardown addressed
    to a queue is worth close to nothing — the same page sent to the owner is
    worth a great deal. So a role-inbox row is inventory rather than a draft to
    send, and the queue says which it is instead of quietly presenting one as
    the other.
    """
    email, website = seller.get("email"), seller.get("website")
    if not email:
        return "no address — hubricon harvest enrich"
    if icp.domain_mismatch(email, website):
        return f"{email} is not on {website} — find the real one on the site"
    if icp.is_role_inbox(email):
        return "role inbox — find the owner (About page, LinkedIn, storefront)"
    if not seller.get("first_name") or icp.bad_greeting(seller.get("first_name")):
        return "no owner's name — find it before sending"
    return None


def queue(db, status: str = "draft", limit: int = 50) -> list[dict]:
    """Teardowns waiting, richest first — with the seller row attached."""
    rows = (db.table("teardowns").select("*").eq("status", status)
            .order("created_at", desc=True).limit(limit).execute().data)
    if not rows:
        return []
    keys = list({r["prospect_key"] for r in rows})
    sellers = {s["seller_id"]: s for s in
               db.table("harvest_sellers").select("*").in_("seller_id", keys).execute().data}
    runs = {r["id"]: r for r in
            db.table("cold_runs").select("id, selected_finding, confidence, dollars_low, "
                                         "dollars_high")
            .in_("id", list({r["cold_run_id"] for r in rows})).execute().data}
    out = []
    for r in rows:
        run = runs.get(r["cold_run_id"], {})
        seller = sellers.get(r["prospect_key"], {})
        stop = blocker(seller)
        out.append({**r, "seller": seller, "blocker": stop, "ready": stop is None,
                    "finding": run.get("selected_finding") or {},
                    "confidence": run.get("confidence"),
                    "dollars_low": run.get("dollars_low"),
                    "dollars_high": run.get("dollars_high")})
    out.sort(key=lambda r: (not r["ready"], -(float(r.get("dollars_high") or 0))))
    return out


def resolve(db, ref: str) -> dict | None:
    """Find one teardown by id prefix, token, seller id, or brand name."""
    ref = (ref or "").strip()
    if not ref:
        return None
    rows = db.table("teardowns").select("*").order("created_at", desc=True).execute().data
    lower = ref.lower()
    for match in (lambda r: r["id"].startswith(lower),
                  lambda r: r["token"] == ref,
                  lambda r: r["prospect_key"].lower() == lower):
        hits = [r for r in rows if match(r)]
        if hits:
            return _attach(db, hits[0])
    sellers = (db.table("harvest_sellers").select("seller_id, brand, seller_name")
               .execute().data)
    keys = {s["seller_id"] for s in sellers
            if lower in ((s.get("brand") or "") + " " + (s.get("seller_name") or "")).lower()}
    hits = [r for r in rows if r["prospect_key"] in keys]
    return _attach(db, hits[0]) if hits else None


def _attach(db, row: dict) -> dict:
    seller = (db.table("harvest_sellers").select("*")
              .eq("seller_id", row["prospect_key"]).execute().data or [{}])[0]
    run = (db.table("cold_runs").select("*").eq("id", row["cold_run_id"]).execute().data
           or [{}])[0]
    return {**row, "seller": seller, "run": run,
            "finding": run.get("selected_finding") or {},
            "blocker": blocker(seller), "ready": blocker(seller) is None,
            "url": copymod.teardown_url(row["token"])}


def name_owner(db, teardown_id: str, *, first_name: str | None = None,
               last_name: str | None = None, email: str | None = None,
               today: date | None = None) -> tuple[bool, str]:
    """Record the owner a human just found, and rewrite the email around it.

    This is the ten minutes the founder lane actually costs, closed in one
    command. The finding does not change — it is already computed and already
    on the page — only the greeting and the address do, so the draft is rebuilt
    from the stored finding rather than remodelled.
    """
    row = (db.table("teardowns").select("*").eq("id", teardown_id).execute().data or [None])[0]
    if not row:
        return False, "no such teardown"
    if row["status"] in ("sent", "rejected"):
        return False, f"this teardown is already {row['status']}"
    patch = {k: v for k, v in (("first_name", first_name), ("last_name", last_name),
                               ("email", (email or "").strip().lower() or None)) if v}
    if not patch:
        return False, "give at least --first-name or --email"
    if email:
        patch["email_confidence"] = "published"
        patch["contact_source"] = "founder, by hand"
    db.table("harvest_sellers").update(patch).eq("seller_id", row["prospect_key"]).execute()

    snap = with_history(db, HarvestSource(db).snapshot(row["prospect_key"]))
    stop = blocker(snap.payload["seller"])
    finding = _rehydrate(row, db)
    if finding is None:
        return False, "the finding behind this teardown is gone; rebuild with --force"
    message = copymod.email(finding, snap, snap.first_name, copymod.teardown_url(row["token"]),
                            outbound.CALENDLY_URL)
    db.table("teardowns").update({"subject": message["subject"], "body": message["body"]}) \
        .eq("id", teardown_id).execute()
    if stop:
        return True, f"saved, but still blocked: {stop}"
    return True, f"saved. The draft now opens 'Hi {snap.first_name}' and goes to {snap.email}."


def _rehydrate(row: dict, db) -> Finding | None:
    run = (db.table("cold_runs").select("selected_finding")
           .eq("id", row["cold_run_id"]).execute().data or [{}])[0]
    payload = run.get("selected_finding")
    return Finding(**payload) if payload else None


# -- decisions ---------------------------------------------------------------------

def decide(db, teardown_id: str, status: str, note: str | None = None) -> None:
    db.table("teardowns").update({
        "status": status,
        "review_note": (note or "")[:500] or None,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "published_at": (datetime.now(timezone.utc).isoformat()
                         if status == "approved" else None),
    }).eq("id", teardown_id).execute()


def mark_sent(db, teardown_id: str, sending_domain: str | None = None) -> tuple[bool, str]:
    """Record a hand-sent teardown, through the same clearance every send uses.

    The founder lane does not send anything from this machine, so the clearance
    runs with allow_dry_run — but every other guard still applies, and the row
    it writes is what stops this prospect being contacted again inside ninety
    days by any lane.
    """
    row = (db.table("teardowns").select("*").eq("id", teardown_id).execute().data or [None])[0]
    if not row:
        return False, "no such teardown"
    source = HarvestSource(db)
    snap = source.snapshot(row["prospect_key"])
    if snap is None:
        return False, "the prospect row is gone"
    clearance = compliance.authorise(db, snap, sending_domain=sending_domain, allow_dry_run=True)
    if not clearance.ok:
        return False, clearance.reason
    compliance.record_send(db, clearance.send, template_id=copymod.TEMPLATE_ID,
                           subject=row.get("subject") or "", teardown_id=teardown_id)
    db.table("teardowns").update({
        "status": "sent", "published_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", teardown_id).execute()
    return True, f"recorded. {snap.email} will not be contacted again for " \
                 f"{settings.recontact_days()} days."


def record_event(db, teardown_id: str, kind: str, detail: dict | None = None) -> None:
    db.table("teardown_events").insert({
        "teardown_id": teardown_id, "kind": kind, "detail": detail or {},
    }).execute()


# -- the numbers -------------------------------------------------------------------

def stats(db) -> dict:
    """The two rates that say whether this is working.

    They are different questions and were conflated in the first version, which
    made a thin harvest look like a broken confidence model:

      *nothing to model*      no listing on file carries a price. Four of the
                              five detectors additionally need a published
                              weight, so a price-only prospect can only ever
                              trip the price-band one, which by construction
                              fires on about one listing in seventy. Both are
                              harvest problems and `hubricon harvest listings`
                              is the fix for both.
      *stayed silent anyway*  the arithmetic ran on a listing with a price and
                              a weight and refused to make a claim.

    COLD_ENGINE.md §2.2 expects roughly half of prospects to produce nothing.
    That figure assumes the price and rank *history* a paid provider sells; on a
    single snapshot four of the five detectors need a weight sitting near a band
    edge, so silence well above half is the expected shape and not a fault. The
    number that would be a fault is a silence rate near zero, which means the
    confidence gate has stopped refusing anything, and that is what the verdict
    below actually watches for.

    Conflating the two made a thin harvest look like a broken gate, which would
    have sent someone to tune the confidence floor when the answer was to crawl
    more storefronts.
    """
    tds = db.table("teardowns").select("id, status, created_at").execute().data
    events = db.table("teardown_events").select("teardown_id, kind").execute().data
    runs = db.table("cold_runs").select("selected_finding, rejected, snapshot").execute().data
    by_status: dict[str, int] = {}
    for t in tds:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    by_kind: dict[str, int] = {}
    for e in events:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    modelled = len(runs)
    selected = sum(1 for r in runs if r.get("selected_finding"))
    why: dict[str, int] = {}
    no_price = no_weight = 0
    for r in runs:
        items = (r.get("snapshot") or {}).get("items") or []
        priced = [i for i in items if i.get("price")]
        weighed = [i for i in priced if i.get("item_weight_oz")]
        if r.get("selected_finding"):
            continue
        if not priced:
            no_price += 1
            continue
        if not weighed:
            no_weight += 1
            continue
        rejected = r.get("rejected") or []
        reason = rejected[0]["reason"] if rejected else \
            "not near a fee band, a price edge, or an oversized box"
        why[reason[:60]] = why.get(reason[:60], 0) + 1
    judged = modelled - no_price - no_weight
    reviewed = by_status.get("approved", 0) + by_status.get("rejected", 0) + \
        by_status.get("sent", 0)
    kept = by_status.get("approved", 0) + by_status.get("sent", 0)
    return {
        "modelled": modelled, "selected": selected,
        "no_price": no_price, "no_weight": no_weight, "judged": judged,
        "silent_rate": round(1 - selected / judged, 3) if judged else None,
        "why_silent": dict(sorted(why.items(), key=lambda kv: -kv[1])),
        "by_status": by_status, "events": by_kind,
        "reviewed": reviewed, "kept": kept,
        "approval_rate": round(kept / reviewed, 3) if reviewed else None,
    }

