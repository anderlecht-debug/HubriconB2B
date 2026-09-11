"""Did the money actually move?

Every dollar on the Decision Ledger used to require a founder typing
`hubricon measure --impact <number>`. Nobody types, so the ledger sat at zero
and the portal told paying clients they were getting `0.0x — at risk`. This
module measures a directive's outcome from the client's OWN later exports, so
the retention case rebuilds itself every Monday.

Pure, like value.py and the models: dicts in, verdicts out, no database. The
IO wrapper lives in cli._measure_for_run.

THE ATTRIBUTION STANDARD
------------------------
Every measured dollar is labelled with how we know it, and the label ships to
the client in the ledger's "how we know" column:

  direct        A counterparty's own record, in the client's own export, shows
                the money moved. Amazon approved a reimbursement we filed.
                Full credit.
  isolated      The measured quantity is the exact line the directive named,
                against that line's own pre-change level. Credit is the
                observed delta times the observed volume.
  attributable  The outcome is confounded by demand, so credit is the
                difference from a stated counterfactual, computed with the same
                model that made the promise and evaluated at the LEAST
                favourable end of its own confidence interval.
  none          We could not isolate it. We say so and bank nothing.

Four guards apply to every family, so no measurement can quietly skip them:

  1. Cap at the promise. An isolated/attributable measurement is capped at
     `expected_impact_usd`; the excess is recorded and named, never totalled.
     (Direct is exempt: a claim pays face value, which legitimately exceeds
     our expected-value estimate.)
  2. Materiality floor. Under MEASURE_MIN_USD the directive closes rather than
     banking noise.
  3. Persistence. An effect must still be present in the latest export. One
     lucky period is not a result.
  4. One dollar, one directive. The same (sku, period) margin movement is
     credited to at most one directive, oldest first.

The bias is deliberate and one-directional: prefer under-claiming. A ledger
that occasionally under-counts survives a skeptical CFO. One that over-counts
once is never trusted again.
"""

from datetime import date

MEASURE_MIN_USD = 25.0          # below this, close it rather than bank noise
MIN_AFTER_DAYS = 14             # an after-window shorter than this proves nothing
PRICE_TOLERANCE = 0.02          # observed vs instructed price, before we call it unexecuted
CAMPAIGN_ALIVE_SHARE = 0.05     # under this share of baseline spend, the campaign was paused
SCHEDULE_CHANGE_SHARE = 0.5     # this share of the catalog moving together is Amazon, not us
BUYBOX_DROP_ALERT = 10.0        # percentage points; mirrors alerts.BUYBOX_DROP_ALERT
UNIT_ELASTIC = -1.0             # assumed when no fit exists: the most demand-destroying ordinary case

# Executed, but nothing a later export could honestly value. We prove the work
# happened and bank nothing — directives.py already refuses to promise dollars
# for these, and measurement must not invent them afterwards.
UNBANKABLE_KINDS = {
    "inventory_reorder",      # avoided stockout: the counterfactual is unobservable
    "conversion_watch",       # real exposure, but it moves with season and competitors
    "traffic_watch",
    "buybox_watch",
    "settlement_step",        # "we are tracing the lines" is not an action with a proof
}


# ── verdict helpers ──────────────────────────────────────────────────────────

def _verdict(d: dict, verdict: str, notes: str, *, usd=None, attribution="none",
             evidence_after=None, window=None) -> dict:
    """Guard 1 lives here, so no family can skip it.

    The site says every dollar is "capped at what we promised", and it says it
    about the Profit Record as a whole. Each measurement used to apply its own
    min() and `measure_ad_bleed` never did, which made the page stricter than
    the code on the most common move we make. Capping centrally means a new
    measurement family is born compliant instead of being audited into it.

    The cap is one-directional: a miss is banked in full, an overshoot is
    banked at the promise and the excess is named in the evidence so the note
    can say what really happened. `direct` is exempt by design — a claim pays
    what Amazon pays, which legitimately exceeds our expected value."""
    evidence_after = dict(evidence_after or {})
    promised = d.get("expected_impact_usd")
    if (usd is not None and promised is not None
            and attribution in ("isolated", "attributable")):
        promised = float(promised)
        if float(usd) > promised:
            evidence_after["measured_before_cap"] = round(float(usd), 2)
            evidence_after["capped_at_promise"] = round(promised, 2)
            usd = round(promised, 2)
    return {
        "directive_id": d.get("id"),
        "kind": d.get("kind"),
        "verdict": verdict,
        "measured_impact_usd": usd,
        "attribution": attribution,
        "measurement_notes": notes,
        "evidence_after": evidence_after,
        "window": window,
    }


def _not_yet(d: dict, why: str) -> dict:
    """Not enough data yet is NOT a zero. Banking zero because an export has not
    landed would record a miss we have no evidence for."""
    return _verdict(d, "not_yet", why)


def _closed(d: dict, why: str, evidence_after=None) -> dict:
    return _verdict(d, "closed", why, evidence_after=evidence_after)


STALE_AFTER_DAYS = 90


def _stalled(d: dict, why: str, since: date, today: date, window=None) -> dict:
    """Nothing to measure YET, because the action has not happened.

    Distinct from "we cannot attribute this": a price step that was approved
    and never made could still be made next week, and closing it on the first
    sweep would mean never measuring it. Retried until the trail is cold, then
    closed honestly as never carried out."""
    if (today - since).days >= STALE_AFTER_DAYS:
        return _verdict(d, "closed", why + f" Still true {STALE_AFTER_DAYS} days on, so it is closed "
                                           f"as never carried out rather than left open forever.",
                        window=window)
    return _verdict(d, "not_yet", why, window=window)


