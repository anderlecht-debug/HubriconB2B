from hubricon_content import state


def _fresh():
    q = state.seed()
    for u in q["units"]:
        if u["kind"] != "video":
            for c in u["checklist"]:
                c["done"] = True
            u["status"] = "done"
    return q


def test_seed_starts_with_tooling():
    q = state.seed()
    item = state.next_item(q)
    assert item["unit"] == "P0-tooling" and item["step"] == "checklist:0"


def test_video_chain_respects_gates():
    q = _fresh()
    item = state.next_item(q)
    assert item["unit"] == "V01" and item["step"] == "facts"
    for s in ("facts", "script", "critique"):
        state.mark(q, "V01", s, "done")
    state.mark(q, "V01", "review", "awaiting")
    nxt = state.next_item(q)
    assert not (nxt.get("unit") == "V01" and nxt.get("step") == "tts")
    assert nxt.get("unit") != "V01"
    state.mark(q, nxt["unit"], nxt["step"], "done")      # the tick finishes the step it was on
    state.approve(q, "V01", "review")
    nxt = state.next_item(q)
    assert nxt["unit"] == "V01" and nxt["step"] == "tts"  # the approved unit resumes before new drafting


def test_reject_sends_script_back_and_three_strikes_stick():
    q = _fresh()
    for s in ("facts", "script", "critique"):
        state.mark(q, "V01", s, "done")
    state.mark(q, "V01", "review", "awaiting")
    state.reject(q, "V01", "review", "hook two is stronger")
    u = state.unit(q, "V01")
    assert u["steps"]["script"] == "todo" and u["status"] == "todo" and u["review_notes"]
    for _ in range(3):
        state.mark(q, "V01", "script", "failed", "guard")
    assert state.unit(q, "V01")["status"] == "stuck"


def test_upload_never_offered_without_founder_voice():
    q = _fresh()
    u = state.unit(q, "V01")
    for s in state.VIDEO_STEPS[:-2]:
        u["steps"][s] = "done"
    u["steps"]["review"] = "approved"
    u["voice"] = "placeholder"
    state.mark(q, "V01", "approve_final", "awaiting")
    state.approve(q, "V01", "approve_final")
    assert u["publishable"] is False and u["steps"]["upload"] == "blocked"
    nxt = state.next_item(q)
    assert not (nxt.get("unit") == "V01" and nxt.get("step") == "upload")


def test_inbox_cap_stops_drafting_ahead():
    q = _fresh()
    q["style_locked"] = True
    videos = [u for u in q["units"] if u["kind"] == "video" and u["status"] == "todo"]
    for u in videos[:state.MAX_AWAITING]:
        for s in ("facts", "script", "critique"):
            u["steps"][s] = "done"
        u["steps"]["review"] = "awaiting"; u["status"] = "awaiting"
    nxt = state.next_item(q)
    assert nxt.get("idle") or nxt.get("kind") != "video"


def test_scenes_wait_for_style_lock_except_first_video():
    q = _fresh()
    v4 = state.unit(q, "V04")
    for s in ("facts", "script", "critique", "tts", "timing"):
        v4["steps"][s] = "done"
    v4["steps"]["review"] = "approved"
    state.unit(q, "V01")["status"] = "blocked"; state.unit(q, "V01")["blocked_on"] = "test"
    nxt = state.next_item(q)
    assert not (nxt.get("unit") == "V04" and nxt.get("step") == "scenes")


def _tier_d(q: dict) -> dict:
    """A long documentary unit (VISUAL_SPEC.md §7.1), past its script review."""
    u = state._video_unit({"day": 90, "title": "A long film", "pillar": 1, "tier": "D", "slug": "long-film",
                           "models": [], "producible": True})
    q["units"] = [x for x in q["units"] if x["kind"] != "video"] + [u]
    for x in q["units"]:
        if x is not u:
            x["status"] = "done"
    for s in ("facts", "script", "critique"):
        u["steps"][s] = "done"
    u["steps"]["review"] = "approved"
    return u


def test_a_tier_d_unit_runs_the_documentary_chain():
    u = state._video_unit({"day": 90, "title": "t", "pillar": 1, "tier": "D", "slug": "s", "models": [], "producible": True})
    assert list(u["steps"]) == state.VIDEO_STEPS_D
    assert state.steps_for({"tier": "A"}) is state.VIDEO_STEPS
    from hubricon_content import qa, script
    assert script.WORDS["D"] == (3000, 7500) and qa.TIER_RANGE["D"] == (1200, 3000)


def test_tier_d_waits_at_steps_still_being_built_and_never_fails_there():
    q = _fresh()
    u = _tier_d(q)
    u["steps"]["tts"] = u["steps"]["timing"] = "done"
    assert state.next_item(q)["step"] == "shots"          # the shot plan is built
    state.mark(q, u["id"], "shots", "done")
    assert state.next_item(q)["step"] == "source"         # and sourcing (§12, phase 2)
    state.mark(q, u["id"], "source", "done")
    nxt = state.next_item(q)
    assert nxt.get("idle") and u["steps"]["pick"] == "todo" and not u["attempts"]


def test_a_unit_blocked_on_a_sourcing_key_resumes_when_the_key_is_set(monkeypatch):
    q = _fresh()
    u = _tier_d(q)
    for s in ("tts", "timing", "shots"):
        u["steps"][s] = "done"
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    state.mark(q, u["id"], "source", "blocked", "PIXABAY_API_KEY is not set (needed by s002) (VISUAL_SPEC.md §6.3)")
    state.refresh_capabilities(q)
    assert u["status"] == "blocked"
    monkeypatch.setenv("PIXABAY_API_KEY", "set")
    state.refresh_capabilities(q)
    assert u["status"] == "todo" and u["steps"]["source"] == "todo"


def test_no_long_film_renders_before_the_visual_trial_is_approved():
    q = _fresh()
    u = _tier_d(q)
    for s in ("tts", "timing", "shots", "source", "pick"):
        u["steps"][s] = "done"
    state.PENDING_D.discard("render_shots")
    try:
        assert state.next_item(q).get("idle")
        q["visual_locked"] = True
        assert state.next_item(q)["step"] == "render_shots"
    finally:
        state.PENDING_D.add("render_shots")


def test_rejecting_a_long_film_at_the_final_review_sends_it_back_to_the_pick():
    q = _fresh()
    u = _tier_d(q)
    for s in state.VIDEO_STEPS_D[4:-2]:
        u["steps"][s] = "done"
    state.mark(q, u["id"], "approve_final", "awaiting")
    state.reject(q, u["id"], "approve_final", "the port shots repeat")
    assert u["steps"]["pick"] == "todo" and u["steps"]["source"] == "done" and u["steps"]["upload"] == "blocked"
