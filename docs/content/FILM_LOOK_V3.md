# Film look v3: "the archive at night"

**The founder's call, 2026-10-06**, after watching the first full Greats draft (G01, Sears):
"The white with the Hubricon branding at the bottom, that's not what we're trying to do… the
graphics… are just terrible, low quality AI slop… the typography is bad… the way the whole video
kind of flows is just not high quality… go through the video with the lens of someone that makes
hundreds upon hundreds of thousands of dollars just making high quality videos and editing… it
should stun me." The photographs and footage, and the script, stay as they are.

This replaces VISUAL_SPEC.md §3's paper room ("the site's charts and documents on white") for
long films. The honesty rules do not move: every figure still comes from facts.json, every proof
figure still carries "Modeled from public data · Not a client · Not a result", every demo figure
still says it is demo data, nothing on screen says more than the narration and the sources do.
Blue is still for money and the leak, nothing else. The site does not change.

## The idea

The paper room becomes **a dark reading room in an archive at night**. One warm key light falls from
the upper left onto a near-black desk and dies into the frame's edges. On that desk:

- **Sources are physical objects.** The 1913 Act, the 1914 guidebook, a catalogue page, the Joint
  Committee's report are aged pages: ivory stock with fibre and foxing, set in period type (Old
  Standard for print, Special Elite for typed records), lit by the key light, casting a soft long
  shadow down and to the right, tilted a few degrees in 3D. The camera drifts over them and pushes
  into the line that matters, and a highlighter swipes across it on the spoken word.
- **Photographs are prints.** A framed archival photograph is a print with a white border lying on
  the desk, or pinned up, with a shadow and a little rotation; a stack is several prints landing on
  each other; a then-and-now is two prints side by side. They move in depth, not as flat cards.
- **Data is light.** Figures, timelines, formulas, charts are drawn as light on the dark: crisp
  ivory type, thin precise rules, the money glowing blue. Lines draw themselves on; numbers count
  up and land with weight; nothing just appears.

The world room (full-frame archival photographs and present-day footage) stays as it is: the
founder likes it. Its photographs may gain the same subtle film character (grain, a faint gate
weave, the vignette), never a heavy filter.

## The reference bar

Think of the best-produced documentary channels on YouTube (Nic Muñoz, Johnny Harris, Magnates
Media, the produced segments of The Diary of a CEO, Wendover, ColdFusion) and the editors paid six
figures to cut them. What they share, and what every shot here must have:

1. **Depth.** Foreground, subject and background; light falling across objects; shadows that agree
   with the light; a camera that moves through space (3D perspective), never a flat card sliding.
2. **Constant intentional motion.** Something is always moving, and every move means something: a
   push into the line being read, a print settling as its date is spoken, a line drawing toward the
   figure that lands on the word. Never a generic fade-up, never a frozen frame.
3. **Typographic hierarchy with character.** Big where it matters (a hero figure at 220 px or more),
   small and tracked where it labels. A display serif (Fraunces, optical sizes) for words with
   weight; Inter for figures and labels; Instrument Serif italic for quotations; period faces only on
   period documents. Never more than two sizes of the same weight fighting in a frame.
4. **Restraint in colour.** Ivory light, warm greys, aged paper, near-black. Amber only for the
   highlighter. Blue only for money and the leak, and it glows. Nothing else is coloured.
5. **Composition.** Strong asymmetric layouts on a grid, generous negative space that is *dark*,
   one focal point per frame, title-safe margins (160 px sides, 90 px top and bottom).
6. **Texture and finish.** Paper fibre, film grain (the encoder adds it), the vignette, a faint warm
   to cool grade. Clean, never dirty; premium, never "vintage filter".
7. **Readable on a phone.** Body text at least 36 px at 1080p, labels at least 26 px, a figure that
   lands reads at a glance.

What it must never look like: a slide; a dashboard; a template; a stock chart; neon; glassmorphism;
gradients for their own sake; emoji; drop shadows that disagree with the light; text typed in
modern sans on a "document"; a logo in the corner.

## The system (content/film/v3/)

- `stage.html`, `fonts.css`, `base.css`: the desk (`/content/assets/film/desk.jpg`), the key light
  (`.key`), the grade and vignette, the camera (`.cam > .rig`, a 3D rig that moves from `--cam-from`
  to `--cam-to` over `--cam-dur`), shared entrances (`.rise`, `.fade`), `.money`, the honesty
  label. Tokens: `--light`, `--light-2`, `--light-3`, `--paper`, `--paper-ink`, `--paper-ink-2`,
  `--marker`, `--blue`, `--blue-glow`, `--serif`, `--quote`, `--sans`, `--period`, `--typed`,
  `--safe-x`, `--safe-y`.
- `clock.js`: per-frame behaviours the renderer drives (`window.__seek(t)`): `data-count` count-ups
  (the element's own text is the exact final figure), `data-type-at` typewriter text,
  `data-flicker`. CSS animations are stepped frame by frame too, so any keyframes work.
- `textures.py`: the paper, desk and dust textures, made by code.
- `kinds/documents`, `kinds/photos`, `kinds/type`, `kinds/charts` (`.mjs` + `.css`): each kind.
- `export_jobs.py` + `frames.mjs`: style frames and motion tests of any shot of a film.

Times in a job are seconds from the shot's first frame: `on` (the word the style's main event lands
on), each `reveals[i].t` (when a figure is spoken), `params.*.at`. Land things on those times.
