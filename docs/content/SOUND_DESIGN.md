# Sound design: what keeps attention and makes a film feel premium

**Decided 2026-10-07 by the founder.** Sound is half the film. The engine
(`content/src/hubricon_content/sound.py`, called by `audio.mix`) turns the practice of the best
sound designers into rules with numbers. `film-qa` checks those numbers on every film, at no token
cost. Nobody has to know how to mix: the rules do it the same way every time.

## The principles, and the rule each became

| Principle | From | The rule in the engine | The number |
|---|---|---|---|
| **The voice is the spine.** Everything else serves its clarity. | Walter Murch | A full chain on the narration: rumble cut, gentle noise reduction, de-ess, a mud cut at 300 Hz, presence at 4.2 kHz, air at 10 kHz, a leveling compressor then a peak one, a limiter. A real voice gets no added room. | `sound.VOICE_CHAIN` |
| **Breaths are human; breath noise is not.** | dialogue editing practice | Every gap of 0.18 s or more between words is pulled down, on 20 ms ramps, never cut to silence. | −9 dB |
| **Carve, don't bury.** Music under speech loses the voice's frequencies, not its body. | mix engineering (sidechain EQ) | Under speech the bed's 250 Hz–5 kHz band drops hard, and its lows and highs only a little. | −12 / −4 dB |
| **Contrast makes impact.** The loudest moment is the silence before it. | Gary Rydstrom, Ben Burtt | The bed dips for the quarter second before each hero figure lands, then recovers. A thesis line opens on a breath of silence. | −7 dB, 0.25 s in, 0.6 s back |
| **Never the same sound twice.** Identical repeats read as a machine. | Ben Burtt | Every tick and paper landing gets its own pitch and level. | ±1.2 semitones, ±2 dB |
| **Two and a half at once.** An ear follows at most about two and a half layers. | Walter Murch, "the Law of Two-and-a-Half" | Transient effects within 0.35 s of each other are thinned by priority: riser > low hit > tick > room change > paper. A low hit under a tick is one designed hit. | 0.35 s |
| **Sound leads picture.** A place is heard before it's seen, and lingers after. | the J-cut and L-cut (Murch) | A footage shot's ambience starts before its cut and tails after. Paper foley leads its picture by three frames. | 0.5 s in, 0.35 s out, 0.1 s |
| **Every room has a tone.** True silence sounds like a fault. | production sound practice | Room tone runs under the whole film, levelled by its body. | −48 dB |
| **Music marks the structure.** | documentary scoring | Each chapter has its own cue from one family. The bed swells while a chapter card holds, with a riser into it and a low drop under it. The end card holds 4 s as the bed resolves to silence. | +8 dB swell |
| **Loud enough, never fatiguing.** | broadcast loudness | −16 LUFS integrated, true peak −2 dBTP before the encode (−1.5 after), a loudness range a documentary breathes in. | `film-qa` |

## What film-qa checks, for no tokens

| Check | Threshold |
|---|---|
| The voice over the music, under speech | at least 15 dB |
| Designed effects a minute (ticks, low hits, room changes, paper, risers) | 2 to 14: enough to keep attention, not so many they tire |
| The longest stretch with nothing designed under the voice | at most 60 s |
| Loudness range | 2–12 LU |
| Integrated loudness | −17 to −15 LUFS |
| True peak | at most −1.5 dBTP |

The mix writes its own numbers to `media/mix.json` (`measured`).

## When the founder records his own takes

The chain above is built for a real voice in a real room. To record:

1. Record in one quiet room, at the same distance from the mic each session, with `content/film/record.mjs`.
2. Run `hubricon-content takes-to-vo <slug>`. It sets the voice and its timing, and the mix applies the chain, the breath control and the carve automatically. Nothing else needs doing.

## Next, when worth it

- **A stereo field:** the voice in the centre, the music wide, foley panned toward where a print lands on screen.
- **Music edited to the picture's hit points:** a cue's downbeat on a chapter card, a sting on the thesis line. Today cues change on chapter bounds.
- **Per-subject ambience from a licensed library,** in place of generated beds where it sounds generic.
