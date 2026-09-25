# The premium standard

Everything Hubricon puts in front of a founder has to read as expensive and certain. This
document says what that means for the videos and the pages, and it is the checklist the
`critique` skill runs before anything reaches the founder's review. It sits beside the
production bible; where they differ, this is stricter.

## Where the standard comes from

High-ticket B2B and financial publishers earn the look the same way: by removal. The pattern
across the references is consistent enough to state as rules.

- Premium is restraint: two or three colours used with absolute intention, at most two
  typefaces, generous spacing, and one strong visual per section doing the work
  ([Snappy-Fix](https://www.snappy-fix.com/blog/branding-that-feels-premium),
  [Zamora Design](https://zamora.design/10-things-that-make-your-design-look-premium/),
  [Hooman](https://hooman.com/blogs/what-make-websites-expensive)).
- Whitespace signals "nothing to prove"; it lowers decision fatigue and builds trust before a
  word is read ([Sophisticated Cloud](https://www.sophisticatedcloud.com/all-blogs/8-web-design-practices-that-make-brands-look-premium),
  [Webwavers](https://webwavers.de/en/blog/website-design-elemente-premium)).
- Editorial typography: a serif with authority for headlines, one quiet face for data, weight
  contrast rather than colour contrast ([Techelix on editorial UI](https://studio.techelix.co/the-art-of-editorial-ui-leveraging-typography-and-whitespace-for-luxury-brands-ui/),
  the Financial Times' Financier commission ([Eye on Design](https://eyeondesign.aiga.org/new-financier-font-gives-the-financial-times-a-smart-luxurious-update/),
  [Klim](https://klim.co.nz/in-use/financial-times/))).
- Charts are chosen by the question they answer and drawn without decoration: direct labels,
  no legends, no 3D, no gradients (the FT's [Visual Vocabulary](https://fountn.design/resource/financial-times-visual-vocabulary/)).
- Motion is subtle and purposeful; flashy animation reads as cheap
  ([OG Blocks](https://ogblocks.dev/blog/how-to-make-your-website-look-premium)).

Hubricon already has the raw material: navy, one amber, Fraunces, a mono for data, and the
rule that every number is real. The standard is about discipline in using them.

## The rules for the videos

**Colour.** Navy ground. Ink for everything that is not the point. One amber element per frame:
the figure being spoken, or the highlighted path, never both. Green and red only where they
mean profit and loss; never as decoration. No gradients, glows, halos or vignettes. Grain
stays subtle.

**Type.** Fraunces for the number and the chapter title. JetBrains Mono, small and dim, for
axes, captions and the demo label. No third face. No more than three text blocks on screen at
once; a frame that needs a fourth needs a cut.

**Charts.** Axes hairline, few ticks, direct labels, no legend, no grid. Build in three beats:
axes, data, annotation. Bands at low opacity. The demo label is always present and always small.

**Motion.** Eased, never linear, except the slow push that keeps a still alive. Nothing bounces,
nothing spins, nothing wipes. Chapter cards are typographic: a hairline, the title, a short
amber rule. Hard cuts.

**Subtitles.** Small, light, sentence case as written in the script, thin outline, wide bottom
margin. They must never look like auto-captions.

**Sound.** The founder's own voice, per paragraph, with continuity between paragraphs. Room tone
under everything. A tick that sounds like a fingertip on a desk, not a beep. A bed that is felt
rather than heard, ducked under speech, sparse piano and low strings, no melody. No synthesised
drone ships.

**Voice.** Only the founder's clone renders. Instant clone for the first videos; the
professional clone before the series is public. No stock voice is ever heard by a viewer,
and the placeholder exists only to prove the machinery. Disclose the clone in every description.

**Pace.** State the figure, hold it, move on. A premium explainer is not slow, but it is never
in a hurry: no jump-cut chatter, no fast zooms, no on-screen text racing the narration.

## The rules for the pages

One CTA. "Free" at most twice. No countdowns, badges of urgency or fake counts. Line length
around sixty characters. Section padding generous enough that each section is one thought.
Numbers in tables, not prose. Nothing that claims a client, a result or a testimonial that does
not exist; the sample tables say demo data.

## What the critique checks on a render

1. One amber element per frame in the sampled frames.
2. No gradient, glow or halo furniture; chapter cards are typographic.
3. At most three text blocks per frame; captions small and dim.
4. Charts have direct labels and a demo label, and no legend or grid.
5. Subtitles are light and small, never boxed or heavy-outlined.
6. Sound: `mix.json` shows `sfx_source` and `bed_source` from ElevenLabs or a licensed bed,
   not procedural, before a final sign-off.
7. Voice: `voice == founder`. Anything else fails the render critique by definition.
