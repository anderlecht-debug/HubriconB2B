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

The hook is a fee cliff, because a seller can check it in thirty seconds and it
is computed from a public product page: the packed weight, the band edge below
it, and the units that weight ships at every month. Which cliff depends on
where the brand sells, and the row says which (harvest_sellers.platform):

- Amazon: the FBA fulfilment-fee weight bands (harvest.amazon.fee_cliff).
- Shopify: the USPS Ground Advantage / UPS bands the brand pays a carrier
  directly (harvest.shopify.shipping_cliff). Same arithmetic, different rate
  card — and a Shopify brand must never be sent copy about "FBA fees" or asked
  for Seller Central exports it does not have.
"""

from . import icp
from .harvest import amazon, shopify

# These three say the DATA is wrong, not that the company is wrong. Rhino USA
# is squarely in the ICP; the harvest just resolved it to micah@micahrich.com.
# They come out of the automated campaign, because emailing a wrong address is
# worse than not emailing, and go to the founder lane for a human to fix.
FOUNDER_LANE_BUCKETS = ("role_inbox", "bad_greeting", "domain_mismatch")

# Written to fit_notes once a row is confirmed out of Instantly, so the hourly
# pass does not look every disqualified address up again forever.
DONE_MARK = "removed from Instantly"

# The step function that makes the hook, per platform, and the words for it.
# A row written before 2026-09-04 carries no platform and is an Amazon seller.
CLIFF_FN = {"amazon": amazon.fee_cliff, "shopify": shopify.shipping_cliff}
PLATFORM_LABEL = {"amazon": "Amazon", "shopify": "Shopify"}
CLIFF_LABEL = {"amazon": "FBA fee band", "shopify": "USPS/UPS shipping band"}
# What the free teardown asks the brand to export. Asking a Shopify brand for
# Seller Central reports says louder than anything else that the email is spam.
EXPORTS = {"amazon": "Five Seller Central exports",
           "shopify": "Five exports out of your Shopify admin"}


def platform_of(row: dict | None) -> str:
    return ((row or {}).get("platform") or "amazon").lower()


def cliff_for(platform: str | None, weight_oz: float | None) -> tuple[int, float] | None:
    """→ (band edge below, ounces over it) using this platform's rate card."""
    return CLIFF_FN.get((platform or "amazon").lower(), amazon.fee_cliff)(weight_oz)


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


def apply_dq(db, rows: list[dict], log=print) -> int:
    """Mark the rows dq. Deliberately does not touch Instantly.

    Un-enrolling needs the campaign id so it can delete the campaign object and
    leave the lead lists alone, and the hourly operator is the only place that
    has both that and the API key. This just records the decision; prune_dq
    acts on it.
    """
    n = 0
    for r in rows:
        lane = "founder lane" if r["bucket"] in FOUNDER_LANE_BUCKETS else "not a customer"
        db.table("prospects").update({
            "status": "dq", "fit_notes": f"{r['bucket']} ({lane}) — {r['why']}",
        }).eq("email", r["email"]).execute()
        n += 1
    log(f"Disqualified {n} prospect(s). The next operator pass un-enrolls them from the campaign; "
        "their lead-list rows stay, because that is the only address the founder lane has for them.")
    return n


