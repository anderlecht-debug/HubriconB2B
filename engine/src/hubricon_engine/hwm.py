"""The fee rule: a share of proven dollars, charged only on new highs.

BUILD_PLAN.md, "The offer" (23 Nov 2026):

    Take rate: 20% of platform-confirmed or randomised dollars, 10% of
    estimated or pooled dollars. Charged only on new highs of the cumulative
    lower bound. Cap: Shopify's capped amount, default $500 a month. Sunset:
    each proven dollar earns a fee for 12 months, then belongs to the brand.
    Guarantee: dispute any dollar and it is refunded and struck from the
    Record, no argument.

This module turns a shop's banked months into one statement per month. Pure,
like value.py and measurement.py: dicts in, statements out, no database and no
network. usage.py turns a statement into the Shopify usage record.

THE RULE, IN ORDER
------------------
1. Strike. Dollars the brand disputed this month leave the Record as if they
   had never been banked. Any fee they produced is refunded on this statement,
   and the part of the peak they built is taken back down, so the next real
   dollar is not spent filling a hole the struck one left.
2. Bank. This month's dollars join the Record. A loss from a Hubricon move is a
   negative dollar: it lowers the cumulative total before anything else does,
   so no fee is charged until the loss is earned back.
3. Measure. The cumulative total we bill against is its LOWER bound: the 25th
   percentile of the book (measurement.bank_the_book's MEASURE_QUANTILE), as
   supplied with the month, never above the plain sum of the Record. A month
   that arrives without one uses the plain sum.
4. Compare with the peak. The fee base is the cumulative lower bound minus the
   highest it has ever been (the high-water mark). At or below the peak, the fee
   is zero. Above it, the peak moves up to the new high whether or not any of
   that rise could be charged.
5. Sunset. The rise is matched to proven dollars not yet charged, oldest first,
   and only dollars banked within the last 12 months can be matched. A dollar
   banked in March is feeable March to February and belongs to the brand after.
   Within one month, estimated dollars are matched before confirmed ones, which
   is the cheaper order for the brand.
6. Rate. Confirmed dollars (direct, isolated, randomised) pay 20%; estimated
   dollars (attributable, pooled) pay 10%.
7. Cap. The month's fee never exceeds the shop's cap. The amount above it is not
   carried as a debt: those dollars count as charged, the statement says
   "capped", and billing pauses until the next new high.

The bias is the same as measurement.py's: when the rule could be read two ways,
it is read the way that charges the brand less.
"""

CONFIRMED_RATE = 0.20       # direct, isolated and randomised dollars
ESTIMATED_RATE = 0.10       # attributable and pooled dollars
SUNSET_MONTHS = 12          # a dollar is feeable in its banked month and the 11 after
DEFAULT_CAP_USD = 500.0     # Shopify's capped amount; only the merchant can raise it
EPS = 1e-9                  # float dust below this is zero

# Measurement's attribution labels (measurement.py, "THE ATTRIBUTION STANDARD"),
# plus the two the offer adds, mapped to the two billing grades.
CONFIRMED_GRADES = {"direct", "isolated", "randomised", "randomized", "confirmed"}
ESTIMATED_GRADES = {"attributable", "pooled", "estimated"}


def grade_of(label: str) -> str:
    """'confirmed' or 'estimated'. An unknown label is an error, not a guess:
    a dollar billed at the wrong rate is worse than a statement that fails."""
    label = (label or "").strip().lower()
    if label in CONFIRMED_GRADES:
        return "confirmed"
    if label in ESTIMATED_GRADES:
        return "estimated"
    raise ValueError(f"unknown grade {label!r}: expected one of "
                     f"{sorted(CONFIRMED_GRADES | ESTIMATED_GRADES)}")


def month_index(month: str) -> int:
    """'2026-11' -> a whole number of months, so ages are plain subtraction."""
    year, mon = str(month)[:7].split("-")
    return int(year) * 12 + int(mon) - 1


