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
