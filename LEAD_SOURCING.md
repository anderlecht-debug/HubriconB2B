# LEAD_SOURCING.md

Shopify prospect discovery, qualification, and contact resolution.
Companion to `COLD_ENGINE.md` — this fills `prospects` and `prospect_snapshots`.
All §2 constraints in `COLD_ENGINE.md` still apply.

> **Status, 2026-09-07.** This is the brief the `hubricon source` package was
> built from. Three things in it did not survive being measured, and
> OPERATIONS.md ("Sourcing Shopify leads") records what replaced them:
>
> * **§2 Tier 1, the Meta Ad Library, is not usable.** Meta's own `ads_archive`
>   docs: ads that did not reach the EU come back only if they are political or
>   social-issue ads. Commercial DTC ads are EU-only, and the cold engine
>   suppresses EU/UK/EEA/CH outright. The `creative_spend_no_catalog_change`
>   detector in §7 goes with it. An app-stack detector stands in as the spend
>   proxy.
> * **§2 Tier 2, Common Crawl, was dropped.** It needs Athena (billed) or a
>   very large local pull, and returns a domain with no size signal. The Tranco
>   top-1M plus a DNS pass does the same job for free *and* ranks what it
>   returns.
> * **§4's paid verification is not in the build.** The founder is not buying
>   leads or verification, so the rule is published addresses only: a guessed
>   address is recorded and shown, never sent to.
>
> §7's `price_ladder_gap` was also not built as a finding — an AOV gap cannot
> be priced off a published rate card, and the cold engine refuses anything it
> cannot price. It is a column on the sheet instead.

---

## 0. The correct mental model

You're right that Shopify merchants want to be found. Domains are effectively free
and effectively unlimited. But the pipeline has three narrowing stages and only the
first one is free:

```
DISCOVERY        millions of domains        free
QUALIFICATION    ~2% survive                free, mostly
CONTACT          ~40% of those resolve      cheap, not free
```

Getting 100,000 Shopify domains is a weekend. Getting 100,000 that do $1M+ and
where you can reach the person who decides on a $6,000/month commitment is the
actual job. **Build the qualification stage first.** If you build discovery first
you will drown in dropshippers.

---

## 1. The unlock: Shopify publishes the catalog

Every Shopify store exposes its full product catalog with no authentication:

```
GET https://{domain}/products.json?limit=250&page=1     # paginated, all products
GET https://{domain}/collections.json                    # collection structure
GET https://{domain}/products/{handle}.js                # single product detail
GET https://{domain}/sitemap_products_1.xml              # full product index
```

`/products.json` returns every product, every variant, every price, compare-at
price, vendor, tags, `created_at`, and `updated_at`.

This is the single most important fact in this document. **You can run a real
pricing teardown on a Shopify store with zero permission from the merchant.** Not a
guess from category priors — their actual catalog, their actual price ladder, their
actual discount structure.

What you can compute from it directly:

- Full price distribution and the gaps in the ladder
- Compare-at vs price across the catalog: how much of the range is permanently
  "on sale," which is margin given away by default
- Variant sprawl and which variants are unavailable (stockouts)
- Catalog churn from `created_at` / `updated_at` velocity
- Price changes over time, if you snapshot weekly (start snapshotting immediately,
  even before the rest is built — this data is unrecoverable retroactively)

A minority of merchants disable `/products.json`. Fall back to the product sitemap
plus the `.js` endpoint per handle. Detect the block and record it rather than
retrying.

**Manners matter here.** Respect `robots.txt`, cap at roughly one request per second
per domain, set an identifying User-Agent with a contact URL, and cache aggressively.
These are public integration endpoints and normal polite crawling is fine; hammering
them is not, and getting Cloudflare-flagged kills the whole channel.

### Fingerprinting a domain as Shopify

Response headers `x-shopid` and `x-shardid`, `powered-by: Shopify`, `cdn.shopify.com`
in the HTML, or a `Shopify` global in page JS. Cheap and near-perfect.

---

## 2. Discovery sources, ranked

### Tier 1 — Meta Ad Library API (free, official, and it qualifies at the same time)

