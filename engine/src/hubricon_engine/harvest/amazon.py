"""Parsers for the three public Amazon pages the harvest reads, plus the
BSR → units curve. Pure functions over page text; nothing here fetches.

Best Sellers  /gp/bestsellers/<slug>, /…/zgbs/<slug>/<node>   → ASINs, child categories, page 2
Product       /dp/<ASIN>                                       → brand, seller id, fulfilment, rank, price, reviews, weight, dims
Seller        /sp?seller=<id>                                  → business name and address (public since 2020-09-01)
"""

from __future__ import annotations

import html
import math
import re

BASE = "https://www.amazon.com"
AMAZON_MERCHANT_IDS = {"ATVPDKIKX0DER"}  # Amazon.com itself
AMAZON_SELLER_NAMES = ("amazon.com", "amazon resale", "amazon warehouse", "amazon")

# Best Sellers category slugs where founder-run private label lives.
CATEGORIES = [
    "kitchen", "home-garden", "beauty", "hpc", "pet-supplies", "sporting-goods",
    "toys-and-games", "baby-products", "office-products", "automotive", "lawn-garden",
    "grocery", "arts-crafts", "industrial", "musical-instruments",
]

# units/month from the top-level category rank. Below rank 1,000 the public
# estimators' Home & Kitchen curve is close to a power law
# (1,000 ≈ 2,000/mo, 10,000 ≈ 270, 100,000 ≈ 35); above it the curve flattens
# (rank 1 ≈ 90k/mo, not the 800k a straight extrapolation gives). Scaled per
# category, always labeled an estimate.
CURVE_A, CURVE_B = 5.925, 0.875
HEAD_KNEE, HEAD_EXP = 1000, 0.55
CATEGORY_SCALE = {
    "home & kitchen": 1.0, "kitchen & dining": 0.9, "beauty & personal care": 1.0,
    "health & household": 1.1, "pet supplies": 0.8, "sports & outdoors": 0.8,
    "toys & games": 0.8, "baby": 0.6, "office products": 0.7, "automotive": 0.5,
    "patio, lawn & garden": 0.6, "grocery & gourmet food": 0.9, "arts, crafts & sewing": 0.5,
    "industrial & scientific": 0.5, "musical instruments": 0.3, "tools & home improvement": 0.7,
    "electronics": 1.0, "clothing, shoes & jewelry": 1.0, "cell phones & accessories": 0.8,
}
DEFAULT_SCALE = 0.6

RESELLER_WORDS = ("trading", "wholesale", "distribut", "import", "deals", "outlet", "warehouse",
                  "liquidat", "surplus", "resale", "supply co", "supplies inc", "marketplace")
OFFSHORE_WORDS = ("shenzhen", "guangzhou", "dongguan", "yiwu", "hangzhou", "shanghai", "ningbo",
                  "co., ltd", "co.,ltd", "co. ltd", "technology co", "trade co", "e-commerce co",
                  "electronic co", "network technology")
# Corporate parents and aggregators: the brand may look private-label on the
# listing, but the seller of record is a conglomerate or a portfolio company,
# not a founder. First pass (2026-09-03) surfaced Unilever, Nestlé, Church &
# Dwight and Pattern in the top 40 of Health & Household.
BIG_PARENT_WORDS = (
    "nestle", "unilever", "procter", "church & dwight", "church and dwight", "johnson & johnson", "kimberly",
    "colgate", "reckitt", "clorox", "henkel", "newell", "spectrum brands", "helen of troy", "hasbro", "mattel",
    "central garden", "purina", "kraft", "pepsico", "coca-cola", "l'oreal", "estee lauder", "shiseido",
    "beiersdorf", "edgewell", "energizer", "stanley black", "hanesbrands", "vf corp", "abbott", "bayer",
    "glaxo", "haleon", "kenvue", "pfizer", "sc johnson", "s.c. johnson", "prestige consumer", "perrigo",
    "pattern inc", "pattern.", "thrasio", "perch", "razor group", "heyday", "branded group", "unybrands",
    "suma brands", "elevate brands", "boosted commerce", "forum brands", "accel club", "d1 brands", "olsam",
    "berlin brands", "dragonfly", "moonshot brands", "acquco", "factory14", "benitago", "accelerator store",
)
NAME_NOISE = ("llc", "inc", "co", "ltd", "corp", "corporation", "company", "store", "official",
              "shop", "usa", "us", "the", "brand", "brands", "group", "international", "direct",
              "products", "home", "online", "retail", "global", "enterprises", "l.l.c")


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def _int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


# -- Best Sellers ---------------------------------------------------------------

