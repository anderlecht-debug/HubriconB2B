"""The narration layer — Claude writes, the engine supplies every number.

The one non-negotiable rule of a financial product with a language model
in it: the model never originates a figure. It is enforced here in code,
not in a prompt:

  1. build_facts() renders every number the letter may mention — already
     formatted by the engine — into a keyed FACTS table.
  2. Claude is asked to write the letter using only {{key}} placeholders
     wherever a figure belongs.
  3. validate() rejects any draft containing a digit, a currency or percent
     sign, a number word, or an unknown placeholder. One retry with the
     violations spelled out; a second failure falls back to the template
     letter in briefing.py and says so.
  4. render() substitutes the placeholders from FACTS.

A fabricated number is therefore a validation failure, never a sentence a
client reads. The model choice is an environment variable; the guardrail
is the architecture.
"""

import json
import os
import re
from typing import Callable

DEFAULT_MODEL = "claude-fable-5-1"
FALLBACK_MODEL = "claude-opus-4-8"
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
NUMBER_WORDS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "million", "billion", "dozen", "percent", "half", "third", "quarter",
    "double", "triple", "twice",
}

SYSTEM = """You write the client letters for Hubricon, a Managed Profit service for product brands that sell on Amazon, on Shopify, or both: the money decisions made for them inside their account, every move written on a Profit Record. You draft the client's Profit Brief. Name the client's platform only as the FACTS name it; never assume Amazon.

The one rule you never break: you do not write numbers. No digits, no currency or percent signs, no number words (two, hundred, half, percent...). Every figure appears only as a placeholder in double braces, {{key}}, using a key from the FACTS list exactly as given. If a fact you want is not in FACTS, describe it without a number or leave it out. Never invent a key.

Voice: private-banking restraint. Short sentences. Plain English, no jargon, no hype, no exclamation marks. The client's first name once, in the greeting. Say what was found, what it is worth, what will be done, and how it will be measured. Admit uncertainty where the FACTS carry a range. Never speculate about why a figure is missing or how a decision was made; if a fact is absent, leave the point out. Verbatim facts are complete sentences: do not add a second full stop after them. Close with the record to date, then a final line that reads exactly: — Hubricon"""


def _money(v) -> str:
    v = float(v or 0)
    return ("−" if v < 0 else "") + f"${abs(v):,.0f}"


def _pct(v, digits=1) -> str:
    return f"{float(v) * 100:.{digits}f}%"


