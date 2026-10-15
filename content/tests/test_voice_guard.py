"""Every film is narrated in the founder's own recorded voice (the founder's call, 2026-10-06:
no ElevenLabs, no clone). The narration step uses his takes when every beat is read, the
offline placeholder only when asked for, and otherwise waits on his reading; nothing in the
pipeline calls ElevenLabs, and a new sound carries a free licence."""

import json
from pathlib import Path

import pytest

from hubricon_content import qa, sfx, state, tts

SRC = Path(tts.__file__).parent


def test_only_his_own_voice_publishes_and_the_description_says_so():
    assert qa.PUBLISHABLE_VOICES == ("own",)
    assert qa.disclosure_for("own") == "Narrated by Hagen Simmons, in his own voice."
    for other in ("founder", "library", "placeholder", None):
        assert "not for publishing" in qa.disclosure_for(other)


def test_nothing_in_the_pipeline_calls_elevenlabs():
    for f in SRC.glob("*.py"):
        assert "api.elevenlabs.io" not in f.read_text(encoding="utf-8"), f.name
    caps = state.capabilities()
    assert not any("eleven" in k for k in caps) and "founder_voice_id" not in caps


def test_the_narration_step_waits_on_his_takes(monkeypatch):
    monkeypatch.setattr(tts, "missing_takes", lambda slug: ["b1", "b4"])
    monkeypatch.setattr(tts, "ALLOW_PLACEHOLDER", False)
    name, why = tts.provider("01-survivorship-bias")
    assert name == "none" and "record.mjs 01-survivorship-bias" in why
    res = tts.run({"slug": "01-survivorship-bias"}, {})
    assert res["status"] == "blocked" and "record.mjs" in res["reason"]


def test_with_every_take_read_the_step_uses_them(monkeypatch):
    monkeypatch.setattr(tts, "missing_takes", lambda slug: [])
    called = {}
    monkeypatch.setattr(tts, "takes_to_vo", lambda u, q, force=False: called.setdefault("ok", {"status": "ok", "voice": "own"}))
    assert tts.provider("s")[0] == "own"
    assert tts.run({"slug": "s"}, {}) == {"status": "ok", "voice": "own"}


def test_a_unit_waiting_on_his_reading_returns_when_the_takes_are_in(monkeypatch):
    q = {"units": [{"id": "V01", "slug": "01-survivorship-bias", "status": "blocked", "steps": {"tts": "blocked"},
                    "blocked_on": "the founder's own takes: read the script at the teleprompter, `node content/film/record.mjs 01-survivorship-bias`"}]}
    monkeypatch.setattr(state, "_takes_in", lambda slug: True)
    state.refresh_capabilities(q)
    assert q["units"][0]["status"] == "todo" and q["units"][0]["steps"]["tts"] == "todo"


def test_new_sound_needs_a_free_licence_and_its_page(tmp_path, monkeypatch):
    monkeypatch.setattr(sfx, "AMBIENCE", tmp_path / "ambience")
    clip = tmp_path / "port.mp3"; clip.write_bytes(b"x")
    with pytest.raises(SystemExit):
        sfx.ambience_add(str(clip), "container port", "elevenlabs", "https://elevenlabs.io/x")
    with pytest.raises(SystemExit):
        sfx.ambience_add(str(clip), "container port", "freesound", "https://example.com/x")
    res = sfx.ambience_add(str(clip), "container port cranes", "freesound", "https://freesound.org/people/a/sounds/1/", "a")
    entry = json.loads((tmp_path / "ambience" / "manifest.json").read_text())["container-port-cranes"]
    assert res["licence"] == entry["licence"] == "Creative Commons CC0 (Freesound)" and entry["url"].startswith("https://freesound.org/")
    # a subject that shares two words finds it; one that shares one plays room tone
    assert sfx.ambience("container port at dawn") == tmp_path / "ambience" / "container-port-cranes.mp3"
    assert sfx.ambience("port office") is None


def test_the_library_on_file_carries_its_paid_subscription_licence():
    for m in (sfx.SFX / "manifest.json", sfx.AMBIENCE / "manifest.json"):
        for name, e in json.loads(m.read_text(encoding="utf-8")).items():
            assert e["licence"] == sfx.PAID_ELEVENLABS and e["made_on"] <= "2026-10-06", (m.name, name)
    assert not (sfx.SFX.parent / "voice.json").exists()
