"""A synthetic narration and a clean shot plan over it, for the shot-plan tests.

The narration is one word every half second (w0, w1, …), each in the middle of
its half second, so a legal cut falls on every multiple of 0.5 s. The plan is a
600-second explainer that meets every rule in VISUAL_SPEC.md §4, §5, §7.4 and
§14.8; each test breaks one rule and expects the validator to say so."""

import copy

from hubricon_content import shots as shotmod

FACTS = {"leak": {"value": "$4,200", "source": "demo catalogue"},
         "share": {"value": "37%", "source": "demo catalogue"},
         "case_leak": {"value": "$6,400", "source": "public-data case study, estimate"}}

# (style, seconds, extras): a ten-minute explainer.
SEQUENCE = [
    ("footage-establish", 6), ("kinetic-thesis", 5), ("footage-insert", 4), ("number-land", 5, {"reveal": "leak"}),
    ("still-push", 6), ("doc-highlight", 6), ("footage-process", 4, {"step": "wide"}),
    ("footage-process", 4, {"step": "medium"}), ("footage-process", 4, {"step": "detail"}),
    ("number-pair", 6, {"reveal": "share"}), ("texture", 7), ("footage-insert", 4),
    ("chart-build", 28), ("chapter", 2.5), ("footage-establish", 8), ("table-scan", 10), ("counterfactual", 14),
    ("footage-observe", 12), ("range-band", 14), ("archive-framed", 10), ("chart-build", 28), ("footage-insert", 4),
    ("formula-build", 10), ("doc-highlight", 12), ("still-pan", 10), ("chart-build", 28), ("footage-establish", 8),
    ("number-land", 6), ("counterfactual", 14), ("texture", 8), ("chapter", 2.5), ("footage-establish", 8),
    ("chart-build", 24), ("kinetic-thesis", 6), ("footage-observe", 12), ("doc-highlight", 12), ("range-band", 14),
    ("footage-insert", 4), ("unit-grid", 10), ("table-scan", 12), ("counterfactual", 14), ("footage-establish", 8),
    ("archive-framed", 10), ("number-land", 8), ("range-band", 14), ("footage-observe", 12), ("formula-build", 10),
    ("texture", 8), ("chart-build", 14), ("footage-establish", 9), ("doc-highlight", 10), ("end", 7),
]


def timing(duration: float, reveals: dict | None = None, cards=()) -> dict:
    words = [{"word": f"w{i}", "start": round(i * 0.5 + 0.125, 3), "end": round(i * 0.5 + 0.375, 3)}
             for i in range(int(duration / 0.5))]
    seg = {"kind": "beat", "index": 1, "start": 0.0, "end": duration, "words": words,
           "reveals": {k: {"t": t, "value": FACTS[k]["value"]} for k, t in (reveals or {}).items()}}
    from hubricon_content.timing import cutpoints
    segs = [seg] + [{"kind": "card", "start": a, "end": b, "title": "A chapter"} for a, b in cards]
    return {"duration": duration, "segments": segs, "cutpoints": cutpoints(segs)}


def build(sequence=SEQUENCE):
    """The plan and its timing: reveals land 1 s into the shots that ask for them."""
    reg = shotmod.registry()
    t, rows, reveals, cards = 0.0, [], {}, []
    for n, item in enumerate(sequence, 1):
        style, secs = item[0], item[1]
        extra = item[2] if len(item) > 2 else {}
        st = reg["styles"][style]
        row = {"id": f"s{n:03d}", "start": t, "end": t + secs, "style": style, "kind": st["kinds"][0],
               "room": st["room"] if st["room"] != "either" else "world", "intent": f"{style} under these words",
               "params": {}, "overlay": {}, "reveals": [], "on": None}
        if "reveal" in extra:
            at = t + extra.get("at", 1.0)
            reveals[extra["reveal"]] = at
            row["reveals"] = [{"key": extra["reveal"], "t": at}]
            row["label"] = "proof" if "case" in extra["reveal"] else "demo"
        if st["on"] == "required":
            row["on"] = "{{%s}}" % extra["reveal"] if "reveal" in extra else f"w{int(t / 0.5) + 2}"
        if st.get("needs_chart"):
            row["chart"] = {"scene": "staircase"}
            if secs > 14:
                row["params"]["builds"] = [t + k for k in range(6, int(secs), 6)]
        if st.get("params", {}).get("clipping"):
            row["params"]["clipping"] = True
        if style == "number-land" and "reveal" not in extra:   # a figure it draws, spoken or not (shots.CONTENT)
            row["params"]["value"] = "{{leak}}"
        if style == "formula-build":           # a formula draws its terms, or the desk is bare (shots.CONTENT)
            row["params"]["terms"] = [{"text": "price"}, {"text": "units"}]
        if style == "footage-process":
            row["params"].update({"group": "pack", "step": extra["step"]})
        if style == "texture":
            row["overlay"]["illustration"] = True
        if row["kind"] in ("footage", "still", "texture", "archive", "stack", "split"):
            row["query"] = ["warehouse conveyor cartons daylight"]
            row["sources"] = {"stock": ["pexels", "pixabay"], "archival": ["loc", "commons"], "ai": ["higgsfield"]}[st["group"]]
            row["fallback"] = "paper:kinetic"
        if style == "chapter":
            cards.append((t, t + secs))
        rows.append(row)
        t += secs
    tm = timing(t, reveals, cards)
    for row in rows:
        row["says"] = " ".join(w["word"] for w in shotmod.words_in(shotmod.spoken(tm), row["start"], row["end"]))
    return {"slug": "fixture", "mode": "explainer", "fps": 30, "shots": rows}, tm


def fresh():
    plan, tm = build()
    return copy.deepcopy(plan), tm
