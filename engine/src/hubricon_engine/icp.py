"""Who is actually in the ICP — one classifier, used on the way in and on the way out.

Hubricon sells to Amazon private-label brands doing roughly $1M-$20M a year.
It does not sell to the people who sell services to those brands.

The SuperSearch keyword exclusions in outbound.SUPERSEARCH_FILTERS were meant
to do this upstream and did not: the 50 leads Instantly returned on 2026-09-02
included six agencies, three finance firms, two freight forwarders and
SmartScout, a direct competitor. Instantly's keyword filter reads a company's
own marketing copy, and an agency whose site says "we grow Amazon FBA brands"
matches "Amazon FBA" exactly as well as a brand does.

So the filter runs here too, on the company name we actually hold, and it runs
at enrollment rather than at push: a lead that never enters the campaign cannot
burn a two-month-old domain. Everything in this module is a pure function over
strings so it can be tested without a database or an API key.
"""

import re

# Service businesses that sell TO Amazon sellers. A brand sells products.
_AGENCY = (
    "agency", "agencies", "marketing group", "digital marketing", "ppc", "media buying",
    "consulting", "consultants", "consultancy", "advisors", "advisory",
    "commerce partners", "ecommerce agency", "growth partners", "brand management",
    "seller services", "account management", "full service",
)
# Tools and platforms, including the ones that compete with Hubricon directly.
_SOFTWARE = (
    "software", "saas", "platform", "analytics", "dashboard", "app", "api",
    "technologies", "tech labs", "data", "intelligence", "insights",
    "smartscout", "jungle scout", "helium 10", "keepa", "sellerboard", "datahawk",
    "perpetua", "pacvue", "teikametrics", "quartile", "downstream",
)
# Money. They fund sellers; they are not sellers.
_FINANCE = (
    "capital", "ventures", "partners lp", "equity", "holdings", "invest", "lending",
    "lender", "loans", "factoring", "trustees", "wealth", "financial", "finlocker",
    "accounting", "bookkeeping", "cpa", "tax", "insurance", "bank",
)
# Moving boxes. Also not sellers.
_LOGISTICS = (
    "logistics", "freight", "3pl", "prep center", "prep centre", "fulfillment services",
    "fulfilment services", "cargo", "forwarder", "warehousing", "supply chain",
    "shipoffers", "unicargo",
)
# Reviewed by hand on 2026-09-03 from the first 50 SuperSearch leads. A company
# name alone cannot tell you that "Bellavix" or "Blueoco" is an agency, so the
# ones already verified are named here. This list is a record of review, not a
# detector: new junk still arrives and still has to be read by a person.
_KNOWN_NON_ICP = {
    "bellavix": "agency", "omg commerce": "agency", "evolved commerce": "agency",
    "ecomm-inroads": "agency", "marketplace sorted": "agency", "brand guarde": "agency",
    "blueoco": "agency", "amz atlas": "education", "smartscout": "software",
    "whipstitch capital": "finance", "custom travel solutions": "not a product brand",
    "white label communications": "not a product brand", "devon office furniture": "not ICP",
    "calmare therapeutics": "public company",
}
# Teaching people to sell on Amazon is a different business from selling on it.
_EDUCATION = ("coaching", "course", "mastermind", "academy", "training", "bootcamp", "mentor")
# Aggregators and roll-ups buy brands; they have their own analytics teams.
_AGGREGATOR = (
    "thrasio", "perch", "aggregator", "roll-up", "rollup", "acquisition", "acquires brands",
    "brand aggregator", "portfolio of brands",
)
# Public companies and household names never answer a cold email from a new vendor.
_TOO_BIG = (
    "incorporated (otc", "(otcqb", "(nasdaq", "(nyse", "plc", "l'oreal", "loreal",
    "unilever", "nestle", "procter", "colgate", "church & dwight", "reckitt",
    "sol de janeiro", "fellow", "weiman", "cerakote", "gorilla grip", "glamnetic", "boka",
)