def _period_days(row: dict) -> float:
    a, b = row.get("period_start"), row.get("period_end")
    if not a or not b:
        return 0.0
    return max(1.0, (date.fromisoformat(str(b)[:10]) - date.fromisoformat(str(a)[:10])).days + 1)


def _acted_on(d: dict) -> date | None:
    stamp = d.get("executed_at") or d.get("responded_at") or d.get("issued_at")
    return date.fromisoformat(str(stamp)[:10]) if stamp else None


def _after_rows(rows: list[dict], since: date | None, today: date) -> list[dict]:
    """Export periods that began after we acted and have run long enough to say
    anything. A window shorter than MIN_AFTER_DAYS is silence, not evidence."""
    if since is None:
        return []
    out = []
    for r in rows:
        start = r.get("period_start")
        if not start or date.fromisoformat(str(start)[:10]) <= since:
            continue
        if _period_days(r) < MIN_AFTER_DAYS and date.fromisoformat(str(r["period_end"])[:10]) < today:
            continue
        out.append(r)
    return sorted(out, key=lambda r: str(r["period_start"]))


# ── Tier A: direct, counterparty-confirmed ───────────────────────────────────

def measure_recovery_filing(d: dict, claims_by_key: dict) -> dict:
    """Amazon's own approval, in the client's own reimbursement export.

    Face value beats our expected-value estimate here and that is correct: the
    promise was `units x value x P(approved)`, and what Amazon actually sent is
    not capped by our guess at the odds."""
    keys = (d.get("evidence") or {}).get("claim_keys") or []
    if not keys:
        return _closed(d, "No claim keys recorded on this directive.")
    seen = [claims_by_key[k] for k in keys if k in claims_by_key]
    if not seen:
        return _not_yet(d, "None of these claims have been settled or denied yet.")

    paid = [c for c in seen if c.get("status") == "paid"]
    settled = sum(float(c.get("paid_amount") or 0) for c in paid)
    denied = [c for c in seen if c.get("status") == "denied"]
    expired = [c for c in seen if c.get("status") == "expired"]
    still_open = [c for c in seen if c.get("status") in ("detected", "filed")]
    if still_open and not paid:
        return _not_yet(d, f"{len(still_open)} of {len(keys)} claims are still with Amazon.")

    # A claim we never filed was reimbursed by Amazon's own reconciliation. It
    # is the client's money either way, but it is not our result.
    ours = [c for c in paid if c.get("filed_at") or c.get("case_id")]
    banked = sum(float(c.get("paid_amount") or 0) for c in ours)
    note = (f"Amazon settled {len(paid)} of {len(keys)} claims for ${settled:,.2f}; "
            f"${banked:,.2f} of that is on claims we filed.")
    if denied:
        note += f" {len(denied)} denied."
    if expired:
        note += f" {len(expired)} expired unfiled."
    if still_open:
        note += f" {len(still_open)} still open."
    return _verdict(d, "measured", note, usd=round(banked, 2), attribution="direct",
                    evidence_after={"settled_total": round(settled, 2), "n_paid": len(paid),
                                    "n_denied": len(denied), "n_expired": len(expired)})


# ── Tier B: isolated ─────────────────────────────────────────────────────────