def prune_dq(db, api, campaign_id: str | None = None, dry: bool = False, log=print) -> int:
    """Un-enroll disqualified prospects from the CAMPAIGN, and only the campaign.

    Marking a row dq in Postgres does nothing to Instantly: the lead stays
    enrolled and would still be emailed the moment the campaign starts sending.
    This runs in the hourly operator, which is the only place that holds the
    API key, and closes that gap.

    It must not touch the lead lists. The first version of this deleted every
    lead object leads_by_email returned, which emptied "Hubricon harvest (auto)"
    from 34 leads to 1 between 20:12 and 20:18 on 2026-09-03. Those lists are
    the harvest's inventory and the founder lane's only record of how to reach
    those brands: a role inbox is the wrong address for a cold sequence and the
    right one for a human who has found the owner's name. Deleting the campaign
    enrolment stops the email; deleting the list row destroys the lead.

    So a lead object is only ever deleted when Instantly says it belongs to this
    campaign. Without a campaign_id to compare against, nothing is deleted.
    """
    rows = [r for r in db.table("prospects").select("email, instantly_lead_id, fit_notes")
            .eq("status", "dq").execute().data
            if (r.get("instantly_lead_id") or r.get("email")) and DONE_MARK not in (r.get("fit_notes") or "")]
    if not rows:
        return 0
    if not campaign_id:
        log("DQ prune: no campaign id, so nothing is deleted "
            "(deleting by address alone would take the lead lists with it).")
        return 0
    if dry:
        log(f"[dry] would un-enroll {len(rows)} disqualified prospect(s) from the campaign")
        return 0
    gone = 0
    for r in rows:
        email = (r.get("email") or "").lower()
        if not email:
            continue
        # A lead exists more than once over there: once in each list it was
        # uploaded to, and once in the campaign it was enrolled into. Only the
        # campaign object is deleted. The list rows are the harvest's inventory
        # and the founder lane's address book, and they stay.
        try:
            objects = api.leads_by_email(email)
        except Exception as err:
            log(f"  lookup failed for {email}: {err}")
            continue
        ids = [l["id"] for l in objects if l.get("id") and l.get("campaign") == campaign_id]
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
    log(f"Un-enrolled {gone} disqualified prospect(s) from the campaign. Their list rows are untouched.")
    return gone


# -- the daily batch -----------------------------------------------------------

def targets(db, limit: int = 25) -> list[dict]:
    """Harvested sellers worth a hand-written email, best first.

    Ready-to-write rows come first: a seller we already have a person's name
    for can be drafted now, while a role inbox costs ten minutes of looking
    first. Within each group, biggest estimated revenue wins.
    """
    rows = db.table("harvest_sellers").select("*").in_("status", ["pushed", "enriched"]).execute().data
    # Which sellers have a listing we can quote a fee cliff from. Two things
    # gate a sendable email and they are independent: knowing who to write to,
    # and having a number to open with.
    with_hook = {p["seller_id"] for p in
                 db.table("harvest_products").select("seller_id, weight_oz, platform").execute().data
                 if p.get("weight_oz") and cliff_for(p.get("platform"), float(p["weight_oz"]))}
    keep = []
    for r in rows:
        if icp.off_icp(r.get("brand") or r.get("seller_name"), r.get("email"), r.get("website"))[0]:
            continue
        named = bool(r.get("first_name")) and not icp.bad_greeting(r.get("first_name"))
        if not named and not icp.is_role_inbox(r.get("email")):
            named = True   # a personal address is a person, even unnamed
        # An address on a domain that is not the brand's is the wrong person,
        # however personal it looks: harvest resolved Rhino USA (rhinousa.com)
        # to micah@micahrich.com. Marking that "ready" would send the batch's
        # best-looking row to a stranger.
        if icp.domain_mismatch(r.get("email"), r.get("website")):
            named = False
        hook = r["seller_id"] in with_hook
        keep.append({**r, "named": named, "has_hook": hook, "ready": named and hook})
    keep.sort(key=lambda r: (not r["ready"], not r["has_hook"], not r["named"],
                             -(float(r.get("est_monthly_revenue") or 0))))
    return keep[:limit]


def target_label(r: dict) -> str:
    if r["ready"]:
        return "READY"
    if r["named"]:
        return "NEEDS A NUMBER"
    if r["has_hook"]:
        return "FIND THE OWNER"
    return "FIND THE OWNER AND A NUMBER"