def build_facts(company: str, first_name: str, deltas: dict | None, directives: list[dict],
                alerts: list[dict], ledger_measured: float, ledger_count: int, issue_number: int,
                health: dict | None = None, value: dict | None = None, recovery: dict | None = None,
                forecast_rows: list[dict] | None = None, risk: dict | None = None,
                anomaly_summary: dict | None = None, inv_econ: dict | None = None,
                data_quality: dict | None = None) -> dict:
    """key -> {"value": formatted string, "label": what it is}. Only formatted
    strings leave this function; the model never sees a raw float."""
    facts = {
        "company": {"value": company, "label": "client company name"},
        "first_name": {"value": first_name or "there", "label": "client first name"},
        "issue_number": {"value": f"{issue_number:03d}", "label": "this issue's number"},
        "ledger_measured": {"value": _money(ledger_measured), "label": "proven to date on the Profit Record"},
        "ledger_count": {"value": str(ledger_count), "label": "number of moves issued to date"},
    }
    # Split the ledger by how each dollar was proved, so a letter can say
    # "confirmed by Amazon's own record" only where that is literally true.
    # validate() already rejects any number the fact table did not supply; this
    # makes the honest phrasings available rather than leaving the model to
    # characterise a total it cannot see behind.
    tiers = {}
    for d in directives:
        if d.get("measured_impact_usd") is None:
            continue
        tiers.setdefault(d.get("attribution") or "unrecorded", []).append(float(d["measured_impact_usd"]))
    for tier, label in (("direct", "measured from a counterparty's own record (Amazon confirmed it)"),
                        ("isolated", "measured on the exact line the move named"),
                        ("attributable", "measured against a stated counterfactual")):
        if tiers.get(tier):
            facts[f"measured_{tier}"] = {"value": _money(sum(tiers[tier])), "label": label}
            facts[f"measured_{tier}_count"] = {"value": str(len(tiers[tier])),
                                               "label": f"moves {label}"}
    if deltas:
        facts["net_latest"] = {"value": _money(deltas["latest"]["net"]), "label": "true net profit, latest period"}
        facts["revenue_latest"] = {"value": _money(deltas["latest"]["revenue"]), "label": "revenue, latest period"}
        if deltas["latest"].get("pct") is not None:
            facts["margin_pct_latest"] = {"value": _pct(deltas["latest"]["pct"]), "label": "blended net margin, latest period"}
        if deltas.get("net_delta") is not None:
            facts["net_delta"] = {"value": _money(abs(deltas["net_delta"])), "label": "size of the net profit change vs the prior period (unsigned; pair with net_direction)"}
            facts["net_direction"] = {"value": "up" if deltas["net_delta"] >= 0 else "down", "label": "direction of the net profit change"}
        if deltas.get("revenue_delta") is not None:
            facts["revenue_delta"] = {"value": _money(abs(deltas["revenue_delta"])), "label": "size of the revenue change vs the prior period (unsigned; pair with revenue_direction)"}
            facts["revenue_direction"] = {"value": "up" if deltas["revenue_delta"] >= 0 else "down", "label": "direction of the revenue change"}
    issued = [d for d in directives if d.get("status") == "issued"]
    facts["moves_before_they_go_live"] = {"value": str(len(issued)), "label": "moves waiting for the client's yes"}
    for i, d in enumerate(issued[:4], start=1):
        facts[f"decision_{i}"] = {"value": d["action_text"].rstrip("."), "label": f"move {i} waiting for the client's yes, verbatim instruction (no closing period)"}
        if d.get("expected_impact_usd") is not None:
            facts[f"decision_{i}_expected"] = {"value": _money(d["expected_impact_usd"]) + " per period", "label": f"expected impact of decision {i}"}
        else:
            facts[f"decision_{i}_expected"] = {"value": "no dollar estimate in advance; the Profit Record measures it after the fact",
                                               "label": f"expected impact of decision {i} (use this phrase verbatim, do not explain further)"}
    critical = [a for a in alerts if a.get("severity") == "critical"]
    if critical:
        facts["critical_alert"] = {"value": critical[0]["message"].rstrip("."), "label": "the most serious alert from the last sweep, verbatim (no closing period)"}
    if health and health.get("status") == "ok":
        facts["health_score"] = {"value": f"{float(health['score']):.0f}", "label": "Health Score out of one hundred"}
        facts["health_grade"] = {"value": health["grade"], "label": "Health Score letter grade"}
        for i, d in enumerate(health.get("top_drivers", [])[:3], start=1):
            facts[f"health_driver_{i}"] = {"value": d["label"].lower(), "label": f"health driver {i} name"}
            facts[f"health_driver_{i}_dollars"] = {"value": _money(d["dollars_at_stake"]), "label": f"dollars behind health driver {i}"}
    if value:
        facts["value_total"] = {"value": _money(value["value_total"]), "label": "proven to date on the Profit Record (moves + recovered)"}
        facts["fees_paid"] = {"value": _money(value["fees_paid"]), "label": "fees invoiced to date"}
        if value.get("roi_multiple") is not None:
            facts["roi_multiple"] = {"value": f"{float(value['roi_multiple']):.1f}×", "label": "value delivered divided by fees paid"}
        facts["identified_unbanked"] = {"value": _money(value["identified_unbanked"]), "label": "found and filed, not yet measured or paid"}
    if recovery and recovery.get("status") == "ok":
        s = recovery["summary"]
        facts["recovery_live_value"] = {"value": _money(s["live_value"]), "label": "face value of open reimbursement claims"}
        facts["recovery_live_ev"] = {"value": _money(s["live_ev"]), "label": "expected value of open claims after approval odds"}
        facts["recovery_n_live"] = {"value": str(s["n_live"]), "label": "number of open claims"}
        facts["recovery_n_expiring"] = {"value": str(s["n_expiring"]), "label": "claims expiring within two weeks"}
        facts["recovery_reimbursed_90d"] = {"value": _money(s["reimbursed_90d"]), "label": "reimbursements Amazon paid in the last ninety days"}
    if risk:
        var = risk.get("var") or {}
        if var.get("status", "ok") == "ok" and var.get("cvar_95") is not None:
            facts["worst_5pct_net"] = {"value": _money(var.get("worst_5pct_net")), "label": "net profit in the worst five-percent of simulated periods"}
            facts["cvar_95"] = {"value": _money(var["cvar_95"]), "label": "expected shortfall below plan in a bad period (CVaR)"}
        conc = (risk.get("concentration") or {}).get("sku_revenue") or {}
        if conc.get("hhi") is not None:
            facts["top_sku_share"] = {"value": _pct(conc.get("top_share") or 0, 0), "label": "revenue share of the largest SKU"}
            facts["top_sku"] = {"value": str(conc.get("top_item")), "label": "the largest SKU"}
            facts["effective_skus"] = {"value": f"{float(conc.get('effective_n') or 0):.1f}", "label": "effective number of SKUs (inverse HHI)"}
    if forecast_rows:
        ok = [f for f in forecast_rows if f.get("status") == "ok" and f.get("fva_pct") is not None]
        if ok:
            fva = sum(float(f["fva_pct"]) for f in ok) / len(ok)
            facts["forecast_fva"] = {"value": f"{fva:.0f}%", "label": "average forecast accuracy gain over the naive baseline"}
            facts["forecast_skus"] = {"value": str(len(ok)), "label": "SKUs with a backtested forecast"}
    if anomaly_summary and anomaly_summary.get("flagged"):
        facts["anomalies_flagged"] = {"value": str(anomaly_summary["flagged"]), "label": "fee or traffic anomalies flagged"}
        facts["anomalies_dollars"] = {"value": _money(anomaly_summary.get("dollar_impact_total")), "label": "dollar impact per period of flagged fee creep and conversion drops"}
        top = (anomaly_summary.get("top") or [None])[0]
        if top:
            facts["anomaly_top"] = {"value": f"{top.get('metric')} on {top.get('item_id')}", "label": "the largest anomaly, what and where"}
    if inv_econ and inv_econ.get("status") == "ok":
        b = inv_econ["summary"]["bleed"]
        facts["inventory_bleed_month"] = {"value": _money(b["total_month"]), "label": "monthly inventory fee bleed (aged, low-inventory, peak storage)"}
        if inv_econ["summary"].get("liquidation_value"):
            facts["liquidation_value"] = {"value": _money(inv_econ["summary"]["liquidation_value"]), "label": "cash available now from liquidating excess"}
    if data_quality and data_quality.get("status") == "flags":
        worst = data_quality.get("worst_gap")
        if worst:
            facts["worst_data_gap"] = {
                "value": (f"{worst['a'].replace('_', ' ')} and {worst['b'].replace('_', ' ')} disagree on "
                          f"{worst['quantity'].replace('_', ' ')} for {worst['period']} by "
                          f"{float(worst['relative_gap']):.0%}"),
                "label": "the largest disagreement between two of the client's own exports, to fix at the upload"}
        gaps = data_quality.get("gaps") or {}
        if gaps:
            first = next(iter(gaps))
            facts["missing_data_months"] = {
                "value": f"{first.replace('_', ' ')} is missing {', '.join(gaps[first][:3])}",
                "label": "months absent from a report inside its own span (missing, not zero)"}
    return facts