def measure_ad_bleed(d: dict, search_terms: list[dict], since: date, today: date) -> dict:
    """The named terms stopped spending, and the campaign did not simply stop.

    Two guards keep this from stealing credit. If the whole campaign went dark,
    the saving was not ours; and we can never claim to have saved more on a
    handful of terms than the campaign's total spend actually fell."""
    ev = d.get("evidence") or {}
    terms = ev.get("terms") or []
    if not terms:
        return _closed(d, "No term list recorded on this directive.")

    after = _after_rows(search_terms, since, today)
    if not after:
        return _not_yet(d, f"No search-term export covering {MIN_AFTER_DAYS}+ days since the change.")
    window = (str(after[0]["period_start"]), str(after[-1]["period_end"]))
    # Distinct export periods, not rows: one period holds many search terms, and
    # summing its length once per term would inflate the prorated baseline.
    seen_periods = {(str(r["period_start"]), str(r["period_end"])): r for r in after}
    after_days = sum(_period_days(r) for r in seen_periods.values())

    named = {(t.get("campaign_name"), t.get("search_term")) for t in terms}
    campaigns = {t.get("campaign_name") for t in terms}
    baseline_by_term = {(t.get("campaign_name"), t.get("search_term")): float(t.get("spend") or 0) for t in terms}
    baseline_days = ev.get("baseline_days") or 30.0

    after_term_spend, after_campaign_spend = {}, {}
    for r in after:
        key = (r.get("campaign_name"), r.get("search_term"))
        spend = float(r.get("spend") or 0)
        if key in named:
            after_term_spend[key] = after_term_spend.get(key, 0.0) + spend
        if r.get("campaign_name") in campaigns:
            after_campaign_spend[r["campaign_name"]] = after_campaign_spend.get(r["campaign_name"], 0.0) + spend

    # Prorate the baseline onto the after-window before comparing.
    scale = after_days / baseline_days if baseline_days else 1.0
    baseline_campaign = {}
    for (camp, _term), spend in baseline_by_term.items():
        baseline_campaign[camp] = baseline_campaign.get(camp, 0.0) + spend

    # The campaign's own total spend before, so the cap below compares like
    # with like. Absent on directives drafted before this was recorded, in
    # which case the cap is skipped rather than applied wrongly.
    campaign_baseline_total = ev.get("campaign_baseline_spend") or {}

    saved, dead = 0.0, []
    for camp in campaigns:
        bleed_expected = baseline_campaign.get(camp, 0.0) * scale
        actual_camp = after_campaign_spend.get(camp, 0.0)
        # Did the campaign keep running? If it went dark, whatever was "saved"
        # on these terms was not saved by the negative match.
        alive_against = float(campaign_baseline_total.get(camp) or bleed_expected) * scale \
            if camp in campaign_baseline_total else bleed_expected
        if alive_against > 0 and actual_camp < alive_against * CAMPAIGN_ALIVE_SHARE:
            dead.append(camp)
            continue
        camp_saved = 0.0
        for (c, term), spend in baseline_by_term.items():
            if c != camp:
                continue
            camp_saved += max(0.0, spend * scale - after_term_spend.get((c, term), 0.0))
        # You cannot save more on terms than the campaign's whole spend fell.
        whole_before = float(campaign_baseline_total.get(camp) or 0) * scale
        if whole_before > 0:
            camp_saved = min(camp_saved, max(0.0, whole_before - actual_camp))
        saved += camp_saved

    if dead and saved <= 0:
        return _verdict(d, "unmeasurable",
                        f"Campaign{'s' if len(dead) > 1 else ''} {', '.join(sorted(map(str, dead)))} stopped "
                        f"spending entirely in the measured window; the saving is not attributable to the "
                        f"negative match.", window=window)

    note = (f"The {len(terms)} negative-matched term(s) spent ${sum(after_term_spend.values()):,.2f} in "
            f"{window[0]} → {window[1]}, against ${sum(baseline_by_term.values()) * scale:,.2f} at the "
            f"prior rate — ${saved:,.2f} saved.")
    if dead:
        note += f" Excludes {', '.join(sorted(map(str, dead)))}, which went dark for other reasons."
    # Guard 1 caps the banked figure in _verdict; say so in the note rather than
    # letting the client read a number here that the Record does not carry.
    promised = d.get("expected_impact_usd")
    if promised is not None and saved > float(promised):
        note += (f" Banked at the ${float(promised):,.2f} we promised — the extra "
                 f"${saved - float(promised):,.2f} is recorded, not claimed.")
    return _verdict(d, "measured", note, usd=round(saved, 2), attribution="isolated",
                    evidence_after={"after_spend": round(sum(after_term_spend.values()), 2),
                                    "prorated_baseline": round(sum(baseline_by_term.values()) * scale, 2),
                                    "excluded_campaigns": sorted(map(str, dead))},
                    window=window)


def _sku_fee_series(econ: list[dict]) -> dict:
    """(sku, metric) -> [(period_start, value, units, sales)] for the fee metrics
    the anomaly detector watches. Built from the same fields models/anomaly.py
    reads, so a flag and its measurement can never disagree about what
    `fee_per_unit` means."""
    out: dict = {}
    for r in econ:
        sku, period = r.get("sku"), r.get("period_start")
        if not sku or not period:
            continue
        units = float(r.get("units_sold") or 0)
        sales = float(r.get("sales") or 0)
        fba = r.get("fba_fulfillment_fees")
        referral = r.get("referral_fees")
        known = [v for v in (referral, fba, r.get("storage_fees"), r.get("other_fees")) if v is not None]
        if units > 0:
            if known:
                out.setdefault((sku, "fee_per_unit"), []).append((period, sum(map(float, known)) / units, units, sales))
            if fba is not None:
                out.setdefault((sku, "fba_fee_per_unit"), []).append((period, float(fba) / units, units, sales))
        if sales > 0 and referral is not None:
            out.setdefault((sku, "referral_rate"), []).append((period, float(referral) / sales, units, sales))
    for series in out.values():
        series.sort(key=lambda t: str(t[0]))
    return out


