---
name: produce-video
description: Run exactly one step of one video unit in the Hubricon pipeline (facts → script → critique → review → tts → timing → scenes → assemble → qa → thumbnail → describe → shorts → approve_final → upload; tier D adds shots → source → pick → render_shots), with the pass criteria for each.
---

# produce-video

Input: `unit` and `step` from `hubricon-content next`. Do only that step, then return to the
caller, which marks it and commits. Every command below is idempotent; re-running a step after
a crash is safe.

| step | command | produces | passes when |
|---|---|---|---|
| facts | `hubricon-content facts <slug>` | `facts.json`, `run.json`, `provenance.json` | exit 0; every key has a value, label and source |
| script | invoke the `script-draft` skill | `script.md` | `hubricon-content script-validate <slug>` prints no problems |
| critique | invoke `critique script <slug>` | `critique.json` | `"pass": true`; otherwise revise via `script-draft` (reads the notes) |
| review | `hubricon-content review <slug>` | `REVIEW.md` block, notification | the command reports `awaiting`; STOP. Do not proceed to tts. The founder runs `approve`/`reject`. |
| tts | `hubricon-content tts <slug>` | `audio/vo-NN.*`, `alignment/*.json`, `voice` recorded | exit 0. If it reports `blocked`, mark blocked with its message (key or clone missing). Placeholder voice sets `publishable: false`. |
| timing | `hubricon-content timing <slug>` | `timing.json` | every beat has bounds; every `{{key}}` has a reveal time |
| scenes | `hubricon-content render-scenes <slug>` | `scenes/*.mp4`, `events.json` | exit 0; requires `style_locked` unless the unit is V01 |
| assemble | `hubricon-content assemble <slug>` | `media/master.mp4` | exit 0 |
| qa | `hubricon-content qa <slug>` then invoke `critique render <slug>` | `qa.json`, `frames/`, `qa.review.json` | both pass. After V01 passes: `hubricon-content style-lock <slug>` writes `docs/content/STYLE-LOCK.md` and `content/assets/style-lock.json`. |
| thumbnail | `hubricon-content thumbnail <slug>` | `thumbnail.png` | one fact value, one chart fragment, no face |
| describe | `hubricon-content describe <slug>` | `description.md` | disclosure line present; number guard clean |
| shorts | `hubricon-content shorts <slug>` | `shorts/NN.mp4` (≤45 s, 9:16, own hook) | at least three |
| approve_final | `hubricon-content review <slug> --final` | `REVIEW.md` block | reports `awaiting`; STOP. The founder runs `approve-final`. |
| upload | `hubricon-content upload <slug>` | YouTube video id (unlisted, synthetic-media flag) | only when `publishable`; otherwise `blocked` with the missing input |

## Tier D: the long documentary films (20–50 minutes)

`docs/content/VISUAL_SPEC.md` governs every frame of a tier-D film; read §3, §4 and §14 before
any tier-D step in a session. Between `timing` and `assemble` the chain is (§7.2):

| step | command | produces | passes when |
|---|---|---|---|
| tts | `hubricon-content tts <slug>` (the clone) **or** `hubricon-content takes-to-vo <slug>` (the founder's own takes from `record.mjs`) | `audio/vo-NN.*`, `alignment/vo-NN.json` | both voices end in the same files, so everything after is one path |
| timing | `hubricon-content timing <slug>` | `timing.json` with `cutpoints` | as above |
| shots | invoke the `shot-plan` skill | `shots.json` | `hubricon-content shots-validate <slug>` prints no problems |
| source | `hubricon-content source <slug>` | `sources/<shot>.jpg`, `content/.cache/assets/…` | every world shot has three candidates after the filters, or its fallback |
| pick | invoke the `visual-pick` skill | `shots.json` with `asset`, `focus`, `motion` | `hubricon-content shots-validate <slug> --picked` prints no problems |
| render_shots | `hubricon-content render-shots <slug>` | `shots/<id>.mp4`, one per shot | every clip is exactly its shot's frame count; needs `visual_locked` |
| scenes | `hubricon-content render-scenes <slug>` | the Manim chart shots only | exit 0 |
| assemble | `hubricon-content assemble <slug>` | `media/master.mp4`, `media/captions.srt` (nothing burned) | exit 0 |

`next` never offers `source`, `pick` or `render_shots` while their tooling is being built
(`state.PENDING_D`), and never `render_shots` or `scenes` on a tier-D unit before the founder
approves the visual trial (`visual_locked`). A rejection at the final review sends a tier-D unit
back to `pick`.

Rules: never skip a gate; never call `tts` on a unit whose `review` is not `approved`; never call
`upload` on a unit whose `approve_final` is not `approved` or whose `voice` is `placeholder`.
Read `docs/content/hubricon-video-production-bible.md` before `scenes` and `assemble` the first
time in a session.