def bestseller_page(page: str) -> dict:
    asins = list(dict.fromkeys(re.findall(r"/dp/([A-Z0-9]{10})", page)))
    subs = list(dict.fromkeys(re.findall(r'href="(/[^"?#]*?/zgbs/[a-z0-9-]+/\d+)', page)))
    nxt = re.search(r'href="([^"]*zgbs/[^"]*pg=2[^"]*)"', page)
    return {
        "asins": asins,
        "subcategories": [BASE + s for s in subs],
        "next": BASE + html.unescape(nxt.group(1)) if nxt else None,
    }


def category_url(slug: str) -> str:
    return f"{BASE}/gp/bestsellers/{slug}"


# -- Product --------------------------------------------------------------------

def weight_to_oz(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"([\d.,]+)\s*(ounces?|oz|pounds?|lbs?|grams?|g|kilograms?|kg)\b", s, re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    unit = m.group(2).lower()
    if unit.startswith(("pound", "lb")):
        return round(n * 16, 3)
    if unit.startswith(("kilogram", "kg")):
        return round(n * 35.274, 3)
    if unit.startswith(("gram", "g")):
        return round(n / 28.3495, 3)
    return round(n, 3)


def estimate_units(bsr: int | None, category: str | None) -> float | None:
    """Monthly units from a top-level category rank. An estimate, labeled as such."""
    if not bsr or bsr < 1:
        return None
    scale = CATEGORY_SCALE.get((category or "").strip().lower(), DEFAULT_SCALE)
    knee = 10 ** (CURVE_A - CURVE_B * math.log10(HEAD_KNEE))
    if bsr >= HEAD_KNEE:
        units = 10 ** (CURVE_A - CURVE_B * math.log10(bsr))
    else:
        units = knee * (HEAD_KNEE / bsr) ** HEAD_EXP
    return round(scale * units, 1)


def _detail(page: str, label: str) -> str | None:
    # table form: <th>Item Weight</th><td>2.4 ounces</td>
    # bullet form: <span>Item Weight ‏ : ‎</span> <span>2.4 ounces</span>
    m = re.search(label + r"[^<]*</t[dh]>\s*<t[dh][^>]*>\s*([^<]+)", page)
    if not m:
        m = re.search(label + r"[^<]*</span>\s*<span[^>]*>\s*([^<]+)", page)
    return _text(m.group(1)) if m else None


def product(page: str, asin: str | None = None) -> dict:
    out: dict = {"asin": asin}
    m = re.search(r'data-csa-c-asin="([A-Z0-9]{10})"', page)
    if not asin and m:
        out["asin"] = m.group(1)
    m = re.search(r'id="productTitle"[^>]*>\s*([^<]+)', page)
    out["title"] = _text(m.group(1))[:200] if m else None
    m = re.search(r"Visit the (.+?) Store<", page)
    if m:
        out["brand"] = _text(m.group(1))
    else:
        m = re.search(r'id="bylineInfo"[^>]*>\s*Brand:\s*([^<]+)', page)
        out["brand"] = _text(m.group(1)) if m else None
    m = re.search(r"[?&;]seller=([A-Z0-9]{10,16})", page)
    out["seller_id"] = m.group(1) if m else None
    m = re.search(r"Sold by:?\s*</span>\s*<span[^>]*>\s*([^<]+)", page) or \
        re.search(r"id=['\"]sellerProfileTriggerId['\"][^>]*>([^<]+)</a>", page)
    out["seller_name"] = _text(m.group(1)) if m else None
    m = re.search(r"Ships from:?\s*</span>\s*<span[^>]*>\s*([^<]+)", page)
    ships = _text(m.group(1)) if m else None
    out["ships_from"] = ships
    merchant_amazon = bool(re.search(r"merchantId[\"']?\s*[:=]\s*[\"']?ATVPDKIKX0DER", page))
    name = (out["seller_name"] or "").lower()
    out["sold_by_amazon"] = name in AMAZON_SELLER_NAMES or (out["seller_id"] is None and merchant_amazon)
    out["fba"] = bool(ships and "amazon" in ships.lower()) or "isAmazonFulfilled=1" in page
    m = re.search(r'a-price-whole">([\d,]+).{0,120}?a-price-fraction">(\d{2})', page, re.S)
    out["price"] = float(m.group(1).replace(",", "") + "." + m.group(2)) if m else None
    m = re.search(r'id="acrCustomerReviewText"[^>]*>([^<]+)', page)
    out["reviews"] = _int(m.group(1)) if m else None
    i = page.find("Best Sellers Rank")
    out["bsr"], out["category"] = None, None
    if i > 0:
        t = _text(page[i:i + 1500])
        ranks = re.findall(r"#([\d,]+)\s+in\s+([A-Za-z&,'\- ]+?)\s*(?:\(|#|$)", t)
        if ranks:
            out["bsr"], out["category"] = _int(ranks[0][0]), ranks[0][1].strip()
    out["weight_oz"] = weight_to_oz(_detail(page, "Item Weight"))
    out["dims"] = _detail(page, r"(?:Product|Package|Item) Dimensions")
    out["related"] = [a for a in dict.fromkeys(re.findall(r'data-asin="([A-Z0-9]{10})"', page))
                      if a != out["asin"]]
    out["est_monthly_units"] = estimate_units(out["bsr"], out["category"])
    out["est_monthly_revenue"] = (round(out["est_monthly_units"] * out["price"], 2)
                                  if out["est_monthly_units"] and out["price"] else None)
    return out


# -- Seller profile -------------------------------------------------------------

def seller(page: str) -> dict:
    out: dict = {"business_name": None, "address": None, "city": None, "state": None,
                 "zip": None, "country": None, "seller_name": None, "emails": []}
    m = re.search(r'id="seller-name"[^>]*>\s*([^<]+)', page)
    out["seller_name"] = _text(m.group(1)) if m else None
    m = re.search(r"Business Name:\s*</span>\s*<span[^>]*>([^<]+)", page)
    out["business_name"] = _text(m.group(1)) if m else None
    i = page.find("Business Address")
    if i > 0:
        lines = [_text(x) for x in re.findall(r'indent-left"[^>]*>\s*<span[^>]*>([^<]*)</span>', page[i:i + 2500])]
        lines = [l for l in lines if l]
        if len(lines) >= 4:
            out["country"], out["zip"], out["state"], out["city"] = lines[-1], lines[-2], lines[-3], lines[-4]
            out["address"] = ", ".join(lines[:-4] + [out["city"], f"{out['state']} {out['zip']}", out["country"]])
        elif lines:
            out["address"] = ", ".join(lines)
            out["country"] = lines[-1] if re.fullmatch(r"[A-Z]{2}", lines[-1]) else None
    text = _text(page)
    out["emails"] = sorted({e.lower() for e in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
                            if not e.lower().endswith(("amazon.com", ".png", ".jpg", ".gif"))})
    return out


def seller_url(seller_id: str) -> str:
    return f"{BASE}/sp?seller={seller_id}"


# -- Who is a private-label brand ------------------------------------------------

def norm_name(s: str | None) -> str:
    words = re.findall(r"[a-z0-9]+", (s or "").lower())
    return "".join(w for w in words if w not in NAME_NOISE)


def looks_private_label(brand: str | None, seller_name: str | None, business_name: str | None) -> bool:
    """The seller *is* the brand: the brand token appears in the storefront or legal name."""
    b = norm_name(brand)
    if len(b) < 3:
        return False
    return any(b in norm_name(n) or (len(norm_name(n)) >= 3 and norm_name(n) in b)
               for n in (seller_name, business_name) if n)


def looks_reseller(seller_name: str | None, business_name: str | None, brand_count: int) -> bool:
    joined = f"{seller_name or ''} {business_name or ''}".lower()
    return brand_count >= 3 or any(w in joined for w in RESELLER_WORDS)


def looks_offshore(business_name: str | None, address: str | None) -> bool:
    joined = f"{business_name or ''} {address or ''}".lower()
    return any(w in joined for w in OFFSHORE_WORDS)


def looks_big_parent(seller_name: str | None, business_name: str | None) -> bool:
    joined = f"{seller_name or ''} {business_name or ''}".lower()
    return any(w in joined for w in BIG_PARENT_WORDS)


# -- Fee cliffs (the data post) --------------------------------------------------

# FBA fulfilment-fee weight bands, US schedule since 2024: small standard in
# 2-oz steps to 16 oz, large standard in 4-oz steps to 3 lb, then 4-oz
# increments to 20 lb. A listing just above an edge pays the next band's fee
# on every unit; trimming packaging by that distance drops it a band. Edges
# only — the dollar amounts move yearly and are not needed for the finding.
WEIGHT_BAND_EDGES_OZ = [2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 36, 40, 44, 48] + [48 + 4 * i for i in range(1, 69)]


def fee_cliff(weight_oz: float | None) -> tuple[int, float] | None:
    """→ (band edge below, ounces above it) for a listing, or None when unknown / in the lightest band."""
    if not weight_oz or weight_oz <= WEIGHT_BAND_EDGES_OZ[0]:
        return None
    below = max(e for e in WEIGHT_BAND_EDGES_OZ if e < weight_oz)
    return below, round(weight_oz - below, 3)