def measure_fee_anomaly(d: dict, econ: list[dict], since: date, today: date) -> dict:
    """The flagged fee came back down, and it was not the whole catalog moving.

    The control group is free and lives in the client's own SKUs: if the same
    metric fell across half the catalog in the same period, Amazon changed a
    rate card and we did not fix anything."""
    ev = d.get("evidence") or {}
    sku, metric = ev.get("item_id"), ev.get("metric")
    baseline, flagged = ev.get("baseline"), ev.get("current")
    if not sku or not metric or baseline is None or flagged is None:
        return _closed(d, "No metric baseline recorded on this directive.")
    if flagged <= baseline:
        return _closed(d, "The flagged level was not above baseline; nothing to recover.")

    series = _sku_fee_series(econ)
    ours = [p for p in series.get((sku, metric), []) if date.fromisoformat(str(p[0])[:10]) > since]
    if not ours:
        return _not_yet(d, f"No {metric} reading for {sku} since the correction.")

    period, current, units, sales = ours[-1]
    volume = sales if metric == "referral_rate" else units
    if volume <= 0:
        return _not_yet(d, f"{sku} recorded no volume in {period}; nothing to value the change against.")

    if current >= flagged:
        return _verdict(d, "measured",
                        f"{metric} on {sku} is still {current:,.4f} in {period}, at or above the flagged "
                        f"{flagged:,.4f}. Nothing recovered yet, and the record says so.",
                        usd=0.0, attribution="isolated", window=(str(period), str(period)))

    # Amazon moving a whole rate card is not our correction.
    movers, watched = 0, 0
    for (other_sku, other_metric), points in series.items():
        if other_metric != metric:
            continue
        before = [v for p, v, _u, _s in points if date.fromisoformat(str(p)[:10]) <= since]
        after = [v for p, v, _u, _s in points if date.fromisoformat(str(p)[:10]) > since]
        if not before or not after:
            continue
        watched += 1
        if after[-1] < before[-1] * 0.99:
            movers += 1
    if watched >= 3 and movers / watched >= SCHEDULE_CHANGE_SHARE:
        return _verdict(d, "unmeasurable",
                        f"{metric} fell on {movers} of {watched} SKUs in the same period — a fee-schedule "
                        f"change, not a correction of ours. Nothing banked.",
                        window=(str(period), str(period)))

    # A fee below its own pre-anomaly level is Amazon, not us.
    recovered = (flagged - current) * volume
    capped = min(recovered, (flagged - baseline) * volume)
    note = (f"{metric} on {sku} fell from {flagged:,.4f} to {current:,.4f} by {period} — "
            f"${capped:,.2f} across {volume:,.0f} {'in sales' if metric == 'referral_rate' else 'units'}.")
    if capped < recovered:
        note += f" Capped at the pre-anomaly level of {baseline:,.4f}; the rest was not ours to claim."
    return _verdict(d, "measured", note, usd=round(capped, 2), attribution="isolated",
                    evidence_after={"after": current, "volume": volume, "period": str(period),
                                    "uncapped": round(recovered, 2)},
                    window=(str(period), str(period)))


def measure_spend_step(d: dict, ppc_spend: list[dict], since: date, today: date) -> dict:
    """Daily spend that stepped up came back to its prior level."""
    ev = d.get("evidence") or {}
    campaign, baseline, flagged = ev.get("item_id"), ev.get("baseline"), ev.get("current")
    if baseline is None or flagged is None or flagged <= baseline:
        return _closed(d, "No spend step-up recorded on this directive.")

    rows = [r for r in ppc_spend
            if str(r.get("campaign_name") or "") == str(campaign or "")
            and r.get("date") and date.fromisoformat(str(r["date"])[:10]) > since]
    if len(rows) < MIN_AFTER_DAYS:
        return _not_yet(d, f"Only {len(rows)} day(s) of spend since the correction; {MIN_AFTER_DAYS} needed.")
    daily = sum(float(r.get("spend") or 0) for r in rows) / len(rows)
    if daily >= flagged:
        return _verdict(d, "measured",
                        f"Daily spend on “{campaign}” is still ${daily:,.2f} against the flagged ${flagged:,.2f}. "
                        f"The step-up was confirmed as intended, or it has not been held down.",
                        usd=0.0, attribution="isolated")
    saved = (flagged - daily) * len(rows)
    capped = min(saved, (flagged - baseline) * len(rows))
    return _verdict(d, "measured",
                    f"Daily spend on “{campaign}” came down from ${flagged:,.2f} to ${daily:,.2f} across "
                    f"{len(rows)} days — ${capped:,.2f} held back.",
                    usd=round(capped, 2), attribution="isolated",
                    evidence_after={"daily_after": round(daily, 2), "days": len(rows)})


def measure_fee_bleed(d: dict, inv_econ: dict | None, since: date, today: date) -> dict:
    """The fee line came off, and the client's own Inventory Health export says so.

    Isolated rather than direct: Amazon's export shows the charge is gone, but
    it does not say we are why. Credit is the fall in the named SKUs' own
    charge, floored at zero and capped at what was being billed."""
    kind = d.get("kind")
    ev = d.get("evidence") or {}
    field = {
        "low_inventory_fee": "low_inventory_fee_month",
        "aged_surcharge": "aged_surcharge_month",
        "peak_storage_premium": "peak_storage_premium_month",
    }[kind]
    before_per_sku = ev.get("per_sku") or {}
    before_total = float(ev.get("monthly_fee") or ev.get("monthly_surcharge") or ev.get("monthly_premium") or 0)
    if not before_total:
        return _closed(d, "No fee baseline recorded on this directive.")
    if kind == "peak_storage_premium" and ev.get("already_in_peak"):
        return _closed(d, "The peak window had already opened when this was raised; the premium was "
                          "spent, and nothing is claimed for it.")

    rows = (inv_econ or {}).get("rows") or []
    if not rows:
        return _not_yet(d, "No inventory-economics read since the change.")
    named = set(ev.get("skus") or before_per_sku.keys())
    after_rows = [r for r in rows if r.get("sku") in named]
    if not after_rows:
        return _not_yet(d, "None of the named SKUs appear in the latest inventory export.")

    after_total = sum(float(r.get(field) or 0) for r in after_rows)
    saved = max(0.0, before_total - after_total)
    if saved < MEASURE_MIN_USD:
        return _verdict(d, "measured",
                        f"The charge is still ${after_total:,.2f}/month against ${before_total:,.2f} before — "
                        f"it has not come off yet.", usd=0.0, attribution="isolated")
    promised = d.get("expected_impact_usd")
    capped = min(saved, float(promised)) if promised is not None and saved > float(promised) > 0 else saved
    gone = [r["sku"] for r in after_rows if not float(r.get(field) or 0)]
    return _verdict(d, "measured",
                    f"The monthly charge on these SKUs fell from ${before_total:,.2f} to ${after_total:,.2f} "
                    f"in your own inventory export"
                    + (f"; it is gone entirely on {', '.join(sorted(gone)[:4])}"
                       f"{'…' if len(gone) > 4 else ''}." if gone else "."),
                    usd=round(capped, 2), attribution="isolated",
                    evidence_after={"after_total": round(after_total, 2), "cleared_skus": sorted(gone)})


