# Operations: the machine that looks for product-market fit

Nothing here needs a person at Hubricon during the week. The only thing the
founder still does by hand is show up to a call a prospect booked.

## The loop

```
Instantly campaign ──► reply ──► triage ──► TEARDOWN? ──► client + upload page
      ▲                                   └► interested ──► Calendly ──► booking ──► client + welcome
      │                                   └► question ──► answered from the fact sheet
   lead lists + SuperSearch                                     │
                                                                ▼
                                           uploads ──► models ──► Issue 001 in the desk ──► "it's ready" email
                                                                │
                                                                ▼
                                                 Stripe (paid) ──► renewed past the free month = PMF signal
```

Three components, each doing only what it is placed to do:

| Component | Where it runs | Sees | Does |
|---|---|---|---|
| `hubricon operator` | GitHub Actions, hourly (`.github/workflows/operator.yml`) | every secret | Instantly campaign, enrollment, reply sync + rule/Claude triage, sending replies, provisioning bookings and TEARDOWN requests, nudges, teardown runs, the daily digest |
| Cloud routine "Hubricon operator — inbox & triage" | claude.ai routines, every 2 h 8 am–6 pm Chicago | Gmail, Google Calendar, Supabase connectors | parses Calendly "New Event" emails into `bookings`; writes replies for anything still `pending_review` |
| `hubricon sweep` | GitHub Actions, Mondays | secrets | the existing weekly ingest / models / alerts pass for active clients, once per channel a client sells on |
| `hubricon harvest` | the founder's Mac, launchd, daily 06:10 | `.env` (Supabase; Instantly key optional) | free leads: Best Sellers → product pages → seller profiles → brand sites; rows wait as `enriched` until the operator pushes them to the Instantly list. Every read is also appended to `harvest_product_observations`, which is the cold engine's price history |
| `hubricon teardown` | the founder's Mac, by hand | `.env` (Supabase, `POSTAL_ADDRESS`) | the cold engine: a priced finding on a harvested seller, a page at `/t/<token>`, and the email that links to it. Sends nothing; records what you sent |

The routine never sends email. The operator never reads the inbox. Both talk
through Supabase (`bookings`, `prospect_messages`, `funnel_events`,
`operator_state`).

## The one-time setup (five minutes, once)

GitHub → repo → Settings → Environments → **Production** → add:

| Secret | Why |
|---|---|
| `INSTANTLY_API_KEY` | Instantly → Settings → Integrations → API keys → v2 key with `all:all`. Outbound is OFF until this exists. Needs the Growth plan or above. |
| `POSTAL_ADDRESS` | A mailing address (PO box is fine). CAN-SPAM requires one in every cold email; the operator refuses to create the campaign without it. It must be real, and it must match the one in `.env` on the Mac — the two write different messages. Change it and the live campaign's copy is re-pushed on the next pass; teardowns already drafted keep the address they were built with, so rebuild those. |
| `ANTHROPIC_API_KEY` | Optional. Lets the hourly run answer prospect questions itself instead of waiting up to 2 h for the routine. Same key as `.env`. |
| `ANTHROPIC_WORKSPACE_ID` | Goes with the key above (`wrkspc_…`, shown beside the key in the Console; same value as `.env`). Identity-linked keys are refused without it, and the questions silently wait for the routine. |

The other five secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`RESEND_API_KEY`, `ALERT_FROM`, `FOUNDER_EMAIL`) are already there from the
sweep.

In Instantly itself: at least one mailbox on gethubricon.com connected with
warmup on. The operator only sends from mailboxes whose warmup is active and
sizes the daily limit to 20 per mailbox (cap 60). Lead lists whose name
contains "Hubricon" are enrolled automatically; SuperSearch is asked for 25
founders a day on top, best effort.

## Two platforms: Amazon and Shopify

Since 2026-09-04 a client sells on Amazon, on Shopify, or on both, and the
same engine reads either. `clients.platform` says which
(`amazon` / `shopify` / `both`); every canonical data row carries a
`channel` (`amazon` / `shopify`) so a brand on both platforms holds the same
SKU twice without the two colliding.

    hubricon platform <client> shopify          # or amazon / both
    hubricon run <client> --channel shopify     # a 'both' client runs once per channel

**The models are channel-blind arithmetic.** A unit is a unit and a fee is a
fee, so margin, elasticity, forecasting, the inventory simulation, ad
response, anomaly detection and the Health Score run unchanged on either
platform. `engine/src/hubricon_engine/channels.py` is the single place the
*mechanics* differ, and nothing else is allowed to test the platform string:

| What | Amazon | Shopify |
|---|---|---|
| Fee stack, in prose | referral, FBA fulfilment, storage | payment processing, shipping labels, apps, 3PL |
| Payout cycle (the cash cone) | every 14 days | daily |
| Fee cliffs (low-inventory, aged surcharge, peak storage) | priced in | none; the newsvendor still runs |
| Reimbursement recovery | the whole desk | not applicable — no warehouse loses units on your behalf |
| Watched during a price step | Buy Box share | conversion rate |
| The seat | a Seller Central user, four permissions | a collaborator account: Orders, Products, Analytics, Reports, Marketing, Discounts |

`margin_results.amazon_fees` keeps its column name on both channels — the
column is older than the second platform. `channels.fee_label()` is what it
is called in front of a client.

**What the client sends.** The upload page reads `clients.platform` and shows
only that platform's cards (`/api/intake` returns it). A Shopify brand sends
its orders export, its products export (unit costs via Cost per item, and the
stock snapshot when the store has a single location), its inventory export
when it has more than one, its payouts export, and its Meta and/or Google Ads
exports. The cost template gained a `fulfillment_per_unit_usd` column: pick,
pack and postage per unit, which no Shopify report itemises and which FBA
sellers leave blank.

**The three Shopify behaviours the intake is built around**, because each one
otherwise costs a client an afternoon and the founder an email:

