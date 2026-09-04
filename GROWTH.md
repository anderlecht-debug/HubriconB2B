# Growth: reaching sellers for free

Two platforms, two free sources of the same kind of row. The Amazon half is
below; the Shopify half is the section that follows it, and it exists because
Amazon fights the crawl and Shopify does not.

The paid "Amazon seller databases" resell public data. Amazon has required
every professional seller to publish a business name and address on its
seller profile since 1 September 2020; Best Sellers lists name the
products, product pages name the brand and the seller, and the brand's own
site publishes the address it wants customers to write to. Chaining those
four public pages is the harvester (`hubricon harvest`, see OPERATIONS.md).
The Internet Archive's captures of those seller profiles are a second copy
of the same database that never touches Amazon (`hubricon harvest wayback`).
The seller's own feedback count on the profile page sizes the account, which
keeps the $100M brands (who will not answer a cold email) off the list.
It replaces the lead-credit spend and keeps the cold-email lane fed.

Cold email is capped by mailboxes, not by leads: two warmed mailboxes send
about 40 first touches a day. The channels below are how the same offer
reaches thousands of sellers at once without buying anything. Each one
takes founder time in minutes, not hours, and none of them ask a prospect
for anything before the free month does.

## The second source: Shopify stores

Amazon has been the problem, not the plan. It fingerprints the client as well
as the pace, answers datacenter ranges with a captcha, and since 2026-09-03
serves a soft-block page once a client is flagged — so the crawl spends its
day backing off instead of reading pages.

A Shopify store publishes more, to anyone, with no captcha at all. Every store
serves `/meta.json` (shop name, city, province, country, currency, primary
domain) and `/products.json` (every product, its vendor, type, variants,
prices, weights and created dates) as plain JSON, because the storefront's own
theme reads them. Review apps put an `aggregateRating` with a review count in
the product page's JSON-LD, which sizes the account the way Amazon's
seller-feedback count did. The contact and legal pages a store must publish —
`/policies/contact-information`, `/policies/legal-notice`, `/pages/about` —
carry the address and often the founder's name. That is the same four-page
chain the Amazon harvest walks, without the adversary.

Finding the stores is the part that took two tries. The Internet Archive lists
captured `*.myshopify.com` homepages for free, but a brand that succeeds buys a
domain, so what the archive keeps is Shopify's own dev stores and abandoned
shops. Five of them yielded nothing worth writing to.

What works is Shopify's own marketplace. Every brand on shop.app is a paying,
trading merchant, and search engines index those pages beside the brand's own
site — so `site:shop.app <category>` is a category-filtered list of real
Shopify stores, and asking each domain for `/meta.json` confirms it in one
request. They all have their own domain, which means a real inbox rather than
`hello@…myshopify.com`, which bounces.

One caveat, learned the hard way on 2026-09-04: the store endpoints answer 429
to a plain HTTP client and serve their JSON happily to headless Chrome from the
same connection. Same fingerprinting lesson Amazon taught, same fix. It still
has to run from the Mac.

    hubricon harvest shopify --limit 40

The qualification bar is the same one: a US brand selling its own products,
roughly $1M–$20M a year, run by someone who answers their own email. A store
whose catalog carries three or more vendors with none dominant is a reseller;
a two-product store is too small; a catalog of thousands is a marketplace.

**The hook changes with the platform.** For an Amazon seller it is the FBA fee
cliff: the packed weight, the band edge just below it, and the units that
weight ships at every month. A Shopify brand pays no FBA fee — it pays USPS
and UPS, whose bands are 4, 8, 12 and 16 ounces and then every pound. A
product that ships at 17 ounces pays the two-pound rate on every unit. Same
arithmetic, same thirty-second check by the seller, different rate card.

Everything downstream is unchanged: the row lands in `harvest_sellers` beside
the Amazon rows, earns a website and a contact address in `enrich`, and goes
to the founder lane or the Instantly list on exactly the same rules — role
inboxes are never cold-emailed.

## 0. The founder lane (the first few clients come from here)

Everything below this is a channel that scales. This one does not, and it is
the one most likely to produce the first paying customer, so it goes first.

The harvest finds brands and published addresses. Almost every address it finds
is a role inbox, because that is what a brand publishes. A cold sequence to
`hello@` is worth close to nothing; a human who spends ten minutes finding the
owner's name and writes about that brand's own listing is worth a great deal.

    hubricon outreach targets                       who is worth the ten minutes
    hubricon outreach brief --seller <seller_id>    one page, with a verify checklist
    hubricon outreach draft --seller <id> --first-name <name>

The hook is the FBA fee cliff, because the seller can check it in thirty
seconds: the packed weight, the band edge just below it, and the units that
weight ships at every month. All three come off a public product page.