This is your best source and it isn't close. Free official API, no scraping,
searchable by country and keyword, returns advertiser page, ad creatives, and the
date each went live.

Why it beats everything else: **it only contains merchants who are currently
spending money on ads.** That is simultaneously a discovery mechanism and the
strongest free revenue qualifier available. A brand running 30 active creatives
continuously for 90 days is spending real budget and mathematically cannot be
certain which SKUs survive blended CAC.

Extract the landing page URL from creatives, resolve redirects, fingerprint for
Shopify. Store creative count and longest-running duration on the prospect — these
become both the qualification score and the email's opening line.

Sweep by category keyword across US, UK, CA, AU. Re-sweep weekly; new advertisers
are your freshest cohort.

### Tier 2 — Common Crawl (free, enormous, one-time bulk)

Petabyte-scale open web crawl with a columnar index queryable via Athena in
`us-east-1`. Filter the index for `cdn.shopify.com` references and you get millions
of Shopify domains for compute cost alone. Explicitly licensed for this use.

This gives breadth. It gives you no signal about size, so everything from Tier 2
must pass through §3 before it's worth anything.

Run once, refresh quarterly. Not a weekly job.

### Tier 3 — Review-app public directories (free, high signal)

Judge.me, Loox, Okendo, Yotpo, and Stamped all publish public directories of the
stores using them, linked directly. So does the Shopify App Store review section
for any major app — merchants review under their store name.

Two things come free with each hit: the domain, and one confirmed piece of their
tech stack. A store running Okendo or Yotpo is paying real money for reviews, which
is itself a size filter. Loox and Judge.me skew smaller; Okendo and Yotpo skew to
your range.

### Tier 4 — Paid databases

Store Leads and BuiltWith already do all of the above and sell it for around
$100–300/month with revenue estimates attached. You want free, and free is genuinely
achievable here, but be honest about the trade: two engineer-weeks costs more than a
year of Store Leads. Consider buying one month purely to **validate your own
qualification model** against theirs, then cancel.

---

## 3. Qualification — where the real work is

Discovery is solved. This section is the constraint.

Score each prospect from free signals. Only prospects clearing the threshold get
contact resolution spent on them.

**Ad spend proxy (strongest).** From Meta Ad Library: active creative count ×
longest continuous run. 20+ creatives running 60+ days is a strong $1M+ signal.
Under 5 creatives is almost always sub-scale.

**Catalog depth and coherence.** From `/products.json`: real brands have 15–300 SKUs
with consistent vendor fields and a coherent price ladder. Dropshippers have 800+
products across unrelated categories at random price points. This filter alone
removes most of the junk from Common Crawl.

**Price point.** Median price under $15 rarely supports a $6k/month engagement.

**Stack depth.** Detected apps from page source. Klaviyo plus a subscription app
plus a reviews app plus a helpdesk is a real operation. A free theme with no apps
is not.

**Shopify Plus signals.** Probabilistic, not definitive — checkout customisation
artifacts, Script Editor remnants, multi-storefront setups, `shopify-plus` strings
in theme assets. Plus starts around $2,300/month, so a positive is a strong size
proxy. Treat absence as no information.

**Catalog velocity.** `updated_at` churn across snapshots. Dead stores look dead.

Weight these, threshold it, and calibrate against a hand-labelled set of 100 stores
where you've guessed revenue from public signals. Expect roughly 2% of Common Crawl
domains and 15–25% of Meta Ad Library domains to survive.

---

## 4. Contact resolution — the honest part

This is where "thousands of free emails" stops being true, and it's worth being
clear-eyed because it determines whether the whole channel works.

**Role accounts are nearly worthless for this offer.** Every Shopify store publishes
`info@`, `hello@`, or `support@` on its contact page. These are free and trivially
scraped. They also route to a customer service agent or a helpdesk queue. A profit
teardown addressed to a support inbox is deleted by someone with no authority to
buy. Do not build the channel on these.

Use them only as a fallback, and only with copy explicitly written to be forwarded:
short, addressed to the owner by name where known, ending with "if you're not the
right person for this, forwarding it takes ten seconds."

