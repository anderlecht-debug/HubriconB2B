"""A long film's score comes from its shot plan (audio.score_events)."""
import numpy as np

from hubricon_content import audio


def _plan():
    return {"shots": [
        {"id": "s1", "room": "paper", "style": "number-land", "on": "{{a}}", "start": 0.0, "end": 5.0,
         "reveals": [{"key": "a", "t": 1.0}]},
        {"id": "s2", "room": "world", "style": "still-push", "start": 5.0, "end": 12.0, "reveals": []},
        {"id": "s3", "room": "paper", "style": "chapter", "start": 12.0, "end": 14.5, "reveals": []},
        {"id": "s4", "room": "paper", "style": "kinetic-thesis", "start": 14.5, "end": 20.0, "reveals": []},
        {"id": "s5", "room": "paper", "style": "doc-highlight", "kind": "document", "start": 20.0, "end": 30.0,
         "reveals": [{"key": "b", "t": 22.0}, {"key": "c", "t": 22.1}]},
    ]}


def _timing():
    return {"segments": [{"kind": "beat", "start": 0.0, "end": 12.0}, {"kind": "card", "start": 12.0, "end": 14.5},
                         {"kind": "beat", "start": 14.5, "end": 30.0}], "chapters": [{"at": 12.0, "title": "x"}]}


def test_score_follows_the_plan():
    ev = audio.score_events(_plan(), _timing())
    assert ev["ticks"] == [1.0, 22.0]                    # every figure lands with a tick, never two at once
    assert ev["subs"] == [1.0]                           # only a hero figure gets the low hit
    assert ev["rooms"] == [5.0]                          # paper → world; the card cut keeps its own whoosh
    assert ev["drops"] == [14.5]                         # the bed drops under the thesis line
    assert ev["risers"] == [12.0]
    assert ev["paper"] == [20.0]                         # a document lands with a paper sound


def test_family_crossfades_without_gaps():
    bed = np.sin(np.linspace(0, 400 * np.pi, audio.SR * 4))
    out = audio._family(bed, audio.SR * 20, [8.0, 14.0])
    assert len(out) == audio.SR * 20
    for t in (7.9, 8.0, 8.1, 14.0):                      # no hole at a chapter boundary
        i = int(t * audio.SR)
        assert np.abs(out[i - 2000:i + 2000]).max() > 0.2