Five to eight a day, ten at the most, sent by hand from Hagen's own mailbox
after editing. Never through Instantly (a young domain should not learn what it
is from the twenty highest-value names) and never through Resend (it carries
client mail). The brief ends in a verification checklist because the harvest
does get these wrong: it resolved Rhino USA to someone else's personal address
and stored "Washington" as Sol de Janeiro's contact first name.

## 1. The data post (weekly, ~20 minutes)

The harvest stores the public weight, dimensions, rank and price of every
product page it reads (`harvest_products`). That is a dataset nobody else
publishes: how many best-selling FBA products sit within an ounce or an inch
of a cheaper fulfilment tier, what that costs per year at their rank, which
categories leak most. Marketplace Pulse built an audience on exactly this
kind of finding.

Format, every time:

- One number in the title. "We checked 1,200 best-selling FBA listings: 31%
  are within 1 oz of a cheaper fee tier."
- The method in two lines (public pages, the fee schedule, the estimate curve
  and its error bars). Sellers trust arithmetic they can check.
- The finding, a chart, and the one thing a seller can do about it today.
- No pitch in the post. The profile and the site do the selling; anyone who
  asks in the comments gets "happy to run yours, first month is free".

Where it goes, same morning: r/FulfillmentByAmazon and r/AmazonSeller,
Amazon Seller Forums (General Selling Questions), LinkedIn, and the FBA
Facebook groups whose admins allow data posts (ask once). One post reaches
more sellers than a month of mailboxes.

`hubricon harvest report` prints the first of these from whatever is on
file: the share of listings within an ounce of a lighter FBA weight band,
by category, with the biggest movers. `--within-oz 0.5` tightens it. The
post is worth publishing once the table holds a thousand weighed products,
about a week of the daily crawl.

## 2. Public Profit Teardown of a named brand (fortnightly)

Pick a well-known private-label brand and run the teardown from public data
only: price history, rank, review velocity, listing weight versus the fee
tier, the stockout pattern visible in the Buy Box. Publish what the numbers
say and what you would change. It demonstrates the product on a brand
everyone recognises, it is shareable, and the brand itself sometimes
replies. Never state a private number as fact; every figure is labelled as
an estimate from public pages.

## 3. Amazon's own directory: the Service Provider Network (once, 30 minutes)

Amazon lists service providers for sellers inside Seller Central and at
sell.amazon.com/tools/service-provider-network. Listing is free; it needs a
Solution Provider Portal account, ID verification and business documents,
and approval takes weeks, so it is applied for now and pays later. It is the
only channel where a seller who is already looking for help finds Hubricon
without anyone emailing them.

## 4. Partners who already hold the list (10 emails, once)

Three kinds of businesses have hundreds of $1M+ sellers as clients and no
margin product to sell them:

- e-commerce bookkeepers and accountants (the A2X partner directory lists
  them by name),
- prep centres and freight forwarders,
- Amazon lenders and factoring companies.

The offer to a partner: their clients get the Profit Teardown and the free
month; the partner gets the anonymised results to publish and a referral fee
on anything that renews. One partner introduction carries more trust than a
thousand cold emails. The template is a three-line email naming one of
their clients' public listings and one number from it.

## 5. Answer engine (15 minutes a week)

Seller Forums and the subreddits carry daily questions about fees, pricing
moves, stockouts and ad spend. Answering with real arithmetic, under the
founder's name, is the slow channel that compounds: the answers rank in
search for years. Rule: answer fully, link nothing, let people click the
profile.

## 6. The testimonial loop

The free month is priced in testimonials and anonymised results. Each one
becomes the next data post's opening line ("a $4M kitchen brand found
$11k/month in three price moves"), which feeds channels 1 and 4. The first
paying client is the whole growth engine; everything above exists to get
them.

## What not to do

- Do not message sellers through Amazon Buyer-Seller Messaging. It is for
  order questions; solicitation gets the buyer account closed and is the
  fastest way to poison the brand with the people it serves.
- Do not automate LinkedIn or Reddit posting. Both ban for it and the
  founder's name is the asset.
- Do not buy lists. The harvester produces the same rows from the same
  public sources, and a purchased list carries the bounces of everyone who
  bought it before.
- The harvester itself reads public pages at a few requests a minute from a
  home connection; Amazon's terms discourage automated access, so it never
  pushes through a captcha and it never runs from a datacenter.

## The week

| When | What | Minutes |
|---|---|---|
| Daily 06:10 | `hubricon harvest all` (launchd, automatic) | 0 |
| Monday | Data post from the harvest table | 20 |
| Wednesday | Answer three questions on the forums | 15 |
| Every other Friday | Public teardown of a named brand | 40 |
| Once | SPN application; ten partner emails | 90 |

Everything else stays with the operator: enrolment, replies, bookings,
teardowns, the digest.
