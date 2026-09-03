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
| `hubricon sweep` | GitHub Actions, Mondays | secrets | the existing weekly ingest / models / alerts pass for active clients |
| `hubricon harvest` | the founder's Mac, launchd, daily 06:10 | `.env` (Supabase; Instantly key optional) | free leads: Best Sellers → product pages → seller profiles → brand sites; rows wait as `enriched` until the operator pushes them to the Instantly list |

The routine never sends email. The operator never reads the inbox. Both talk
through Supabase (`bookings`, `prospect_messages`, `funnel_events`,
`operator_state`).

## The one-time setup (five minutes, once)

GitHub → repo → Settings → Environments → **Production** → add:

| Secret | Why |
|---|---|
| `INSTANTLY_API_KEY` | Instantly → Settings → Integrations → API keys → v2 key with `all:all`. Outbound is OFF until this exists. Needs the Growth plan or above. |
| `POSTAL_ADDRESS` | A mailing address (PO box is fine). CAN-SPAM requires one in every cold email; the operator refuses to create the campaign without it. |
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
```

**Second source, the Wayback Machine.** The Internet Archive holds ~1,800
captures of `amazon.com/sp?seller=…` from 2021 on, each with the storefront
name, business name and address, country and feedback counts. `hubricon
harvest wayback` reads them from web.archive.org (three fetchers, ~2
requests a second, never Amazon) into `harvest_sellers` with `source =
'wayback'`; the storefront name stands in for the brand and the size
estimate comes from the feedback count, so the row still has to earn a live
website and contact address in `enrich`. The CDX listing is saved at
`~/.hubricon/harvest/wayback-sellers.cdx`; delete it to re-list.

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
