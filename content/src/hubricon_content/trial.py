"""The visual trial (VISUAL_SPEC.md §12, phase 5): one shot of every style in the
library, silent, on the demo catalogue's figures, rendered by the same code as a
film. The founder watches it (beside one Nic Munoz episode) before the look is
locked; until then nothing long renders for publishing.

`hubricon-content visual-trial` writes content/videos/visual-trial/: a plan and a
timing built from TRIAL below (each shot's words read at 150 words a minute and
held for the style's length), the clips, trial.mp4 and qa/contact.jpg. Pictures
come from content/assets/trial.json, which maps each style to sourced files; a
style with no file there is drawn on a labelled placeholder ("no asset yet")
rather than a fake.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import render_shots, shots, timing
from .state import CONTENT_DIR

SLUG = "visual-trial"
DIR = CONTENT_DIR / "videos" / SLUG
ASSETS = CONTENT_DIR / "assets" / "trial.json"
SOURCE_UNIT = CONTENT_DIR / "videos" / "05-cash-conversion-cycle"

# (style, seconds, the words under the shot, extras). The words come from the approved V05
# script, so every figure is one the demo catalogue's run produced.
TRIAL = [
    ("chapter", 2.5, "", {"params": {"title": "The visual trial"}}),
    ("footage-establish", 8, "Goods leave a warehouse long before the money comes back.", {}),
    ("footage-process", 4, "The wire leaves for the supplier,", {"params": {"group": "trial", "step": "wide"}}),
    ("footage-process", 4, "the container crosses the ocean,", {"params": {"group": "trial", "step": "medium"}}),
    ("footage-process", 4, "and the cartons land on the shelf.", {"params": {"group": "trial", "step": "detail"}}),
    ("footage-insert", 4, "A tape gun seals the last carton.", {"on": "carton."}),
    ("footage-observe", 11, "For that long the money is gone and there's nothing new to sell, and the bank balance waits on dates the P&L does not carry.", {}),
    ("still-push", 8, "A bank counter, where the balance is supposed to follow the books.", {"overlay": {"credit": "Library of Congress"}}),
    ("still-pan", 9, "Rows of ledgers, a long window in which the books and the bank agree.", {"motion": "pan-right"}),
    ("still-reveal", 9, "One price tag, and then the shelf of ten thousand it belongs to.", {"on": "shelf"}),
    ("archive-framed", 8, "This is what a mail-order catalogue looked like then.", {}),
    ("archive-stack", 9, "One catalogue, then another, then a third, each one a promise of goods.", {"on": "third,", "params": {"focus_index": 2}}),
    ("split-then-now", 9, "The catalogue then, and the warehouse that ships it today.", {"on": "today."}),
    ("texture", 8, "A cone drawn too narrow tells you you're safe.", {"overlay": {"illustration": True}}),
    ("doc-highlight", 9, "The platform holds the sale for a {{payout_cycle}} cycle before it pays you.", {"on": "{{payout_cycle}}",
        "params": {"lines": ["Payouts", "Sales are held for a {{payout_cycle}} cycle before payout.", "Payouts arrive in the bank on the next business day."],
                   "line": 2, "source": "The demo catalogue's payout schedule · Tarnhollow demo data"}}),
    ("doc-clipping", 8, "It was news, on this date, that the catalogue shipped.", {"on": "shipped.", "params": {"clipping": True,
        "lines": ["The catalogue shipped to every county."], "line": 1, "source": "A placeholder clipping until the archive is sourced"}}),
    ("table-scan", 10, "The largest, {{largest_wire}}, for {{largest_wire_sku}}, leaves on day {{largest_wire_day}}.", {"on": "{{largest_wire}}",
        "params": {"heading": "The wire schedule", "columns": ["SKU", "Day", "Amount"],
                   "rows": [["{{largest_wire_sku}}", "{{largest_wire_day}}", "{{largest_wire}}"]], "row": 1, "cell": 3,
                   "source": "Tarnhollow demo data, the cash horizon"}}),
    ("receipt", 8, "How Hubricon counts a dollar: the move, how we know, called before, measured after.", {"params": {
        "heading": "How a dollar is counted", "rows": [{"move": "Overstocked orders trimmed to the economic quantity",
        "why": "A miss stays at what it earned", "how": "Isolated", "before": "{{nv_bleed_month}}", "after": "{{nv_bleed_month}}",
        "counts": "{{nv_bleed_month}}"}], "total": "{{nv_bleed_month}}"}}),
    ("number-land", 7, "Stock past its economic quantity costs {{nv_bleed_month}} a month to hold.", {"on": "{{nv_bleed_month}}"}),
    ("number-pair", 9, "{{cash_on_hand}} on hand today, against {{wires_total}} of wires already scheduled.", {"on": "{{wires_total}}",
        "params": {"question": "Cash on hand against the wires already scheduled", "gap": "More going out than is in the bank, on a profitable business."}}),
    ("unit-grid", 8, "Of {{nv_skus}} products, {{nv_skus_below_95}} want a lower service level than the flat default.", {"on": "{{nv_skus_below_95}}",
        "params": {"heading": "Products that want less than the flat default", "total": "{{nv_skus}}", "filled": "{{nv_skus_below_95}}",
                   "caption": "One dot per product in the demo catalogue."}}),
    ("chart-build", 12, "Revenue last month was {{rev_latest}}, and {{net_latest}} of it was true net profit.", {"on": "{{net_latest}}", "chart": {"scene": "waterfall"}}),
    ("match-bridge", 5, "A staircase in a building, and then Amazon's fee staircase.", {"params": {"bridge": {"to": "s024", "shape": "steps"}}}),
    ("counterfactual", 10, "Less than an ounce past the edge, paid on every unit.", {"on": "edge,", "chart": {"scene": "staircase"},
        "params": {"heading": "Less than an ounce past the edge. Paid on every unit."}, "label": "proof"}),
    ("range-band", 10, "Ten thousand versions of the next ninety days, and the band holds eight in ten.", {"on": "band", "chart": {"scene": "cash_cone"}}),
    ("timeline", 10, "Wire, then lead time, then shelf, then payout.", {"params": {"heading": "Four clocks in a row",
        "events": [{"date": "Day 0", "label": "the wire", "at": 0.3}, {"date": "{{lead_time_typical}}", "label": "the goods land", "at": 1.2},
                   {"date": "", "label": "the shelf", "at": 2.0}, {"date": "{{payout_cycle}}", "label": "the payout", "at": 2.8}]}}),
    ("bars-recall", 4, "The wire and the payout, side by side.", {"params": {"layout": "bars",
        "events": [{"date": "the wire", "label": "{{lead_time_typical}}", "at": 0.0}, {"date": "the payout", "label": "{{payout_cycle}}", "at": 0.0}]}}),
    ("formula-build", 8, "Wire, plus lead time, plus shelf, plus payout, is the cycle.", {"params": {"terms": [
        {"text": "wire", "at": 0.1}, {"text": "lead time", "at": 0.8}, {"text": "shelf", "at": 1.6}, {"text": "payout", "at": 2.2},
        {"text": "the cycle", "at": 3.0}], "ops": ["+", "+", "+", "="], "caption": "The days between a dollar leaving and coming back."}}),
    ("kinetic-thesis", 6, "The P&L has no calendar.", {}),
    ("quote", 7, "The P&L has no calendar.", {"params": {"text": "The P&L has no calendar.", "attribution": "From the V05 script, 2026"}}),
    ("breath", 2, "", {"room": "world", "kind": "footage"}),
    ("callback", 8, "The same cone, now with the trough marked.", {"on": "trough", "params": {"callback": "s025"}, "chart": {"scene": "cash_cone"}}),
    ("end", 6, "", {}),
]
TRIAL_WORDS = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
STOCK, ARCHIVAL = ["pexels", "pixabay"], ["loc", "smithsonian", "commons"]
# What each sourced trial shot asks the libraries for: the concrete nouns of its words (§6.1).
QUERIES = {
    "footage-establish": (["warehouse loading dock trucks daylight wide"], STOCK),
    "s003": (["container ship port cranes wide"], STOCK),
    "s004": (["shipping container truck loading"], STOCK),
    "s005": (["cardboard boxes conveyor belt close up"], STOCK),
    "footage-insert": (["tape gun sealing cardboard box close up"], STOCK),
    "footage-observe": (["warehouse conveyor belt boxes moving static"], STOCK),
    "still-push": (["bank teller window interior"], ARCHIVAL),
    "still-pan": (["library book stacks interior"], ARCHIVAL),
    "still-reveal": (["general store shelves interior"], ARCHIVAL),
    "archive-framed": (["mail order catalog"], ARCHIVAL),
    "archive-stack": (["catalog cover"], ARCHIVAL),
    "split-then-now": (["mail order warehouse", "warehouse shelves boxes"], ARCHIVAL + STOCK),
    "match-bridge": (["concrete staircase steps building"], STOCK),
    "breath": (["rain loading dock static"], STOCK),
    "texture": (["paper ledger pages still life"], ["higgsfield"]),
}


def _assets() -> dict:
    try:
        return json.loads(ASSETS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build() -> tuple[dict, dict]:
    """The trial's plan and timing: each shot a beat of its own, its words read at
    150 wpm from the shot's start, then held to the style's length."""
    facts = json.loads((SOURCE_UNIT / "facts.json").read_text(encoding="utf-8"))
    reg = shots.registry()
    assets = _assets()
    segments, plan, t = [], [], 0.0
    for n, (style, secs, words, extra) in enumerate(TRIAL, 1):
        st = reg["styles"][style]
        text = TRIAL_WORDS.sub(lambda m: str(facts[m.group(1)]["value"]), words)
        spoken, _ = timing.estimate_words(text)
        spoken = [{**w, "start": round(t + 0.2 + w["start"], 3), "end": round(t + 0.2 + w["end"], 3)} for w in spoken]
        # every figure in the words is revealed at its first word
        reveals, cursor = [], 0
        for m in TRIAL_WORDS.finditer(words):
            first = str(facts[m.group(1)]["value"]).split()[0]
            hit = next((i for i in range(cursor, len(spoken)) if spoken[i]["word"].rstrip(".,;:") == first.rstrip(".,;:")), None)
            if hit is not None:
                reveals.append({"key": m.group(1), "t": spoken[hit]["start"]})
                cursor = hit + 1
        kind = "card" if style == "chapter" else "beat"
        seg = {"kind": kind, "index": n, "start": round(t, 3), "end": round(t + secs, 3), "words": spoken,
               "spoken": [{**r, "value": facts[r["key"]]["value"]} for r in reveals], "reveals": {}}
        if kind == "card":
            seg["title"] = extra.get("params", {}).get("title", "")
        segments.append(seg)
        on = extra.get("on")
        shot = {"id": f"s{n:03d}", "start": round(t, 3), "end": round(t + secs, 3), "style": style,
                "room": extra.get("room") or (st["room"] if st["room"] != "either" else "paper"),
                "kind": extra.get("kind") or st["kinds"][0], "on": on, "params": dict(extra.get("params") or {}),
                "overlay": dict(extra.get("overlay") or {}), "chart": extra.get("chart"), "says": text,
                "reveals": reveals if st["room"] == "paper" or style == "callback" else [],
                "label": extra.get("label") or ("demo" if reveals or st["group"] == "charts" else None),
                "focus": extra.get("focus", [0.5, 0.5]), "motion": extra.get("motion") or {"still-push": "push", "still-reveal": "reveal",
                                                                                          "texture": "drift"}.get(style),
                "intent": f"the trial's {style}"}
        q = QUERIES.get(shot["id"]) or QUERIES.get(style)
        if q:
            shot["query"], shot["sources"], shot["fallback"] = q[0], q[1], "paper:kinetic"
        a = assets.get(shot["id"]) or assets.get(style)
        if a:
            shot["asset"] = a.get("asset")
            if "right" in a:
                shot["params"]["right"] = a["right"]
        plan.append(shot)
        t += secs
    tm = {"slug": SLUG, "duration": round(t, 3), "segments": segments, "chapters": [], "clips": [], "estimated": False,
          "trial": True, "cutpoints": timing.cutpoints(segments), "fps": 30, "width": 1920, "height": 1080}
    return {"slug": SLUG, "mode": "explainer", "fps": 30, "shots": plan}, tm


def missing_assets(plan: dict) -> list[str]:
    need = {"footage", "still", "texture", "archive", "stack", "split"}
    return [s["style"] for s in plan["shots"] if s["kind"] in need and not s.get("asset")]


def placeholder(style: str) -> dict:
    """A labelled card where a picture belongs but none exists yet: better than a fake."""
    from PIL import Image, ImageDraw, ImageFont
    from . import tokens
    out = CONTENT_DIR / ".cache" / "trial" / f"placeholder-{style}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (2400, 1350), tokens.rgb("paper_2"))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(tokens.font_file(600)), 72)
    small = ImageFont.truetype(str(tokens.font_file(400)), 48)
    draw.text((160, 560), f"No picture yet: {style}", font=font, fill=tokens.rgb("ink"))
    note = "made by the runner through Higgsfield" if style == "texture" else "the pick has not chosen one"
    draw.text((160, 680), note, font=small, fill=tokens.rgb("ink_3"))
    img.save(out)
    return {"id": f"placeholder:{style}", "file": str(out), "source": "placeholder"}


def write() -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    plan, tm = build()
    old = {}
    if (DIR / "shots.json").exists():
        old = {s["id"]: s for s in json.loads((DIR / "shots.json").read_text(encoding="utf-8"))["shots"]}
    for s in plan["shots"]:
        prev = old.get(s["id"])
        if prev and prev.get("style") == s["style"] and prev.get("asset") and not str((prev["asset"] if isinstance(prev["asset"], dict) else {}).get("id", "")).startswith("placeholder:"):
            for k in ("asset", "focus", "motion"):
                if prev.get(k) is not None:
                    s[k] = prev[k]
            if (prev.get("params") or {}).get("right"):
                s["params"]["right"] = prev["params"]["right"]
        if s["kind"] == "texture" and not s.get("asset"):
            s["asset"] = placeholder("texture")
    for name in ("facts.json", "run.json"):
        (DIR / name).write_text((SOURCE_UNIT / name).read_text(encoding="utf-8"), encoding="utf-8")
    (DIR / "shots.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (DIR / "timing.json").write_text(json.dumps(tm, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"shots": len(plan["shots"]), "seconds": tm["duration"], "missing_assets": missing_assets(plan)}


def concat(slug_dir: Path, plan: dict, out: Path) -> Path:
    """The clips joined in order, re-encoded once (the master's settings, §8.5)."""
    from . import grade
    lst = slug_dir / "shots" / "concat.txt"
    lst.write_text("".join(f"file '{(slug_dir / 'shots' / (s['id'] + '.mp4')).resolve()}'\n" for s in plan["shots"]), encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-r", "30",
                    *grade.encode_args("master"), "-movflags", "+faststart", "-an", str(out)], check=True, timeout=7200)
    return out