def pack_text(db, limit: int, calendly_url: str) -> str:
    """A day's worth of founder-lane work in one page.

    The founder's call on 2026-09-03 was to hand-work these rather than cold
    email them, so the bottleneck is no longer leads, it is the ten minutes a
    person spends per brand. This puts the brief and the draft side by side so
    that ten minutes is spent looking up a name, not running commands.
    """
    rows = targets(db, limit)
    if not rows:
        return "No sellers on file are ready for the founder lane yet. Run `hubricon harvest all` first."
    ready = [r for r in rows if r["ready"]]
    out = [
        "FOUNDER LANE — today's batch",
        f"  {len(ready)} of {len(rows)} are ready to write. Two things gate an email: "
        "who to write to, and a number to open with.",
        "  Five to eight a day. Ten at the very most. Send from your own mailbox, by hand.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        facts = seller_facts(db, r["seller_id"])
        if facts is None:
            continue
        out += ["=" * 78, f"{i}. {r.get('brand') or r.get('seller_name')}   [{target_label(r)}]",
                "=" * 78, ""]
        out += [brief_text(facts), ""]
        if r["named"]:
            d = founder_email(facts, r.get("first_name") or "there", calendly_url)
            label = "DRAFT" if d["complete"] else "DRAFT — INCOMPLETE, needs a number before it can go"
            out += ["  " + label, f"  To:      {d['to']}"
                    + ("   (guessed address — Instantly's verifier has not seen this one)"
                       if (r.get("email_confidence") == "pattern") else ""),
                    f"  Subject: {d['subject']}", ""]
            out += ["  " + line for line in d["body"].split("\n")]
        else:
            site = (r.get("website") or "").rstrip("/")
            if icp.domain_mismatch(r.get("email"), r.get("website")):
                out += [f"  NOTE: {r.get('email')} is not on {site}. The address we hold is probably",
                        "  someone else's. Find the real one on the site before anything is sent.", ""]
            out += [
                "  FIND THE OWNER (about ten minutes), then:",
                f"    hubricon outreach draft --seller {r['seller_id']} --first-name <name>",
                "",
                "  Where to look, in order:",
                f"    1. {site}/pages/about  —  the founder's story is usually signed",
                f"    2. LinkedIn: \"{r.get('brand') or ''}\" founder OR owner",
                f"    3. {site}/policies/contact-information  —  Shopify makes every store publish one"
                if platform_of(r) == "shopify" else
                "    3. Amazon storefront → \"About the seller\"",
                f"    4. {r.get('business_name') or 'the legal name'} in the "
                + (f"{r['state']} business registry" if r.get("state") else "state business registry")
                + " — an LLC filing names its members",
            ]
        out += [""]
    out += ["=" * 78,
            "Every one of these is yours to send. Nothing here emails anyone automatically."]
    return "\n".join(out)


# -- the per-seller brief ------------------------------------------------------

def seller_facts(db, seller_id: str) -> dict | None:
    """Everything the harvest holds about one seller, plus the cliff per item.

    The cliff comes from the seller's platform, not the product's: an Amazon
    listing is measured against the FBA fee bands, a Shopify product against
    the carrier's shipping bands.
    """
    srows = db.table("harvest_sellers").select("*").eq("seller_id", seller_id).execute().data
    if not srows:
        return None
    s = srows[0]
    platform = platform_of(s)
    prods = db.table("harvest_products").select("*").eq("seller_id", seller_id).execute().data
    items = []
    for p in prods:
        weight = float(p["weight_oz"]) if p.get("weight_oz") is not None else None
        cliff = cliff_for(platform, weight)
        items.append({
            "asin": p.get("asin"), "title": (p.get("title") or "")[:70], "price": p.get("price"),
            "weight_oz": weight, "bsr": p.get("bsr"), "units": p.get("est_monthly_units"),
            "revenue": p.get("est_monthly_revenue"),
            "band_edge": cliff[0] if cliff else None, "over_by": cliff[1] if cliff else None,
        })
    items.sort(key=lambda i: (i["over_by"] is None, i["over_by"] or 0))
    return {"seller": s, "items": items, "platform": platform}


def brief_text(facts: dict) -> str:
    """A page the founder reads before writing. Ends in a verification checklist.

    The checklist is not decoration. The harvest resolved Rhino USA to
    micah@micahrich.com and a brand called BigFoot to a 1990s email provider,
    and it stored "Washington" as Sol de Janeiro's contact first name. Every
    one of those would have been visible in ten seconds of looking.
    """
    s, items = facts["seller"], facts["items"]
    platform = facts.get("platform") or platform_of(s)
    shop = platform == "shopify"
    site = (s.get("website") or "").rstrip("/")
    rev = s.get("est_monthly_revenue")
    lines = [
        f"{s.get('brand') or s.get('seller_name')}  ({s.get('seller_id')})",
        f"  platform      {PLATFORM_LABEL.get(platform, 'Amazon')}",
        f"  storefront    {s.get('seller_name')}",
        f"  legal name    {s.get('business_name') or '—'}",
        f"  address       {', '.join(x for x in (s.get('city'), s.get('state'), s.get('country')) if x) or '—'}",
        f"  website       {s.get('website') or '—'}",
        f"  contact       {s.get('email') or '—'}  ({s.get('email_confidence') or 'none'})",
        f"  person        {s.get('first_name') or '—'} {s.get('last_name') or ''}".rstrip(),
        f"  reviews       {s.get('reviews_max') or '?'} on the busiest listing we sampled" if shop else
        f"  feedback      {s.get('ratings_12mo') or '?'} in 12 months, {s.get('ratings_lifetime') or '?'} lifetime",
        (f"  est revenue   ${float(rev):,.0f}/mo (estimate from public review counts and prices)" if shop else
         f"  est revenue   ${float(rev):,.0f}/mo (estimate from public rank and price)") if rev else
        "  est revenue   unknown",
        f"  category      {s.get('top_category') or '—'}" if shop else
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
    if best and shop:
        below, above = shopify.band_names(best["band_edge"])
        lines.append(f"    {best['asin']} ships at {best['weight_oz']:g} oz; the {below} band ends at "
                     f"{best['band_edge']} oz, so every unit pays the {above} rate on USPS and UPS.")
    elif best:
        lines.append(f"    {best['asin']} ships at {best['weight_oz']:g} oz. The band below ends at "
                     f"{best['band_edge']} oz, so it is {best['over_by']:g} oz into the next fee band "
                     f"on every unit.")
    else:
        lines.append(f"    No {CLIFF_LABEL.get(platform, CLIFF_LABEL['amazon'])} hook for this seller. Find "
                     "another specific, checkable number before writing, or skip them.")
    lines += ["", "  Verify before sending (the harvest gets these wrong):",
              "    [ ] the website really belongs to this brand"]
    if shop:
        item = best or (items[0] if items else None)
        lines += [f"    [ ] a named owner exists — {site}/pages/about, LinkedIn, "
                  f"{site}/policies/contact-information",
                  "    [ ] still roughly $1M-$20M/yr — the revenue above is estimated from review "
                  "counts, which is rough",
                  "    [ ] the packed weight still matches: "
                  + (f"https://{item['asin']}" if item else f"{site}/products/…")]
    else:
        lines += ["    [ ] a named owner exists — About page, LinkedIn, Amazon storefront 'About the seller'",
                  "    [ ] still roughly $1M-$20M/yr, not an aggregator or a household name",
                  "    [ ] the weight on the live listing still matches what we stored"]
    return "\n".join(lines)


def founder_email(facts: dict, first_name: str, calendly_url: str) -> dict:
    """A draft for the founder to edit and send from his own mailbox.

    Short, specific, one ask, no tracking. The claims match the website and the
    triage fact sheet: free teardown, $6,000/mo after, first month free.
    """
    s, items = facts["seller"], facts["items"]
    platform = facts.get("platform") or platform_of(s)
    brand = s.get("brand") or s.get("seller_name")
    best = next((i for i in items if i["over_by"] is not None), None)
    if best and platform == "shopify":
        below, above = shopify.band_names(best["band_edge"])
        subject = f"{brand}: {best['over_by']:g} oz over a shipping band"
        hook = (f"Your {_short_title(best)} ships at {best['weight_oz']:g} oz; the {below} band ends at "
                f"{best['band_edge']} oz, so every unit pays the {above} rate on USPS and UPS. "
                f"Public product page, public weight — I have no access to your store.")
    elif best:
        subject = f"{brand}: {best['over_by']:g} oz over an FBA fee band"
        hook = (f"Your {_short_title(best)} lists at {best['weight_oz']:g} oz. "
                f"The FBA weight band below it ends at {best['band_edge']} oz, so every unit you ship "
                f"pays the next band up. Public page, public weight — I have no access to your account.")
    else:
        # No listing on file, so there is no checkable number. Refuse to write
        # the plausible-sounding version: "the fee side looks like it's costing
        # you more than it should" asserts a problem we have not measured, and
        # a seller can tell the difference between that and an ounce count.
        # Leave the gap visible so it cannot be sent by accident.
        subject = f"{brand}: [ONE SPECIFIC NUMBER — see the brief]"
        hook = (f"[NO HOOK ON FILE. Open one of their listings, check the packed weight against the "
                f"{CLIFF_LABEL.get(platform, CLIFF_LABEL['amazon'])} below it, or find another number you "
                f"can point at. Replace this whole paragraph with it. Do not send this email without one.]")
    who = "Amazon private-label brands" if platform != "shopify" else "founder-run Shopify brands"
    body = (
        f"Hi {first_name},\n\n"
        f"{hook}\n\n"
        f"I run Hubricon. I do the margin math for {who}: what each price can "
        f"take before units drop, where the next ad dollar stops paying, which SKU stocks out first.\n\n"
        f"If it's useful I'll do a written Profit Teardown of {brand} for free. "
        f"{EXPORTS.get(platform, EXPORTS['amazon'])}, about fifteen minutes on your side, and the report "
        f"is back within 24 hours. No seat "
        f"in your account, no card, and if it finds nothing worth fixing I'll tell you that and you "
        f"keep the report.\n\n"
        f"Worth a look? Reply and I'll send the upload page, or grab 20 minutes: {calendly_url}\n\n"
        f"Hagen Simmons\nHubricon\n"
    )
    return {"to": s.get("email"), "subject": subject, "body": body, "complete": best is not None}


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
    platform = facts.get("platform") or platform_of(s)
    brand = s.get("brand") or s.get("seller_name")
    best = next((i for i in items if i["over_by"] is not None), None)
    if not best:
        raise ValueError("partner_email needs a listing with a fee cliff to quote")
    units = f"about {float(best['units']):,.0f} units a month (estimated from public rank)" \
        if best.get("units") else "every unit it ships"
    if platform == "shopify":
        below, above = shopify.band_names(best["band_edge"])
        seller_kind, band = "Shopify brands", f"{below} USPS/UPS band"
        cost = f"pays the {above} rate"
    else:
        seller_kind, band = "Amazon sellers", f"{best['band_edge']} oz FBA band"
        cost = "pays the next band's fee"
    body = (
        f"{partner_name} — you work with {seller_kind}; I do margin analytics for a few of them.\n\n"
        f"I pulled {_possessive(brand)} public listing ({best['asin']}): it ships at {best['weight_oz']:g} oz, "
        f"{best['over_by']:g} oz over the {band}, so it {cost} on {units}. "
        f"Public page, public weight — no account access.\n\n"
        f"If it's useful to your clients: they get a free written Profit Teardown and a free first "
        f"month, you get the anonymised results to publish and {referral_terms}. Want the one-pager?\n\n"
        f"Hagen Simmons\nHubricon\n"
    )
    return {"subject": f"one number on {brand}'s listing", "body": body}
