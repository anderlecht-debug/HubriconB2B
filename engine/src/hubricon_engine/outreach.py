"""The manual lane: briefs and drafts a human sends by hand.

Nothing in this module sends an email. Every function returns text for the
founder to read, edit and send from his own mailbox. That is deliberate:

- Instantly is the automated lane. On 2026-09-03 it had 84 leads enrolled and
  had never sent, and the list it was about to send to contained six agencies,
  three finance firms and a direct competitor.
- Resend is the transactional lane. It carries client magic links, welcome
  mail, teardown notices and the founder digest on hubricon.com. Its terms
  cover opt-in mail, and cold outreach through it risks the deliverability of
  the onboarding path. It is the wrong tool and this module never uses it.
- The first few customers of a new company come from a human writing to a
  named person about their specific listing. That is what this produces.

The hook is the FBA fee cliff, because a seller can check it in thirty seconds
and it is computed from a public product page: the packed weight, the band edge
below it, and the units that weight ships at every month.
"""

from . import icp
from .harvest import amazon

# These three say the DATA is wrong, not that the company is wrong. Rhino USA
# is squarely in the ICP; the harvest just resolved it to micah@micahrich.com.
# They come out of the automated campaign, because emailing a wrong address is
# worse than not emailing, and go to the founder lane for a human to fix.
FOUNDER_LANE_BUCKETS = ("role_inbox", "bad_greeting", "domain_mismatch")

# Written to fit_notes once a row is confirmed out of Instantly, so the hourly
# pass does not look every disqualified address up again forever.
DONE_MARK = "removed from Instantly"


# -- who should never have been enrolled ---------------------------------------

def dq_scan(db) -> list[dict]:
    """Prospects on file that fail the ICP gate, with the reason.

    Read-only. `hubricon outreach dq` prints this; `--apply` writes it.
    """
    rows = db.table("prospects").select(
        "email, first_name, company_name, website, source, status, instantly_lead_id"
    ).neq("status", "dq").execute().data
    out = []
    for r in rows:
        bucket, why = icp.off_icp(r.get("company_name"), r.get("email"), r.get("website"))
        if not bucket and icp.domain_mismatch(r.get("email"), r.get("website")):
            bucket, why = "domain_mismatch", f"{r.get('email')} is not on {r.get('website')}"
        if not bucket and icp.bad_greeting(r.get("first_name")):
            bucket, why = "bad_greeting", f'"Hi {r.get("first_name")}," reads as a mistake'
        if not bucket and icp.is_role_inbox(r.get("email")):
            bucket, why = "role_inbox", "reaches a support queue; needs a named owner first"
        if bucket:
            out.append({**r, "bucket": bucket, "why": why})
    out.sort(key=lambda r: (r["bucket"], r.get("company_name") or ""))
    return out


def dq_text(rows: list[dict]) -> str:
    if not rows:
        return "Nothing to disqualify: every prospect on file passes the ICP gate."
    founder = sum(1 for r in rows if r["bucket"] in FOUNDER_LANE_BUCKETS)
    lines = [f"{len(rows)} prospect(s) come out of the automated campaign.",
             f"  {founder} are good fits with bad data → founder lane, fix the address by hand.",
             f"  {len(rows) - founder} are not customers at all.", ""]
    bucket = None
    for r in rows:
        if r["bucket"] != bucket:
            bucket = r["bucket"]
            lane = "→ founder lane, worth a human" if bucket in FOUNDER_LANE_BUCKETS else "→ not a customer"
            lines.append(f"{bucket}  {lane}")
        lines.append(f"  {(r.get('company_name') or '?')[:34]:<34} {(r.get('email') or '')[:34]:<34} {r['why']}")
    return "\n".join(lines)


def apply_dq(db, rows: list[dict], api=None, log=print) -> int:
    """Mark the rows dq and, when Instantly is reachable, delete the lead there.

    Deleting is the point: a row marked dq here but still sitting in an active
    Instantly campaign will still be emailed by Instantly.
    """
    n = 0
    for r in rows:
        lane = "founder lane" if r["bucket"] in FOUNDER_LANE_BUCKETS else "not a customer"
        db.table("prospects").update({
            "status": "dq", "fit_notes": f"{r['bucket']} ({lane}) — {r['why']}",
        }).eq("email", r["email"]).execute()
        lead_id = r.get("instantly_lead_id")
        if api is not None and lead_id:
            try:
                api.delete_lead(lead_id)
            except Exception as err:
                log(f"  could not delete {r['email']} from Instantly: {err}")
        n += 1
    log(f"Disqualified {n} prospect(s)."
        + ("" if api is not None else "  (No Instantly key here: they stay in the campaign until"
                                      " the hourly operator runs this with the key.)"))
    return n