def contact(slug_dir: Path, plan: dict, out: Path, across: int = 6) -> Path:
    """qa/contact.jpg: one frame per shot at its middle, labelled with id and style (§10)."""
    from PIL import Image, ImageDraw, ImageFont
    from . import tokens
    W, H, pad, cap = 480, 270, 10, 30
    rows = (len(plan["shots"]) + across - 1) // across
    sheet = Image.new("RGB", (across * (W + pad) + pad, rows * (H + cap + pad) + pad), tokens.rgb("paper_2"))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(tokens.font_file(400, display=False)), 18)
    for i, s in enumerate(plan["shots"]):
        clip = slug_dir / "shots" / f"{s['id']}.mp4"
        mid = (float(s["end"]) - float(s["start"])) / 2
        frame = slug_dir / "qa" / f"{s['id']}.jpg"
        frame.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{mid:.2f}", "-i", str(clip), "-frames:v", "1", "-vf",
                        f"scale={W}:{H}", str(frame)], check=True, timeout=120)
        x, y = pad + (i % across) * (W + pad), pad + (i // across) * (H + cap + pad)
        with Image.open(frame) as im:
            sheet.paste(im.convert("RGB"), (x, y))
        draw.text((x, y + H + 6), f"{s['id']} · {s['style']}", font=font, fill=tokens.rgb("ink_2"))
        frame.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return out


def run(workers: int | None = None, force: bool = False) -> dict:
    info = write()
    plan = json.loads((DIR / "shots.json").read_text(encoding="utf-8"))
    if info["missing_assets"]:
        return {"status": "blocked", "reason": f"no trial asset for: {', '.join(sorted(set(info['missing_assets'])))} "
                                                f"(content/assets/trial.json)", **info}
    res = render_shots.render({"slug": SLUG}, force=force, workers=workers)
    film = concat(DIR, plan, DIR / "trial.mp4")
    sheet = contact(DIR, plan, DIR / "qa" / "contact.jpg")
    return {**res, **info, "film": str(film), "contact": str(sheet)}
