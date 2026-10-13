"""Packaging first: three titles, three thumbnail concepts, the opening paying off the chosen one."""
import json

from hubricon_content import film_qa, shots, thumbnail
from hubricon_content import script as sm

HEAD = """TITLE: Why One Price Held
THUMBNAIL: A coin on dark paper | TEXT: Never measured | PICTURE: s001
TITLE 1: Why One Price Held
TITLE 2: The Price Nobody Measured
TITLE 3: One Price, Fifty Years
THUMBNAIL 1: A coin on dark paper | TEXT: Never measured | PICTURE: s001
THUMBNAIL 2: The span as one figure | TEXT: {{span}} unmoved
THUMBNAIL 3: The tower lit at night | TEXT: Paid in dimes
HOOKS
1. A hook.
SCRIPT
[0:00] OPEN
  VO: A coin.
"""


def test_three_titles_and_three_concepts_are_required_and_the_chosen_ones_come_from_them():
    assert sm.packaging(sm.parse(HEAD)) == []
    bad = HEAD.replace("TITLE 3: One Price, Fifty Years\n", "").replace("TITLE: Why One Price Held", "TITLE: Something else")
    bad = bad.replace("TEXT: Paid in dimes", "TEXT: Paid for in dimes by millions")
    p = sm.packaging(sm.parse(bad))
    assert any("TITLE 3 missing" in x for x in p) and any("THUMBNAIL 3: its text is 6 words" in x for x in p)
    assert sm.thumbnail_concept("A coin | TEXT: {{span}} unmoved")["text"] == "{{span}} unmoved"
    assert sm.thumbnail_concept("A coin | TEXT: Never | PICTURE: s001")["picture"] == "s001"


def test_the_opening_must_pay_off_the_chosen_thumbnail(tmp_path, monkeypatch):
    (tmp_path / "script.md").write_text(HEAD)
    timing = {"segments": [{"kind": "beat", "spoken": [{"key": "span", "t": 30.0}]}]}
    plan = {"shots": [{"id": "s001", "start": 0.0, "end": 4.0, "room": "world", "kind": "still", "query": ["coin"]},
                      {"id": "s002", "start": 4.0, "end": 9.0, "room": "paper", "kind": "number", "params": {}}]}
    assert film_qa.packaging(tmp_path, plan, timing) == []                    # s001, the thumbnail's picture, opens the film
    plan["shots"][0]["id"] = "s009"
    plan["shots"][0]["query"] = ["warehouse"]
    out = film_qa.packaging(tmp_path, plan, timing)
    assert out and out[0]["check"] == "packaging" and "first 5 s" in out[0]["msg"]
    (tmp_path / "script.md").write_text(HEAD.replace("THUMBNAIL: A coin on dark paper | TEXT: Never measured | PICTURE: s001",
                                                     "THUMBNAIL: The span as one figure | TEXT: {{span}} unmoved"))
    assert "span" in film_qa.packaging(tmp_path, plan, timing)[0]["msg"]      # the figure is said at 30 s, not in the opening