def prune_dq(db, api, dry: bool = False, log=print) -> int:
    """Delete disqualified prospects' leads from Instantly.

    Marking a row dq in Postgres does nothing to Instantly: the lead stays
    enrolled and would still be emailed the moment the campaign starts sending.
    This runs in the hourly operator, which is the only place that holds the
    API key, and closes that gap.
    """
    rows = [r for r in db.table("prospects").select("email, instantly_lead_id, fit_notes")
            .eq("status", "dq").execute().data
            if (r.get("instantly_lead_id") or r.get("email")) and DONE_MARK not in (r.get("fit_notes") or "")]
    if not rows:
        return 0
    if dry:
        log(f"[dry] would remove {len(rows)} disqualified lead(s) from Instantly")
        return 0
    gone = 0
    for r in rows:
        email = (r.get("email") or "").lower()
        # A lead exists twice over there: once in the list it was uploaded to
        # and once in the campaign it was enrolled into. Deleting the stored id
        # removes one of them and leaves the other free to be emailed, which is
        # the whole failure this function exists to prevent.
        ids = [r["instantly_lead_id"]] if r.get("instantly_lead_id") else []
        if email:
            try:
                ids += [l["id"] for l in api.leads_by_email(email) if l.get("id") and l["id"] not in ids]
            except Exception as err:
                log(f"  lookup failed for {email}: {err}")
                continue
        failed = False
        for lead_id in ids:
            try:
                api.delete_lead(lead_id)
            except Exception as err:
                if getattr(err, "status", None) != 404:  # already gone is fine
                    log(f"  could not remove {email} from Instantly: {err}")
                    failed = True
                    break
        if failed:
            continue
        note = ((r.get("fit_notes") or "") + f"; {DONE_MARK} ({len(ids)} lead object(s))").strip("; ")
        db.table("prospects").update({"instantly_lead_id": None, "fit_notes": note[:500]}) \
            .eq("email", r["email"]).execute()
        if ids:
            gone += 1
    log(f"Removed {gone} disqualified lead(s) from Instantly so the campaign cannot email them.")
    return gone


# -- the per-seller brief ------------------------------------------------------

def seller_facts(db, seller_id: str) -> dict | None:
    """Everything the harvest holds about one seller, plus the fee cliff per ASIN."""
    srows = db.table("harvest_sellers").select("*").eq("seller_id", seller_id).execute().data
    if not srows:
        return None
    s = srows[0]
    prods = db.table("harvest_products").select("*").eq("seller_id", seller_id).execute().data
    items = []
    for p in prods:
        weight = float(p["weight_oz"]) if p.get("weight_oz") is not None else None
        cliff = amazon.fee_cliff(weight)
        items.append({
            "asin": p.get("asin"), "title": (p.get("title") or "")[:70], "price": p.get("price"),
            "weight_oz": weight, "bsr": p.get("bsr"), "units": p.get("est_monthly_units"),
            "revenue": p.get("est_monthly_revenue"),
            "band_edge": cliff[0] if cliff else None, "over_by": cliff[1] if cliff else None,
        })
    items.sort(key=lambda i: (i["over_by"] is None, i["over_by"] or 0))
    return {"seller": s, "items": items}


def brief_text(facts: dict) -> str:
    """A page the founder reads before writing. Ends in a verification checklist.

    The checklist is not decoration. The harvest resolved Rhino USA to
    micah@micahrich.com and a brand called BigFoot to a 1990s email provider,
    and it stored "Washington" as Sol de Janeiro's contact first name. Every
    one of those would have been visible in ten seconds of looking.
    """
    s, items = facts["seller"], facts["items"]
    rev = s.get("est_monthly_revenue")
    lines = [
        f"{s.get('brand') or s.get('seller_name')}  ({s.get('seller_id')})",
        f"  storefront    {s.get('seller_name')}",
        f"  legal name    {s.get('business_name') or '—'}",
        f"  address       {', '.join(x for x in (s.get('city'), s.get('state'), s.get('country')) if x) or '—'}",
        f"  website       {s.get('website') or '—'}",
        f"  contact       {s.get('email') or '—'}  ({s.get('email_confidence') or 'none'})",
        f"  person        {s.get('first_name') or '—'} {s.get('last_name') or ''}".rstrip(),
        f"  feedback      {s.get('ratings_12mo') or '?'} in 12 months, {s.get('ratings_lifetime') or '?'} lifetime",
        f"  est revenue   ${float(rev):,.0f}/mo (estimate from public rank and price)" if rev else
        "  est revenue   unknown",
        f"  category      {s.get('top_category') or '—'}, best rank {s.get('top_bsr') or '—'}",
        "",
        "  Listings we hold:",
    ]
    if not items:
        lines.append("    none — this row came from an archived profile, so there is no listing to quote.")
    for i in items:
        w = f"{i['weight_oz']:g} oz" if i["weight_oz"] is not None else "weight unknown"
        cliff = (f"{i['over_by']:g} oz over the {i['band_edge']} oz band"
                 if i["over_by"] is not None else "no band edge below it")
        units = f"{float(i['units']):,.0f}/mo" if i.get("units") else "units unknown"
        lines.append(f"    {i['asin']}  {w:<16} {cliff:<32} {units}")
        if i["title"]:
            lines.append(f"      {i['title']}")
    best = next((i for i in items if i["over_by"] is not None), None)
    lines += ["", "  The hook:"]
    if best:
        lines.append(f"    {best['asin']} ships at {best['weight_oz']:g} oz. The band below ends at "
                     f"{best['band_edge']} oz, so it is {best['over_by']:g} oz into the next fee band "
                     f"on every unit.")
    else:
        lines.append("    No fee-cliff hook for this seller. Find another specific, checkable number "
                     "before writing, or skip them.")
    lines += [
        "",
        "  Verify before sending (the harvest gets these wrong):",
        "    [ ] the website really belongs to this brand",
        "    [ ] a named owner exists — About page, LinkedIn, Amazon storefront 'About the seller'",
        "    [ ] still roughly $1M-$20M/yr, not an aggregator or a household name",
        "    [ ] the weight on the live listing still matches what we stored",
    ]
    return "\n".join(lines)