# ── Tier C: attributable, against a stated counterfactual ────────────────────

def _split_fees(row: dict) -> tuple[float, float]:
    """(proportional, fixed) fee dollars for one margin row. A row with no
    itemised split — an older run, or a channel that reports one blended fee
    line — puts everything in the proportional bucket, which is what the
    engine assumed before the split existed."""
    split = row.get("fee_split") or {}
    if split.get("basis") == "itemized":
        return (float(split.get("proportional_fees") or 0),
                float(split.get("fixed_fees") or 0))
    return float(row.get("amazon_fees") or 0), 0.0


def _observed(rows: list[dict]) -> dict | None:
    """Actual profit for a set of margin rows: revenue less fees, cost and ads.
    The factual side is never modelled — only the counterfactual is."""
    if not rows:
        return None
    units = sum(float(r.get("units") or 0) for r in rows)
    revenue = sum(float(r.get("revenue") or 0) for r in rows)
    if units <= 0 or revenue <= 0:
        return None
    return {
        "units": units, "revenue": revenue,
        "price": revenue / units,
        "fees": sum(float(r.get("amazon_fees") or 0) for r in rows),
        # the same split pricing_engine priced the promise with, summed over
        # the measured window, so the counterfactual charges a fixed FBA fee
        # per unit rather than a percentage of a price that changed
        "proportional_fees": sum(_split_fees(r)[0] for r in rows),
        "fixed_fees": sum(_split_fees(r)[1] for r in rows),
        "cogs": sum(float(r.get("cogs") or 0) for r in rows),
        "ads": sum(float(r.get("ad_spend_allocated") or 0) for r in rows),
        "net": sum(float(r.get("net_margin") or 0) for r in rows),
        "periods": sorted(str(r["period_start"]) for r in rows),
    }


def _counterfactual_profit(eps: float, p0: float, p1: float, units_after: float,
                           unit_cost: float, fee_rate: float, fixed_fee: float = 0.0) -> float:
    """What the SKU would have earned at the old price, given the volume it
    actually did at the new one.

    Anchoring on the AFTER period's own units is the whole point: whatever
    demand shock, season or competitor hit that period hit the factual and the
    counterfactual identically, so it cancels. Rolling forward from a stale
    baseline period would credit us with the weather."""
    q_cf = units_after * (p0 / p1) ** eps if p1 > 0 else units_after
    return q_cf * (p0 * (1 - fee_rate) - unit_cost - fixed_fee)


def measure_price_step(d: dict, margins: list[dict], traffic: list[dict],
                       since: date, today: date) -> dict:
    ev = d.get("evidence") or {}
    sku, p0, p_new = ev.get("sku"), ev.get("p0"), ev.get("p_new")
    if not sku or not p0:
        return _closed(d, "No price baseline recorded on this directive.")

    after_rows = [m for m in margins if m.get("sku") == sku and m.get("period_start")
                  and date.fromisoformat(str(m["period_start"])[:10]) > since]
    after = _observed(after_rows)
    if not after:
        return _not_yet(d, f"No margin period for {sku} since the change.")
    window = (after["periods"][0], after["periods"][-1])

    # Gate on execution. This kills the largest class of false credit: a step
    # that was recommended, approved, and never actually made in the account.
    p1 = after["price"]
    if p_new and abs(p1 - p_new) / p_new > PRICE_TOLERANCE and abs(p1 - p0) / p0 <= PRICE_TOLERANCE:
        return _stalled(d, f"The price on file for {sku} is still ${p1:,.2f} — the step to "
                           f"${p_new:,.2f} has not been made, so there is nothing to measure.",
                        since, today, window)

    if after["revenue"] <= 0 or after["units"] <= 0:
        return _not_yet(d, f"{sku} recorded no sales in the measured window.")
    unit_cost = after["cogs"] / after["units"] if after["cogs"] else None
    if unit_cost is None or unit_cost <= 0:
        return _closed(d, f"No landed cost on file for {sku}; the counterfactual cannot be priced honestly.")
    fee_rate = min(0.9, max(0.0, after["proportional_fees"] / after["revenue"]))
    fixed_fee = after["fixed_fees"] / after["units"] if after["units"] > 0 else 0.0

    eps = ev.get("elasticity")
    ci = ev.get("ci95") or []
    candidates = [e for e in ([eps] + list(ci)) if e is not None]
    if not candidates:
        candidates = [UNIT_ELASTIC]

    factual = after["revenue"] - after["fees"] - after["cogs"]
    # Bank the LEAST favourable reading of our own fit: a wide confidence
    # interval costs us credit, which is the incentive we want.
    deltas = [factual - _counterfactual_profit(float(e), p0, p1, after["units"], unit_cost,
                                               fee_rate, fixed_fee)
              for e in candidates]
    delta = min(deltas)

    promised = d.get("expected_impact_usd")
    capped = delta
    if promised is not None and delta > float(promised) > 0:
        capped = float(promised)

    # Never suppress a loss: if the step cost the Featured Offer, that belongs
    # on the record at its measured value, negative or not.
    buybox_note = ""
    before_bb = [float(t["buy_box_pct"]) for t in traffic
                 if t.get("sku") == sku and t.get("buy_box_pct") is not None
                 and t.get("period_start") and date.fromisoformat(str(t["period_start"])[:10]) <= since]
    after_bb = [float(t["buy_box_pct"]) for t in traffic
                if t.get("sku") == sku and t.get("buy_box_pct") is not None
                and t.get("period_start") and date.fromisoformat(str(t["period_start"])[:10]) > since]
    if before_bb and after_bb and before_bb[-1] - after_bb[-1] >= BUYBOX_DROP_ALERT:
        buybox_note = (f" Buy Box share fell {before_bb[-1] - after_bb[-1]:.0f} points over the same window — "
                       f"the step cost the Featured Offer.")

    if abs(capped) < MEASURE_MIN_USD and not buybox_note:
        return _closed(d, f"The step moved less than ${MEASURE_MIN_USD:,.0f} on {sku}; not material.",
                       evidence_after={"delta": round(delta, 2)})

    note = (f"{sku} sold {after['units']:,.0f} units at ${p1:,.2f} in {window[0]} → {window[1]}, "
            f"earning ${factual:,.2f} before ads. At the old ${p0:,.2f}, the fitted curve "
            f"(ε {min(candidates):.2f} to {max(candidates):.2f}) puts the same demand at "
            f"${factual - delta:,.2f} — a difference of ${delta:,.2f}, taken at the least favourable "
            f"end of the confidence interval.{buybox_note}")
    if capped != delta:
        note += f" Capped at the ${float(promised):,.2f} we promised."
    return _verdict(d, "measured", note, usd=round(capped, 2), attribution="attributable",
                    evidence_after={"p1": round(p1, 2), "units_after": after["units"],
                                    "factual_profit": round(factual, 2), "uncapped": round(delta, 2),
                                    "elasticities": candidates},
                    window=window)


