# Recording the films in your own voice

Every film is narrated by you, in your own recorded voice (your call, 2026-10-06: no ElevenLabs,
no clone). The description of every film says so: "Narrated by Hagen Simmons, in his own voice."
Nothing on the voice side needs a paid service: the teleprompter records you, and faster-whisper,
running on this PC, matches your reading to the script's words so the pictures land on them.

## The time it takes

A film is read at about 150 words a minute, so a 30-minute film is about 30 minutes of reading and
roughly an hour at the microphone once retakes are counted. Retakes are cheap: you re-record one beat,
never the whole film. Three films on a Saturday covers half a week of one a day.

## The setup

- One microphone, the same one every time, 15 to 20 cm from your mouth, slightly off-axis so
  plosives don't pop. A USB condenser or a decent dynamic is fine; a laptop mic is not.
- A quiet room with soft surfaces. A closet full of clothes beats a kitchen. Fans, fridges and
  HVAC off. Phone on silent and out of the room.
- No noise reduction, no EQ, no compression, no normalising. The teleprompter already turns off the
  browser's echo cancellation, noise suppression and automatic gain, records at 256 kbps, and keeps
  each beat as a 48 kHz mono WAV; the mix does the rest (−16 LUFS, a light compressor, room tone).
- Leave a second of silence before you start each beat. Do not trim it.

## Reading a film

A script can be read only once you have approved it (`hubricon-content approve <slug>`); the
teleprompter refuses to keep takes for one that isn't.

    cd /home/lp9/Hubricon/HubriconB2B-content
    node content/film/record.mjs <slug>

Open the address it prints. It shows one beat at a time with its figures filled in; read it, listen
back, keep it or take it again. Each kept beat lands in `content/videos/<slug>/takes/b<N>.wav`.
When every beat has a take, the next runner tick turns them into the film's narration
(`hubricon-content tts <slug>`, which calls `takes-to-vo`): the takes are copied, never altered,
and timed word by word. A unit waiting on your reading goes back to work on its own once the
takes are in.

## How to read

As you would explain it to one founder across a table, not as a broadcaster. Slightly slower than
conversation, full stops honoured, no performance. Read figures in full and the same way every time:
"$65,320" as "sixty-five thousand, three hundred and twenty dollars", percentages as "seven percent",
and dates as they are written. The subtitles show the script's own words whatever the transcriber
hears, but a figure read differently from the screen is a mistake a viewer will notice.

## Sound around your voice

The tick, the whoosh, the music bed and the world ambience already on file were made with ElevenLabs
during your paid subscription, which licenses them for commercial use for good; they stay. Any new
sound comes from Freesound under its CC0 licence or from Pixabay, filed with its page and licence:

    .venv/bin/hubricon-content ambience-add <file> --subject "container port cranes" \
        --source freesound --url https://freesound.org/people/<who>/sounds/<id>/ --author <who>

A subject with no clip on file plays room tone alone.