def founder_email(facts: dict, first_name: str, calendly_url: str) -> dict:
    """A draft for the founder to edit and send from his own mailbox.

    Short, specific, one ask, no tracking. The claims match the website and the
    triage fact sheet: free teardown, $6,000/mo after, first month free.
    """
    s, items = facts["seller"], facts["items"]
    brand = s.get("brand") or s.get("seller_name")
    best = next((i for i in items if i["over_by"] is not None), None)
    if best:
        subject = f"{brand}: {best['over_by']:g} oz over an FBA fee band"
        hook = (f"Your {_short_title(best)} lists at {best['weight_oz']:g} oz. "
                f"The FBA weight band below it ends at {best['band_edge']} oz, so every unit you ship "
                f"pays the next band up. Public page, public weight — I have no access to your account.")
    else:
        subject = f"{brand}: the margin question nobody answers"
        hook = (f"I've been reading {brand}'s listings and the fee side looks like it's costing you "
                f"more than it should.")
    body = (
        f"Hi {first_name},\n\n"
        f"{hook}\n\n"
        f"I run Hubricon. I do the margin math for Amazon private-label brands: what each price can "
        f"take before units drop, where the next ad dollar stops paying, which SKU stocks out first.\n\n"
        f"If it's useful I'll do a written Profit Teardown of {brand} for free. Five Seller Central "
        f"exports, about fifteen minutes on your side, and the report is back within 24 hours. No seat "
        f"in your account, no card, and if it finds nothing worth fixing I'll tell you that and you "
        f"keep the report.\n\n"
        f"Worth a look? Reply and I'll send the upload page, or grab 20 minutes: {calendly_url}\n\n"
        f"Hagen Simmons\nHubricon\n"
    )
    return {"to": s.get("email"), "subject": subject, "body": body}


def _short_title(item: dict) -> str:
    """Amazon titles are keyword stuffing. Quote enough to be recognised, no more."""
    title = (item.get("title") or "").strip()
    if not title:
        return item.get("asin") or "listing"
    words = title.replace(",", " ").split()
    return " ".join(words[:6]).rstrip(" -") or item["asin"]


def _possessive(name: str) -> str:
    """"Tens Towels's" reads as a typo to the person whose brand it is."""
    return f"{name}'" if name.endswith(("s", "S")) else f"{name}'s"


PARTNER_TARGETS = """The ten, one email each (verify each is current before sending):
  bookkeepers / accountants (A2X partner directory)   4
  prep centres and 3PLs serving private-label brands  3
  lenders and factors to Amazon sellers               3"""


def partner_email(facts: dict, partner_name: str, referral_terms: str) -> dict:
    """GROWTH.md channel 4: three lines, one number, naming a public listing.

    The number must come from a public page and be labelled an estimate, and the
    email must never imply we know anything about the partner's client's account.
    """
    s, items = facts["seller"], facts["items"]
    brand = s.get("brand") or s.get("seller_name")
    best = next((i for i in items if i["over_by"] is not None), None)
    if not best:
        raise ValueError("partner_email needs a listing with a fee cliff to quote")
    units = f"about {float(best['units']):,.0f} units a month (estimated from public rank)" \
        if best.get("units") else "every unit it ships"
    body = (
        f"{partner_name} — you work with Amazon sellers; I do margin analytics for a few of them.\n\n"
        f"I pulled {_possessive(brand)} public listing ({best['asin']}): it ships at {best['weight_oz']:g} oz, "
        f"{best['over_by']:g} oz over the {best['band_edge']} oz FBA band, so it pays the next band's "
        f"fee on {units}. Public page, public weight — no account access.\n\n"
        f"If it's useful to your clients: they get a free written Profit Teardown and a free first "
        f"month, you get the anonymised results to publish and {referral_terms}. Want the one-pager?\n\n"
        f"Hagen Simmons\nHubricon\n"
    )
    return {"subject": f"one number on {brand}'s listing", "body": body}
