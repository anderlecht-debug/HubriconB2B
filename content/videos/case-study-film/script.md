TITLE:            One listing, a fraction of an ounce past an edge
THUMBNAIL:        {{step_np}} a unit, in blue, on the riser between the dots
PILLAR:           0
TIER:             F
AWARENESS STAGE:  problem-aware
CTA:              Book the call. Not ready yet? The whole method is free at hubricon.com/learn.
SPIKY CLAIM:      A P&L is an average, and a fee step only shows up as a counterfactual, so the reports you trust cannot show you this one.
MISCONCEPTION:    Amazon's fees creep up a little as a product gets heavier or pricier. Small change, small difference.
RUNTIME:          about 3 min

HOOKS (three, pick one)
1. {{step_np}} a unit. That's what one real listing pays, on every sale, for sitting {{over}} past an edge on Amazon's fee card. Its P&L will never show it. Here's why, and here's the arithmetic.
2. {{leak_p10}} to {{leak_p90}} a year. That's what one listing pays on a single step of Amazon's fee staircase, for a fraction of an ounce. Nobody around it is running the math.
3. {{weight}}. That's the published weight of the listing in this film, and it sits a fraction of an ounce past an edge on Amazon's card. Your cost model is a line. Amazon's is a staircase.

SCRIPT
[0:00] HOOK
  VO: {{step_np}} a unit. That's what one real listing pays, on every sale, for sitting {{over}} past an edge on Amazon's fee card. Its P&L will never show it. Here's why, and here's the arithmetic.
  VISUAL: number: {{step_np}} lands alone, then the words "a unit, on every sale"
  CLIP: yes

[0:15] THE STAIRCASE
  VO: Most of us carry a mental model of cost that's a line. Heavier costs a little more. Pricier costs a little more. A small change makes a small difference. Amazon's fulfilment fee isn't a line. It's a staircase. It's flat for a stretch, then it steps, then it's flat again. Inside a step, another ounce costs nothing. Across an edge, the next ounce costs the whole step, on every unit, every month, until something moves.
  VISUAL: kinetic: "Your mental model is linear." then "Amazon's cost structure is a staircase."
  CLIP: yes

[0:45] WHERE THIS LISTING SITS
  VO: This is a real listing, modeled from its public page and nothing else: {{who}}'s best-selling paint scratch remover, in {{category}}. Its page lists an item weight of {{weight}}. The edge on the card is at {{edge}}. So every unit it ships pays the next step up.
  VISUAL: number: the published weight in ink, then where the edge is
  DATA SOURCE: the public-data case study, modeled from public data
  CLIP: yes

[1:05] THE COUNTERFACTUAL
  VO: Now the same listing, one step the other way. It would pay {{step_np}} less a unit, and {{step_peak}} less from {{peak_from}}, when Amazon's holiday card takes over. No report shows you that, because the lighter version never shipped. A P&L is an average. A cliff is only visible as a counterfactual. On roughly {{units}} units a month, that one step is worth {{leak_p10}} to {{leak_p90}} a year.
  VISUAL: staircase: the hollow dot one step down, the riser between the two in blue, the yearly range beneath
  DATA SOURCE: the public-data case study, modeled from public data
  CLIP: yes

[1:35] TEN THOUSAND YEARS
  VO: That's a range, not a number, on purpose. Volume read from a public sales rank can be off by a long way in either direction. So we didn't take one guess. We ran this listing's year {{years}} times, with volume and cost moving the way they really move, and read the spread. Each faint line is one of those years. The band is where most of them land, the bad end included. Months at a loss, before ads, storage and returns: {{months_losing}} of {{months_total}}.
  VISUAL: montecarlo: the paths fan out from today, settle to almost nothing, then the band fills
  DATA SOURCE: the public-data case study, modeled from public data
  CLIP: yes

[2:00] THE CLIFF, AND THE GAP
  VO: There's a bigger step that no public page can show. Once a unit has sat {{cliff_day}} days in Amazon's warehouse, its storage surcharge goes from {{aged_before}} to {{aged_after}} a cubic foot, overnight. How close this brand's stock sits to that line, its page doesn't say. It doesn't show ads, either, or returns. That's the gap, and only your own exports close it.
  VISUAL: aging: storage plus the surcharge by age, the day-271 riser in blue
  DATA SOURCE: Amazon's published storage schedule, on the case-study unit's size, modeled from public data
  CLIP: no

[2:25] WHAT THIS IS
  VO: We picked this listing because it had a finding. Of {{brands_modeled}} Amazon brands we've modeled from public pages, {{brands_silent}} showed nothing worth fixing, and we say so. On a call, we look at your own numbers with you, and if the arithmetic doesn't clear our fee at your size, we tell you that too.
  VISUAL: number: {{brands_silent}} of {{brands_modeled}}, the words "nothing worth fixing" beneath
  CLIP: no

[2:45] THE CLOSE
  VO: You can build this yourself. If you're doing real volume and want it run with rigor, this is what I do, and I only get paid when it works.
  VISUAL: kinetic: the two ways out, the call and the course, the call first
  CTA: Book the call. Not ready yet? The whole method is free at hubricon.com/learn.
  CLIP: no

RE-HOOK AUDIT: 0:00, 0:15, 0:45, 1:05, 1:35, 2:00, 2:25, 2:45
DERIVED ASSETS: the home page's one film, in the proof block under the offer (assets/home.js VIDEO) · Shorts and Reels cut at 0:00, 0:45, 1:05 and 1:35, each ending on hubricon.com/learn · every frame carries "Modeled from public data · Not a client · Not a result"
