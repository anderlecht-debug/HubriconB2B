"""Resolved shot jobs for style frames: what the v3 stage draws, for any shots of a film.
    FILM_LOOK=v3 python content/film/v3/export_jobs.py <slug> <ids,comma> <out.json>
Each job is exactly what render-shots hands the stage (figures filled, times relative to the
shot, stills graded), plus `stills`: the seconds to capture (a third in, two thirds, the end)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from hubricon_content import render_shots, shots, tokens  # noqa: E402
from hubricon_content import script as sm  # noqa: E402

slug, ids, out = sys.argv[1], sys.argv[2].split(","), Path(sys.argv[3])
d = sm.video_dir(slug)
tokens.refresh()
plan = json.loads((d / "shots.json").read_text(encoding="utf-8"))
timing, _ = shots.load_timing(d)
facts = sm.load_facts(slug)
jobs = []
for s in plan["shots"]:
    if s["id"] not in ids:
        continue
    job = render_shots.Job(s, plan, timing, facts, d)
    job.resolve_assets()
    j = dict(job.job)
    sec = j["seconds"]
    j["stills"] = [round(sec * f, 2) for f in (0.33, 0.66)] + [round(max(0, sec - 0.2), 2)]
    jobs.append(j)
out.write_text(json.dumps(jobs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(jobs)} jobs → {out}")
