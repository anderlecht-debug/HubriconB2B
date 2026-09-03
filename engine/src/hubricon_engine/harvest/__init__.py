"""Free lead harvest: the sellers Amazon makes public, one polite request at a time.

Every professional seller on amazon.com has a profile page carrying the
business name and address Amazon has required them to publish since
September 2020. Best Sellers lists name the products, product pages name
the brand and the seller, and the brand's own site usually publishes a
contact address. Chaining those four public pages yields the same rows the
paid "Amazon seller databases" sell, for nothing.

Modules:
  fetch    polite HTTP (cookie jar, pacing, captcha detection, parsed-result cache)
  amazon   parsers for Best Sellers, product and seller-profile pages + a BSR→units curve
  enrich   brand → website (direct guess, then Bing) → published contact / founder name
  run      the crawl → enrich → push pipeline, status, and the launchd install

The crawl must run from a residential connection (the founder's Mac):
datacenter ranges get a captcha. Pushing the finished rows to Instantly can
run anywhere the API key lives, so the hourly operator does it too.
"""
