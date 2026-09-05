from hubricon_engine.briefing import build_script, parse_loom_id, period_deltas, top_story


def test_parse_loom_id_accepts_share_embed_and_bare():
    vid = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    assert parse_loom_id(f"https://www.loom.com/share/{vid}") == vid
    assert parse_loom_id(f"https://www.loom.com/share/{vid}?sid=xyz&t=12") == vid
    assert parse_loom_id(f"https://www.loom.com/embed/{vid}") == vid
    assert parse_loom_id(vid) == vid
    assert parse_loom_id("https://youtube.com/watch?v=nope") is None
    assert parse_loom_id("not a url") is None


MARGINS = [
    {"sku": "A", "period_start": "2026-06-01", "revenue": 10000.0, "net_margin": 2000.0},
    {"sku": "B", "period_start": "2026-06-01", "revenue": 5000.0, "net_margin": 500.0},
    {"sku": "A", "period_start": "2026-07-01", "revenue": 12000.0, "net_margin": 3100.0},
    {"sku": "B", "period_start": "2026-07-01", "revenue": 5000.0, "net_margin": 600.0},
]


def test_period_deltas_compares_latest_two_periods():
    d = period_deltas(MARGINS)
    assert d["period"] == "2026-07-01"
    assert d["latest"]["net"] == 3700.0
    assert d["net_delta"] == 1200.0       # 3700 - 2500
    assert d["revenue_delta"] == 2000.0   # 17000 - 15000
    assert abs(d["latest"]["pct"] - 3700 / 17000) < 1e-9
    assert period_deltas([]) is None
    single = period_deltas(MARGINS[:2])
    assert single["net_delta"] is None    # one period: nothing to compare


def test_top_story_prefers_critical_alert_then_biggest_directive():
    alerts = [{"severity": "critical", "message": "WIDGET-RED: 100% stockout risk."}]
    directives = [{"expected_impact_usd": 900, "action_text": "Cut bleed terms."}]
    assert "WIDGET-RED" in top_story(directives, alerts, [])
    assert "Cut bleed terms" in top_story(directives, [], [])
    fallback = top_story([], [], [{"status": "ok", "item_id": "S1", "elasticity": -0.4}])
    assert "S1" in fallback and "price-insensitive" in fallback


def test_build_script_hits_all_beats_with_real_numbers():
    directives = [
        {"status": "issued", "module": "advertising", "action_text": "Negative-match 11 terms.",
         "expected_impact_usd": 1940, "measured_impact_usd": None},
        {"status": "done", "module": "pricing", "action_text": "Old test.",
         "expected_impact_usd": 800, "measured_impact_usd": 1240},
    ]
    script = build_script("Acme Goods", "Jane", period_deltas(MARGINS),
                          directives, [], [], ledger_measured=1240, ledger_count=2)
    assert script.startswith("# Briefing script — Acme Goods")
    assert "Jane — your net profit is up $1,200" in script    # hook, name + dollar first
    assert "$3,700" in script and "$17,000" in script          # the three numbers
    assert "Negative-match 11 terms." in script                # issued action listed
    # An already-measured directive is history, not a decision: it must not be
    # read out as something waiting on the client. (The old form of this
    # assertion ended in `or True` and could never fail.)
    desk = script.split("## On your desk")[1].split("## The record")[0]
    assert "Old test." not in desk
    assert "$1,240" in script                                  # ledger close
    assert "Approve or decline" in script


def test_build_memo_is_a_numbered_letter_with_real_numbers():
    from hubricon_engine.briefing import build_memo

    directives = [{"status": "issued", "module": "advertising",
                   "action_text": "Cut bleed.", "expected_impact_usd": 500, "measured_impact_usd": None}]
    memo = build_memo("Acme Goods", "Jane", period_deltas(MARGINS),
                      directives, [], [], ledger_measured=1240, ledger_count=3, issue_number=4)
    assert memo.startswith("Issue No. 004")
    assert "Dear Jane," in memo
    assert "$3,700" in memo and "up $1,200" in memo          # real numbers, prose form
    assert "one decision" in memo                             # decision count in words
    assert "$1,240" in memo and memo.rstrip().endswith("— Hubricon")


def test_build_memo_baseline_framing_on_first_issue():
    from hubricon_engine.briefing import build_memo

    memo = build_memo("Acme", "", period_deltas(MARGINS[:2]), [], [], [], 0, 0, issue_number=1)
    assert "Issue No. 001" in memo and "baseline" in memo and "$2,500" in memo


def test_build_script_first_period_hook():
    script = build_script("Acme", "", period_deltas(MARGINS[:2]), [], [], [], 0, 0)
    assert "first full read" in script and "$2,500" in script


def test_beats_and_script_tell_the_same_story():
    """The video speaks `speech` over a slide built from the same beat, so a
    line in one that is missing from the other is a defect."""
    from hubricon_engine.briefing import build_beats
    directives = [{"status": "issued", "module": "advertising", "action_text": "Negative-match 11 terms.",
                   "expected_impact_usd": 1940, "measured_impact_usd": None}]
    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), directives, [], [], 1240, 2)
    script = build_script("Acme Goods", "Jane", period_deltas(MARGINS), directives, [], [], 1240, 2)
    assert [b["heading"] for b in beats] == ["Hook", "The three numbers", "The why",
                                             "On your desk", "The record"]
    for b in beats:
        assert b["speech"] in script
        # Spoken text is read aloud: no markdown, no stage directions.
        assert "##" not in b["speech"] and "[" not in b["speech"]


def test_a_quiet_period_still_has_something_to_say():
    from hubricon_engine.briefing import build_beats
    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), [], [], [], 0, 0)
    desk = next(b for b in beats if b["heading"] == "On your desk")
    assert "Nothing needs your decision" in desk["speech"]
    assert desk["points"] == []