def measure_negative_margin(d: dict, margins: list[dict], inventory: list[dict],
                            since: date, today: date) -> dict:
    """Reprice, cut the ads, or exit — the instruction is a menu, so read from
    the client's own data which one happened before valuing it."""
    ev = d.get("evidence") or {}
    sku = ev.get("sku")
    before_net = float(ev.get("baseline_net") or 0)
    before_units = float(ev.get("baseline_units") or 0)
    before_revenue = float(ev.get("baseline_revenue") or 0)
    before_ads = float(ev.get("baseline_ad_spend") or 0)
    if not sku:
        return _closed(d, "No SKU recorded on this directive.")
    p0 = before_revenue / before_units if before_units > 0 else None

    after_rows = [m for m in margins if m.get("sku") == sku and m.get("period_start")
                  and date.fromisoformat(str(m["period_start"])[:10]) > since]
    if not after_rows:
        return _not_yet(d, f"No margin period for {sku} since the change.")
    after = _observed(after_rows)
    window = (sorted(str(r["period_start"]) for r in after_rows)[0],
              sorted(str(r["period_start"]) for r in after_rows)[-1])

    if after is None:
        # Zero units. An exit only counts as one if the listing was pulled;
        # a stockout booked as a deliberate exit is exactly the number this
        # ledger exists not to print.
        on_hand = sum(float(r.get("on_hand_units") or 0) + float(r.get("inbound_units") or 0)
                      for r in inventory if r.get("sku") == sku)
        if on_hand > 0:
            return _stalled(d, f"{sku} sold nothing in {window[0]} → {window[1]} while still holding "
                               f"{on_hand:,.0f} units — that is a stockout or a suppressed listing, "
                               f"not an exit, so nothing is banked for it.",
                            since, today, window)
        saved = -before_net
        return _verdict(d, "measured",
                        f"{sku} was exited: no units sold and no stock held in {window[0]} → {window[1]}, "
                        f"against ${before_net:,.2f} of net loss in the baseline period.",
                        usd=round(min(saved, float(d.get("expected_impact_usd") or saved)), 2),
                        attribution="attributable", window=window)

    if p0 and after["price"] > p0 * (1 + PRICE_TOLERANCE):
        # Repriced. No fit on a loss-making SKU, so assume unit-elastic — the
        # most demand-destroying ordinary case, which gives the smallest credit.
        unit_cost = after["cogs"] / after["units"] if after["cogs"] else None
        if not unit_cost:
            return _closed(d, f"No landed cost on file for {sku}; the reprice cannot be valued honestly.")
        fee_rate = min(0.9, max(0.0, after["fees"] / after["revenue"]))
        factual = after["revenue"] - after["fees"] - after["cogs"]
        cf = _counterfactual_profit(UNIT_ELASTIC, p0, after["price"], after["units"], unit_cost, fee_rate)
        delta = factual - cf
        promised = d.get("expected_impact_usd")
        capped = min(delta, float(promised)) if promised is not None and delta > float(promised) > 0 else delta
        if abs(capped) < MEASURE_MIN_USD:
            return _closed(d, f"The reprice moved less than ${MEASURE_MIN_USD:,.0f} on {sku}.")
        return _verdict(d, "measured",
                        f"{sku} was repriced ${p0:,.2f} → ${after['price']:,.2f}. Against the same demand at "
                        f"the old price, assuming unit-elastic demand (no fit exists for a loss-making SKU, "
                        f"so we take the assumption that credits us least), the difference is ${delta:,.2f}.",
                        usd=round(capped, 2), attribution="attributable", window=window)

    if before_ads > 0 and after["ads"] < before_ads:
        cut = before_ads - after["ads"]
        improvement = after["net"] - before_net
        credit = max(0.0, min(cut, improvement))
        if credit < MEASURE_MIN_USD and improvement >= 0:
            return _closed(d, f"The ad cut on {sku} moved less than ${MEASURE_MIN_USD:,.0f}.")
        return _verdict(d, "measured",
                        f"Ad allocation on {sku} fell ${cut:,.2f} and its net moved from ${before_net:,.2f} to "
                        f"${after['net']:,.2f}. Credit is the smaller of the two — ${credit:,.2f} — because a "
                        f"cut that did not reach the bottom line is not a saving."
                        + ("" if improvement >= 0 else " The SKU got worse despite the cut, and that stands."),
                        usd=round(credit if improvement >= 0 else improvement, 2),
                        attribution="attributable", window=window)

    return _closed(d, f"{sku} is still selling at its old price with the same ad allocation — "
                      f"none of the three routes was taken.", evidence_after={"net_after": after["net"]})