def _usd(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def run(shop: str, months: list[dict], *, cap_usd: float = DEFAULT_CAP_USD,
        confirmed_rate: float = CONFIRMED_RATE, estimated_rate: float = ESTIMATED_RATE,
        sunset_months: int = SUNSET_MONTHS) -> list[dict]:
    """One statement per month, in order.

    `months` is the shop's banked results, oldest first. Each is:

        {"month": "2026-03",
         "dollars": [{"id": "d-17", "usd": 412.50, "grade": "isolated",
                      "month": "2026-03"}, ...],   # month defaults to the result's
         "lower_bound": 380.0,      # optional: cumulative book p25 after this month
         "disputed": ["d-4"],       # optional: ids the brand disputed this month
         "cap_usd": 750.0}          # optional: the merchant raised the cap

    A negative `usd` is a loss from a Hubricon move. Grade "none" banks nothing
    (measurement could not isolate it) and is skipped."""
    record: dict[str, dict] = {}    # id -> the dollar, with what it has been charged
    struck: set[str] = set()
    peak = 0.0
    out = []
    prev = None
    for m in months:
        now = month_index(m["month"])
        if prev is not None and now <= prev:
            raise ValueError(f"months must be in order: {m['month']} after index {prev}")
        prev = now
        lines: list[str] = []

        # 1. Strike disputed dollars and refund what they paid.
        refunds = 0.0
        refunded_ids = []
        for did in m.get("disputed") or []:
            d = record.get(did)
            if d is None or did in struck:
                lines.append(f"Dispute on {did}: no such dollar on the Record, nothing to strike.")
                continue
            if d["usd"] <= 0:
                lines.append(f"Dispute on {did}: it is a loss of {_usd(d['usd'])}, and losses stay "
                             f"on the Record so they keep holding fees back.")
                continue
            struck.add(did)
            refunds += d["fee_paid"]
            peak = max(0.0, peak - d["consumed"])
            refunded_ids.append(did)
            lines.append(f"You disputed {did} ({_usd(d['usd'])}). It is struck from the Record"
                         + (f" and the {_usd(d['fee_paid'])} it was charged is refunded below."
                            if d["fee_paid"] > EPS else "; it had not been charged."))
            del record[did]

        # 2. Bank this month's dollars.
        for raw in m.get("dollars") or []:
            if (raw.get("grade") or "").strip().lower() == "none":
                continue
            did = str(raw["id"])
            if did in record or did in struck:
                raise ValueError(f"dollar {did} banked twice")
            usd = float(raw["usd"])
            record[did] = {"id": did, "usd": usd, "grade": grade_of(raw["grade"]),
                           "banked": month_index(raw.get("month") or m["month"]),
                           "consumed": 0.0, "fee_paid": 0.0}

        # 3. The cumulative lower bound: never above the Record's own sum.
        point = sum(d["usd"] for d in record.values())
        lb = m.get("lower_bound")
        cumulative = point if lb is None else min(float(lb), point)
        losses = sum(d["usd"] for d in record.values() if d["usd"] < 0)

        # 4. Compare with the peak.
        peak_before = peak
        rise = max(0.0, cumulative - peak_before)
        peak = max(peak, cumulative)

        # 5. Match the rise to feeable dollars, oldest first, estimated before
        #    confirmed within a month. Anything left over belongs to dollars past
        #    their sunset (or to a lower bound the Record cannot name a dollar for).
        feeable = sorted(
            (d for d in record.values()
             if d["usd"] > 0 and d["usd"] - d["consumed"] > EPS and now - d["banked"] < sunset_months
             and d["banked"] <= now),
            key=lambda d: (d["banked"], d["grade"] != "estimated", d["id"]))
        left = rise
        take: list[tuple[dict, float]] = []
        for d in feeable:
            if left <= EPS:
                break
            amt = min(left, d["usd"] - d["consumed"])
            take.append((d, amt))
            left -= amt
        sunset_excluded = max(0.0, left)
        sunset_old = sum(d["usd"] - d["consumed"] for d in record.values()
                         if d["usd"] > 0 and now - d["banked"] >= sunset_months
                         and d["usd"] - d["consumed"] > EPS)

        # 6. Rate.
        feeable_confirmed = sum(a for d, a in take if d["grade"] == "confirmed")
        feeable_estimated = sum(a for d, a in take if d["grade"] == "estimated")
        fee_raw = confirmed_rate * feeable_confirmed + estimated_rate * feeable_estimated

        # 7. Cap. The excess is forgiven, not owed.
        cap = float(m.get("cap_usd", cap_usd))
        fee = min(fee_raw, cap)
        capped = fee_raw > cap + EPS
        scale = fee / fee_raw if fee_raw > EPS else 0.0
        for d, amt in take:
            d["consumed"] += amt
            rate = confirmed_rate if d["grade"] == "confirmed" else estimated_rate
            d["fee_paid"] += rate * amt * scale

        # The glass box: the same numbers, in sentences.
        expl = [f"Your Record's cumulative proven total (its {'lower bound' if lb is not None else 'sum'}) "
                f"is {_usd(cumulative)}; the highest it has been before this month is {_usd(peak_before)}."]
        if losses < -EPS:
            expl.append(f"That total already has {_usd(-losses)} of losses from our moves taken off. "
                        f"Losses come off first, so nothing is charged until they are earned back.")
        if rise <= EPS:
            expl.append("It did not pass its previous high, so there is no fee this month.")
        else:
            expl.append(f"It rose {_usd(rise)} above its previous high. Only that rise can be charged.")
            if feeable_confirmed > EPS:
                expl.append(f"{_usd(feeable_confirmed)} of it is confirmed (platform record or "
                            f"randomised test), charged at {confirmed_rate:.0%}.")
            if feeable_estimated > EPS:
                expl.append(f"{_usd(feeable_estimated)} of it is estimated (modelled or pooled), "
                            f"charged at {estimated_rate:.0%}.")
            if sunset_excluded > EPS:
                expl.append(f"{_usd(sunset_excluded)} of the rise is not charged: the dollars behind it "
                            f"are more than {sunset_months} months old and now belong to you.")
        if sunset_old > EPS:
            expl.append(f"{_usd(sunset_old)} of proven dollars on your Record are past their "
                        f"{sunset_months}-month sunset and will never be charged.")
        if capped:
            expl.append(f"The fee would have been {_usd(fee_raw)}, above your {_usd(cap)} monthly cap. "
                        f"We charge {_usd(cap)} and the {_usd(fee_raw - cap)} above it is not carried "
                        f"forward. Billing is paused until the Record sets a new high.")
        elif fee > EPS:
            expl.append(f"Fee this month: {_usd(fee)}.")
        if refunds > EPS:
            expl.append(f"Refunded for disputed dollars: {_usd(refunds)}.")
        net = fee - refunds
        if refunds > EPS or fee > EPS:
            expl.append(f"Net this month: {_usd(net)}" +
                        (" (a refund to you)." if net < -EPS else "."))

        out.append({
            "shop": shop,
            "month": m["month"],
            "peak_before": round(peak_before, 2),
            "cumulative": round(cumulative, 2),
            "cumulative_point": round(point, 2),
            "losses": round(losses, 2),
            "rise": round(rise, 2),
            "feeable_confirmed": round(feeable_confirmed, 2),
            "feeable_estimated": round(feeable_estimated, 2),
            "sunset_excluded": round(sunset_excluded, 2),
            "fee_before_cap": round(fee_raw, 2),
            "cap_usd": round(cap, 2),
            "fee": round(fee, 2),
            "capped": capped,
            "capped_usd": round(max(0.0, fee_raw - cap), 2),
            "refunds": round(refunds, 2),
            "refunded_ids": refunded_ids,
            "net": round(net, 2),
            "peak_after": round(peak, 2),
            "explanation": lines + expl,
        })
    return out
