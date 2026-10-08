# The script kit: draft anywhere, hand it over, the film starts

Draft a film's script wherever you like: a claude.ai project, another tool, or by hand. Write it in
the format below and hand it over. From then on the machine runs everything else.

## Handing a script over (any one of these)

- **Drop the file in `~/Hubricon/scripts-inbox/`** (`.md` or `.txt`). The runner checks the folder every
  30 minutes. A clean script is filed and moved to `taken/`. A script with problems is moved to `refused/`,
  with its problems in a `.problems.json` file beside it.
- **Paste it into any Claude Code chat on this machine**, with a line saying it's a film script. The
  session saves it and runs the intake. Every chat knows how, from `~/.claude/CLAUDE.md`.
- **Run it yourself:** `hubricon-content script-in <file>` in `HubriconB2B-content/content`. Add `--dry`
  to check a script without filing it.

The intake costs no tokens. It checks the script, writes the film's folder, builds its figures, and
queues the film as approved (handing it over is your approval). Then it tells you to record:

    node content/film/record.mjs <slug>

Once your takes are in, the runner runs the whole line on its own:

1. takes to narration and timing;
2. the shot plan (one capped model reply, about 0.16M tokens);
3. pictures;
4. render;
5. film-qa;
6. the draft.

You get a draft to watch.

## What to give your drafting tool

1. This kit.
2. `docs/content/SCRIPT_REFERENCE.md`: the visual style names, the chart scenes and the demo's figure
   keys. It is generated, so it is always current.
3. `docs/content/series/greats-of-commerce.md` for a Greats film: its architecture (§2), how history
   is written honestly (§3) and its cinematography (§4).
4. One approved script as the model: `content/videos/greats-02-the-dime/script.md` (with its
   `history.json` for how sources are written).

## The format

```
SERIES:           Greats of Commerce
TITLE:            Woolworth's Kept Its Dime Ceiling for {{w_ceiling_span}}. Here's What It Never Told Them
SHORT:            the dime
THUMBNAIL:        One {{key}} figure and one chart fragment; no face, no arrows
PILLAR:           3
TIER:             D
AWARENESS STAGE:  problem-aware
CTA:              The free Price Curve course at hubricon.com/learn, then the one soft close.
SPIKY CLAIM:      One disputable sentence the film earns.
MISCONCEPTION:    The intuitive belief the film takes apart.
RUNTIME:          29–32 min

HOOKS (three, pick one)
1. {{key}} in the first sentence. The misconception in the second. The loop opened in the third.
2. …
3. …

SCRIPT
[0:00] COLD OPEN
  VO: The narration, exactly as you will read it. Every figure is a {{key}}.
  VISUAL: still-push on <the picture, where it comes from and its licence>; number-land on {{key}}
  CLIP: yes

[1:20] CHAPTER — ONE PRICE
  VO: One price.
  VISUAL: chapter

[4:18] A BEAT THAT DRAWS A CHART
  VO: …
  VISUAL: staircase of the demo product's price steps …
  DATA SOURCE: demo: Tarnhollow demo data
  CLIP: no

[28:55] THE HONEST LIMIT
  VO: What this can't do, and what that needs.
  VISUAL: …
  DATA SOURCE: demo: Tarnhollow demo data
  CTA: The free Price Curve course at hubricon.com/learn. …
  CLIP: yes

RE-HOOK AUDIT: 0:31, 1:02, 1:37, …   (every re-hook, never more than 40 s apart)
DERIVED ASSETS: …

FACTS
w_ceiling_span | more than 50 years | how long the ceiling held | https://… (the document and where in it)
w_rent | $30 a month | the Lancaster store's rent | https://archive.org/… (the company's centennial report)
```

`SERIES`, `SHORT` (a few words naming the film) and `SLUG` are optional. They set the film's name, for
example `greats-04-the-dime`. A Greats film is numbered after the last one.

## The rules the intake checks

**Figures and sources**

- **Every figure is a `{{key}}`.** That covers digits, currency, percentages and dates with numbers, in
  the VO, the hooks, the title, the thumbnail and the CTA. Write the sentence around the key:
  "The rent was {{w_rent}}."
- **Every key has a FACTS line with a source.** The line is `key | value | label | source`. Keys are lower
  case, with digits and `_`; give a film's keys one prefix (`w_` for Woolworth). The source names the
  document and where in it, with a link wherever there is one. A figure with no source is refused.
  Nothing is invented: if you can't source a figure, describe it without a number.
- **Demo figures** (the Tarnhollow demo, for the bridge to today) use the keys in
  `SCRIPT_REFERENCE.md` and need no FACTS line. Each beat that shows one says
  `DATA SOURCE: demo: Tarnhollow demo data`.

**Length and structure**

- **Tier D runs 3,000 to 7,500 spoken words.**
- **Three hooks**, each under 45 words, with a `{{key}}` in the first sentence.
- **Beats** start with `[m:ss] NAME`. A chapter is `[m:ss] CHAPTER — NAME` with `VO: Name.` and
  `VISUAL: chapter`.

**Every beat's VISUAL**

- **Every beat has a `VISUAL`** naming at least one style from `SCRIPT_REFERENCE.md` (`still-push`,
  `archive-framed`, `number-land` …).
- Say where a picture comes from and its licence. The film uses public-domain, CC0 and "no known
  restrictions" archives, and states the picture's real place and date: never "captioned as Lancaster"
  for a picture of Scranton.
- **A beat that draws a chart** carries `DATA SOURCE:`: the demo run (`demo: …`), the public-data case
  study, or a published source (`published: …`).

**Clips, the call to action and re-hooks**

- **At least three `CLIP: yes`** beats, on self-contained moments.
- **Exactly one `CTA:`**, on the honest-limit beat, pointing to hubricon.com/learn. Pillars 1 to 4 name no
  product in the soft close. Never the Teardown.
- **A re-hook at least every 40 seconds**, listed honestly in `RE-HOOK AUDIT`.

**Banned phrases**

- **Never these:** "in today's video", "let's dive in", "game-changer", "secret", "hack", "crazy",
  "insane", "simply", "just", "obviously", "of course", "the truth is", "imagine".

When a script is refused, every problem comes back in one list, with the beat it is in. Fix them where
you drafted it and hand it over again.
