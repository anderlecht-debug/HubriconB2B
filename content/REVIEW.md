# Review inbox

Updated 2026-09-19T00:01:39+00:00. Everything here is parked until you decide. Nothing renders before a script is approved; nothing uploads before the final sign-off.

## V01 · day 1 · tier A · pillar 4 — script gate

**Title:** Why most business advice is useless: survivorship bias, with numbers  
**Thumbnail:** $65,320 ⟨year_luck_spread⟩ in amber beside the fan of paths, the top tenth lit  
**Spiky claim:** Most of the gap between the top tenth and the median of similar businesses is dice, and from the outside you cannot tell which.  
**Misconception:** The founders who finished on top did something different. Find out what, and copy it.  
**CTA:** Subscribe, and the newsletter. Nothing else.  
**Estimated runtime:** about 4 min 33 s · **voice:** placeholder until the clone exists

### Hooks (the first is the one that ships unless you say otherwise)

1. $65,320 ⟨year_luck_spread⟩. That's the gap between the luckiest tenth and the unluckiest tenth of 2,000 ⟨year_paths⟩ versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.
2. $45,419 ⟨year_top_vs_median⟩ above the median, same prices, same reorders, same ad budget. That's how far luck alone carried the top tenth in a year. Everything they'd tell you about how they did it would be true, and useless.
3. Here are 2,000 ⟨year_paths⟩ companies that ran an identical plan. The top tenth finished with $1,014,998 ⟨year_top_decile⟩. The bottom tenth finished with $924,168 ⟨year_bottom_decile⟩. Only one of those groups gets asked for advice.

### Script

**[0:00] HOOK**  
$65,320 ⟨year_luck_spread⟩. That's the gap between the luckiest tenth and the unluckiest tenth of 2,000 ⟨year_paths⟩ versions of the same business, running the same plan for a year. You'd read the winners' interviews and call it strategy. It's dice, and I can show you the dice.  

**[0:15] LET THEM BE WRONG**  
Here's the model most of us run on. Somebody grew a brand until it was big. They wrote the post, they did the podcast, they listed the moves. Reorder deeper. Hold the price. Cut the bottom of the catalog. The moves worked for them, so the moves must be the reason. It's a fair model. It's how we learn nearly everything. Watch someone succeed, then do what they did. The problem isn't the logic. The problem is who we get to watch.  

**[0:45] THE CRACK**  
So let's find out what the winners did. Not from an interview. From a machine that ran the same plan 2,000 ⟨year_paths⟩ times. One catalog, 24 ⟨n_skus⟩ products, about $3.5M ⟨annual_revenue_m⟩ a year in sales, $262,000 ⟨cash_on_hand⟩ in the bank on day one. Same prices every run. Same reorder points. Same ad spend. The only thing that changes between runs is which customers show up on which day. Here's how the year ends. The median finished at $969,579 ⟨year_terminal_p50⟩. The top tenth finished at $1,014,998 ⟨year_top_decile⟩. The bottom tenth, $924,168 ⟨year_bottom_decile⟩.  

**[1:15] CHAPTER 1 — THE DICE**  
Now go and interview the top tenth. Every one of them can tell you, truthfully, what they did. They reordered on schedule. They held their price through the slow months. They kept the ads running. And every one of those things is also what the bottom tenth did, because it is the same plan. The gap between $1,014,998 ⟨year_top_decile⟩ and $924,168 ⟨year_bottom_decile⟩ is which days the customers came, and nothing else. That gap is $65,320 ⟨year_luck_spread⟩. It's 7% ⟨year_luck_spread_pct⟩ of the median outcome, produced by the order the demand arrived in. If you only ever hear from the top, you will credit all of it to the moves. The moves were shared. The outcome wasn't. And the story the winners tell about the moves will be sincere, detailed, and wrong about what caused what.  

**[2:45] CHAPTER 2 — THE WORST DAY**  
Here's the part that should bother you more. Look at the worst day of the year for the winners. The lowest their cash went was $95,201 ⟨year_top_trough⟩. Now look at the lowest point for every run, winners and losers together: $95,201 ⟨year_all_trough⟩. Same number. The top tenth went through the identical worst day as the bottom tenth, on the same date, for the same reason: the supplier wires leave before the platform pays out. Nobody in the winners' circle will mention that day, because they came out the other side and it stopped mattering. The people it did matter to aren't giving interviews. That is survivorship bias in a sentence. The sample you can hear from was selected by the outcome you are trying to explain. So the advice isn't merely incomplete. It is tilted toward whatever risk the survivors happened to survive.  

**[4:00] WHAT TO DO**  
A short list, and you can do all of it this week. First, before you copy anyone, ask for the denominator. How many people ran this plan, and how many of them are not on the podcast. If nobody can answer, treat the advice as a story, not a method. Next, look for the shared moves. If the winners and the losers did the same thing, that thing is not the explanation, however confidently it's told. Last, run your own plan more than once. Take your last year, change nothing but the order the demand arrived in, and see how wide the spread gets. If it's wide, most of what you'd credit to skill is variance, and the plan should be judged on its worst tenth, not its best.  

**[4:45] THE HONEST LIMIT**  
What you can't do by hand is that last step at any real scale. Running a year of a 24 ⟨n_skus⟩-product catalog 2,000 ⟨year_paths⟩ times, with demand that moves together across products the way it really does, is a model, and a bad model is worse than no model. What you can do today is stop asking winners how they won. Ask how many people ran their plan, and where the rest of them are.  
*CTA:* If this was useful, subscribe. The newsletter carries one of these a week.  

### Shot list

| at | scene | data source |
|---|---|---|
| 0:00 | kinetic: the spread lands on the first word, then the count of paths |  |
| 0:15 | kinetic: the misconception in the viewer's own words (a real screenshot of a "how I scaled it" post replaces this beat when the founder supplies one) |  |
| 0:45 | paths: every path drawn thin, then the ending spread at the right edge | cash horizon paths, one-year horizon, Tarnhollow demo data |
| 1:15 | paths: the top tenth lit amber, the median line, the spread bracket at the right edge | cash horizon paths, one-year horizon, Tarnhollow demo data |
| 2:45 | cash_cone: the cone with the trough marked and the supplier wires as red ticks | cash horizon on Tarnhollow demo data |
| 4:00 | kinetic: the steps landing one at a time |  |
| 4:45 | kinetic: the closing question |  |

### Decide

```
hubricon-content approve 01-survivorship-bias
hubricon-content reject  01-survivorship-bias --note "what to change"
```
Edit `content/videos/01-survivorship-bias/script.md` first if you prefer; it is re-validated on approve.
