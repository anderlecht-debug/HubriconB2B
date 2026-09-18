TITLE:            Why most business advice is useless: survivorship bias, with numbers
THUMBNAIL:        {{year_luck_spread}} in amber beside the fan of paths, the top tenth lit
PILLAR:           4
TIER:             A
AWARENESS STAGE:  unaware
CTA:              Subscribe, and the newsletter. Nothing else.
SPIKY CLAIM:      Most of the gap between the top tenth and the median of similar businesses is dice, and from the outside you cannot tell which.
MISCONCEPTION:    The founders who finished on top did something different. Find out what, and copy it.
RUNTIME:          5–6 min

HOOKS (three, pick one)
1. {{year_luck_spread}}. That's the gap between the luckiest tenth and the unluckiest tenth of {{year_paths}} versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.
2. {{year_top_vs_median}} above the median, same prices, same reorders, same ad budget. That's how far luck alone carried the top tenth in a year. Everything they'd tell you about how they did it would be true, and useless.
3. Here are {{year_paths}} companies that ran an identical plan. The top tenth finished with {{year_top_decile}}. The bottom tenth finished with {{year_bottom_decile}}. Only one of those groups gets asked for advice.

SCRIPT
[0:00] HOOK
  VO: {{year_luck_spread}}. That's the gap between the luckiest tenth and the unluckiest tenth of {{year_paths}} versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.
  VISUAL: kinetic: the spread lands on the first word, then the count of paths
  CLIP: yes

[0:15] LET THEM BE WRONG
  VO: Here's the model most of us run on. Somebody grew a brand until it was big. They wrote the post, they did the podcast, they listed the moves. Reorder deeper. Hold the price. Cut the bottom of the catalog. The moves worked for them, so the moves must be the reason. It's a fair model. It's how we learn nearly everything. Watch someone succeed, then do what they did. The problem isn't the logic. The problem is who we get to watch.
  VISUAL: kinetic: the misconception in the viewer's own words (a real screenshot of a "how I scaled it" post replaces this beat when the founder supplies one)
  CLIP: no

[0:45] THE CRACK
  VO: So let's find out what the winners did. Not from an interview. From a machine that ran the same plan {{year_paths}} times. One catalog, {{n_skus}} products, about {{annual_revenue_m}} a year in sales, {{cash_on_hand}} in the bank on day one. Same prices every run. Same reorder points. Same ad spend. The only thing that changes between runs is which customers show up on which day. Here's how the year ends. The median finished at {{year_terminal_p50}}. The top tenth finished at {{year_top_decile}}. The bottom tenth, {{year_bottom_decile}}.
  VISUAL: paths: every path drawn thin, then the ending spread at the right edge
  DATA SOURCE: cash horizon paths, one-year horizon, Tarnhollow demo data
  CLIP: yes

[1:15] CHAPTER 1 — THE DICE
  VO: Now go and interview the top tenth. Every one of them can tell you, truthfully, what they did. They reordered on schedule. They held their price through the slow months. They kept the ads running. And every one of those things is also what the bottom tenth did, because it is the same plan. The gap between {{year_top_decile}} and {{year_bottom_decile}} is which days the customers came, and nothing else. That gap is {{year_luck_spread}}. It's {{year_luck_spread_pct}} of the median outcome, produced by the order the demand arrived in. If you only ever hear from the top, you will credit all of it to the moves. The moves were shared. The outcome wasn't. And the story the winners tell about the moves will be sincere, detailed, and wrong about what caused what.
  VISUAL: paths: the top tenth lit amber, the median line, the spread bracket at the right edge
  DATA SOURCE: cash horizon paths, one-year horizon, Tarnhollow demo data
  CLIP: yes

[2:45] CHAPTER 2 — THE WORST DAY
  VO: Here's the part that should bother you more. Look at the worst day of the year for the winners. The lowest their cash went was {{year_top_trough}}. Now look at the lowest point for every run, winners and losers together: {{year_all_trough}}. Same number. The top tenth went through the identical worst day as the bottom tenth, on the same date, for the same reason: the supplier wires leave before the platform pays out. Nobody in the winners' circle will mention that day, because they came out the other side and it stopped mattering. The people it did matter to aren't giving interviews. That is survivorship bias in a sentence. The sample you can hear from was selected by the outcome you are trying to explain. So the advice isn't merely incomplete. It is tilted toward whatever risk the survivors happened to survive.
  VISUAL: cash_cone: the cone with the trough marked and the supplier wires as red ticks
  DATA SOURCE: cash horizon on Tarnhollow demo data
  CLIP: yes

[4:00] WHAT TO DO
  VO: A short list, and you can do all of it this week. First, before you copy anyone, ask for the denominator. How many people ran this plan, and how many of them are not on the podcast. If nobody can answer, treat the advice as a story, not a method. Next, look for the shared moves. If the winners and the losers did the same thing, that thing is not the explanation, however confidently it's told. Last, run your own plan more than once. Take your last year, change nothing but the order the demand arrived in, and see how wide the spread gets. If it's wide, most of what you'd credit to skill is variance, and the plan should be judged on its worst tenth, not its best.
  VISUAL: kinetic: the steps landing one at a time
  TEMPLATE: none for this pillar

[4:45] THE HONEST LIMIT
  VO: What you can't do by hand is that last step at any real scale. Running a year of a {{n_skus}}-product catalog {{year_paths}} times, with demand that moves together across products the way it really does, is a model, and a bad model is worse than no model. What you can do today is stop asking winners how they won. Ask how many people ran their plan, and where the rest of them are.
  VISUAL: kinetic: the closing question
  CTA: If this was useful, subscribe. The newsletter carries one of these a week.

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:15, 1:50, 2:20, 2:45, 3:20, 3:50, 4:00, 4:30, 4:45, 5:10 — no gap over 40 s
DERIVED ASSETS: LinkedIn post: "the winners' worst day was everyone's worst day" · X thread spine: same plan, {{year_paths}} runs, {{year_luck_spread}} of dice · newsletter section: how to ask for the denominator · clips at 0:00, 0:45, 1:15, 2:45