_BUCKETS = (
    ("agency", _AGENCY),
    ("software", _SOFTWARE),
    ("finance", _FINANCE),
    ("logistics", _LOGISTICS),
    ("education", _EDUCATION),
    ("aggregator", _AGGREGATOR),
    ("too_big", _TOO_BIG),
)

# Addresses that reach a customer-service queue, not a person who can buy.
# These are not disqualified as leads: they move to the founder lane, where a
# human finds the owner's name first. See outreach.py.
ROLE_LOCALS = frozenset((
    "info", "hello", "hi", "support", "contact", "help", "sales", "orders", "order",
    "service", "customerservice", "customer", "team", "admin", "office", "concierge",
    "care", "inquiries", "enquiries", "shop", "store", "mail", "general", "press",
    "consumerrelations", "hey", "howdy",
))


def _hay(*parts: str | None) -> str:
    return " " + re.sub(r"\s+", " ", " ".join(p or "" for p in parts)).lower().strip() + " "


def off_icp(company_name: str | None, email: str | None = None, website: str | None = None) -> tuple[str | None, str]:
    """-> (bucket, why) when this row is not an Amazon private-label brand.

    (None, "") means nothing disqualifying was found. The check is deliberately
    one-directional: it rejects what is clearly not a brand rather than trying
    to prove that something is one. A false negative costs one wasted email; a
    false positive costs a customer.
    """
    hay = _hay(company_name, website)
    for name, bucket in _KNOWN_NON_ICP.items():
        if " " + name in hay:
            return bucket, f"{bucket}: reviewed by hand on 2026-09-03, not a private-label brand"
    for bucket, words in _BUCKETS:
        for w in words:
            if w in hay:
                return bucket, f"{bucket}: company name matches {w!r}"
    if email:
        local, _, domain = email.lower().partition("@")
        # An address at a free provider is a person, not a brand's own domain.
        if domain in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"):
            return "no_domain", f"contact address is on {domain}, not a brand domain"
    return None, ""


def is_role_inbox(email: str | None) -> bool:
    """True when the address reaches a queue rather than a named person."""
    if not email or "@" not in email:
        return False
    local = re.sub(r"[._-]?\d+$", "", email.split("@", 1)[0].lower())
    return local in ROLE_LOCALS


def domain_mismatch(email: str | None, website: str | None) -> bool:
    """True when the contact address is not on the brand's own domain.

    The enrichment guesses a website and then scrapes an address off it, and
    when the website guess is wrong both are wrong together: harvest resolved
    Rhino USA (rhinousa.com) to micah@micahrich.com, and a brand called BigFoot
    to help@bigfoot.com, a 1990s email provider. The two domains disagreeing is
    the cheapest available signal that the row is fiction.
    """
    if not email or not website or "@" not in email:
        return False
    dom = email.split("@", 1)[1].lower().strip(". ")
    site = re.sub(r"^https?://", "", website.lower()).split("/")[0]
    site = site[4:] if site.startswith("www.") else site
    if not site:
        return False
    return not (dom == site or dom.endswith("." + site) or site.endswith("." + dom))


def bad_greeting(first_name: str | None) -> bool:
    """True when "Hi {first_name}," would read as a mistake.

    harvest stored "Leather" for Leather Honey and "Washington" for Sol de
    Janeiro: the first is half a brand name, the second is a word off an
    address. Both render a greeting that tells the reader this was automated.
    The "<Brand> team" fallback is fine and is not flagged here.
    """
    if not first_name:
        return True
    n = first_name.strip()
    if not n or len(n) < 2:
        return True
    if n.lower().endswith(" team"):
        return False
    # A single capitalised word that is also a US state or a common noun off an
    # address line is the failure mode we saw; require it to look like a name.
    return n.lower() in {
        "washington", "oregon", "virginia", "georgia", "carolina", "dakota", "jersey",
        "york", "mexico", "hampshire", "island", "leather", "honey", "beauty", "brands",
        "company", "group", "usa", "international", "products",
    }