def validate(text: str, facts: dict) -> list[str]:
    """Every way a draft can smuggle a number in. Empty list = clean."""
    problems = []
    for key in PLACEHOLDER.findall(text):
        if key not in facts:
            problems.append(f"unknown placeholder {{{{{key}}}}}")
    stripped = PLACEHOLDER.sub(" ", text)
    if re.search(r"\d", stripped):
        problems.append("contains digits outside placeholders")
    if re.search(r"[$€£%]", stripped):
        problems.append("contains a currency or percent sign outside placeholders")
    words = {w for w in re.findall(r"[a-z]+", stripped.lower())}
    bad = sorted(words & NUMBER_WORDS)
    if bad:
        problems.append("contains number words: " + ", ".join(bad))
    if not stripped.strip():
        problems.append("empty draft")
    return problems


def render(text: str, facts: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(facts[m.group(1)]["value"]), text)


def _prompt(facts: dict, structure: str) -> str:
    table = "\n".join(f"- {{{{{k}}}}}: {v['label']}" for k, v in facts.items())
    return (f"FACTS (use as placeholders exactly; never write their values yourself):\n{table}\n\n"
            f"Write:\n{structure}\n\nReturn the letter only, no preamble.")


LETTER_STRUCTURE = """A Profit Brief of five to seven short paragraphs:
1. 'Profit Brief No. {{issue_number}}' on its own line, then 'Dear {{first_name}},'.
2. The headline: net profit and its direction versus the prior period, on what revenue and margin.
3. The one thing to understand this month — the critical alert if there is one, otherwise the largest opportunity (recovery claims, anomalies, inventory bleed, or the Health Score's top driver), with its dollars.
4. One short paragraph per move waiting for the client's yes: the instruction verbatim, then its expected impact placeholder. After the last one, a single sentence on how the Profit Record measures them.
5. The Health Score and grade, naming the drivers costing the most.
6. The record: value delivered against fees paid, and what is identified but not yet banked.
7. Sign-off."""


