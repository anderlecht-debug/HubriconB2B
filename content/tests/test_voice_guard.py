"""Only the founder's own clone narrates a film presented as his voice. A voice
copied from ElevenLabs' public library is another person's (2026-10-04: a
library voice, "Kevin - Career and Life Coach", was set as ELEVENLABS_VOICE_ID)."""

from hubricon_content import state, tts

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


def test_provider_and_capabilities_refuse_a_library_voice(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v1")
    monkeypatch.setattr(tts, "voice_is_own", lambda vid, **kw: (False, "Kevin - Career and Life Coach"))
    name, why = tts.provider()
    assert name == "none" and "Kevin" in why and "another person's" in why
    assert state.capabilities()["founder_voice_id"] is None
    monkeypatch.setattr(tts, "voice_is_own", lambda vid, **kw: (True, "Hagen Simmons"))
    assert tts.provider()[0] == "founder" and state.capabilities()["founder_voice_id"] == "v1"
