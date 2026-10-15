Plan the shots of the film greats-02-the-dime.

1. Read content/videos/greats-02-the-dime/plan-brief.md. It is the only file you need: the rules, the plan fields, the styles, the figures and every sentence with its time and legal cuts. Do not read other files.
2. Write content/videos/greats-02-the-dime/shots.json as the brief says. Write it in a few large writes, by a short Python script that builds the list, not shot by shot. Keep each `intent` to twelve words or fewer. Give every world or archival shot `query`, `sources` and `fallback`. Give number, pair and formula shots a `params.print` with a `want` (query and sources) whenever a true picture fits the sentence.
3. Run `content/.venv/bin/hubricon-content shots-fill greats-02-the-dime`, then `content/.venv/bin/hubricon-content shots-validate greats-02-the-dime`. Fix what it names; screen-mix shares are advisory. Stop when it prints clean, or after three validate rounds.

Reply with the number of shots and the validator's last line, nothing else.