def _call_claude(system: str, prompt: str, model: str) -> str:
    import anthropic

    # Identity-linked API keys must name the workspace they act in on every
    # request; the Console shows the id (wrkspc_…) beside the key.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": workspace} if workspace else None,
    )
    response = client.beta.messages.create(
        model=model,
        max_tokens=4000,
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": FALLBACK_MODEL}],
        output_config={"effort": "medium"},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    return "".join(b.text for b in response.content if b.type == "text").strip()


def narrate(facts: dict, structure: str = LETTER_STRUCTURE, call: Callable[[str, str, str], str] | None = None,
            model: str | None = None) -> dict:
    """Returns {"text": rendered letter or None, "model", "attempts", "reason",
    "placeholders": count}. `call` is injectable so tests never touch the network."""
    model = model or os.environ.get("HUBRICON_NARRATOR_MODEL", DEFAULT_MODEL)
    call = call or _call_claude
    prompt = _prompt(facts, structure)
    attempts, problems = 0, []
    for attempt in range(2):
        attempts += 1
        try:
            draft = call(SYSTEM, prompt, model)
        except Exception as err:  # network, auth, refusal — never a client-facing failure
            return {"text": None, "model": model, "attempts": attempts, "reason": f"{type(err).__name__}: {err}", "placeholders": 0}
        problems = validate(draft, facts)
        if not problems:
            return {"text": render(draft, facts), "model": model, "attempts": attempts, "reason": None,
                    "placeholders": len(PLACEHOLDER.findall(draft))}
        prompt = (prompt + "\n\nYour previous draft was rejected by the number guard: "
                  + "; ".join(problems) + ". Rewrite it using placeholders only.")
    return {"text": None, "model": model, "attempts": attempts,
            "reason": "rejected by the number guard: " + "; ".join(problems), "placeholders": 0}


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("HUBRICON_NARRATOR", "on").lower() != "off"


def facts_json(facts: dict) -> str:
    return json.dumps({k: v["value"] for k, v in facts.items()}, indent=2, ensure_ascii=False)
