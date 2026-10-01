# Recording your voice for the clone

The narration is the one thing on screen that has to be you. A clone made from bad audio
sounds like a bad clone; a clone made from five minutes of you reading calmly in a quiet room
sounds like you on a good day. Nothing else in the pipeline can compensate for the input.

## Two clones, in order

**Now: Instant Voice Clone.** Available on the current Starter tier. Give it 3 to 5 minutes and
it is good enough for the first videos and for judging the whole chain with your own voice.

**Before publishing the series: Professional Voice Clone.** Needs the Creator tier ($22/month at
the time of writing, which also raises the monthly character allowance to 100,000) and 30 minutes
or more of clean recording; ElevenLabs recommends up to 3 hours and trains for a few hours. This
is the one that is hard to tell from you. Record the 30 minutes over two or three sittings with
the same setup; the pipeline keeps working on the instant clone until you swap the voice id.

## The setup

- One microphone, the same one every time, 15 to 20 cm from your mouth, slightly off-axis so
  plosives don't pop. A USB condenser or a decent dynamic is fine; a laptop mic is not.
- A quiet room with soft surfaces. A closet with clothes beats a kitchen. Fans, fridges and
  HVAC off. Phone on silent and out of the room.
- Record WAV, 48 kHz, 24-bit, mono. No noise reduction, no EQ, no compression, no normalising.
  ElevenLabs wants the raw signal; processing removes what the model learns from.
- Leave two seconds of room silence at the start of every take. Do not trim it.

## What to read

Read as you would explain it to one founder across a table, not as a broadcaster. Slightly
slower than conversation, full stops honoured, no performance. The material below is what the
clone will be asked to say, so read that:

1. Two or three of the parked scripts in `content/REVIEW.md`, straight through. That is 10 to 15
   minutes of exactly the register we need: numbers, short sentences, one idea at a time.
2. A page of `HUBRICON.md`, so the clone has the product vocabulary.
3. For the professional clone, add a lesson or two from `content/learn/lessons/` and keep going
   until the total passes 30 minutes.

Numbers matter. Read "$65,320" as "sixty-five thousand, three hundred and twenty dollars" and
percentages as "seven percent". Consistency here is what makes the clone read figures well.

## Making the clone

Put the files in one folder, then:

    cd /home/lp9/Hubricon/HubriconB2B-content/content
    .venv/bin/hubricon-content voice-clone --name "Hagen Simmons" /path/to/take-*.wav

It prints a voice id. Add `ELEVENLABS_VOICE_ID=<id>` to `/home/lp9/Hubricon/HubriconB2B/.env`.
Then listen before anything renders:

    .venv/bin/hubricon-content voice-preview 01-survivorship-bias

That writes `content/voice-previews/<slug>-founder.mp3`: the hook and the first chapter in your
clone with the pipeline's exact settings. If it sounds off, adjust `ELEVENLABS_STABILITY`
(lower is more expressive, higher is steadier; 0.40 to 0.55 is the range for narration) and
`ELEVENLABS_STYLE` (keep under 0.15) in `.env` and preview again. The settings you settle on are
frozen into the style lock with the first video.

## Budget

A five-minute video is roughly 4,500 characters; a Desk video is about 8,500. The Starter tier's
40,000 characters a month covers roughly six videos with no retakes. The full calendar at one
video a day needs the Pro tier (500,000 characters) or a slower cadence.
