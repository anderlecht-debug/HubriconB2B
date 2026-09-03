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
uv run hubricon harvest listings       # profile-only sellers: read the storefront, keep two live listings (rank, price, weight)
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
