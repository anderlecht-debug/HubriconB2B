# Content pipeline — state

Updated 2026-09-20T09:30:25+00:00 · style locked: False

## Capabilities

- elevenlabs_key: True
- founder_voice_id: None
- youtube_token: False
- youtube_client: False
- textures_cached: False
- music_bed: elevenlabs
- sfx: elevenlabs

## Now

- idle

## Awaiting your review

- V01 · Why most business advice is useless: survivorship bias, with numbers · gate `review` → see `content/REVIEW.md`
- V04 · Your A/B test told you nothing. Here's the sample size you needed · gate `review` → see `content/REVIEW.md`
- V05 · Cash conversion cycle: the number that decides whether you survive · gate `review` → see `content/REVIEW.md`
- V07 · Contribution margin vs gross margin — the one that actually matters · gate `review` → see `content/REVIEW.md`
- V08 · Elasticity in plain English, and why your price is probably wrong · gate `review` → see `content/REVIEW.md`

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

- V02 · The $48,000 Amazon owes you and will never mention: Needs the founder's raw Seller Central screen recording (doctrine §10). The script and shot list are pre-written from recovery.run on demo data so only the recording remains. Protected Playbook feeder.
- V03 · Your bestseller might be your worst product. Here's how to check: Needs real SKU economics screenshots from Seller Central (doctrine §10). Engine-only variant on demo data is possible if the founder prefers; ask before promoting.
- V06 · Your FBA fee is not your FBA fee: Needs real fee preview and settlement screenshots from Seller Central.
- V10 · What a 12% return rate actually costs you: Needs the real FBA returns report on screen.
- V12 · Does $19.99 actually work? Charm pricing, tested: No engine model and no data for charm-price tests; producing it would require invented figures.
- V13 · Ad spend with zero attributed sales: find it in 20 minutes: Needs the real Campaign Manager search-term report on screen.
- V14 · LTV/CAC is lying to you: No engine model for LTV or CAC; needs a model or real figures.
- V20 · Storage fees: the cost that compounds while you sleep: Needs the real inventory health and storage fee reports on screen.
- V21 · Payback period: the only growth metric that can't be faked: No engine model for payback period; needs a model or real figures.
- V26 · The reimbursement windows closing on you right now: Needs the founder's raw Seller Central screen recording. Script and shot list pre-written from recovery.run. Protected Playbook feeder.
- V27 · Shopify's quiet margin killer: the shipping subsidy: Needs real Shopify orders and payouts exports on screen.

### Inputs the pipeline needs from you

1. Your voice: 3 to 5 minutes of clean audio now (see `docs/content/VOICE-RECORDING.md`), then `hubricon-content voice-clone --name "Hagen Simmons" <wav files>` and `ELEVENLABS_VOICE_ID` in `/home/lp9/Hubricon/HubriconB2B/.env`. Nothing renders in any other voice.
2. ElevenLabs tier: Starter's 40,000 characters a month covers about six videos. Creator (100,000) unlocks the professional clone the series should ship on; Pro (500,000) covers a video a day.
3. YouTube: a Google Cloud OAuth client JSON at `content/.secrets/client_secret.json`, then one interactive `hubricon-content youtube-auth` in a browser.
4. One interactive Higgsfield texture batch saved to `content/assets/textures/` with `manifest.json` (or accept the procedural fallback).
5. A licensed music bed in `content/assets/music/` (or ElevenLabs music once the key exists).
6. Course 1 screen recordings (one raw 4–8 minute recording per lesson) and Seller Central screenshots for the pillar-1 Desk videos.
7. `loginctl enable-linger lp9` (sudo if refused); optional `sudo pacman -S espeak-ng texlive-basic texlive-latexextra`.
8. Merge the `content → main` pull request when `/learn` is ready; deploy is a push to `main`.

## Stuck (three failures; needs a look)

- none

## Next five

- V09 · The price increase you're afraid of is probably free
- V11 · Discounting: the math of what you just gave away
- V15 · You don't have a revenue problem. You have a cash trough
- V16 · The $60,000 wire you're guessing on
- V17 · Why 95% service level is wrong for most of your SKUs