def measure_campaign_trim(d: dict, ads_rows: list[dict], since: date, today: date) -> dict:
    """Gross spend saved is flattery — those dollars were buying something.
    Net saving is the only figure measurement can confirm."""
    ev = d.get("evidence") or {}
    name = ev.get("campaign_name")
    before_spend = float(ev.get("current_spend") or 0)
    avg_margin = float(ev.get("avg_margin") or 0)
    row = next((r for r in ads_rows if r.get("campaign_name") == name), None)
    if row is None:
        return _not_yet(d, f"No ad-efficiency read for “{name}” since the change.")
    after_spend = float(row.get("current_spend") or 0)
    if after_spend >= before_spend:
        return _verdict(d, "measured",
                        f"“{name}” is still spending ${after_spend:,.2f} against ${before_spend:,.2f} — "
                        f"the trim has not happened.", usd=0.0, attribution="isolated")
    cut = before_spend - after_spend
    roas = float(row.get("marginal_roas") or ev.get("marginal_roas") or 0)
    forgone = max(0.0, cut * roas * avg_margin)
    net = cut - forgone
    promised = d.get("expected_impact_usd")
    capped = min(net, float(promised)) if promised is not None and net > float(promised) > 0 else net
    if abs(capped) < MEASURE_MIN_USD:
        return _closed(d, f"The trim on “{name}” netted less than ${MEASURE_MIN_USD:,.0f}.")
    return _verdict(d, "measured",
                    f"“{name}” came down ${cut:,.2f}. At a marginal ROAS of {roas:,.2f} and a "
                    f"{avg_margin:.0%} contribution margin, roughly ${forgone:,.2f} of profit came off with it — "
                    f"a net ${net:,.2f}.",
                    usd=round(capped, 2), attribution="attributable",
                    evidence_after={"spend_after": after_spend, "forgone": round(forgone, 2)})


def measure_branded_pause(d: dict, search_terms: list[dict], margins: list[dict],
                          since: date, today: date) -> dict:
    """The most defensible number in the product, and it is allowed to hurt:
    spend saved less the margin on units that stopped arriving."""
    ev = d.get("evidence") or {}
    brand_terms = [t.lower() for t in (ev.get("brand_terms") or [])]
    baseline_spend = float(ev.get("baseline_spend") or 0)
    avg_margin = float(ev.get("avg_margin") or 0)
    if not brand_terms or baseline_spend <= 0:
        return _closed(d, "No branded-spend baseline recorded on this directive.")

    after = _after_rows(search_terms, since, today)
    if not after:
        return _not_yet(d, f"No search-term export covering {MIN_AFTER_DAYS}+ days since the pause.")
    window = (str(after[0]["period_start"]), str(after[-1]["period_end"]))
    latest_end = max(str(r["period_end"]) for r in after)
    branded = [r for r in after if str(r["period_end"]) == latest_end
               and any(b in (r.get("search_term") or "").lower() for b in brand_terms)]
    spend_after = sum(float(r.get("spend") or 0) for r in branded)
    sales_after = sum(float(r.get("sales_7d") or 0) for r in branded)
    baseline_sales = float(ev.get("baseline_sales") or 0)

    saved = baseline_spend - spend_after
    if saved <= 0:
        return _verdict(d, "measured",
                        f"Branded spend is ${spend_after:,.2f} against ${baseline_spend:,.2f} before — "
                        f"the pause has not happened.", usd=0.0, attribution="isolated", window=window)
    forgone = max(0.0, (baseline_sales - sales_after)) * avg_margin if baseline_sales else 0.0
    net = saved - forgone
    promised = d.get("expected_impact_usd")
    capped = min(net, float(promised)) if promised is not None and net > float(promised) > 0 else net
    note = (f"Branded spend fell from ${baseline_spend:,.2f} to ${spend_after:,.2f} in "
            f"{window[0]} → {window[1]} — ${saved:,.2f} saved"
            + (f", less ${forgone:,.2f} of margin on branded sales that did not arrive." if forgone else
               ", with no measurable fall in branded sales."))
    if net < 0:
        note += " The pause cost more than it saved, and that stands on the record."
    return _verdict(d, "measured", note, usd=round(capped, 2), attribution="attributable",
                    evidence_after={"spend_after": round(spend_after, 2), "forgone": round(forgone, 2)},
                    window=window)


# ── the dispatcher, and the guards no family may skip ────────────────────────

MEASURABLE_STATUSES = ("approved", "done")


