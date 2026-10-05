"""A film's voice is what it says it is. The founder's own clone narrates as his
voice; a voice copied from ElevenLabs' library is another person's, and narrates
only when the founder has chosen it in content/assets/voice.json, disclosed as an
AI library voice (2026-10-04: "Kevin - Career and Life Coach")."""

from hubricon_content import qa, state, tts

LIBRARY = {"name": "Kevin - Career and Life Coach", "category": "professional",
           "sharing": {"status": "copied", "original_voice_id": "someone-elses-id"}}
OWN = {"name": "Hagen Simmons", "category": "professional", "sharing": None}


def test_a_library_voice_is_refused_and_named():
    own, name = tts.voice_is_own("v1", fetch=lambda vid: LIBRARY)
    assert own is False and name == "Kevin - Career and Life Coach"


def test_the_accounts_own_clone_is_accepted():
    assert tts.voice_is_own("v2", fetch=lambda vid: OWN) == (True, "Hagen Simmons")
    shared_by_us = {**OWN, "sharing": {"status": "enabled", "original_voice_id": "v3"}}
    assert tts.voice_is_own("v3", fetch=lambda vid: shared_by_us)[0] is True


def test_a_voice_that_cannot_be_checked_never_narrates():
    def down(vid):
        raise OSError("network")
    assert tts.voice_is_own("v4", fetch=down)[0] is False


def test_an_unchosen_library_voice_is_refused(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v1")
    monkeypatch.setattr(tts, "voice_is_own", lambda vid, **kw: (False, "Kevin - Career and Life Coach"))
    monkeypatch.setattr(tts, "chosen_voice", lambda: {"kind": "library", "voice_id": "some-other-voice"})
    name, why = tts.provider()
    assert name == "none" and "Kevin" in why and "voice.json" in why
    assert state.capabilities()["founder_voice_id"] is None


def test_the_chosen_library_voice_narrates_and_says_what_it_is(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v1")
    monkeypatch.setattr(tts, "voice_is_own", lambda vid, **kw: (False, "Kevin - Career and Life Coach"))
    monkeypatch.setattr(tts, "chosen_voice", lambda: {"kind": "library", "voice_id": "v1", "name": "Kevin", "on": "2026-10-04"})
    assert tts.provider()[0] == "library" and state.capabilities()["founder_voice_id"] == "v1"
    assert "library" in qa.PUBLISHABLE_VOICES
    line = qa.disclosure_for("library")
    assert "AI voice from ElevenLabs' voice library" in line and "Hagen Simmons's voice" not in line


def test_the_recorded_choice_matches_what_the_founder_picked():
    chosen = tts.chosen_voice()
    assert chosen["kind"] == "library" and chosen["name"] == "Kevin - Career and Life Coach" and chosen["voice_id"]


def test_provider_and_capabilities_accept_only_a_known_voice(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v1")
    monkeypatch.setattr(tts, "chosen_voice", lambda: {})
    monkeypatch.setattr(tts, "voice_is_own", lambda vid, **kw: (True, "Hagen Simmons"))
    assert tts.provider()[0] == "founder" and state.capabilities()["founder_voice_id"] == "v1"
