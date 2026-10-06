"""The short source line a figure frame shows (FILM_LOOK_V3.md: every sourced figure says where
it comes from, in one label slot). A fact's `source` is provenance for a person checking it: a
URL, or a long engine note. On screen it becomes a name a viewer can read: a title we know, else
the publisher. Never a guessed title. Demo and case-study figures show none, because their
honesty label already says what they are."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Titles checked against the sources themselves (G01's research); a URL not here falls back to
# its publisher, never to a guess.
TITLES = {
    "archive.org/details/parcelpostreport00unit": "Joint Committee of Congress on Parcel Post, report of December 1, 1914",
    "www.govinfo.gov/content/pkg/STATUTE-37/pdf/STATUTE-37-Pg539.pdf": "The Parcel Post Act, 37 Stat. 539 (1912)",
    "archive.org/details/searsannualreports": "Sears, Roebuck and Co., annual reports",
    "archive.org/details/visittosearsroeb00sear": "A Visit to Sears, Roebuck and Co., Chicago, 1914",
    "archive.org/details/ElectricalGoodsCatalogue134": "Sears, Roebuck and Co. catalogue, spring 1917",
    "archive.org/details/crossroadsoffree007728mbp": "The Crossroads of Freedom: the 1912 campaign speeches of Woodrow Wilson",
    "archive.org/details/sim_cosmopolitan_1904-02_36_4": "The Cosmopolitan, February 1904",
    "archive.org/details/sim_marketing-communications-1888_1918-08-08_104_6": "Printers’ Ink, August 8, 1918",
    "about.usps.com/publications/pub100.pdf": "USPS, The United States Postal Service: An American History",
    "about.usps.com/who/profile/history/pdf/on-this-day.pdf": "USPS, On This Day in Postal History",
    "about.usps.com/who/profile/history/pdf/rural-free-delivery.pdf": "USPS, Rural Free Delivery",
    "about.usps.com/who/profile/history/pdf/universal-service-postal-monopoly-history.pdf": "USPS, Universal Service and the Postal Monopoly",
    "www.nber.org/system/files/chapters/c10234/c10234.pdf": "Raff and Temin, NBER",
    "www.baltimoresun.com/news/bs-xpm-1993-01-26-1993026112-story.html": "The Baltimore Sun, January 26, 1993",
}
PUBLISHERS = {
    "archive.org": "Internet Archive", "about.usps.com": "USPS", "www.uspsoig.gov": "USPS Office of Inspector General",
    "www.prc.gov": "Postal Regulatory Commission", "www.govinfo.gov": "U.S. Government Publishing Office",
    "www.nber.org": "NBER", "www.searsarchives.claeys.co": "Sears Archives", "www.chicago.gov": "City of Chicago",
    "www.immigrantentrepreneurship.org": "Immigrant Entrepreneurship", "static.moaf.org": "Museum of American Finance",
    "www.sil.si.edu": "Smithsonian Libraries", "postalmuseum.si.edu": "Smithsonian National Postal Museum",
    "www.baltimoresun.com": "The Baltimore Sun",
}
COVERED = re.compile(r"demo data|demo catalogue|public-data case study|Tarnhollow|\.RUN|\.EV|\.FIT|MARGIN\.|NEWSVENDOR|"
                     r"SPEND\.|ANOMALY\.|PRICE\.|cash horizon|health score|forecast ladder|policy constants|reason-code|module note",
                     re.I)


def one(source: str) -> str | None:
    """A readable name for one fact source, or None when the honesty label covers it."""
    s = str(source or "").strip()
    if not s or COVERED.search(s):
        return None
    m = re.match(r"https?://(\S+?)(?:[\s(]|$)", s)
    if m:
        key = m.group(1).rstrip("/")
        if key in TITLES:
            return TITLES[key]
        host = urlparse("https://" + key).netloc
        return PUBLISHERS.get(host, host.removeprefix("www."))
    # a written source ("Amazon's published US FBA fee card, 2026 non-peak schedule (…), as recorded in …")
    s = re.split(r",\s*as recorded|\s\(", s)[0]
    return s.strip(" ,;")


def label(keys: list[str], facts: dict, limit: int = 2) -> str | None:
    """The shot's source line: the distinct sources of the figures it reveals, at most `limit`."""
    names: list[str] = []
    for k in keys:
        n = one(facts.get(k, {}).get("source", ""))
        if n and n not in names:
            names.append(n)
    return " · ".join(names[:limit]) or None
