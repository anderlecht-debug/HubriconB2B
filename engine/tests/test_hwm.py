"""The fee rule, held to its promises on fixed cases and on random ones.

The random cases loop over a fixed seed, so a failure always reproduces."""

import random

import pytest

from hubricon_engine import hwm

GRADES = ["direct", "isolated", "randomised", "attributable", "pooled"]


def _month(i: int) -> str:
    return f"{2026 + i // 12}-{i % 12 + 1:02d}"


def _random_history(rng: random.Random, n_months: int, *, disputes=True, lower=True):
    months, ids = [], []
    for i in range(n_months):
        dollars = []
        for _ in range(rng.randint(0, 4)):
            did = f"d{len(ids)}"
            usd = round(rng.uniform(-800, 2500), 2)
            dollars.append({"id": did, "usd": usd, "grade": rng.choice(GRADES)})
            ids.append((did, usd))
        m = {"month": _month(i), "dollars": dollars}
        if lower and rng.random() < 0.7:
            # A lower bound somewhere under the plain sum (or above it: the
            # rule must clamp it).
            point = sum(u for _, u in ids)
            m["lower_bound"] = round(point - rng.uniform(-200, 1500), 2)
        if disputes and ids and rng.random() < 0.2:
            m["disputed"] = [rng.choice(ids)[0]]
        if rng.random() < 0.1:
            m["cap_usd"] = rng.choice([100.0, 250.0, 1000.0])
        months.append(m)
    return months


CASES = [(seed, _random_history(random.Random(seed), random.Random(seed).randint(3, 30)))
         for seed in range(400)]


def test_simple_month_charges_the_rates():
    s = hwm.run("a.myshopify.com", [{"month": "2026-01", "dollars": [
        {"id": "c", "usd": 1000, "grade": "direct"},
        {"id": "e", "usd": 1000, "grade": "attributable"}]}], cap_usd=10_000)
    assert s[0]["feeable_confirmed"] == 1000 and s[0]["feeable_estimated"] == 1000
    assert s[0]["fee"] == 300.0 and not s[0]["capped"]
    assert any("20%" in line for line in s[0]["explanation"])


def test_unknown_grade_is_an_error():
    with pytest.raises(ValueError):
        hwm.run("a", [{"month": "2026-01", "dollars": [{"id": "x", "usd": 1, "grade": "vibes"}]}])


def test_fee_never_charged_below_previous_peak():
    for seed, months in CASES:
        for st in hwm.run("s", months):
            if st["cumulative"] <= st["peak_before"]:
                assert st["fee"] == 0, seed
            # The dollars charged never exceed the rise over the peak.
            charged = st["feeable_confirmed"] + st["feeable_estimated"]
            assert charged <= max(0.0, st["cumulative"] - st["peak_before"]) + 0.02, seed
            assert st["peak_after"] >= st["peak_before"] - 1e-9, seed


def test_total_fees_bounded_by_rate_times_max_cumulative():
    for seed, months in CASES:
        out = hwm.run("s", months)
        top = max([0.0] + [st["cumulative"] for st in out])
        net = sum(st["fee"] - st["refunds"] for st in out)
        assert net <= hwm.CONFIRMED_RATE * top + 0.05, seed
    # Without disputes the gross fees obey it too.
    for seed in range(200):
        rng = random.Random(10_000 + seed)
        out = hwm.run("s", _random_history(rng, rng.randint(3, 30), disputes=False))
        top = max([0.0] + [st["cumulative"] for st in out])
        assert sum(st["fee"] for st in out) <= hwm.CONFIRMED_RATE * top + 0.05, seed


def test_losses_are_deducted_first():
    months = [
        {"month": "2026-01", "dollars": [{"id": "w", "usd": 1000, "grade": "direct"}]},
        {"month": "2026-02", "dollars": [{"id": "l", "usd": -600, "grade": "isolated"}]},
        {"month": "2026-03", "dollars": [{"id": "w2", "usd": 500, "grade": "direct"}]},
        {"month": "2026-04", "dollars": [{"id": "w3", "usd": 300, "grade": "direct"}]},
    ]
    out = hwm.run("s", months)
    assert out[0]["fee"] == 200.0
    assert out[1]["fee"] == 0 and out[1]["cumulative"] == 400
    # $500 earned back only reaches $900, under the $1,000 peak: still nothing.
    assert out[2]["fee"] == 0
    assert any("Losses come off first" in line for line in out[2]["explanation"])
    # $1,200 is $200 over the peak: only that $200 is charged.
    assert out[3]["rise"] == 200 and out[3]["fee"] == 40.0
    # Property: a month whose total is pulled under the peak by losses pays nothing.
    for seed, ms in CASES:
        for st in hwm.run("s", ms):
            if st["losses"] < 0 and st["cumulative"] <= st["peak_before"]:
                assert st["fee"] == 0, seed


