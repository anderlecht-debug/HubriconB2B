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
    desk = script.split("## Before it goes live")[1].split("## The record")[0]
    assert "Old test." not in desk
    assert "$1,240" in script                                  # ledger close
    assert "Approve or decline" in script


def test_build_memo_is_a_numbered_letter_with_real_numbers():
    from hubricon_engine.briefing import build_memo

    directives = [{"status": "issued", "module": "advertising",
                   "action_text": "Cut bleed.", "expected_impact_usd": 500, "measured_impact_usd": None}]
    memo = build_memo("Acme Goods", "Jane", period_deltas(MARGINS),
                      directives, [], [], ledger_measured=1240, ledger_count=3, issue_number=4)
    assert memo.startswith("Profit Brief No. 004")
    assert "Dear Jane," in memo
    assert "$3,700" in memo and "up $1,200" in memo          # real numbers, prose form
    assert "one decision" in memo                             # decision count in words
    assert "$1,240" in memo and memo.rstrip().endswith("— Hubricon")


def test_build_memo_baseline_framing_on_first_issue():
    from hubricon_engine.briefing import build_memo

    memo = build_memo("Acme", "", period_deltas(MARGINS[:2]), [], [], [], 0, 0, issue_number=1)
    assert "Profit Brief No. 001" in memo and "baseline" in memo and "$2,500" in memo


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
                                             "Before it goes live", "The record"]
    for b in beats:
        assert b["speech"] in script
        # Spoken text is read aloud: no markdown, no stage directions.
        assert "##" not in b["speech"] and "[" not in b["speech"]


def test_an_approved_move_is_going_live_not_waiting_for_a_decision():
    """'Before it goes live' counts decisions the way the letter does: issued
    only. An approved move is past deciding — inside the standing yes with the
    window closed — so it is named as going live, and one already executed is
    on the Record's side of the line and named nowhere here."""
    from hubricon_engine.briefing import build_beats, build_memo
    directives = [
        {"status": "issued", "module": "advertising", "action_text": "Negative-match 11 terms.",
         "expected_impact_usd": 1940, "measured_impact_usd": None},
        {"status": "approved", "module": "pricing", "action_text": "Move SKU-1 $20.00 → $19.00.",
         "expected_impact_usd": 400, "measured_impact_usd": None},
        {"status": "approved", "module": "pricing", "action_text": "Already live.",
         "expected_impact_usd": 100, "measured_impact_usd": None, "executed_at": "2026-09-01T00:00:00Z"},
    ]
    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), directives, [], [], 1240, 2)
    desk = next(b for b in beats if b["heading"] == "Before it goes live")
    assert "There is one decision waiting" in desk["speech"]
    assert [p[0] for p in desk["points"]] == ["ADVERTISING", "GOING LIVE"]
    assert desk["points"][-1] == ("GOING LIVE", "1 move(s) inside your standing yes, window closed — "
                                                "going live this week")
    assert "Already live" not in str(desk["points"])
    memo = build_memo("Acme Goods", "Jane", period_deltas(MARGINS), directives, [], [], 1240, 2, issue_number=3)
    assert "There is one decision waiting" in memo                # the letter counts the same way

    # Only approved moves: nothing to decide, and the video still says what goes live.
    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), directives[1:2], [], [], 1240, 2)
    desk = next(b for b in beats if b["heading"] == "Before it goes live")
    assert "Nothing needs your decision" in desk["speech"]
    assert desk["points"] == [("GOING LIVE", "1 move(s) inside your standing yes, window closed — "
                                             "going live this week")]


def test_a_quiet_period_still_has_something_to_say():
    from hubricon_engine.briefing import build_beats
    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), [], [], [], 0, 0)
    desk = next(b for b in beats if b["heading"] == "Before it goes live")
    assert "Nothing needs your decision" in desk["speech"]
    assert desk["points"] == []


def test_the_letter_and_the_video_close_on_the_three_record_numbers():
    """The close is the strip in Hubricon: proven, found and filed, billed.
    The memo, the numbers slide and the spoken record beat all carry all three."""
    from hubricon_engine.briefing import build_beats, build_memo

    memo = build_memo("Acme Goods", "Jane", period_deltas(MARGINS), [], [], [],
                      1240, 2, issue_number=5, ledger_found=2400, fees_billed=6000)
    close = memo.split("Your Profit Record to date:")[1]
    assert "$1,240 proven across 2 moves" in close
    assert "$2,400 found and filed, not yet banked" in close and "$6,000 billed" in close
    assert "in our favor or against us" in close

    beats = build_beats("Acme Goods", "Jane", period_deltas(MARGINS), [], [], [], 1240, 2,
                        ledger_found=2400, fees_billed=6000)
    numbers = dict(next(b for b in beats if b["heading"] == "The three numbers")["points"])
    assert numbers["Proven on your Profit Record"] == "$1,240 across 2"
    assert numbers["Found and filed, not yet banked"] == "$2,400"
    assert numbers["Billed to date"] == "$6,000"
    record = next(b for b in beats if b["heading"] == "The record")["speech"]
    assert "$1,240 proven across 2 moves" in record and "$2,400 found and filed" in record
    assert "$6,000 billed" in record

    # Existing positional callers pass nothing for the two new numbers and get zeros.
    memo0 = build_memo("Acme", "", period_deltas(MARGINS[:2]), [], [], [], 0, 0, issue_number=1)
    assert "$0 found and filed, not yet banked · $0 billed" in memo0
