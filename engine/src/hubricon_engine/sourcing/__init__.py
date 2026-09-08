"""Finding Shopify stores worth writing to, before the cold engine writes to them.

`hubricon teardown` can already model a store and draft the email; what it
cannot do is *find* stores. The Shopify discovery that existed before this
package was six Bing searches a run against `site:shop.app`, plus a Wayback
index of `*.myshopify.com` homepages that OPERATIONS.md records as close to
worthless — together about 120 stores a run, every page through headless
Chrome at six seconds each.

This package is the funnel in front of that, and it is deliberately shaped
around what is free:

    discover.py   millions of domains        free
    score.py      ~2% survive                free
    contact.py    ~40% of those resolve      free, and honest about the rest

The order matters. Discovery is solved and cheap; qualification is the whole
job. Build the score first or you drown in dropshippers.

Three things were measured on 2026-09-05 and each one changed the design:

  * **The Meta Ad Library is not usable here.** Meta's own docs for
    `ads_archive`: ads that did not reach the EU come back only if they are
    about social issues, elections or politics. Commercial DTC ads are an
    EU-only dataset — and `cold/settings.py` suppresses EU/UK/EEA/CH entirely
    for want of a legitimate-interest basis. The one geography the API serves
    is the one we refuse to mail, so there is no ad-spend signal here and
    `stack.py` stands in for it.
  * **Tranco plus DNS is the discovery unlock.** A Shopify store on its own
    domain resolves into 23.227.38.0/24 or CNAMEs to shops.myshopify.com
    (allbirds.com → 23.227.38.32, gymshark.com → 23.227.38.65). The Tranco
    top-1M list is a free download, a million DNS lookups is minutes, and not
    one request touches a store. Better still, the rank *is* the size signal
    that a bulk crawl of the open web cannot give.
  * **Plain HTTP is not always refused.** `harvest/shopify.py` sends every
    Shopify request through Chrome on the strength of a 2026-09-04 run where
    every plain fetch answered 429. Re-tested across seven stores and three
    user agents: allbirds, brooklinen and drinkolipop returned 200 with full
    JSON on plain HTTP regardless of the agent, while gymshark, ridge and
    bombas refused every client alike. The blocker is the store's edge, not
    the client, so `fetch.py` tries plain first and escalates only when it
    has to.

Modules:

    fetch.py      plain-first, Chrome-on-refusal, over harvest's own Fetcher
    discover.py   Tranco → DNS → HTTP fingerprint, plus the existing search route
    catalog.py    /products.json → price ladder, compare-at, catalogue velocity
    stack.py      the paid apps a storefront loads, which is the spend proxy
    score.py      the free signals, weighted, and the calibration harness
    contact.py    a named person, and the published/pattern distinction
    sheet.py      the Google Sheet (Apps Script webhook) and the CSV beside it
    push.py       the Instantly holding pen — and the four fences around it
    run.py        the passes, the promotion into harvest_sellers, launchd

**Nothing in this package sends an email.** `push.py` writes to a lead list
that `outbound.enroll_from_lists` cannot match, promoted rows land at
`candidate` where `harvest/run.py::push` does not look for them, and every
teardown built from them goes through `hubricon teardown review` like any
other. That is a requirement, not an accident: see the fences in push.py.
"""
