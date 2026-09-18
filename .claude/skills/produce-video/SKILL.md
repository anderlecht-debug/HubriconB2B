---
name: produce-video
description: Run exactly one step of one video unit in the Hubricon pipeline (facts → script → critique → review → tts → timing → scenes → assemble → qa → thumbnail → describe → shorts → approve_final → upload), with the pass criteria for each.
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

Rules: never skip a gate; never call `tts` on a unit whose `review` is not `approved`; never call
`upload` on a unit whose `approve_final` is not `approved` or whose `voice` is `placeholder`.
Read `docs/content/hubricon-video-production-bible.md` before `scenes` and `assemble` the first
time in a session.