| Shopify does this | What the page does about it |
|---|---|
| An export sends only what is on screen — a filter or a search silently ships a slice | The primer above the first card says to clear filters first, and so does the onboarding email |
| A dated export never downloads; it is emailed to the exporter *and* the store owner | Same primer. Without it a client waits for a browser download that is never coming |
| `Variant Inventory Qty` is printed only for a single-location store ([Shopify's CSV guide](https://help.shopify.com/en/manual/products/import-export/using-csv)) | A separate `shopify_inventory` card and parser sums Products → Inventory → Export across locations. The products parser now writes no stock row at all for a blank quantity, so coverage cannot read "inventory on file" while the models have nothing |

Three more things make the page cheap to get right: every date input arrives
prefilled to the window its card asks for (`data-window="months:6"` /
`"days:90"`); the orders card repeats, so a store whose six-month export
exceeds the 50 MB cap can send a month per row and land identical rows; and
the browser reads each picked file's header and checks it against the same
required columns the parser will demand. A file on the wrong card is named
and blocked before upload rather than discovered a day later — the four lists
that has to keep in step (parsers, `/api/intake`, the check constraint, the
page's cards and signatures) are held together by
`engine/tests/test_intake_page.py`.

**Customer data.** A Shopify orders export carries the customer's name, email
and address, because that is how the platform stores an order. The parser
reads ten fields from it — order name, status, dates, refund total, SKU,
quantity, price, discount — and writes a per-SKU monthly aggregate. No
customer name, email, address, phone or payment detail is ever written to the
database. The privacy page says exactly this, and the upload card tells the
client they may delete those columns first.

**Where the platform comes from.** The site's application gate asks "Where you
sell" and rides the answer along on the Calendly booking; the operator reads
it (`onboarding.platform_from_answers`) and writes it when it provisions the
client. A stated answer beats the column default, but never overwrites a
platform someone set by hand. A prospect the harvest found on a Shopify store
is provisioned as Shopify when they reply TEARDOWN, so nobody is ever sent
Seller Central instructions for a store they do not have.

## The free lead harvest (runs on the Mac)

`hubricon harvest` builds the same rows the paid seller databases sell, from
public pages: Amazon Best Sellers lists → product pages (brand, seller id,
rank, price, weight) → the seller profile every professional seller has had
to publish since 2020 (business name, address, country) → the brand's own
site (published contact address, founder's name). GROWTH.md has the
reasoning and the other free channels.

It has to run from a home connection: Amazon answers datacenter ranges
(GitHub Actions included) with a captcha. So, once, on the Mac:

```
cd engine
uv run hubricon harvest install        # launchd: daily 06:10, `hubricon harvest all`
uv run hubricon harvest all --max-products 40   # first pass by hand, watch it work
uv run hubricon harvest status
```

It runs twice a day (06:10 and 18:10). Each run reads four rotating
categories two levels deep (Kitchen → Bakeware → Muffin Pans is where
$1M–$20M brands rank; page 1 of Kitchen is the giants), up to ~250 product
pages at 7–12 seconds apart, the profiles of the third-party FBA sellers it
found, then the sites of the US founder-run brands among them. About an
hour a run. The pace matters: on 2026-09-03 about 180 Amazon requests in
35 minutes drew captchas, and the run stops for the rest of the day at the
second captcha. Sellers whose profile could not be read that day carry no
country and are neither enriched nor pushed until a later crawl of their
category fills it in. Rows land in
`harvest_sellers` as `candidate` → `enriched` (has an address) → `pushed`
(in the Instantly list "Hubricon harvest (auto)", which the hourly operator
enrolls like any other Hubricon list). Skips are recorded with a reason:
`skip_non_us`, `skip_reseller` (three brands or reseller wording),
`skip_size` (a single listing bigger than the $20M ceiling), `no_website`,
`no_email`. Leads without a found person are addressed "Hi <Brand> team".

Pushing needs the Instantly key. If it is in the root `.env` the Mac pushes
at the end of its run; if not, the hourly operator (which has it) pushes
whatever is `enriched` on its next pass. Either way nothing is contacted
twice: Instantly skips addresses already in the workspace, and the campaign
stops for the whole company on any reply.

Knobs (env): `HARVEST_MAX_PRODUCTS` (250 per run), `HARVEST_CATEGORIES_PER_RUN` (4),
`HARVEST_DEPTH` (2), `HARVEST_SUBCATS` (6 child lists per level),
`HARVEST_MIN_MONTHLY_REVENUE` (2500, estimated, below it a row waits),
`HARVEST_MAX_ASIN_MONTHLY_REVENUE` (300000: one listing above it means a
brand past the $20M ceiling; the first pass showed $600k let Unilever-scale
brands through), `HARVEST_PUSH_LIMIT` (40). Sellers of record that are a
conglomerate or an aggregator (Nestlé, Pattern, Thrasio…) are skipped by
name, and child-category lists are read before a category's page 1, where
the giants sit.
**Size is judged by the seller's own feedback count** (since 2026-09-03):
the profile page shows "N ratings in the last 12 months"; buyers rate the
seller on roughly one order in five hundred, so the count tracks the whole
account. Band `HARVEST_MIN_RATINGS_12MO`–`HARVEST_MAX_RATINGS_12MO`
(100–5,000 ≈ $0.5M–$40M a year; Gorilla Grip shows 8,703, MED PRIDE
10,609, a $2M brand ~200) plus a lifetime cap of 80,000. Listing-level
estimates alone let $100M brands through because one listing under the
ceiling says nothing about the other two hundred.

```
uv run hubricon harvest requalify      # re-read live profiles of pushed/enriched/candidate rows with today's band
uv run hubricon harvest prune          # skip_* rows still in Instantly → deleted there (the operator does this hourly)
uv run hubricon harvest wayback        # second source: archived seller profiles, no Amazon request (below)
uv run hubricon harvest listings       # profile-only sellers: read the storefront, keep two live listings (rank, price, weight)
uv run hubricon harvest shopify        # third source: Shopify stores, no Amazon request at all (below)
```

**The named owner comes from SuperSearch, not the website.** Public pages
give a brand's role inbox (hello@, info@), which the campaign gate treats as
a support queue and routes to the founder lane. The brand is the qualified
part, so the operator asks Instantly's SuperSearch for the Founder/Owner/CEO
at exactly the pushed brands' domains (`domains` filter, one lead per
company, verified work email) into the list "Hubricon harvest owners (auto)",
which enrolls like any Hubricon list. `HARVEST_OWNER_LOOKUPS_DAILY` (50)
caps the Instantly lead credits spent a day; each row is asked about once
(`person_source = supersearch:requested`). Rows that never get a named owner
stay in the harvest list for the founder lane.

**Which categories pay, measured 2026-09-04** (share of sellers found that
became a lead): Baby 20% · Beauty & Personal Care 16% · Automotive 12% ·
Home & Kitchen 11% · Health & Household 10% · Kitchen & Dining 9% · Patio,
Lawn & Garden 8%. Office Products, Tools & Home Improvement and Computers
produced nothing from 37 sellers between them, and a 125-page crawl of
Computers returned 6 candidates against Kitchen's 9 from 34 pages. Computers
and electronics are dominated by offshore sellers and resellers. Crawl the
top of that list; the others are not worth the page budget.

**What the archive is worth, measured 2026-09-04.** Best Sellers turns 204
sellers into 34 leads (17%); the archive turns 1,503 into 27 (1.8%). Roughly
20 Amazon pages buy a lead through Best Sellers. `harvest profiles`, which
reads a live profile for each seller id the archive knows (one page per
seller, the cheapest possible), came out at ~120 pages per lead because the
population is dormant accounts and resellers. The archive indexes whoever
got captured, not whoever is trading. Spend the day's Amazon budget on Best
Sellers.

**Second source, the Wayback Machine.** The Internet Archive holds ~1,800
captures of `amazon.com/sp?seller=…` from 2021 on, each with the storefront
name, business name and address, country and feedback counts. `hubricon
harvest wayback` reads them from web.archive.org (three fetchers, ~2
requests a second, never Amazon) into `harvest_sellers` with `source =
'wayback'`; the storefront name stands in for the brand and the size
estimate comes from the feedback count, so the row still has to earn a live
website and contact address in `enrich`. The CDX listing is saved at
`~/.hubricon/harvest/wayback-sellers.cdx`; delete it to re-list.

**Third source, Shopify stores.** Amazon is the adversary; Shopify is not.
Every store serves `/meta.json` (name, city, province, country, currency,
primary domain) and `/products.json?limit=250` (every product, its vendor,
type, variants, prices, weights and dates), and the contact and legal pages
it must publish carry the address and often the founder's name. `hubricon
harvest shopify` walks that chain into `harvest_sellers` with `platform` and
`source` both `shopify`; `harvest all` runs it after `listings`, fenced so an
archive outage costs a log line and not the night's Amazon work.

**Where the stores come from (`--source`, default `search`).** Shopify's own
consumer marketplace, shop.app, lists brands that are paying, trading Shopify
merchants, and search engines index those pages next to the brand's own
domain. So the pass runs `site:shop.app <category>` over a rotating category
list, takes the brand domains out of the results, and asks each one for
`/meta.json`. A domain that answers is a live Shopify store, and it has its
own domain — which is the difference between a lead we can write to and
`hello@…myshopify.com`, which bounces.

`--source archive` is the old path: the Wayback listing of myshopify.com
homepages. It is kept because it costs nothing, but it is close to worthless.
A store that succeeds buys a domain, so the archive captures that instead and
the myshopify index keeps the dev stores, the abandoned shops and the hobby
projects. Reading five of its handles on 2026-09-04 produced no lead with both
a size estimate and a real inbox; the same day, five category searches produced
four live US stores at their own domains from twenty-three probed candidates.

What a live pass actually does, measured on 2026-09-04:

- **It must go through Chrome.** Every `/meta.json` and `/products.json`
  fetched with a plain urllib session answered **429** — large stores and
  small, custom domains and myshopify ones alike — while the same URLs
  returned their JSON in headless Chrome from the same connection. It is the
  Amazon lesson again: the client is fingerprinted, not just the pace. The
  fetcher takes `chrome_hosts`, and the Shopify pass passes `("",)` so every
  host goes through Chrome. About six seconds a page, so a store's four or
  five pages take under a minute.
- **Chrome hands back the DOM, not the bytes.** `--dump-dom` wraps JSON in
  `<pre>…</pre>` with the entities escaped, so `shopify.json_payload` unwraps
  that before parsing. A password page or a React app is not a payload and
  returns None.
- **The catalogue is read from the myshopify host.** A headless storefront
  (Hydrogen/Oxygen) serves a React app at its own domain, so `/products.json`
  there answers with HTML — thehydrojug.com did exactly that, while
  hydrojug.myshopify.com returned all 250 products. The brand's own domain is
  still the row's website and where the contact pages are read.
- **The primary domain can be the checkout host.** That same store reports
  `checkout.thehydrojug.com` in meta.json; `store_domain` strips the label so
  the founder-lane email never points at a checkout.
- **The archive is read with plain HTTP, the stores with Chrome.** They are
  two fetchers on purpose. `store_fetcher()` routes every host through Chrome,
  and Chrome answers web.archive.org's plain-text page count with its viewer
  (`<pre>42897</pre>` instead of `42897`), which reads as zero pages — the
  first live run listed nothing at all for exactly this reason.
- **Discovery samples the archive, it does not sweep it.** The Wayback CDX
  index of `*.myshopify.com` homepages runs to **42,897 pages**, sorted
  alphabetically: page 0 is `0-5-yas-…`, page 200 is `0c2e44-cb`. Reading the
  first N returns nothing but Shopify's own generated dev stores, so the pass
  spreads its page budget across the whole index and drops handles that are
  blobs rather than names (`ctq2ua-gn` out, `ruggit-collars` in). Ask for the
  page count on its own: add `fl=` or `collapse=` and the archive answers
  `- -` instead of a number. The listing is cached at
  `~/.hubricon/harvest/shopify-stores.cdx`; delete it to re-list.

**A store with no custom domain is not a lead.** `myshopify.com` has an MX
record, so a guessed `hello@<store>.myshopify.com` passes every cheap check
and hard-bounces. Such rows are `no_email`, never `enriched`. The push's
revenue floor would have caught them anyway (they carry no revenue estimate),
but bounces are the one cost a two-month-old sending domain cannot absorb, so
the guess is refused at the source.

Two things are **not** calibrated, and the founder owns them:

- `HARVEST_SHOPIFY_ORDERS_PER_REVIEW` (50) is a guess, unlike the Amazon
  `REVENUE_PER_RATING` figure which was checked against named brands. The
  whole `$500k–$40M` band rides on it. Check ten stores of known size and
  adjust before pushing anything to Instantly.
- **Many stores publish no review count.** The size estimate comes from
  `aggregateRating` in a product page's JSON-LD, and a store whose review app
  renders client-side has none — HydroJug, a brand far above the ceiling, came
  back with no estimate at all. As on the Amazon side an unknown never
  disqualifies, so such a row stays a candidate with no size on it and waits
  in the founder lane rather than entering the campaign. Read the note before
  writing to one.

Knobs (env): `HARVEST_SHOPIFY_LIMIT` (120 stores a CLI run),
`HARVEST_SHOPIFY_CDX_PAGES` (40 index pages sampled), `HARVEST_SHOPIFY_SAMPLE`
(3 product pages a store), `HARVEST_SHOPIFY_ORDERS_PER_REVIEW` (50),
`HARVEST_SHOPIFY_MIN_ANNUAL` / `HARVEST_SHOPIFY_MAX_ANNUAL` (500,000 /
40,000,000), `HARVEST_RUN_ALL_SHOPIFY` (60 stores per scheduled run).

The founder lane's hook changes with the platform: an Amazon seller gets the
FBA weight band, a Shopify brand gets the USPS/UPS one ("ships at 17.2 oz; the
1-lb band ends at 16 oz, so every unit pays the 2-lb rate"). `hubricon
outreach` picks the right one from the row's platform, and the verify
checklist points at the store's own product and contact-information pages.
`harvest requalify` and `harvest listings` skip Shopify rows: there is no
Amazon profile or storefront to re-read.

Parsed pages are cached in `~/.hubricon/harvest` for 30 days, so a re-run
costs only what is new. If Amazon starts answering with captchas the run
waits ten minutes once, then stops for the day; the digest says so.

**Amazon pages go through the Mac's own Chrome** (since 2026-09-03). Amazon
fingerprints the client, not just the pace: a plain Python session drew a
captcha on its second product page while the same pages loaded cleanly in
headless Chrome from the same connection. The fetcher runs one headless
Chrome process per Amazon page (`--dump-dom`, private profile under
`~/.hubricon/chrome-profile`, ~6 s a page) whenever Chrome is installed;
every other host stays on plain HTTP. `HARVEST_AMAZON_CLIENT=urllib` turns
it off, `HARVEST_CHROME=/path` points at another binary.

Amazon's conditions of use discourage automated access. The harvester reads
public pages at a human's pace from a home connection, never pushes through
a captcha, and never runs from a datacenter. That is the whole risk posture;
the founder owns it.

## Sourcing Shopify leads: `hubricon source`

The harvest finds companies on Amazon. `hubricon teardown` models a Shopify
store and writes the email. What was missing between them was a way to *find*
Shopify stores at any volume: `harvest shopify` runs six Bing searches against
`site:shop.app` and samples a Wayback index of `*.myshopify.com` homepages,
about 120 stores a run with every page through Chrome at six seconds each.

`hubricon source` is the funnel in front of that. Three narrowing stages, and
only the first is genuinely unlimited:

```
DISCOVERY        Tranco top-1M -> DNS -> HTTP     free
QUALIFICATION    ~2% survive                      free
CONTACT          ~40% of those resolve            free, and honest about the rest
```

```
cd engine
uv run hubricon source discover --limit 2000    # domains -> live Shopify stores
uv run hubricon source qualify --limit 200      # catalogue, stack, score
uv run hubricon source contact --limit 60       # a named person, published address
uv run hubricon source sheet                    # -> Google Sheet + leads.csv
uv run hubricon source push --dry-run           # -> Instantly holding pen
uv run hubricon source promote                  # -> harvest_sellers, for the teardown
uv run hubricon source all                      # all of the above, one pass
uv run hubricon source status
uv run hubricon source install                  # launchd: 07:40 and 19:40
```

### Nothing here sends anything

This lane exists to fill a sheet and a list, not an outbox, and that is
enforced rather than intended. `outbound.enroll_from_lists` enrols **any**
Instantly list whose name contains `INSTANTLY_LIST_MATCH` (default `hubricon`)
into the live campaign, and the hourly operator runs with `COLD_DRY_RUN=false`
— so a list called "Hubricon sourcing" would start cold-emailing strangers
within the hour. Four fences, each with a test in `tests/test_sourcing.py`:

1. The list is named **`Sourcing holding pen (manual enroll only)`**. No
   "hubricon" token, so the enrolment cannot match it. It is a constant in
   `sourcing/push.py`, not an environment knob.
2. `push` re-reads the name Instantly reports and raises `WouldEnroll` if it
   has been renamed to something enrollable. A rename becomes an error.
3. Only `add_leads(list_id=…)`. `campaign_id` is never passed and `create_lead`
   — the per-prospect dispatch path — is never called from this package.
4. Only `published`, non-role addresses are pushed at all.

`promote` writes rows into `harvest_sellers` at **`candidate`**, not
`enriched`, because `harvest/run.py::push` selects `enriched` and pushes it to
the auto-enrolled list. From there a teardown is built as a `draft` and goes
through `hubricon teardown review` / `approve` like every other one.

It does **not** overwrite a skip. `promote` re-reads the store through
`harvest/shopify.py::read_store`, and where that returns `skip_reseller`,
`skip_non_us` or `skip_size`, the verdict stands and the store is not promoted —
its judgement is the one the cold engine trusts, not this package's score. The
first live run wrote `candidate` unconditionally and promoted Boston Scally,
which `read_store` had just rejected as a multi-brand catalogue; that is
laundering a reseller into the prospect table on our own say-so, and the two
classifiers disagreeing is information rather than something to paper over.

### Where the domains come from

**Not the Meta Ad Library**, which LEAD_SOURCING.md ranks first. Meta's own
`ads_archive` documentation: *"Ads that did not reach any location in the EU
will only return if they are about social issues, elections or politics."*
`ad_type=ALL` — ordinary product ads — is an EU-only dataset, and
`COLD_SUPPRESSED_JURISDICTIONS` suppresses EU/UK/EEA/CH entirely for want of a
documented legitimate-interest basis. The only geography the API covers is the
only one we will not write to. There is no free ad-spend signal on this
platform; the app stack stands in for it.

**Not Common Crawl** either. Free to read, but the columnar index wants Athena
(billed per query) or a local pull in the hundreds of gigabytes, and what comes
back is a domain with no size signal at all.

**Tranco plus DNS**, measured 2026-09-05. Every Shopify store on its own domain
either resolves into `23.227.38.0/24` or CNAMEs `www` to `shops.myshopify.com`
— `allbirds.com` → `23.227.38.32`, `gymshark.com` → `23.227.38.65`. The Tranco
top-1M is a free download, a million DNS lookups is minutes of concurrency, and
**not one request touches a store**. The rank is not a by-product: it is the
traffic proxy that a bulk web crawl cannot give, and it carries most of the
weight in the score.

DNS is precise but not complete. A store behind Cloudflare or Vercel shows its
proxy instead (`ridge.com` → `104.20.21.75`, `bombas.com` → `76.76.21.21`, both
real Shopify stores), so a second pass asks `/meta.json` — one request that
settles both "is this Shopify" and "what is the myshopify handle", which is the
row key everywhere downstream. `--source search` still runs the shop.app route,
which reaches brands Tranco's ranks never see.

**Where in the ranking the stores are**, measured 2026-09-07 over the full
top-1M, 600 domains sampled per band, DNS only:

| rank band | Shopify | what is in it |
|---|---|---|
| 1 – 10,000 | 0.00% | Google, Microsoft, the CDNs. Nothing. |
| 10,000 – 50,000 | 0.50% | Toys R Us, Native Instruments — brands, not DTC |
| 50,000 – 150,000 | 1.00% | Smartwool, Orthofeet |
| 150,000 – 400,000 | 2.83% | Scotch & Soda, Storelli |
| 400,000 – 1,000,000 | 4.50% | the long tail, and increasingly non-US |

So the head of the list is waste and the tail is mostly foreign, and the window
(`SOURCING_RANK_FROM` / `_TO`, 20,000–600,000) is where a US brand doing
$1M–$20M actually ranks. Extrapolated, the whole list holds roughly **35,000
Shopify stores**. A live pass over ranks 150,000–210,514 returned **1,250 stores
from 40,000 domains** and did not touch one of them to do it.

A cursor in `operator_state` (`sourcing.tranco_cursor`) remembers where the last
pass stopped, so successive runs walk down the ranking instead of re-probing the
head; it wraps to the top of the window when it runs off the end, because the
list is rebuilt daily and a store that was not there in March is there now.
**Every DNS hit is written as a row**, not just the ones a pass has HTTP budget
to probe — the first live run kept 25 of 1,250 and moved the cursor past the
rest, which would have lost them for good. The unprobed rows carry no handle and
`qualify` fills it in when it reaches them.

### Plain HTTP first, Chrome only on a refusal

`harvest/shopify.py` sends every Shopify request through Chrome, on the
strength of a 2026-09-04 pass where every plain `/meta.json` answered 429.
Re-measured 2026-09-05 across seven stores and three user agents — a browser
UA, a named bot UA, and `Python-urllib/3.12`:

| store | meta.json | products.json |
|---|---|---|
| allbirds.com | 200 | 200 |
| brooklinen.com | 200 | 200 |
| drinkolipop.com | 200 | 200 |
| gymshark.com | 404 | 403 |
| ridge.com | 403 | 403 |
| bombas.com | 429 | 429 |

The agent made no difference anywhere and the store made all of it: what
refuses is the edge in front of the store, and what answers answers anything.
So `sourcing/fetch.py` tries plain HTTP and escalates only on a refusal — a 404
is not a refusal and does not spend a browser launch. Shopify's own robots.txt
disallows neither endpoint (checked the same day), and the pass runs at one
request a second per host with a contact URL in the agent string.

### The score, and the fact that it is not calibrated yet

Free signals only, weighted, in `sourcing/score.py`: Tranco rank band, the paid
apps the storefront loads, catalogue depth and vendor coherence, median price,
Shopify Plus artifacts, catalogue velocity, and the existing review-based
revenue estimate. The stack is the interesting one — nobody installs Elevar or
Northbeam without media spend worth attributing, or Attentive without a list
worth texting, so a monthly invoice is a spend proxy in a way a free theme with
no apps is a spend proxy in the other direction. Allbirds returns Elevar,
Attentive and Yotpo from one homepage fetch; Gymshark returns Rebuy.

**Read past the first page of the catalogue.** Shopify caps `/products.json` at
250 products, and reading one page made every large catalogue look like exactly
250 items — which silently disabled the best junk filter available, since the
scorer throws out a catalogue over 800 SKUs as a supplier feed and nothing could
ever reach 800. `SOURCING_CATALOG_PAGES` (4) fixes it, and only stores that
filled the first page cost more than one request. It paid for itself on the
first re-run: `donsfurniture.com` had scored 74 and qualified on a truncated
count, and reads as 1,000+ products and disqualified once the pages are read.

**The country is asked first, before a catalogue page is read.** The engine is
US-only and the cold engine suppresses EU/UK/EEA/CH, so a non-US store is not a
prospect at any score — and the deeper Tranco bands are full of them. Without
that gate the scorer put `oglmove.com`, a Hong Kong store, at 76 and a whole
contact pass was spent on a company we can never write to. An *unknown* country
still never disqualifies, the same rule the harvest applies; `promote` catches
those when it re-reads the store.

**Two numbers are guesses and the founder owns them.** `SOURCING_MIN_SCORE`
(55) and the rank bands in `score.py` have never been checked against a labelled
set. Do that before trusting a single lead:

```
uv run hubricon source calibrate --file labels.csv   # csv of domain,good
```

It prints precision and recall at each threshold. Recall is cheap here — there
are always more domains — so take the threshold whose *precision* is
acceptable. The same afternoon should settle
`HARVEST_SHOPIFY_ORDERS_PER_REVIEW` (50), which this pass inherits and which
the Shopify section above already flags as an uncalibrated guess the whole
$500k–$40M band rides on.

### Contact: published only, and role inboxes never

Two rules, both of them decisions rather than code:

**A guessed address is never sent to.** Shopify merchants overwhelmingly run
Google Workspace with catch-all, so `dana@brand.com` is accepted by the domain
whether or not anybody reads it, and every free check — syntax, MX, disposable
lists — passes it. Paid verification is the only thing that separates a real
mailbox from a catch-all and there is none in this build, so a guess is stored
with `email_confidence = 'pattern'`, written to the sheet marked "do not send",
and refused at the push. It is there so a future batch verification has
something to verify.

**A role inbox is founder-lane inventory, not campaign inventory.** The
2026-09-03 decision stands: `info@`, `hello@` and `support@` reach a
customer-service queue and are never cold-emailed. They still go on the sheet,
with `sendable = no` and the reason, because a qualified brand is worth ninety
seconds of a person's time even when the crawler could not find its owner.

A store with no custom domain is refused at the source: `myshopify.com` has an
MX record, so a guess there resolves and hard-bounces, and bounces are the one
cost a two-month-old sending domain cannot absorb.

### The Google Sheet

One Apps Script web app, no GCP project and no service-account key. Paste
`scripts/sheet-sync.gs` into the sheet (Extensions → Apps Script), deploy it as
a web app with **Execute as: me** and **Who has access: anyone with the link**,
and put the URL and the shared secret in `.env` as `SOURCING_SHEET_URL` /
`SOURCING_SHEET_SECRET`. Rows upsert on `domain`, so re-running refreshes the
sheet rather than duplicating it. `~/.hubricon/sourcing/leads.csv` is written
every pass regardless, so a webhook that is not set up yet never loses a run.

If the engine reports "answered HTML rather than JSON", the deployment has the
wrong access setting — that is the one setup slip worth knowing about.

### One new finding: `permanent_discount`

Shopify rows had two detectors and in practice one: `carrier_band_edge` only
fires above a pound, and `price_cut_no_rank_gain` needs history these rows
rarely have. So most sourced stores would have produced no teardown at all,
and sourcing more of them would have changed nothing.

`/products.json` publishes `compare_at_price` beside `price`, so when a store
lists a product at $32 against its own $45 anchor, the $13 is arithmetic rather
than estimation — no rate card required, which makes it the cheapest honest
finding on the platform. It fires only when most of the catalogue is priced the
same way (one discounted product is marketing; a whole shelf is a price), and
its confidence turns on price history: three readings of the same price a
fortnight apart earns the word "permanent", and until then the finding sits
below `COLD_MIN_CONFIDENCE` and `select` will not send it. `compare_at_price`
is now stored on `harvest_products` and the observation rows accrue on every
pass, so the fortnight starts the first time a store is promoted.

**`price_ladder_gap` was not built.** A gap in the price ladder is real and
visible in one API call, but the dollars behind it are counterfactual AOV,
which no published rate card prices — and `cold/findings.py` refuses anything
it cannot price, so the finding would have been generated and then rejected
every time. The gap is on the sheet as `ladder_gap` instead, where it is a hook
for a person rather than a claim from a machine.

## The cold engine: `hubricon teardown`

The founder lane's old hook was an ounce count — "your listing is 0.6 oz over an
FBA band" — with no dollar attached to it. A seller cannot act on an ounce. The
cold engine prices that ounce off Amazon's published fee schedule, puts the
arithmetic and its chart on a page at `hubricon.com/t/<token>`, and writes the
email that links to it. Same free lead source, a teardown instead of a hint.

### The division of labour: you find them, the engine writes to them

The crawl finds companies. It does not find *people*: a thousand harvested
sellers yielded two named owners, because a founder's name lives in a sentence
on an About page, or on LinkedIn, or nowhere. That was the binding constraint on
this whole lane, and it is the one thing a person does in ninety seconds and a
crawler cannot do at all.

So the split is: **you find the lead, the engine does everything after it.**

```
hubricon teardown add holtzleather.com
hubricon teardown add holtzleather.com --email nora@holtzleather.com --first-name Nora
hubricon teardown add --file leads.csv          one per line: domain, email, name
pbpaste | hubricon teardown add -               straight from the clipboard
```

A lead is a domain, or an Amazon seller id. With an address and a first name if
you found them — which is the whole point, and which lets the engine skip the
enrichment guesswork that gets addresses wrong. The file is forgiving: commas or
tabs, a header row or not, columns in any order, `#` comments, blanks. A company
listed twice is one lead. A line it cannot read is reported, not fatal.

What happens then, in about twenty seconds a store: it resolves the domain to
the store behind it, reads the catalogue and the contact pages, writes the same
rows a crawl would have written, models every listing, and leaves a teardown in
the review queue. A live run of two pasted domains read 308 products and
produced a sendable teardown.

This is cheaper than crawling in every sense. One store is three or four
requests against a host that does not fight you, instead of a day of Best
Sellers pages against one that does. Nothing needs the Mac to be awake on a
schedule, and nothing gets fingerprinted.

### The one command

```
cd engine
uv run hubricon teardown
```

Builds whatever is buildable and then shows what is waiting, split into what is
ready to send and what needs ten minutes of looking first. Then:

```
uv run hubricon teardown review              read them one at a time, decide s/n
uv run hubricon teardown show <id>           one in full: the email and the page URL
uv run hubricon teardown open <id>           the page exactly as the prospect sees it
uv run hubricon teardown name <id> --first-name Dana --email dana@brand.com
uv run hubricon teardown approve <id>        publishes the page; the URL goes live
uv run hubricon teardown add <domain>        a lead you found: fetch, model, queue
uv run hubricon teardown sent <id>           after you send it, by hand, from your mailbox
uv run hubricon teardown stats               the gate: how often it stays silent, how often you keep it
```

Nothing here sends an email. `sent` records that you did, which is what makes
the ninety-day and three-touch rules real — a hand-sent email nobody wrote down
is a prospect the automated lane will mail again next week.

`POSTAL_ADDRESS` has to be in `.env` on the Mac as well as in the GitHub
environment. CAN-SPAM requires it in the message and the engine refuses to draft
without one.

### Sending: Instantly does it, on both warmed domains

Approved teardowns go out through Instantly, in their own campaign —
**"Hubricon — Profit Teardown (per-prospect)"** — beside the existing one. It is
where both warmed domains already live, and COLD_ENGINE.md §2.4's three
requirements (domain rotation, per-domain daily caps, automatic pause on bounce
or complaint) are things Instantly already does. A second dispatcher would mean
warming domains twice and reconciling two records of who was contacted.

**That campaign's subject and body are a single merge field each.** The bytes a
prospect reads are the bytes you approved. A campaign holding fixed prose with
numbers merged into it would put a second author between the finding and the
inbox, and any divergence would be invisible until a stranger read it.

```
uv run hubricon teardown send --dry-run     who would go, and what they would get
COLD_DRY_RUN=false hubricon teardown send   dispatch now, from this machine
```

You do not have to run it. **The hourly operator dispatches every approved
teardown on its own pass**, because it is the thing that holds
`INSTANTLY_API_KEY` — your Mac does not. So the loop is: `add` the leads,
`review` them, `approve` the ones you want, and the next hourly pass sends them.

`COLD_DRY_RUN: "false"` is set on that job in `operator.yml`, and it has to be:
the flag defaults to on and is checked once per teardown, so without it the
campaign is created, the mailboxes are synced, the caps are right, and every
approved teardown is denied one at a time — a lane that looks healthy and sends
nothing. It was exactly that for the first hours it existed. On the Mac the flag
is still on by default, which is why `teardown send` there needs it spelled out.

Caps: `COLD_PER_MAILBOX_DAILY` (default 30) times the number of mailboxes past
warmup. Two mailboxes is 60 a day, which is the number you are aiming at. Add
mailboxes and the ceiling rises with them; the campaign's sender list and limits
are re-synced on every pass, so a mailbox that finishes warming is used without
anyone touching anything.

Every lead still goes through `can_contact` immediately before it is pushed. A
teardown that fails keeps its approved status and is reported in the digest
rather than silently skipped — you decided to send it, so the reason it could
not go is something you need to see.

### What it will and will not claim

Five detectors, all computed from pages the seller published themselves:

| Finding | The claim | Where the dollars come from |
|---|---|---|
| `price_band_edge` | a listing at $10.49 nets less than the same listing at $9.99 | the 2026 schedule prices every weight band three times, by sale price; crossing $10 costs 82c–$1.01 a unit |
| `size_tier_edge` | one dimension over the small-standard envelope moves every unit to large-standard rates | the two tiers' fee at that weight |
| `dim_weight_overage` | past a cubic foot the fee is set by the box, not the product | the fee at dimensional weight against the fee at real weight |
| `fee_band_edge` | the published item weight is already over a band edge, before Amazon's packaging | the band step on the schedule |
| `price_cut_no_rank_gain` | a price cut that bought no rank | the cut, net of the referral fee |
| `carrier_band_edge` (Shopify) | a parcel over a pound is billed at two | USPS Notice 123, zones 1–8 |

`price_band_edge` is the strongest and needs nothing but the price the seller
set: two published rates and their own listing. `fee_band_edge` is the honest
version of the old hook — a product page publishes the *item* weight and Amazon
bills the *packed* weight, so the engine says the unit is **at least** in the
band above and prices the step conditionally, rather than asserting a band it
cannot see.

**Roughly half of prospects should produce nothing.** `hubricon teardown stats`
prints that rate and says so when it looks wrong. Sending nothing is a correct
output; a wrong number sent to a $5M seller costs more than the channel earns,
and this ICP talks to each other constantly.

### The rate card

Every dollar the engine claims comes from one table.

```
uv run hubricon teardown ratecard
```

prints it beside its effective window and tells you where to check it. It is the
2026 US non-peak schedule, 15 Jan – 14 Oct, plus the 3.5% fuel surcharge that
started 17 April. **On 15 October the peak card takes over and this one goes
stale**: the engine stops pricing anything and says so rather than quoting a low
number. Update `engine/src/hubricon_engine/cold/priors.py` and it starts again.

### Shopify: the pound, not the ounce

**A claim this business was making stopped being true on 12 July 2026.** Until
then USPS Ground Advantage priced 4, 8, 12 and 15.99 oz separately, and the
Shopify hook quoted those tiers. On that date USPS collapsed all four into one:
at published Commercial rates every parcel under a pound now costs the same
within a zone, whatever it weighs. "You are 1.5 oz over the 8 oz band" is a
false statement about a stranger's business, so those edges are gone from
`harvest/shopify.py` — which removes the sentence from `hubricon outreach` and
the cold engine at once, since both read the same list.

What survives is larger, because USPS rounds anything over a pound up to the
next whole pound. A parcel at 16.5 oz is billed at **two** pounds; the same
parcel at 15.9 oz is billed at the flat sub-pound rate. That step is **96¢ to
$4.47** — the range is the spread across zones 1 to 8, and the teardown page
draws all eight rather than averaging them, because a brand's zone mix is not
public and guessing at it is the one thing worth refusing.

The card is USPS Notice 123 Commercial prices (`pe.usps.com`), effective
2026-07-12, in `cold/priors.py`. Commercial rather than Retail because that is
what a brand buying labels through Shopify Shipping or Pirate Ship pays; Retail
is two to four dollars dearer and would overstate every claim. The 48 oz edge
and above needs the 4 lb row, which is not on file, so it stays unpriced and is
never sent.

Shopify rows usually carry no volume estimate — the harvest reads a catalogue,
not a sales rank — so those findings stand on the per-unit number alone,
gated by `COLD_MIN_PER_UNIT_ONLY_USD` (default 50¢) instead of the monthly floor.

### Price history, for free

`harvest_products` holds one row per listing and the crawl overwrites it, so
last week's price is gone — which is why the price-history detectors normally
need a paid provider. Since 2026-09-04 every crawl also appends what it saw to
`harvest_product_observations`, one row per listing per day. The twice-daily
passes therefore build the price and rank series a subscription would have sold
us, and `price_cut_no_rank_gain` starts firing about a fortnight after the first
run. Nothing to configure; it happens on every `hubricon harvest`.

### Guardrails

`cold/compliance.py` is the only path to a send, and a send object cannot be
constructed without a clearance from it — a caller who forgets the check gets an
exception rather than a delivered email. It checks, in order: `COLD_DRY_RUN`
(on by default), an address, not one of ours, the global `suppressions` table,
jurisdiction (EU/UK suppressed — no documented legitimate-interest basis yet),
a postal address, ninety days and three touches per prospect, and the per-domain
daily cap.

```
uv run hubricon teardown suppress someone@brand.com --reason "replied: remove me"
```

honours an objection immediately, across every lane.

### The gate this is at

COLD_ENGINE.md Phase 3: the founder sends fifty by hand from his own mailbox and
handles every reply.

**Phase 4 is not happening this quarter.** It needs three to five dedicated
sending domains warmed for three weeks before the first send, and never
hubricon.com or gethubricon.com — those carry client mail. The founder's call on
2026-09-04 was not to register them this quarter, so the cold lane stays
hand-sent: `hubricon teardown` builds and `sent` records, and nothing in the
repo dispatches. The dispatch code, domain rotation and bounce/complaint
auto-pause are deliberately unbuilt rather than built and disabled. Phase 5
(video) waits on the page converting.

Answers to COLD_ENGINE.md §6, recorded 2026-09-04: no Keepa (the harvest is the
source); EU/UK suppressed entirely; contact emails come from the harvest's
enrichment, recorded in `harvest_sellers.contact_source`; no sending domains
this quarter.

## The ledger measures itself

The value ledger is the retention case, and until 2026-09-04 every dollar on it
came from the founder typing `hubricon measure --impact`. Nobody types, so the
ledger sat at zero and the portal told paying clients `0.0× — at risk`.

`measurement.py` now runs inside the Monday sweep, reads each approved
directive's captured `evidence` against the client's own later exports, and
labels every dollar with how it was proved:

| Tier | Means | Example |
|---|---|---|
| `direct` | A counterparty's own record shows the money moved | Amazon approved a reimbursement we filed |
| `isolated` | The exact line the directive named, against its own prior level | A negative-matched term's spend went to zero |
| `attributable` | Confounded by demand, so measured against a stated counterfactual at the **least favourable** end of our own confidence interval | A price step |
| `none` | We could not isolate it, and we say so | A campaign that was paused wholesale |

Four guards apply to every family: capped at what we promised, a $25 materiality
floor, the effect must still be present in the latest export, and the same
(sku, period) movement is credited to at most one directive.

    hubricon measure <client> --auto --dry-run    # every verdict, banking nothing
    hubricon measure <client> --auto              # what the sweep would bank, now

The client sees all of this in the desk's **"how we know"** column, which
renders `measurement_notes` beside every ledger row.

**What still needs a person.** Recording the retainer start when someone says
yes (`hubricon retainer <client>`), filing reimbursement claims
(`hubricon recover <client> file`), executing approved directives in the client's
account and recording it (`hubricon execute`), the daily Buy Box reading on a
live price test (`hubricon watch`), and confirming when an ad spend step-up was
intended. Everything else measures itself.

## The loop past paid: proof, the ask, the month, and what it teaches the cold engine

The business is meant to run as a loop — effort, customers, results, word of
mouth, customers — and until 2026-09-08 it stopped at "results". The day-30
pass inserted two unanswered `consents` rows and nothing asked, collected,
published or credited anything. Five modules close it, all inside the jobs
that already run:

```
value.compute ──► proof.detect ──► results ──► (consent) ──► public_results()
                                                    │              │
                    referral.ask_if_due ◄───────────┘              ├──► results.html
                    rides the Issue, once                          ├──► the campaign copy (outbound)
                           │                                       └──► the teardown page + email (cold)
                    /say/<token> ──► consents, testimonial, referral link
                           │
                    ?ref=<code> on a booking ──► referral.attribute
                           │
                    referred client clears day 30 ──► referral.credit_referrer
```

### Proof (`proof.py`, hourly, after billing)

Every verified event the ledger supports becomes a row in `results`: the first
reimbursement Amazon paid on a claim **we filed**, each directive measured
`direct`, the day-30 gate clearing, the ledger crossing three or five times the
fee. `proof.detect` is pure and keys off `value_total` and `roi_multiple` —
never `billing.verdict`'s total, which counts identified-but-unbanked value and
is the right bar for an invoice and the wrong one for a claim to a stranger.

Nothing is public without `anonymised_results` consent. `public_results()` is
the **first function in the schema anon may execute**; it returns one card per
brand (category, revenue band, platform, amount rounded down to the hundred,
how we know, month), re-checks consent on every read, and never returns a
client id. `results.html` renders it; index.html shows the same cards in its
proof section and hides the section while the list is empty.

A card needs an industry word, which the crawl cannot know:

```
uv run hubricon proof                       # every result row, and the line the copy carries
uv run hubricon proof set <client> --industry kitchen --revenue-band '$1M–$5M'
uv run hubricon proof line                  # the sentence, or "(none)"
```

**The proof line.** One sentence, two templates in `proof.py`, every figure a
`{{placeholder}}` filled from the RPC and checked with `narrate.validate` — the
same guard the Issue letter runs under, so the line can never carry a number
the ledger did not. It goes three places by itself: the campaign email
(`outbound.campaign_spec(proof_line=…)` replaces the "track record isn't"
paragraph, and `effective_copy_version` folds a hash of the line into the copy
version so `sync_copy` PATCHes Instantly on the next pass — a withdrawn consent
moves it back the same way), the cold teardown email, and the teardown page
above its button.

### The ask (`referral.py`, rides the Issue)

`referral.ask_due` is true at the moment of maximum value — the ledger at three
times the fee, or the first recovered dollar — with no consent answered. The
ask is one more paragraph in the fortnightly Issue email (`cli._publish_issue`),
sent once (`client_touches` kind `consent_ask`), never chased. It links to
`/say/<token>` (`api/consent.js`), minted by the intake-token machinery, where
the client ticks or leaves each consent — anonymised results, named results,
calibration, testimonial — writes two lines, and finds their own referral link.
An unticked box is written as `false`; either answer is fine and both are
recorded.

### The month

The link is `hubricon.com/?ref=<code>`. index.html keeps the code in
`sessionStorage` and appends `|ref:<code>` to the Calendly `utm_content`, so it
arrives in `bookings.answers` like the platform does. `operator.bookings` calls
`referral.attribute`: `bookings.ref_code`, `clients.referred_by_client_id` (or
`referred_by_partner_id`), a `prospects` row with `source = referral|partner`,
and a line in the digest so the founder knows who sent them before the call.

The credit is paid at the referred client's **own** day-30 gate, in the same
pass that starts their billing, and nowhere else. A referrer already on a
subscription gets a Stripe customer-balance credit for one month
(`Idempotency-Key: referral-<referred id>`), which applies itself to their next
ACH invoice; a referrer still in their free month, or one whose gate came back
`short`, gets `free_months + 1`, which `billing.due_for_decision` honours.
Partners are never auto-paid: the digest says "pay the partner per terms".

```
uv run hubricon partner add books --name "A2X Bookkeeping" --kind bookkeeper --terms "one month per renewal"
uv run hubricon partner email books <seller_id>      # drafts GROWTH.md channel 4, with their link
```

### Speed (`speed.py`)

Three set-once timestamps on the client row — `exports_landed_at` (the first
pass that found typed data), `first_issue_at` (Issue 001), `first_value_at`
(the first measured or recovered dollar) — make the 24-hour promise a number.
`hubricon promises` fails a client who has waited longer than
`speed.SLA_HOURS` for Issue 001, and the digest carries the medians. The
promise is Issue 001 inside 24 hours; time to the first dollar is reported and
never promised.

### Calibration (`calibration.py`, Monday, after the sweep)

The cold engine prices a stranger's listing from published cards and two
guesses: units per sales rank, and orders per Shopify review. A client's own
exports are the only ground truth those guesses will get.

terms.html §10 says we never use one client's data to advise another, so:
**nothing is read from a client who has not granted the separate
`calibration` consent** on the /say page, and what is written is an aggregate
— a slope, a rate, a ratio — with the number of clients and observations on
the row. Below the floor (two accounts, thirty observations; one account for a
referral rate, which only verifies a published card) the row says
`insufficient` with a null value and the published figure stands. Readers
(`priors.referral_rate`, `harvest/amazon.estimate_units`,
`harvest/shopify.estimate_annual`) fall back to the card when nothing is
loaded, and a finding that used a learned figure says so in its assumptions
and carries `Finding.provenance`.

```
uv run hubricon calibrate          # compute and write; the sweep does this weekly
uv run hubricon calibrate show
```

### The scoreboard, continued (`loop.py`)

`pmf_scoreboard()` now runs past paid: asks sent, consents, testimonials,
results published, referral links, referral bookings, referred clients paying,
partner bookings, median hours to Issue 001, and the teardown lane joined to
what came back (`teardowns_sent / replied / booked`, written by
`loop.attribute_reply` from the reply sync and `loop.attribute_booking` from
the booking pass). `renewed` runs from `retainer_started_at` — the same clock
billing uses — rather than `created_at`.

```
uv run hubricon loop               # every arrow as a conversion from the one before
```

## The rolling gate, and the smaller door

Two founder decisions, 2026-09-08. Both live in `billing.py` and run inside
the hourly `operator.billing` pass, which stays the only code that bills.

### Our invoices never run ahead of the ledger

Day 30 was the only month the guarantee covered. Now every invoice Stripe
raises for a retainer is judged by the same bar as day 30 — measured plus
identified value since the retainer began — against everything billed through
that invoice (`billing.rolling_verdict`). The decision is written on the
`invoices` row (`gate_decision`, `gate_value`, `gate_fees`), so it is taken
exactly once. Covered is silent apart from the digest; not covered is
**voided** if the invoice is still open, or **credited** to the customer
balance if ACH already settled it (`billing.waive_invoice`), and the client
gets one letter saying which and why. Void invoices drop out of the ledger's
fee denominator, so a waived month is a month that was never billed.

Read-only until `STRIPE_SECRET_KEY` is set: without it an uncovered invoice
is a digest warning, never a silent bill. terms §3, welcome and the index
guarantee say the sentence; `hubricon promises` tracks it.

### The smaller door: recovery-only

Hormozi's downsell, for the founder who will not commit to $6,000 with a
stranger. No retainer. We file the reimbursements Amazon owes them and
invoice a share (`RECOVERY_SHARE`, 0.25) of what Amazon **actually paid on
claims we filed**, at month end, nothing else (`billing.recovery_due`,
`billing.invoice_recovery_share`). Nothing landed, no invoice; under
`RECOVERY_MIN_INVOICE_USD` (50) it rolls forward. Each paid claim carries the
`recovery_invoices` row that billed it, so it is billed once. It is a `plan`
on the client row, not a second product: same intake, same ledger, same proof
cards, same ask.

**Where it sits in the funnel:**

```
cold email / teardown page ─► TEARDOWN reply or booking ─► welcome + upload page
        │                                │
        │                     day 3 nudge · day 7 files             (unchanged)
        │                                │
        │                     day 14, no exports, Amazon ─► DOWNSELL email, once (client_touches 'downsell')
        │
   stretch-fit call (<$1M) ─► founder offers recovery-only on the call ─► `hubricon downsell <client>`
                                         │
   exports land ─► Issue 001 ─► day-30 gate ─┬─ clears ─► retainer ─► rolling gate on every invoice
                                             └─ short  ─► the letter names the smaller door ─► reply RECOVERY
                                                                                              ─► `hubricon downsell`
   recovery plan: claims filed ─► Amazon pays ─► month end ─► one invoice for the share ─► ledger · proof · the ask
   the way back up: identified value beyond reimbursements ≥ the fee ─► digest: "offer the retainer"
```

The switch is a command, never a keyword the triage acts on: a plan is a
contract, and a person confirms it.

```
uv run hubricon downsell <client>                # recovery-only at RECOVERY_SHARE
uv run hubricon downsell <client> --share 0.2    # a different share, agreed in writing
uv run hubricon downsell <client> --retainer     # back onto the flat fee
```

The site never shows the downsell. It is offered by a person on a call, by the
day-14 email, and by the day-30 letter — the three places a founder has said
"not at that price" without saying it. Shopify has no reimbursements and so no
smaller door yet; a Shopify founder who stalls gets the day-7 files email and
nothing further.

## Keeping the promises the site makes

Each of these used to depend on someone remembering. They are now jobs.

| Promise | Where it is made | What keeps it |
|---|---|---|
| A three-minute video brief every two weeks | index.html, welcome.html, terms.html §2 | `.github/workflows/issue.yml` daily → `hubricon issue --send`; each client's fortnight runs from their own retainer date. The video is generated (slides from the same beats the narration speaks) and never blocks the letter |
| Corrections stated with their dollars **before** they go live, vetoable by reply | terms.html §6 | `sweep --issue` → `issue.issue_drafts`. **If the notification does not send, no veto window opens and nothing can auto-approve** |
| A standing mandate the client sets | welcome.html Step 2 | `hubricon mandate`; `issue.load_mandate` falls back to exactly what the Terms publish, never anything more permissive |
| First fixes live in week one | welcome.html | `hubricon execute` records it; the sweep escalates anything approved and unexecuted past 7 days |
| Buy Box watched daily through a price step | index.html, terms.html §6 | `hubricon watch --alert` |
| "If we don't find you more than we cost, you walk away owing nothing" | 8 surfaces, terms.html §3 | The operator's day-30 pass is the **only** code that starts billing. Below the bar no subscription is created — there is no invoice to write off |
| Free data + ledger export, any time | 11 times across 6 surfaces | `hubricon export <client>`; the desk's "Request your export" opens a tracked request |
| Deletion in 30 days · DSAR in 7 · breach notice in 72h · 14 days' notice of a terms change | privacy.html, terms.html §14 | `hubricon request`; the operator escalates anything within two days of its deadline and shouts when one is overdue |
| The 90-day plan drafted from the Teardown | welcome.html Step 2 | `draft_plan_for_run` inside the teardown; it stays `draft` until the founder commits it on the kickoff call |

Secrets this adds, all optional — each degrades to a printed reason rather than
a silent failure:

| Secret | Without it |
|---|---|
| `ELEVENLABS_API_KEY` | Issues publish with the letter and report, no video (or set `HUBRICON_TTS=local` for a local voice) |
| `STRIPE_PRICE_ID` | A client who clears the guarantee is flagged in the digest instead of being billed. Nobody is ever wrongly billed |

    hubricon promises                # which promises the machine can keep, right now
    hubricon promises --client <x>   # …and that client's own clocks

Every gap it finds is repeated in the daily digest, because a promise that fails
for want of a secret fails *quietly* — the client simply does not get the thing
the site says they get, and nothing else would surface it.

## When the campaign is silent: `hubricon doctor`

On 2026-09-03 the campaign had 84 leads enrolled, had been activated twelve
times, and had never sent an email. Nothing said so: the analytics call was
failing and its error was being swallowed, so `operator_state` held no
`instantly.analytics` key at all after twenty hours of hourly passes.

That cannot recur. Every pass now writes `instantly.health` to `operator_state`
with plain-English verdicts, and `hubricon doctor` reads it back. The founder's
Mac has no `INSTANTLY_API_KEY` and no `gh` CLI, so the database is the only log
that reaches both machines: run `doctor` locally and it reports what the cloud
last saw, with the timestamp.

If activation is not sticking, the answer is almost always in the Instantly
dashboard, not in the code. Check in this order:

1. **The campaign's status badge.** "Account Suspended", "Accounts Unhealthy"
   and "Bounce Protect" are statuses the API reports as negative numbers.
   `POST /activate` returns 200 for all of them and the status snaps back.
2. **Billing.** Sending needs a live paid plan. A lapsed card puts the
   workspace read-only while the API keeps answering 200.
3. **Campaign → Accounts.** Are both mailboxes actually ticked on this
   campaign? `email_list` can be dropped silently at creation.
4. **Campaign → Schedule.** An active campaign with no valid schedule sends
   nothing, forever.
5. **Campaign → Leads.** Leads sitting under "Risky" or "Catch-all" are never
   sent while `allow_risky_contacts` is false, which it should stay.

## Two lanes, and which leads go in which

The automated lane is Instantly. The manual lane is `hubricon outreach`, and it
never sends anything: it prints briefs and drafts that Hagen edits and sends
from his own mailbox.

The split is not about lead quality, it is about the address. Of the 35
harvest-sourced prospects on file on 2026-09-03, every single one was a role
inbox (`info@`, `hello@`, `support@`) that reaches a customer-service queue.
Those are worth real money and worth a human; they are worthless to a cold
sequence. So the harvest is a founder-lane source, not a campaign source, until
enrichment starts finding named owners.

Since 2026-09-04 the founder lane's email comes from `hubricon teardown`, which
prices the hook and gives it a page. `hubricon outreach` still holds the
disqualification pass, the target list and the partner template:

    hubricon outreach dq [--apply]     who should never have been enrolled
    hubricon outreach targets          in-ICP sellers worth a hand-written email
    hubricon outreach brief --seller   one page on a seller, with a verify checklist
    hubricon outreach draft --seller --first-name   the email, to edit and send by hand
    hubricon outreach partner --seller --partner --referral   the partner template

`role_inbox`, `bad_greeting` and `domain_mismatch` mean the *data* is wrong, not
the company. Rhino USA is squarely in the ICP and the harvest had resolved it to
`micah@micahrich.com`. Those go to the founder lane, not the bin.

**Resend is never used for outreach.** It carries client magic links, welcome
mail, teardown notices and this digest on hubricon.com. Cold email through it
would put the onboarding path's deliverability at risk to save some typing.

## What "PMF" means here, in numbers

`hubricon scoreboard` (or the daily digest) prints:

- contacted → replied → interested → bookings → onboarding → teardowns delivered
- paid → **renewed past the free month** → churned

The bar is **3 clients renewed past the free month at full price**. Below
that we are learning; above it, growth tactics are worth running. The
scoreboard excludes every internal address and the dry-run workspace.

## Reading the digest

Arrives at 8:17 am Chicago from the operator. Sections:

- **PMF scoreboard** — the numbers above.
- **Instantly campaign** — sent / replies / bounces as Instantly reports them.
- **Harvest** — sellers on file by status (candidate / enriched / pushed /
  skipped). If it stops moving for two days the Mac job is not running:
  `launchctl list | grep hubricon`, then `~/Library/Logs/hubricon-harvest.err`.
- **Replies waiting for a written answer** — the routine clears these within
  two hours; if a name sits there for a day, the routine is not running
  (check https://claude.ai/code/routines).
- **Only you can do these** — booked calls with times; teardowns delivered
  (optionally record a Loom and attach it with `hubricon brief … --video`).
- **Warnings** — missing secrets, API errors, a client whose files failed to
  parse.

## Running it by hand

```
cd engine
uv run hubricon operator --dry-run          # read everything, change nothing
uv run hubricon operator --send             # one real pass
uv run hubricon operator --send --digest    # …and email the digest
uv run hubricon scoreboard
```

Actions → "Hourly operator" → Run workflow does the same in the cloud (tick
"dry run" to rehearse).

## Guardrails

- Cold email is one plain-text email and no follow-ups (the founder's call,
  2026-09-03: the first email is the one that gets answered), weekdays 8–5
  Chicago, unsubscribe header on, opens and links untracked, stops for the
  whole company on a reply. Every claim in it is on the site. To change the
  copy, edit `campaign_spec` in `engine/src/hubricon_engine/outbound.py` and
  bump `COPY_VERSION`; the next operator pass updates the live campaign in
  place, so threads already sent keep their history.
- Replies to prospects come from templates or from Claude constrained to the
  fact sheet in `engine/src/hubricon_engine/triage.py`. No numbers the engine
  did not compute, no discounts, no guarantees.
- `not interested`, `unsubscribe`, out-of-office and bounces get no reply and
  the lead is closed in Instantly.
- Internal addresses (hubricon.com, gethubricon.com, hubricon.internal, the
  founder's Gmail, "John Doe") are never prospects, never clients, never
  counted.
- Prospects who say "later" get `follow_up_at` 90 days out; nothing
  re-contacts them automatically yet.
- Nobody is turned away before the founder has talked to them. The site's
  application never declines; every non-test booking is provisioned and
  welcomed. The routine's fit flag (`bookings.qualified` / `dq_reason`) is
  informational and shows up in the digest as "sell on this call".

## The 60-second Teardown (`/teardown`)

The lead magnet in front of the call. A visitor types five numbers off their
own product page — price, item weight, package dimensions, category, rank,
and optionally a landed cost — and the page prices one unit off Amazon's own
card, in the browser: the fee stack, the cliff (the same four detectors the
cold engine runs), the break-even ACoS and price floor, what 15 October does
to that unit, ten thousand simulated months, and where the listing sits among
everything the crawl has weighed in its category. Then the bridge: what a
public page cannot show, and the full Teardown.

Nothing is fetched from Amazon. Amazon soft-blocks datacenter fetches and the
harvest reads pages from the Mac, so the page never tries; the numbers are on
the listing under "Product information" and typing them is the sixty seconds.

**One table, two languages.** `engine/.../cold/priors.py` stays the only place
a published figure is edited. `hubricon teardown ratecard --json > ratecard.json`
writes the browser's copy; `lib/fees.js` is a port of priors/findings/shelf
over that JSON, used by the page and by `api/quick.js`. `lib/fees.test.mjs`
pins the port to `lib/fees.golden.json`, values the Python produced:

    cd engine && uv run hubricon teardown ratecard --json > ../ratecard.json
    node --test lib/fees.test.mjs

When a card changes: edit priors.py, run the pytest suite, regenerate the
JSON, regenerate the golden file, run the node test:

    cd engine && uv run python scripts/fees_golden.py    # writes ../lib/fees.golden.json The peak card (15 Oct 2026 – 14 Jan 2027) was
loaded on 2026-09-08 from a published reproduction and cross-checked against
one of Amazon's own worked examples; verify the rest against Seller Central
before 15 October. `priors.card_for(today)` picks the card in force, so the
cold engine no longer goes dark on the 15th.

**The API route.** `api/quick.js`: `?asin=` prefills from `harvest_products`
(public numbers the crawl already read); `?bench=<category>&oz=&dims=`
computes the category benchmark from `harvest_products` and returns
aggregates only, from 30 listings up; `POST` records a run in `tool_runs`
and creates (or advances) a `prospects` row at `wants_teardown`, source
`tool`. That is the whole deep follow-up: the hourly operator already
provisions every `wants_teardown` prospect and emails the private upload
page, so a tool lead gets the full Teardown path with no new job.

The result is reproducible from its URL — the inputs ride in the hash — so
"copy a link" and "send me this" both work without storing anything a
visitor did not ask to keep.

**The Shopify side (2026-09-09).** Same page, a platform toggle. A Shopify
product has no size tier and no rank, so the inputs are the product's own
numbers — price, compare-at, the shipping weight on the variant, units an
order, what the store charges for shipping, the plan (sets the Shopify
Payments rate), and orders a month typed by the merchant, which is why no
Shopify monthly figure is bracketed. The cards are USPS Ground Advantage
commercial by zone (already in priors) and Shopify Payments by plan (added to
priors, `payments_fee`). Outputs: one order through payments and the carrier
as a zone range with the subsidy chart, the pound cliff (`carrier_band_edge`
ported), the anchor gap (`permanent_discount` without the history it needs
to say "permanent"), break-even ROAS and the price floor, and the Shopify
benchmark on the pound boundary — which prints its store count, because 455
weighed parcels from 11 stores is those stores, not the market.

`?product=<url>` prefills: first the crawl's row (`asin` holds
`<domain>/products/<handle>` for Shopify rows), then the store's own
`/products/<handle>.json` and `/products.json?limit=250` with a browser
identity and a four-second timeout. Hosts are validated (public DNS names
only, never an address or a private suffix, and the redirect target is
re-checked) because the server fetches a URL a stranger typed. Stores that
refuse a datacenter fall back to typing; that case is expected and the page
says so. The capture creates the prospect exactly as the Amazon side does;
`teardown_requests` reads the platform from `tool_runs` when the harvest
does not know the address, so a Shopify merchant gets Shopify instructions.