def _sku_of(d: dict) -> str | None:
    return (d.get("evidence") or {}).get("sku")


def _dedupe_overlapping(verdicts: list[dict], directives_by_id: dict) -> list[dict]:
    """One dollar, one directive.

    A SKU can carry both a price step and a negative-margin instruction, and
    both read the same margin rows. Oldest directive keeps the dollars; the
    other says where they went. Without this the ledger double-counts the same
    money and the whole exercise is worthless."""
    claimed: dict[tuple, str] = {}
    out = []
    for v in verdicts:
        d = directives_by_id.get(v["directive_id"], {})
        sku = _sku_of(d)
        if v["verdict"] != "measured" or not sku or not v.get("window"):
            out.append(v)
            continue
        key = (sku, v["window"])
        holder = claimed.get(key)
        if holder is None:
            claimed[key] = v["directive_id"]
            out.append(v)
            continue
        out.append(_verdict(d, "unmeasurable",
                            f"The same movement on {sku} over {v['window'][0]} → {v['window'][1]} is already "
                            f"banked on directive {str(holder)[:8]}; counting it twice would inflate the ledger.",
                            window=v["window"]))
    return out


def measure(directives: list[dict], data: dict, margins: list[dict], ads_rows: list[dict],
            claims: list[dict], today: date | None = None, inv_econ: dict | None = None) -> list[dict]:
    """One verdict per directive that is due a measurement.

    `data` is the canonical export dict every model reads (cli._load_data), so
    every number here comes from a file the client sent us."""
    today = today or date.today()
    claims_by_key = {c["claim_key"]: c for c in claims if c.get("claim_key")}
    search_terms = data.get("ppc_search_terms") or []
    econ = data.get("sku_economics") or []
    traffic = data.get("asin_traffic") or []
    inventory = data.get("inventory_levels") or []
    ppc_spend = data.get("ppc_spend") or []

    due = [d for d in directives
           if d.get("status") in MEASURABLE_STATUSES and d.get("measured_at") is None
           # A directive drafted before the measurement contract carries no
           # kind and no evidence. There is nothing to measure it against, and
           # closing it would silently retire work that is genuinely pending —
           # so it is left exactly as it is, for a person to settle.
           and d.get("kind")]
    verdicts = []
    for d in due:
        kind = d.get("kind")
        since = _acted_on(d)
        if kind in UNBANKABLE_KINDS:
            verdicts.append(_closed(
                d, "Executed. No later export can honestly value this one, so the work is on the record "
                   "and no dollars are claimed."))
            continue
        if since is None:
            verdicts.append(_not_yet(d, "No issue or approval date on this directive to measure from."))
            continue
        if kind == "recovery_filing":
            verdicts.append(measure_recovery_filing(d, claims_by_key))
        elif kind == "ad_bleed_terms":
            verdicts.append(measure_ad_bleed(d, search_terms, since, today))
        elif kind in ("fee_anomaly", "referral_anomaly"):
            verdicts.append(measure_fee_anomaly(d, econ, since, today))
        elif kind == "spend_step":
            verdicts.append(measure_spend_step(d, ppc_spend, since, today))
        elif kind == "price_step":
            verdicts.append(measure_price_step(d, margins, traffic, since, today))
        elif kind == "negative_margin_sku":
            verdicts.append(measure_negative_margin(d, margins, inventory, since, today))
        elif kind == "campaign_trim":
            verdicts.append(measure_campaign_trim(d, ads_rows, since, today))
        elif kind == "branded_pause":
            verdicts.append(measure_branded_pause(d, search_terms, margins, since, today))
        elif kind in ("low_inventory_fee", "aged_surcharge", "peak_storage_premium"):
            verdicts.append(measure_fee_bleed(d, inv_econ, since, today))
        elif kind == "liquidation":
            verdicts.append(_closed(
                d, "Liquidation proceeds arrive as a settlement line we cannot separate from ordinary "
                   "sales; the work is recorded and no dollars are claimed."))
        else:
            verdicts.append(_closed(d, f"No measurement family defined for {kind!r}."))

    verdicts = _dedupe_overlapping(verdicts, {d["id"]: d for d in due if d.get("id")})

    # Materiality, applied last so every family gets the same floor.
    final = []
    for v in verdicts:
        usd = v.get("measured_impact_usd")
        if v["verdict"] == "measured" and usd is not None and 0 < abs(usd) < MEASURE_MIN_USD:
            v = {**v, "verdict": "closed", "measured_impact_usd": None, "attribution": "none",
                 "measurement_notes": v["measurement_notes"] + f" Under the ${MEASURE_MIN_USD:,.0f} "
                                                               f"materiality floor, so nothing is banked."}
        final.append(v)
    return final


def to_patch(v: dict, run_id: str | None = None) -> dict | None:
    """The database patch for a verdict, or None when nothing should change."""
    if v["verdict"] == "not_yet":
        return None
    patch = {
        "measurement_notes": v["measurement_notes"],
        "attribution": v["attribution"],
        "measured_run_id": run_id,
    }
    if v["verdict"] in ("measured", "reverted"):
        patch["status"] = "done"
        patch["measured_impact_usd"] = v["measured_impact_usd"]
        patch["measured_at"] = f"{date.today().isoformat()}T00:00:00+00:00"
    else:
        # closed / unmeasurable: the work is recorded, no dollars are claimed.
        patch["status"] = "closed"
        patch["measured_at"] = f"{date.today().isoformat()}T00:00:00+00:00"
    return patch
