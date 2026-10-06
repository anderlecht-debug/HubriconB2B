# Content pipeline — state

Updated 2026-10-06T07:05:10+00:00 · style locked: True

## Capabilities

- youtube_token: False
- youtube_client: False
- textures_cached: False
- music_bed: on file
- sfx: on file

## Now

- idle

## Awaiting your review

- nothing waiting

## Done

- P0-tooling · Tooling, docs, skills, state, runner, timer
- P1-template · Reimbursement Playbook spreadsheet template
- P1-lessons · Reimbursement Playbook written lessons
- P1-course-page · learn/reimbursement-playbook.html
- P1-api-learn · api/learn.js capture and routing
- P1-learn-hub · learn/index.html
- P1-followup · Recovered-amount follow-up
- P1-index-links · Nav and footer links on index.html

## Blocked on founder input

- T01 · October 15: what Amazon's holiday fees cost one listing, to the cent: the founder's own takes: read the script at the teleprompter, `node content/film/record.mjs october-15` (docs/content/VOICE-RECORDING.md)
- F01 · The case-study film: one listing, a fraction of an ounce past an edge: the founder's own takes: read the script at the teleprompter, `node content/film/record.mjs case-study-film` (docs/content/VOICE-RECORDING.md)
- F02 · The store study's film: a real store's orders, called before and measured after: the founder's own takes: read the script at the teleprompter, `node content/film/record.mjs store-study-film` (docs/content/VOICE-RECORDING.md)
- V01 · Why most business advice is useless: survivorship bias, with numbers: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs 01-survivorship-bias (docs/content/VOICE-RECORDING.md)
- V02 · The $48,000 Amazon owes you and will never mention: Needs the founder's raw Seller Central screen recording (doctrine §10). The script and shot list are pre-written from recovery.run on demo data so only the recording remains. Protected Playbook feeder.
- V03 · Your bestseller might be your worst product. Here's how to check: Needs real SKU economics screenshots from Seller Central (doctrine §10). Engine-only variant on demo data is possible if the founder prefers; ask before promoting.
- V05 · Cash conversion cycle: the number that decides whether you survive: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs 05-cash-conversion-cycle (docs/content/VOICE-RECORDING.md)
- V06 · Your FBA fee is not your FBA fee: Needs real fee preview and settlement screenshots from Seller Central.
- V07 · Contribution margin vs gross margin — the one that actually matters: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs 07-contribution-vs-gross-margin (docs/content/VOICE-RECORDING.md)
- V10 · What a 12% return rate actually costs you: Needs the real FBA returns report on screen.
- V12 · Does $19.99 actually work? Charm pricing, tested: No engine model and no data for charm-price tests; producing it would require invented figures.
- V13 · Ad spend with zero attributed sales: find it in 20 minutes: Needs the real Campaign Manager search-term report on screen.
- V14 · LTV/CAC is lying to you: No engine model for LTV or CAC; needs a model or real figures.
- V20 · Storage fees: the cost that compounds while you sleep: Needs the real inventory health and storage fee reports on screen.
- V21 · Payback period: the only growth metric that can't be faked: No engine model for payback period; needs a model or real figures.
- V26 · The reimbursement windows closing on you right now: Needs the founder's raw Seller Central screen recording. Script and shot list pre-written from recovery.run. Protected Playbook feeder.
- V27 · Shopify's quiet margin killer: the shipping subsidy: Needs real Shopify orders and payouts exports on screen.
- G01 · Greats of Commerce 1: the rate card that built Sears: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs greats-01-sears-parcel-post (docs/content/VOICE-RECORDING.md)
- G02 · Greats of Commerce 2: the dime: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs greats-02-the-dime (docs/content/VOICE-RECORDING.md)
- G03 · Greats of Commerce 3: the corner: the founder's own takes: read the script at the teleprompter, node content/film/record.mjs greats-03-the-corner (docs/content/VOICE-RECORDING.md)

### Inputs the pipeline needs from you

1. Watch the style reel (`content/videos/style-reel/style-reel.mp4`, 36 s, silent: the site's own charts and type on a film stage). If the look is right, freeze it: `node content/film/lock.mjs`. Every film after reuses it.
2. Read F01 (the home page's case-study film) and T01 (October 15) in `content/REVIEW.md`; `hubricon-content approve <slug>` or `reject <slug> --note "..."`. T01 is dated: it is only worth publishing before the holiday card ends.
3. Your voice, your own recording first (HUBRICON_SPEC.md): `node content/film/record.mjs <slug>` opens a teleprompter at http://127.0.0.1:8790; read each beat, keep the take. Then `node content/film/render.mjs content/videos/<slug>/board.json content/videos/<slug>/media/master.mp4 --audio content/videos/<slug>/takes` and `node content/film/check.mjs content/videos/<slug>/board.json content/videos/<slug>/media/master.mp4`.
4. YouTube: a Google Cloud OAuth client JSON at `content/.secrets/client_secret.json`, then one interactive `hubricon-content youtube-auth` in a browser.
5. A licensed music bed in `content/assets/music/` if the series is to have one (the films render without).
6. Seller Central screenshots or screen recordings for the parked pieces that need them (V02, V03, V06, V10, V13, V20, V26).

## Stuck (three failures; needs a look)

- none

## Next five

- V04 · Your A/B test told you nothing. Here's the sample size you needed
- V08 · Elasticity in plain English, and why your price is probably wrong
- V09 · The price increase you're afraid of is probably free
- V11 · Discounting: the math of what you just gave away
- V15 · You don't have a revenue problem. You have a cash trough