def test_sunset_excludes_dollars_older_than_twelve_months():
    # A dollar banked in Jan 2026 whose lower bound only clears 13 months later.
    months = [{"month": "2026-01", "dollars": [{"id": "old", "usd": 1000, "grade": "direct"}],
               "lower_bound": 0.0}]
    months += [{"month": _month(i), "dollars": [], "lower_bound": 0.0} for i in range(1, 13)]
    months[-1]["lower_bound"] = 1000.0    # index 12 = 2027-01, 12 months on
    out = hwm.run("s", months)
    assert out[-1]["month"] == "2027-01"
    assert out[-1]["fee"] == 0 and out[-1]["sunset_excluded"] == 1000
    assert out[-1]["peak_after"] == 1000    # the high still moves; the dollar is the brand's
    # The month before (11 months on) it would still have been feeable.
    months[11]["lower_bound"] = 1000.0
    out = hwm.run("s", months[:12])
    assert out[-1]["fee"] == 200.0
    # Property: a charged dollar is never 12 or more months old.
    for seed in range(300):
        rng = random.Random(20_000 + seed)
        ms = _random_history(rng, rng.randint(14, 30))
        for i in range(len(ms)):
            out = hwm.run("s", ms[: i + 1])[-1]
            # Only dollars from the last 12 months can be charged, so the charge
            # never exceeds what those months banked in positive dollars.
            recent = sum(max(0.0, d["usd"]) for m in ms[max(0, i - 11): i + 1] for d in m["dollars"])
            assert out["feeable_confirmed"] + out["feeable_estimated"] <= recent + 0.02, seed


def test_cap_is_never_exceeded_and_never_carried():
    months = [{"month": "2026-01", "dollars": [{"id": "a", "usd": 10_000, "grade": "direct"}]},
              {"month": "2026-02", "dollars": []}]
    out = hwm.run("s", months)
    assert out[0]["fee"] == 500.0 and out[0]["capped"] and out[0]["capped_usd"] == 1500.0
    assert out[1]["fee"] == 0    # the $1,500 above the cap is not a debt
    assert any("not carried forward" in line for line in out[0]["explanation"])
    for seed, ms in CASES:
        for st, m in zip(hwm.run("s", ms), ms):
            assert st["fee"] <= m.get("cap_usd", hwm.DEFAULT_CAP_USD) + 1e-9, seed
    # Configurable per shop.
    assert hwm.run("s", months, cap_usd=50)[0]["fee"] == 50.0


def test_dispute_refunds_the_fee_and_strikes_the_dollar():
    months = [
        {"month": "2026-01", "dollars": [{"id": "a", "usd": 1000, "grade": "direct"},
                                         {"id": "b", "usd": 1000, "grade": "pooled"}]},
        {"month": "2026-02", "dollars": [], "disputed": ["a"]},
        {"month": "2026-03", "dollars": [{"id": "c", "usd": 500, "grade": "direct"}]},
    ]
    out = hwm.run("s", months)
    assert out[0]["fee"] == 300.0
    assert out[1]["refunds"] == 200.0 and out[1]["refunded_ids"] == ["a"]
    assert out[1]["net"] == -200.0 and out[1]["cumulative"] == 1000
    assert any("struck from the Record" in line for line in out[1]["explanation"])
    # The struck dollar's part of the peak went with it, so c is charged in full.
    assert out[2]["peak_before"] == 1000 and out[2]["fee"] == 100.0
    # Property: every dispute of a charged dollar produces a refund.
    hits = 0
    for seed, ms in CASES:
        out = hwm.run("s", ms)
        for st, m in zip(out, ms):
            for did in st["refunded_ids"]:
                assert did in (m.get("disputed") or [])
            hits += st["refunds"] > 0
    assert hits > 0


def test_dispute_of_capped_fee_refunds_only_what_was_paid():
    months = [{"month": "2026-01", "dollars": [{"id": "a", "usd": 5000, "grade": "direct"},
                                               {"id": "b", "usd": 5000, "grade": "direct"}]},
              {"month": "2026-02", "dollars": [], "disputed": ["a"]}]
    out = hwm.run("s", months)
    assert out[0]["fee"] == 500.0
    assert out[1]["refunds"] == 250.0


def test_lower_bound_is_clamped_to_the_record():
    out = hwm.run("s", [{"month": "2026-01", "dollars": [{"id": "a", "usd": 100, "grade": "direct"}],
                         "lower_bound": 9999}])
    assert out[0]["cumulative"] == 100 and out[0]["fee"] == 20.0