**Finding the actual decision-maker, in order of yield:**

1. **The About / Our Story page.** DTC brands are founder-branded almost by
   definition. The founder's name is usually on the site, often with a photo.
   Free, and it works more often than anything else.
2. **LinkedIn by company domain.** Filter to founder, owner, CEO, or head of
   ecommerce. Reliable, and gives you a second channel to reach them on.
3. **Company registries.** The privacy policy or terms page usually names the legal
   entity. UK Companies House is free and lists directors with full names. US state
   registries vary but Delaware, California, and Florida are workable.
4. **Press and podcasts.** This ICP does a lot of founder interviews. A site search
   for the brand name plus "founder" resolves a surprising share.
5. **Apollo.** You already have it connected. Works properly on Shopify companies in
   a way it never did on Amazon sellers, because these are real registered
   businesses with real web presence.

Then construct candidates against the domain — `first@`, `first.last@`, `flast@` —
and verify.

**Verification is mandatory and it is not free.** Shopify merchants overwhelmingly
run Google Workspace with catch-all enabled, so a domain will accept mail to
anything and tell you nothing. Budget roughly $0.001–0.004 per email through
MillionVerifier, ZeroBounce, or NeverBounce.

Skipping this step will destroy the sending domains you spent three weeks warming.
That is the single most expensive mistake available in this build, and it is
completely avoidable for about $40 per 10,000 addresses.

---

## 5. Pipeline shape

```
Meta Ad Library sweep (weekly)  ──┐
Common Crawl pull (quarterly)   ──┼──  domains
Review-app directories (monthly)──┘        │
                                           ▼
                              Shopify fingerprint  (drop non-Shopify)
                                           │
                                           ▼
                              /products.json snapshot     → store raw, keep history
                                           │
                                           ▼
                              qualification score (§3)     → ~2% survive
                                           │
                                           ▼
                              contact resolution (§4)      → ~40% resolve
                                           │
                                           ▼
                              email verification            → paid, mandatory
                                           │
                                           ▼
                              prospects table → COLD_ENGINE.md Phase 2
```

Weekly targets once running: 20,000 domains discovered, ~400 qualified, ~160 with a
verified decision-maker address. That comfortably feeds 500 sends a week at the
three-touch cadence.

---

## 6. Build order

Do these in order. Each is a few days, not weeks.

1. **Shopify fingerprint + `/products.json` fetcher, with polite rate limiting and
   raw-payload storage.** Start snapshotting immediately, even on a small seed list.
   Price history you don't collect today is gone forever, and it's the backbone of
   the strongest finding you have.
2. **Meta Ad Library sweep.** Highest-value source, and the API is well documented.
3. **Qualification scorer**, calibrated against 100 hand-labelled stores. Do not
   skip the hand-labelling; an uncalibrated scorer produces confident garbage.
4. **Contact resolution + verification.**
5. **Common Crawl bulk pull.** Last, because without steps 3 and 4 it's just volume
   you can't use.

---

## 7. What changes in COLD_ENGINE.md

The three Amazon detectors in Phase 2 are replaced. Shopify equivalents, all
computable from `/products.json` plus Meta Ad Library:

- **`permanent_discount`** — SKUs where compare-at exceeds price on essentially
  every snapshot. The "sale" is the real price, and the anchor is doing nothing.
  Straight margin given away, and it's visible in a single API call.
- **`price_ladder_gap`** — clustering that leaves the catalog with no step between
  entry and premium, capping AOV. Quantifiable against category norms.
- **`creative_spend_no_catalog_change`** — sustained ad spend against a catalog whose
  prices haven't moved in six months. Rising CAC absorbed entirely by margin, which
  is the exact question a DTC founder cannot answer and knows they can't.

Update `sources/` to `shopify.py` and `meta_ads.py`. `priors.py` needs DTC priors
instead of Amazon FBA ones: shipping cost per order, return rate, and blended CAC by
category. Confidence gating in §2.2 is unchanged and matters more here, not less —
you know their prices exactly, but you're still assuming their costs.
